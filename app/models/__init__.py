# app/models/__init__.py
"""Módulo de modelos ORM SQLAlchemy de persistencia relacional."""

from app.models.entities import (
    Base,
    User,
    Snapshot,
    AnalysisReport,
    MonitoredTarget,
)

__all__ = [
    "Base",
    "User",
    "Snapshot",
    "AnalysisReport",
    "MonitoredTarget",
]
