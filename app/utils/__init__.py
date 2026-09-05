# app/utils/__init__.py
"""Utilidades para manipulación de HTML, scroll y limpieza de texto."""

from app.utils.utils import (
    configurar_html2text,
    auto_scroll_pagina,
    auto_scroll_pagina_sync,
    limpiar_dom_ruido,
)

__all__ = [
    "configurar_html2text",
    "auto_scroll_pagina",
    "auto_scroll_pagina_sync",
    "limpiar_dom_ruido",
]
