#!/usr/bin/env python3
"""Step 1: Export guoxue.db wx tables to a TSV file for PostgreSQL COPY import."""

import logging
import sqlite3
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "guji_export.tsv"
BATCH_SIZE = 10000


def esc(val) -> str:
    if val is None:
        return "\\N"
    s = str(val)
    s = s.replace("\\", "\\\\")
    s = s.replace("\t", "\\t")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return s


def main():
    if not SOURCE_DB.exists():
        logger.error(f"Source not found: {SOURCE_DB}")
        return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(SOURCE_DB))
    conn.execute("PRAGMA cache_size = -512000")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get tables
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%' ORDER BY name"
    )
    tables = []
    for (name,) in cur.fetchall():
        cur.execute(f"SELECT COUNT(*) FROM [{name}]")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            tables.append((name, cnt))
    total_source = sum(c for _, c in tables)
    logger.info(f"{len(tables)} tables, {total_source:,} rows total")

    total = 0
    t0 = time.time()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i, (table, expected) in enumerate(tables, 1):
            logger.info(f"[{i}/{len(tables)}] {table} (~{expected:,})")
            t_table = time.time()
            table_count = 0
            last_id = 0

            while True:
                cur.execute(
                    f"SELECT * FROM [{table}] WHERE rowid > ? ORDER BY rowid LIMIT {BATCH_SIZE}",
                    (last_id,),
                )
                rows = cur.fetchall()
                if not rows:
                    break

                for row in rows:
                    row_id = row["id"] if "id" in row.keys() else row[0]
                    content = None
                    if "body" in row.keys() and row["body"]:
                        content = row["body"]
                    elif "d" in row.keys() and row["d"]:
                        content = row["d"]

                    if not content or len(content) < 10:
                        continue

                    title = content[:50].split("\n")[0][:50]
                    f.write(
                        f"{esc(table)}\t{esc(row_id)}\t{esc(title)}\t{esc(content)}\t{esc(len(content))}\t\\N\t古籍\t{{}}\n"
                    )
                    table_count += 1

                last_id = rows[-1]["id"] if "id" in rows[-1].keys() else rows[-1][0]

            total += table_count
            elapsed = time.time() - t0
            rate = total / elapsed if elapsed > 0 else 0
            logger.info(
                f"  => {table}: {table_count:,} in {time.time()-t_table:.0f}s, total: {total:,} ({rate:.0f}/s)"
            )

    conn.close()
    elapsed = time.time() - t0
    logger.info(f"Export DONE in {elapsed:.0f}s, {total:,} rows to {OUTPUT_FILE}")
    logger.info(f"File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
