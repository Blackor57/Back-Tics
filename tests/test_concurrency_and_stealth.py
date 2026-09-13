# tests/test_concurrency_and_stealth.py
import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from bs4 import BeautifulSoup

from app.core.config import MAX_CONCURRENT_BROWSERS, MAX_CONCURRENT_OLLAMA_REQUESTS
from app.utils.stealth_helper import (
    get_stealth_launch_args,
    get_stealth_context_kwargs,
    apply_stealth,
    apply_stealth_sync,
    HAS_PLAYWRIGHT_STEALTH,
)
from app.services.ollama_analyzer import get_ollama_semaphore
from app.utils.utils import limpiar_dom_ruido


class TestConcurrencyAndStealth(unittest.TestCase):
    def test_stealth_launch_args_and_context(self):
        """Verifica que los argumentos de Chromium y opciones de contexto incluyan flags anti-bot."""
        args = get_stealth_launch_args()
        self.assertIn("--disable-blink-features=AutomationControlled", args)
        self.assertIn("--no-sandbox", args)

        ctx_kwargs = get_stealth_context_kwargs()
        self.assertIn("user_agent", ctx_kwargs)
        self.assertIn("Mozilla", ctx_kwargs["user_agent"])
        self.assertIn("extra_http_headers", ctx_kwargs)
        self.assertIn("Sec-Ch-Ua", ctx_kwargs["extra_http_headers"])

    def test_apply_stealth_sync_mock(self):
        """Verifica que apply_stealth_sync aplique las evasiones sin generar excepciones."""
        mock_page = MagicMock()
        del mock_page._playwright_stealth_applied
        apply_stealth_sync(mock_page)
        self.assertTrue(
            mock_page.add_init_script.called or
            mock_page.evaluate.called
        )

    def test_apply_stealth_async_mock(self):
        """Verifica que apply_stealth aplique las evasiones de forma asíncrona."""
        async def run_test():
            mock_page = AsyncMock()
            del mock_page._playwright_stealth_applied
            await apply_stealth(mock_page)
            self.assertTrue(
                mock_page.add_init_script.called or
                mock_page.evaluate.called
            )

        asyncio.run(run_test())

    def test_concurrency_config_and_semaphore(self):
        """Verifica que los límites de concurrencia y los semáforos estén configurados correctamente."""
        self.assertGreaterEqual(MAX_CONCURRENT_BROWSERS, 1)
        self.assertGreaterEqual(MAX_CONCURRENT_OLLAMA_REQUESTS, 1)

        sem = get_ollama_semaphore()
        self.assertIsInstance(sem, asyncio.Semaphore)
        self.assertEqual(sem._value, MAX_CONCURRENT_OLLAMA_REQUESTS)

    def test_limpiar_dom_ruido_publicidad_y_elementos_dinamicos(self):
        """Verifica que limpiar_dom_ruido elimine efectivamente anuncios, cookies y banners."""
        html_sucio = """
        <html>
            <body>
                <header>Encabezado del portal</header>
                <div role="banner" class="banner-top">Banner publicitario superior</div>
                <div class="ad-container" id="adsbox">
                    <p>Anuncio publicitario de Google</p>
                </div>
                <div data-ad-client="ca-pub-12345">Widget publicitario</div>
                <div class="cookie-consent" id="cookie-notice">
                    <p>Este sitio utiliza cookies para mejorar la experiencia.</p>
                </div>
                <div class="view-counter">1,450 personas leyendo esto</div>
                <article>
                    <h1>Título de Noticia Real</h1>
                    <p>Contenido legítimo de la noticia de interés público.</p>
                </article>
                <footer>Pie de página con copyright</footer>
            </body>
        </html>
        """
        soup = BeautifulSoup(html_sucio, "html.parser")
        soup_limpio = limpiar_dom_ruido(soup)

        texto_limpio = soup_limpio.get_text()

        # Debe preservar el contenido real
        self.assertIn("Título de Noticia Real", texto_limpio)
        self.assertIn("Contenido legítimo de la noticia", texto_limpio)

        # Debe haber eliminado el ruido
        self.assertNotIn("Banner publicitario superior", texto_limpio)
        self.assertNotIn("Anuncio publicitario de Google", texto_limpio)
        self.assertNotIn("Widget publicitario", texto_limpio)
        self.assertNotIn("Este sitio utiliza cookies", texto_limpio)
        self.assertNotIn("1,450 personas leyendo", texto_limpio)
        self.assertNotIn("Encabezado del portal", texto_limpio)
        self.assertNotIn("Pie de página con copyright", texto_limpio)

    def test_semaphore_concurrency_limiting(self):
        """Verifica que el semáforo limite estrictamente las operaciones en vuelo concurrentes."""
        async def run_concurrency_simulation():
            sem = asyncio.Semaphore(2)
            active_count = 0
            peak_active = 0

            async def worker():
                nonlocal active_count, peak_active
                async with sem:
                    active_count += 1
                    if active_count > peak_active:
                        peak_active = active_count
                    await asyncio.sleep(0.05)
                    active_count -= 1

            tasks = [asyncio.create_task(worker()) for _ in range(6)]
            await asyncio.gather(*tasks)
            return peak_active

        peak = asyncio.run(run_concurrency_simulation())
        self.assertEqual(peak, 2, "El semáforo debe limitar estrictamente el pico de tareas concurrentes a 2")


if __name__ == "__main__":
    unittest.main()
