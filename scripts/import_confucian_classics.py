#!/usr/bin/env python3
"""批量导入儒家经典(Wikisource子页面模式) — 孟子14章+周易+尚書+春秋公羊傳
用法: ZHINENG_DB_PASS=xxx python3 scripts/import_confucian_classics.py
"""
import os
import re
import sys
import time
import asyncio
import requests
import asyncpg

EMBED_URL = os.environ.get("EMBED_URL", "http://localhost:8001/embed")
CHUNK_SIZE = 400

CONFUCIAN_PAGES = [
    ("孟子·梁惠王上", "孟子/梁惠王上"),
    ("孟子·梁惠王下", "孟子/梁惠王下"),
    ("孟子·公孫丑上", "孟子/公孫丑上"),
    ("孟子·公孫丑下", "孟子/公孫丑下"),
    ("孟子·滕文公上", "孟子/滕文公上"),
    ("孟子·離婁上", "孟子/離婁上"),
    ("孟子·離婁下", "孟子/離婁下"),
    ("孟子·告子上", "孟子/告子上"),
    ("孟子·告子下", "孟子/告子下"),
    ("孟子·盡心上", "孟子/盡心上"),
    ("孟子·盡心下", "孟子/盡心下"),
    ("周易", "周易"),
    ("尚書·堯典", "尚書/堯典"),
    ("春秋公羊傳", "春秋公羊傳"),
]


def fetch_wikisource(page_title):
    encoded = requests.utils.quote(page_title)
    api = f"https://zh.wikisource.org/w/api.php?action=parse&page={encoded}&prop=wikitext&format=json&utf8=1"
    time.sleep(2)
    r = requests.get(api, timeout=30, headers={"User-Agent": "LingZhiBot/1.0"})
    if r.status_code == 429:
        time.sleep(10)
        r = requests.get(api, timeout=30, headers={"User-Agent": "LingZhiBot/1.0"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"API error: {data['error'].get('info', '')[:80]}")
    return clean_wikitext(data["parse"]["wikitext"]["*"])


def clean_wikitext(text):
    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        if not line or line.startswith(("{{", "}}", "__", "<", "|", "{|", "|}")):
            lines.append("")
            continue
        line = re.sub(r"\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", line)
        line = re.sub(r"\[\[([^\]]*)\]\]", r"\1", line)
        line = line.replace("'''", "").replace("''", "")
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def chunk_text(text, size=CHUNK_SIZE):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for para in paragraphs:
        while len(para) > size:
            if cur:
                chunks.append(cur)
            chunks.append(para[:size])
            para = para[size:]
        if len(cur) + len(para) + 2 > size and cur:
            chunks.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c.strip()) > 10]


async def main():
    if not os.environ.get("ZHINENG_DB_PASS"):
        print("ERROR: ZHINENG_DB_PASS required")
        sys.exit(1)

    conn = await asyncpg.connect(
        host=os.environ.get("ZHINENG_DB_HOST", "localhost"),
        port=int(os.environ.get("ZHINENG_DB_PORT", "5436")),
        user=os.environ.get("ZHINENG_DB_USER", "zhineng"),
        password=os.environ.get("ZHINENG_DB_PASS", ""),
        database=os.environ.get("ZHINENG_DB_NAME", "zhineng_kb"),
    )

    total_chunks = 0
    success = 0
    for title, page in CONFUCIAN_PAGES:
        print(f"\n{'='*50}\n{title}")
        existing = await conn.fetchval(
            "SELECT id FROM documents WHERE title=$1 AND category='儒家'", title
        )
        if existing:
            print(f"  SKIP (exists id={existing})")
            continue
        try:
            text = fetch_wikisource(page)
        except Exception as e:
            print(f"  FAIL: {e}")
            continue
        if len(text) < 200:
            print(f"  SKIP (too short {len(text)})")
            continue
        chunks = chunk_text(text)
        print(f"  {len(text)} chars, {len(chunks)} chunks")
        print(f"  embedding...")
        embeddings = []
        for i, c in enumerate(chunks):
            r = requests.post(EMBED_URL, json={"text": c}, timeout=30)
            if r.status_code != 200:
                print(f"  embed fail at {i}")
                break
            embeddings.append(r.json()["embedding"])
            if (i + 1) % 20 == 0:
                print(f"    {i+1}/{len(chunks)}")
            time.sleep(0.05)
        if len(embeddings) != len(chunks):
            print(f"  partial embed, skipping")
            continue
        async with conn.transaction():
            doc_id = await conn.fetchval(
                "INSERT INTO documents(title,category,content) VALUES($1,$2,$3) RETURNING id",
                title, "儒家", text,
            )
            off = 0
            for i, (c, emb) in enumerate(zip(chunks, embeddings)):
                es = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
                await conn.execute(
                    "INSERT INTO doc_chunks(doc_id,chunk_index,content,start_offset,end_offset,embedding) VALUES($1,$2,$3,$4,$5,$6::vector)",
                    doc_id, i, c, off, off + len(c), es,
                )
                await conn.execute(
                    "UPDATE doc_chunks SET search_vector=to_tsvector('simple',content) WHERE doc_id=$1 AND chunk_index=$2",
                    doc_id, i,
                )
                off += len(c)
        print(f"  DONE doc_id={doc_id}")
        total_chunks += len(chunks)
        success += 1

    await conn.close()
    print(f"\n{'='*50}\nSummary: {success}/{len(CONFUCIAN_PAGES)} imported, {total_chunks} chunks")


if __name__ == "__main__":
    asyncio.run(main())
