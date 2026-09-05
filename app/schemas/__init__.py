# app/schemas/__init__.py
"""Módulo de esquemas de validación Pydantic para SIMAP."""

from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    ResendVerificationRequest,
    MessageResponse,
)
from app.schemas.tracking import (
    TrackTargetCreate,
    TrackTargetUpdate,
    TrackTargetResponse,
)
from app.schemas.schemas import (
    ScrapeIndexRequest,
    ItemDetalleRequest,
    DeepScrapeRequest,
    FullPipelineRequest,
    ScrapeIndexResponse,
    ArticuloDetalleResponse,
    DeepScrapeResponse,
    FullPipelineResponse,
    AnalyzeRequest,
    AnalyzeResponse,
)

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "ResendVerificationRequest",
    "MessageResponse",
    "TrackTargetCreate",
    "TrackTargetUpdate",
    "TrackTargetResponse",
    "ScrapeIndexRequest",
    "ItemDetalleRequest",
    "DeepScrapeRequest",
    "FullPipelineRequest",
    "ScrapeIndexResponse",
    "ArticuloDetalleResponse",
    "DeepScrapeResponse",
    "FullPipelineResponse",
    "AnalyzeRequest",
    "AnalyzeResponse",
]
