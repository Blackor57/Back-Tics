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

# =========================================================
# CONFIGURACIÓN DEL EVENT LOOP EN WINDOWS (LIFESPAN)
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Forzar la política de ProactorEventLoop en Windows al arrancar el servidor
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    yield


app = FastAPI(
    title="Universal Web Scraper API",
    description="API REST modular para la extracción de índices y contenido profundo (Deep Scraping) sin IA.",
    version="1.0.0",
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
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)