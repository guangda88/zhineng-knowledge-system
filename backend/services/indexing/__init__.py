"""
索引更新模块

提供文档增量索引功能，包括文件监控和自动索引更新。
"""

from .incremental_indexer import IncrementalIndexer
from .watchdog_handler import AsyncFileWatcher, FileWatcher, IndexingEventHandler

__all__ = [
    "AsyncFileWatcher",
    "FileWatcher",
    "IndexingEventHandler",
    "IncrementalIndexer",
]
