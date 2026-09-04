# scraper_service/scraper.py
import asyncio
import re
from typing import Dict, Any, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from readability import Document
from playwright.sync_api import sync_playwright

try:
    from config import BROWSER_VIEWPORT, DEFAULT_USER_AGENT, PAGE_TIMEOUT_MS
    from utils import limpiar_dom_ruido, configurar_html2text, auto_scroll_pagina_sync
except ImportError:
    from .config import BROWSER_VIEWPORT, DEFAULT_USER_AGENT, PAGE_TIMEOUT_MS
    from .utils import limpiar_dom_ruido, configurar_html2text, auto_scroll_pagina_sync


class UniversalScraperNoAI:
    def __init__(self):
        self.h2t = configurar_html2text()

    def _extraer_entidades(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        bloques = soup.find_all(["article", "li", "tr"])
        if not bloques or len(bloques) < 3:
            candidatos = soup.find_all(["div", "section"])
            bloques = [
                c for c in candidatos
                if c.find(["h1", "h2", "h3", "h4", "h5", "strong"]) and c.find("a", href=True)
            ]

        items = []
        urls_vistas = set()

        for bloque in bloques:
            enlace_tag = bloque.find("a", href=True) if bloque.name != "a" else bloque
            if not enlace_tag:
                continue

            raw_url = enlace_tag["href"].strip()
            full_url = urljoin(base_url, raw_url)

            if full_url in urls_vistas or full_url.startswith("javascript:") or full_url == base_url:
                continue

            titulo_tag = bloque.find(["h1", "h2", "h3", "h4", "h5", "strong"])
            titulo = titulo_tag.get_text(strip=True) if titulo_tag else enlace_tag.get_text(strip=True)
            titulo = re.sub(r'\s+', ' ', titulo).strip()

            if len(titulo) >= 12:
                urls_vistas.add(full_url)
                items.append({"titulo": titulo, "url": full_url})

        return items

    def _ejecutar_scrape_sync(self, url: str) -> Dict[str, Any]:
        """Ejecuta Playwright de forma síncrona en un worker thread."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport=BROWSER_VIEWPORT,
                user_agent=DEFAULT_USER_AGENT
            )
            page = context.new_page()
            page.route("**/*.{png,jpg,jpeg,svg,gif,css,woff,woff2}", lambda route: route.abort())

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                auto_scroll_pagina_sync(page)
                page_title = page.title()
                html_raw = page.content()
            except Exception as e:
                raise RuntimeError(f"Fallo al cargar la página {url}: {str(e)}")
            finally:
                browser.close()

        soup = BeautifulSoup(html_raw, "html.parser")
        soup = limpiar_dom_ruido(soup)

        entidades = self._extraer_entidades(soup, url)

        if len(entidades) >= 3:
            return {
                "url": url,
                "site_title": page_title,
                "tipo_contenido": "lista_entidades",
                "total_items": len(entidades),
                "data": entidades
            }

        doc = Document(html_raw)
        titulo_documento = doc.title() or page_title
        html_cuerpo = doc.summary()

        soup_doc = BeautifulSoup(html_cuerpo, "html.parser")
        texto_limpio_md = self.h2t.handle(str(soup_doc)).strip()

        return {
            "url": url,
            "site_title": titulo_documento,
            "tipo_contenido": "articulo_individual",
            "total_items": 1,
            "data": texto_limpio_md
        }

    async def scrape(self, url: str) -> Dict[str, Any]:
        """Envuelve la ejecución síncrona en un threadpool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._ejecutar_scrape_sync, url)
