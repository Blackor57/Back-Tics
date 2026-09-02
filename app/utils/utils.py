# utils.py

import re
from bs4 import BeautifulSoup
import html2text
from app.core.config import MAX_SCROLL_HEIGHT_PX


def configurar_html2text() -> html2text.HTML2Text:
    """Configura el convertidor de HTML a Markdown limpio."""
    h2t = html2text.HTML2Text()
    h2t.ignore_links = False
    h2t.ignore_images = True
    h2t.ignore_tables = False
    h2t.body_width = 0
    h2t.single_line_break = True
    return h2t


async def auto_scroll_pagina(page) -> None:
    """Ejecuta scroll progresivo en la página para disparar peticiones dinámicas XHR / Lazy Loading."""
    script_scroll = f"""
    async () => {{
        await new Promise((resolve) => {{
            let totalHeight = 0;
            let distance = 350;
            let timer = setInterval(() => {{
                let scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;

                if (totalHeight >= {MAX_SCROLL_HEIGHT_PX} || totalHeight >= scrollHeight) {{
                    clearInterval(timer);
                    resolve();
                }}
            }}, 100);
        }});
    }}
    """
    await page.evaluate(script_scroll)


def auto_scroll_pagina_sync(page) -> None:
    """Ejecuta scroll progresivo de forma síncrona para navegadores controlados por Playwright Sync."""
    page.evaluate(f"""() => {{
        window.scrollBy(0, Math.min(1500, {MAX_SCROLL_HEIGHT_PX}));
    }}""")
    page.wait_for_timeout(1000)


def limpiar_dom_ruido(soup: BeautifulSoup) -> BeautifulSoup:
    """Remueve etiquetas basura y componentes de interfaz que no contienen información semántica."""
    etiquetas_basura = [
        "script", "style", "nav", "footer", "header", "noscript",
        "iframe", "svg", "form", "aside", "button", "input", "dialog"
    ]
    for tag in soup(etiquetas_basura):
        tag.decompose()

    # Opcional: Eliminar modales o banners por patrones de clase
    patrones_ruido = re.compile(
        r'(banner|ad-container|cookie|modal|popup|social-share|widget-footer)',
        re.IGNORECASE
    )
    for tag in soup.find_all(class_=patrones_ruido):
        tag.decompose()

    return soup