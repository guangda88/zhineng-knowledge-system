"""
测试增量索引器
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.indexing.incremental_indexer import IncrementalIndexer


@pytest.fixture
def temp_dir():
    """临时目录 fixture"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_ingestion_service():
    """模拟文档导入服务"""
    service = MagicMock()
    service.ingest_directory = AsyncMock(return_value={
        "success_count": 2,
        "failed_count": 0,
        "skipped_count": 0,
        "total_files": 2
    })
    return service


class TestIncrementalIndexer:
    """测试增量索引器"""

    @pytest.mark.asyncio
    async def test_incremental_indexer_initialization(self, temp_dir, mock_ingestion_service):
        """测试增量索引器初始化"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        assert indexer.watch_dir == Path(temp_dir).absolute()
        assert indexer.ingestion_service == mock_ingestion_service
        assert indexer.batch_size == 50
        assert indexer.batch_interval == 10.0
        assert not indexer._running

    @pytest.mark.asyncio
    async def test_incremental_indexer_start_stop(self, temp_dir, mock_ingestion_service):
        """测试增量索引器启动和停止"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        await indexer.start()
        assert indexer._running
        assert indexer.watcher._running

        await indexer.stop()
        assert not indexer._running
        assert not indexer.watcher._running

    @pytest.mark.asyncio
    async def test_on_file_created(self, temp_dir, mock_ingestion_service):
        """测试文件创建事件处理"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        await indexer._on_file_created("/tmp/test.txt")

        async with indexer._lock:
            assert "/tmp/test.txt" in indexer._pending_files

    @pytest.mark.asyncio
    async def test_on_file_modified(self, temp_dir, mock_ingestion_service):
        """测试文件修改事件处理"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        await indexer._on_file_modified("/tmp/test.txt")

        async with indexer._lock:
            assert "/tmp/test.txt" in indexer._pending_files

    @pytest.mark.asyncio
    async def test_on_file_deleted(self, temp_dir, mock_ingestion_service):
        """测试文件删除事件处理"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        await indexer._on_file_deleted("/tmp/test.txt")

        async with indexer._lock:
            assert "/tmp/test.txt" in indexer._deleted_files

    @pytest.mark.asyncio
    async def test_file_created_and_deleted(self, temp_dir, mock_ingestion_service):
        """测试文件创建后删除"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        # 文件创建
        await indexer._on_file_created("/tmp/test.txt")

        async with indexer._lock:
            assert "/tmp/test.txt" in indexer._pending_files

        # 文件删除
        await indexer._on_file_deleted("/tmp/test.txt")

        async with indexer._lock:
            assert "/tmp/test.txt" not in indexer._pending_files
            assert "/tmp/test.txt" in indexer._deleted_files

    @pytest.mark.asyncio
    async def test_process_pending_files(self, temp_dir, mock_ingestion_service):
        """测试处理待处理文件"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        # 创建测试文件
        test_file1 = os.path.join(temp_dir, "test1.txt")
        test_file2 = os.path.join(temp_dir, "test2.txt")
        Path(test_file1).write_text("content1")
        Path(test_file2).write_text("content2")

        # 添加到待处理队列
        async with indexer._lock:
            indexer._pending_files.add(test_file1)
            indexer._pending_files.add(test_file2)

        # 处理待处理文件
        await indexer._process_pending_files()

        # 验证调用
        mock_ingestion_service.ingest_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_pending_files_invalid_files(self, temp_dir, mock_ingestion_service):
        """测试处理不存在的文件"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        # 添加不存在的文件
        async with indexer._lock:
            indexer._pending_files.add("/tmp/nonexistent1.txt")
            indexer._pending_files.add("/tmp/nonexistent2.txt")

        # 处理待处理文件（应该被过滤）
        await indexer._process_pending_files()

        # 验证未被调用
        mock_ingestion_service.ingest_directory.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_status(self, temp_dir, mock_ingestion_service):
        """测试获取状态"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        await indexer.start()

        status = await indexer.get_status()

        assert status["running"] == True
        assert status["watch_dir"] == str(Path(temp_dir).absolute())
        assert "pending_files_count" in status
        assert "deleted_files_count" in status
        assert status["batch_size"] == 50
        assert status["batch_interval"] == 10.0

        await indexer.stop()

    @pytest.mark.asyncio
    async def test_trigger_batch_process(self, temp_dir, mock_ingestion_service):
        """测试手动触发批处理"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service
        )

        # 创建测试文件
        test_file = os.path.join(temp_dir, "test.txt")
        Path(test_file).write_text("test content")

        # 添加到待处理队列
        async with indexer._lock:
            indexer._pending_files.add(test_file)

        # 手动触发批处理
        await indexer.trigger_batch_process()

        # 验证调用
        mock_ingestion_service.ingest_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_batch_size_and_interval(self, temp_dir, mock_ingestion_service):
        """测试自定义批大小和间隔"""
        indexer = IncrementalIndexer(
            watch_dir=temp_dir,
            ingestion_service=mock_ingestion_service,
            batch_size=20,
            batch_interval=5.0
        )

        await indexer.start()

        status = await indexer.get_status()
        assert status["batch_size"] == 20
        assert status["batch_interval"] == 5.0

        await indexer.stop()
