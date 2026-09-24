# chatbot_service/app/database.py
"""
Motor asíncrono SQLAlchemy (asyncpg) + pool asyncpg de SOLO LECTURA.

Dos zonas de acceso a PostgreSQL:
1. `AsyncSession` (SQLAlchemy): consultas ORM/estructuradas (páginas, cambios, alertas).
2. `readonly_pool` (asyncpg plano): ejecución del SQL generado por el LLM dentro
   de una transacción READ ONLY (defensa frente a prompts maliciosos).
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import ASYNC_PG_URL, DATABASE_URL, SQL_TIMEOUT_SECONDS

logger = logging.getLogger("uvicorn.error")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

# Pool exclusivo para el text-to-SQL (sólo lectura).
_readonly_pool: asyncpg.Pool | None = None


async def get_readonly_pool() -> asyncpg.Pool:
    """Devuelve (creando bajo demanda) el pool asyncpg de sólo-lectura."""
    global _readonly_pool
    if _readonly_pool is None:
        _readonly_pool = await asyncpg.create_pool(
            ASYNC_PG_URL, min_size=1, max_size=4, timeout=SQL_TIMEOUT_SECONDS  # type: ignore[arg-type]
        )
    return _readonly_pool


async def close_readonly_pool() -> None:
    """Cierra el pool de sólo-lectura (útil en el lifespan de la app)."""
    global _readonly_pool
    if _readonly_pool is not None:
        await _readonly_pool.close()
        _readonly_pool = None


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Sesión SQLAlchemy asíncrona reutilizable con `async with`.

    *No* es apta como `Depends(...)` de FastAPI porque `@asynccontextmanager`
    envuelve el generator; para las rutas usa `get_db()`.
    """
    async with SessionLocal() as session:
        yield session


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI: yield de una `AsyncSession` con `async with`.

    FastAPI admite *dependencies* que son *async generators* (con `yield`).
    Este es el acceso correcto para las rutas (`Depends(get_db)`).
    """
    async with get_session() as session:
        yield session


_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pages (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    nombre TEXT,
    ultima_revision TIMESTAMPTZ,
    estado VARCHAR(20) NOT NULL DEFAULT 'activa',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
CREATE INDEX IF NOT EXISTS idx_pages_estado ON pages(estado);

CREATE TABLE IF NOT EXISTS changes (
    id SERIAL PRIMARY KEY,
    page_id INT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    fecha TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resumen TEXT,
    contenido_diff TEXT,
    hash TEXT UNIQUE,
    tipo VARCHAR(30) NOT NULL DEFAULT 'cambio'
);
CREATE INDEX IF NOT EXISTS idx_changes_page_fecha ON changes(page_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_changes_fecha ON changes(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_changes_hash ON changes(hash);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    page_id INT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    tipo VARCHAR(50) NOT NULL DEFAULT 'cambio_detectado',
    severidad VARCHAR(20) NOT NULL DEFAULT 'media',
    fecha TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alerts_page_fecha ON alerts(page_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_severidad ON alerts(severidad);
CREATE INDEX IF NOT EXISTS idx_alerts_fecha ON alerts(fecha DESC);

CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    change_id INT NOT NULL REFERENCES changes(id) ON DELETE CASCADE,
    vector vector(768) NOT NULL,
    contenido TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_embeddings_change ON embeddings(change_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING hnsw (vector vector_cosine_ops);
"""


async def ensure_schema() -> None:
    """
    Crea (idempotente) la extensión pgvector y las tablas del chatbot.
    Ejecutado en el arranque para cubrir volúmenes de Postgres ya inicializados
    (donde init.sql de docker-entrypoint no vuelve a correr).
    """
    async with engine.begin() as conn:
        for statement in _SCHEMA_SQL.split(";"):
            stmt = statement.strip()
            if stmt:
                try:
                    await conn.execute(text(stmt))
                except Exception as e:  # noqa: BLE001 - no romper el arranque por una sentencia
                    logger.warning("Schema idle: %s -> %s", stmt.splitlines()[0] if stmt else "", e)
    logger.info("Esquema del chatbot (pgvector, pages, changes, alerts, embeddings) verificado.")