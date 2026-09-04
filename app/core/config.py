import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables desde archivo .env si existe
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

BROWSER_VIEWPORT = {"width": 1440, "height": 900}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

PAGE_TIMEOUT_MS = 30000
DEEP_PAGE_TIMEOUT_MS = 25000

# Límite máximo de scroll en píxeles para detectar Lazy Loading sin bucles infinitos
MAX_SCROLL_HEIGHT_PX = 3000

# =========================================================
# CONFIGURACIÓN DE BASE DE DATOS (POSTGRESQL)
# =========================================================
# Permite postgresql+asyncpg:// para async con SQLAlchemy
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "simap_db")

DEFAULT_DB_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Asegurar driver asyncpg para compatibilidad con SQLAlchemy async y Windows ProactorEventLoop
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

# =========================================================
# CONFIGURACIÓN DE OLLAMA (MICROSERVICIO IA LOCAL)
# =========================================================
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:latest")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180.0"))

# =========================================================
# DIRECTORIO DE REPORTES
# =========================================================
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# CONFIGURACIÓN DE AUTENTICACIÓN JWT
# =========================================================
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "simap-scraper-secret-key-2026-very-secure-random-jwt-token")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 días

# =========================================================
# CONFIGURACIÓN DE CORREO ELECTRÓNICO (SMTP)
# =========================================================
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_USER", "notificaciones@simap.com"))
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")

# =========================================================
# CONFIGURACIÓN DEL MICROSERVICIO DE SCRAPING
# =========================================================
SCRAPER_SERVICE_URL = os.getenv("SCRAPER_SERVICE_URL", "http://localhost:8001")

