# chatbot_service/app/schemas.py
"""Modelos Pydantic de entrada/salida del endpoint /chat."""
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Cuerpo de la petición /chat (misma forma POST + streaming SSE)."""

    session_id: str = Field(..., min_length=1, max_length=128, description="Identificador de la sesión del navegador.")
    message: str = Field(..., min_length=1, max_length=2000, description="Mensaje del usuario.")
    stream: bool = Field(True, description="Reservado: el endpoint siempre responde en streaming SSE.")


class ChatTurn(BaseModel):
    """Un turno almacenado en Redis (memoria de conversación)."""

    role: str
    content: str
    ts: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    ollama: bool = False
    postgres: bool = False
    redis: bool = False


class BackfillResponse(BaseModel):
    pages_procesadas: int = 0
    cambios_creados: int = 0
    embeddings_creados: int = 0
    mensaje: str = ""