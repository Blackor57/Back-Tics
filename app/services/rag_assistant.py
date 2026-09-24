# app/services/rag_assistant.py
"""
Asistente de Consulta de Datos Scrapeados (RAG con Ollama).

Recuperación Aumentada por Generación básica:
1. El corpus se construye a partir de los Snapshots almacenados en PostgreSQL
   (datos extraídos por el scraper) y de contexto adicional proporcionado.
2. La pregunta del usuario y los documentos se convierten en embeddings
   mediante Ollama (/api/embed) y se seleccionan los K más similares.
3. El contexto recuperado se inyecta en un prompt y Ollama genera una
   respuesta fundamentada ÚNICAMENTE en esos datos.
"""
import re
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

import httpx
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    EMBEDDING_MODEL,
    EMBEDDING_TIMEOUT_SECONDS,
    OLLAMA_TIMEOUT_SECONDS,
)
from app.models.entities import Snapshot

logger = logging.getLogger("uvicorn.error")

_embed_semaphore: Optional[asyncio.Semaphore] = None


def get_embed_semaphore() -> asyncio.Semaphore:
    global _embed_semaphore
    if _embed_semaphore is None:
        _embed_semaphore = asyncio.Semaphore(2)
    return _embed_semaphore


def _tokenizar(texto: str) -> set:
    """Tokeniza a minúsculas y extrae sólo términos informativos, para fallback sin embeddings."""
    palabras = set(re.findall(r"[a-záéíóúñü]{4,}", texto.lower()))
    return palabras


def construir_documentos(data: Any) -> List[Dict[str, Any]]:
    """
    Convierte los datos de un snapshot (lista de entidades o texto continuo)
    en una lista de documentos {texto, titulo, url, fecha}.
    """
    docs: List[Dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            titulo = str(item.get("titulo") or item.get("title") or "").strip()
            url = str(item.get("url") or item.get("link") or "")
            contenido = str(item.get("contenido") or item.get("contenido_markdown") or "").strip()
            if contenido:
                for parrafo in _dividir_parrafos(contenido):
                    docs.append({"texto": parrafo, "titulo": titulo, "url": url})
            elif titulo:
                docs.append({"texto": titulo, "titulo": titulo, "url": url})
    else:
        for segmento in _dividir_parrafos(str(data or "")):
            docs.append({"texto": segmento, "titulo": "", "url": ""})
    return docs


def _dividir_parrafos(texto: str, max_len: int = 900) -> List[str]:
    """Divide texto continuo en segmentos de tamaño razonable manteniendo párrafos."""
    parrafos = [p.strip() for p in re.split(r"\n+", texto) if len(p.strip()) > 10]
    segmentos: List[str] = []
    buffer = ""
    for p in parrafos:
        if len(buffer) + len(p) > max_len and buffer:
            segmentos.append(buffer.strip())
            buffer = ""
        buffer += ("" if not buffer else " ") + p
    if buffer.strip():
        segmentos.append(buffer.strip())
    return segmentos or [texto[:max_len]]


class RagAssistant:
    """
    Orquesta la consulta RAG: recupera contexto relevante de los snapshots
    y lo alimenta a Ollama para responder la pregunta del usuario.
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_model = EMBEDDING_MODEL

    # ============================================
    # RECUPERACIÓN DEL CORPUS (SNAPSHOTS + EXTRA)
    # ============================================
    async def obtener_corpus(
        self,
        db: AsyncSession,
        url: Optional[str] = None,
        dias: int = 30,
        contexto_extra: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Devuelve la lista de documentos disponibles para consulta RAG."""
        documentos: List[Dict[str, Any]] = []

        stmt = select(Snapshot).where(
            Snapshot.created_at >= datetime.now(timezone.utc) - timedelta(days=max(dias, 1))
        )
        if url:
            stmt = stmt.where(Snapshot.url == url)
        stmt = stmt.order_by(Snapshot.created_at.desc()).limit(200)

        try:
            result = await db.execute(stmt)
            snapshots = result.scalars().all()
        except Exception as e:
            logger.warning(f"No se pudo cargar snapshots para RAG: {str(e)}")
            snapshots = []

        for snapshot in snapshots:
            for doc in construir_documentos(snapshot.data):
                doc["fecha"] = snapshot.created_at.isoformat() if snapshot.created_at else None
                doc["snapshot_id"] = snapshot.id
                doc["url"] = doc.get("url") or snapshot.url
                if not doc.get("titulo"):
                    doc["titulo"] = snapshot.site_title or snapshot.url
                documentos.append(doc)

        if contexto_extra and contexto_extra.strip():
            for segmento in _dividir_parrafos(contexto_extra):
                documentos.append({
                    "texto": segmento,
                    "titulo": "Contexto adicional proporcionado",
                    "url": "",
                    "fecha": datetime.now(timezone.utc).isoformat(),
                    "snapshot_id": None,
                })

        return documentos

    # ============================================
    # EMBEDDINGS VÍA OLLAMA
    # ============================================
    async def _obtener_embedding(self, texto: str) -> Optional[List[float]]:
        """Genera el vector de embedding de un texto usando Ollama /api/embed."""
        def _parsear(data: Dict[str, Any]) -> Optional[List[float]]:
            emb = data.get("embeddings") or data.get("embedding")
            if emb and isinstance(emb, list):
                if emb and isinstance(emb[0], list):
                    return [float(x) for x in emb[0]]
                return [float(x) for x in emb]
            return None

        try:
            async with get_embed_semaphore():
                async with httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT_SECONDS) as client:
                    payload = {"model": self.embedding_model, "input": texto, "options": {"num_gpu": -1}}
                    res = await client.post(f"{self.base_url}/api/embed", json=payload)
                    if res.status_code not in (200, 201):
                        # Ollama antiguo: endpoint /api/embeddings
                        res = await client.post(
                            f"{self.base_url}/api/embeddings",
                            json={"model": self.embedding_model, "prompt": texto},
                        )
                    res.raise_for_status()
                    return _parsear(res.json())
        except Exception as e:
            logger.warning(f"Error al generar embedding con Ollama: {str(e)}")
        return None

    # ============================================
    # RECUPERACIÓN DE CONTEXTO (VECTORIAL + FALLBACK)
    # ============================================
    async def recuperar_contexto(
        self,
        pregunta: str,
        documentos: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Selecciona los K documentos más relevantes para la pregunta usando
        similitud coseno sobre embeddings de Ollama. Si los embeddings fallan,
        aplica un scoring por solapamiento de tokens como respaldo.
        """
        if not documentos:
            return []

        q_emb = await self._obtener_embedding(pregunta)

        if q_emb:
            # Embeddings por lotes de los textos
            todos: List[Optional[List[float]]] = [None] * len(documentos)
            batch = 16
            for i in range(0, len(documentos), batch):
                grupo_docs = documentos[i:i + batch]
                textos = [d["texto"][:1500] for d in grupo_docs]
                try:
                    async with get_embed_semaphore():
                        async with httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT_SECONDS) as client:
                            payload = {"model": self.embedding_model, "input": textos}
                            res = await client.post(f"{self.base_url}/api/embed", json=payload)
                            if res.status_code not in (200, 201):
                                embs = []
                                for txt_ in textos:
                                    e = await self._obtener_embedding(txt_)
                                    if e:
                                        embs.append(e)
                            else:
                                embs = res.json().get("embeddings") or []
                    if not embs:
                        continue
                    for j, emb in enumerate(embs):
                        if i + j < len(todos) and emb:
                            todos[i + j] = [float(x) for x in emb]
                except Exception as e:
                    logger.warning(f"Error en embeddings por lote: {str(e)}")
                    break

            q_vec = np.array(q_emb, dtype=float)
            q_norm = np.linalg.norm(q_vec)
            for idx, doc in enumerate(documentos):
                vec = todos[idx]
                if not vec:
                    continue
                v = np.array(vec, dtype=float)
                denom = q_norm * np.linalg.norm(v)
                score = float(np.dot(q_vec, v) / denom) if denom > 0 else 0.0
                doc = dict(doc)
                # Saber que se recuperó por embeddings
                doc["__score"] = score
                documentos[idx] = doc

            recuperados = [
                d for d in documentos
                if d.get("__score", 0) != 0 or d.get("texto") == pregunta
            ]
            if recuperados:
                recuperados.sort(key=lambda d: d.get("__score", 0), reverse=True)
                return [dict(d) for d in recuperados[:top_k]]

        # Fallback: similitud por tokens (Jaccard/TF)
        tokens_pregunta = _tokenizar(pregunta)
        scored: List[Dict[str, Any]] = []
        for doc in documentos:
            tokens_doc = _tokenizar(doc["texto"])
            if tokens_pregunta and tokens_doc:
                interseccion = len(tokens_pregunta & tokens_doc)
                union = len(tokens_pregunta | tokens_doc)
                score = interseccion / max(union, 1)
            else:
                score = 0.0
            if score > 0:
                doc = dict(doc)
                doc["__score"] = score
                scored.append(doc)

        scored.sort(key=lambda d: d.get("__score", 0), reverse=True)
        return [dict(d) for d in scored[:top_k]]

    # ============================================
    # GENERACIÓN DE RESPUESTA CON OLLAMA
    # ============================================
    async def responder(
        self,
        pregunta: str,
        documentos: List[Dict[str, Any]],
        top_k: int = 5,
        temperatura: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Responde a la pregunta del usuario basándose únicamente en el contexto recuperado.
        Devuelve la respuesta junto con las fuentes utilizadas.
        """
        recuperados = await self.recuperar_contexto(pregunta, documentos, top_k)

        if not recuperados:
            return {
                "respuesta": (
                    "No se encontró contexto suficiente en los datos scrapeados para responder "
                    "esta consulta. Ejecuta un análisis previo (scraping + snapshot) sobre la URL de interés."
                ),
                "fuentes": [],
                "modelo": self.model,
            }

        contexto_formateado = "\n\n".join(
            f"[Fuente {i + 1}] Título: {d.get('titulo', '')} | URL: {d.get('url', 'N/D')}\n{d['texto']}"
            for i, d in enumerate(recuperados)
        )

        prompt = f"""Eres el Asistente de Consulta de Datos Scrapeados de la plataforma SIMAP.
Usa EXCLUSIVAMENTE el contexto proporcionado (datos previamente extraídos por el sistema de monitoreo web)
para responder. No inventes datos, hechos ni nombres. Si el contexto no contiene la información,
indícalo claramente y sugiere qué páginas monitoreadas podrían contenerla.

CONTEXTO EXTRAÍDO DEL MONITOREO:
{contexto_formateado}

PREGUNTA DEL USUARIO:
{pregunta}

Responde en español, de forma clara y concisa (máximo 180 palabras).
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperatura,
                "num_predict": 512,
                "num_ctx": 4096,
            },
        }

        respuesta = ""
        try:
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
                res = await client.post(f"{self.base_url}/api/generate", json=payload)
                res.raise_for_status()
                data = res.json()
                respuesta = (data.get("response") or "").strip()
        except Exception as e:
            logger.error(f"Error al generar respuesta RAG con Ollama: {str(e)}")
            respuesta = (
                "Ollama no está disponible en este momento. "
                "El contexto más relevante recuperado fue:\n\n" + contexto_formateado
            )

        fuentes = [
            {
                "titulo": d.get("titulo", ""),
                "url": d.get("url", ""),
                "extracto": d.get("texto", "")[:300],
                "score": round(float(d.get("__score", 0.0)), 4),
                "fecha": d.get("fecha"),
                "snapshot_id": d.get("snapshot_id"),
            }
            for d in recuperados
        ]

        return {"respuesta": respuesta, "fuentes": fuentes, "modelo": self.model}