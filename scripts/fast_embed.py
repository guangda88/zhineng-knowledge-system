"""Fast inline embedding generator - updates directly, no staging table.
Each batch commits immediately so progress is preserved on interruption.
Logs to /tmp/fast_embed.log for visibility.
"""
import asyncio, asyncpg, time, logging, os
import torch
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/fast_embed.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL")
MODEL_PATH = os.getenv("EMBEDDING_MODEL", "/data/models/bge-small-zh")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "128"))
MAX_TEXT = 512

async def run():
    device = "cpu"  # GPU OOM — two services using 5.3GB of 6GB VRAM
    logger.info(f"Loading model from {MODEL_PATH} on {device}...")
    model = SentenceTransformer(MODEL_PATH, device=device)
    logger.info(f"Model loaded on {device}: {next(model.parameters()).device}")

    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=4)
    total = await pool.fetchval("SELECT count(*) FROM documents WHERE embedding IS NULL")
    logger.info(f"{total} rows to embed (batch={BATCH_SIZE})")

    if total == 0:
        logger.info("Nothing to do!")
        await pool.close()
        return

    updated = 0
    failed = 0
    t0 = time.time()
    batch_num = 0

    while True:
        rows = await pool.fetch(
            "SELECT id, content FROM documents WHERE embedding IS NULL "
            "ORDER BY id LIMIT $1",
            BATCH_SIZE,
        )
        if not rows:
            break

        texts = [(r["content"] or "")[:MAX_TEXT] for r in rows]

        try:
            embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for row, emb in zip(rows, embeddings):
                        vec_str = "[" + ",".join(map(str, emb.tolist())) + "]"
                        try:
                            await conn.execute(
                                "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                                vec_str,
                                row["id"],
                            )
                            updated += 1
                        except Exception as e3:
                            logger.error(f"Update failed id={row['id']}: {e3}")
                            failed += 1

            batch_num += 1
            elapsed = time.time() - t0
            rate = updated / elapsed if elapsed > 0 else 0
            remaining = (total - updated) / rate if rate > 0 else 0
            logger.info(
                f"batch {batch_num}: {updated}/{total} ({updated*100//total}%) "
                f"rate={rate:.1f}/s eta={remaining:.0f}s"
            )
        except Exception as e:
            logger.error(f"Batch encode failed: {e}")
            failed += len(rows)

    elapsed = time.time() - t0
    logger.info(f"Done: {updated} updated, {failed} failed in {elapsed:.0f}s")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(run())
