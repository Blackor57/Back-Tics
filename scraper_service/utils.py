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
    """
    Remueve etiquetas basura y componentes de interfaz que no contienen información semántica:
    scripts, estilos, banners publicitarios, widgets de cookies, contadores y elementos dinámicos.
    """
    etiquetas_basura = [
        "script", "style", "nav", "footer", "header", "noscript",
        "iframe", "svg", "form", "aside", "button", "input", "dialog"
    ]
    for tag in soup(etiquetas_basura):
        tag.decompose()

    patrones_ruido = re.compile(
        r'(banner|ad-container|advertisement|adsbox|sponsor|cookie|consent|modal|popup|social-share|share-buttons|widget-footer|related-posts|trending-bar|contador-visitas|view-counter|fecha-carga|live-update|timestamp-relative)',
        re.IGNORECASE
    )
    for tag in soup.find_all(class_=patrones_ruido):
        tag.decompose()

    for tag in soup.find_all(id=patrones_ruido):
        tag.decompose()

    for tag in soup.find_all(attrs={"role": re.compile(r'^(banner|complementary)$', re.IGNORECASE)}):
        tag.decompose()

    for tag in soup.find_all(attrs={"aria-modal": "true"}):
        tag.decompose()

    for tag in soup.find_all(attrs={"data-ad-client": True}):
        tag.decompose()

    for tag in soup.find_all(attrs={"data-ad-slot": True}):
        tag.decompose()

    return soup
