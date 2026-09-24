# chatbot_service/app/vector_search.py
"""
Búsqueda semántica con pgvector.

1. Embedding de la consulta con nomic-embed-text (768 dims) vía Ollama.
2. SELECT sobre `embeddings` ordenado por distancia coseno `<=>`.
3. JOIN con changes y pages para devolver contexto enriquecido.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import VECTOR_TOP_K
from app.database import get_session
from app.ollama import OllamaClient

logger = logging.getLogger("uvicorn.error")

_SEARCH_SQL = """
SELECT
    e.id                                   AS embedding_id,
    c.id                                   AS change_id,
    p.nombre                               AS pagina,
    p.url                                  AS url,
    c.fecha                                AS fecha,
    c.resumen                              AS resumen,
    c.contenido_diff                       AS contenido_diff,
    c.tipo                                 AS tipo,
    1 - (e.vector <=> CAST(:q AS vector)) AS similitud
FROM embeddings e
JOIN changes c ON c.id = e.change_id
JOIN pages p ON p.id = c.page_id
ORDER BY e.vector <=> CAST(:q AS vector)
LIMIT :k
"""


def _format_number(value: Any) -> Any:
    try:
        if isinstance(value, float):
            return round(value, 4)
        return float(value)
    except (TypeError, ValueError):
        return value


def _to_vector_literal(values: List[float]) -> str:
    """Serializa una lista de floats como literal pgvector: '[0.10, -0.02, ...]'."""
    return "[" + ",".join(f"{v:.12g}" for v in values) + "]"


class VectorSearch:
    """Recupera cambios semánticamente similares a una consulta."""

    def __init__(self, client: OllamaClient, top_k: int = VECTOR_TOP_K) -> None:
        self.client = client
        self.top_k = top_k

    async def search(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        q_emb = await self.client.embed_query(query)
        if q_emb is None:
            logger.warning("No se pudo generar el embedding de la consulta.")
            return []

        limit = k or self.top_k
        try:
            async with get_session() as session:
                result = await session.execute(
                    text(_SEARCH_SQL),
                    {"q": _to_vector_literal(q_emb), "k": min(limit, 20)},
                )
                rows = result.mappings().all()
        except Exception as e:  # noqa: BLE001
            logger.warning("Búsqueda vectorial falló: %s", e)
            return []

        return [
            {
                "change_id": r["change_id"],
                "pagina": r["pagina"] or r["url"] or "Sin nombre",
                "url": r["url"],
                "fecha": str(r["fecha"]) if r["fecha"] else None,
                "resumen": r["resumen"],
                "contenido": (r["contenido_diff"] or "")[:1500],
                "tipo": r["tipo"],
                "similitud": _format_number(r["similitud"]),
            }
            for r in rows
        ]

    def format_context(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "(No se encontraron resultados semánticamente relacionados.)"
        lines = []
        for i, row in enumerate(results, start=1):
            lines.append(
                f"[{i}] Página: {row['pagina']} | URL: {row['url']} | "
                f"Fecha: {row['fecha'] or 'N/A'} | Similitud: {row['similitud']}"
            )
            if row.get("resumen"):
                lines.append(f"    Resumen: {row['resumen']}")
            if row.get("contenido"):
                lines.append(f"    Contenido: {row['contenido'][:800]}")
        return "\n".join(lines)[:6000]