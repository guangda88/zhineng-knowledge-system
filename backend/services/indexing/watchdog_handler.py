"""
文件系统监控处理器

使用 Watchdog 监控文档目录变化，触发增量索引更新。
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional, Set

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class IndexingEventHandler(FileSystemEventHandler):
    """
    文档索引事件处理器

    监听文件系统事件并触发索引更新。
    """

    def __init__(
        self,
        on_file_created: Optional[Callable[[str], None]] = None,
        on_file_modified: Optional[Callable[[str], None]] = None,
        on_file_deleted: Optional[Callable[[str], None]] = None,
        on_file_moved: Optional[Callable[[str, str], None]] = None,
        ignore_patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0,
    ):
        """
        初始化事件处理器

        Args:
            on_file_created: 文件创建回调
            on_file_modified: 文件修改回调
            on_file_deleted: 文件删除回调
            on_file_moved: 文件移动回调
            ignore_patterns: 忽略的文件模式列表
            debounce_seconds: 防抖时间（秒），避免同一文件短时间内多次触发
        """
        super().__init__()
        self.on_file_created = on_file_created
        self.on_file_modified = on_file_modified
        self.on_file_deleted = on_file_deleted
        self.on_file_moved = on_file_moved
        self.ignore_patterns = ignore_patterns or [
            ".DS_Store",
            ".git",
            ".gitignore",
            "__pycache__",
            "*.pyc",
            "*.swp",
            "*.tmp",
            "~*",
        ]
        self.debounce_seconds = debounce_seconds

        # 防抖缓存
        self._debounce_cache: dict[str, float] = {}
        self._loop = asyncio.get_event_loop()

    def _should_ignore(self, path: str) -> bool:
        """检查是否应该忽略该文件"""
        path_obj = Path(path)
        filename = path_obj.name

        # 检查文件名模式
        for pattern in self.ignore_patterns:
            if pattern.startswith("."):
                # 检查扩展名
                if path_obj.suffix == pattern or filename == pattern:
                    return True
            elif "*" in pattern:
                # 简单通配符匹配
                import fnmatch

                if fnmatch.fnmatch(filename, pattern):
                    return True
            elif filename == pattern:
                return True

        return False

    def _is_debounced(self, path: str) -> bool:
        """检查是否在防抖期内"""
        import time

        now = time.time()
        last_event = self._debounce_cache.get(path, 0)

        if now - last_event < self.debounce_seconds:
            return True

        self._debounce_cache[path] = now
        return False

    def on_created(self, event: FileCreatedEvent):
        """文件创建事件"""
        if event.is_directory or self._should_ignore(event.src_path):
            return

        if self._is_debounced(event.src_path):
            logger.debug(f"文件创建事件被防抖: {event.src_path}")
            return

        logger.info(f"检测到文件创建: {event.src_path}")
        if self.on_file_created:
            self.on_file_created(event.src_path)

    def on_modified(self, event: FileModifiedEvent):
        """文件修改事件"""
        if event.is_directory or self._should_ignore(event.src_path):
            return

        if self._is_debounced(event.src_path):
            logger.debug(f"文件修改事件被防抖: {event.src_path}")
            return

        logger.info(f"检测到文件修改: {event.src_path}")
        if self.on_file_modified:
            self.on_file_modified(event.src_path)

    def on_deleted(self, event: FileDeletedEvent):
        """文件删除事件"""
        if event.is_directory or self._should_ignore(event.src_path):
            return

        logger.info(f"检测到文件删除: {event.src_path}")
        if self.on_file_deleted:
            self.on_file_deleted(event.src_path)

    def on_moved(self, event: FileMovedEvent):
        """文件移动事件"""
        if event.is_directory or self._should_ignore(event.dest_path):
            return

        logger.info(f"检测到文件移动: {event.src_path} -> {event.dest_path}")
        if self.on_file_moved:
            self.on_file_moved(event.src_path, event.dest_path)


class FileWatcher:
    """
    文件监控器

    使用 Watchdog 监控指定目录的文件变化。
    """

    def __init__(
        self, watch_path: str, event_handler: IndexingEventHandler, recursive: bool = True
    ):
        """
        初始化文件监控器

        Args:
            watch_path: 监控目录路径
            event_handler: 事件处理器
            recursive: 是否递归监控子目录
        """
        self.watch_path = Path(watch_path).absolute()
        self.event_handler = event_handler
        self.recursive = recursive
        self.observer = Observer()
        self._running = False

    def start(self):
        """启动文件监控"""
        if self._running:
            logger.warning(f"文件监控已在运行: {self.watch_path}")
            return

        if not self.watch_path.exists():
            logger.error(f"监控目录不存在: {self.watch_path}")
            raise FileNotFoundError(f"监控目录不存在: {self.watch_path}")

        self.observer.schedule(self.event_handler, str(self.watch_path), recursive=self.recursive)
        self.observer.start()
        self._running = True

        logger.info(f"文件监控已启动: {self.watch_path} (递归: {self.recursive})")

    def stop(self):
        """停止文件监控"""
        if not self._running:
            return

        self.observer.stop()
        self.observer.join()
        self._running = False

        logger.info(f"文件监控已停止: {self.watch_path}")

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.stop()


class AsyncFileWatcher(FileWatcher):
    """
    异步文件监控器

    将文件系统事件转换为异步回调。
    """

    def __init__(
        self,
        watch_path: str,
        recursive: bool = True,
        ignore_patterns: Optional[List[str]] = None,
        debounce_seconds: float = 2.0,
    ):
        """
        初始化异步文件监控器

        Args:
            watch_path: 监控目录路径
            recursive: 是否递归监控子目录
            ignore_patterns: 忽略的文件模式列表
            debounce_seconds: 防抖时间（秒）
        """
        self._on_file_created_callback: Optional[Callable[[str], Awaitable]] = None
        self._on_file_modified_callback: Optional[Callable[[str], Awaitable]] = None
        self._on_file_deleted_callback: Optional[Callable[[str], Awaitable]] = None
        self._on_file_moved_callback: Optional[Callable[[str, str], Awaitable]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # 创建事件处理器
        event_handler = IndexingEventHandler(
            on_file_created=self._on_file_created,
            on_file_modified=self._on_file_modified,
            on_file_deleted=self._on_file_deleted,
            on_file_moved=self._on_file_moved,
            ignore_patterns=ignore_patterns,
            debounce_seconds=debounce_seconds,
        )

        super().__init__(watch_path, event_handler, recursive)

    async def start(self):
        """启动异步文件监控"""
        # 保存事件循环引用
        self._loop = asyncio.get_running_loop()
        # 调用父类的同步 start 方法
        super().start()
        logger.info(f"异步文件监控已启动: {self.watch_path}")

    async def stop(self):
        """停止异步文件监控"""
        self._loop = None
        # 调用父类的同步 stop 方法
        super().stop()
        logger.info(f"异步文件监控已停止: {self.watch_path}")

    def on_file_created(self, callback: Callable[[str], Awaitable]):
        """注册文件创建回调"""
        self._on_file_created_callback = callback
        return self

    def on_file_modified(self, callback: Callable[[str], Awaitable]):
        """注册文件修改回调"""
        self._on_file_modified_callback = callback
        return self

    def on_file_deleted(self, callback: Callable[[str], Awaitable]):
        """注册文件删除回调"""
        self._on_file_deleted_callback = callback
        return self

    def on_file_moved(self, callback: Callable[[str, str], Awaitable]):
        """注册文件移动回调"""
        self._on_file_moved_callback = callback
        return self

    def _on_file_created(self, path: str):
        """文件创建事件（同步转异步）"""
        if self._on_file_created_callback and self._loop:
            asyncio.run_coroutine_threadsafe(self._on_file_created_callback(path), self._loop)

    def _on_file_modified(self, path: str):
        """文件修改事件（同步转异步）"""
        if self._on_file_modified_callback and self._loop:
            asyncio.run_coroutine_threadsafe(self._on_file_modified_callback(path), self._loop)

    def _on_file_deleted(self, path: str):
        """文件删除事件（同步转异步）"""
        if self._on_file_deleted_callback and self._loop:
            asyncio.run_coroutine_threadsafe(self._on_file_deleted_callback(path), self._loop)

    def _on_file_moved(self, src_path: str, dest_path: str):
        """文件移动事件（同步转异步）"""
        if self._on_file_moved_callback and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._on_file_moved_callback(src_path, dest_path), self._loop
            )
