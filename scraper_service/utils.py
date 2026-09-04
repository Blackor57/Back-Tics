# scraper_service/utils.py
import re
from bs4 import BeautifulSoup
import html2text

try:
    from config import MAX_SCROLL_HEIGHT_PX
except ImportError:
    from .config import MAX_SCROLL_HEIGHT_PX



def configurar_html2text() -> html2text.HTML2Text:
    """Configura el convertidor de HTML a Markdown limpio."""
    h2t = html2text.HTML2Text()
    h2t.ignore_links = False
    h2t.ignore_images = True
    h2t.ignore_tables = False
    h2t.body_width = 0
    h2t.single_line_break = True
    return h2t


def auto_scroll_pagina_sync(page) -> None:
    """Ejecuta scroll progresivo de forma síncrona para disparar Lazy Loading."""
    page.evaluate(f"""() => {{
        window.scrollBy(0, Math.min(1500, {MAX_SCROLL_HEIGHT_PX}));
    }}""")
    page.wait_for_timeout(1000)


def limpiar_dom_ruido(soup: BeautifulSoup) -> BeautifulSoup:
    """Remueve etiquetas y componentes de interfaz innecesarios."""
    etiquetas_basura = [
        "script", "style", "nav", "footer", "header", "noscript",
        "iframe", "svg", "form", "aside", "button", "input", "dialog"
    ]
    for tag in soup(etiquetas_basura):
        tag.decompose()

    patrones_ruido = re.compile(
        r'(banner|ad-container|cookie|modal|popup|social-share|widget-footer)',
        re.IGNORECASE
    )
    for tag in soup.find_all(class_=patrones_ruido):
        tag.decompose()

    return soup
