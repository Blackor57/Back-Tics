# database.py
import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import DATABASE_URL
from app.models.entities import Base

logger = logging.getLogger("uvicorn.error")

# Crear el motor asíncrono para PostgreSQL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Creador de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def init_db() -> bool:
    """
    Inicializa las tablas en la base de datos PostgreSQL si aún no existen.
    Devuelve True si la conexión fue exitosa, o False si PostgreSQL aún no está disponible.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;"))
            except Exception:
                pass
        logger.info("✅ Conexión con PostgreSQL establecida y tablas verificadas exitosamente.")
        return True
    except Exception as e:
        logger.warning(
            f"⚠️ No se pudo conectar a PostgreSQL en {DATABASE_URL}: {str(e)}\n"
            f"Verifique que el servicio de PostgreSQL esté en ejecución y las credenciales sean correctas."
        )
        return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Inyector de dependencias para endpoints de FastAPI que requieran sesión de base de datos.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
