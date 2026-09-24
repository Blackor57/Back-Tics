# chatbot_service/app/models.py
"""
Modelos SQLAlchemy del esquema RAG del chatbot.
Sólo mapean las tablas (no crean el vector column, que se gestiona con SQL
directo en vector_search.py). El esquema completo se asegura con DDL
idempotente en database.ensure_schema() / init.sql.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    nombre: Mapped[Optional[str]] = mapped_column(Text)
    ultima_revision: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(20), default="activa")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Change(Base):
    __tablename__ = "changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resumen: Mapped[Optional[str]] = mapped_column(Text)
    contenido_diff: Mapped[Optional[str]] = mapped_column(Text)
    hash: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    tipo: Mapped[str] = mapped_column(String(30), default="cambio")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(50), default="cambio_detectado")
    severidad: Mapped[str] = mapped_column(String(20), default="media")
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)