"""
分布式速率限制器

使用Redis实现跨进程的全局速率限制，防止API调用过于频繁
"""
import asyncio
import time
import threading
from typing import Optional, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def _get_async_redis(redis_url: str, decode_responses: bool = True):
    """获取异步 Redis 客户端（使用 redis.asyncio）"""
    import redis.asyncio as aioredis
    return aioredis.from_url(redis_url, decode_responses=decode_responses)


def _get_sync_redis(redis_url: str, decode_responses: bool = True):
    """获取同步 Redis 客户端（仅用于同步上下文）"""
    import redis as sync_redis
    return sync_redis.from_url(redis_url, decode_responses=decode_responses)


class DistributedRateLimiter:
    """基于Redis的分布式速率限制器（异步优先）"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_calls: int = 60,  # 时间窗口内最大调用次数
        period: int = 60,  # 时间窗口（秒）
        burst: int = 10  # 突发容量
    ):
        """
        初始化分布式速率限制器

        Args:
            redis_url: Redis连接URL
            max_calls: 时间窗口内最大调用次数
            period: 时间窗口（秒）
            burst: 允许的突发请求数
        """
        self.redis_url = redis_url
        self._async_redis = None
        self._sync_redis = _get_sync_redis(redis_url, decode_responses=True)
        self.max_calls = max_calls
        self.period = period
        self.burst = burst

    async def _get_async_redis(self):
        if self._async_redis is None:
            self._async_redis = _get_async_redis(self.redis_url)
        return self._async_redis

    def acquire(self, key: str, timeout: Optional[float] = None) -> bool:
        """
        获取调用许可（同步版本，仅用于非异步上下文）

        Args:
            key: 速率限制键名（如"api_calls"）
            timeout: 最大等待时间（秒），None表示无限等待

        Returns:
            是否成功获取许可
        """
        import warnings
        warnings.warn(
            "DistributedRateLimiter.acquire() is synchronous and blocks the thread. "
            "Use acquire_async() in async contexts.",
            DeprecationWarning,
            stacklevel=2,
        )
        start_time = time.time()

        while True:
            current_calls = self._sync_redis.get(f"rate_limit:{key}")

            if current_calls is None or int(current_calls) < self.max_calls:
                pipe = self._sync_redis.pipeline()
                pipe.incr(f"rate_limit:{key}")
                pipe.expire(f"rate_limit:{key}", self.period)
                pipe.execute()
                return True

            ttl = self._sync_redis.ttl(f"rate_limit:{key}")
            wait_time = ttl / 1000.0 if ttl > 0 else 1.0

            if timeout is not None and (time.time() - start_time) >= timeout:
                return False

            time.sleep(min(wait_time, 1.0))

    async def acquire_async(self, key: str, timeout: Optional[float] = None) -> bool:
        """异步版本的acquire（推荐在异步上下文中使用）"""
        redis_client = await self._get_async_redis()
        start_time = time.time()

        while True:
            current_calls = await redis_client.get(f"rate_limit:{key}")

            if current_calls is None or int(current_calls) < self.max_calls:
                pipe = redis_client.pipeline()
                await pipe.incr(f"rate_limit:{key}")
                await pipe.expire(f"rate_limit:{key}", self.period)
                await pipe.execute()
                return True

            ttl = await redis_client.ttl(f"rate_limit:{key}")
            wait_time = ttl / 1000.0 if ttl > 0 else 1.0

            if timeout is not None and (time.time() - start_time) >= timeout:
                return False

            await asyncio.sleep(min(wait_time, 1.0))

    def get_usage(self, key: str) -> dict:
        """获取当前使用情况"""
        current_calls = self._sync_redis.get(f"rate_limit:{key}")
        ttl = self._sync_redis.ttl(f"rate_limit:{key}")

        return {
            "current_calls": int(current_calls) if current_calls else 0,
            "max_calls": self.max_calls,
            "remaining_time": ttl,
            "usage_percent": (int(current_calls) / self.max_calls * 100) if current_calls else 0
        }


def rate_limit(
    key: str = "default",
    max_calls: int = 60,
    period: int = 60,
    timeout: Optional[float] = None
):
    """
    速率限制装饰器

    Args:
        key: 速率限制键名
        max_calls: 时间窗口内最大调用次数
        period: 时间窗口（秒）
        timeout: 最大等待时间

    Example:
        @rate_limit(key="api_calls", max_calls=100, period=60, timeout=10)
        def call_api():
            # 你的代码
            pass
    """
    limiter = DistributedRateLimiter(max_calls=max_calls, period=period)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not limiter.acquire(key, timeout=timeout):
                raise Exception(f"Rate limit exceeded for {key}")
            return func(*args, **kwargs)
        return wrapper

    return decorator


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例1: 基本使用
    limiter = DistributedRateLimiter(
        max_calls=100,  # 每分钟最多100次调用
        period=60,
        burst=10
    )

    # 示例2: 装饰器使用
    @rate_limit(key="glm_api", max_calls=60, period=60)
    def call_glm_api(prompt: str):
        # API调用代码
        pass

    # 示例3: 令牌桶（更适合高并发）
    token_limiter = TokenBucketRateLimiter(
        rate=10.0,  # 每秒10个令牌
        capacity=100  # 桶容量100
    )

    # 示例4: 多进程安全
    # 每个进程使用相同的Redis配置
    # 自动实现全局速率限制
