#!/usr/bin/env python3
"""快速诊断数据库锁死问题

用法:
    python scripts/diagnose_locks.py          # 快速诊断
    python scripts/diagnose_locks.py --fix    # 尝试自动修复
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).parent.parent))

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


async def check_file_locks() -> list:
    print_header("📁 文件锁检查")

    lock_dir = Path("/tmp/zhineng_imports")
    issues = []

    if not lock_dir.exists():
        print("  ✅ 锁目录不存在")
        return issues

    for lock_file in lock_dir.glob("*.lock"):
        try:
            content = lock_file.read_text().strip()
            lines = content.split("\n")
            pid = int(lines[0]) if lines else None

            if pid and is_process_running(pid):
                print(f"  🟢 {lock_file.stem}: PID {pid} 运行中")
            else:
                print(f"  🔴 {lock_file.stem}: PID {pid} 已死 (需要清理)")
                issues.append(("file_lock", lock_file, pid))
        except Exception as e:
            print(f"  ⚠️  {lock_file}: 读取失败 - {e}")

    return issues


async def check_database_locks(conn: asyncpg.Connection) -> list:
    print_header("🗄️  数据库锁检查")

    issues = []

    # 确保表存在
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS import_locks (
            id SERIAL PRIMARY KEY,
            task_name VARCHAR(100) UNIQUE NOT NULL,
            status VARCHAR(20) NOT NULL,
            pid INTEGER,
            started_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            error_message TEXT
        );
    """
    )

    # 查询运行中的锁
    rows = await conn.fetch(
        """
        SELECT task_name, status, pid, started_at,
               EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_ago
        FROM import_locks
        WHERE status = 'running'
        ORDER BY started_at DESC
    """
    )

    if not rows:
        print("  ✅ 无运行中的导入任务")
        return issues

    for row in rows:
        pid = row["pid"]
        is_running = pid is not None and is_process_running(pid)
        is_expired = row["minutes_ago"] > 60

        if is_expired:
            print(f"  ⏰ {row['task_name']}: 运行 {row['minutes_ago']:.1f} 分钟 (已过期)")
            issues.append(("db_lock_expired", row["task_name"], pid))
        elif not is_running:
            print(f"  🔴 {row['task_name']}: PID {pid} 已死 (需要清理)")
            issues.append(("db_lock_dead", row["task_name"], pid))
        else:
            print(f"  🟢 {row['task_name']}: PID {pid} 运行中 ({row['minutes_ago']:.1f} 分钟)")

    return issues


async def check_blocked_queries(conn: asyncpg.Connection) -> list:
    print_header("⚠️  阻塞查询检查")

    issues = []

    rows = await conn.fetch(
        """
        SELECT
            blocked.pid as blocked_pid,
            blocked.usename as blocked_user,
            blocked.query as blocked_query,
            blocking.pid as blocking_pid,
            blocking.usename as blocking_user,
            blocking.query as blocking_query,
            EXTRACT(EPOCH FROM (NOW() - blocked.query_start))/60 as blocked_minutes
        FROM pg_stat_activity AS blocked
        JOIN pg_stat_activity AS blocking
            ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
        WHERE blocked.datname = current_database()
        ORDER BY blocked.query_start
    """
    )

    if not rows:
        print("  ✅ 无阻塞查询")
        return issues

    for row in rows:
        blocked_query = (
            (row["blocked_query"][:50] + "...")
            if row["blocked_query"] and len(row["blocked_query"]) > 50
            else row["blocked_query"]
        )
        blocking_query = (
            (row["blocking_query"][:50] + "...")
            if row["blocking_query"] and len(row["blocking_query"]) > 50
            else row["blocking_query"]
        )

        print(f"  🔒 PID {row['blocked_pid']} 被 PID {row['blocking_pid']} 阻塞")
        print(f"     等待: {row['blocked_minutes']:.1f} 分钟")
        print(f"     被阻塞: {blocked_query}")
        print(f"     阻塞者: {blocking_query}")
        issues.append(("blocked_query", row["blocked_pid"], row["blocking_pid"]))

    return issues


async def check_long_transactions(conn: asyncpg.Connection) -> list:
    print_header("⏱️  长事务检查")

    issues = []

    rows = await conn.fetch(
        """
        SELECT
            pid,
            usename,
            application_name,
            state,
            query,
            EXTRACT(EPOCH FROM (NOW() - query_start))/60 as minutes_running
        FROM pg_stat_activity
        WHERE state IN ('active', 'idle in transaction')
          AND datname = current_database()
          AND pid != pg_backend_pid()
          AND EXTRACT(EPOCH FROM (NOW() - query_start)) > 300  -- 5分钟
        ORDER BY query_start DESC
    """
    )

    if not rows:
        print("  ✅ 无长事务")
        return issues

    for row in rows:
        query_preview = (
            (row["query"][:50] + "...") if row["query"] and len(row["query"]) > 50 else row["query"]
        )
        print(f"  ⏱️  PID {row['pid']}: 运行 {row['minutes_running']:.1f} 分钟")
        print(f"     应用: {row['application_name'] or 'unknown'}")
        print(f"     查询: {query_preview}")
        issues.append(("long_transaction", row["pid"], row["minutes_running"]))

    return issues


async def fix_issues(issues: list, conn: asyncpg.Connection):
    print_header("🔧 自动修复")

    fixed = 0

    for issue_type, *args in issues:
        if issue_type == "file_lock":
            lock_file = args[0]
            try:
                lock_file.unlink()
                print(f"  ✅ 删除文件锁: {lock_file.name}")
                fixed += 1
            except Exception as e:
                print(f"  ❌ 删除失败: {e}")

        elif issue_type in ("db_lock_dead", "db_lock_expired"):
            task_name = args[0]
            try:
                await conn.execute(
                    """
                    UPDATE import_locks
                    SET status = 'cleaned',
                        completed_at = NOW(),
                        error_message = '自动诊断清理'
                    WHERE task_name = $1
                """,
                    task_name,
                )
                print(f"  ✅ 清理数据库锁: {task_name}")
                fixed += 1
            except Exception as e:
                print(f"  ❌ 清理失败: {e}")

    print(f"\n  总计修复: {fixed} 项")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="快速诊断数据库锁死")
    parser.add_argument("--fix", action="store_true", help="自动修复发现的问题")

    args = parser.parse_args()

    print("\n🔍 灵知系统 - 数据库锁死诊断")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_issues = []

    # 检查文件锁
    file_issues = await check_file_locks()
    all_issues.extend(file_issues)

    # 检查数据库锁
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        db_issues = await check_database_locks(conn)
        all_issues.extend(db_issues)

        blocked_issues = await check_blocked_queries(conn)
        all_issues.extend(blocked_issues)

        long_tx_issues = await check_long_transactions(conn)
        all_issues.extend(long_tx_issues)
    finally:
        await conn.close()

    # 汇总
    print_header("📊 诊断汇总")

    if not all_issues:
        print("  ✅ 未发现问题")
        return 0

    print(f"  发现 {len(all_issues)} 个问题:")

    issue_types = {}
    for issue_type, *args in all_issues:
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

    for issue_type, count in issue_types.items():
        icon = "🔴" if "dead" in issue_type or "expired" in issue_type else "⚠️"
        print(f"    {icon} {issue_type}: {count}")

    # 修复建议
    print_header("💡 建议")

    if args.fix:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            await fix_issues(all_issues, conn)
        finally:
            await conn.close()
    else:
        print("  运行以下命令修复:")
        print("    python scripts/diagnose_locks.py --fix")
        print()
        print("  或使用:")
        print("    python scripts/db_lock_monitor.py --clean  # 清理过期锁")
        print("    python scripts/db_lock_monitor.py --kill   # 终止所有导入进程")

    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
