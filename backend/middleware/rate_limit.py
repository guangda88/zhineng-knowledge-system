"""API限流中间件

为FastAPI应用添加请求速率限制保护
"""

import logging
import os
from typing import Optional

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.gateway.rate_limiter import InMemoryRateLimiter, RateLimit

logger = logging.getLogger(__name__)


# 全局限流器实例
rate_limiter: Optional[InMemoryRateLimiter] = None


def get_rate_limiter() -> InMemoryRateLimiter:
    """获取限流器实例（单例模式）"""
    global rate_limiter
    if rate_limiter is None:
        # 从环境变量读取配置
        requests_per_minute = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
        whitelist_ips = (
            os.getenv("RATE_LIMIT_WHITELIST", "").split(",")
            if os.getenv("RATE_LIMIT_WHITELIST")
            else []
        )

        rate_limiter = InMemoryRateLimiter(
            default_limit=RateLimit(requests=requests_per_minute, window=60),
            whitelist=[ip.strip() for ip in whitelist_ips if ip.strip()],
        )
        logger.info(f"初始化限流器: {requests_per_minute} 请求/分钟, 白名单: {whitelist_ips}")
    return rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API限流中间件

    基于IP地址的请求速率限制。
    仅在请求来自可信代理时才读取 X-Forwarded-For / X-Real-IP 头，
    防止攻击者伪造头绕过限流。
    """

    _trusted_proxies: set = set()

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        trusted = os.getenv("TRUSTED_PROXIES", "")
        if trusted:
            self._trusted_proxies = {ip.strip() for ip in trusted.split(",") if ip.strip()}

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求并应用限流"""
        client_ip = self._get_client_ip(request)

        if request.url.path in ["/health", "/health/", "/metrics"]:
            return await call_next(request)

        limiter = get_rate_limiter()
        allowed, info = await limiter.check(client_ip) if limiter else (True, {})

        if not allowed:
            logger.warning(f"限流触发: IP={client_ip}, 信息={info}")
            limit_info = info.get("limit") or {}
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": info.get("retry_after", 60),
                    "limit": limit_info,
                },
                headers={
                    "Retry-After": str(info.get("retry_after", 60)),
                    "X-RateLimit-Limit": str(limit_info.get("requests", 60) if isinstance(limit_info, dict) else 60),
                    "X-RateLimit-Reset": str(int(info.get("reset_at", 0))),
                },
            )

        response = await call_next(request)

        # 安全地添加限流头信息（处理白名单情况）
        if info:
            limit_info = info.get("limit")
            if isinstance(limit_info, dict):
                response.headers["X-RateLimit-Limit"] = str(limit_info.get("requests", 60))
            else:
                response.headers["X-RateLimit-Limit"] = str(limit_info if limit_info else 60)
            response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP地址

        仅在直接连接 IP 属于可信代理时才读取转发头。
        """
        direct_ip = request.client.host if request.client else None

        if direct_ip and direct_ip in self._trusted_proxies:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()

            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip

        if direct_ip:
            return direct_ip

        return "unknown"
