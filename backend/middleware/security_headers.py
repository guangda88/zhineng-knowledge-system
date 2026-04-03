"""安全响应头中间件

添加安全相关的 HTTP 响应头，包括 CSP, HSTS, X-Frame-Options 等。
"""

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全响应头中间件

    添加以下安全响应头:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    - Content-Security-Policy: default-src 'self'
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: geolocation=(), microphone=(), camera=()
    """

    def __init__(self, app, hsts_enabled: bool = True):
        super().__init__(app)
        self.hsts_enabled = hsts_enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求并添加安全响应头"""
        response = await call_next(request)

        # 添加安全响应头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS (仅 HTTPS)
        if self.hsts_enabled and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # CSP (内容安全策略)
        # 基础策略：仅允许同源资源
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # 开发环境需要 unsafe-inline
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]

        # 根据环境调整 CSP
        if getattr(request.app.state, "ENVIRONMENT", "production") == "development":
            # 开发环境：允许调试工具
            csp_directives.append(
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:*"
            )
            csp_directives.append("connect-src 'self' http://localhost:* ws://localhost:*")

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response


# 便捷函数
def add_security_headers(request: Request, call_next):
    """添加安全响应头的替代实现（作为中间件函数）"""

    async def middleware(request: Request, call_next) -> Response:
        security_middleware = SecurityHeadersMiddleware(request.app, hsts_enabled=True)
        return await security_middleware.dispatch(request, call_next)

    return middleware(request, call_next)
