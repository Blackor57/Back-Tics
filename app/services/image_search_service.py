# app/services/image_search_service.py
"""
Servicio de búsqueda visual por imagen usando Google Gemini Vision.

Flujo:
1. Recibe los bytes de la imagen (.jpg, .png, .webp).
2. Envía la imagen a Gemini con un prompt especializado de visión por computadora.
3. Gemini identifica detalladamente el producto u objeto en la foto (marca, modelo, tipo, etc.).
4. Construye una URL de búsqueda directa y de alta precisión (por defecto en Amazon con el producto exacto,
   además de Google Shopping y enlaces directos).
5. Retorna la información estructurada con todas las variantes de URL solicitadas.
"""

import base64
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("uvicorn.error")

# URL base de la REST API de Gemini
_GEMINI_REST_BASE = "https://generativelanguage.googleapis.com/v1/models"

# Tiempo máximo de espera para la llamada a Gemini Vision
_GEMINI_TIMEOUT = 45.0


class ImageSearchService:
    """Analiza imágenes con Gemini Vision y genera URLs de búsqueda precisas."""

    async def search_by_image(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> Dict[str, Any]:
        """
        Recibe los bytes de una imagen, identifica el producto mediante Gemini Vision
        y devuelve la URL más cercana y precisa (por defecto búsqueda en Amazon con ese producto).

        Args:
            image_bytes: Contenido binario de la imagen.
            mime_type: MIME type de la imagen (por defecto 'image/jpeg').

        Returns:
            Dict con:
                - url: URL principal de búsqueda (por defecto Amazon con el producto)
                - result_url: Alias de url
                - similar_url: Alias de url
                - link: Alias de url
                - product_name: Nombre detallado del producto identificado
                - search_query: Término de búsqueda optimizado
                - category: Categoría del producto
                - confidence: Nivel de confianza ('alta', 'media', 'baja')
                - amazon_url: URL directa de búsqueda en Amazon
                - google_shopping_url: URL de búsqueda en Google Shopping
                - google_search_url: URL de búsqueda en Google
        """
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY no está configurada. "
                "Agrégala al archivo .env para habilitar la búsqueda por imagen."
            )

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = self._build_prompt()
        request_body = self._build_request_body(b64_image, mime_type, prompt)

        raw_text = await self._call_gemini(request_body)
        result = self._extract_result(raw_text)
        return result

    # ------------------------------------------------------------------
    # Prompts & Request Body
    # ------------------------------------------------------------------

    def _build_prompt(self) -> str:
        return (
            "Eres un experto de clase mundial en visión por computadora y reconocimiento de productos para e-commerce. "
            "Examina minuciosamente la imagen proporcionada e identifica con precisión el producto, objeto o dispositivo principal. "
            "\n\n"
            "Instrucciones de precisión:\n"
            "1. Si la imagen muestra un teclado, determina si es mecánico o de membrana, color, factor de forma (60%, TKL, completo), "
            "tipo de switches si son visibles, y marca o modelo si tiene logotipo o tipografía reconocible.\n"
            "2. Si es cualquier otro producto (mouse, ropa, tecnología, etc.), extrae marca, modelo y características distintivas.\n"
            "3. En 'search_query', crea la frase de búsqueda IDEAL para encontrar exactamente este artículo en Amazon o Google. "
            "Debe tener entre 3 y 8 palabras clave precisas y en español o inglés según proceda (ej: 'teclado mecanico gamer rgb switch azul').\n"
            "\n\n"
            "Responde ÚNICAMENTE con un objeto JSON válido con exactamente la siguiente estructura:\n"
            "{\n"
            '  "producto": "Nombre descriptivo y específico del producto identificado",\n'
            '  "marca": "Marca si es visible/identificable, o null",\n'
            '  "modelo": "Modelo exacto si es reconocible, o null",\n'
            '  "categoria": "Categoría (ej: Teclados, Computación, Periféricos, Audio, etc.)",\n'
            '  "search_query": "término de búsqueda optimizado para Amazon",\n'
            '  "direct_url": null,\n'
            '  "confianza": "alta"\n'
            "}"
        )

    def _build_request_body(self, b64_image: str, mime_type: str, prompt: str) -> dict:
        return {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image,
                            }
                        },
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }

    # ------------------------------------------------------------------
    # Llamada a Gemini con Failover Automático
    # ------------------------------------------------------------------

    async def _call_gemini(self, body: dict) -> str:
        """
        Llama a la REST API de Gemini. Si el modelo principal experimenta alta demanda (503/429),
        intenta automáticamente con modelos alternativos compatibles disponibles en la cuenta.
        """
        preferred_model = GEMINI_MODEL or "gemini-3.5-flash"
        fallback_candidates = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

        models_to_try: List[str] = [preferred_model]
        for candidate in fallback_candidates:
            if candidate not in models_to_try:
                models_to_try.append(candidate)

        last_error = None

        for model in models_to_try:
            url = f"{_GEMINI_REST_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                async with httpx.AsyncClient(timeout=_GEMINI_TIMEOUT) as client:
                    response = await client.post(url, json=body)

                    # Si el modelo tiene un pico temporal de demanda, intentar con el siguiente
                    if response.status_code in (503, 429) and model != models_to_try[-1]:
                        logger.warning(
                            "Modelo %s no disponible temporalmente (%s). Reintentando con modelo alternativo...",
                            model,
                            response.status_code,
                        )
                        continue

                    response.raise_for_status()
                    data = response.json()

                    # Extraer texto de la respuesta
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError) as exc:
                        logger.error(
                            "Estructura inesperada de Gemini en modelo %s: %s",
                            model,
                            json.dumps(data)[:400],
                        )
                        raise RuntimeError(
                            f"Gemini ({model}) no devolvió partes de contenido válidas."
                        ) from exc

            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in (503, 429) and model != models_to_try[-1]:
                    logger.warning(
                        "Error %s en modelo %s. Intentando fallback...",
                        exc.response.status_code,
                        model,
                    )
                    continue

                logger.error(
                    "Gemini API error %s en modelo %s: %s",
                    exc.response.status_code,
                    model,
                    exc.response.text[:500],
                )
                raise RuntimeError(
                    f"Error al contactar Gemini ({exc.response.status_code}): "
                    f"{exc.response.text[:250]}"
                ) from exc

            except Exception as exc:
                last_error = exc
                logger.error(
                    "Error de conexión con Gemini en modelo %s: %s",
                    model,
                    str(exc),
                )
                if model != models_to_try[-1]:
                    continue
                raise RuntimeError(f"No se pudo conectar a Gemini: {str(exc)}") from exc

        raise RuntimeError(
            f"No fue posible obtener respuesta de Gemini tras intentar con {models_to_try}: {str(last_error)}"
        )

    # ------------------------------------------------------------------
    # Extracción y Construcción de URLs
    # ------------------------------------------------------------------

    def _extract_result(self, raw_text: str) -> Dict[str, Any]:
        """
        Parsea el texto JSON devuelto por Gemini y construye las URLs
        de búsqueda en Amazon y otros motores con la máxima precisión posible.
        """
        raw_text = raw_text.strip()

        # Limpiar posibles delimitadores markdown ```json ... ```
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

        parsed_data: Optional[Dict[str, Any]] = None

        # Intento 1: Parseo de JSON directo
        try:
            parsed_data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Buscar el primer bloque { ... } con regex
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                try:
                    parsed_data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        if parsed_data and isinstance(parsed_data, dict):
            return self._build_urls_from_payload(parsed_data)

        # Intento 2: Fallback por regex si Gemini devolvió texto sin formato
        logger.warning(
            "Respuesta de Gemini no fue un JSON estricto. Aplicando fallback de texto: %s",
            raw_text[:200],
        )

        # Si hay una URL en el texto
        url_match = re.search(r"https?://[^\s\"'<>]+", raw_text)
        if url_match:
            found_url = url_match.group(0).rstrip(".,;)")
            return {
                "url": found_url,
                "result_url": found_url,
                "similar_url": found_url,
                "link": found_url,
                "product_name": "Producto identificado",
                "search_query": "producto",
                "category": None,
                "confidence": "media",
                "amazon_url": found_url,
                "google_shopping_url": found_url,
                "google_search_url": found_url,
            }

        # Intento 3: Usar las primeras palabras como término de búsqueda
        clean_words = re.sub(r"[^\w\s]", "", raw_text).split()[:6]
        search_query = " ".join(clean_words) if clean_words else "producto"
        return self._build_urls_from_payload({
            "producto": search_query,
            "search_query": search_query,
            "confianza": "baja",
        })

    def _build_urls_from_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera URLs de alta precisión para Amazon, Google Shopping y Google Search.
        Por defecto la URL principal entregada es la de Amazon buscando el producto específico.
        """
        # Extraer el término de búsqueda más preciso disponible
        search_query = (
            data.get("search_query")
            or data.get("producto")
            or data.get("item")
            or "producto"
        ).strip()

        # Limpiar comillas innecesarias
        search_query = search_query.strip("\"'")

        # URL codificada para parámetros GET
        encoded_query = urllib.parse.quote_plus(search_query)

        # 1. URL por defecto: Búsqueda del producto en Amazon
        amazon_url = f"https://www.amazon.com/s?k={encoded_query}"

        # 2. URLs complementarias
        google_shopping_url = f"https://www.google.com/search?tbm=shop&q={encoded_query}"
        google_search_url = f"https://www.google.com/search?q={encoded_query}"

        # Si Gemini proporcionó una URL directa válida y verificable
        direct_url = data.get("direct_url") or data.get("url")
        primary_url = amazon_url
        if direct_url and isinstance(direct_url, str) and direct_url.startswith("http") and not direct_url.endswith("www"):
            # Si hay una URL directa de alta fidelidad que no sea un placeholder genérico
            if "amazon" in direct_url or not direct_url.endswith(".com/"):
                primary_url = direct_url

        producto = data.get("producto") or search_query
        confidence = data.get("confianza") or data.get("confidence") or "alta"
        category = data.get("categoria") or data.get("category")

        logger.info(
            "Identificación exitosa: producto='%s' | query='%s' | amazon_url='%s'",
            producto,
            search_query,
            amazon_url,
        )

        return {
            "url": primary_url,
            "result_url": primary_url,
            "similar_url": primary_url,
            "link": primary_url,
            "product_name": producto,
            "search_query": search_query,
            "category": category,
            "confidence": confidence,
            "amazon_url": amazon_url,
            "google_shopping_url": google_shopping_url,
            "google_search_url": google_search_url,
        }
