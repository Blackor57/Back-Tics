# app/services/scraper_client.py
import logging
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import SCRAPER_SERVICE_URL
from app.services.scraper import UniversalScraperNoAI
from app.services.deep_scraper import DeepScraperNoAI

logger = logging.getLogger("scraper_client")


class ScraperClient:
    """
    Cliente HTTP inter-servicio que comunica el Core API con el Microservicio de Scraping.
    Implementa tolerancia a fallos con fallback a ejecución local si el microservicio remoto no está activo.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or SCRAPER_SERVICE_URL).rstrip("/")
        self.timeout = httpx.Timeout(connect=5.0, read=90.0, write=10.0, pool=10.0)
        self._fallback_scraper = UniversalScraperNoAI()
        self._fallback_deep = DeepScraperNoAI()

    async def scrape_index(self, url: str) -> Dict[str, Any]:
        """Solicita al microservicio de scraping extraer el índice de la URL dada."""
        endpoint = f"{self.base_url}/scrape/index"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(endpoint, json={"url": url})
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Scraper service respondió status {res.status_code}: {res.text}")
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.warning(
                f"Microservicio de Scraping inaccesible en {self.base_url} ({str(e)}). "
                f"Activando fallback de extracción en el proceso local..."
            )
        except Exception as e:
            logger.error(f"Error al comunicar con Scraper Service: {str(e)}. Intentando fallback local...")

        # Fallback local
        return await self._fallback_scraper.scrape(url)

    async def scrape_deep(self, items: List[Dict[str, str]]) -> Dict[str, Any]:
        """Solicita al microservicio de scraping procesar artículos en profundidad."""
        endpoint = f"{self.base_url}/scrape/deep"
        try:
            payload_items = [{"titulo": i.get("titulo", ""), "url": i["url"]} for i in items]
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(endpoint, json={"items": payload_items})
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Scraper service respondió status {res.status_code}: {res.text}")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.warning(f"Scraper service inaccesible en {self.base_url}. Ejecutando deep scraping localmente...")
        except Exception as e:
            logger.error(f"Error en comunicación con Scraper Service: {str(e)}. Usando fallback local...")

        # Fallback local
        articulos = await self._fallback_deep.procesar_novedades_en_profundidad(items)
        return {
            "total_procesados": len(articulos),
            "articulos": articulos
        }

    async def scrape_full_pipeline(self, url: str, limit: int = 5) -> Dict[str, Any]:
        """Solicita al microservicio de scraping la extracción completa de portada + novedades."""
        endpoint = f"{self.base_url}/scrape/full-pipeline"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(endpoint, json={"url": url, "limit": limit})
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Scraper service respondió status {res.status_code}: {res.text}")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.warning(f"Scraper service inaccesible en {self.base_url}. Ejecutando full-pipeline localmente...")
        except Exception as e:
            logger.error(f"Error en comunicación con Scraper Service: {str(e)}. Usando fallback local...")

        # Fallback local
        indice = await self._fallback_scraper.scrape(url)
        if indice.get("tipo_contenido") != "lista_entidades":
            return {
                "url_origen": url,
                "sitio_titulo": indice.get("site_title", ""),
                "total_indexados": 1,
                "total_procesados_profundidad": 1,
                "articulos": [
                    {
                        "url": url,
                        "titulo_detalle": indice.get("site_title", ""),
                        "contenido_markdown": indice.get("data", ""),
                        "caracteres": len(indice.get("data", ""))
                    }
                ]
            }

        noticias = indice.get("data", [])[:limit]
        articulos = await self._fallback_deep.procesar_novedades_en_profundidad(noticias)
        return {
            "url_origen": url,
            "sitio_titulo": indice.get("site_title", ""),
            "total_indexados": len(indice.get("data", [])),
            "total_procesados_profundidad": len(articulos),
            "articulos": articulos
        }
