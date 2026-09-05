# app/schemas/schemas.py
"""
Esquemas Pydantic para peticiones y respuestas de Scraping e Inteligencia (SIMAP).
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field


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


class AnalyzeRequest(BaseModel):
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/"})
    guardar_snapshot: bool = Field(default=True, description="Almacenar captura histórica en PostgreSQL")
    generar_documentos: bool = Field(default=True, description="Generar reportes Excel y Word con gráficos")


class AnalyzeResponse(BaseModel):
    url: str
    sitio_titulo: str
    snapshot_id: Optional[int] = None
    snapshot_anterior_id: Optional[int] = None
    es_linea_base: bool
    total_items: int
    analisis_ia: Dict[str, Any]
    delta: Optional[Dict[str, Any]] = None
    descargas: Dict[str, Optional[str]]
    created_at: str
