"""速率限制器

实现API请求速率限制
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 常量配置
DEFAULT_REQUEST_LIMIT = 100  # 默认请求数量
DEFAULT_WINDOW_SECONDS = 60  # 默认时间窗口（秒）
DEFAULT_BURST_MULTIPLIER = 2.0  # 默认突发流量倍数


@dataclass
class RateLimit:
    """速率限制配置"""

    requests: int  # 请求数量
    window: int  # 时间窗口（秒）

    def to_dict(self) -> Dict:
        return {
            "requests": self.requests,
            "window": self.window,
            "rate": f"{self.requests}/{self.window}s",
        }


class RateLimiter:
    """速率限制器基类"""

    def __init__(self, default_limit: Optional[RateLimit] = None, whitelist: Optional[list] = None):
        """初始化速率限制器

        Args:
            default_limit: 默认限制配置
            whitelist: 白名单IP列表
        """
        self.default_limit = default_limit or RateLimit(
            requests=DEFAULT_REQUEST_LIMIT, window=DEFAULT_WINDOW_SECONDS
        )
        self.whitelist = whitelist or []
        self._limits: Dict[str, RateLimit] = {}

    def set_limit(self, key: str, limit: RateLimit) -> None:
        """设置特定key的限制

        Args:
            key: 限制键（如IP地址）
            limit: 限制配置
        """
        self._limits[key] = limit

    def is_whitelisted(self, key: str) -> bool:
        """检查是否在白名单中

        Args:
            key: 限制键

        Returns:
            是否在白名单
        """
        return key in self.whitelist

    async def check(self, key: str) -> tuple[bool, Dict]:
        """检查是否允许请求

        Args:
            key: 限制键（如IP地址）

        Returns:
            (是否允许, 限制信息)
        """
        raise NotImplementedError

    async def reset(self, key: str) -> None:
        """重置限制计数

        Args:
            key: 限制键
        """
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    """内存速率限制器

    使用滑动窗口算法实现
    """

    def __init__(self, default_limit: Optional[RateLimit] = None, whitelist: Optional[list] = None):
        super().__init__(default_limit, whitelist)
        # {key: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, Dict]:
        """检查是否允许请求

        Args:
            key: 限制键

        Returns:
            (是否允许, 限制信息)
        """
        # 白名单检查
        if self.is_whitelisted(key):
            return True, {"allowed": True, "whitelisted": True, "limit": None}

        limit = self._limits.get(key, self.default_limit)
        current_time = time.time()

        async with self._lock:
            # 获取该key的请求记录
            requests = self._requests[key]

            # 移除时间窗口外的记录
            window_start = current_time - limit.window
            self._requests[key] = [(ts, count) for ts, count in requests if ts > window_start]

            # 计算当前窗口内的请求数
            total_requests = sum(count for _, count in self._requests[key])

            if total_requests >= limit.requests:
                # 计算重置时间
                oldest_request = min(self._requests[key], key=lambda x: x[0])
                reset_time = oldest_request[0] + limit.window

                return False, {
                    "allowed": False,
                    "limit": limit.to_dict(),
                    "current": total_requests,
                    "reset_at": reset_time,
                    "retry_after": int(reset_time - current_time),
                }

            # 记录本次请求
            self._requests[key].append((current_time, 1))

            return True, {
                "allowed": True,
                "limit": limit.to_dict(),
                "current": total_requests + 1,
                "remaining": limit.requests - total_requests - 1,
            }

    async def reset(self, key: str) -> None:
        """重置限制计数

        Args:
            key: 限制键
        """
        async with self._lock:
            if key in self._requests:
                del self._requests[key]

    def get_stats(self) -> Dict:
        """获取限制器统计"""
        return {
            "total_keys": len(self._requests),
            "whitelisted_keys": len(self.whitelist),
            "custom_limits": len(self._limits),
        }


class TokenBucketRateLimiter(RateLimiter):
    """令牌桶速率限制器

    使用令牌桶算法实现，支持突发流量
    """

    def __init__(
        self,
        default_limit: Optional[RateLimit] = None,
        whitelist: Optional[list] = None,
        burst_multiplier: float = DEFAULT_BURST_MULTIPLIER,
    ):
        super().__init__(default_limit, whitelist)
        self.burst_multiplier = burst_multiplier
        # {key: (tokens, last_update)}
        self._buckets: Dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    def _refill_rate(self, limit: RateLimit) -> float:
        """计算令牌补充速率

        Args:
            limit: 限制配置

        Returns:
            每秒补充的令牌数
        """
        return limit.requests / limit.window

    async def check(self, key: str) -> tuple[bool, Dict]:
        """检查是否允许请求"""
        if self.is_whitelisted(key):
            return True, {"allowed": True, "whitelisted": True}

        limit = self._limits.get(key, self.default_limit)
        current_time = time.time()

        async with self._lock:
            if key not in self._buckets:
                # 初始化桶，允许突发
                self._buckets[key] = (limit.requests * self.burst_multiplier, current_time)

            tokens, last_update = self._buckets[key]

            # 计算补充的令牌
            refill_rate = self._refill_rate(limit)
            elapsed = current_time - last_update
            tokens = min(tokens + elapsed * refill_rate, limit.requests * self.burst_multiplier)

            if tokens < 1:
                # 令牌不足
                refill_time = (1 - tokens) / refill_rate
                return False, {
                    "allowed": False,
                    "limit": limit.to_dict(),
                    "current": int(tokens),
                    "refill_in": refill_time,
                }

            # 消耗一个令牌
            tokens -= 1
            self._buckets[key] = (tokens, current_time)

            return True, {"allowed": True, "limit": limit.to_dict(), "current": int(tokens)}

    async def reset(self, key: str) -> None:
        """重置令牌桶"""
        async with self._lock:
            if key in self._buckets:
                del self._buckets[key]
