# main.py

import asyncio
import json
from scraper import UniversalScraperNoAI
from deep_scraper import DeepScraperNoAI


async def ejecutar_flujo_completo(url_objetivo: str):
    print(f"=== PASO 1: Scrapeando índice en {url_objetivo} ===")
    index_scraper = UniversalScraperNoAI()
    resultado_indice = await index_scraper.scrape(url_objetivo)

    print(f"Sitio: {resultado_indice['site_title']}")
    print(f"Tipo de contenido: {resultado_indice['tipo_contenido']}")

    if resultado_indice["tipo_contenido"] == "lista_entidades":
        items_encontrados = resultado_indice["data"]
        print(f"Total de ítems en portada: {len(items_encontrados)}")

        # Simulación: Tomamos los primeros 2 ítems para hacer Deep Scraping
        novedades_a_procesar = items_encontrados[:10]

        print("\n=== PASO 2: Realizando Deep Scraping de los ítems seleccionados ===")
        deep_scraper = DeepScraperNoAI()
        articulos_completos = await deep_scraper.procesar_novedades_en_profundidad(novedades_a_procesar)

        for i, art in enumerate(articulos_completos, 1):
            print(f"\n---------------- ÍTEM EN PROFUNDIDAD #{i} ----------------")
            print(f"Título Portada: {art['titulo']}")
            print(f"Título Artículo: {art['titulo_detalle']}")
            print(f"URL: {art['url']}")
            print(f"Caracteres extraídos: {art['caracteres']}")
            print("\nTexto Extraído:\n")
            print(art["contenido_markdown"] + "...")
    else:
        print("\nEs un texto continuo único. Contenido extraído:\n")
        print(resultado_indice["data"][:500])


if __name__ == "__main__":
    url_prueba = "https://www.gob.pe/institucion/mininter/noticias"
    asyncio.run(ejecutar_flujo_completo(url_prueba))