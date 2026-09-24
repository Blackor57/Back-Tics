# chatbot_service/scripts/sync_from_snapshots.py
"""
Uso (desde chatbot_service/):
    python scripts/sync_from_snapshots.py [--backfill]

Ingiere los snapshots ya scrapeados (tabla `snapshots`) en el esquema
normalizado del chatbot (pages + changes + embeddings).
Equivalente a: curl -X POST http://localhost:8501/admin/sync-from-snapshots
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import sync_service
from app.database import ensure_schema, get_session, engine
from app.ollama import ollama_client


async def main(backfill: bool) -> None:
    await ensure_schema()
    async with get_session() as session:
        conteo = await sync_service.sync_from_snapshots(session)
        print(f"páginas: {conteo['pages']} | cambios: {conteo['changes']}")

        if backfill:
            emb = await sync_service.backfill_embeddings(session, ollama_client)
            print(f"embeddings: {emb['embeddings']}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincroniza snapshots al esquema RAG.")
    parser.add_argument("--backfill", action="store_true", help="Genera también embeddings.")
    args = parser.parse_args()
    asyncio.run(main(args.backfill))