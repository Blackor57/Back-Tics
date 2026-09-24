# chatbot_service/app/ollama.py
"""
Cliente HTTP asíncrono para Ollama (httpx).

- generate():           respuesta completa (router, SQL, resumenes).
- generate_stream():    generación en streaming (respuestas finales).
- embed():              embeddings para nomic-embed-text (768 dims).

Un semáforo global limita las peticiones concurrentes a Ollama para respetar
el presupuesto de RAM (< 3 GB). qwen2.5:3b + nomic-embed-text + Redis.
"""
import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.config import (
    MAX_CONCURRENT_OLLAMA_REQUESTS,
    OLLAMA_BASE_URL,
    OLLAMA_CHAT_MODEL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_TIMEOUT_SECONDS,
)

logger = logging.getLogger("uvicorn.error")

_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_OLLAMA_REQUESTS)
    return _semaphore


class OllamaClient:
    """Wraper de la API /api/generate, /api/chat y /api/embed de Ollama."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        chat_model: str = OLLAMA_CHAT_MODEL,
        embed_model: str = OLLAMA_EMBED_MODEL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.timeout = OLLAMA_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception as e:  # noqa: BLE001
            logger.warning("list_models falló: %s", e)
            return []

    @staticmethod
    def _parse_response(data: Dict[str, Any]) -> str:
        """Extrae el texto de la respuesta de /api/generate o /api/chat."""
        if isinstance(data, dict):
            if data.get("message") and isinstance(data.get("message"), dict):
                return data["message"].get("content", "")
            return data.get("response", "")
        return ""

    # ------------------------------------------------------------------
    # Generación completa (no streaming)
    # ------------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        *,
        format: str = "json",
        temperature: float = 0.0,
        num_predict: int = 1024,
    ) -> str:
        """
        Genera una respuesta completa. Por defecto pide JSON estricto a Ollama
        (válido para el router de intención y el generador de SQL).
        """
        payload: Dict[str, Any] = {
            "model": self.chat_model,
            "prompt": prompt,
            "stream": False,
            "format": format,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": OLLAMA_NUM_CTX,
                "stop": ["<|end|>"],
            },
        }
        if system:
            payload["system"] = system

        async with _get_semaphore():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return self._parse_response(resp.json())

    # ------------------------------------------------------------------
    # Streaming (eventos de tokens para la respuesta final)
    # ------------------------------------------------------------------
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.3,
        num_predict: int = 700,
    ) -> AsyncIterator[str]:
        """Genera tokens incrementales vía /api/chat (soporta rol system)."""
        payload: Dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": OLLAMA_NUM_CTX,
                "stop": ["<|end|>"],
            },
        }
        async with _get_semaphore():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("error"):
                            raise RuntimeError(data["error"])
                        chunk = self._parse_response(data)
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            break

    # ------------------------------------------------------------------
    # Embeddings (nomic-embed-text, 768 dimensiones)
    # ------------------------------------------------------------------
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Genera los embeddings de una lista de textos (lote de entrada de Ollama)."""
        if not texts:
            return []
        payload: Dict[str, Any] = {"model": self.embed_model, "input": texts}
        async with _get_semaphore():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/embed", json=payload)
                if resp.status_code not in (200, 201):
                    # Compatibilidad con versiones antiguas de Ollama
                    resp = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.embed_model, "prompt": texts[0]},
                    )
                resp.raise_for_status()
                data = resp.json()

        raw = data.get("embeddings")
        if raw is None:
            raw = data.get("embedding")

        if isinstance(raw, list):
            if raw and isinstance(raw[0], list):
                return [[float(x) for x in emb] for emb in raw]
            return [[float(x) for x in raw]]
        return []

    async def embed_query(self, text: str) -> Optional[List[float]]:
        """Embedding de una sola consulta (devuelve 768 floats o None)."""
        try:
            result = await self.embed([text])
            if result:
                return result[0]
        except Exception as e:  # noqa: BLE001
            logger.warning("embed_query falló: %s", e)
        return None


ollama_client = OllamaClient()