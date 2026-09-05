# endpoint.py

import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import REPORTS_DIR
from app.core.database import get_db
from app.core.security import get_optional_current_user
from app.models.entities import Snapshot, AnalysisReport, User
from app.schemas.schemas import (
    ScrapeIndexRequest,
    ItemDetalleRequest,
    DeepScrapeRequest,
    FullPipelineRequest,
    ScrapeIndexResponse,
    ArticuloDetalleResponse,
    DeepScrapeResponse,
    FullPipelineResponse,
    AnalyzeRequest,
    AnalyzeResponse,
)
from app.services.scraper_client import ScraperClient
from app.services.snapshot_service import SnapshotService
from app.services.ollama_analyzer import OllamaAnalyzer
from app.services.chart_generator import ChartGenerator
from app.services.excel_reporter import ExcelReporter
from app.services.word_reporter import WordReporter

router = APIRouter(tags=["Scraper & Inteligencia"])

# Instanciamos el cliente del microservicio de scraping y servicios de IA
scraper_client = ScraperClient()
ollama_analyzer = OllamaAnalyzer()


# ==========================================
# ENDPOINTS DE SCRAPING DETERMINISTA (SIN IA)
# ==========================================

@router.post(
    "/scrape/index", 
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
        resultado = await scraper_client.scrape_index(url_str)
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
    "/scrape/deep", 
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
        return await scraper_client.scrape_deep(items_dict)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado durante el Deep Scraping: {str(e)}"
        )


@router.post(
    "/scrape/full-pipeline",
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
    try:
        return await scraper_client.scrape_full_pipeline(url_str, limit=payload.limit or 5)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en full-pipeline: {str(e)}"
        )


# =========================================================
# ENDPOINTS DE INTELIGENCIA CON OLLAMA & HISTÓRICO POSTGRESQL
# =========================================================

@router.post(
    "/intelligence/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analizar con Ollama, comparar versiones en PostgreSQL y generar reportes"
)
async def analyze_and_report(
    payload: AnalyzeRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Pipeline inteligente completo:
    1. Scrapea la URL en vivo.
    2. Consulta si existe un snapshot previo en PostgreSQL y calcula el delta temporal.
    3. Invoca a Ollama para análisis semántico (resumen, categorías, sentimientos y evolución).
    4. Genera gráficos con Matplotlib e informes ejecutivos en Excel y Word.
    5. Almacena el nuevo snapshot y el reporte en PostgreSQL.
    """
    from datetime import datetime
    url_str = str(payload.url)

    # 1. Extracción de contenido en vivo a través del microservicio de scraping
    try:
        resultado_scrape = await scraper_client.scrape_index(url_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al scrapear la página: {str(e)}"
        )

    site_title = resultado_scrape.get("site_title") or "Página Web"
    tipo_contenido = resultado_scrape.get("tipo_contenido", "lista_entidades")
    data_scraped = resultado_scrape.get("data", [])

    # 2. Búsqueda de snapshot anterior para comparación temporal
    snapshot_previo = None
    delta = None
    es_linea_base = True

    try:
        snapshot_previo = await SnapshotService.obtener_ultimo_snapshot(db, url_str)
        if snapshot_previo:
            es_linea_base = False
            delta = SnapshotService.calcular_delta(snapshot_previo.data, data_scraped)
    except Exception:
        pass

    # 3. Guardar el nuevo snapshot en PostgreSQL si se solicitó
    nuevo_snapshot = None
    if payload.guardar_snapshot:
        try:
            nuevo_snapshot = await SnapshotService.guardar_snapshot(
                session=db,
                url=url_str,
                site_title=site_title,
                tipo_contenido=tipo_contenido,
                data=data_scraped
            )
        except Exception:
            pass

    # 4. Análisis semántico con Ollama (Local)
    analisis_ia = await ollama_analyzer.analizar_contenido(
        url=url_str,
        site_title=site_title,
        articulos_o_texto=data_scraped,
        delta=delta
    )

    # 5. Generar Gráficos y Reportes en Excel y Word
    excel_url = None
    word_url = None

    if payload.generar_documentos:
        temp_chart_dir = REPORTS_DIR / "charts"
        temp_chart_dir.mkdir(parents=True, exist_ok=True)
        chart_paths = []

        try:
            # Gráficos con Matplotlib
            if analisis_ia.get("categorias"):
                chart_paths.append(
                    ChartGenerator.generar_grafico_categorias(analisis_ia["categorias"], temp_chart_dir)
                )
            if analisis_ia.get("sentimientos"):
                chart_paths.append(
                    ChartGenerator.generar_grafico_sentimientos(analisis_ia["sentimientos"], temp_chart_dir)
                )
            if delta and delta.get("es_lista") and (delta.get("total_nuevos", 0) > 0 or delta.get("total_salientes", 0) > 0):
                chart_paths.append(
                    ChartGenerator.generar_grafico_delta(delta, temp_chart_dir)
                )

            # Nombres únicos de archivos
            timestamp_id = uuid.uuid4().hex[:8]
            excel_filename = f"reporte_{timestamp_id}.xlsx"
            word_filename = f"informe_{timestamp_id}.docx"
            excel_path = REPORTS_DIR / excel_filename
            word_path = REPORTS_DIR / word_filename

            articulos_lista = data_scraped if isinstance(data_scraped, list) else [{"titulo": site_title, "url": url_str}]

            # Generar Excel
            ExcelReporter.generar_reporte(
                url=url_str,
                site_title=site_title,
                analisis_ia=analisis_ia,
                articulos=articulos_lista,
                delta=delta,
                chart_paths=chart_paths,
                output_file=excel_path
            )

            # Generar Word
            WordReporter.generar_reporte(
                url=url_str,
                site_title=site_title,
                analisis_ia=analisis_ia,
                articulos=articulos_lista,
                delta=delta,
                chart_paths=chart_paths,
                output_file=word_path
            )

            # Almacenar registro de reporte en PostgreSQL
            try:
                reporte = AnalysisReport(
                    user_id=current_user.id if current_user else None,
                    url=url_str,
                    current_snapshot_id=nuevo_snapshot.id if nuevo_snapshot else None,
                    previous_snapshot_id=snapshot_previo.id if snapshot_previo else None,
                    resumen_ejecutivo=analisis_ia.get("resumen_ejecutivo", ""),
                    metricas={
                        "categorias": analisis_ia.get("categorias"),
                        "sentimientos": analisis_ia.get("sentimientos"),
                        "entidades": analisis_ia.get("entidades_clave")
                    },
                    diferencias_delta=delta,
                    excel_path=str(excel_path),
                    word_path=str(word_path)
                )
                db.add(reporte)
                await db.flush()
                await db.refresh(reporte)

                excel_url = f"/api/v1/reports/download/excel/{reporte.id}"
                word_url = f"/api/v1/reports/download/word/{reporte.id}"
            except Exception:
                excel_url = f"/api/v1/reports/file/{excel_filename}"
                word_url = f"/api/v1/reports/file/{word_filename}"

        except Exception as e:
            pass

    return {
        "url": url_str,
        "sitio_titulo": site_title,
        "snapshot_id": nuevo_snapshot.id if nuevo_snapshot else None,
        "snapshot_anterior_id": snapshot_previo.id if snapshot_previo else None,
        "es_linea_base": es_linea_base,
        "total_items": len(data_scraped) if isinstance(data_scraped, list) else 1,
        "analisis_ia": analisis_ia,
        "delta": delta,
        "descargas": {
            "excel": excel_url,
            "word": word_url
        },
        "created_at": datetime.now().isoformat()
    }


# =========================================================
# ENDPOINTS DE DESCARGA DE REPORTES Y CONSULTA HISTÓRICA
# =========================================================

@router.get(
    "/reports/download/excel/{report_id}",
    summary="Descargar reporte Excel generado"
)
async def download_excel(report_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(AnalysisReport).where(AnalysisReport.id == report_id)
    res = await db.execute(stmt)
    report = res.scalars().first()
    if not report or not report.excel_path or not Path(report.excel_path).exists():
        raise HTTPException(status_code=404, detail="Archivo Excel no encontrado.")
    return FileResponse(
        report.excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(report.excel_path).name
    )


@router.get(
    "/reports/download/word/{report_id}",
    summary="Descargar informe Word generado"
)
async def download_word(report_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(AnalysisReport).where(AnalysisReport.id == report_id)
    res = await db.execute(stmt)
    report = res.scalars().first()
    if not report or not report.word_path or not Path(report.word_path).exists():
        raise HTTPException(status_code=404, detail="Archivo Word no encontrado.")
    return FileResponse(
        report.word_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(report.word_path).name
    )


@router.get(
    "/reports/file/{filename}",
    summary="Descargar archivo directo de reportes"
)
async def download_file(filename: str):
    file_path = REPORTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    media_type = "application/octet-stream"
    if filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(str(file_path), media_type=media_type, filename=filename)


@router.get(
    "/reports/list",
    summary="Listar historial de reportes generados"
)
async def list_reports(
    limit: int = 20,
    solo_mis_reportes: bool = False,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AnalysisReport)
    if solo_mis_reportes and current_user:
        stmt = stmt.where(AnalysisReport.user_id == current_user.id)
    stmt = stmt.order_by(AnalysisReport.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    reports = res.scalars().all()
    return [
        {
            "id": r.id,
            "url": r.url,
            "resumen_ejecutivo": r.resumen_ejecutivo[:200] if r.resumen_ejecutivo else "",
            "excel_url": f"/api/v1/reports/download/excel/{r.id}" if r.excel_path else None,
            "word_url": f"/api/v1/reports/download/word/{r.id}" if r.word_path else None,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in reports
    ]


@router.get(
    "/snapshots/history",
    summary="Consultar historial de snapshots de una URL"
)
async def list_snapshots(url: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Snapshot).where(Snapshot.url == url).order_by(Snapshot.created_at.desc())
    res = await db.execute(stmt)
    snaps = res.scalars().all()
    return [
        {
            "id": s.id,
            "url": s.url,
            "site_title": s.site_title,
            "total_items": s.total_items,
            "created_at": s.created_at.isoformat() if s.created_at else None
        }
        for s in snaps
    ]