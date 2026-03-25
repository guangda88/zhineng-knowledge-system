"""缓存管理器

提供统一的缓存接口，支持多级缓存、缓存预热、统计等功能
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar

from .memory_cache import MemoryCache
from .redis_cache import RedisCache, RedisConfig

logger = logging.getLogger(__name__)

# 尝试导入缓存指标收集器
try:
    from monitoring.cache_metrics import (
        CacheLevel,
        CacheMetricsCollector,
        CacheMetricsMiddleware,
        get_cache_metrics_collector,
    )

    CACHE_METRICS_AVAILABLE = True
except ImportError:
    CACHE_METRICS_AVAILABLE = False
    logger.warning("缓存指标收集器不可用，监控功能将受限")

T = TypeVar("T")


class CacheLevel(Enum):
    """缓存级别"""

    L1 = "memory"  # 内存缓存
    L2 = "redis"  # Redis缓存


class CacheStrategy(Enum):
    """缓存策略"""

    WRITE_THROUGH = "write_through"  # 写入时同步更新所有层级
    WRITE_BACK = "write_back"  # 写入时只更新L1，异步更新L2
    WRITE_AROUND = "write_around"  # 写入时不更新缓存


@dataclass
class CacheConfig:
    """缓存配置"""

    enabled: bool = True
    default_ttl: int = 3600  # 默认TTL（秒）
    max_size: int = 1000  # L1缓存最大条目数
    key_prefix: str = "zhineng_kb:"  # 缓存键前缀

    # 缓存策略
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH

    # 各类资源的TTL配置
    ttl_config: Dict[str, int] = field(
        default_factory=lambda: {
            "query_result": 3600,  # 查询结果缓存1小时
            "vector_search": 1800,  # 向量搜索缓存30分钟
            "llm_response": 7200,  # LLM响应缓存2小时
            "document": 86400,  # 文档内容缓存1天
            "domain_stats": 300,  # 领域统计缓存5分钟
            "health_check": 60,  # 健康检查缓存1分钟
            "embedding": 604800,  # 嵌入向量缓存7天
            "bm25_index": 86400,  # BM25索引缓存1天
        }
    )

    # 预热配置
    warm_up_enabled: bool = True
    warm_up_batch_size: int = 50

    # 统计配置
    stats_enabled: bool = True
    stats_sample_rate: float = 1.0  # 统计采样率


@dataclass
class CacheStats:
    """缓存统计信息"""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    l1_hits: int = 0
    l2_hits: int = 0
    errors: int = 0

    @property
    def total_requests(self) -> int:
        """总请求数"""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def l1_hit_rate(self) -> float:
        """L1命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.l1_hits / self.total_requests

    @property
    def l2_hit_rate(self) -> float:
        """L2命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.l2_hits / self.total_requests


class CacheManager:
    """缓存管理器

    提供多级缓存支持：
    - L1: 内存缓存（快速，容量小）
    - L2: Redis缓存（较慢，容量大，分布式）

    特性：
    - 自动回填：L2命中时自动回填L1
    - 批量操作：支持批量获取和设置
    - 缓存预热：支持预加载常用数据
    - 统计监控：记录命中率等指标
    """

    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        redis_url: Optional[str] = None,
        redis_config: Optional[RedisConfig] = None,
        enable_metrics: bool = True,
    ):
        """初始化缓存管理器

        Args:
            config: 缓存配置
            redis_url: Redis连接URL（已弃用，建议使用redis_config）
            redis_config: Redis配置
            enable_metrics: 是否启用指标收集
        """
        self.config = config or CacheConfig()

        # L1: 内存缓存
        self._l1_cache = MemoryCache(
            max_size=self.config.max_size, default_ttl=self.config.default_ttl
        )

        # L2: Redis缓存（可选）
        self._l2_cache: Optional[RedisCache] = None
        if redis_url or redis_config:
            try:
                if redis_config:
                    self._l2_cache = RedisCache(config=redis_config)
                else:
                    self._l2_cache = RedisCache(url=redis_url, key_prefix=self.config.key_prefix)
                logger.info("Redis缓存已启用")
            except Exception as e:
                logger.warning(f"Redis缓存初始化失败，仅使用内存缓存: {e}")

        # 统计信息
        self._stats = CacheStats()
        self._stats_lock = asyncio.Lock()

        # 热键追踪（用于缓存预热）
        self._hot_keys: Dict[str, int] = {}
        self._hot_keys_lock = asyncio.Lock()
        self._hot_keys_threshold = 10  # 访问次数阈值

        # 缓存指标收集器
        self._metrics_collector: Optional[CacheMetricsCollector] = None
        self._metrics_middleware: Optional[CacheMetricsMiddleware] = None
        if enable_metrics and CACHE_METRICS_AVAILABLE:
            try:
                self._metrics_collector = get_cache_metrics_collector()
                self._metrics_middleware = CacheMetricsMiddleware(self._metrics_collector)
                logger.info("缓存指标收集器已启用")
            except Exception as e:
                logger.warning(f"缓存指标收集器初始化失败: {e}")

    def is_enabled(self) -> bool:
        """检查缓存是否启用"""
        return self.config.enabled

    def _make_key(self, key: str, namespace: str = "") -> str:
        """生成缓存键

        Args:
            key: 原始键
            namespace: 命名空间

        Returns:
            完整缓存键
        """
        if namespace:
            key = f"{namespace}:{key}"

        # 添加前缀
        full_key = f"{self.config.key_prefix}{key}"

        # 如果键太长，使用哈希
        if len(full_key) > 200:
            key_hash = hashlib.md5(full_key.encode(), usedforsecurity=False).hexdigest()[:8]
            full_key = f"{self.config.key_prefix}hash:{key_hash}"

        return full_key

    def _get_ttl(self, resource_type: str) -> int:
        """获取资源的TTL

        Args:
            resource_type: 资源类型

        Returns:
            TTL（秒）
        """
        return self.config.ttl_config.get(resource_type, self.config.default_ttl)

    async def _track_hot_key(self, key: str) -> None:
        """追踪热键

        Args:
            key: 缓存键
        """
        if not self.config.warm_up_enabled:
            return

        async with self._hot_keys_lock:
            self._hot_keys[key] = self._hot_keys.get(key, 0) + 1

    async def _update_stats(
        self,
        hit: bool = False,
        miss: bool = False,
        l1_hit: bool = False,
        l2_hit: bool = False,
        set_op: bool = False,
        delete_op: bool = False,
        error: bool = False,
    ) -> None:
        """更新统计信息

        Args:
            hit: 命中
            miss: 未命中
            l1_hit: L1命中
            l2_hit: L2命中
            set_op: 设置操作
            delete_op: 删除操作
            error: 错误
        """
        if not self.config.stats_enabled:
            return

        # 采样
        import random

        if random.random() > self.config.stats_sample_rate:
            return

        async with self._stats_lock:
            if hit:
                self._stats.hits += 1
            if miss:
                self._stats.misses += 1
            if l1_hit:
                self._stats.l1_hits += 1
            if l2_hit:
                self._stats.l2_hits += 1
            if set_op:
                self._stats.sets += 1
            if delete_op:
                self._stats.deletes += 1
            if error:
                self._stats.errors += 1

    async def get(
        self,
        key: str,
        namespace: str = "",
        default: Any = None,
        update_l1: bool = True,
    ) -> Any:
        """获取缓存值

        Args:
            key: 缓存键
            namespace: 命名空间
            default: 默认值
            update_l1: 是否回填L1缓存

        Returns:
            缓存值或默认值
        """
        if not self.is_enabled():
            return default

        start_time = time.time()
        full_key = self._make_key(key, namespace)

        # 先查L1
        try:
            value = await self._l1_cache.get(full_key)
            if value is not None:
                await self._update_stats(hit=True, l1_hit=True)
                await self._track_hot_key(full_key)

                # 记录指标
                if self._metrics_collector:
                    self._metrics_collector.record_hit(CacheLevel.L1, namespace, "get")
                    duration = time.time() - start_time
                    self._metrics_collector.record_latency(duration, "get")

                return value
        except Exception as e:
            logger.warning(f"L1缓存读取失败: {e}")
            if self._metrics_collector:
                self._metrics_collector.record_error(CacheLevel.L1, "get_failed")

        # 再查L2
        if self._l2_cache:
            try:
                value = await self._l2_cache.get(full_key)
                if value is not None:
                    await self._update_stats(hit=True, l2_hit=True)
                    await self._track_hot_key(full_key)

                    # 回填L1
                    if update_l1:
                        await self._l1_cache.set(full_key, value, ttl=self._get_ttl(namespace))

                    # 记录指标
                    if self._metrics_collector:
                        self._metrics_collector.record_hit(CacheLevel.L2, namespace, "get")
                        duration = time.time() - start_time
                        self._metrics_collector.record_latency(duration, "get")

                    return value
            except Exception as e:
                logger.warning(f"L2缓存读取失败: {e}")
                await self._update_stats(error=True)
                if self._metrics_collector:
                    self._metrics_collector.record_error(CacheLevel.L2, "get_failed")

        await self._update_stats(miss=True)

        # 记录未命中
        if self._metrics_collector:
            self._metrics_collector.record_miss(namespace, "get")
            duration = time.time() - start_time
            self._metrics_collector.record_latency(duration, "get")

        return default

    async def get_many(
        self,
        keys: List[str],
        namespace: str = "",
    ) -> Dict[str, Any]:
        """批量获取缓存值

        Args:
            keys: 缓存键列表
            namespace: 命名空间

        Returns:
            键值对字典
        """
        if not self.is_enabled():
            return {}

        results = {}

        # 先从L1批量获取
        for key in keys:
            value = await self.get(key, namespace)
            if value is not None:
                results[key] = value

        return results

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str = "",
        ttl: Optional[int] = None,
    ) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            namespace: 命名空间
            ttl: 过期时间（秒），None表示使用默认
        """
        if not self.is_enabled():
            return

        start_time = time.time()
        full_key = self._make_key(key, namespace)

        # 确定TTL
        if ttl is None:
            ttl = self._get_ttl(namespace)

        try:
            # 根据策略设置缓存
            strategy = self.config.strategy
            # 支持字符串和枚举
            if isinstance(strategy, str):
                strategy = CacheStrategy(strategy)

            if strategy == CacheStrategy.WRITE_THROUGH:
                # 同步写入所有层级
                await self._l1_cache.set(full_key, value, ttl=ttl)
                if self._l2_cache:
                    await self._l2_cache.set(full_key, value, ttl=ttl)

            elif strategy == CacheStrategy.WRITE_BACK:
                # 只写L1，异步写L2
                await self._l1_cache.set(full_key, value, ttl=ttl)
                if self._l2_cache:
                    # 使用后台任务而不是create_task来避免未等待的协程警告
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.call_soon(
                                lambda: asyncio.create_task(
                                    self._l2_cache.set(full_key, value, ttl=ttl)
                                )
                            )
                        else:
                            # 如果事件循环未运行，直接等待
                            await self._l2_cache.set(full_key, value, ttl=ttl)
                    except RuntimeError:
                        # 事件循环不可用，回退到同步写入
                        await self._l2_cache.set(full_key, value, ttl=ttl)

            else:  # WRITE_AROUND
                # 不写缓存
                pass

            await self._update_stats(set_op=True)

            # 记录指标
            if self._metrics_collector:
                self._metrics_collector.record_set(namespace)
                duration = time.time() - start_time
                self._metrics_collector.record_latency(duration, "set")

        except Exception as e:
            logger.error(f"缓存设置失败: {e}")
            if self._metrics_collector:
                self._metrics_collector.record_error(CacheLevel.L1, "set_failed")
            raise

    async def set_many(
        self,
        mapping: Dict[str, Any],
        namespace: str = "",
        ttl: Optional[int] = None,
    ) -> None:
        """批量设置缓存值

        Args:
            mapping: 键值对字典
            namespace: 命名空间
            ttl: 过期时间（秒）
        """
        tasks = [self.set(key, value, namespace, ttl) for key, value in mapping.items()]
        await asyncio.gather(*tasks)

    async def delete(
        self,
        key: str,
        namespace: str = "",
    ) -> None:
        """删除缓存值

        Args:
            key: 缓存键
            namespace: 命名空间
        """
        full_key = self._make_key(key, namespace)

        await self._l1_cache.delete(full_key)

        if self._l2_cache:
            await self._l2_cache.delete(full_key)

        await self._update_stats(delete_op=True)

    async def delete_many(
        self,
        keys: List[str],
        namespace: str = "",
    ) -> None:
        """批量删除缓存值

        Args:
            keys: 缓存键列表
            namespace: 命名空间
        """
        tasks = [self.delete(key, namespace) for key in keys]
        await asyncio.gather(*tasks)

    async def delete_pattern(self, pattern: str, namespace: str = "") -> None:
        """按模式删除缓存

        Args:
            pattern: 匹配模式
            namespace: 命名空间
        """
        if namespace:
            pattern = f"{self._make_key('', namespace)}{pattern}"
        else:
            pattern = f"{self.config.key_prefix}{pattern}"

        await self._l1_cache.delete_pattern(pattern)

        if self._l2_cache:
            await self._l2_cache.delete_pattern(pattern)

    async def clear(self) -> None:
        """清空所有缓存"""
        await self._l1_cache.clear()

        if self._l2_cache:
            await self._l2_cache.clear()

        logger.info("所有缓存已清空")

    async def exists(self, key: str, namespace: str = "") -> bool:
        """检查键是否存在

        Args:
            key: 缓存键
            namespace: 命名空间

        Returns:
            是否存在
        """
        value = await self.get(key, namespace)
        return value is not None

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        namespace: str = "",
        ttl: Optional[int] = None,
    ) -> T:
        """获取缓存值或通过工厂函数创建

        Args:
            key: 缓存键
            factory: 异步工厂函数
            namespace: 命名空间
            ttl: 过期时间

        Returns:
            缓存值或工厂结果
        """
        value = await self.get(key, namespace)
        if value is not None:
            return value

        # 调用工厂函数
        value = await factory()
        await self.set(key, value, namespace, ttl)

        return value

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计

        Returns:
            统计信息
        """
        stats = {
            "enabled": self.is_enabled(),
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "hit_rate": round(self._stats.hit_rate, 4),
            "l1_hits": self._stats.l1_hits,
            "l2_hits": self._stats.l2_hits,
            "l1_hit_rate": round(self._stats.l1_hit_rate, 4),
            "l2_hit_rate": round(self._stats.l2_hit_rate, 4),
            "sets": self._stats.sets,
            "deletes": self._stats.deletes,
            "errors": self._stats.errors,
            "l1_size": self._l1_cache.size,
            "l2_available": self._l2_cache is not None,
            "strategy": self.config.strategy.value,
        }

        # 添加缓存指标收集器的统计
        if self._metrics_collector:
            stats["metrics_collector"] = self._metrics_collector.get_stats()

        return stats

    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats = CacheStats()

    async def warm_up(
        self,
        data: Dict[str, Any],
        namespace: str = "",
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """缓存预热

        Args:
            data: 预热数据
            namespace: 命名空间
            batch_size: 批大小

        Returns:
            预热统计
        """
        if not self.config.warm_up_enabled:
            logger.info("缓存预热已禁用")
            return {"skipped": True, "reason": "disabled"}

        batch_size = batch_size or self.config.warm_up_batch_size

        logger.info(f"开始缓存预热，数据量: {len(data)}, 批大小: {batch_size}")

        stats = {
            "total": len(data),
            "success": 0,
            "failed": 0,
            "start_time": time.time(),
        }

        # 分批预热
        for i in range(0, len(data), batch_size):
            batch = dict(list(data.items())[i : i + batch_size])

            for key, value in batch.items():
                try:
                    await self.set(key, value, namespace=namespace)
                    stats["success"] += 1
                except Exception as e:
                    logger.warning(f"预热失败 [{key}]: {e}")
                    stats["failed"] += 1

            logger.info(f"预热进度: {min(i + batch_size, len(data))}/{len(data)}")

        stats["duration"] = time.time() - stats["start_time"]
        stats["skipped"] = False

        logger.info(
            f"缓存预热完成: 成功={stats['success']}, 失败={stats['failed']}, "
            f"耗时={stats['duration']:.2f}秒"
        )

        return stats

    async def warm_up_from_generator(
        self,
        generator: Callable[[], Awaitable[Dict[str, Any]]],
        namespace: str = "",
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """从生成器预热缓存

        Args:
            generator: 异步数据生成函数
            namespace: 命名空间
            batch_size: 批大小

        Returns:
            预热统计
        """
        data = await generator()
        return await self.warm_up(data, namespace, batch_size)

    async def get_hot_keys(self, threshold: Optional[int] = None) -> List[str]:
        """获取热键列表

        Args:
            threshold: 访问次数阈值

        Returns:
            热键列表
        """
        threshold = threshold or self._hot_keys_threshold

        async with self._hot_keys_lock:
            return [key for key, count in self._hot_keys.items() if count >= threshold]

    def reset_hot_keys(self) -> None:
        """重置热键追踪"""
        self._hot_keys.clear()

    async def health_check(self) -> Dict[str, Any]:
        """健康检查

        Returns:
            健康状态
        """
        health = {
            "status": "healthy",
            "l1": "ok",
            "l2": "disabled",
        }

        # 检查L1
        try:
            await self._l1_cache.set("__health_check__", "ok", ttl=10)
            value = await self._l1_cache.get("__health_check__")
            if value != "ok":
                health["l1"] = "error"
                health["status"] = "degraded"
        except Exception as e:
            health["l1"] = f"error: {e}"
            health["status"] = "unhealthy"

        # 检查L2
        if self._l2_cache:
            try:
                is_healthy = await self._l2_cache.health_check()
                health["l2"] = "ok" if is_healthy else "error"
                if not is_healthy:
                    health["status"] = "degraded" if health["status"] == "healthy" else "unhealthy"
            except Exception as e:
                health["l2"] = f"error: {e}"
                health["status"] = "unhealthy"

        return health

    async def close(self) -> None:
        """关闭缓存管理器"""
        if self._l2_cache:
            await self._l2_cache.close()
        logger.info("缓存管理器已关闭")


# 全局缓存管理器实例
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager(
    config: Optional[CacheConfig] = None,
    redis_url: Optional[str] = None,
) -> CacheManager:
    """获取全局缓存管理器

    Args:
        config: 缓存配置
        redis_url: Redis连接URL

    Returns:
        缓存管理器实例
    """
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager(config, redis_url)
    return _global_cache_manager


async def setup_cache(
    redis_url: Optional[str] = None,
    redis_config: Optional[RedisConfig] = None,
    config: Optional[CacheConfig] = None,
) -> CacheManager:
    """设置并初始化缓存

    Args:
        redis_url: Redis连接URL
        redis_config: Redis配置
        config: 缓存配置

    Returns:
        初始化后的缓存管理器
    """
    cache_config = config or CacheConfig()
    manager = get_cache_manager(cache_config, redis_url)

    # 如果提供了Redis配置，创建Redis缓存
    if redis_config and manager._l2_cache is None:
        try:
            manager._l2_cache = RedisCache(config=redis_config)
            logger.info("Redis缓存已启用")
        except Exception as e:
            logger.warning(f"Redis缓存初始化失败: {e}")

    # 执行健康检查
    health = await manager.health_check()
    logger.info(f"缓存管理器初始化完成，健康状态: {health['status']}")

    return manager


def cached(
    cache_manager: Optional[CacheManager] = None,
    namespace: str = "",
    ttl: Optional[int] = None,
):
    """缓存装饰器（简单版本）

    建议使用 decorators.py 中的装饰器

    Args:
        cache_manager: 缓存管理器
        namespace: 命名空间
        ttl: 过期时间

    Returns:
        装饰器函数
    """

    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # 获取缓存管理器
            cm = cache_manager or get_cache_manager()

            # 生成缓存键
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # 尝试获取缓存
            cached_value = await cm.get(cache_key, namespace)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 设置缓存
            await cm.set(cache_key, result, namespace=namespace, ttl=ttl)

            return result

        return wrapper

    return decorator
