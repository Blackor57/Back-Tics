# chatbot_service/app/config.py
"""
Configuración central del microservicio de chatbot.
Todas las valores se inyectan por variables de entorno (ver docker-compose.yml).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# BASE DE DATOS POSTGRESQL (SQLAlchemy async + asyncpg)
# =========================================================
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres_password")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "simap_db")

DEFAULT_DB_URL = (
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

# DSN plano (sin driver) para el pool asyncpg de sólo-lectura que ejecuta el
# SQL generado por el LLM (frontera de seguridad adicional del text-to-SQL).
ASYNC_PG_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# =========================================================
# REDIS (memoria de conversación)
# =========================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHAT_HISTORY_TURNS = int(os.getenv("CHAT_HISTORY_TURNS", "10"))
MEMORY_TTL_SECONDS = int(os.getenv("MEMORY_TTL_SECONDS", str(24 * 3600)))
MEMORY_KEY_PREFIX = "simap:chat"

# =========================================================
# OLLAMA (IA local, bajo consumo)
# =========================================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300.0"))
# Máximo de llamadas concurrentes a Ollama -> protege la RAM (1 = frugal).
MAX_CONCURRENT_OLLAMA_REQUESTS = int(os.getenv("MAX_CONCURRENT_OLLAMA_REQUESTS", "1"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

# =========================================================
# PARÁMETROS DEL PIPELINE RAG
# =========================================================
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "6"))
SQL_MAX_ROWS = int(os.getenv("SQL_MAX_ROWS", "100"))
SQL_TIMEOUT_SECONDS = float(os.getenv("SQL_TIMEOUT_SECONDS", "15.0"))
FINAL_MAX_TOKENS = int(os.getenv("FINAL_MAX_TOKENS", "700"))