# scraper_service/deep_scraper.py
import asyncio
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from readability import Document
from playwright.sync_api import sync_playwright

try:
    from config import BROWSER_VIEWPORT, DEFAULT_USER_AGENT, DEEP_PAGE_TIMEOUT_MS
    from utils import configurar_html2text
except ImportError:
    from .config import BROWSER_VIEWPORT, DEFAULT_USER_AGENT, DEEP_PAGE_TIMEOUT_MS
    from .utils import configurar_html2text


class DeepScraperNoAI:
    def __init__(self):
        self.h2t = configurar_html2text()

    def _extraer_articulo_sync(self, url: str) -> Dict[str, Any]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport=BROWSER_VIEWPORT,
                user_agent=DEFAULT_USER_AGENT
            )
            page = context.new_page()
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
        resultados = []
        for item in novedades:
            detalle = self._extraer_articulo_sync(item["url"])
            resultados.append({**item, **detalle})
        return resultados

    async def procesar_novedades_en_profundidad(self, novedades: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._procesar_novedades_sync, novedades)
