# -*- coding: utf-8 -*-
"""
分层缓存管理器
Tiered Cache Manager with Stale-While-Revalidate Pattern

PERFORMANCE OPTIMIZATION:
- 分层缓存策略（HOT/WARM/COLD）
- Stale-While-Revalidate模式
- 提高缓存命中率（预期从<50%提升到>80%）
"""

import asyncio
import json
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass

import redis
from cachetools import TTLCache

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """缓存级别"""

    HOT = 1  # 热数据（频繁访问）- 1小时
    WARM = 2  # 温数据（偶尔访问）- 30分钟
    COLD = 3  # 冷数据（很少访问）- 5分钟


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    created_at: float
    expires_at: float
    level: CacheLevel
    access_count: int = 0
    last_accessed: float = 0


class StaleWhileRevalidateCache:
    """
    过期时重新验证的缓存

    Stale-While-Revalidate模式：
    1. 缓存过期时，返回过期数据
    2. 同时异步刷新缓存
    3. 下次请求返回新鲜数据

    优势：
    - 减少延迟（返回过期数据而非等待）
    - 提高缓存命中率
    - 减少后端负载
    """

    def __init__(
        self,
        redis_client=None,
        ttl_by_level: Dict[CacheLevel, int] = None,
        enable_stale: bool = True,
    ):
        """
        初始化Stale-While-Revalidate缓存

        Args:
            redis_client: Redis客户端
            ttl_by_level: 各级别TTL配置
            enable_stale: 是否启用过期数据返回
        """
        self.redis_client = redis_client
        self.enable_stale = enable_stale

        # 默认TTL配置
        self.ttl_by_level = ttl_by_level or {
            CacheLevel.HOT: 3600,  # 1小时
            CacheLevel.WARM: 1800,  # 30分钟
            CacheLevel.COLD: 300,  # 5分钟
        }

        # 内存缓存（L1）
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.memory_max_size = 10000

        # 正在刷新的键
        self.refreshing_keys: Dict[str, asyncio.Task] = {}

        logger.info("StaleWhileRevalidateCache initialized")

    async def get(
        self,
        key: str,
        level: CacheLevel = CacheLevel.WARM,
        data_loader: Optional[Callable] = None,
    ) -> tuple[Any, bool]:
        """
        获取缓存

        Args:
            key: 缓存键
            level: 缓存级别
            data_loader: 数据加载函数（用于异步刷新）

        Returns:
            (值, 是否过期)
        """
        now = time.time()

        # L1: 内存缓存
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            entry.access_count += 1
            entry.last_accessed = now

            if entry.expires_at > now:
                # 未过期
                return entry.value, False
            else:
                # 已过期
                if self.enable_stale:
                    # 触发异步刷新
                    if data_loader and key not in self.refreshing_keys:
                        asyncio.create_task(self._revalidate(key, data_loader, level))
                    return entry.value, True  # 返回过期数据
                else:
                    # 删除过期条目
                    del self.memory_cache[key]
                    return None, True

        # L2: Redis缓存
        if self.redis_client:
            try:
                cached = await asyncio.to_thread(self.redis_client.get, key)
                if cached:
                    entry_data = json.loads(cached)
                    entry = CacheEntry(**entry_data)

                    if entry.expires_at > now:
                        # 未过期，回填到内存缓存
                        self._set_memory(key, entry)
                        return entry.value, False
                    else:
                        # 已过期
                        if self.enable_stale:
                            if data_loader and key not in self.refreshing_keys:
                                asyncio.create_task(self._revalidate(key, data_loader, level))
                            return entry.value, True
                        else:
                            await asyncio.to_thread(self.redis_client.delete, key)
                            return None, True
            except Exception as e:
                logger.warning(f"Failed to get from Redis: {e}")

        return None, False

    async def set(self, key: str, value: Any, level: CacheLevel = CacheLevel.WARM):
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            level: 缓存级别
        """
        ttl = self.ttl_by_level[level]
        now = time.time()

        # 创建缓存条目
        entry = CacheEntry(
            value=value,
            created_at=now,
            expires_at=now + ttl,
            level=level,
            access_count=0,
            last_accessed=now,
        )

        # 写入内存缓存
        self._set_memory(key, entry)

        # 写入Redis缓存
        if self.redis_client:
            try:
                await asyncio.to_thread(
                    self.redis_client.setex,
                    key,
                    ttl,
                    json.dumps(entry.__dict__),
                )
            except Exception as e:
                logger.warning(f"Failed to set to Redis: {e}")

    async def _revalidate(self, key: str, data_loader: Callable, level: CacheLevel):
        """
        异步刷新缓存

        Args:
            key: 缓存键
            data_loader: 数据加载函数
            level: 缓存级别
        """
        if key in self.refreshing_keys:
            return

        task = asyncio.current_task()
        self.refreshing_keys[key] = task

        try:
            logger.debug(f"Revalidating cache key: {key}")
            new_value = await data_loader(key)
            await self.set(key, new_value, level)
            logger.debug(f"Cache revalidated: {key}")
        except Exception as e:
            logger.error(f"Failed to revalidate cache {key}: {e}")
        finally:
            if key in self.refreshing_keys:
                del self.refreshing_keys[key]

    def _set_memory(self, key: str, entry: CacheEntry):
        """设置内存缓存（LRU淘汰）"""
        if len(self.memory_cache) >= self.memory_max_size:
            # 删除最旧的条目（最久未访问）
            oldest_key = min(
                self.memory_cache.keys(),
                key=lambda k: self.memory_cache[k].last_accessed,
            )
            del self.memory_cache[oldest_key]

        self.memory_cache[key] = entry

    async def delete(self, key: str):
        """删除缓存"""
        # 删除内存缓存
        if key in self.memory_cache:
            del self.memory_cache[key]

        # 删除Redis缓存
        if self.redis_client:
            try:
                await asyncio.to_thread(self.redis_client.delete, key)
            except Exception as e:
                logger.warning(f"Failed to delete from Redis: {e}")

        # 清理刷新任务
        if key in self.refreshing_keys:
            task = self.refreshing_keys[key]
            task.cancel()
            del self.refreshing_keys[key]

    async def clear_expired(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = [key for key, entry in self.memory_cache.items() if entry.expires_at <= now]

        for key in expired_keys:
            del self.memory_cache[key]

        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired memory cache entries")

    def get_stats(self) -> dict:
        """获取缓存统计"""
        now = time.time()
        total = len(self.memory_cache)
        active = sum(1 for e in self.memory_cache.values() if e.expires_at > now)
        expired = total - active

        # 计算访问热度
        hot_keys = sum(1 for e in self.memory_cache.values() if e.access_count > 10)

        return {
            "total": total,
            "active": active,
            "expired": expired,
            "hot_keys": hot_keys,
            "max_size": self.memory_max_size,
            "usage_percent": (
                (total / self.memory_max_size) * 100 if self.memory_max_size > 0 else 0
            ),
            "refreshing": len(self.refreshing_keys),
        }


# 全局缓存实例
_tiered_cache: Optional[StaleWhileRevalidateCache] = None


def get_tiered_cache() -> StaleWhileRevalidateCache:
    """获取全局分层缓存实例"""
    global _tiered_cache
    if _tiered_cache is None:
        # 初始化Redis客户端
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=False,  # 需要二进制模式存储pickle数据
        )
        _tiered_cache = StaleWhileRevalidateCache(redis_client=redis_client)
    return _tiered_cache
