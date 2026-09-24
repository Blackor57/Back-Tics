# chatbot_service/main.py
"""
SIMAP Chatbot RAG - Microservicio 5.

FastAPI que expone /chat en streaming (SSE) para el widget React.
Arranque: garantiza el esquema pgvector y comprueba los modelos de Ollama.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import api
from app.database import close_readonly_pool, engine, ensure_schema
from app.intent import INTENTS
from app.memory import memory
from app.ollama import ollama_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando SIMAP Chatbot RAG...")
    await ensure_schema()

    if not await ollama_client.is_available():
        logger.warning("Ollama no responde en %s. Modelos requeridos: %s y %s",
                       ollama_client.base_url, ollama_client.chat_model, ollama_client.embed_model)
    else:
        modelos = set(await ollama_client.list_models())
        for r in (ollama_client.chat_model, ollama_client.embed_model):
            if not any(r in m for m in modelos):
                logger.warning("Modelo '%s' no detectado. Ejecuta: docker exec simap_ollama ollama pull %s", r, r)

    logger.info("Chatbot RAG listo. Intenciones soportadas: %s", ", ".join(INTENTS))
    try:
        yield
    finally:
        await memory.close()
        await close_readonly_pool()
        await engine.dispose()


app = FastAPI(
    title="SIMAP Chatbot RAG",
    description="Asistente conversacional que consulta PostgreSQL (text-to-SQL + pgvector) "
                "y genera respuestas con Ollama, con memoria de sesión en Redis.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)


@app.get("/")
async def root() -> dict:
    return {
        "servicio": "SIMAP Chatbot RAG",
        "endpoint_chat": "/chat (POST, responde SSE)",
        "health": "/health",
        "admin": ["/admin/sync-from-snapshots", "/admin/backfill-embeddings"],
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8501, reload=True)