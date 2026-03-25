# -*- coding: utf-8 -*-
"""
Rate Limiting Middleware
速率限制中间件

Implements per-IP and per-user rate limiting using Redis as a backend.
Supports sliding window, fixed window, and token bucket algorithms.
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers

from .tcm_exceptions import RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Default limits
    default_requests_per_minute: int = 60
    default_requests_per_hour: int = 1000

    # Per-IP limits
    ip_requests_per_minute: int = 30
    ip_requests_per_hour: int = 500

    # Per-user limits (authenticated users)
    user_requests_per_minute: int = 60
    user_requests_per_hour: int = 2000

    # Admin limits (higher for admin users)
    admin_requests_per_minute: int = 120
    admin_requests_per_hour: int = 5000

    # Token bucket settings
    burst_size: int = 10  # Allow bursts up to this size
    refill_rate: float = 1.0  # Tokens per second

    # Redis settings
    redis_prefix: str = "ratelimit"
    redis_ttl: int = 3600  # 1 hour

    # Enable/disable features
    enable_ip_limiting: bool = True
    enable_user_limiting: bool = True
    enable_endpoint_limits: bool = True

    # Specific endpoint limits (endpoint -> requests_per_minute)
    endpoint_limits: Dict[str, int] = field(
        default_factory=lambda: {
            "/api/auth/login": 5,
            "/api/auth/register": 3,
            "/api/documents/upload": 10,
            "/api/search": 30,
        }
    )


class RateLimiterBackend:
    """
    Abstract base class for rate limiter storage backends.
    """

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a request is allowed under the rate limit.

        Args:
            key: Unique identifier for the rate limit bucket
            limit: Maximum requests allowed in the window
            window: Time window in seconds
            current_time: Current timestamp (for testing)

        Returns:
            Tuple of (is_allowed, info_dict)
        """
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiterBackend):
    """
    In-memory rate limiter using sliding window algorithm.

    Uses a deque to track request timestamps within the window.
    Suitable for single-instance deployments or development.
    """

    def __init__(self):
        self._windows: Dict[str, deque] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit using sliding window algorithm.

        The sliding window provides smooth rate limiting by tracking
        exact timestamps of requests within the window.
        """
        now = current_time or time.time()

        async with self._lock:
            if key not in self._windows:
                self._windows[key] = deque()

            window_queue = self._windows[key]

            # Remove timestamps outside the window
            cutoff_time = now - window
            while window_queue and window_queue[0] < cutoff_time:
                window_queue.popleft()

            # Check if limit is exceeded
            request_count = len(window_queue)
            is_allowed = request_count < limit

            if is_allowed:
                window_queue.append(now)

            # Calculate when the oldest request will expire
            reset_time = None
            if window_queue:
                reset_time = window_queue[0] + window

            # Cleanup if queue is empty
            if not window_queue and key in self._windows:
                del self._windows[key]

            return is_allowed, {
                "limit": limit,
                "remaining": max(
                    0, limit - request_count - (1 if not is_allowed else 0)
                ),
                "reset": reset_time,
                "window": window,
            }


class TokenBucketRateLimiter(RateLimiterBackend):
    """
    Token bucket rate limiter implementation.

    The token bucket allows for bursts while maintaining a long-term rate.
    """

    def __init__(self):
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: Optional[float] = None,
        refill_rate: Optional[float] = None,
        burst_size: Optional[int] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit using token bucket algorithm.

        Tokens are added at a constant rate (refill_rate) up to burst_size.
        Each request consumes one token.
        """
        now = current_time or time.time()
        refill = refill_rate or (limit / window)
        burst = burst_size or min(limit, 10)

        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = {
                    "tokens": burst,
                    "last_update": now,
                    "burst": burst,
                    "refill_rate": refill,
                }

            bucket = self._buckets[key]

            # Calculate tokens to add based on time elapsed
            time_passed = now - bucket["last_update"]
            tokens_to_add = time_passed * bucket["refill_rate"]

            # Update tokens, capped at burst size
            bucket["tokens"] = min(burst, bucket["tokens"] + tokens_to_add)
            bucket["last_update"] = now

            # Check if we have enough tokens
            is_allowed = bucket["tokens"] >= 1

            if is_allowed:
                bucket["tokens"] -= 1

            # Calculate when bucket will be full
            tokens_needed = bucket["burst"] - bucket["tokens"]
            time_to_full = (
                tokens_needed / bucket["refill_rate"] if tokens_needed > 0 else 0
            )

            return is_allowed, {
                "limit": int(burst),
                "remaining": int(bucket["tokens"]) if bucket["tokens"] >= 0 else 0,
                "reset": now + time_to_full,
                "window": window,
                "refill_rate": bucket["refill_rate"],
            }


class RedisRateLimiter(RateLimiterBackend):
    """
    Redis-based rate limiter using sliding window.

    Uses Redis sorted sets to track request timestamps.
    Suitable for distributed deployments.
    """

    def __init__(self, redis_client):
        """
        Initialize Redis rate limiter.

        Args:
            redis_client: Redis client instance (should support async operations)
        """
        self.redis = redis_client

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit using Redis sorted sets (sliding window).
        """
        now = current_time or time.time()
        cutoff_time = now - window

        try:
            # Remove old entries and count current ones
            pipe = self.redis.pipeline(transaction=True)
            pipe.zremrangebyscore(key, 0, cutoff_time)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window + 1)
            results = await pipe.execute()

            request_count = results[2] - 1  # Exclude the one we just added
            is_allowed = request_count < limit

            # Get the oldest timestamp for reset calculation
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            reset_time = now + window
            if oldest:
                reset_time = oldest[0][1] + window

            return is_allowed, {
                "limit": limit,
                "remaining": max(
                    0, limit - request_count - (1 if not is_allowed else 0)
                ),
                "reset": reset_time,
                "window": window,
            }

        except Exception as e:
            logger.error(f"Redis rate limiter error: {e}")
            # Fail open - allow request if Redis is down
            return True, {
                "limit": limit,
                "remaining": limit,
                "reset": now + window,
                "window": window,
                "error": str(e),
            }


class RateLimiter:
    """
    Rate limiter that supports multiple algorithms and backends.
    """

    def __init__(
        self,
        backend: RateLimiterBackend,
        config: Optional[RateLimitConfig] = None,
    ):
        self.backend = backend
        self.config = config or RateLimitConfig()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"

    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request state (set by auth middleware)."""
        if hasattr(request.state, "user_id"):
            return request.state.user_id
        if hasattr(request.state, "user") and request.state.user:
            return str(getattr(request.state.user, "id", None))
        return None

    def _get_endpoint_limit(self, path: str) -> Optional[int]:
        """Get rate limit for specific endpoint."""
        # Check for exact match first
        if path in self.config.endpoint_limits:
            return self.config.endpoint_limits[path]

        # Check for prefix match
        for endpoint, limit in self.config.endpoint_limits.items():
            if path.startswith(endpoint):
                return limit

        return None

    def _is_admin_user(self, request: Request) -> bool:
        """Check if the current user is an admin."""
        if hasattr(request.state, "user"):
            user = request.state.user
            if hasattr(user, "role"):
                return user.role in ("admin", "superuser")
        return False

    async def check_rate_limit(
        self,
        request: Request,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if the request should be rate limited.

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (is_allowed, info_dict)
        """
        info = {}
        is_admin = self._is_admin_user(request)
        user_id = self._get_user_id(request)
        client_ip = self._get_client_ip(request)
        path = request.url.path

        # Determine which limits to apply
        checks = []

        # Per-IP limiting
        if self.config.enable_ip_limiting and client_ip != "unknown":
            ip_key = f"ip:{client_ip}"
            if is_admin:
                checks.append((ip_key, self.config.admin_requests_per_minute, 60))
            else:
                checks.append((ip_key, self.config.ip_requests_per_minute, 60))

        # Per-user limiting (for authenticated users)
        if self.config.enable_user_limiting and user_id:
            user_key = f"user:{user_id}"
            if is_admin:
                checks.append((user_key, self.config.admin_requests_per_minute, 60))
            else:
                checks.append((user_key, self.config.user_requests_per_minute, 60))

        # Endpoint-specific limiting
        if self.config.enable_endpoint_limits:
            endpoint_limit = self._get_endpoint_limit(path)
            if endpoint_limit:
                endpoint_key = f"endpoint:{path}"
                if user_id:
                    endpoint_key = f"endpoint:{path}:{user_id}"
                checks.append((endpoint_key, endpoint_limit, 60))

        # Check all limits (most restrictive wins)
        is_allowed = True
        limit_info = None

        for key, limit, window in checks:
            allowed, check_info = await self.backend.is_allowed(key, limit, window)
            if not allowed:
                is_allowed = False
                limit_info = check_info
                break
            elif (
                limit_info is None or check_info["remaining"] < limit_info["remaining"]
            ):
                limit_info = check_info

        if limit_info:
            info.update(limit_info)

        return is_allowed, info


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Automatically rate limits incoming requests based on IP and user.
    Adds rate limit headers to responses.
    """

    def __init__(
        self,
        app,
        rate_limiter: RateLimiter,
        excluded_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.excluded_paths = set(
            excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
        )

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter."""
        path = request.url.path

        # Skip excluded paths
        if path in self.excluded_paths:
            return await call_next(request)

        # Check rate limit
        is_allowed, info = await self.rate_limiter.check_rate_limit(request)

        if not is_allowed:
            # Rate limit exceeded
            retry_after = int(info.get("reset", time.time() + 60) - time.time())
            retry_after = max(1, retry_after)

            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "limit": info.get("limit"),
                    "window": info.get("window"),
                    "retry_after": retry_after,
                },
            )
            response.headers["X-RateLimit-Limit"] = str(info.get("limit", ""))
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(
                int(info.get("reset", time.time()))
            )
            response.headers["Retry-After"] = str(retry_after)
            return response

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        if info:
            response.headers["X-RateLimit-Limit"] = str(info.get("limit", ""))
            response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", ""))
            response.headers["X-RateLimit-Reset"] = str(
                int(info.get("reset", time.time()))
            )

        return response


# Convenience function for creating rate limiter
async def create_rate_limiter(
    redis_client=None,
    config: Optional[RateLimitConfig] = None,
    algorithm: str = "sliding_window",
) -> RateLimiter:
    """
    Create a rate limiter instance.

    Args:
        redis_client: Optional Redis client for distributed rate limiting
        config: Rate limit configuration
        algorithm: Rate limiting algorithm ('sliding_window', 'token_bucket')

    Returns:
        Configured RateLimiter instance
    """
    cfg = config or RateLimitConfig()

    if redis_client:
        backend = RedisRateLimiter(redis_client)
    elif algorithm == "token_bucket":
        backend = TokenBucketRateLimiter()
    else:
        backend = InMemoryRateLimiter()

    return RateLimiter(backend, cfg)


# Decorator for rate limiting individual functions
def rate_limit(
    requests: int,
    window: int,
    key_func: Optional[callable] = None,
    backend: Optional[RateLimiterBackend] = None,
):
    """
    Decorator to rate limit a function.

    Args:
        requests: Number of requests allowed
        window: Time window in seconds
        key_func: Function to extract rate limit key from arguments
        backend: Rate limiter backend (uses in-memory if None)

    Usage:
        @rate_limit(requests=10, window=60)
        async def expensive_operation():
            ...
    """
    if backend is None:
        backend = InMemoryRateLimiter()

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = func.__name__

            is_allowed, info = await backend.is_allowed(key, requests, window)

            if not is_allowed:
                raise RateLimitError(
                    message=f"Rate limit exceeded for {func.__name__}",
                    limit=requests,
                    window=f"{window}s",
                    retry_after=int(
                        info.get("reset", time.time() + window) - time.time()
                    ),
                )

            return (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )

        return wrapper

    return decorator


# FastAPI依赖函数
class RateLimitDependency:
    """
    FastAPI速率限制依赖

    为FastAPI端点提供速率限制功能
    """

    def __init__(
        self,
        requests: int = 60,
        window: int = 60,
        key_prefix: str = "rate_limit",
        redis_client=None,
    ):
        """
        初始化速率限制依赖

        Args:
            requests: 允许的请求数量
            window: 时间窗口（秒）
            key_prefix: 速率限制键前缀
            redis_client: Redis客户端实例
        """
        self.requests = requests
        self.window = window
        self.key_prefix = key_prefix

        if redis_client:
            self.backend = RedisRateLimiter(redis_client)
        else:
            self.backend = InMemoryRateLimiter()

    async def __call__(
        self, request: Request
    ) -> tuple[bool, dict]:
        """
        验证请求速率限制

        Args:
            request: FastAPI请求对象

        Returns:
            (是否允许, 限制信息)

        Raises:
            RateLimitError: 如果超过速率限制
        """
        # 生成速率限制键
        client_ip = self._get_client_ip(request)
        key = f"{self.key_prefix}:{client_ip}:{request.url.path}"

        # 检查是否允许
        is_allowed, info = await self.backend.is_allowed(
            key, self.requests, self.window
        )

        # 添加速率限制响应头
        request.state.rate_limit_info = {
            "limit": info["limit"],
            "remaining": info["remaining"],
            "reset": info["reset"],
            "window": self.window,
        }

        if not is_allowed:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": info["limit"],
                    "window": f"{self.window}s",
                    "retry_after": int(
                        info["reset"] - time.time()
                    ) if info["reset"] > time.time() else 1
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(
                        max(1, int(info["reset"] - time.time()))
                    ),
                }
            )

        return True, info

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端IP地址

        Args:
            request: FastAPI请求对象

        Returns:
            客户端IP地址
        """
        # 尝试从代理头获取真实IP
        forwarded = request.headers.get("X-Forwarded-For")
        real_ip = request.headers.get("X-Real-IP")

        if forwarded:
            # X-Forwarded-For可能包含多个IP，取第一个
            return forwarded.split(",")[0].strip()
        elif real_ip:
            return real_ip.strip()
        else:
            # 回退到直接连接的IP
            return request.client.host if request.client else "unknown"


# 预定义的速率限制依赖
def create_rate_limit_dependency(
    requests: int = 60,
    window: int = 60,
    key_prefix: str = "default",
    redis_client=None,
) -> RateLimitDependency:
    """
    创建速率限制依赖

    Args:
        requests: 允许的请求数量
        window: 时间窗口（秒）
        key_prefix: 速率限制键前缀
        redis_client: Redis客户端实例

    Returns:
        RateLimitDependency实例

    Example:
    -------
    ```python
    from middleware.rate_limiter import create_rate_limit_dependency

    # 创建登录端点速率限制（5次/分钟）
    login_rate_limiter = create_rate_limit_dependency(
        requests=5,
        window=60,
        key_prefix="login"
    )

    @app.post("/api/v1/auth/login")
    async def login(
        credentials: LoginRequest,
        _: bool = Depends(login_rate_limiter)
    ):
        ...
    ```
    """
    return RateLimitDependency(
        requests=requests,
        window=window,
        key_prefix=key_prefix,
        redis_client=redis_client,
    )


__all__ = [
    "RateLimitConfig",
    "RateLimiterBackend",
    "InMemoryRateLimiter",
    "TokenBucketRateLimiter",
    "RedisRateLimiter",
    "RateLimiter",
    "RateLimitMiddleware",
    "create_rate_limiter",
    "rate_limit",
    "RateLimitDependency",
    "create_rate_limit_dependency",
]
