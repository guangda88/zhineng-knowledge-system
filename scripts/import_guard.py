#!/usr/bin/env python3
"""统一导入门卫 - 所有导入操作的统一入口

防止多进程并发导致的数据库锁死问题。

用法:
    # 导入古籍数据
    python scripts/import_guard.py guji

    # 导入教科书
    python scripts/import_guard.py textbooks

    # 查看状态
    python scripts/import_guard.py --status

    # 强制解锁
    python scripts/import_guard.py --unlock guji
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.import_manager import ImportLockError, ImportManager

# 导入任务配置
IMPORT_TASKS = {
    "guji": {
        "script": "import_guji_safe.py",
        "module": "scripts.import_guji_safe",
        "function": "main",
        "description": "古籍数据导入",
    },
    "textbooks": {
        "script": "import_textbooks.py",
        "module": "scripts.import_textbooks",
        "function": "main",
        "description": "教科书数据导入",
    },
    "sys_books": {
        "script": "import_sys_books.py",
        "module": "scripts.import_sys_books",
        "function": "main",
        "description": "系统书目导入",
    },
    "guji_fast": {
        "script": "import_guji_fast.py",
        "module": "scripts.import_guji_fast",
        "function": "main",
        "description": "古籍数据快速导入",
    },
}


def print_status():
    """打印所有导入任务状态"""
    print("\n📊 导入任务状态:")
    print("=" * 60)

    # 文件锁状态
    lock_dir = ImportManager.LOCK_DIR
    if lock_dir.exists():
        print("\n文件锁:")
        for lock_file in lock_dir.glob("*.lock"):
            try:
                content = lock_file.read_text().strip()
                print(f"  📌 {lock_file.stem}:")
                print(f"     {content.replace(chr(10), ' | ')}")
            except:
                print(f"  📌 {lock_file.stem}: (无法读取)")
    else:
        print("\n文件锁: 无")

    # 数据库锁状态
    async def check_db_status():
        import asyncpg

        database_url = os.getenv(
            "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
        )
        try:
            conn = await asyncpg.connect(database_url)
            rows = await conn.fetch(
                """
                SELECT task_name, status, pid, started_at,
                       EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_ago
                FROM import_locks
                ORDER BY started_at DESC
                LIMIT 10
            """
            )
            await conn.close()

            if rows:
                print("\n数据库锁:")
                for row in rows:
                    status_icon = "🟢" if row["status"] == "running" else "✅"
                    print(f"  {status_icon} {row['task_name']}:")
                    print(f"     状态: {row['status']}, PID: {row['pid']}")
                    print(f"     运行: {row['minutes_ago']:.1f} 分钟")
            else:
                print("\n数据库锁: 无记录")

        except Exception as e:
            print(f"\n数据库锁: 查询失败 - {e}")

    asyncio.run(check_db_status())

    print("\n可用任务:")
    for name, config in IMPORT_TASKS.items():
        print(f"  • {name}: {config['description']}")


def force_unlock(task_name: str):
    """强制解锁指定任务"""
    print(f"\n🔓 解锁任务: {task_name}")

    # 删除文件锁
    lock_file = ImportManager.LOCK_DIR / f"{task_name}.lock"
    if lock_file.exists():
        lock_file.unlink()
        print(f"  ✅ 删除文件锁: {lock_file}")
    else:
        print(f"  ℹ️  文件锁不存在: {lock_file}")

    # 更新数据库状态
    async def update_db():
        import asyncpg

        database_url = os.getenv(
            "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
        )
        conn = await asyncpg.connect(database_url)
        try:
            await conn.execute(
                """
                UPDATE import_locks
                SET status = 'unlocked',
                    completed_at = NOW(),
                    error_message = '手动解锁'
                WHERE task_name = $1 AND status = 'running'
            """,
                task_name,
            )
            print("  ✅ 数据库状态已更新")
        except Exception as e:
            print(f"  ⚠️  数据库更新失败: {e}")
        finally:
            await conn.close()

    asyncio.run(update_db())


async def run_import(task_name: str, *args):
    """运行导入任务"""
    if task_name not in IMPORT_TASKS:
        print(f"❌ 未知任务: {task_name}")
        print(f"可用任务: {', '.join(IMPORT_TASKS.keys())}")
        return 1

    task = IMPORT_TASKS[task_name]
    print(f"\n🚀 启动导入任务: {task['description']}")
    print(f"   任务名称: {task_name}")
    print(f"   执行脚本: {task['script']}")

    try:
        # 使用 ImportManager 确保独占运行
        async with ImportManager(task_name):
            # 导入并执行任务
            module = __import__(task["module"], fromlist=[task["function"]])
            func = getattr(module, task["function"])

            # 如果是协程函数，直接运行
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()

        print(f"\n✅ 任务 {task_name} 完成")
        return 0

    except ImportLockError as e:
        print(f"\n❌ 导入失败: {e}")
        print("\n提示:")
        print("  1. 检查是否有其他导入进程在运行")
        print("  2. 使用 --status 查看详细状态")
        print(f"  3. 如需强制解锁: python scripts/import_guard.py --unlock {task_name}")
        return 1

    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="统一导入门卫 - 防止并发锁死",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/import_guard.py guji              # 导入古籍
  python scripts/import_guard.py textbooks --limit 10
  python scripts/import_guard.py --status          # 查看状态
  python scripts/import_guard.py --unlock guji     # 强制解锁
        """,
    )

    parser.add_argument("task", nargs="?", help="任务名称 (guji, textbooks, sys_books, ...)")
    parser.add_argument("--status", action="store_true", help="查看所有任务状态")
    parser.add_argument("--unlock", metavar="TASK", help="强制解锁指定任务")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="传递给导入脚本的额外参数")

    args = parser.parse_args()

    if args.status:
        print_status()
        return 0

    if args.unlock:
        force_unlock(args.unlock)
        return 0

    if not args.task:
        parser.print_help()
        return 1

    # 运行导入任务
    return asyncio.run(run_import(args.task, *args.args))


if __name__ == "__main__":
    sys.exit(main())
