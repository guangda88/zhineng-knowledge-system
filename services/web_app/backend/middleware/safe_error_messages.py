# -*- coding: utf-8 -*-
"""
安全错误消息处理中间件
Security Error Message Handling Middleware

优化错误消息以防止信息泄露：
- 不暴露内部实现细节
- 不显示敏感的系统信息
- 不泄露数据库结构
- 防止通过错误信息进行侦察
"""

import logging
import traceback
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class SafeErrorMessageConfig:
    """安全错误消息配置"""

    # 通用错误消息（不泄露信息）
    GENERIC_ERROR = "An error occurred while processing your request"
    AUTH_ERROR = "Authentication failed"
    AUTHORIZATION_ERROR = "You don't have permission to perform this action"
    VALIDATION_ERROR = "Invalid input data"
    NOT_FOUND_ERROR = "The requested resource was not found"
    RATE_LIMIT_ERROR = "Too many requests. Please try again later"
    SERVER_ERROR = "Internal server error"

    # 是否在开发环境显示详细错误
    DEBUG_MODE: bool = False

    # 敏感错误模式（不应在日志中显示）
    SENSITIVE_PATTERNS = [
        r"password",
        r"token",
        r"secret",
        r"key",
        r"credential",
        r"auth",
        r"connection.*string",
    ]


class SafeErrorMessageMiddleware(BaseHTTPMiddleware):
    """
    安全错误消息中间件

    拦截所有异常并返回安全的错误消息，防止信息泄露。

    Features:
    - 通用错误消息（生产环境）
    - 详细错误消息（开发环境，可配置）
    - 敏感信息过滤
    - 结构化错误响应
    - 安全日志记录
    """

    def __init__(
        self,
        app: ASGIApp,
        config: Optional[SafeErrorMessageConfig] = None,
        debug: bool = False,
    ):
        """
        初始化安全错误消息中间件

        Args:
            app: ASGI应用
            config: 错误消息配置
            debug: 是否显示详细错误信息（仅开发环境）
        """
        super().__init__(app)
        self.config = config or SafeErrorMessageConfig()
        self.config.DEBUG_MODE = debug

        logger.info(
            f"Safe Error Message Middleware initialized (debug={debug})"
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        处理请求并捕获异常

        Args:
            request: FastAPI请求
            call_next: 下一个中间件/处理器

        Returns:
            安全的错误响应或正常响应
        """
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            # HTTP异常已经处理，只需确保安全
            return self._handle_http_exception(e, request)
        except ValidationError as e:
            # Pydantic验证错误
            return self._handle_validation_error(e, request)
        except Exception as e:
            # 未处理的异常
            return self._handle_unexpected_error(e, request)

    def _handle_http_exception(
        self,
        exception: HTTPException,
        request: Request
    ) -> JSONResponse:
        """
        处理HTTP异常

        Args:
            exception: HTTP异常
            request: 请求对象

        Returns:
            安全的HTTP错误响应
        """
        status_code = exception.status_code
        detail = exception.detail

        # 根据状态码选择安全消息
        if status_code == 401:
            message = self.config.AUTH_ERROR
        elif status_code == 403:
            message = self.config.AUTHORIZATION_ERROR
        elif status_code == 404:
            message = self.config.NOT_FOUND_ERROR
        elif status_code == 429:
            message = self.config.RATE_LIMIT_ERROR
        elif status_code >= 500:
            message = self.config.SERVER_ERROR
        else:
            message = self.config.GENERIC_ERROR

        # 记录安全错误（过滤敏感信息）
        self._log_error(exception, request, message)

        # 开发环境显示详细信息
        if self.config.DEBUG_MODE:
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": message,
                    "detail": detail,
                    "status_code": status_code,
                    "debug": {
                        "path": str(request.url.path),
                        "method": request.method,
                        "exception": str(exception),
                    }
                }
            )
        else:
            # 生产环境使用通用消息
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": message,
                    "status_code": status_code,
                }
            )

    def _handle_validation_error(
        self,
        exception: ValidationError,
        request: Request
    ) -> JSONResponse:
        """
        处理验证错误

        Args:
            exception: 验证错误
            request: 请求对象

        Returns:
            安全的验证错误响应
        """
        # 记录验证错误
        logger.warning(
            f"Validation error for {request.url.path}: "
            f"{len(exception.errors())} errors"
        )

        # 开发环境显示详细验证错误
        if self.config.DEBUG_MODE:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": self.config.VALIDATION_ERROR,
                    "detail": exception.errors(),
                    "status_code": 422,
                }
            )
        else:
            # 生产环境隐藏具体字段错误
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": self.config.VALIDATION_ERROR,
                    "status_code": 422,
                    "hint": "Check your input data and try again"
                }
            )

    def _handle_unexpected_error(
        self,
        exception: Exception,
        request: Request
    ) -> JSONResponse:
        """
        处理未预期的异常

        Args:
            exception: 异常对象
            request: 请求对象

        Returns:
            安全的服务器错误响应
        """
        # 记录完整的错误堆栈（仅日志，不返回给客户端）
        self._log_error(exception, request, self.config.SERVER_ERROR, traceback=True)

        # 开发环境显示堆栈跟踪
        if self.config.DEBUG_MODE:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": self.config.SERVER_ERROR,
                    "status_code": 500,
                    "debug": {
                        "exception_type": type(exception).__name__,
                        "exception_message": str(exception),
                        "path": str(request.url.path),
                        "method": request.method,
                        "traceback": traceback.format_exc(),
                    }
                }
            )
        else:
            # 生产环境返回通用消息
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": self.config.SERVER_ERROR,
                    "status_code": 500,
                }
            )

    def _log_error(
        self,
        exception: Exception,
        request: Request,
        message: str,
        traceback: bool = False
    ):
        """
        记录安全错误（过滤敏感信息）

        Args:
            exception: 异常对象
            request: 请求对象
            message: 安全错误消息
            traceback: 是否包含堆栈跟踪
        """
        # 过滤敏感信息
        safe_message = self._filter_sensitive_info(message)
        exception_type = type(exception).__name__
        exception_message = self._filter_sensitive_info(str(exception))

        # 构建日志记录
        log_data = {
            "exception_type": exception_type,
            "message": safe_message,
            "path": str(request.url.path),
            "method": request.method,
            "status_code": getattr(exception, "status_code", 500),
        }

        # 如果是HTTPException，记录状态码
        if isinstance(exception, HTTPException):
            log_data["http_status"] = exception.status_code

        # 添加异常消息（已过滤）
        if exception_message:
            log_data["exception_message"] = exception_message

        # 根据严重性选择日志级别
        if isinstance(exception, HTTPException) and exception.status_code < 500:
            logger.warning(f"Client error: {log_data}")
        else:
            logger.error(f"Server error: {log_data}", exc_info=traceback)

    def _filter_sensitive_info(self, message: str) -> str:
        """
        过滤敏感信息

        Args:
            message: 原始消息

        Returns:
            过滤后的安全消息
        """
        import re

        filtered_message = message.lower()

        # 替换敏感信息为占位符
        for pattern in self.config.SENSITIVE_PATTERNS:
            filtered_message = re.sub(
                pattern,
                "[REDACTED]",
                filtered_message,
                flags=re.IGNORECASE
            )

        return filtered_message


def create_safe_error_middleware(
    config: Optional[SafeErrorMessageConfig] = None,
    debug: bool = False,
) -> SafeErrorMessageMiddleware:
    """
    创建安全错误消息中间件

    Args:
        config: 错误消息配置
        debug: 是否显示详细错误信息

    Returns:
        SafeErrorMessageMiddleware实例

    Example:
    -------
    ```python
    from middleware.safe_error_messages import create_safe_error_middleware

    # 开发环境
    app.add_middleware(create_safe_error_middleware, debug=True)

    # 生产环境
    app.add_middleware(create_safe_error_middleware, debug=False)
    ```
    """
    def middleware_factory(app: ASGIApp) -> SafeErrorMessageMiddleware:
        return SafeErrorMessageMiddleware(
            app=app,
            config=config,
            debug=debug
        )

    return middleware_factory


__all__ = [
    "SafeErrorMessageMiddleware",
    "SafeErrorMessageConfig",
    "create_safe_error_middleware",
]
