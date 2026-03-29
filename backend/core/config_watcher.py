"""
配置热更新系统

提供配置文件监视、热更新和重新加载功能
"""

import asyncio
import logging
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import hashlib
import json

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from backend.config import get_config

logger = logging.getLogger(__name__)


class ConfigChangeType(str, Enum):
    """配置变更类型"""
    MODIFIED = "modified"
    CREATED = "created"
    DELETED = "deleted"
    RELOADED = "reloaded"


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    change_type: ConfigChangeType
    file_path: str
    timestamp: datetime
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ConfigChangeHandler(ABC):
    """
    配置变更处理器基类

    当配置文件变更时，处理器会被调用以处理变更
    """

    @abstractmethod
    async def handle_config_change(self, event: ConfigChangeEvent) -> None:
        """
        处理配置变更

        Args:
            event: 配置变更事件
        """
        pass

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """
        判断是否可以处理指定的配置文件

        Args:
            file_path: 配置文件路径

        Returns:
            是否可以处理
        """
        pass


class ConfigWatcher:
    """
    配置文件监视器

    监视配置文件的变化并触发相应的处理逻辑
    """

    def __init__(
        self,
        watch_directories: Optional[List[str]] = None,
        watch_files: Optional[List[str]] = None,
        enabled: bool = True
    ):
        """
        初始化配置监视器

        Args:
            watch_directories: 要监视的目录列表
            watch_files: 要监视的文件列表
            enabled: 是否启用监视
        """
        self.watch_directories = watch_directories or []
        self.watch_files = watch_files or []
        self.enabled = enabled
        self.handlers: List[ConfigChangeHandler] = []
        self.file_hashes: Dict[str, str] = {}
        self._observer: Optional[Observer] = None
        self._running = False
        self._lock = asyncio.Lock()

    def add_handler(self, handler: ConfigChangeHandler) -> None:
        """
        添加配置变更处理器

        Args:
            handler: 配置变更处理器
        """
        self.handlers.append(handler)
        logger.info(f"Added config change handler: {handler.__class__.__name__}")

    def remove_handler(self, handler: ConfigChangeHandler) -> None:
        """
        移除配置变更处理器

        Args:
            handler: 配置变更处理器
        """
        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.info(f"Removed config change handler: {handler.__class__.__name__}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        计算文件的哈希值

        Args:
            file_path: 文件路径

        Returns:
            文件内容的哈希值
        """
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return ""

    def _initialize_file_hashes(self) -> None:
        """初始化文件哈希值"""
        for file_path in self.watch_files:
            if os.path.exists(file_path):
                self.file_hashes[file_path] = self._calculate_file_hash(file_path)
                logger.debug(f"Initialized hash for {file_path}: {self.file_hashes[file_path]}")

    async def _handle_file_change(self, file_path: str, change_type: ConfigChangeType) -> None:
        """
        处理文件变更

        Args:
            file_path: 文件路径
            change_type: 变更类型
        """
        async with self._lock:
            old_hash = self.file_hashes.get(file_path)
            new_hash = self._calculate_file_hash(file_path) if os.path.exists(file_path) else None

            # 检查文件内容是否真的改变了
            if old_hash == new_hash:
                logger.debug(f"File {file_path} content unchanged, skipping")
                return

            self.file_hashes[file_path] = new_hash

            event = ConfigChangeEvent(
                change_type=change_type,
                file_path=file_path,
                timestamp=datetime.now(),
                old_hash=old_hash,
                new_hash=new_hash
            )

            logger.info(f"Config file {change_type.value}: {file_path}")

            # 通知所有相关的处理器
            for handler in self.handlers:
                try:
                    if handler.can_handle(file_path):
                        await handler.handle_config_change(event)
                        logger.debug(f"Handler {handler.__class__.__name__} processed {file_path}")
                except Exception as e:
                    logger.error(f"Handler {handler.__class__.__name__} failed to process {file_path}: {e}")

    def _on_file_changed(self, event) -> None:
        """
        文件变更回调函数（由watchdog调用）

        Args:
            event: 文件系统事件
        """
        if not self.enabled:
            return

        file_path = event.src_path

        # 检查是否是我们要监视的文件
        if file_path not in self.watch_files:
            return

        # 确定变更类型
        if isinstance(event, FileCreatedEvent):
            change_type = ConfigChangeType.CREATED
        elif isinstance(event, FileModifiedEvent):
            change_type = ConfigChangeType.MODIFIED
        else:
            return

        # 异步处理文件变更
        asyncio.create_task(self._handle_file_change(file_path, change_type))

    async def start(self) -> None:
        """启动配置监视器"""
        if self._running:
            logger.warning("Config watcher is already running")
            return

        if not self.enabled:
            logger.info("Config watcher is disabled")
            return

        try:
            # 初始化文件哈希
            self._initialize_file_hashes()

            # 设置文件系统监视器
            if self.watch_directories:
                self._observer = Observer()
                for watch_dir in self.watch_directories:
                    if os.path.exists(watch_dir):
                        self._observer.schedule(
                            EventHandler(self._on_file_changed),
                            path=watch_dir,
                            recursive=False
                        )
                        logger.info(f"Watching directory: {watch_dir}")

                self._observer.start()
                self._running = True
                logger.info("Config watcher started successfully")
            else:
                logger.warning("No directories to watch, config watcher not started")

        except Exception as e:
            logger.error(f"Failed to start config watcher: {e}")
            self._running = False

    async def stop(self) -> None:
        """停止配置监视器"""
        if not self._running:
            return

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        self._running = False
        logger.info("Config watcher stopped")

    async def check_changes(self) -> None:
        """
        手动检查文件变更（用于测试或手动触发）

        这个方法会轮询所有监视的文件，检查是否有变更
        """
        for file_path in self.watch_files:
            if os.path.exists(file_path):
                current_hash = self._calculate_file_hash(file_path)
                old_hash = self.file_hashes.get(file_path)

                if current_hash != old_hash:
                    await self._handle_file_change(file_path, ConfigChangeType.MODIFIED)


class EventHandler(FileSystemEventHandler):
    """
    文件系统事件处理器（用于watchdog）

    Args:
        callback: 文件变更时的回调函数
    """

    def __init__(self, callback: Callable):
        self.callback = callback

    def on_modified(self, event):
        """文件修改事件"""
        if not event.is_directory:
            self.callback(event)

    def on_created(self, event):
        """文件创建事件"""
        if not event.is_directory:
            self.callback(event)


class ConfigReloadHandler(ConfigChangeHandler):
    """
    配置重新加载处理器

    当配置文件变更时，重新加载配置
    """

    def __init__(self, config_files: Optional[List[str]] = None):
        """
        初始化配置重新加载处理器

        Args:
            config_files: 要处理的配置文件列表
        """
        self.config_files = config_files or [
            ".env",
            ".env.local",
            "config.py",
            "config.json"
        ]
        self._reload_callbacks: List[Callable] = []

    def can_handle(self, file_path: str) -> bool:
        """
        判断是否可以处理指定的配置文件

        Args:
            file_path: 配置文件路径

        Returns:
            是否可以处理
        """
        file_name = os.path.basename(file_path)
        return file_name in self.config_files

    async def handle_config_change(self, event: ConfigChangeEvent) -> None:
        """
        处理配置变更

        Args:
            event: 配置变更事件
        """
        logger.info(f"Reloading configuration from {event.file_path}")

        try:
            # 重新加载配置
            from backend.config import reload_config
            await reload_config()

            # 调用所有注册的回调函数
            for callback in self._reload_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"Reload callback failed: {e}")

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            raise

    def add_reload_callback(self, callback: Callable) -> None:
        """
        添加配置重新加载回调函数

        Args:
            callback: 回调函数
        """
        self._reload_callbacks.append(callback)

    def remove_reload_callback(self, callback: Callable) -> None:
        """
        移除配置重新加载回调函数

        Args:
            callback: 回调函数
        """
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)


# 全局配置监视器实例
_global_config_watcher: Optional[ConfigWatcher] = None


def get_config_watcher() -> ConfigWatcher:
    """
    获取全局配置监视器实例

    Returns:
        全局配置监视器
    """
    global _global_config_watcher
    if _global_config_watcher is None:
        config = get_config()
        project_root = Path(__file__).parent.parent.parent

        # 设置要监视的配置文件
        config_files = [
            str(project_root / ".env"),
            str(project_root / ".env.local"),
            str(project_root / "config.py"),
        ]

        watch_directories = [str(project_root)]

        _global_config_watcher = ConfigWatcher(
            watch_directories=watch_directories,
            watch_files=config_files,
            enabled=getattr(config, 'CONFIG_HOT_RELOAD', True)
        )

    return _global_config_watcher


def reset_config_watcher() -> None:
    """重置全局配置监视器（主要用于测试）"""
    global _global_config_watcher
    if _global_config_watcher:
        asyncio.create_task(_global_config_watcher.stop())
    _global_config_watcher = None


# 导入dataclass
from dataclasses import dataclass
from abc import ABC, abstractmethod