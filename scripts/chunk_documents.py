"""
文档分块脚本 - 使用远程 embedding 服务
将 documents 表中的长文档（>400字符）分块存入 doc_chunks 表。
"""

import asyncio
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL"),
)
EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")

CHUNK_SIZE = 300
OVERLAP = 50
MIN_DOC_CHARS = 400
DOC_BATCH = 32
EMBED_BATCH = 16
CATEGORIES = os.getenv("CHUNK_CATEGORIES", "")  # comma-separated, e.g. "佛家,道家,中医"
SKIP_EMBED = os.getenv("SKIP_EMBED", "").strip().lower() in ("1", "true", "yes")

_SENTENCE_ENDS = re.compile(r"[。！？；\n]")


def chunk_text(text: str):
    if len(text) <= CHUNK_SIZE:
        return [(text, 0, len(text))]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            m = _SENTENCE_ENDS.search(text[end:min(end + 50, len(text))])
            if m:
                end += m.end()
        else:
            end = len(text)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append((chunk, start, end))
        start = end - OVERLAP
        if chunks and start <= chunks[-1][1]:
            start = end
    return chunks


def segment(text: str) -> str:
    try:
        import jieba
        jieba.setLogLevel(logging.WARNING)
        words = jieba.lcut(text)
        valid = set("仁义礼智信道德气心神精")
        return " ".join(w for w in words if w.strip() and (len(w.strip()) > 1 or w.strip() in valid))
    except ImportError:
        return text


async def embed(client, texts):
    r = await client.post(f"{EMBEDDING_URL}/embed_batch", json={"texts": texts}, timeout=120)
    if r.status_code == 200:
        return r.json()["embeddings"]
    raise RuntimeError(f"Embed error {r.status_code}: {r.text[:200]}")


async def main():
    conn = await asyncpg.connect(DB_URL)
    logger.info("DB connected")

    cats = [c.strip() for c in CATEGORIES.split(",") if c.strip()] if CATEGORIES else []
    cat_clause = ""
    cat_params = []
    if cats:
        cat_clause = "AND d.category = ANY($3)"
        cat_params = [cats]
        logger.info(f"Filtering categories: {cats}")

    need_q = "SELECT count(*) FROM documents d WHERE length(d.content) > $1 "
    if cats:
        need_q += "AND d.category = ANY($2)"
        need = await conn.fetchval(need_q, MIN_DOC_CHARS, cats)
    else:
        need = await conn.fetchval(need_q, MIN_DOC_CHARS)
    done = await conn.fetchval("SELECT count(DISTINCT doc_id) FROM doc_chunks") or 0
    logger.info(f"Documents to chunk: {need}, already done: {done}")

    async with httpx.AsyncClient(timeout=120) as client:
        total_chunks = 0
        total_docs = 0

        offset = 0
        while True:
            if cats:
                docs = await conn.fetch(
                    """
                    SELECT id, content FROM documents d
                    WHERE length(d.content) > $1
                      AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
                      AND d.category = ANY($2)
                    ORDER BY id LIMIT $3
                    """,
                    MIN_DOC_CHARS,
                    cats,
                    DOC_BATCH,
                )
            else:
                docs = await conn.fetch(
                    """
                    SELECT id, content FROM documents d
                    WHERE length(d.content) > $1
                      AND NOT EXISTS (SELECT 1 FROM doc_chunks dc WHERE dc.doc_id = d.id)
                    ORDER BY id LIMIT $2
                    """,
                    MIN_DOC_CHARS,
                    DOC_BATCH,
                )
            if not docs:
                break

            all_parts = []
            for doc in docs:
                parts = chunk_text(doc["content"])
                for idx, (text, s, e) in enumerate(parts):
                    all_parts.append((doc["id"], idx, text))

            if not all_parts:
                continue

            texts = [p[2] for p in all_parts]

            if SKIP_EMBED:
                for j, (doc_id, chunk_idx, content) in enumerate(all_parts):
                    seg = segment(content)
                    await conn.execute(
                        """INSERT INTO doc_chunks (doc_id, chunk_index, content, search_vector)
                        VALUES ($1, $2, $3, to_tsvector('simple', $4))
                        ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                            content = EXCLUDED.content, search_vector = EXCLUDED.search_vector,
                            updated_at = now()""",
                        doc_id, chunk_idx, content, seg,
                    )
                    total_chunks += 1
            else:
                for i in range(0, len(texts), EMBED_BATCH):
                    batch_texts = texts[i:i + EMBED_BATCH]
                    batch_parts = all_parts[i:i + EMBED_BATCH]
                    try:
                        embeddings = await embed(client, batch_texts)
                    except Exception as e:
                        logger.error(f"Embed failed: {e}, inserting without embedding")
                        embeddings = None

                    for j, (doc_id, chunk_idx, content) in enumerate(batch_parts):
                        seg = segment(content)
                        if embeddings:
                            emb_str = "[" + ",".join(map(str, embeddings[j])) + "]"
                            await conn.execute(
                                """INSERT INTO doc_chunks (doc_id, chunk_index, content, embedding, search_vector)
                                VALUES ($1, $2, $3, $4::vector, to_tsvector('simple', $5))
                                ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                                    content = EXCLUDED.content, embedding = EXCLUDED.embedding,
                                    search_vector = EXCLUDED.search_vector, updated_at = now()""",
                                doc_id, chunk_idx, content, emb_str, seg,
                            )
                        else:
                            await conn.execute(
                                """INSERT INTO doc_chunks (doc_id, chunk_index, content, search_vector)
                                VALUES ($1, $2, $3, to_tsvector('simple', $4))
                                ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                                    content = EXCLUDED.content, search_vector = EXCLUDED.search_vector,
                                    updated_at = now()""",
                                doc_id, chunk_idx, content, seg,
                            )
                        total_chunks += 1

            total_docs += len(docs)
            logger.info(f"Progress: {total_docs} docs, {total_chunks} chunks")

    await conn.close()
    logger.info(f"Done: {total_docs} docs, {total_chunks} chunks")


if __name__ == "__main__":
    asyncio.run(main())
