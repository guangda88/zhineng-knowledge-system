#!/usr/bin/env python3
"""数据库锁监控工具 - 检测和报告锁冲突

用法:
    python scripts/db_lock_monitor.py          # 检查锁状态
    python scripts/db_lock_monitor.py --kill   # 终止所有导入进程
    python scripts/db_lock_monitor.py --clean  # 清理过期锁
"""

import asyncio
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)
LOCK_DIR = Path("/tmp/zhineng_imports")
LOCK_TIMEOUT_MINUTES = 60  # 1小时后认为锁过期


async def check_file_locks():
    """检查文件锁状态"""
    print("\n📁 文件锁状态:")
    print("=" * 60)

    if not LOCK_DIR.exists():
        print("  锁目录不存在")
        return []

    locks = []
    for lock_file in LOCK_DIR.glob("*.lock"):
        try:
            content = lock_file.read_text().strip()
            lines = content.split("\n")
            pid = int(lines[0]) if lines else None
            started = lines[1] if len(lines) > 1 else "未知"

            # 检查进程是否还在运行
            is_running = pid is not None and _is_process_running(pid)

            locks.append(
                {
                    "name": lock_file.stem,
                    "file": lock_file,
                    "pid": pid,
                    "started": started,
                    "is_running": is_running,
                }
            )

            status = "🟢 运行中" if is_running else "🔴 进程已死"
            print(f"  {lock_file.stem}:")
            print(f"    文件: {lock_file}")
            print(f"    PID: {pid}")
            print(f"    启动: {started}")
            print(f"    状态: {status}")

        except Exception as e:
            print(f"  {lock_file}: 读取失败 - {e}")

    return locks


async def check_database_locks(conn):
    """检查数据库锁状态"""
    print("\n🗄️  数据库锁状态:")
    print("=" * 60)

    # 创建表（如果不存在）
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

    # 查询运行中的任务
    rows = await conn.fetch(
        """
        SELECT task_name, status, pid, started_at,
               EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_ago
        FROM import_locks
        WHERE status = 'running'
        ORDER BY started_at DESC
    """
    )

    locks = []
    for row in rows:
        pid = row["pid"]
        is_running = pid is not None and _is_process_running(pid)
        is_expired = row["minutes_ago"] > LOCK_TIMEOUT_MINUTES

        locks.append(
            {
                "name": row["task_name"],
                "pid": pid,
                "started": row["started_at"],
                "minutes_ago": row["minutes_ago"],
                "is_running": is_running,
                "is_expired": is_expired,
            }
        )

        status = "🟢 运行中" if is_running else "🔴 进程已死"
        if is_expired:
            status = "⏰ 已过期"

        print(f"  {row['task_name']}:")
        print(f"    PID: {pid}")
        print(f"    启动: {row['started_at']}")
        print(f"    运行: {row['minutes_ago']:.1f} 分钟")
        print(f"    状态: {status}")

    return locks


async def check_active_database_locks(conn):
    """检查 PostgreSQL 中活跃的锁等待"""
    print("\n🔒 数据库活跃锁:")
    print("=" * 60)

    # 查询锁等待情况
    rows = await conn.fetch(
        """
        SELECT
            pid,
            usename,
            application_name,
            state,
            query,
            wait_event_type,
            wait_event,
            EXTRACT(EPOCH FROM (NOW() - query_start))/60 as minutes_running
        FROM pg_stat_activity
        WHERE state IN ('active', 'idle in transaction')
          AND datname = current_database()
          AND pid != pg_backend_pid()
        ORDER BY query_start DESC
        LIMIT 20
    """
    )

    if not rows:
        print("  无活跃事务")
        return []

    for row in rows:
        wait_info = ""
        if row["wait_event_type"]:
            wait_info = f" 等待: {row['wait_event_type']}/{row['wait_event']}"

        query_preview = (
            (row["query"][:80] + "...") if row["query"] and len(row["query"]) > 80 else row["query"]
        )

        print(f"  PID {row['pid']} ({row['usename']}):")
        print(f"    应用: {row['application_name'] or 'unknown'}")
        print(f"    状态: {row['state']}{wait_info}")
        print(f"    运行: {row['minutes_running']:.1f} 分钟")
        print(f"    查询: {query_preview}")
        print()

    return rows


async def check_blocked_queries(conn):
    """检查被阻塞的查询"""
    print("\n⚠️  被阻塞的查询:")
    print("=" * 60)

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
        LIMIT 10
    """
    )

    if not rows:
        print("  无阻塞查询")
        return []

    for row in rows:
        blocked_query = (
            (row["blocked_query"][:60] + "...")
            if row["blocked_query"] and len(row["blocked_query"]) > 60
            else row["blocked_query"]
        )
        blocking_query = (
            (row["blocking_query"][:60] + "...")
            if row["blocking_query"] and len(row["blocking_query"]) > 60
            else row["blocking_query"]
        )

        print(f"  🔒 被阻塞 PID {row['blocked_pid']}:")
        print(f"     查询: {blocked_query}")
        print(f"     等待: {row['blocked_minutes']:.1f} 分钟")
        print(f"     阻塞者 PID {row['blocking_pid']}:")
        print(f"     查询: {blocking_query}")
        print()

    return rows


def _is_process_running(pid):
    """检查进程是否在运行"""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)  # 发送空信号，不杀死进程
        return True
    except OSError:
        return False


async def kill_import_processes():
    """终止所有导入相关进程"""
    print("\n🔪 终止导入进程:")
    print("=" * 60)

    # 1. 终止文件锁对应的进程
    if LOCK_DIR.exists():
        for lock_file in LOCK_DIR.glob("*.lock"):
            try:
                content = lock_file.read_text().strip()
                pid = int(content.split("\n")[0])
                if _is_process_running(pid):
                    print(f"  终止 PID {pid} ({lock_file.stem})...")
                    os.kill(pid, signal.SIGTERM)
                else:
                    print(f"  PID {pid} 已死 ({lock_file.stem})")
            except Exception as e:
                print(f"  处理 {lock_file} 失败: {e}")

    # 2. 终止数据库中记录的进程
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT task_name, pid
            FROM import_locks
            WHERE status = 'running' AND pid IS NOT NULL
        """
        )

        for row in rows:
            pid = row["pid"]
            if _is_process_running(pid):
                print(f"  终止 PID {pid} ({row['task_name']})...")
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception as e:
                    print(f"    失败: {e}")

    finally:
        await conn.close()


async def clean_expired_locks():
    """清理过期的锁"""
    print(f"\n🧹 清理过期锁 (>{LOCK_TIMEOUT_MINUTES} 分钟):")
    print("=" * 60)

    cleaned = 0

    # 1. 清理文件锁
    if LOCK_DIR.exists():
        for lock_file in LOCK_DIR.glob("*.lock"):
            try:
                content = lock_file.read_text().strip()
                lines = content.split("\n")
                pid = int(lines[0]) if lines else None

                # 如果进程已死，删除锁文件
                if pid is None or not _is_process_running(pid):
                    lock_file.unlink()
                    print(f"  删除 {lock_file.name} (进程已死)")
                    cleaned += 1
                    continue

                # 检查启动时间
                if len(lines) > 1:
                    try:
                        started = datetime.fromisoformat(lines[1])
                        if datetime.now() - started > timedelta(minutes=LOCK_TIMEOUT_MINUTES):
                            lock_file.unlink()
                            print(f"  删除 {lock_file.name} (已过期)")
                            cleaned += 1
                    except:
                        pass

            except Exception as e:
                print(f"  处理 {lock_file} 失败: {e}")

    # 2. 清理数据库锁
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        result = await conn.execute(
            """
            UPDATE import_locks
            SET status = 'expired',
                completed_at = NOW(),
                error_message = '锁超时自动清理'
            WHERE status = 'running'
              AND (
                  pid IS NULL
                  OR NOT EXISTS (
                      SELECT 1 FROM pg_stat_activity
                      WHERE pid = import_locks.pid
                  )
                  OR started_at < NOW() - INTERVAL '1 hour'
              )
        """
        )

        # 解析 affected rows
        if result:
            parts = result.split()
            if parts:
                db_cleaned = int(parts[-1])
                print(f"  数据库: 清理 {db_cleaned} 条过期记录")
                cleaned += db_cleaned

    finally:
        await conn.close()

    print(f"\n  总计清理: {cleaned} 条")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="数据库锁监控工具")
    parser.add_argument("--kill", action="store_true", help="终止所有导入进程")
    parser.add_argument("--clean", action="store_true", help="清理过期锁")
    parser.add_argument("--watch", action="store_true", help="持续监控")
    parser.add_argument("--interval", type=int, default=5, help="监控间隔(秒)")

    args = parser.parse_args()

    if args.kill:
        await kill_import_processes()
        return

    if args.clean:
        await clean_expired_locks()
        return

    # 默认：显示状态
    while True:
        print("\n" + "=" * 60)
        print(f"🔍 数据库锁状态检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        file_locks = await check_file_locks()
        db_locks = await check_database_locks(await asyncpg.connect(DATABASE_URL))

        conn = await asyncpg.connect(DATABASE_URL)
        try:
            await check_active_database_locks(conn)
            blocked = await check_blocked_queries(conn)
        finally:
            await conn.close()

        # 汇总
        total_file_locks = len([l for l in file_locks if l["is_running"]])
        total_db_locks = len([l for l in db_locks if l["is_running"]])
        total_blocked = len(blocked)

        print("\n" + "=" * 60)
        print(f"📊 汇总:")
        print(f"  运行中的文件锁: {total_file_locks}")
        print(f"  运行中的数据库锁: {total_db_locks}")
        print(f"  被阻塞的查询: {total_blocked}")

        if total_blocked > 0:
            print("\n⚠️  检测到查询阻塞！建议:")
            print("  1. 运行: python scripts/db_lock_monitor.py --clean")
            print("  2. 或: python scripts/db_lock_monitor.py --kill")

        if not args.watch:
            break

        print(f"\n下次检查在 {args.interval} 秒后...")
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    asyncio.run(main())
