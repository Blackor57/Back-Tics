# chatbot_service/app/sync_service.py
"""
Poblamiento del esquema RAG desde los datos ya scrapeados (MySQL snapshots).

El scraper de SIMAP guarda capturas en la tabla `snapshots` (backend). Este
módulo las ingiere en el modelo normalizado del chatbot:
    snapshots.data  ->  pages + changes
    changes         ->  embeddings (nomic-embed-text, 768 dims)

Se ejecuta a petición (POST /admin/sync-from-snapshots y /admin/backfill-
embeddings) o desde scripts/.
"""
import hashlib
import json
import logging
from typing import Any, Dict, List

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import EMBEDDING_DIM
from app.models import Alert, Change, Page
from app.ollama import OllamaClient
from app.vector_search import _to_vector_literal

logger = logging.getLogger("uvicorn.error")


def _resumir_datos(data: Any) -> str:
    """Convierte el JSON del snapshot en un resumen textual compacto."""
    if isinstance(data, list):
        partes = []
        for item in data[:10]:
            if isinstance(item, dict):
                titulo = str(item.get("titulo") or item.get("title") or "").strip()
                url = str(item.get("url") or item.get("link") or "").strip()
                partes.append(f"- {titulo} {('(' + url + ')') if url else ''}".strip())
            else:
                partes.append(str(item))
        return "\n".join(partes)
    return str(data)[:2000]


async def _obtener_snapshots(session: AsyncSession) -> List[Any]:
    try:
        result = await session.execute(
            text("SELECT id, url, site_title, data, created_at FROM snapshots ORDER BY created_at ASC")
        )
        return list(result.mappings())
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo leer snapshots: %s", e)
        return []


async def _crear_cambio(session: AsyncSession, page: Page, snapshot: Dict[str, Any]) -> Change | None:
    resumen = _resumir_datos(snapshot.get("data"))
    contenido = json.dumps(snapshot.get("data", []), ensure_ascii=False)[:4000]
    cambio_hash = hashlib.md5(f"{snapshot['id']}:{contenido}".encode("utf-8")).hexdigest()

    exists = await session.execute(select(Change.id).where(Change.hash == cambio_hash))
    if exists.scalar_one_or_none():
        return None

    cambio = Change(
        page_id=page.id,
        fecha=snapshot.get("created_at"),
        resumen=resumen[:2000] if resumen else None,
        contenido_diff=contenido,
        hash=cambio_hash,
        tipo="captura_snapshot",
    )
    session.add(cambio)
    await session.flush()
    return cambio


async def sync_from_snapshots(
    session: AsyncSession,
    *,
    max_pages: int = 500,
) -> Dict[str, int]:
    """Ingiere snapshots existentes en pages + changes. Devuelve conteos."""
    snapshots = await _obtener_snapshots(session)
    if not snapshots:
        return {"pages": 0, "changes": 0}

    pages_procesadas = 0
    cambios_creados = 0

    for snap in snapshots[:max_pages]:
        url = snap.get("url")
        if not url:
            continue

        page_result = await session.execute(select(Page).where(Page.url == url))
        page = page_result.scalar_one_or_none()
        if page is None:
            page = Page(
                url=url,
                nombre=snap.get("site_title") or url,
                estado="activa",
                ultima_revision=snap.get("created_at"),
            )
            session.add(page)
            await session.flush()
            pages_procesadas += 1
        else:
            page.ultima_revision = snap.get("created_at") or page.ultima_revision
            if not page.nombre:
                page.nombre = snap.get("site_title")

        cambio = await _crear_cambio(session, page, snap)
        if cambio:
            cambios_creados += 1

    await session.commit()
    return {"pages": pages_procesadas, "changes": cambios_creados}


async def backfill_embeddings(
    session: AsyncSession,
    client: OllamaClient,
    *,
    batch_size: int = 8,
    max_items: int = 2000,
) -> Dict[str, int]:
    """
    Genera embeddings (nomic-embed-text) para los cambios que aún no tienen
    cobertura vectorial. Inserta filas en `embeddings`.
    """
    # Cambios sin embeddings
    stmt = text(
        """
        SELECT c.id, c.resumen, c.contenido_diff
        FROM changes c
        WHERE NOT EXISTS (
            SELECT 1 FROM embeddings e WHERE e.change_id = c.id
        )
        ORDER BY c.id
        LIMIT :max_items
        """
    )
    result = await session.execute(stmt, {"max_items": max_items})
    cambios = list(result.mappings())
    if not cambios:
        return {"embeddings": 0}

    creados = 0
    for i in range(0, len(cambios), batch_size):
        lote = cambios[i:i + batch_size]
        textos: List[str] = []
        for c in lote:
            contenido = (c.get("resumen") or "") + "\n" + (c.get("contenido_diff") or "")
            textos.append((contenido or "").strip()[:2000] or f"Cambio {c['id']}")
        try:
            vectors = await client.embed(textos)
        except Exception as e:  # noqa: BLE001
            logger.warning("Embeddings del lote fallaron: %s", e)
            continue

        for c, vector in zip(lote, vectors):
            if len(vector) != EMBEDDING_DIM:
                continue
            await session.execute(
                text(
                    "INSERT INTO embeddings (change_id, vector, contenido) "
                    "VALUES (:cid, CAST(:vector AS vector), :contenido)"
                ),
                {
                    "cid": c["id"],
                    "vector": _to_vector_literal(vector),
                    "contenido": ((c.get("resumen") or "") + "\n" + (c.get("contenido_diff") or "")).strip()[:4000],
                },
            )
            creados += 1
        await session.commit()

    return {"embeddings": creados}


async def crear_alertas_sin_conexion(session: AsyncSession) -> int:
    """Crea alertas 'sin_revision' para páginas sin cambios en los últimos 7 días."""
    result = await session.execute(
        text(
            """
            INSERT INTO alerts (page_id, tipo, severidad)
            SELECT p.id, 'sin_revision', 'alta'
            FROM pages p
            WHERE NOT EXISTS (
                SELECT 1 FROM changes c
                WHERE c.page_id = p.id
                  AND c.fecha >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            )
            AND NOT EXISTS (
                SELECT 1 FROM alerts a
                WHERE a.page_id = p.id
                  AND a.tipo = 'sin_revision'
                  AND a.fecha >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            )
            """
        )
    )
    await session.commit()
    return result.rowcount or 0