"""中间件配置模块

提供安全相关的中间件配置，包括CORS、安全头、请求日志等。
"""

import logging
import time
from typing import Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_config
from .request_stats import increment_error_count, increment_request_count

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """配置错误"""


def get_allowed_origins() -> list[str]:
    """
    获取允许的跨域来源

    安全策略：
    - 生产环境必须通过环境变量指定
    - 开发环境可使用默认本地地址
    """
    config = get_config()

    # 如果配置了允许的来源，使用配置
    if config.ALLOWED_ORIGINS and "*" not in config.ALLOWED_ORIGINS:
        return config.ALLOWED_ORIGINS

    # 检查环境变量（向后兼容）
    import os
    origins_str = os.getenv("ALLOWED_ORIGINS", "").strip()

    if not origins_str:
        environment = config.ENVIRONMENT.lower()

        if environment in ("production", "prod"):
            logger.error("ALLOWED_ORIGINS 在生产环境必须设置")
            raise ConfigError(
                "安全错误: ALLOWED_ORIGINS 在生产环境必须设置。"
                "请设置为允许的域名列表，如: 'https://example.com,https://api.example.com'"
            )

        # 开发环境默认值
        logger.warning("ALLOWED_ORIGINS 未设置，使用开发环境默认值")
        return [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8001"
        ]

    # 清理并验证每个来源
    origins = []
    for origin in origins_str.split(","):
        origin = origin.strip()
        if origin:
            # 基本验证
            if not (origin.startswith("http://") or origin.startswith("https://")):
                logger.warning(f"无效的来源格式: {origin}，将被忽略")
                continue
            origins.append(origin)

    if not origins:
        raise ConfigError("ALLOWED_ORIGINS 配置无效，未找到有效的来源地址")

    return origins


async def add_security_headers(request: Request, call_next):
    """
    添加安全响应头

    参考: OWASP 安全最佳实践
    """
    config = get_config()
    response = await call_next(request)

    # 防止 MIME 类型嗅探
    response.headers["X-Content-Type-Options"] = "nosniff"

    # 防止点击劫持
    response.headers["X-Frame-Options"] = "DENY"

    # 启用浏览器 XSS 过滤
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # 内容安全策略
    environment = config.ENVIRONMENT.lower()
    if environment in ("production", "prod"):
        # 生产环境: 仅允许同源资源
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        # HSTS: 强制 HTTPS (有效期1年)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    else:
        # 开发环境: 更宽松的策略
        response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline'"

    # Referrer 策略
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    start_time = time.time()
    increment_request_count()

    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        if request.url.path.startswith("/api/"):
            logger.info(
                f"{request.method} {request.url.path} - "
                f"{response.status_code} - {process_time:.3f}s"
            )

        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        increment_error_count()
        logger.error(f"Request error: {str(e)}")
        raise
