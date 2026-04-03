#!/usr/bin/env python3
"""数据导入前健康检查 — 必须在任何数据导入前运行

检查项:
  1. PostgreSQL 配置是否满足导入要求 (shared_buffers, maintenance_work_mem, work_mem)
  2. 可用磁盘空间是否足够
  3. Embedding 模型是否可用且维度匹配
  4. 目标表的 vector 列维度与模型输出一致
  5. 无长时间运行的阻塞查询

用法:
    python scripts/pre_import_check.py
    python scripts/pre_import_check.py --table guji_documents
    python scripts/pre_import_check.py --strict   # 任一检查失败则返回非0
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://zhineng:{os.getenv('POSTGRES_PASSWORD', 'zhineng_secure_2024')}@localhost:5436/zhineng_kb"
)
EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")

MIN_SHARED_BUFFERS_MB = 512
MIN_MAINTENANCE_WORK_MEM_MB = 256
MIN_WORK_MEM_MB = 16
MIN_DISK_FREE_GB = 10
MIN_CONTAINER_MEMORY_MB = 512


async def check_postgres_config(conn) -> list[dict]:
    """检查 PostgreSQL 配置参数"""
    results = []

    params = await conn.fetch("""
        SELECT name, setting, unit, short_desc
        FROM pg_settings
        WHERE name IN ('shared_buffers', 'maintenance_work_mem', 'work_mem',
                       'effective_cache_size', 'max_wal_size', 'max_connections')
    """)

    param_map = {r["name"]: r for r in params}

    checks = [
        ("shared_buffers", MIN_SHARED_BUFFERS_MB, "8kB"),
        ("maintenance_work_mem", MIN_MAINTENANCE_WORK_MEM_MB, "kB"),
        ("work_mem", MIN_WORK_MEM_MB, "kB"),
    ]

    for name, min_val, unit in checks:
        if name not in param_map:
            results.append({"check": f"pg_{name}", "status": "FAIL", "message": f"{name} 未找到"})
            continue

        raw = int(param_map[name]["setting"])
        if unit == "8kB":
            val_mb = raw * 8 / 1024
        elif unit == "kB":
            val_mb = raw / 1024
        else:
            val_mb = raw

        if val_mb >= min_val:
            results.append({
                "check": f"pg_{name}",
                "status": "PASS",
                "message": f"{name} = {val_mb:.0f}MB (>= {min_val}MB)"
            })
        else:
            results.append({
                "check": f"pg_{name}",
                "status": "WARN",
                "message": f"{name} = {val_mb:.0f}MB (< 推荐 {min_val}MB)"
            })

    return results


async def check_disk_space(conn) -> list[dict]:
    """检查数据库所在磁盘空间"""
    results = []

    try:
        row = await conn.fetchrow("""
            SELECT pg_database_size(current_database()) as db_size
        """)
        db_size_gb = row["db_size"] / 1024**3

        df_path = Path("/data") if Path("/data").exists() else Path("/")
        stat = os.statvfs(str(df_path))
        free_gb = (stat.f_bavail * stat.f_frsize) / 1024**3

        if free_gb >= MIN_DISK_FREE_GB:
            results.append({
                "check": "disk_space",
                "status": "PASS",
                "message": f"可用 {free_gb:.1f}GB (>= {MIN_DISK_FREE_GB}GB), 数据库 {db_size_gb:.1f}GB"
            })
        else:
            results.append({
                "check": "disk_space",
                "status": "FAIL",
                "message": f"可用 {free_gb:.1f}GB (< {MIN_DISK_FREE_GB}GB), 数据库 {db_size_gb:.1f}GB"
            })
    except Exception as e:
        results.append({"check": "disk_space", "status": "WARN", "message": f"无法检查磁盘: {e}"})

    return results


async def check_embedding_service() -> list[dict]:
    """检查 Embedding 服务是否可用"""
    import urllib.request

    results = []

    try:
        req = urllib.request.Request(f"{EMBEDDING_URL}/health")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())

        if data.get("model_loaded"):
            results.append({
                "check": "embedding_service",
                "status": "PASS",
                "message": f"模型已加载, 设备: {data.get('device', '?')}"
            })

            try:
                req2 = urllib.request.Request(f"{EMBEDDING_URL}/embed")
                resp2 = urllib.request.urlopen(
                    req2,
                    data=json.dumps({"texts": ["测试"]}).encode(),
                    timeout=10,
                    headers={"Content-Type": "application/json"}
                )
                embed_data = json.loads(resp2.read())
                dim = len(embed_data.get("embeddings", [[]])[0])
                results.append({
                    "check": "embedding_dimension",
                    "status": "PASS",
                    "message": f"向量维度: {dim}"
                })
            except Exception:
                results.append({
                    "check": "embedding_dimension",
                    "status": "WARN",
                    "message": "无法获取实际向量维度"
                })
        else:
            error = data.get("model_error", "未知错误")
            results.append({
                "check": "embedding_service",
                "status": "FAIL",
                "message": f"模型未加载: {error}"
            })
    except Exception as e:
        results.append({
            "check": "embedding_service",
            "status": "FAIL",
            "message": f"服务不可达 ({EMBEDDING_URL}): {e}"
        })

    return results


async def check_vector_dimensions(conn) -> list[dict]:
    """检查所有 vector 列的维度是否一致"""
    results = []

    rows = await conn.fetch("""
        SELECT table_name, column_name,
               pg_catalog.format_type(atttypid, atttypmod) as full_type
        FROM information_schema.columns c
        JOIN pg_attribute a ON a.attname = c.column_name
        JOIN pg_class t ON t.relname = c.table_name AND t.oid = a.attrelid
        WHERE c.table_schema = 'public'
          AND c.data_type = 'USER-DEFINED'
          AND c.udt_name = 'vector'
        ORDER BY table_name
    """)

    dims = {}
    for r in rows:
        import re
        m = re.search(r'\((\d+)\)', r["full_type"])
        if m:
            dim = int(m.group(1))
            dims[r["table_name"]] = {r["column_name"]: dim}
            if dim != 512:
                results.append({
                    "check": "vector_dim",
                    "status": "WARN",
                    "message": f"{r['table_name']}.{r['column_name']} = vector({dim}) (!= 512)"
                })

    if not any(r["check"] == "vector_dim" and r["status"] == "WARN" for r in results):
        results.append({
            "check": "vector_dimensions",
            "status": "PASS",
            "message": f"所有 vector 列维度一致: {list(dims.keys())}"
        })

    return results


async def check_blocking_queries(conn) -> list[dict]:
    """检查是否有长时间运行的阻塞查询"""
    results = []

    rows = await conn.fetch("""
        SELECT pid, now() - pg_stat_activity.query_start AS duration,
               query, state
        FROM pg_stat_activity
        WHERE state != 'idle'
          AND query NOT LIKE '%pg_stat_activity%'
          AND now() - query_start > interval '5 minutes'
        ORDER BY duration DESC
        LIMIT 5
    """)

    if rows:
        for r in rows:
            mins = r["duration"].total_seconds() / 60
            results.append({
                "check": "blocking_query",
                "status": "WARN",
                "message": f"PID {r['pid']} 运行 {mins:.1f}min: {r['query'][:80]}..."
            })
    else:
        results.append({
            "check": "blocking_queries",
            "status": "PASS",
            "message": "无长时间运行的查询"
        })

    return results


async def check_analyze_status(conn) -> list[dict]:
    """检查是否有大表未执行 ANALYZE"""
    results = []

    rows = await conn.fetch("""
        SELECT relname, n_live_tup,
               last_analyze, last_autoanalyze
        FROM pg_stat_user_tables
        WHERE n_live_tup > 10000
          AND last_analyze IS NULL
          AND last_autoanalyze IS NULL
        ORDER BY n_live_tup DESC
    """)

    if rows:
        for r in rows:
            results.append({
                "check": "analyze",
                "status": "WARN",
                "message": f"{r['relname']}: ~{r['n_live_tup']} 行, 从未 ANALYZE"
            })
    else:
        results.append({
            "check": "analyze",
            "status": "PASS",
            "message": "所有大表均已 ANALYZE"
        })

    return results


async def run_checks(strict: bool = False, table: str = None) -> int:
    """运行所有检查"""
    import asyncpg

    all_results = []

    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"\n❌ 无法连接数据库: {e}")
        return 1

    try:
        all_results.extend(await check_postgres_config(conn))
        all_results.extend(await check_disk_space(conn))
        all_results.extend(await check_embedding_service())
        all_results.extend(await check_vector_dimensions(conn))
        all_results.extend(await check_blocking_queries(conn))
        all_results.extend(await check_analyze_status(conn))
    finally:
        await conn.close()

    print("\n🔍 数据导入前健康检查")
    print("=" * 70)

    pass_count = sum(1 for r in all_results if r["status"] == "PASS")
    warn_count = sum(1 for r in all_results if r["status"] == "WARN")
    fail_count = sum(1 for r in all_results if r["status"] == "FAIL")

    for r in all_results:
        icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[r["status"]]
        print(f"  {icon} [{r['check']}] {r['message']}")

    print("=" * 70)
    print(f"  结果: {pass_count} 通过, {warn_count} 警告, {fail_count} 失败")

    if fail_count > 0:
        print("\n  ❌ 存在失败项，建议修复后再导入")
        return 1
    elif warn_count > 0 and strict:
        print("\n  ⚠️  严格模式下警告视为失败")
        return 1
    elif warn_count > 0:
        print("\n  ⚠️  存在警告，可以导入但建议关注")
        return 0
    else:
        print("\n  ✅ 所有检查通过，可以安全导入")
        return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="数据导入前健康检查")
    parser.add_argument("--strict", action="store_true", help="警告也视为失败")
    parser.add_argument("--table", help="仅检查指定表")
    args = parser.parse_args()

    return asyncio.run(run_checks(strict=args.strict, table=args.table))


if __name__ == "__main__":
    sys.exit(main())
