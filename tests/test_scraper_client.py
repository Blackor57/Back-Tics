# tests/test_scraper_client.py
import unittest
from app.services.scraper_client import ScraperClient


class TestScraperClient(unittest.TestCase):
    def test_client_initialization(self):
        """Verifica la inicialización del cliente con URL base."""
        client = ScraperClient(base_url="http://test-scraper:8001/")
        self.assertEqual(client.base_url, "http://test-scraper:8001")

    def test_client_fallback_instance(self):
        """Verifica que el cliente tenga instanciado su motor de fallback local."""
        client = ScraperClient()
        self.assertIsNotNone(client._fallback_scraper)
        self.assertIsNotNone(client._fallback_deep)


if __name__ == "__main__":
    unittest.main()
