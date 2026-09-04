# main.py

import sys
import asyncio
from contextlib import asynccontextmanager
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
import uvicorn

from app.api.v1.endpoint import router as scrape_router
from app.api.v1.auth import router as auth_router
from app.api.v1.tracking import router as tracking_router
from app.core.database import init_db
from app.services.monitor_scheduler import MonitorScheduler

# =========================================================
# CONFIGURACIÓN DEL EVENT LOOP EN WINDOWS (LIFESPAN)
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Política de event loop en Windows si es menor a Python 3.14
    if sys.platform == 'win32' and sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    
    # Inicializar tablas en PostgreSQL
    await init_db()

    # Iniciar el motor de monitoreo continuo en segundo plano
    await MonitorScheduler.iniciar()

    try:
        yield
    finally:
        await MonitorScheduler.detener()


app = FastAPI(
    title="Universal Web Scraper & Intelligence API",
    description="API REST modular para scraping universal, gestión de usuarios JWT, monitoreo continuo de páginas con alertas por correo y análisis inteligente con Ollama.",
    version="2.1.0",
    lifespan=lifespan
)

# =========================================================
# CONFIGURACIÓN DE CORS
# Permite comunicación fluida con clientes frontend (React, Vite, Next, etc.)
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# RUTAS Y ENDPOINTS
# =========================================================
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(tracking_router, prefix="/api/v1/tracking")
app.include_router(scrape_router, prefix="/api/v1")



@app.get("/", tags=["General"])
async def root():
    return {
        "message": "Universal Web Scraper API está en funcionamiento",
        "docs": "/docs",
        "version": "1.0.0",
        "status": "online"
    }


@app.get("/health", tags=["General"])
async def health_check():
    return {
        "status": "healthy"
    }


# =========================================================
# EJECUCIÓN DIRECTA
# =========================================================
if __name__ == "__main__":
    if sys.platform == 'win32' and sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)