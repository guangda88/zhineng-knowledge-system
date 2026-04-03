#!/usr/bin/env python3
"""导入管理器 - 防止并发导入导致数据库锁死

使用方法:
    from backend.services.import_manager import ImportManager

    with ImportManager("guji_import") as mgr:
        mgr.run_import(import_function)
"""

import fcntl
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


class ImportLockError(Exception):
    """导入锁冲突异常"""


class ImportManager:
    """导入管理器 - 提供进程互斥和资源管理"""

    # 锁文件目录
    LOCK_DIR = Path("/tmp/zhineng_imports")
    LOCK_DIR.mkdir(exist_ok=True)

    def __init__(self, task_name: str, database_url=None, timeout: int = 300):
        """
        初始化导入管理器

        Args:
            task_name: 任务名称，用于锁文件
            database_url: 数据库连接URL
            timeout: 锁超时时间(秒)
        """
        self.task_name = task_name
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
        )
        self.timeout = timeout

        self.lock_file = None
        self.lock_fd = None
        self.conn = None
        self.task_id = None

        # 设置信号处理
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """设置信号处理器，确保清理"""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理 - 清理资源并退出"""
        logger.warning(f"收到信号 {signum}，正在清理...")
        self._cleanup()
        sys.exit(130)  # 128 + SIGINT

    def _acquire_file_lock(self) -> None:
        """获取文件锁，防止多进程并发"""
        lock_file = self.LOCK_DIR / f"{self.task_name}.lock"

        try:
            # 打开锁文件
            fd = os.open(lock_file, os.O_CREAT | os.O_WRONLY, 0o644)

            # 尝试获取非阻塞锁
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # 写入进程信息
            os.write(fd, f"{os.getpid()}\n{datetime.now().isoformat()}\n".encode())

            self.lock_fd = fd
            self.lock_file = lock_file
            logger.info(f"获取文件锁成功: {lock_file}")

        except IOError:
            # 读取锁文件内容
            try:
                with open(lock_file) as f:
                    content = f.read()
                raise ImportLockError(
                    f"任务 {self.task_name} 已在运行\n"
                    f"锁信息: {content}\n"
                    f"如需强制解锁，删除文件: {lock_file}"
                )
            except (OSError, IOError):
                raise ImportLockError(
                    f"无法获取锁 {lock_file}，" f"可能有其他进程正在运行 {self.task_name}"
                )

    async def _check_database_locks(self) -> None:
        """检查数据库中是否有冲突的导入任务"""
        try:
            conn = await asyncpg.connect(self.database_url, timeout=10)

            # 创建导入任务表（如果不存在）
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

            # 检查是否有运行中的导入任务
            result = await conn.fetchrow(
                """
                SELECT COUNT(*) as count
                FROM import_locks
                WHERE task_name = $1
                  AND status = 'running'
                  AND (pg_backend_pid() != pid OR pid IS NULL)
            """,
                self.task_name,
            )

            await conn.close()

            if result and result["count"] > 0:
                raise ImportLockError(f"数据库中已有任务 {self.task_name} 在运行")

            logger.info("数据库锁检查通过")

        except asyncpg.PostgresConnectionError as e:
            logger.warning(f"无法连接数据库检查锁: {e}")
            # 继续执行，可能数据库还未启动

    async def _register_import_task(self) -> None:
        """在数据库中注册导入任务"""
        try:
            self.conn = await asyncpg.connect(self.database_url, timeout=10)

            # 创建导入任务表（如果不存在）
            await self.conn.execute(
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

            # 插入或更新任务记录
            await self.conn.execute(
                """
                INSERT INTO import_locks (task_name, status, pid)
                VALUES ($1, 'running', $2)
                ON CONFLICT (task_name)
                DO UPDATE SET
                    status = 'running',
                    pid = EXCLUDED.pid,
                    started_at = NOW(),
                    error_message = NULL
            """,
                self.task_name,
                os.getpid(),
            )

            # 获取任务ID
            result = await self.conn.fetchrow(
                "SELECT id FROM import_locks WHERE task_name = $1", self.task_name
            )
            self.task_id = result["id"] if result else None

            logger.info(f"注册导入任务: {self.task_name} (ID: {self.task_id})")

        except Exception as e:
            logger.warning(f"无法注册导入任务: {e}")

    async def _complete_import_task(self, error: Optional[str] = None) -> None:
        """标记导入任务完成"""
        if not self.conn:
            return

        try:
            await self.conn.execute(
                """
                UPDATE import_locks
                SET status = $1,
                    completed_at = NOW(),
                    error_message = $2
                WHERE task_name = $3
            """,
                "completed" if error is None else "failed",
                error,
                self.task_name,
            )

            logger.info(f"任务 {self.task_name} 状态: {error or 'completed'}")

        except Exception as e:
            logger.warning(f"无法更新任务状态: {e}")

    def _release_file_lock(self) -> None:
        """释放文件锁"""
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
            except OSError as e:
                logger.debug(f"释放文件锁失败: {e}")
            self.lock_fd = None

        if self.lock_file and self.lock_file.exists():
            try:
                self.lock_file.unlink()
            except OSError:
                pass

        logger.info(f"释放文件锁: {self.task_name}")

    def _cleanup(self) -> None:
        """清理资源"""
        # 1. 完成数据库任务
        if self.conn:
            try:
                # 创建新的事件循环来运行异步清理
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._complete_import_task("进程被终止"))
                finally:
                    loop.close()
            except (RuntimeError, OSError):
                pass

        # 2. 释放文件锁
        self._release_file_lock()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        # 1. 获取文件锁
        self._acquire_file_lock()

        # 2. 检查数据库锁
        await self._check_database_locks()

        # 3. 注册导入任务
        await self._register_import_task()

        # 4. 设置数据库超时
        if self.conn:
            await self.conn.execute(f"SET statement_timeout = '{self.timeout}s';")
            await self.conn.execute("SET lock_timeout = '5s';")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        error = str(exc_val) if exc_val else None

        # 完成任务
        await self._complete_import_task(error)

        # 关闭数据库连接
        if self.conn:
            await self.conn.close()
            self.conn = None

        # 释放文件锁
        self._release_file_lock()

        return False  # 不抑制异常

    def run_import(self, import_func, *args, **kwargs):
        """同步运行导入函数"""
        import asyncio

        async def _run():
            async with self:
                return await import_func(self.conn, *args, **kwargs)

        return asyncio.run(_run())


# 便捷函数
def acquire_import_lock(task_name: str):
    """
    获取导入锁的便捷函数

    用法:
        @acquire_import_lock("my_task")
        async def my_import(conn):
            # 导入逻辑
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with ImportManager(task_name) as mgr:
                return await func(mgr.conn, *args, **kwargs)

        return wrapper

    return decorator


# 命令行工具
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="导入任务管理")
    parser.add_argument("task", help="任务名称")
    parser.add_argument("--force-unlock", action="store_true", help="强制解锁")
    parser.add_argument("--status", action="store_true", help="查看状态")

    args = parser.parse_args()

    if args.force_unlock:
        lock_file = ImportManager.LOCK_DIR / f"{args.task}.lock"
        if lock_file.exists():
            lock_file.unlink()
            print(f"已解锁: {args.task}")
        else:
            print(f"锁文件不存在: {lock_file}")

    elif args.status:
        print(f"锁目录: {ImportManager.LOCK_DIR}")
        for lock_file in ImportManager.LOCK_DIR.glob("*.lock"):
            with open(lock_file) as f:
                print(f"\n{lock_file.name}:")
                print(f.read())
