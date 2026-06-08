#!/usr/bin/env python3
"""从Wikisource批量导入中医古籍全文到知识库

用法: python3 scripts/import_wikisource_tcm.py [--dry-run] [--limit N]
环境变量:
  ZHINENG_DB_PASS - 数据库密码 (必需)
  EMBED_URL - embedding服务URL (默认 http://localhost:8001/embed)
"""
import os
import re
import sys
import time
import asyncio
import argparse

import requests
import asyncpg

EMBED_URL = os.environ.get("EMBED_URL", "http://localhost:8001/embed")
CHUNK_SIZE = 400

# Wikisource 中医核心经典 (按优先级, 已验证页面有效)
TCM_CLASSICS = [
    # 第一批: 已导入的经典(去重跳过)
    ("傷寒論", "傷寒論"),
    ("金匱要略", "金匱要略"),
    ("神農本草經", "神農本草經"),
    ("本草綱目", "本草綱目"),
    ("難經", "難經"),
    ("溫熱論", "溫熱論"),
    ("古今醫案按", "古今醫案按"),
    ("冷廬醫話", "冷廬醫話"),
    # 第二批: 新增经典
    ("脾胃論", "脾胃論"),
    ("血證論", "血證論"),
    ("醫學心悟", "醫學心悟"),
    ("醫方集解", "醫方集解"),
    ("中藏經", "中藏經"),
    ("丹溪心法", "丹溪心法"),
    ("內外傷辨惑論", "內外傷辨惑論"),
    ("溫疫論", "溫疫論"),
    ("針灸甲乙經", "針灸甲乙經"),
    ("濕熱條辨", "濕熱條辨"),
    ("千金寶要", "千金寶要"),
    ("醫學三字經", "醫學三字經"),
    ("脈症治方", "脈症治方"),
    ("名醫別錄", "名醫別錄"),
]


def fetch_wikisource(page_title):
    """从Wikisource获取全文，使用API避免HTML解析"""
    encoded_title = requests.utils.quote(page_title)
    api_url = (
        f"https://zh.wikisource.org/w/api.php?"
        f"action=parse&page={encoded_title}&prop=wikitext&format=json&utf8=1"
    )
    time.sleep(1.5)
    r = requests.get(api_url, timeout=30, headers={"User-Agent": "LingZhiBot/1.0"})
    if r.status_code == 429:
        time.sleep(8)
        r = requests.get(api_url, timeout=30, headers={"User-Agent": "LingZhiBot/1.0"})
    if r.status_code != 200:
        raise RuntimeError(f"API {r.status_code}: {r.text[:100]}")
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"API error: {data['error'].get('info', '')[:100]}")
    wikitext = data["parse"]["wikitext"]["*"]
    return clean_wikitext(wikitext)


def clean_wikitext(text):
    """清理wikitext标记，提取纯文本"""
    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        if not line:
            lines.append("")
            continue
        if line.startswith(("{{", "}}", "__", "<", "|", "{|", "|}")):
            continue
        if "[[" in line and "]]" in line:
            line = re.sub(r"\[\[[^|\]]*\|([^\]]*)\]\]", r"\1", line)
            line = re.sub(r"\[\[([^\]]*)\]\]", r"\1", line)
        if "'''" in line:
            line = line.replace("'''", "").replace("''", "")
        lines.append(line)
    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


def chunk_text(text, size=CHUNK_SIZE):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
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
    return [c for c in chunks if len(c.strip()) > 10]


def embed_single(text):
    r = requests.post(EMBED_URL, json={"text": text}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Embed failed: {r.status_code}")
    return r.json()["embedding"]


async def import_one(conn, title, page_title, dry_run=False):
    print(f"\n{'='*60}")
    print(f"Fetching: {title}")
    try:
        text = fetch_wikisource(page_title)
    except Exception as e:
        print(f"  FAIL fetch: {e}")
        return None

    if len(text) < 100:
        print(f"  SKIP: too short ({len(text)} chars)")
        return None

    chunks = chunk_text(text)
    print(f"  Text: {len(text)} chars, {len(chunks)} chunks")

    if dry_run:
        print(f"  [DRY-RUN] would insert doc + {len(chunks)} chunks")
        return len(chunks)

    existing = await conn.fetchval(
        "SELECT id FROM documents WHERE title = $1 AND category = '中医'", title
    )
    if existing:
        print(f"  SKIP: already exists (id={existing})")
        return 0

    print(f"  Embedding {len(chunks)} chunks...")
    embeddings = []
    for i, chunk in enumerate(chunks):
        emb = embed_single(chunk)
        embeddings.append(emb)
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(chunks)}")
        time.sleep(0.05)

    async with conn.transaction():
        doc_id = await conn.fetchval(
            "INSERT INTO documents (title, category, content) VALUES ($1, $2, $3) RETURNING id",
            title, "中医", text,
        )
        offset = 0
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            emb_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
            await conn.execute(
                """INSERT INTO doc_chunks (doc_id, chunk_index, content, start_offset, end_offset, embedding)
                   VALUES ($1, $2, $3, $4, $5, $6::vector)""",
                doc_id, i, chunk, offset, offset + len(chunk), emb_str,
            )
            await conn.execute(
                "UPDATE doc_chunks SET search_vector = to_tsvector('simple', content) WHERE doc_id = $1 AND chunk_index = $2",
                doc_id, i,
            )
            offset += len(chunk)

    print(f"  DONE: doc_id={doc_id}, {len(chunks)} chunks")
    return len(chunks)


async def main():
    parser = argparse.ArgumentParser(description="Import TCM classics from Wikisource")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="limit number of classics")
    args = parser.parse_args()

    if not os.environ.get("ZHINENG_DB_PASS"):
        print("ERROR: ZHINENG_DB_PASS env var required")
        sys.exit(1)

    classics = TCM_CLASSICS[: args.limit] if args.limit else TCM_CLASSICS

    conn = await asyncpg.connect(
        host=os.environ.get("ZHINENG_DB_HOST", "localhost"),
        port=int(os.environ.get("ZHINENG_DB_PORT", "5436")),
        user=os.environ.get("ZHINENG_DB_USER", "zhineng"),
        password=os.environ.get("ZHINENG_DB_PASS", ""),
        database=os.environ.get("ZHINENG_DB_NAME", "zhineng_kb"),
    )

    total_chunks = 0
    success = 0
    for title, page in classics:
        result = await import_one(conn, title, page, args.dry_run)
        if result is not None and result > 0:
            total_chunks += result
            success += 1

    await conn.close()
    print(f"\n{'='*60}")
    print(f"Summary: {success}/{len(classics)} imported, {total_chunks} chunks total")


if __name__ == "__main__":
    asyncio.run(main())
