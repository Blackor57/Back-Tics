# chatbot_service/app/api.py
"""
Router FastAPI del chatbot:
- POST /chat             : pipeline RAG completo con respuesta en streaming SSE.
- GET  /health           : estado de Ollama, PostgreSQL y Redis.
- POST /admin/sync       : ingiere snapshots en pages/changes.
- POST /admin/backfill   : genera embeddings para los cambios faltantes.
"""
import json
import logging
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import sync_service
from app.config import VECTOR_TOP_K
from app.database import get_db, get_session
from app.intent import IntentRouter
from app.memory import memory
from app.ollama import OllamaClient, ollama_client
from app.orchestrate import ChatPipeline
from app.schemas import BackfillResponse, ChatRequest, HealthResponse
from app.vector_search import VectorSearch

logger = logging.getLogger("uvicorn.error")

router = APIRouter()


def _build_pipeline(client: OllamaClient) -> ChatPipeline:
    return ChatPipeline(
        client=client,
        memory=memory,
        router=IntentRouter(client),
        vector_search=VectorSearch(client, top_k=VECTOR_TOP_K),
    )


async def _stream_with_memory(
    pipeline: ChatPipeline,
    session_id: str,
    message: str,
) -> AsyncGenerator[str, None]:
    """Envuelve el pipeline y persiste el turno completo en Redis al finalizar."""
    assistant_parts: list[str] = []
    try:
        async for event in pipeline.chat(session_id, message):
            yield event
            if event.startswith("data: "):
                try:
                    payload = json.loads(event[6:])
                    if payload.get("content"):
                        assistant_parts.append(payload["content"])
                except json.JSONDecodeError:
                    pass
    except Exception:  # noqa: BLE001
        logger.exception("Streaming interrumpido.")
    finally:
        try:
            if assistant_parts:
                await memory.add_turn(session_id, message, "".join(assistant_parts))
        except Exception:  # noqa: BLE001
            logger.warning("No se pudo guardar el turno en Redis.")


@router.post(
    "/chat",
    summary="Chat RAG de SIMAP con respuesta en streaming (SSE)",
    description="Recibe {session_id, message} y devuelve eventos Server-Sent Events: "
    "intent, source, token y done.",
)
async def chat(payload: ChatRequest) -> StreamingResponse:
    pipeline = _build_pipeline(ollama_client)

    async def event_stream() -> AsyncGenerator[str, None]:
        # Ping inicial para mantener la conexión viva
        yield f"event: keepalive\ndata: {json.dumps({'ok': True})}\n\n"
        async for event in _stream_with_memory(pipeline, payload.session_id, payload.message):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/health", response_model=HealthResponse, summary="Estado de dependencias")
async def health() -> HealthResponse:
    import redis.asyncio as aioredis

    ollama_ok = await ollama_client.is_available()
    postgres_ok = True
    redis_ok = True
    try:
        async with get_session() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        logger.warning("health: Postgres no responde -> %s: %s", type(e).__name__, str(e)[:220])
        postgres_ok = False
    try:
        r = aioredis.from_url(memory.url, decode_responses=True)
        await r.ping()
        await r.aclose()
    except Exception:  # noqa: BLE001
        redis_ok = False
    return HealthResponse(
        status="healthy" if (ollama_ok and postgres_ok and redis_ok) else "degraded",
        ollama=ollama_ok,
        postgres=postgres_ok,
        redis=redis_ok,
    )


@router.post(
    "/admin/sync-from-snapshots",
    response_model=BackfillResponse,
    summary="Ingesta de snapshots existentes en pages/changes",
)
async def sync_snapshots(db: AsyncSession = Depends(get_db)) -> BackfillResponse:
    try:
        conteo = await sync_service.sync_from_snapshots(db)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error en /admin/sync-from-snapshots")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return BackfillResponse(
        pages_procesadas=conteo["pages"],
        cambios_creados=conteo["changes"],
        embeddings_creados=0,
        mensaje="Snapshots ingeridos correctamente.",
    )


@router.post(
    "/admin/backfill-embeddings",
    response_model=BackfillResponse,
    summary="Genera embeddings pgvector para los cambios sin cobertura",
)
async def backfill(db: AsyncSession = Depends(get_db)) -> BackfillResponse:
    try:
        conteo = await sync_service.backfill_embeddings(db, ollama_client)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error en /admin/backfill-embeddings")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return BackfillResponse(
        pages_procesadas=0,
        cambios_creados=0,
        embeddings_creados=conteo["embeddings"],
        mensaje="Embeddings generados correctamente.",
    )


@router.get("/session/{session_id}/clear", summary="Borra el historial de una sesión")
async def clear_session(session_id: str) -> Dict[str, Any]:
    await memory.clear(session_id)
    return {"ok": True, "session_id": session_id}