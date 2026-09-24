# chatbot_service/app/summarize.py
"""
Resumidor de cambios detectados (intención "resumen").

Convierte los cambios recientes recuperados de PostgreSQL en un texto compacto
y genera con Ollama un resumen ejecutivo en markdown.
"""
import logging
from typing import Any, AsyncIterator, Dict, List

from app import prompts
from app.ollama import OllamaClient
from app.sql_agent import SqlSafeResult

logger = logging.getLogger("uvicorn.error")


def _cambios_a_texto(result: SqlSafeResult, max_items: int = 15) -> str:
    if not result.rows:
        return "(No hay cambios registrados en el período consultado.)"
    lines: List[str] = []
    for row in result.rows[:max_items]:
        pagina = row.get("nombre") or row.get("url") or row.get("pagina") or "Sin nombre"
        fecha = row.get("fecha") or "N/A"
        resumen = row.get("resumen") or ""
        lines.append(f"- [{fecha}] {pagina}: {resumen}"[:500])
    return "\n".join(lines)


async def summarize_changes(
    client: OllamaClient,
    result: SqlSafeResult,
    question: str,
) -> AsyncIterator[str]:
    """Devuelve un flujo de tokens con el resumen ejecutivo de los cambios."""
    cambios = _cambios_a_texto(result)
    prompt = prompts.TEMPLATE_SUMMARIZE.format(cambios=cambios)
    messages = [
        {"role": "system", "content": prompts.SUMMARIZE_SYSTEM},
        {"role": "user", "content": f"{question}\n\n{prompt}"},
    ]
    try:
        async for token in client.generate_stream(messages, temperature=0.2, num_predict=600):
            yield token
    except Exception as e:  # noqa: BLE001
        logger.warning("Fallo streaming del resumen, respondiendo con datos crudos: %s", e)
        yield "\n\n".join(
            f"- **{r.get('nombre') or r.get('url') or 'Página'}** ({r.get('fecha') or 'N/A'}): "
            f"{r.get('resumen')}"
            for r in result.rows[:10]
        )