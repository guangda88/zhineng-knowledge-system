#!/usr/bin/env python3
"""导入何氏虛勞心傳(Wikisource全文)到知识库 — 文档+分块+embedding (asyncpg版)"""
import os
import re
import time
import asyncio
import requests
import asyncpg

EMBED_URL = os.environ.get("EMBED_URL", "http://localhost:8001/embed")
if not os.environ.get("ZHINENG_DB_PASS"):
    raise RuntimeError("ZHINENG_DB_PASS env var required")
TXT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "books", "何氏医著", "何氏虛勞心傳_wikisource全文.txt")
CHUNK_SIZE = 300


def load_text():
    with open(TXT_PATH, encoding="utf-8") as f:
        raw = f.read()
    m = re.search(r"字数：(\d+)", raw)
    declared = int(m.group(1)) if m else 0
    lines = raw.strip().split("\n")
    body_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(("何氏虛勞心傳", "作者：", "来源：", "字数：")):
            continue
        body_lines.append(line)
    return "\n\n".join(body_lines), declared


def chunk_text(text, size=CHUNK_SIZE):
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        while len(para) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:size])
            para = para[size:]
        if len(current) + len(para) + 2 > size and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def embed_single(text):
    r = requests.post(EMBED_URL, json={"text": text}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Embed failed: {r.status_code} {r.text[:100]}")
    return r.json()["embedding"]


async def main():
    body, declared = load_text()
    print(f"Loaded text: {len(body)} chars (declared {declared})")

    chunks = chunk_text(body)
    print(f"Chunked into {len(chunks)} pieces (avg {len(body) // len(chunks)} chars)")

    print(f"Embedding {len(chunks)} chunks via {EMBED_URL}...")
    embeddings = []
    for i, chunk in enumerate(chunks):
        emb = embed_single(chunk)
        embeddings.append(emb)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(chunks)} embedded")
        time.sleep(0.05)
    print(f"Got {len(embeddings)} embeddings (dim {len(embeddings[0])})")

    conn = await asyncpg.connect(
        host=os.environ.get("ZHINENG_DB_HOST", "localhost"),
        port=int(os.environ.get("ZHINENG_DB_PORT", "5436")),
        user=os.environ.get("ZHINENG_DB_USER", "zhineng"),
        password=os.environ.get("ZHINENG_DB_PASS", ""),
        database=os.environ.get("ZHINENG_DB_NAME", "zhineng_kb"),
    )
    try:
        await conn.execute("BEGIN")
        doc_id = await conn.fetchval(
            "INSERT INTO documents (title, category, content) VALUES ($1, $2, $3) RETURNING id",
            "何氏虛勞心傳", "中医", body,
        )
        print(f"Inserted document id={doc_id}")

        offset = 0
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            emb_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
            await conn.execute(
                """INSERT INTO doc_chunks (doc_id, chunk_index, content, start_offset, end_offset, embedding)
                   VALUES ($1, $2, $3, $4, $5, $6::vector)""",
                doc_id, i, chunk, offset, offset + len(chunk), emb_str,
            )
            offset += len(chunk)

        await conn.execute("COMMIT")
        actual = await conn.fetchval("SELECT count(*) FROM doc_chunks WHERE doc_id = $1", doc_id)
        print(f"Done: doc_id={doc_id}, {actual} chunks in DB, {len(body)} chars")
    except Exception:
        await conn.execute("ROLLBACK")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
