# scraper_service/deep_scraper.py
import asyncio
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from readability import Document
from playwright.sync_api import sync_playwright

try:
    from config import BROWSER_VIEWPORT, DEFAULT_USER_AGENT, DEEP_PAGE_TIMEOUT_MS
    from utils import configurar_html2text
    from stealth_helper import get_stealth_launch_args, get_stealth_context_kwargs, apply_stealth_sync
except ImportError:
    from .config import BROWSER_VIEWPORT, DEFAULT_USER_AGENT, DEEP_PAGE_TIMEOUT_MS
    from .utils import configurar_html2text
    from .stealth_helper import get_stealth_launch_args, get_stealth_context_kwargs, apply_stealth_sync


class DeepScraperNoAI:
    def __init__(self):
        self.h2t = configurar_html2text()

    def _extraer_articulo_sync(self, url: str) -> Dict[str, Any]:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=get_stealth_launch_args()
            )
            ctx_options = get_stealth_context_kwargs()
            ctx_options["viewport"] = BROWSER_VIEWPORT
            if DEFAULT_USER_AGENT:
                ctx_options["user_agent"] = DEFAULT_USER_AGENT

            context = browser.new_context(**ctx_options)
            page = context.new_page()
            apply_stealth_sync(page)
            page.route("**/*.{png,jpg,jpeg,svg,gif,css,woff,woff2}", lambda route: route.abort())

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=DEEP_PAGE_TIMEOUT_MS)
                html_raw = page.content()
            except Exception as e:
                return {
                    "url": url,
                    "error": str(e),
                    "titulo_detalle": "",
                    "contenido_markdown": "",
                    "caracteres": 0
                }
            finally:
                browser.close()

        doc = Document(html_raw)
        titulo = doc.title()
        html_cuerpo = doc.summary()
        soup = BeautifulSoup(html_cuerpo, "html.parser")
        texto_markdown = self.h2t.handle(str(soup)).strip()

        return {
            "url": url,
            "titulo_detalle": titulo,
            "contenido_markdown": texto_markdown,
            "caracteres": len(texto_markdown)
        }

    def _procesar_novedades_sync(self, novedades: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Procesa múltiples artículos reutilizando una sola instancia de Chromium
        para optimizar CPU/RAM y evitar explosión de procesos.
        """
        resultados = []
        if not novedades:
            return resultados

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=get_stealth_launch_args()
            )
            ctx_options = get_stealth_context_kwargs()
            ctx_options["viewport"] = BROWSER_VIEWPORT
            if DEFAULT_USER_AGENT:
                ctx_options["user_agent"] = DEFAULT_USER_AGENT

            context = browser.new_context(**ctx_options)

            for item in novedades:
                url = item.get("url", "")
                page = context.new_page()
                apply_stealth_sync(page)
                page.route("**/*.{png,jpg,jpeg,svg,gif,css,woff,woff2}", lambda route: route.abort())

                html_raw = ""
                error_msg = None
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=DEEP_PAGE_TIMEOUT_MS)
                    html_raw = page.content()
                except Exception as e:
                    error_msg = str(e)
                finally:
                    page.close()

                if error_msg:
                    resultados.append({
                        **item,
                        "url": url,
                        "error": error_msg,
                        "titulo_detalle": "",
                        "contenido_markdown": "",
                        "caracteres": 0
                    })
                    continue

                doc = Document(html_raw)
                titulo = doc.title()
                html_cuerpo = doc.summary()
                soup = BeautifulSoup(html_cuerpo, "html.parser")
                texto_markdown = self.h2t.handle(str(soup)).strip()

                resultados.append({
                    **item,
                    "url": url,
                    "titulo_detalle": titulo,
                    "contenido_markdown": texto_markdown,
                    "caracteres": len(texto_markdown)
                })

            browser.close()

        return resultados

    async def procesar_novedades_en_profundidad(self, novedades: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._procesar_novedades_sync, novedades)
