#!/usr/bin/env python3
"""用户价值分析系统数据库迁移脚本

运行方式: python scripts/migrate_user_analytics.py
"""
import asyncio
import sys
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from backend.core.database import init_db_pool


async def run_migration():
    """执行迁移"""

    # 读取迁移SQL
    migration_file = Path(__file__).parent / "migrations" / "add_user_analytics.sql"
    with open(migration_file, "r") as f:
        sql_content = f.read()

    print("🚀 Starting user analytics migration...")
    print(f"📄 Migration file: {migration_file}")

    try:
        # 初始化数据库连接
        pool = await init_db_pool()

        async with pool.acquire() as conn:
            # 分割SQL语句（简单实现，忽略注释和空行）
            statements = []
            current_statement = []

            for line in sql_content.split("\n"):
                # 跳过注释块
                if line.strip().startswith("--"):
                    continue

                # 累积语句
                if line.strip():
                    current_statement.append(line)
                elif current_statement:
                    # 空行，结束当前语句
                    stmt = "\n".join(current_statement).strip()
                    if stmt and not stmt.startswith("--"):
                        statements.append(stmt)
                    current_statement = []

            # 添加最后一个语句
            if current_statement:
                stmt = "\n".join(current_statement).strip()
                if stmt and not stmt.startswith("--"):
                    statements.append(stmt)

            # 执行语句
            executed = 0
            failed = 0

            for i, statement in enumerate(statements, 1):
                # 跳过纯注释和空语句
                if not statement or statement.startswith("--"):
                    continue

                try:
                    await conn.execute(text(statement))
                    executed += 1

                    if executed <= 10 or executed % 10 == 0:
                        print(f"✓ Executed {executed}/{len(statements)}")

                except Exception as e:
                    failed += 1
                    print(f"✗ Statement {i} failed: {str(e)[:100]}")
                    print(f"  Statement preview: {statement[:100]}...")

            # 提交事务
            await conn.execute(text("COMMIT"))

            print(f"\n{'='*60}")
            print("✅ Migration completed!")
            print(f"   Executed: {executed} statements")
            print(f"   Failed: {failed} statements")

            if failed > 0:
                print("\n⚠️  Some statements failed. Please check the errors above.")

            # 验证表是否创建成功
            print(f"\n{'='*60}")
            print("📊 Verifying tables...")

            tables_to_check = [
                "user_activity_log",
                "user_feedback",
                "user_profile",
                "data_deletion_requests",
            ]

            for table in tables_to_check:
                try:
                    result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"✓ Table '{table}' exists (count: {count})")
                except Exception as e:
                    print(f"✗ Table '{table}' not found: {e}")

            print(f"\n{'='*60}")
            print("🎉 Migration verification complete!")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_migration())
    sys.exit(exit_code)
