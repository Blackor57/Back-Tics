# app/services/monitor_scheduler.py
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.entities import MonitoredTarget, AnalysisReport, User
from app.services.scraper_client import ScraperClient
from app.services.snapshot_service import SnapshotService
from app.services.ollama_analyzer import OllamaAnalyzer
from app.services.email_service import EmailService

logger = logging.getLogger("monitor_scheduler")


class MonitorScheduler:
    """
    Motor en segundo plano que monitorea periódicamente las URLs configuradas por los usuarios.
    Detecta cambios importantes (novedades en deltas) y despacha notificaciones por correo.
    """
    _running = False
    _task: Optional[asyncio.Task] = None
    _check_interval_seconds = 120  # Revisa la cola cada 2 minutos

    @classmethod
    async def iniciar(cls):
        """Inicia el bucle asíncrono del planificador si no está corriendo."""
        if cls._running:
            return
        cls._running = True
        cls._task = asyncio.create_task(cls._loop())
        logger.info("🚀 Motor de monitoreo continuo y alertas iniciado.")

    @classmethod
    async def detener(cls):
        """Detiene el bucle asíncrono del planificador."""
        cls._running = False
        if cls._task:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
            cls._task = None
        logger.info("🛑 Motor de monitoreo continuo detenido.")

    @classmethod
    async def _loop(cls):
        """Bucle principal de ejecución periódica."""
        # Esperar 10 segundos al iniciar la app para permitir que la BD y servicios carguen
        await asyncio.sleep(10)
        while cls._running:
            try:
                await cls._procesar_targets_pendientes()
            except Exception as e:
                logger.error(f"Error imprevisto en ciclo de monitoreo: {str(e)}")
            
            # Esperar hasta el siguiente chequeo
            try:
                await asyncio.sleep(cls._check_interval_seconds)
            except asyncio.CancelledError:
                break

    @classmethod
    async def _procesar_targets_pendientes(cls):
        """Busca y procesa los objetivos de monitoreo que requieren verificación."""
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as db:
            # Traer targets activos junto a la relación user
            stmt = (
                select(MonitoredTarget)
                .options(selectinload(MonitoredTarget.user))
                .where(MonitoredTarget.activo == True)
            )
            res = await db.execute(stmt)
            targets = res.scalars().all()

            if not targets:
                return

            scraper = ScraperClient()
            ollama = OllamaAnalyzer()

            for target in targets:
                # 1. Verificar si el seguimiento ya caducó por fecha_fin
                target_fin = target.fecha_fin
                if target_fin.tzinfo is None:
                    target_fin = target_fin.replace(tzinfo=timezone.utc)

                if now >= target_fin:
                    logger.info(f"El seguimiento para {target.url} ha alcanzado su fecha fin. Desactivando.")
                    target.activo = False
                    await db.commit()
                    continue

                # 2. Verificar si corresponde ejecutar según la frecuencia en horas
                debe_ejecutar = False
                if target.ultimo_chequeo is None:
                    debe_ejecutar = True
                else:
                    ultimo = target.ultimo_chequeo
                    if ultimo.tzinfo is None:
                        ultimo = ultimo.replace(tzinfo=timezone.utc)
                    horas_transcurridas = (now - ultimo).total_seconds() / 3600.0
                    if horas_transcurridas >= target.frecuencia_horas:
                        debe_ejecutar = True

                if not debe_ejecutar:
                    continue

                # 3. Ejecutar scraping y comparación de snapshot
                logger.info(f"🔍 Ejecutando chequeo programado para: {target.url} (Usuario: {target.user.email})")
                try:
                    resultado_scrape = await scraper.scrape_index(target.url)
                    site_title = resultado_scrape.get("site_title") or target.url
                    tipo_contenido = resultado_scrape.get("tipo_contenido", "lista_entidades")
                    data_scraped = resultado_scrape.get("data", [])

                    # Obtener snapshot previo
                    snapshot_previo = await SnapshotService.obtener_ultimo_snapshot(db, target.url)
                    delta = None
                    if snapshot_previo:
                        delta = SnapshotService.calcular_delta(snapshot_previo.data, data_scraped)

                    # Guardar nuevo snapshot
                    nuevo_snapshot = await SnapshotService.guardar_snapshot(
                        session=db,
                        url=target.url,
                        site_title=site_title,
                        tipo_contenido=tipo_contenido,
                        data=data_scraped
                    )

                    # 4. Comprobar si hay cambios relevantes (novedades en lista o modificaciones en texto continuo)
                    total_nuevos = delta.get("total_nuevos", 0) if delta else 0
                    cambio_texto = not delta.get("es_lista", True) and abs(delta.get("variacion_caracteres", 0)) > 50 if delta else False

                    if delta and (total_nuevos > 0 or cambio_texto):
                        logger.info(f"🔔 Cambios detectados en {target.url} ({total_nuevos} novedades/cambios). Generando análisis y alerta...")

                        
                        # Análisis de IA con Ollama
                        analisis_ia = {}
                        try:
                            analisis_ia = await ollama.analizar_contenido(
                                url=target.url,
                                site_title=site_title,
                                articulos_o_texto=data_scraped,
                                delta=delta
                            )
                        except Exception as err_ia:
                            logger.warning(f"No se pudo completar el análisis de IA para la alerta: {str(err_ia)}")
                            analisis_ia = {
                                "resumen_ejecutivo": f"Se identificaron {total_nuevos} nuevas publicaciones en la web monitoreada."
                            }

                        # Registrar el reporte en la base de datos vinculado al usuario
                        try:
                            reporte = AnalysisReport(
                                user_id=target.user_id,
                                url=target.url,
                                current_snapshot_id=nuevo_snapshot.id if nuevo_snapshot else None,
                                previous_snapshot_id=snapshot_previo.id if snapshot_previo else None,
                                resumen_ejecutivo=analisis_ia.get("resumen_ejecutivo", ""),
                                metricas={
                                    "categorias": analisis_ia.get("categorias"),
                                    "sentimientos": analisis_ia.get("sentimientos")
                                },
                                diferencias_delta=delta
                            )
                            db.add(reporte)
                        except Exception as e_rep:
                            logger.warning(f"No se pudo registrar reporte histórico: {str(e_rep)}")

                        # 5. Enviar correo de alerta si está habilitado
                        if target.notificar_email and target.user and target.user.email:
                            novedades = delta.get("novedades", [])
                            resumen_ia = analisis_ia.get("resumen_ejecutivo", "")
                            sentimientos = analisis_ia.get("sentimientos", {})
                            sentimiento_str = None
                            if sentimientos and isinstance(sentimientos, dict):
                                sentimiento_str = ", ".join([f"{k}: {v}" for k, v in sentimientos.items()])

                            await EmailService.enviar_alerta_cambio_relevante(
                                destinatario=target.user.email,
                                nombre_usuario=target.user.nombre_completo or target.user.email.split("@")[0],
                                url_monitoreada=target.url,
                                total_nuevos=total_nuevos,
                                resumen_ejecutivo=resumen_ia,
                                novedades=novedades,
                                sentimiento_general=sentimiento_str
                            )

                    # Actualizar fecha del último chequeo
                    target.ultimo_chequeo = datetime.now(timezone.utc)
                    await db.commit()

                except Exception as err_target:
                    logger.error(f"Error al procesar target #{target.id} ({target.url}): {str(err_target)}")
                    await db.rollback()
