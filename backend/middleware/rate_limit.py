"""API限流中间件

为FastAPI应用添加请求速率限制保护
"""

import logging
import os
from typing import Optional

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from gateway.rate_limiter import InMemoryRateLimiter, RateLimit

logger = logging.getLogger(__name__)


# 全局限流器实例
rate_limiter: Optional[InMemoryRateLimiter] = None


def get_rate_limiter() -> InMemoryRateLimiter:
    """获取限流器实例（单例模式）"""
    global rate_limiter
    if rate_limiter is None:
        # 从环境变量读取配置
        requests_per_minute = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
        whitelist_ips = os.getenv("RATE_LIMIT_WHITELIST", "").split(",") if os.getenv("RATE_LIMIT_WHITELIST") else []

        rate_limiter = InMemoryRateLimiter(
            default_limit=RateLimit(requests=requests_per_minute, window=60),
            whitelist=[ip.strip() for ip in whitelist_ips if ip.strip()]
        )
        logger.info(f"初始化限流器: {requests_per_minute} 请求/分钟, 白名单: {whitelist_ips}")
    return rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API限流中间件

    基于IP地址的请求速率限制
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求并应用限流"""
        # 获取客户端IP（考虑代理情况）
        client_ip = self._get_client_ip(request)

        # 跳过健康检查端点
        if request.url.path in ["/health", "/health/", "/metrics"]:
            return await call_next(request)

        # 检查限流
        limiter = get_rate_limiter()
        allowed, info = await limiter.check(client_ip)

        if not allowed:
            logger.warning(f"限流触发: IP={client_ip}, 信息={info}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": info.get("retry_after", 60),
                    "limit": info.get("limit", {})
                },
                headers={
                    "Retry-After": str(info.get("retry_after", 60)),
                    "X-RateLimit-Limit": str(info.get("limit", {}).get("requests", 60)),
                    "X-RateLimit-Reset": str(int(info.get("reset_at", 0)))
                }
            )

        # 处理请求
        response = await call_next(request)

        # 添加限流响应头
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", {}).get("requests", 60))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP地址

        支持代理/X-Forwarded-For
        """
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 默认使用直接连接的IP
        if request.client:
            return request.client.host

        return "unknown"
