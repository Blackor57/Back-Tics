import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    from playwright_stealth import Stealth
    _STEALTH_INSTANCE = Stealth()
    HAS_PLAYWRIGHT_STEALTH = True
except ImportError:
    _STEALTH_INSTANCE = None
    HAS_PLAYWRIGHT_STEALTH = False
    logger.warning("playwright-stealth no está instalado. Se utilizarán técnicas de ofuscación nativas por script.")

STEALTH_LAUNCH_ARGS: List[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--lang=es-ES,es",
]

STEALTH_CONTEXT_KWARGS: Dict[str, Any] = {
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "locale": "es-ES",
    "timezone_id": "America/Bogota",
    "extra_http_headers": {
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
}

FALLBACK_STEALTH_SCRIPT = """
(() => {
    // Ocultar navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
    });

    // Simular objeto window.chrome
    if (!window.chrome) {
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
    }

    // Simular plugins comunes de navegador
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });

    // Simular idiomas
    Object.defineProperty(navigator, 'languages', {
        get: () => ['es-ES', 'es', 'en-US', 'en'],
    });

    // Sobrescribir permisos de notificaciones para evitar detección
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
})();
"""


def get_stealth_launch_args() -> List[str]:
    """Retorna argumentos CLI recomendados para Chromium con ofuscación anti-bot."""
    return list(STEALTH_LAUNCH_ARGS)


def get_stealth_context_kwargs() -> Dict[str, Any]:
    """Retorna opciones de contexto (User-Agent, Viewport, Headers) realistas."""
    return dict(STEALTH_CONTEXT_KWARGS)


async def apply_stealth(page_or_context: Any) -> None:
    """
    Aplica técnicas de ofuscación avanzadas para evadir Cloudflare y sistemas anti-bot.
    Utiliza playwright-stealth si está disponible; de lo contrario, inyecta scripts de evasión nativos.
    """
    if HAS_PLAYWRIGHT_STEALTH and _STEALTH_INSTANCE is not None:
        try:
            await _STEALTH_INSTANCE.apply_stealth_async(page_or_context)
            logger.debug("Ofuscación aplicada exitosamente con playwright-stealth.")
            return
        except Exception as e:
            logger.warning(f"Error aplicando playwright-stealth: {e}. Aplicando scripts de respaldo.")

    # Fallback si falla o no está disponible
    try:
        if hasattr(page_or_context, "add_init_script"):
            await page_or_context.add_init_script(FALLBACK_STEALTH_SCRIPT)
        elif hasattr(page_or_context, "evaluate"):
            await page_or_context.evaluate(FALLBACK_STEALTH_SCRIPT)
        logger.debug("Ofuscación aplicada exitosamente mediante script de respaldo.")
    except Exception as e:
        logger.error(f"Error al aplicar scripts de ofuscación de respaldo: {e}")


def apply_stealth_sync(page_or_context: Any) -> None:
    """
    Aplica técnicas de ofuscación avanzadas de forma sincrónica.
    Utiliza playwright-stealth si está disponible; de lo contrario, inyecta scripts nativos.
    """
    if HAS_PLAYWRIGHT_STEALTH and _STEALTH_INSTANCE is not None:
        try:
            _STEALTH_INSTANCE.apply_stealth_sync(page_or_context)
            logger.debug("Ofuscación sync aplicada exitosamente con playwright-stealth.")
            return
        except Exception as e:
            logger.warning(f"Error aplicando playwright-stealth sync: {e}. Aplicando scripts de respaldo.")

    try:
        if hasattr(page_or_context, "add_init_script"):
            page_or_context.add_init_script(FALLBACK_STEALTH_SCRIPT)
        elif hasattr(page_or_context, "evaluate"):
            page_or_context.evaluate(FALLBACK_STEALTH_SCRIPT)
        logger.debug("Ofuscación sync aplicada exitosamente mediante script de respaldo.")
    except Exception as e:
        logger.error(f"Error al aplicar scripts de ofuscación de respaldo sync: {e}")
