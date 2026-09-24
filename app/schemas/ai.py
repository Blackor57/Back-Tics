# app/schemas/ai.py
"""
Esquemas Pydantic para los módulos de IA de SIMAP:
- Asistente RAG de consulta sobre datos scrapeados.
- Transcripción de medios (faster-whisper + Ollama).
- Agente de Monitoreo Autónomo (function calling con Ollama).
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


# =========================================================
# ASISTENTE RAG (CONSULTA SOBRE DATOS SCRAPEADOS)
# =========================================================
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Pregunta del usuario sobre los datos scrapeados.")
    url: Optional[str] = Field(None, description="Restringir la búsqueda a esta URL monitoreada.")
    top_k: int = Field(5, ge=1, le=20, description="Cantidad de fragmentos de contexto a recuperar.")
    dias: int = Field(30, ge=1, le=365, description="Ventana temporal de snapshots a considerar.")
    contexto_extra: Optional[str] = Field(None, description="Texto adicional (ej. una transcripción reciente) para incluir en el corpus.")
    temperatura: float = Field(0.2, ge=0.0, le=1.0, description="Temperatura de generación del LLM.")


class FuenteRagResponse(BaseModel):
    titulo: str
    url: str
    extracto: str
    score: float
    fecha: Optional[str] = None
    snapshot_id: Optional[int] = None


class AskResponse(BaseModel):
    pregunta: str
    respuesta: str
    fuentes: List[FuenteRagResponse]
    modelo: str
    total_fragmentos: int


# =========================================================
# TRANSCRIPCIÓN DE MEDIOS
# =========================================================
class TranscribeRequest(BaseModel):
    media_url: Optional[HttpUrl] = Field(None, description="URL directa de audio/video o plataforma (YouTube, Vimeo...).")
    pagina_origen: Optional[HttpUrl] = Field(None, description="URL de la página scrapeada de la que detectar medios.")
    idioma: Optional[str] = Field("es", description="Código de idioma para whisper (ISO 639-1).")
    resumir: bool = Field(True, description="Generar resumen estructurado con Ollama al final.")
    incluir_segmentos: bool = Field(False, description="Incluir la lista de segmentos con marcas de tiempo.")
    modelo_whisper: Optional[str] = Field(None, description="Tamaño del modelo whisper (tiny/base/small/medium).")


class TranscribeResponse(BaseModel):
    url: str
    ruta_archivo: Optional[str] = None
    titulo: Optional[str] = None
    formato: Optional[str] = None
    duracion_segundos: Optional[float] = None
    transcripcion: Optional[str] = None
    idioma_detectado: Optional[str] = None
    segmentos: Optional[List[Dict[str, Any]]] = None
    resumen_ia: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# =========================================================
# AGENTE DE MONITOREO AUTÓNOMO
# =========================================================
class AgentProcesarRequest(BaseModel):
    contexto: str = Field(..., min_length=10, description="Contenido recién detectado (novedades del scraping).")
    instrucciones: Optional[str] = Field(None, description="Instrucciones extra de criterio para el agente.")
    url_fuente: Optional[str] = Field(None, description="URL de origen del contenido analizado.")
    destinatario: Optional[str] = Field(None, description="Correo destino para alertas (por defecto: administrador).")


class AgentSobreUrlRequest(BaseModel):
    url: HttpUrl = Field(..., description="Página a inspeccionar de forma autónoma: scrape + delta + agente.")
    instrucciones: Optional[str] = Field(None, description="Criterio personalizado para el análisis del agente.")
    destinatario: Optional[str] = Field(None, description="Correo destino del administrador.")


class AccionAgenteResponse(BaseModel):
    herramienta: str
    argumentos: Dict[str, Any]
    resultado: Optional[Any] = None
    ok: bool
    canal: str


class AgentProcesarResponse(BaseModel):
    respuesta: str
    acciones: List[AccionAgenteResponse]


class EventoAgenteResponse(BaseModel):
    id: int
    tipo_evento: str
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    url_fuente: Optional[str] = None
    nivel_prioridad: Optional[str] = None
    canal: Optional[str] = None
    razon_ia: Optional[str] = None
    created_at: Optional[str] = None


class ConsultaMediaRequest(BaseModel):
    datos: Any = Field(..., description="Resultado de scraping (lista de ítems o texto) donde detectar media.")
    max_resultados: int = Field(10, ge=1, le=50)


class ConsultaMediaResponse(BaseModel):
    detectadas: List[Dict[str, Any]]
    total: int