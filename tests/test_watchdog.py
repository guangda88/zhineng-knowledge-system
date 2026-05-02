"""
测试 watchdog 文件监控处理器
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

import pytest

from backend.services.indexing.watchdog_handler import (
    AsyncFileWatcher,
    FileWatcher,
    IndexingEventHandler,
)


@pytest.fixture
def temp_dir():
    """临时目录 fixture"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestIndexingEventHandler:
    """测试事件处理器"""

    def test_should_ignore_basic_patterns(self, temp_dir):
        """测试忽略基本文件模式"""
        handler = IndexingEventHandler()

        # 应该忽略的文件
        assert handler._should_ignore(os.path.join(temp_dir, ".DS_Store"))
        assert handler._should_ignore(os.path.join(temp_dir, "test.pyc"))
        assert handler._should_ignore(os.path.join(temp_dir, "test.swp"))
        assert handler._should_ignore(os.path.join(temp_dir, ".git"))

        # 不应该忽略的文件
        assert not handler._should_ignore(os.path.join(temp_dir, "document.pdf"))
        assert not handler._should_ignore(os.path.join(temp_dir, "readme.txt"))

    def test_debounce_mechanism(self):
        """测试防抖机制"""
        handler = IndexingEventHandler(debounce_seconds=1.0)

        # 第一次检查 - 未被防抖
        assert not handler._is_debounced("test.txt")

        # 立即第二次检查 - 被防抖
        assert handler._is_debounced("test.txt")

        # 等待 1 秒后 - 不被防抖
        time.sleep(1.1)
        assert not handler._is_debounced("test.txt")


class TestFileWatcher:
    """测试文件监控器"""

    def test_file_watcher_initialization(self, temp_dir):
        """测试文件监控器初始化"""
        handler = IndexingEventHandler()
        watcher = FileWatcher(temp_dir, handler)

        assert watcher.watch_path == Path(temp_dir).absolute()
        assert not watcher._running

    def test_file_watcher_start_stop(self, temp_dir):
        """测试文件监控器启动和停止"""
        handler = IndexingEventHandler()
        watcher = FileWatcher(temp_dir, handler)

        watcher.start()
        assert watcher._running

        watcher.stop()
        assert not watcher._running

    def test_file_watcher_context_manager(self, temp_dir):
        """测试上下文管理器"""
        handler = IndexingEventHandler()

        with FileWatcher(temp_dir, handler) as watcher:
            assert watcher._running

        assert not watcher._running

    def test_file_watcher_nonexistent_dir(self, temp_dir):
        """测试不存在的目录"""
        handler = IndexingEventHandler()
        nonexistent_dir = os.path.join(temp_dir, "nonexistent")

        with pytest.raises(FileNotFoundError):
            FileWatcher(nonexistent_dir, handler).start()


class TestAsyncFileWatcher:
    """测试异步文件监控器"""

    @pytest.mark.asyncio
    async def test_async_file_watcher_initialization(self, temp_dir):
        """测试异步文件监控器初始化"""
        watcher = AsyncFileWatcher(temp_dir)

        assert watcher.watch_path == Path(temp_dir).absolute()
        assert not watcher._running

    @pytest.mark.asyncio
    async def test_async_file_watcher_start_stop(self, temp_dir):
        """测试异步文件监控器启动和停止"""
        watcher = AsyncFileWatcher(temp_dir)

        await watcher.start()
        assert watcher._running

        await watcher.stop()
        assert not watcher._running

    @pytest.mark.asyncio
    async def test_file_created_callback(self, temp_dir):
        """测试文件创建回调"""
        created_files = []

        async def on_created(path: str):
            created_files.append(path)

        watcher = AsyncFileWatcher(temp_dir)
        watcher.on_file_created(on_created)

        await watcher.start()

        # 创建测试文件
        test_file = os.path.join(temp_dir, "test.txt")
        Path(test_file).write_text("test content")

        # 等待事件处理
        await asyncio.sleep(0.5)

        await watcher.stop()

        assert any(f.endswith("test.txt") for f in created_files)

    @pytest.mark.asyncio
    async def test_file_modified_callback(self, temp_dir):
        """测试文件修改回调"""
        modified_files = []

        async def on_modified(path: str):
            modified_files.append(path)

        watcher = AsyncFileWatcher(temp_dir)
        watcher.on_file_modified(on_modified)

        # 先创建文件
        test_file = os.path.join(temp_dir, "test.txt")
        Path(test_file).write_text("initial content")

        await watcher.start()

        # 修改文件
        Path(test_file).write_text("modified content")

        # 等待事件处理
        await asyncio.sleep(0.5)

        await watcher.stop()

        assert any(f.endswith("test.txt") for f in modified_files)

    @pytest.mark.asyncio
    async def test_file_deleted_callback(self, temp_dir):
        """测试文件删除回调"""
        deleted_files = []

        async def on_deleted(path: str):
            deleted_files.append(path)

        watcher = AsyncFileWatcher(temp_dir)
        watcher.on_file_deleted(on_deleted)

        # 先创建文件
        test_file = os.path.join(temp_dir, "test.txt")
        Path(test_file).write_text("test content")

        await watcher.start()

        # 删除文件
        os.remove(test_file)

        # 等待事件处理
        await asyncio.sleep(0.5)

        await watcher.stop()

        assert any(f.endswith("test.txt") for f in deleted_files)
