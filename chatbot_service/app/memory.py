# chatbot_service/app/memory.py
"""
Memoria de conversación con Redis (async).

Guarda los últimos CHAT_HISTORY_TURNS turnos (usuario + asistente) por
session_id como lista de objetos JSON bajo la clave simap:chat:{session_id}.
Usa LIST + LTRIM para mantener acotada la ventana de contexto.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import redis.asyncio as aioredis

from app.config import (
    CHAT_HISTORY_TURNS,
    MEMORY_KEY_PREFIX,
    MEMORY_TTL_SECONDS,
    REDIS_URL,
)

logger = logging.getLogger("uvicorn.error")


class RedisMemory:
    """Memoria de sesión basada en Redis."""

    def __init__(self, url: str = REDIS_URL) -> None:
        self.url = url
        self._redis: aioredis.Redis | None = None

    async def _client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.url, decode_responses=True)
        return self._redis

    @staticmethod
    def _key(session_id: str) -> str:
        return f"{MEMORY_KEY_PREFIX}:{session_id}"

    def _max_len(self) -> int:
        # 2 mensajes por turno (usuario + asistente)
        return max(CHAT_HISTORY_TURNS * 2, 2)

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Recupera los últimos turnos de la sesión (más antiguo -> más reciente)."""
        try:
            r = await self._client()
            raw = await r.lrange(self._key(session_id), 0, -1)
            history: List[Dict[str, Any]] = []
            for item in raw:
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, dict):
                        history.append(parsed)
                except (json.JSONDecodeError, TypeError):
                    continue
            return history
        except Exception as e:  # noqa: BLE001 - la memoria nunca debe romper el chat
            logger.warning("No se pudo leer la memoria Redis (%s): %s", session_id, e)
            return []

    async def add_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        """Guarda un turno completo y recorta la lista al máximo de turnos."""
        try:
            r = await self._client()
            key = self._key(session_id)
            now = datetime.now(timezone.utc).isoformat()
            pipeline = r.pipeline()
            pipeline.rpush(
                key,
                json.dumps({"role": "user", "content": user_message, "ts": now}),
                json.dumps({"role": "assistant", "content": assistant_message, "ts": now}),
            )
            pipeline.ltrim(key, -self._max_len(), -1)
            pipeline.expire(key, MEMORY_TTL_SECONDS)
            await pipeline.execute()
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo guardar en Redis (%s): %s", session_id, e)

    async def clear(self, session_id: str) -> None:
        """Borra el historial de una sesión."""
        try:
            r = await self._client()
            await r.delete(self._key(session_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo limpiar la sesión (%s): %s", session_id, e)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


memory = RedisMemory()