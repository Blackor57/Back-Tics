# scraper_service/main.py
import sys
import asyncio
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field
import uvicorn

try:
    from scraper import UniversalScraperNoAI
    from deep_scraper import DeepScraperNoAI
except ImportError:
    from .scraper import UniversalScraperNoAI
    from .deep_scraper import DeepScraperNoAI


@asynccontextmanager
async def lifespan(app: FastAPI):
    if sys.platform == 'win32' and sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    yield


app = FastAPI(
    title="SIMAP - Microservicio de Scraping",
    description="Microservicio dedicado y desacoplado para extracción web, renderizado con Playwright y aislamiento de DOM.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper_indice = UniversalScraperNoAI()
deep_scraper = DeepScraperNoAI()


# ==========================================
# ESQUEMAS PYDANTIC
# ==========================================

class ScrapeIndexRequest(BaseModel):
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/"})


class ItemDetalleRequest(BaseModel):
    titulo: Optional[str] = Field(None, json_schema_extra={"example": "Título de referencia"})
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/noticia-1"})


class DeepScrapeRequest(BaseModel):
    items: List[ItemDetalleRequest] = Field(..., min_length=1)


class FullPipelineRequest(BaseModel):
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/"})
    limit: Optional[int] = Field(default=5, ge=1, le=20)


# ==========================================
# ENDPOINTS DEL MICROSERVICIO
# ==========================================

@app.get("/health", tags=["Salud"])
async def health():
    return {
        "status": "healthy",
        "service": "scraper-service",
        "version": "1.0.0"
    }


@app.post("/scrape/index", summary="Extraer índice o portada con Playwright")
async def scrape_index(payload: ScrapeIndexRequest):
    try:
        url_str = str(payload.url)
        return await scraper_indice.scrape(url_str)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en Scraper Service al procesar índice: {str(e)}"
        )


@app.post("/scrape/deep", summary="Extracción de artículos en profundidad")
async def scrape_deep(payload: DeepScrapeRequest):
    try:
        items_dict = [{"titulo": item.titulo or "", "url": str(item.url)} for item in payload.items]
        articulos_procesados = await deep_scraper.procesar_novedades_en_profundidad(items_dict)
        return {
            "total_procesados": len(articulos_procesados),
            "articulos": articulos_procesados
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en Scraper Service durante Deep Scraping: {str(e)}"
        )


@app.post("/scrape/full-pipeline", summary="Extracción completa de portada y detalle")
async def scrape_full_pipeline(payload: FullPipelineRequest):
    url_str = str(payload.url)
    try:
        resultado_indice = await scraper_indice.scrape(url_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener índice: {str(e)}"
        )

    if resultado_indice.get("tipo_contenido") != "lista_entidades":
        return {
            "url_origen": url_str,
            "sitio_titulo": resultado_indice.get("site_title", ""),
            "total_indexados": 1,
            "total_procesados_profundidad": 1,
            "articulos": [
                {
                    "url": url_str,
                    "titulo_detalle": resultado_indice.get("site_title", ""),
                    "contenido_markdown": resultado_indice.get("data", ""),
                    "caracteres": len(resultado_indice.get("data", ""))
                }
            ]
        }

    noticias_portada = resultado_indice.get("data", [])
    total_encontradas = len(noticias_portada)
    noticias_a_procesar = noticias_portada[:payload.limit]

    try:
        articulos_completos = await deep_scraper.procesar_novedades_en_profundidad(noticias_a_procesar)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en Deep Scraping: {str(e)}"
        )

    return {
        "url_origen": url_str,
        "sitio_titulo": resultado_indice.get("site_title", ""),
        "total_indexados": total_encontradas,
        "total_procesados_profundidad": len(articulos_completos),
        "articulos": articulos_completos
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
