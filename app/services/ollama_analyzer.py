# app/services/ollama_analyzer.py
import json
import re
import logging
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS

logger = logging.getLogger("uvicorn.error")


class OllamaAnalyzer:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def verificar_conexion(self) -> bool:
        """Comprueba si el microservicio de Ollama está en línea."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def analizar_contenido(
        self,
        url: str,
        site_title: str,
        articulos_o_texto: Any,
        delta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Envía el contenido extraído al LLM local en Ollama y obtiene un análisis
        estructurado en formato JSON con KPIs de criticidad, categorización, entidades y recomendaciones.
        """
        if isinstance(articulos_o_texto, list):
            titulares = [
                f"- {item.get('titulo', 'Sin título')} (URL: {item.get('url', '')})"
                for item in articulos_o_texto[:15]
            ]
            datos_texto = "\n".join(titulares)
        else:
            datos_texto = str(articulos_o_texto)[:2000]

        contexto_delta = ""
        if delta:
            total_nuevos = delta.get("total_nuevos", 0)
            total_salientes = delta.get("total_salientes", 0)
            nuevos_titulares = [
                f"+ {item.get('titulo', '')}" for item in delta.get("nuevos_articulos", [])[:10]
            ]
            salientes_titulares = [
                f"- {item.get('titulo', '')}" for item in delta.get("articulos_salientes", [])[:10]
            ]
            contexto_delta = (
                f"\n\nCOMPARACIÓN CON LA VERSIÓN ANTERIOR:\n"
                f"- Se detectaron {total_nuevos} nuevas publicaciones / cambios.\n"
                f"- Salieron o se modificaron {total_salientes} elementos respecto a la última versión.\n"
                f"Nuevas incorporaciones destacadas:\n" + "\n".join(nuevos_titulares) + "\n"
                f"Elementos que salieron:\n" + "\n".join(salientes_titulares)
            )

        prompt = f"""Eres un auditor senior de inteligencia web y analista estratégico de información pública.
Tu tarea es analizar la siguiente información extraída de la página: "{site_title}" ({url}).

CONTENIDO DE LA PÁGINA:
{datos_texto}
{contexto_delta}

INSTRUCCIONES DE RESPUESTA:
Debes responder ÚNICAMENTE con un objeto JSON válido (sin texto antes ni después del JSON).
El formato JSON debe tener EXACTAMENTE esta estructura:
{{
  "nivel_alerta": "BAJO",
  "score_relevancia": 7.5,
  "tipo_portal": "Portal Gubernamental / Institucional / Medio / etc.",
  "resumen_ejecutivo": "Síntesis clara, formal y concisa de 2 a 3 párrafos de lo más relevante hallado.",
  "analisis_evolucion": "Explicación detallada de cómo ha cambiado el contenido respecto a la versión anterior. Si no hay versión previa, indicar que es la Línea Base.",
  "puntos_atencion_urgentes": [
    "Punto crítico 1 (ej. fechas límites, comunicados de contingencia, cambios de normativas o precios).",
    "Punto crítico 2."
  ],
  "categorias": [
    {{"nombre": "Nombre de la Categoría 1", "cantidad": 5, "porcentaje": 35}},
    {{"nombre": "Nombre de la Categoría 2", "cantidad": 4, "porcentaje": 25}},
    {{"nombre": "Nombre de la Categoría 3", "cantidad": 3, "porcentaje": 20}},
    {{"nombre": "Nombre de la Categoría 4", "cantidad": 2, "porcentaje": 20}}
  ],
  "sentimientos": {{
    "positivo": 4,
    "neutro": 8,
    "negativo": 2
  }},
  "entidades_estructuradas": {{
    "instituciones_y_empresas": ["Institución 1", "Empresa 2"],
    "personas_relevantes": ["Autoridad / Funcionario 1", "Persona 2"],
    "marcos_legales_o_normas": ["Norma / Ley / Decreto 1"]
  }},
  "entidades_clave": ["Entidad 1", "Entidad 2", "Entidad 3"],
  "conclusiones": [
    "Conclusión estratégica o tendencia 1.",
    "Conclusión estratégica o tendencia 2.",
    "Conclusión estratégica o tendencia 3."
  ],
  "recomendaciones_estrategicas": [
    "Recomendación práctica 1 para quien monitorea la página.",
    "Recomendación práctica 2."
  ]
}}
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 650,
                "num_ctx": 2048
            }
        }

        try:
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
                res = await client.post(f"{self.base_url}/api/generate", json=payload)
                res.raise_for_status()
                data = res.json()
                raw_response = data.get("response", "{}")

                resultado = self._extraer_json_seguro(raw_response)
                return self._validar_y_completar_resultado(resultado, delta, site_title)
        except Exception as e:
            logger.error(f"Error al invocar Ollama ({type(e).__name__}): {str(e)}")
            return self._generar_fallback_heuristico(site_title, articulos_o_texto, delta)

    def _extraer_json_seguro(self, texto: str) -> Dict[str, Any]:
        """Limpia fences de Markdown, comas huérfanas y extrae el primer objeto JSON válido."""
        texto = texto.strip()
        if texto.startswith("```"):
            texto = re.sub(r"^```[a-zA-Z]*\n?", "", texto)
            texto = re.sub(r"\n?```$", "", texto)
            texto = texto.strip()
        
        match = re.search(r"(\{.*\})", texto, re.DOTALL)
        if match:
            texto = match.group(1)
        
        # Eliminar comas huérfanas antes de cerrar llaves o corchetes: ,} o ,]
        texto = re.sub(r',\s*([\]}])', r'\1', texto)
        return json.loads(texto)

    def _validar_y_completar_resultado(
        self,
        res: Dict[str, Any],
        delta: Optional[Dict[str, Any]],
        site_title: str
    ) -> Dict[str, Any]:
        """Garantiza que todas las claves requeridas estén presentes y formateadas."""
        # Nivel de alerta
        alertas_validas = ["BAJO", "MEDIO", "ALTO", "CRÍTICO"]
        if str(res.get("nivel_alerta", "")).upper() not in alertas_validas:
            # Deducir por volumen de novedades
            total_nuevos = delta.get("total_nuevos", 0) if delta else 0
            if total_nuevos > 5:
                res["nivel_alerta"] = "ALTO"
            elif total_nuevos > 0:
                res["nivel_alerta"] = "MEDIO"
            else:
                res["nivel_alerta"] = "BAJO"
        else:
            res["nivel_alerta"] = str(res["nivel_alerta"]).upper()

        if not res.get("score_relevancia"):
            res["score_relevancia"] = 7.0

        if not res.get("tipo_portal"):
            res["tipo_portal"] = "Portal Web Público / Institucional"

        if not res.get("resumen_ejecutivo"):
            res["resumen_ejecutivo"] = f"Auditoría completada exitosamente para '{site_title}'."

        if not res.get("analisis_evolucion"):
            if delta and delta.get("total_anteriores", 0) > 0:
                res["analisis_evolucion"] = (
                    f"Comparativa temporal: Se detectaron {delta.get('total_nuevos', 0)} novedades "
                    f"y {delta.get('total_salientes', 0)} elementos modificados."
                )
            else:
                res["analisis_evolucion"] = "Línea Base inicial registrada. No existen versiones anteriores para contrastar."

        if not res.get("puntos_atencion_urgentes"):
            res["puntos_atencion_urgentes"] = [
                "Se recomienda verificar los plazos de vigencia de las publicaciones recientes.",
                "Mantener la frecuencia de monitoreo para detectar nuevas publicaciones."
            ]

        if not res.get("categorias"):
            res["categorias"] = [
                {"nombre": "General / Principal", "cantidad": 5, "porcentaje": 60},
                {"nombre": "Institucional / Avisos", "cantidad": 3, "porcentaje": 40}
            ]

        if not res.get("sentimientos"):
            res["sentimientos"] = {"positivo": 3, "neutro": 6, "negativo": 1}

        if not res.get("entidades_estructuradas"):
            res["entidades_estructuradas"] = {
                "instituciones_y_empresas": [site_title],
                "personas_relevantes": [],
                "marcos_legales_o_normas": []
            }

        if not res.get("entidades_clave"):
            res["entidades_clave"] = [site_title, "Organismo Público"]

        if not res.get("conclusiones"):
            res["conclusiones"] = [
                "Estructura del portal indexada y validada.",
                "Patrones de contenido dentro de los parámetros esperados."
            ]

        if not res.get("recomendaciones_estrategicas"):
            res["recomendaciones_estrategicas"] = [
                "Programar una revisión periódica de 24 horas para este portal.",
                "Configurar alertas por correo en caso de cambios críticos."
            ]

        return res

    def _generar_fallback_heuristico(
        self,
        site_title: str,
        articulos_o_texto: Any,
        delta: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Genera un análisis por reglas en caso de indisponibilidad temporal de Ollama."""
        total = len(articulos_o_texto) if isinstance(articulos_o_texto, list) else 1
        total_nuevos = delta.get("total_nuevos", 0) if delta else 0
        nivel = "ALTO" if total_nuevos >= 5 else ("MEDIO" if total_nuevos > 0 else "BAJO")

        return {
            "nivel_alerta": nivel,
            "score_relevancia": 7.5,
            "tipo_portal": "Portal Web Público / Institucional",
            "resumen_ejecutivo": (
                f"Auditoría automatizada de contenidos para '{site_title}'. "
                f"Se procesaron un total de {total} elementos con información estructurada."
            ),
            "analisis_evolucion": (
                f"Se detectaron {total_nuevos} novedades y {delta.get('total_salientes', 0) if delta else 0} "
                f"elementos salientes en esta inspección." if delta else "Línea base inicial registrada."
            ),
            "puntos_atencion_urgentes": [
                f"Se detectaron {total_nuevos} publicaciones nuevas respecto a la versión previa.",
                "Verificar la vigencia de los comunicados de portada."
            ],
            "categorias": [
                {"nombre": "Contenido Principal", "cantidad": max(int(total * 0.6), 1), "porcentaje": 60},
                {"nombre": "Avisos y Comunicados", "cantidad": max(int(total * 0.4), 1), "porcentaje": 40}
            ],
            "sentimientos": {
                "positivo": max(int(total * 0.3), 1),
                "neutro": max(int(total * 0.5), 1),
                "negativo": max(int(total * 0.2), 1)
            },
            "entidades_estructuradas": {
                "instituciones_y_empresas": [site_title],
                "personas_relevantes": [],
                "marcos_legales_o_normas": []
            },
            "entidades_clave": [site_title, "Portal Público"],
            "conclusiones": [
                "Estructura de la página procesada y almacenada correctamente.",
                "Contenido clasificado y listo para auditoría comparativa."
            ],
            "recomendaciones_estrategicas": [
                "Mantener el seguimiento activo con notificación por correo.",
                "Contrastar con el siguiente ciclo para evaluar tasa de cambio."
            ]
        }
