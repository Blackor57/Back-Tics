# chatbot_service/scripts/backfill_embeddings.py
"""
Uso (desde chatbot_service/):
    python scripts/backfill_embeddings.py

Genera embeddings (nomic-embed-text, 768 dims) para los cambios que aún no
tienen cobertura en la tabla `embeddings`.
Equivalente a: curl -X POST http://localhost:8501/admin/backfill-embeddings
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import sync_service
from app.database import ensure_schema, get_session, engine
from app.ollama import ollama_client


async def main(max_items: int, batch: int) -> None:
    await ensure_schema()
    async with get_session() as session:
        conteo = await sync_service.backfill_embeddings(
            session, ollama_client, batch_size=batch, max_items=max_items
        )
        print(f"embeddings creados: {conteo['embeddings']}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera embeddings pgvector para changes.")
    parser.add_argument("--max-items", type=int, default=2000, help="Máximo de cambios a procesar.")
    parser.add_argument("--batch", type=int, default=8, help="Tamaño de lote de embeddings.")
    args = parser.parse_args()
    asyncio.run(main(args.max_items, args.batch))