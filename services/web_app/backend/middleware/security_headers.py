# -*- coding: utf-8 -*-
"""
Security Response Headers Middleware
安全响应头中间件

实现OWASP推荐的安全响应头，增强Web应用安全性
"""

import logging
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class SecurityHeadersConfig:
    """安全响应头配置"""

    # 内容安全策略
    CONTENT_SECURITY_POLICY: str = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self' https://api.openai.com https://*.openai.com; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    # X-Frame-Options防止点击劫持
    X_FRAME_OPTIONS: str = "DENY"

    # X-Content-Type-Options防止MIME类型嗅探
    X_CONTENT_TYPE_OPTIONS: str = "nosniff"

    # X-XSS-Protection
    X_XSS_PROTECTION: str = "1; mode=block"

    # Referrer-Policy控制Referrer信息泄露
    REFERRER_POLICY: str = "strict-origin-when-cross-origin"

    # Permissions-Policy（原Feature-Policy）
    PERMISSIONS_POLICY: str = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=(), "
        "ambient-light-sensor=()"
    )

    # Strict-Transport-Security（仅HTTPS）
    # 注意：在开发环境（HTTP）中不启用此头
    STRICT_TRANSPORT_SECURITY: Optional[str] = None
    # 生产环境应该是：STRICT_TRANSPORT_SECURITY = "max-age=31536000; includeSubDomains; preload"

    # Cross-Origin-Opener-Policy
    CROSS_ORIGIN_OPENER_POLICY: str = "same-origin"

    # Cross-Origin-Embedder-Policy
    CROSS_ORIGIN_EMBEDDER_POLICY: str = "require-corp"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全响应头中间件

    为所有响应添加OWASP推荐的安全响应头。

    Features:
    - CSP (Content Security Policy) - 防止XSS
    - X-Frame-Options - 防止点击劫持
    - X-Content-Type-Options - 防止MIME嗅探
    - X-XSS-Protection - 浏览器XSS过滤
    - Referrer-Policy - 控制Referrer信息
    - Permissions-Policy - 控制敏感API访问
    - HSTS (HTTPS only) - 强制HTTPS
    """

    def __init__(
        self,
        app: ASGIApp,
        config: Optional[SecurityHeadersConfig] = None,
        enable_hsts: bool = False,
    ):
        """
        初始化安全响应头中间件

        Args:
            app: ASGI应用
            config: 安全头配置，默认使用SecurityHeadersConfig
            enable_hsts: 是否启用HSTS（仅HTTPS环境）
        """
        super().__init__(app)
        self.config = config or SecurityHeadersConfig()
        self.enable_hsts = enable_hsts

        logger.info("Security Headers Middleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求并添加安全响应头

        Args:
            request: FastAPI请求
            call_next: 下一个中间件/处理器

        Returns:
            添加了安全响应头的FastAPI响应
        """
        response = await call_next(request)

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.config.CONTENT_SECURITY_POLICY

        # X-Frame-Options
        response.headers["X-Frame-Options"] = self.config.X_FRAME_OPTIONS

        # X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = self.config.X_CONTENT_TYPE_OPTIONS

        # X-XSS-Protection
        response.headers["X-XSS-Protection"] = self.config.X_XSS_PROTECTION

        # Referrer-Policy
        response.headers["Referrer-Policy"] = self.config.REFERRER_POLICY

        # Permissions-Policy
        response.headers["Permissions-Policy"] = self.config.PERMISSIONS_POLICY

        # Cross-Origin-Opener-Policy
        response.headers["Cross-Origin-Opener-Policy"] = self.config.CROSS_ORIGIN_OPENER_POLICY

        # Cross-Origin-Embedder-Policy
        response.headers["Cross-Origin-Embedder-Policy"] = self.config.CROSS_ORIGIN_EMBEDDER_POLICY

        # Strict-Transport-Security（仅HTTPS环境）
        if self.enable_hsts and self.config.STRICT_TRANSPORT_SECURITY:
            response.headers["Strict-Transport-Security"] = self.config.STRICT_TRANSPORT_SECURITY
            logger.debug("HSTS header added")

        # Cache-Control for sensitive endpoints
        if request.url.path.startswith("/api/v1/auth"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response


def create_security_headers_middleware(
    config: Optional[SecurityHeadersConfig] = None,
    enable_hsts: bool = False,
) -> SecurityHeadersMiddleware:
    """
    创建安全响应头中间件

    Args:
        config: 安全头配置
        enable_hsts: 是否启用HSTS

    Returns:
        SecurityHeadersMiddleware实例

    Example:
    -------
    ```python
    from middleware.security_headers import create_security_headers_middleware

    # 开发环境（HTTP）
    app.add_middleware(create_security_headers_middleware, enable_hsts=False)

    # 生产环境（HTTPS）
    app.add_middleware(create_security_headers_middleware, enable_hsts=True)
    ```
    """

    def middleware_factory(app: ASGIApp) -> SecurityHeadersMiddleware:
        return SecurityHeadersMiddleware(app=app, config=config, enable_hsts=enable_hsts)

    return middleware_factory


__all__ = [
    "SecurityHeadersMiddleware",
    "SecurityHeadersConfig",
    "create_security_headers_middleware",
]
