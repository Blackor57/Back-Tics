# chatbot_service/app/intent.py
"""
Router de intención del chatbot.

Usa qwen2.5:3b (prompt + formato JSON) para clasificar la consulta del usuario
en una de las 6 intenciones: factual, busqueda, comparacion, resumen, estado, accion.
Si Ollama no responde con JSON válido, se aplica un fallback por palabras clave.
"""
import json
import logging
import re
from typing import Any, Dict, List

from app import prompts
from app.ollama import OllamaClient

logger = logging.getLogger("uvicorn.error")

INTENTS = {"factual", "busqueda", "comparacion", "resumen", "estado", "accion"}

# Fallback léxico si Ollama falla: (patrón, intent)
_KEYWORD_RULES: List[tuple[str, str]] = [
    (r"\b(resume|resumen|sintetiza|sintesis)\b", "resumen"),
    (r"\b(compara|comparar|diferencia|vs\.?|version(es)? anteriores?)\b", "comparacion"),
    (r"\b(estado|salud|en linea|caida|cayó|caido|offline|online|severidad|alerta)\b", "estado"),
    (r"\b(scrap\w*|raspa|raspea|analiza[\w\s]*en\s+vivo|monitoreo|programa|agenda|correo|reporte|descarga)\b", "accion"),
    (r"\b(que cambios|cambios|novedades|noticias|contenido|similar|parecido|relacionado|alguna vez (menciono|dijo))\b", "busqueda"),
]


def _fallback_intent(message: str) -> str:
    for pattern, intent in _KEYWORD_RULES:
        if re.search(pattern, message, re.IGNORECASE):
            return intent
    return "factual"


def _parse_intent(raw: str) -> Dict[str, Any]:
    """Extrae intent y confianza de una respuesta JSON (tolera ruido)."""
    try:
        json_block = re.search(r"(\{.*\})", raw, re.DOTALL)
        data = json.loads(json_block.group(1)) if json_block else json.loads(raw)
    except (json.JSONDecodeError, AttributeError, IndexError):
        data = {}

    intent = str(data.get("intent", "")).strip().lower()
    if intent not in INTENTS:
        intent = _fallback_intent(raw)
    return {"intent": intent, "razon": data.get("razon", "")}


class IntentRouter:
    """Clasifica la consulta del usuario usando Ollama (con fallback léxico)."""

    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    async def classify(self, message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        historial_resumido = _serializar_historial(history)
        prompt = (
            f"CONSULTA DEL USUARIO:\n{message}\n\n"
            f"HISTORIAL RECIENTE:\n{historial_resumido}\n\n"
            if historial_resumido.strip()
            else f"CONSULTA DEL USUARIO:\n{message}\n"
        )
        try:
            raw = await self.client.generate(
                prompt,
                system=prompts.INTENT_ROUTER_SYSTEM,
                format="json",
                temperature=0.0,
                num_predict=64,
            )
            result = _parse_intent(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("Router de intención falló, usando heurística: %s", e)
            result = {"intent": _fallback_intent(message), "razon": "fallback por heurística"}

        # La confianza se estima simple: 0.9 si vino de Ollama, 0.6 si vino de heurística
        result.setdefault("confidence", 0.9 if result.get("razon") else 0.6)
        return result


def _serializar_historial(history: List[Dict[str, Any]], max_turns: int = 4) -> str:
    """Convierte el historial en texto plano acotado para el prompt del router."""
    lines: List[str] = []
    for turn in history[-2 * max_turns:]:
        role = "Usuario" if turn.get("role") == "user" else "Asistente"
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines)[:1500]