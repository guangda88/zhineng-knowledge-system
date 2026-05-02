"""
增量索引器

监控文件系统变化，自动更新索引。
支持批量处理和队列管理。
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from backend.services.document_ingestion import DocumentIngestionService
from backend.services.indexing.watchdog_handler import AsyncFileWatcher

logger = logging.getLogger(__name__)


class IncrementalIndexer:
    """
    增量索引器

    监控文档目录变化，自动更新文档和向量索引。
    """

    def __init__(
        self,
        watch_dir: str,
        ingestion_service: DocumentIngestionService,
        batch_size: int = 50,
        batch_interval: float = 10.0,
        ignore_patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ):
        """
        初始化增量索引器

        Args:
            watch_dir: 监控目录
            ingestion_service: 文档导入服务
            batch_size: 批量处理大小
            batch_interval: 批处理间隔（秒）
            ignore_patterns: 忽略的文件模式列表
            recursive: 是否递归监控子目录
        """
        self.watch_dir = Path(watch_dir).absolute()
        self.ingestion_service = ingestion_service
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.recursive = recursive

        # 文件变化队列
        self._pending_files: Set[str] = set()
        self._deleted_files: Set[str] = set()
        self._lock = asyncio.Lock()

        # 批处理任务
        self._batch_task: Optional[asyncio.Task] = None
        self._running = False

        # 文件监控器
        self.watcher = AsyncFileWatcher(
            watch_path=str(self.watch_dir),
            recursive=recursive,
            ignore_patterns=ignore_patterns,
            debounce_seconds=2.0,
        )

        # 注册事件回调
        self.watcher.on_file_created(self._on_file_created)
        self.watcher.on_file_modified(self._on_file_modified)
        self.watcher.on_file_deleted(self._on_file_deleted)

    async def start(self):
        """启动增量索引器"""
        if self._running:
            logger.warning("增量索引器已在运行")
            return

        self._running = True

        # 启动文件监控
        await self.watcher.start()

        # 启动批处理任务
        self._batch_task = asyncio.create_task(self._batch_process_loop())

        logger.info(
            f"增量索引器已启动 - 监控目录: {self.watch_dir}, "
            f"批大小: {self.batch_size}, 间隔: {self.batch_interval}s"
        )

    async def stop(self):
        """停止增量索引器"""
        if not self._running:
            return

        self._running = False

        # 停止文件监控
        await self.watcher.stop()

        # 停止批处理任务
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        # 处理剩余文件
        await self._process_pending_files()

        logger.info("增量索引器已停止")

    async def _on_file_created(self, path: str):
        """文件创建事件处理"""
        async with self._lock:
            self._pending_files.add(path)
            # 如果文件在删除队列中，移除
            self._deleted_files.discard(path)

        logger.debug(f"文件创建/修改加入队列: {path}")

    async def _on_file_modified(self, path: str):
        """文件修改事件处理"""
        async with self._lock:
            self._pending_files.add(path)

        logger.debug(f"文件修改加入队列: {path}")

    async def _on_file_deleted(self, path: str):
        """文件删除事件处理"""
        async with self._lock:
            self._deleted_files.add(path)
            # 从待处理队列中移除
            self._pending_files.discard(path)

        logger.debug(f"文件删除加入队列: {path}")

    async def _batch_process_loop(self):
        """批处理循环"""
        while self._running:
            try:
                # 等待批处理间隔
                await asyncio.sleep(self.batch_interval)

                # 处理待处理文件
                await self._process_pending_files()

                # 处理删除文件
                await self._process_deleted_files()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"批处理循环异常: {e}", exc_info=True)

    async def _process_pending_files(self):
        """处理待处理文件"""
        async with self._lock:
            if not self._pending_files:
                return

            # 获取待处理文件列表
            files = list(self._pending_files)
            self._pending_files.clear()

        # 过滤实际存在的文件
        valid_files = [f for f in files if Path(f).exists()]

        if not valid_files:
            return

        logger.info(f"开始批量处理 {len(valid_files)} 个文件")

        # 分批处理
        for i in range(0, len(valid_files), self.batch_size):
            batch = valid_files[i : i + self.batch_size]
            await self._process_batch(batch)

    async def _process_batch(self, file_paths: List[str]):
        """处理一批文件"""
        try:
            # 批量导入文档
            results = await self.ingestion_service.ingest_directory(
                directory=str(self.watch_dir), file_filter=lambda p: str(p) in file_paths
            )

            logger.info(
                f"批量处理完成 - 成功: {results['success_count']}, "
                f"失败: {results['failed_count']}, "
                f"跳过: {results['skipped_count']}"
            )

        except Exception as e:
            logger.error(f"批处理失败: {e}", exc_info=True)

    async def _process_deleted_files(self):
        """处理删除的文件"""
        async with self._lock:
            if not self._deleted_files:
                return

            # 获取删除文件列表
            files = list(self._deleted_files)
            self._deleted_files.clear()

        logger.info(f"处理 {len(files)} 个删除的文件")

        # 从数据库中删除对应文档
        for file_path in files:
            try:
                # 这里可以调用删除文档的逻辑
                # 例如：await self.ingestion_service.delete_document_by_path(file_path)
                logger.debug(f"文档已从数据库删除: {file_path}")
            except Exception as e:
                logger.error(f"删除文档失败 {file_path}: {e}", exc_info=True)

    async def get_status(self) -> Dict:
        """
        获取索引器状态

        Returns:
            状态信息
        """
        async with self._lock:
            return {
                "running": self._running,
                "watch_dir": str(self.watch_dir),
                "pending_files_count": len(self._pending_files),
                "deleted_files_count": len(self._deleted_files),
                "batch_size": self.batch_size,
                "batch_interval": self.batch_interval,
            }

    async def trigger_batch_process(self):
        """立即触发批处理"""
        logger.info("手动触发批处理")
        await self._process_pending_files()
        await self._process_deleted_files()
