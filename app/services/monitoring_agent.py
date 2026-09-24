# app/services/monitoring_agent.py
"""
Agente de Monitoreo Autónomo (Function Calling vía Ollama).

Cuando el scraping detecta cambios (por ejemplo, una nueva licitación pública),
Ollama analiza el texto, determina la relevancia y decide ejecutar herramientas:
  1. enviar_alerta_correo    -> notifica al administrador por SMTP.
  2. registrar_evento_sheet  -> registra el evento en Google Sheets (gspread).
  3. detectar_media_en_pagina-> localiza audios/videos para transcripción.

El agente usa la API /api/chat de Ollama con la definición de tools (herramientas),
ejecuta las llamadas localmente y realimenta los resultados al modelo hasta obtener
una conclusión final.
"""
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    ADMIN_ALERT_EMAIL,
    AGENT_MAX_ITERATIONS,
)
from app.models.entities import AgentEvent, Snapshot
from app.services.email_service import EmailService
from app.services.google_sheets_client import GoogleSheetsClient
from app.services.media_transcriber import MediaTranscriber, detectar_media_en_pagina
from app.services.scraper_client import ScraperClient
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger("uvicorn.error")

# =========================================================
# DEFINICIÓN DE HERRAMIENTAS (TOOLS) PARA OLLAMA
# =========================================================

HERRAMIENTAS_AGENTE: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "enviar_alerta_correo",
            "description": (
                "Envía un correo electrónico de alerta al administrador del sistema "
                "cuando se detecta un evento crítico (licitación, norma, comunicado urgente)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "asunto": {"type": "string", "description": "Asunto del correo."},
                    "mensaje": {"type": "string", "description": "Mensaje claro y formal con los detalles del evento."},
                    "url_fuente": {"type": "string", "description": "URL de la noticia/publicación que originó el evento."},
                    "destinatario": {"type": "string", "description": "Opcional. Correo destino; si se omite se usa el administrador configurado."},
                },
                "required": ["asunto", "mensaje"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_evento_sheet",
            "description": (
                "Registra un evento relevante detectado en el monitoreo en una hoja de "
                "cálculo de Google Sheets (gspread) para llevar un historial auditable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_evento": {"type": "string", "description": "Categoría del evento, ej: licitacion_publica, norma_publicada, comunicado_urgente."},
                    "titulo": {"type": "string", "description": "Título breve del evento."},
                    "descripcion": {"type": "string", "description": "Descripción detallada del evento."},
                    "url_fuente": {"type": "string", "description": "URL de la publicación que originó el evento."},
                    "nivel_prioridad": {"type": "string", "enum": ["BAJO", "MEDIO", "ALTO", "CRÍTICO"], "description": "Nivel de importancia del evento."},
                },
                "required": ["tipo_evento", "titulo", "descripcion", "url_fuente", "nivel_prioridad"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detectar_media_en_pagina",
            "description": (
                "Busca URLs de audio o video (sesiones, entrevistas) dentro de una página "
                "monitoreada, útiles para transcripción posterior con whisper."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pagina_origen": {"type": "string", "description": "URL de la página donde buscar medios."},
                },
                "required": ["pagina_origen"],
            },
        },
    },
]

SISTEMA_AGENTE = """Eres el Agente de Monitoreo Autónomo de SIMAP, un sistema de inteligencia web.
Analizas contenido recién extraído de páginas públicas (gobierno, licitaciones, noticias, normativa)
y decides si amerita ACCIÓN AUTOMÁTICA.

Reglas:
1. Determina si el contenido contiene un EVENTO RELEVANTE (licitación nueva, norma/decreto, comunicado
   oficial urgente, cifra crítica, convocatoria, cambio regulatorio).
2. Si hay un evento relevante, usa las herramientas disponibles:
   - 'registrar_evento_sheet' SIEMPRE para dejar evidencia auditable del evento.
   - 'enviar_alerta_correo' si el evento es ALTO o CRÍTICO.
3. Si el contenido es de menor relevancia (rutina, sin cambios importantes), responde indicando
   que no se requirió acción.
4. Responde en español, con un resumen final claro de las decisiones y acciones ejecutadas.
"""


class MonitoringAgent:
    """
    Orquesta el ciclo de function calling con Ollama y ejecuta las herramientas en local.
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    # ============================================
    # EJECUCIÓN DEL CICLO DE HERRAMIENTAS
    # ============================================
    async def ejecutar(
        self,
        contexto: str,
        instrucciones: str = "",
        url_fuente: str = "",
        destinatario_preferido: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta el agente con un texto de contexto (novedades detectadas).
        Devuelve la respuesta final del LLM y el registro de acciones ejecutadas.
        """
        mensaje_usuario = f"""CONTENIDO RECIÉN DETECTADO EN EL MONITOREO:{contexto}"""
        if instrucciones:
            mensaje_usuario += f"""

INSTRUCCIONES DEL OPERADOR (DEBES RESPETARLAS):
{instrucciones}"""
        mensaje_usuario += f"""

URL DE ORIGEN DEL CONTENIDO: {url_fuente or "desconocida"}"""

        mensajes: List[Dict[str, Any]] = [
            {"role": "system", "content": SISTEMA_AGENTE},
            {"role": "user", "content": mensaje_usuario},
        ]

        acciones: List[Dict[str, Any]] = []
        iteraciones = 0

        while iteraciones < AGENT_MAX_ITERATIONS:
            iteraciones += 1
            payload = {
                "model": self.model,
                "messages": mensajes,
                "tools": HERRAMIENTAS_AGENTE,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 900, "num_ctx": 8192},
            }

            try:
                async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
                    res = await client.post(f"{self.base_url}/api/chat", json=payload)
                    res.raise_for_status()
                    data = res.json()
            except Exception as e:
                logger.error(f"Error al invocar al agente en Ollama: {str(e)}")
                return {
                    "respuesta": "Error de conexión con Ollama durante el análisis del agente.",
                    "acciones": acciones,
                    "error": str(e),
                }

            mensaje = data.get("message", {})
            tiene_tools = bool(mensaje.get("tool_calls"))

            # Anexar mensaje del asistente (puede traer texto + tool_calls)
            mensajes.append(mensaje)

            if not tiene_tools:
                break

            for llamada in mensaje.get("tool_calls", []):
                funcion = llamada.get("function", {})
                nombre = funcion.get("name", "")
                try:
                    argumentos = json.loads(funcion.get("arguments") or "{}")
                except Exception:
                    argumentos = {}

                resultado = await self._ejecutar_herramienta(
                    nombre,
                    argumentos,
                    url_fuente=url_fuente,
                    destinatario_preferido=destinatario_preferido,
                    db=db,
                    user_id=user_id,
                )
                acciones.append(resultado)

                mensajes.append({
                    "role": "tool",
                    "content": json.dumps(resultado.get("resultado", {}), ensure_ascii=False),
                })

        # Extraer la conclusión final (último mensaje de texto puro del asistente)
        respuesta_final = ""
        for m in reversed(mensajes):
            if m.get("role") == "assistant" and m.get("content"):
                respuesta_final = str(m["content"]).strip()
                break

        return {"respuesta": respuesta_final or "El agente completó el análisis sin conclusión textual.", "acciones": acciones}

    # ============================================
    # DESPACHADOR DE HERRAMIENTAS
    # ============================================
    async def _ejecutar_herramienta(
        self,
        nombre: str,
        argumentos: Dict[str, Any],
        url_fuente: str = "",
        destinatario_preferido: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Ejecuta la herramienta indicada y registra el evento persistente."""
        accion = {
            "herramienta": nombre,
            "argumentos": argumentos,
            "resultado": None,
            "ok": False,
            "canal": "sistema",
        }

        if nombre == "enviar_alerta_correo":
            destino = argumentos.get("destinatario") or destinatario_preferido or ADMIN_ALERT_EMAIL
            asunto = argumentos.get("asunto", "Alerta del Agente de Monitoreo SIMAP")
            mensaje = argumentos.get("mensaje", "")
            fuente = argumentos.get("url_fuente") or url_fuente
            ok = False
            if destino:
                ok = await EmailService.enviar_mensaje_automatizado(
                    destinatario=destino,
                    asunto=asunto,
                    mensaje=mensaje,
                    url_fuente=fuente,
                    metadatos=f"Evento detectado automáticamente por Ollama. Prioridad: {argumentos.get('nivel_prioridad', 'NO ESPECIFICADA')}",
                )
            accion["resultado"] = {"enviado": ok, "destinatario": destino}
            accion["ok"] = ok
            accion["canal"] = "email"
            await self._persistir_evento(db, user_id, {
                "tipo_evento": "alerta_correo",
                "titulo": asunto[:290],
                "descripcion": mensaje[:1000],
                "url_fuente": fuente,
                "nivel_prioridad": "ALTO",
                "razon_ia": mensaje[:500],
            }, canal="email")

        elif nombre == "registrar_evento_sheet":
            resultado_sheet = await GoogleSheetsClient.registrar_evento({
                "tipo_evento": argumentos.get("tipo_evento", "evento_generico"),
                "titulo": argumentos.get("titulo", ""),
                "descripcion": argumentos.get("descripcion", ""),
                "url_fuente": argumentos.get("url_fuente") or url_fuente,
                "nivel_prioridad": argumentos.get("nivel_prioridad", "BAJO"),
                "origen_ia": "agente_simap_ollama",
            })
            accion["resultado"] = resultado_sheet
            accion["ok"] = bool(resultado_sheet.get("ok"))
            accion["canal"] = "sheets"
            await self._persistir_evento(db, user_id, {
                "tipo_evento": argumentos.get("tipo_evento", "evento_generico"),
                "titulo": argumentos.get("titulo", ""),
                "descripcion": argumentos.get("descripcion", ""),
                "url_fuente": argumentos.get("url_fuente") or url_fuente,
                "nivel_prioridad": argumentos.get("nivel_prioridad", "BAJO"),
                "razon_ia": f"Registro en sheets: {resultado_sheet.get('modo', resultado_sheet.get('sheet', ''))}",
            }, canal="sheets")

        elif nombre == "detectar_media_en_pagina":
            pagina = argumentos.get("pagina_origen") or url_fuente
            medios = await detectar_media_en_pagina(pagina) if pagina else []
            accion["resultado"] = {"detectadas": medios, "total": len(medios)}
            accion["ok"] = True
            accion["canal"] = "sistema"
            if medios:
                await self._persistir_evento(db, user_id, {
                    "tipo_evento": "media_detectada",
                    "titulo": f"Se detectaron {len(medios)} medios audiovisuales",
                    "descripcion": json.dumps([m["url"] for m in medios[:5]], ensure_ascii=False),
                    "url_fuente": pagina,
                    "nivel_prioridad": "MEDIO",
                    "razon_ia": "Agente detectó audio/video para transcripción.",
                }, canal="sistema")

        return accion

    @staticmethod
    async def _persistir_evento(
        db: Optional[AsyncSession],
        user_id: Optional[int],
        datos: Dict[str, Any],
        canal: str,
    ) -> None:
        """Guarda el evento del agente en PostgreSQL (agente_events) si hay sesión."""
        if not db:
            return
        try:
            evento = AgentEvent(
                user_id=user_id,
                tipo_evento=datos.get("tipo_evento", "evento_generico"),
                titulo=datos.get("titulo"),
                descripcion=datos.get("descripcion"),
                url_fuente=datos.get("url_fuente"),
                nivel_prioridad=datos.get("nivel_prioridad"),
                canal=canal,
                razon_ia=datos.get("razon_ia"),
                metadatos=datos,
            )
            db.add(evento)
            await db.flush()
        except Exception as e:
            logger.warning(f"No se pudo persistir evento del agente: {str(e)}")

    # ============================================
    # CICLO COMPLETO SOBRE UNA URL (SCRAPE + DELTA + AGENTE)
    # ============================================
    async def analizar_cambio_en_url(
        self,
        url: str,
        instrucciones: str = "",
        destinatario_preferido: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta el monitoreo autónomo completo:
        1. Scrapea la URL por el microservicio existente.
        2. Compara con el snapshot previo para conocer las novedades.
        3. Guarda el snapshot actual.
        4. Entrega las novedades al Agente (Ollama) para decidir acciones.
        """
        scraper = ScraperClient()
        try:
            resultado = await scraper.scrape_index(url)
        except Exception as e:
            return {"error": f"No se pudo scrapear la URL: {str(e)}"}

        site_title = resultado.get("site_title") or url
        tipo_contenido = resultado.get("tipo_contenido", "lista_entidades")
        data_scraped = resultado.get("data", [])

        delta = None
        if db:
            try:
                snapshot_previo = await SnapshotService.obtener_ultimo_snapshot(db, url)
                if snapshot_previo:
                    delta = SnapshotService.calcular_delta(snapshot_previo.data, data_scraped)
                await SnapshotService.guardar_snapshot(db, url, site_title, tipo_contenido, data_scraped)
            except Exception as e:
                logger.warning(f"No se pudo calcular delta en agente: {str(e)}")

        # Construir el contexto del agente a partir de las novedades o del contenido del sitio
        nuevos = (delta or {}).get("nuevos_articulos", []) or []
        contexto = ""
        if nuevos:
            contexto = "NUEVAS PUBLICACIONES DETECTADAS:\n" + "\n".join(
                f"- {item.get('titulo', 'Sin título')} (URL: {item.get('url', '')})" for item in nuevos[:20]
            )
        elif isinstance(data_scraped, list):
            contexto = "CONTENIDO ACTUAL DEL SITIO:\n" + "\n".join(
                f"- {item.get('titulo', '')} (URL: {item.get('url', '')})" for item in data_scraped[:20]
            )
        else:
            contexto = f"CONTENIDO ACTUAL DEL SITIO:\n{str(data_scraped)[:3000]}"

        resultado_agente = await self.ejecutar(
            contexto=contexto,
            instrucciones=instrucciones,
            url_fuente=url,
            destinatario_preferido=destinatario_preferido,
            db=db,
            user_id=user_id,
        )

        return {
            "url": url,
            "sitio_titulo": site_title,
            "total_items": len(data_scraped) if isinstance(data_scraped, list) else 1,
            "delta": delta,
            "contexto_agente": contexto[:2000],
            **resultado_agente,
        }