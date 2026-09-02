# config.py

BROWSER_VIEWPORT = {"width": 1440, "height": 900}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

PAGE_TIMEOUT_MS = 30000
DEEP_PAGE_TIMEOUT_MS = 25000

# Límite máximo de scroll en píxeles para detectar Lazy Loading sin bucles infinitos
MAX_SCROLL_HEIGHT_PX = 3000