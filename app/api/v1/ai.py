# app/api/v1/ai.py
"""
Endpoints de Inteligencia Avanzada (SIMAP AI):
- /ask                   -> Asistente RAG: responder preguntas con datos scrapeados (Ollama).
- /transcribe            -> Transcripción local de audios/videos (faster-whisper + Ollama).
- /media/detect          -> Detección de URLs de audio/video en datos scrapeados.
- /agent/process         -> Agente de Monitoreo Autónomo (function calling vía Ollama).
- /agent/run-on-url      -> Ciclo completo: scrape + delta + agente autónomo.
- /agent/events          -> Historial de eventos generados por el agente.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_optional_current_user
from app.models.entities import User, AgentEvent
from app.schemas.ai import (
    AskRequest,
    AskResponse,
    TranscribeRequest,
    TranscribeResponse,
    AgentProcesarRequest,
    AgentProcesarResponse,
    AgentSobreUrlRequest,
    ConsultaMediaRequest,
    ConsultaMediaResponse,
    EventoAgenteResponse,
)
from app.services.rag_assistant import RagAssistant
from app.services.media_transcriber import MediaTranscriber, detectar_urls_media
from app.services.monitoring_agent import MonitoringAgent

router = APIRouter(tags=["Inteligencia Avanzada (RAG, Whisper y Agente)"])

rag = RagAssistant()
transcriber = MediaTranscriber()
agente = MonitoringAgent()


# =========================================================
# ASISTENTE RAG: PREGUNTAS SOBRE DATOS SCRAPEADOS
# =========================================================
@router.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Responder preguntas del usuario basándose en los datos scrapeados (RAG con Ollama)"
)
async def ask_data_assistant(
    payload: AskRequest,
    _current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe una pregunta (ej. "¿Qué dijo el alcalde sobre el presupuesto hoy?") y responde
    usando únicamente el contexto de los datos extraídos por el scraping (snapshots en PostgreSQL).
    """
    documentos = await rag.obtener_corpus(
        db=db,
        url=payload.url,
        dias=payload.dias,
        contexto_extra=payload.contexto_extra,
    )
    resultado = await rag.responder(
        pregunta=payload.question,
        documentos=documentos,
        top_k=payload.top_k,
        temperatura=payload.temperatura,
    )
    return {
        "pregunta": payload.question,
        "respuesta": resultado["respuesta"],
        "fuentes": resultado["fuentes"],
        "modelo": resultado["modelo"],
        "total_fragmentos": len(documentos),
    }


# =========================================================
# TRANSCRIPCIÓN DE MEDIOS (faster-whisper + Ollama)
# =========================================================
@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    status_code=status.HTTP_200_OK,
    summary="Descargar audio/video y transcribirlo localmente (faster-whisper + resumen Ollama)"
)
async def transcribe_media(
    payload: TranscribeRequest,
    _current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Dada una URL de audio/video (o una página detectada por el scraping), descarga el archivo,
    lo transcribe con faster-whisper y (opcional) genera un resumen con Ollama.
    """
    try:
        resultado = await transcriber.procesar_sesion(
            media_url=str(payload.media_url) if payload.media_url else None,
            pagina_origen=str(payload.pagina_origen) if payload.pagina_origen else None,
            idioma=payload.idioma,
            resumir=payload.resumir,
            incluir_segmentos=payload.incluir_segmentos,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el pipeline de transcripción: {str(e)}"
        )

    if "error" in resultado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resultado["error"]
        )
    return resultado


@router.post(
    "/media/detect",
    response_model=ConsultaMediaResponse,
    status_code=status.HTTP_200_OK,
    summary="Detectar URLs de audio/video dentro de datos scrapeados"
)
async def detect_media_in_data(
    payload: ConsultaMediaRequest,
    _current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Busca enlaces de video/audio dentro del resultado de un scraping."""
    detectadas = detectar_urls_media(payload.datos, max_resultados=payload.max_resultados)
    return {"detectadas": detectadas, "total": len(detectadas)}


# =========================================================
# AGENTE DE MONITOREO AUTÓNOMO (FUNCTION CALLING VÍA OLLAMA)
# =========================================================
@router.post(
    "/agent/process",
    response_model=AgentProcesarResponse,
    status_code=status.HTTP_200_OK,
    summary="Analizar novedades detectadas con el Agente (Ollama) y ejecutar Email/Sheets"
)
async def agent_process(
    payload: AgentProcesarRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    El agente analiza el contexto (nuevas publicaciones o cambios críticos), determina su
    relevancia y ejecuta automáticamente herramientas: enviar correo SMTP al administrador
    y registrar el evento en Google Sheets (gspread).
    """
    try:
        resultado = await agente.ejecutar(
            contexto=payload.contexto,
            instrucciones=payload.instrucciones or "",
            url_fuente=payload.url_fuente or "",
            destinatario_preferido=payload.destinatario,
            db=db,
            user_id=current_user.id if current_user else None,
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando el agente: {str(e)}"
        )
    return resultado


@router.post(
    "/agent/run-on-url",
    status_code=status.HTTP_200_OK,
    summary="Inspección autónoma completa: scrape + delta + agente Ollama"
)
async def agent_run_on_url(
    payload: AgentSobreUrlRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ejecuta un ciclo de monitoreo autónomo sobre una URL:
    1. Scrapea la página.
    2. Compara contra el snapshot histórico (delta).
    3. Alimenta el Agente para que actúe sobre los cambios críticos encontrados.
    """
    try:
        resultado = await agente.analizar_cambio_en_url(
            url=str(payload.url),
            instrucciones=payload.instrucciones or "",
            destinatario_preferido=payload.destinatario,
            db=db,
            user_id=current_user.id if current_user else None,
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la inspección autónoma: {str(e)}"
        )
    if "error" in resultado:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=resultado["error"]
        )
    return resultado


@router.get(
    "/agent/events",
    response_model=list[EventoAgenteResponse],
    status_code=status.HTTP_200_OK,
    summary="Historial de eventos registrados por el Agente de Monitoreo"
)
async def agent_events(
    limit: int = 30,
    canal: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentEvent)
    if canal:
        stmt = stmt.where(AgentEvent.canal == canal)
    if current_user:
        stmt = stmt.where(AgentEvent.user_id == current_user.id)
    stmt = stmt.order_by(AgentEvent.created_at.desc()).limit(min(limit, 200))
    result = await db.execute(stmt)
    eventos = result.scalars().all()
    return [
        EventoAgenteResponse(
            id=e.id,
            tipo_evento=e.tipo_evento,
            titulo=e.titulo,
            descripcion=e.descripcion,
            url_fuente=e.url_fuente,
            nivel_prioridad=e.nivel_prioridad,
            canal=e.canal,
            razon_ia=e.razon_ia,
            created_at=e.created_at.isoformat() if e.created_at else None,
        )
        for e in eventos
    ]