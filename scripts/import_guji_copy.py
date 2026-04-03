#!/usr/bin/env python3
"""Guji import via psql COPY protocol - fastest method.

Reads SQLite rows, streams them to psql COPY stdin.
"""

import logging
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DB = Path(__file__).parent.parent / "lingzhi_ubuntu" / "database" / "guoxue.db"
PSQL_CMD = ["docker", "exec", "-i", "dfdd3b278296_zhineng-postgres", "psql", "-U", "zhineng", "-d", "zhineng_kb"]
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

    # Truncate
    logger.info("Truncating...")
    subprocess.run(PSQL_CMD + ["-c", "TRUNCATE guji_documents;"], check=True, capture_output=True)
    logger.info("Truncated.")

    # Get tables
    conn = sqlite3.connect(str(SOURCE_DB))
    conn.execute("PRAGMA cache_size = -512000")
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wx%' ORDER BY name")
    tables = []
    for (name,) in cur.fetchall():
        cur.execute(f"SELECT COUNT(*) FROM [{name}]")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            tables.append((name, cnt))
    conn.close()
    total_source = sum(c for _, c in tables)
    logger.info(f"{len(tables)} tables, {total_source:,} rows total")

    # Start COPY
    copy_sql = "COPY guji_documents (source_table, source_id, title, content, content_length, dynasty, category, tags) FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N');"
    proc = subprocess.Popen(
        PSQL_CMD + ["-c", copy_sql],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    conn = sqlite3.connect(str(SOURCE_DB))
    conn.execute("PRAGMA cache_size = -512000")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total = 0
    t0 = time.time()

    for i, (table, expected) in enumerate(tables, 1):
        logger.info(f"[{i}/{len(tables)}] {table} (~{expected:,})")
        t_table = time.time()
        table_count = 0
        last_id = 0
        buf = []

        while True:
            cur.execute(f"SELECT * FROM [{table}] WHERE rowid > ? ORDER BY rowid LIMIT {BATCH_SIZE}", (last_id,))
            rows = cur.fetchall()
            if not rows:
                break

            for row in rows:
                row_id = row['id'] if 'id' in row.keys() else row[0]
                content = None
                if 'body' in row.keys() and row['body']:
                    content = row['body']
                elif 'd' in row.keys() and row['d']:
                    content = row['d']

                if not content or len(content) < 10:
                    continue

                title = content[:50].split('\n')[0][:50]
                buf.append(f"{esc(table)}\t{esc(row_id)}\t{esc(title)}\t{esc(content)}\t{esc(len(content))}\t\\N\t古籍\t{{}}")
                table_count += 1

            last_id = rows[-1]['id'] if 'id' in rows[-1].keys() else rows[-1][0]

            if len(buf) >= BATCH_SIZE:
                proc.stdin.write(("\n".join(buf) + "\n").encode("utf-8"))
                total += len(buf)
                buf = []
                elapsed = time.time() - t0
                rate = total / elapsed if elapsed > 0 else 0
                logger.info(f"  total: {total:,} ({rate:.0f}/s)")

        if buf:
            proc.stdin.write(("\n".join(buf) + "\n").encode("utf-8"))
            total += len(buf)

        logger.info(f"  => {table}: {table_count:,} in {time.time()-t_table:.0f}s")

    conn.close()
    proc.stdin.close()
    stdout, stderr = proc.communicate(timeout=600)
    elapsed = time.time() - t0

    if proc.returncode != 0:
        logger.error(f"COPY error: {stderr.decode()[:500]}")
    logger.info(f"DONE in {elapsed:.0f}s, {total:,} rows")

    # Verify
    r = subprocess.run(PSQL_CMD + ["-c", "SELECT COUNT(*), COUNT(DISTINCT source_table) FROM guji_documents;"], capture_output=True, text=True)
    logger.info(f"Verify: {r.stdout.strip()}")


if __name__ == "__main__":
    main()
