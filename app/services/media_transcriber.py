# app/services/media_transcriber.py
"""
Transcripción de Medios (sesiones, audios y videos detectados durante el scraping).

Flujo:
1. Detecta URLs de audio/video dentro de los datos scrapeados (expresiones regulares
   y hosts conocidos de video/streaming).
2. Descarga la pista de audio con yt-dlp (portales de video) o descarga directa con httpx.
3. Transcribe localmente con faster-whisper (mismo entorno que Ollama: 100% local).
4. El texto resultante puede alimentar a Ollama para generar un resumen estructurado,
   de modo que la transcripción quede disponible para el asistente RAG y el agente.
"""
import re
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

import httpx

from app.core.config import MEDIA_DOWNLOADS_DIR, WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE
from app.services.scraper_client import ScraperClient

logger = logging.getLogger("uvicorn.error")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Extensiones de archivos de audio/video directos
PATRON_EXTENSION_MEDIA = re.compile(
    r"https?://[^\s\"'<>\\]+?\.(?:mp3|wav|m4a|aac|ogg|oga|opus|flac|wma|mp4|m4v|webm|mkv|mov|avi|m3u8)(?:\?[^\s\"'<>\\]*)?",
    re.IGNORECASE,
)

# Hosts de plataformas de video/audio que requieren yt-dlp
HOSTS_VIDEO = {
    "youtube.com", "youtu.be", "www.youtube.com",
    "vimeo.com", "www.vimeo.com",
    "dailymotion.com", "www.dailymotion.com",
    "soundcloud.com", "www.soundcloud.com",
    "twitch.tv", "www.twitch.tv",
    "facebook.com", "www.facebook.com",
    "odysee.com", "www.odysee.com",
    "archive.org", "www.archive.org",
}

_TOKENIZAR_URL = re.compile(r"(https?://[^\s\"'<>]+)", re.IGNORECASE)


def _dominio(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def detectar_urls_media(
    datos: Any,
    max_resultados: int = 10,
) -> List[Dict[str, Any]]:
    """
    Busca URLs de audio/video dentro de los datos scrapeados
    (lista de noticias, texto markdown o dicts aislados).
    """
    encontradas: List[Dict[str, Any]] = []
    vistos: set = set()

    def _agregar(url: str, titulo: str = ""):
        url_limpia = url.rstrip(".,;")
        if url_limpia.startswith(("http:", "https:")) and url_limpia not in vistos:
            base = _dominio(url_limpia)
            es_video = any(h in base for h in HOSTS_VIDEO)
            es_directo = bool(PATRON_EXTENSION_MEDIA.match(url_limpia)) or ".m3u8" in url_limpia.lower()
            if es_video or es_directo:
                vistos.add(url_limpia)
                encontradas.append({
                    "url": url_limpia,
                    "titulo": titulo[:200],
                    "tipo": "plataforma_video" if es_video else "archivo_directo",
                })

    def _procesar_texto(texto: str, titulo: str = ""):
        for match in _TOKENIZAR_URL.findall(texto):
            _agregar(match, titulo)

    if isinstance(datos, list):
        for item in datos:
            if not isinstance(item, dict):
                continue
            titulo_item = str(item.get("titulo") or item.get("title") or "").strip()
            for clave in ("url", "link", "src", "contenido", "contenido_markdown"):
                valor = item.get(clave)
                if not isinstance(valor, str):
                    continue
                if valor.startswith("http"):
                    _agregar(valor, titulo_item)
                _procesar_texto(valor, titulo_item)
    elif isinstance(datos, dict):
        for clave in ("data", "articulos", "contenido_markdown"):
            if clave in datos:
                _procesar_texto(str(datos[clave]))
    else:
        _procesar_texto(str(datos))

    return encontradas[:max_resultados]


async def detectar_media_en_pagina(url: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Scrapea una página mediante el microservicio existente y localiza
    las URLs de audio/video publicadas en ella (ej. sesiones de concejo).
    """
    scraper = ScraperClient()
    media: List[Dict[str, Any]] = []

    try:
        resultado = await scraper.scrape_full_pipeline(url, limit=limit)
        media = detectar_urls_media(resultado, max_resultados=10)
        return media
    except Exception as e:
        logger.warning(f"Error al detectar medios en {url}: {str(e)}")
        return media


class MediaTranscriber:
    """
    Servicio de descarga y transcripción local de sesiones de audio/video.
    """

    def __init__(self) -> None:
        self.directorio = MEDIA_DOWNLOADS_DIR

    # ============================================
    # DESCARGAR PISTA DE AUDIO
    # ============================================
    async def descargar_pista_audio(self, url: str) -> Dict[str, Any]:
        """
        Descarga el audio de una URL. Usa yt-dlp para plataformas de video
        y descarga directa con httpx para archivos. Ejecuta en threadpool.
        """
        dominio = _dominio(url)
        es_plataforma = any(h in dominio for h in HOSTS_VIDEO)

        if es_plataforma:
            return await asyncio.to_thread(self._descargar_con_ytdlp, url)
        return await self._descargar_directa(url)

    def _descargar_con_ytdlp(self, url: str) -> Dict[str, Any]:
        """Descarga bestaudio con yt-dlp (devuelve contenedor original sin conversión)."""
        try:
            import yt_dlp
        except ImportError:
            return {"error": "yt-dlp no está instalado. Ejecuta: pip install yt-dlp"}

        try:
            import uuid
            template = str(self.directorio / f"media_{uuid.uuid4().hex[:8]}.%(ext)s")
            opciones = {
                "format": "bestaudio/best",
                "outtmpl": template,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "http_headers": {"User-Agent": DEFAULT_USER_AGENT},
            }
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=True)
                ruta_resuelta = Path(ydl.prepare_filename(info))
                if not ruta_resuelta.exists():
                    ruta_resuelta = Path(template.replace("%(ext)s", info.get("ext", "mp3")))
                return {
                    "url": url,
                    "ruta": str(ruta_resuelta),
                    "titulo": info.get("title") or "",
                    "duracion_segundos": info.get("duration"),
                    "formato": ruta_resuelta.suffix.lstrip("."),
                }
        except Exception as e:
            logger.error(f"yt-dlp falló para {url}: {str(e)}")
            return {"error": f"yt-dlp no pudo descargar la URL: {str(e)}"}

    async def _descargar_directa(self, url: str) -> Dict[str, Any]:
        """Descarga un archivo directo (.mp3/.mp4/.m4a/...) mediante httpx."""
        ext_guess = Path(urlparse(url).path).suffix or ".mp3"
        if ext_guess == ".m3u8":
            return {"error": "Los streams HLS (.m3u8) requieren ffmpeg. Proporciona la URL del archivo base."}

        ruta = self.directorio / f"media_{uuid4_hex()}{ext_guess}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0),
                follow_redirects=True,
                headers={"User-Agent": DEFAULT_USER_AGENT},
            ) as client:
                async with client.stream("GET", url) as res:
                    res.raise_for_status()
                    with open(ruta, "wb") as fh:
                        async for chunk in res.aiter_bytes():
                            fh.write(chunk)
            return {
                "url": url,
                "ruta": str(ruta),
                "titulo": ruta.name,
                "duracion_segundos": None,
                "formato": ext_guess.lstrip("."),
            }
        except Exception as e:
            logger.error(f"Descarga directa falló para {url}: {str(e)}")
            return {"error": f"No se pudo descargar el archivo: {str(e)}"}

    # ============================================
    # TRANSCRIPCIÓN LOCAL CON faster-whisper
    # ============================================
    async def transcribir_archivo(
        self,
        ruta: str,
        idioma: Optional[str] = WHISPER_LANGUAGE,
        modelo: Optional[str] = None,
        incluir_segmentos: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe un archivo de audio/video local con faster-whisper."""
        if not Path(ruta).exists():
            return {"error": f"El archivo no existe en la ruta: {ruta}"}
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return {"error": "faster-whisper no está instalado. Ejecuta: pip install faster-whisper"}

        def _transcribir():
            try:
                modelo_cargado = WhisperModel(
                    modelo or WHISPER_MODEL,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                )
            except Exception as e:
                logger.warning(f"No se pudo cargar modelo whisper ({WHISPER_MODEL}): {str(e)}")
                raise
            segmentos, info = modelo_cargado.transcribe(
                ruta,
                language=idioma,
                vad_filter=True,
                beam_size=5,
            )
            lista_segmentos = []
            texto_completo = []
            for seg in segmentos:
                texto_completo.append(seg.text.strip())
                if incluir_segmentos:
                    lista_segmentos.append({
                        "inicio": round(seg.start, 2),
                        "fin": round(seg.end, 2),
                        "texto": seg.text.strip(),
                    })
            return {
                "transcripcion": " ".join(t for t in texto_completo if t),
                "segmentos": lista_segmentos,
                "idioma_detectado": getattr(info, "language", None),
                "idioma_probabilidad": round(float(getattr(info, "language_probability", 0) or 0), 4),
                "duracion_segundos": round(float(getattr(info, "duration", 0) or 0), 2),
            }

        try:
            return await asyncio.to_thread(_transcribir)
        except Exception as e:
            logger.error(f"Error durante la transcripción: {str(e)}")
            return {"error": f"Error durante la transcripción con whisper: {str(e)}"}

    # ============================================
    # RESUMEN ESTRUCTURADO CON OLLAMA
    # ============================================
    async def resumir_transcripcion(self, transcripcion: str, url_fuente: str = "") -> Dict[str, Any]:
        """Envía la transcripción a Ollama para generar un resumen ejecutivo estructurado."""
        if not transcripcion or len(transcripcion) < 40:
            return {"resumen": "", "puntos_clave": [], "menciones": []}

        from app.core.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS

        prompt = f"""Eres un transcriptor de sesiones públicas. Resume la siguiente transcripción
de una sesión (audio/video) detectada en el monitoreo web. Responde ÚNICAMENTE con JSON válido:
{{
  "resumen": "Resumen ejecutivo de 2-3 párrafos en español.",
  "puntos_clave": ["Decisión o tema clave 1", "Decisión o tema clave 2"],
  "menciones": ["Personas o instituciones mencionadas"]
}}

TRANSCRIPCIÓN ({url_fuente}):
{transcripcion[:6000]}"""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 600, "num_ctx": 8192},
        }
        try:
            import json as _json
            import re as _re
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
                res = await client.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate", json=payload)
                res.raise_for_status()
                raw = res.json().get("response", "{}")
                match = _re.search(r"(\{.*\})", raw, _re.DOTALL)
                if match:
                    return _json.loads(_re.sub(r",\s*([\]}])", r"\1", match.group(1)))
        except Exception as e:
            logger.error(f"Error al resumir transcripción con Ollama: {str(e)}")
        return {"resumen": transcripcion[:800], "puntos_clave": [], "menciones": []}

    # ============================================
    # PIPELINE COMPLETO
    # ============================================
    async def procesar_sesion(
        self,
        media_url: Optional[str] = None,
        pagina_origen: Optional[str] = None,
        idioma: Optional[str] = WHISPER_LANGUAGE,
        resumir: bool = True,
        incluir_segmentos: bool = False,
    ) -> Dict[str, Any]:
        """
        Flujo completo:
        1. Resolver la URL de media (proporcionada o detectada en la página scrapeada).
        2. Descargar la pista de audio.
        3. Transcribir con faster-whisper.
        4. Opcionalmente resumir con Ollama para alimentar al RAG/agente.
        """
        if not media_url and not pagina_origen:
            return {"error": "Se requiere 'media_url' o 'pagina_origen' para transcribir."}

        if not media_url and pagina_origen:
            detectadas = await detectar_media_en_pagina(pagina_origen)
            if not detectadas:
                return {
                    "error": "No se detectaron URLs de audio/video en la página indicada.",
                    "detectadas": [],
                }
            media_url = detectadas[0]["url"]
            logger.info(f"Se seleccionó la primera de {len(detectadas)} URLs de media encontradas: {media_url}")

        descarga = await self.descargar_pista_audio(media_url)
        if "error" in descarga:
            return {"error": descarga["error"], "url": media_url}

        transcripcion = await self.transcribir_archivo(
            ruta=descarga["ruta"],
            idioma=idioma,
            incluir_segmentos=incluir_segmentos,
        )
        if "error" in transcripcion:
            return {**descarga, **transcripcion, "url": media_url}

        resultado = {**descarga, **transcripcion, "url": media_url}
        if resumir:
            resumen_ia = await self.resumir_transcripcion(transcripcion["transcripcion"], media_url)
            resultado["resumen_ia"] = resumen_ia

        return resultado


def uuid4_hex() -> str:
    import uuid

    return uuid.uuid4().hex[:12]