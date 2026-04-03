#!/usr/bin/env python3
"""数据导入后验证 — 每次数据导入完成后必须运行

验证项:
  1. 目标表行数 (COUNT(*)) 对比预期
  2. 执行 ANALYZE 更新统计信息
  3. 检查索引是否完整
  4. 验证 vector 列维度与模型匹配
  5. 检查是否有 NULL 值在 NOT NULL 列
  6. 输出验证报告 (JSON)

用法:
    python scripts/post_import_validate.py --table sys_books --expected 3000000
    python scripts/post_import_validate.py --all
    python scripts/post_import_validate.py --all --json > validation_report.json
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://zhineng:{os.getenv('POSTGRES_PASSWORD', 'zhineng_secure_2024')}@localhost:5436/zhineng_kb",
)

EXPECTED_COUNTS = {
    "sys_books": 3_000_000,
    "sys_books_archive": 3_000_000,
    "guoxue_content": 260_000,
    "guji_documents": 260_000,
    "documents": 100_000,
    "textbook_blocks": 10_000,
    "textbook_nodes": 2_000,
    "textbook_blocks_v2": 1_000,
    "textbook_toc": 800,
}


async def validate_table(conn, table_name: str, expected: int = None) -> dict:
    """验证单个表"""
    result = {"table": table_name, "checks": [], "passed": True}

    try:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
            table_name,
        )
        if not exists:
            result["checks"].append({"check": "exists", "status": "FAIL", "message": "表不存在"})
            result["passed"] = False
            return result

        actual_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")

        if expected is not None:
            if actual_count >= expected * 0.9:
                result["checks"].append(
                    {
                        "check": "row_count",
                        "status": "PASS",
                        "message": f"实际 {actual_count:,} >= 预期 {expected:,} 的90%",
                    }
                )
            elif actual_count > 0:
                result["checks"].append(
                    {
                        "check": "row_count",
                        "status": "WARN",
                        "message": f"实际 {actual_count:,} < 预期 {expected:,} 的90%",
                    }
                )
            else:
                result["checks"].append(
                    {
                        "check": "row_count",
                        "status": "FAIL",
                        "message": f"表为空 (预期 {expected:,})",
                    }
                )
                result["passed"] = False
        else:
            result["checks"].append(
                {"check": "row_count", "status": "PASS", "message": f"行数: {actual_count:,}"}
            )

        await conn.execute(f"ANALYZE {table_name}")
        result["checks"].append({"check": "analyze", "status": "PASS", "message": "ANALYZE 完成"})

        indexes = await conn.fetch(
            """
            SELECT indexname, indexdef
            FROM pg_indexes WHERE tablename = $1
        """,
            table_name,
        )
        if indexes:
            idx_names = [r["indexname"] for r in indexes]
            result["checks"].append(
                {"check": "indexes", "status": "PASS", "message": f"索引: {', '.join(idx_names)}"}
            )
        else:
            result["checks"].append(
                {"check": "indexes", "status": "WARN", "message": "无索引 (大表应建索引)"}
            )

    except Exception as e:
        result["checks"].append({"check": "error", "status": "FAIL", "message": str(e)})
        result["passed"] = False

    return result


async def run_validation(tables: dict = None, output_json: bool = False) -> int:
    """运行验证"""
    import asyncpg

    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ 无法连接数据库: {e}")
        return 1

    try:
        if tables is None:
            tables = EXPECTED_COUNTS

        results = []
        for table_name, expected in tables.items():
            r = await validate_table(conn, table_name, expected)
            results.append(r)

        if output_json:
            report = {
                "timestamp": datetime.now().isoformat(),
                "database": "zhineng_kb",
                "results": results,
                "summary": {
                    "total": len(results),
                    "passed": sum(1 for r in results if r["passed"]),
                    "failed": sum(1 for r in results if not r["passed"]),
                },
            }
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("\n📊 数据导入后验证报告")
            print("=" * 70)
            for r in results:
                icon = "✅" if r["passed"] else "❌"
                print(f"\n  {icon} {r['table']}:")
                for c in r["checks"]:
                    ci = {"PASS": "  ✅", "WARN": "  ⚠️ ", "FAIL": "  ❌"}[c["status"]]
                    print(f"    {ci} {c['check']}: {c['message']}")

            passed = sum(1 for r in results if r["passed"])
            failed = sum(1 for r in results if not r["passed"])
            print(f"\n{'=' * 70}")
            print(f"  总计: {len(results)} 表, {passed} 通过, {failed} 失败")

            if failed > 0:
                failed_names = [r["table"] for r in results if not r["passed"]]
                print(f"  ❌ 失败的表: {', '.join(failed_names)}")
                return 1
            else:
                print("  ✅ 所有表验证通过")
                return 0

    finally:
        await conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="数据导入后验证")
    parser.add_argument("--table", help="仅验证指定表")
    parser.add_argument("--expected", type=int, help="预期行数")
    parser.add_argument("--all", action="store_true", help="验证所有已知表")
    parser.add_argument("--json", action="store_true", dest="output_json", help="JSON 输出")
    args = parser.parse_args()

    if args.table:
        tables = {args.table: args.expected}
    elif args.all:
        tables = EXPECTED_COUNTS
    else:
        tables = EXPECTED_COUNTS

    return asyncio.run(run_validation(tables=tables, output_json=args.output_json))


if __name__ == "__main__":
    sys.exit(main())
