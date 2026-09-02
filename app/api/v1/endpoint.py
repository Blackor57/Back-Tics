# endpoint.py

from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, status
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, HttpUrl, Field

from app.services.scraper import UniversalScraperNoAI
from app.services.deep_scraper import DeepScraperNoAI

router = APIRouter(prefix="/scrape", tags=["Scraper"])

# Instanciamos los scrapers
scraper_indice = UniversalScraperNoAI()
deep_scraper = DeepScraperNoAI()


# ==========================================
# ESQUEMAS DE PETICIÓN Y RESPUESTA (PYDANTIC)
# ==========================================

class ScrapeIndexRequest(BaseModel):
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/"})


class ItemDetalleRequest(BaseModel):
    titulo: Optional[str] = Field(None, json_schema_extra={"example": "Título opcional del artículo en portada"})
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/peru/actualidad/sismo-en-peru-igp-reporto-temblor-noticia-1500000"})


class DeepScrapeRequest(BaseModel):
    items: List[ItemDetalleRequest] = Field(
        ..., 
        min_length=1,
        description="Lista de URLs/items detectados como novedades para extraer su contenido completo."
    )


class FullPipelineRequest(BaseModel):
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/"})
    limit: Optional[int] = Field(
        default=5, 
        ge=1, 
        le=20, 
        description="Número máximo de noticias de la portada a las que se les hará Deep Scraping."
    )


class ScrapeIndexResponse(BaseModel):
    url: str
    site_title: str
    tipo_contenido: str
    total_items: int
    data: Any


class ArticuloDetalleResponse(BaseModel):
    url: str
    titulo: Optional[str] = None
    titulo_detalle: str
    contenido_markdown: str
    caracteres: int
    error: Optional[str] = None


class DeepScrapeResponse(BaseModel):
    total_procesados: int
    articulos: List[ArticuloDetalleResponse]


class FullPipelineResponse(BaseModel):
    url_origen: str
    sitio_titulo: str
    total_indexados: int
    total_procesados_profundidad: int
    articulos: List[Dict[str, Any]]


# ==========================================
# ENDPOINTS HTTP POST
# ==========================================

@router.post(
    "/index", 
    response_model=ScrapeIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Extraer índice o listado principal (Nivel 1)"
)
async def scrape_index(payload: ScrapeIndexRequest):
    """
    Recibe una URL objetivo, navega mediante Playwright, dispara el auto-scroll
    y extrae la lista de títulos y enlaces o el texto continuo si es un artículo único.
    """
    try:
        url_str = str(payload.url)
        resultado = await scraper_indice.scrape(url_str)
        return resultado
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado al procesar el índice: {str(e)}"
        )


@router.post(
    "/deep", 
    response_model=DeepScrapeResponse,
    status_code=status.HTTP_200_OK,
    summary="Extraer contenido completo de novedades (Nivel 2 - Deep Scraping)"
)
async def scrape_deep(payload: DeepScrapeRequest):
    """
    Recibe una lista de objetos que contienen URLs nuevas y realiza Deep Scraping 
    aislando el texto del artículo con Readability y convirtiéndolo a Markdown limpio.
    """
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
            detail=f"Error inesperado durante el Deep Scraping: {str(e)}"
        )


@router.post(
    "/full-pipeline",
    response_model=FullPipelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Scrapear portada y hacer Deep Scraping automáticamente (Todo en uno)"
)
async def scrape_full_pipeline(payload: FullPipelineRequest):
    """
    Recibe la URL de una portada/índice, obtiene la lista de noticias principales
    y automáticamente realiza Deep Scraping del contenido completo de cada una.
    """
    url_str = str(payload.url)

    # PASO 1: Extraer el índice de la portada (Nivel 1)
    try:
        resultado_indice = await scraper_indice.scrape(url_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener el índice de la portada: {str(e)}"
        )

    # Caso A: Si la página resulta ser un artículo individual o texto continuo
    if resultado_indice["tipo_contenido"] != "lista_entidades":
        return {
            "url_origen": url_str,
            "sitio_titulo": resultado_indice["site_title"],
            "total_indexados": 1,
            "total_procesados_profundidad": 1,
            "articulos": [
                {
                    "url": url_str,
                    "titulo_detalle": resultado_indice["site_title"],
                    "contenido_markdown": resultado_indice["data"],
                    "caracteres": len(resultado_indice["data"])
                }
            ]
        }

    # Caso B: La portada devolvió una lista de noticias
    noticias_portada = resultado_indice["data"]
    total_encontradas = len(noticias_portada)

    # Recortar la lista al límite indicado por el usuario
    noticias_a_procesar = noticias_portada[:payload.limit]

    # PASO 2: Realizar Deep Scraping automático (Nivel 2)
    try:
        articulos_completos = await deep_scraper.procesar_novedades_en_profundidad(noticias_a_procesar)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la fase de Deep Scraping: {str(e)}"
        )

    return {
        "url_origen": url_str,
        "sitio_titulo": resultado_indice["site_title"],
        "total_indexados": total_encontradas,
        "total_procesados_profundidad": len(articulos_completos),
        "articulos": articulos_completos
    }