# app/services/gemini_vision.py
import base64
import json
import logging
from typing import Any, Dict, Optional
from io import BytesIO

import httpx
import google.generativeai as genai

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_VISION_MODEL,
    GEMINI_GENERATION_MODEL,
    GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE,
)

logger = logging.getLogger("uvicorn.error")


class GeminiVisionService:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.vision_model_name = GEMINI_VISION_MODEL
        self.generation_model_name = GEMINI_GENERATION_MODEL
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"No se pudo configurar Gemini: {e}")

    async def analyze_image(
        self, image_bytes: bytes, mime_type: str = "image/jpeg", prompt: str = None
    ) -> Dict[str, Any]:
        """Analiza una imagen con Gemini Vision y retorna JSON estructurado."""
        if not self.api_key:
            return {
                "success": False,
                "error": "GEMINI_API_KEY no configurada. Debe configurarse en .env",
                "sugerencias_monitoreo": [],
            }

        if prompt is None:
            prompt = """Eres un analista experto en identificación visual e inteligencia de fuentes.

Analiza la imagen proporcionada con gran precisión. Tu tarea es:
1. Identificar qué objeto, elemento, marca, producto, letrero, documento, pantalla o contexto visual aparece.
2. Extraer información relevante (texto visible, marca, modelo, números, logotipo, colores, fecha/hora visibles, ubicación, etc.).
3. Recomendar SÓLO sitios web PÚBLICOS y ÚTILES para monitorear o hacer seguimiento de lo identificado.
4. Para cada sugerencia, incluye: nombre del sitio, URL sugerida (preferentemente dominio oficial o plataforma pública reconocida), categoría (news/monitoring/tech/finance/general), explicación breve de por qué es útil, y nivel_de_prioridad (ALTO/MEDIO/BAJO).
5. Prioriza fuentes oficiales, repositorios públicos, sitios de seguimiento de precios/disponibilidad, medios especializados, bases públicas o fuentes confiables.

Responde ÚNICAMENTE con un objeto JSON válido con esta estructura EXACTA (sin texto antes/después):

{
  "identificacion": {
    "tipo": "producto|marca|componente|documento|letrero|pantalla|evento|otro",
    "descripcion": "Descripción concisa y objetiva de lo que se ve",
    "texto_visible": ["texto extraído si existe"],
    "marca": "marca detectada o null",
    "modelo": "modelo detectado o null",
    "elementos_clave": ["elementos relevantes"]
  },
  "contexto": "Contexto general interpretado",
  "sugerencias_monitoreo": [
    {
      "nombre": "Nombre del sitio web",
      "url": "https://ejemplo.com",
      "categoria": "news|monitoring|tech|finance|general",
      "explicacion": "Razón por la que conviene monitorearlo",
      "nivel_de_prioridad": "ALTO"
    }
  ],
  "palabras_clave": ["palabra1", "palabra2"],
  "recomendaciones_adicionales": "Recomendaciones prácticas breves"
}"""

        try:
            image_data = {
                "mime_type": mime_type,
                "data": image_bytes,
            }
            model = genai.GenerativeModel(self.vision_model_name)
            response = model.generate_content(
                [prompt, {"inline_data": image_data}],
                generation_config={
                    "temperature": GEMINI_TEMPERATURE,
                    "max_output_tokens": GEMINI_MAX_TOKENS,
                },
            )
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                parts = text.split("```")
                if len(parts) >= 3:
                    text = parts[1].strip()
            result = json.loads(text)
            result["success"] = True
            return result
        except Exception as e:
            logger.error(f"Error analizando imagen con Gemini: {e}")
            return {
                "success": False,
                "error": str(e),
                "sugerencias_monitoreo": [],
            }
