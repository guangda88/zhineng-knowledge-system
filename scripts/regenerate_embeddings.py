"""Regenerate all embeddings using BGE-small-zh-v1.5 model."""
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 64


async def regenerate_table(pool, model, table: str, text_columns: list[str], label: str):
    """Regenerate embeddings for a single table."""
    loop = asyncio.get_event_loop()

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM {table} WHERE embedding IS NULL"
        )

    if total == 0:
        logger.info(f"[{label}] No rows to update")
        return 0

    logger.info(f"[{label}] Processing {total} rows...")
    updated = 0
    failed = 0

    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT id, {', '.join(text_columns)} FROM {table} "
                f"WHERE embedding IS NULL ORDER BY id LIMIT {BATCH_SIZE}"
            )

        if not rows:
            break

        texts = []
        for row in rows:
            parts = [str(row[c]) for c in text_columns if row[c]]
            texts.append("\n".join(parts)[:512])

        try:
            embeddings = await loop.run_in_executor(
                None,
                lambda: model.encode(texts, normalize_embeddings=True, batch_size=BATCH_SIZE).tolist(),
            )

            async with pool.acquire() as conn:
                for row, embedding in zip(rows, embeddings):
                    try:
                        vector_str = "[" + ",".join(map(str, embedding)) + "]"
                        await conn.execute(
                            f"UPDATE {table} SET embedding = $1::vector WHERE id = $2",
                            vector_str, row["id"],
                        )
                        updated += 1
                    except Exception as e:
                        logger.error(f"[{label}] Update row {row['id']}: {e}")
                        failed += 1
        except Exception as e:
            logger.error(f"[{label}] Batch embed failed: {e}")
            failed += len(rows)

        if updated % 500 < BATCH_SIZE:
            logger.info(f"[{label}] Progress: {updated}/{total} ({failed} failed)")

    logger.info(f"[{label}] Done: {updated} updated, {failed} failed")
    return updated


async def main():
    import asyncpg
    from sentence_transformers import SentenceTransformer

    logger.info("Loading BGE-small-zh-v1.5 model...")
    loop = asyncio.get_event_loop()
    model = await loop.run_in_executor(
        None,
        lambda: SentenceTransformer("BAAI/bge-small-zh-v1.5", device="cpu"),
    )
    logger.info(f"Model loaded, dim={model.get_sentence_embedding_dimension()}")

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb",
    )
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=4)

    try:
        t0 = time.time()
        await regenerate_table(pool, model, "documents", ["title", "content"], "documents")
        await regenerate_table(pool, model, "textbook_blocks", ["content"], "textbook_blocks")
        await regenerate_table(pool, model, "textbook_blocks_v2", ["content"], "textbook_blocks_v2")
        elapsed = time.time() - t0
        logger.info(f"All done in {elapsed:.0f}s")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
