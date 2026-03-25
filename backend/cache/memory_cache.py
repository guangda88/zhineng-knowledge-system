"""内存缓存实现

使用字典实现简单的内存缓存，支持TTL和LRU
"""

import asyncio
import time
from typing import Any, Dict, Optional
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class MemoryCache:
    """内存缓存

    使用LRU策略的内存缓存
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """初始化内存缓存

        Args:
            max_size: 最大条目数
            default_ttl: 默认TTL（秒）
        """
        self._max_size = max_size
        self._default_ttl = default_ttl

        # 使用OrderedDict实现LRU
        self._cache: OrderedDict = OrderedDict()

        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None

    @property
    def size(self) -> int:
        """获取当前缓存大小"""
        return len(self._cache)

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在或过期返回None
        """
        if key not in self._cache:
            return None

        # 检查是否过期
        value, expiry = self._cache[key]
        if expiry is not None and time.time() > expiry:
            del self._cache[key]
            return None

        # LRU: 移动到末尾
        self._cache.move_to_end(key)

        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示使用默认
        """
        # 计算过期时间
        ttl = ttl if ttl is not None else self._default_ttl
        expiry = time.time() + ttl if ttl > 0 else None

        # 检查容量
        if key not in self._cache and len(self._cache) >= self._max_size:
            # 删除最旧的项（LRU）
            self._cache.popitem(last=False)

        # 设置值
        self._cache[key] = (value, expiry)

        # LRU: 移动到末尾
        self._cache.move_to_end(key)

    async def delete(self, key: str) -> None:
        """删除缓存值

        Args:
            key: 缓存键
        """
        if key in self._cache:
            del self._cache[key]

    async def delete_pattern(self, pattern: str) -> None:
        """按模式删除缓存

        Args:
            pattern: 匹配模式（支持*通配符）
        """
        import fnmatch

        keys_to_delete = [
            key for key in self._cache
            if fnmatch.fnmatch(key, pattern)
        ]

        for key in keys_to_delete:
            del self._cache[key]

    async def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    async def cleanup_expired(self) -> None:
        """清理过期条目"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items()
            if expiry is not None and current_time > expiry
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)

    def get_info(self) -> Dict[str, Any]:
        """获取缓存信息

        Returns:
            缓存信息
        """
        return {
            "type": "memory",
            "size": len(self._cache),
            "max_size": self._max_size,
            "default_ttl": self._default_ttl
        }
