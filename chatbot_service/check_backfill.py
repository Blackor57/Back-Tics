# check_backfill.py - reintento de sync + backfill de embeddings
import asyncio
import sys

sys.path.insert(0, ".")

from app.database import get_session, init_engine  # noqa: E402
from app import sync_service  # noqa: E402
from sqlalchemy import text  # noqa: E402


async def main():
    from app.ollama import OllamaClient
    client = OllamaClient(base_url="http://ollama:11434")
    async with get_session() as s:
        r = await s.execute(text("SELECT count(*) FROM changes"))
        n = r.scalar_one()
        print("changes:", n)
        r = await s.execute(text("SELECT count(*) FROM embeddings"))
        print("embeddings:", r.scalar_one())
        if n:
            c = await sync_service.backfill_embeddings(s, client)
            print("backfill result:", c)


asyncio.run(main())
