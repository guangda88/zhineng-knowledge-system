"""
中间件管理系统

提供统一的中间件注册、配置和生命周期管理
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class MiddlewareOrder(str, Enum):
    """中间件执行顺序"""

    FIRST = "first"  # 最先执行
    EARLY = "early"  # 早期执行
    NORMAL = "normal"  # 正常执行
    LATE = "late"  # 晚期执行
    LAST = "last"  # 最后执行


@dataclass
class MiddlewareConfig:
    """中间件配置"""

    name: str
    enabled: bool = True
    order: MiddlewareOrder = MiddlewareOrder.NORMAL
    priority: int = 0  # 同级中的优先级，数字越小越优先
    options: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "MiddlewareConfig") -> bool:
        """用于排序"""
        order_priority = {
            MiddlewareOrder.FIRST: 0,
            MiddlewareOrder.EARLY: 1,
            MiddlewareOrder.NORMAL: 2,
            MiddlewareOrder.LATE: 3,
            MiddlewareOrder.LAST: 4,
        }
        if order_priority[self.order] != order_priority[other.order]:
            return order_priority[self.order] < order_priority[other.order]
        return self.priority < other.priority


class ManagedMiddleware(BaseHTTPMiddleware):
    """
    被管理的中间件基类

    提供标准的中间件接口，支持启用/禁用和配置
    """

    def __init__(self, app: ASGIApp, config: MiddlewareConfig):
        super().__init__(app)
        self.config = config
        self.name = config.name
        self.enabled = config.enabled
        self.options = config.options

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        if not self.enabled:
            return await call_next(request)

        return await self.process_request(request, call_next)

    async def process_request(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求的具体逻辑

        Args:
            request: HTTP请求
            call_next: 下一个中间件/路由的调用函数

        Returns:
            HTTP响应
        """
        # 默认实现：直接传递给下一个处理器
        return await call_next(request)


class RequestLoggingMiddleware(ManagedMiddleware):
    """
    请求日志中间件

    记录所有HTTP请求的详细信息
    """

    async def process_request(self, request: Request, call_next: Callable) -> Response:
        """记录请求信息"""
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # 添加请求ID到请求状态
        request.state.request_id = request_id

        # 记录请求开始
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"(ID: {request_id}, Client: {request.client.host if request.client else 'unknown'})"
        )

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求完成
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"(ID: {request_id}, Status: {response.status_code}, "
                f"Time: {process_time:.3f}s)"
            )

            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            return response

        except Exception as e:
            # 记录请求异常
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"(ID: {request_id}, Error: {str(e)}, Time: {process_time:.3f}s)"
            )
            raise


class ErrorHandlingMiddleware(ManagedMiddleware):
    """
    错误处理中间件

    捕获并处理应用程序中的异常
    """

    async def process_request(self, request: Request, call_next: Callable) -> Response:
        """处理请求并捕获异常"""
        try:
            return await call_next(request)

        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)

            # 根据异常类型返回不同的响应
            from fastapi import HTTPException
            from fastapi.responses import JSONResponse

            if isinstance(e, HTTPException):
                return JSONResponse(
                    status_code=e.status_code,
                    content={
                        "error": e.detail,
                        "status": "error",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            else:
                # 对于未知异常，返回通用错误响应
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Internal server error",
                        "detail": (
                            str(e) if self.options.get("debug", False) else "An error occurred"
                        ),
                        "status": "error",
                        "timestamp": datetime.now().isoformat(),
                    },
                )


class RateLimitMiddleware(ManagedMiddleware):
    """
    限流中间件

    基于IP地址的请求频率限制
    """

    def __init__(self, app: ASGIApp, config: MiddlewareConfig):
        super().__init__(app, config)
        self.request_counts: Dict[str, List[float]] = {}
        self.max_requests = self.options.get("max_requests", 100)
        self.window_seconds = self.options.get("window_seconds", 60)

    async def process_request(self, request: Request, call_next: Callable) -> Response:
        """检查并应用限流"""
        # 获取客户端IP
        client_ip = self._get_client_ip(request)

        # 清理过期的请求记录
        current_time = time.time()
        self._cleanup_old_requests(current_time)

        # 检查是否超过限流
        if self._is_rate_limited(client_ip, current_time):
            from fastapi.responses import JSONResponse

            logger.warning(f"Rate limit exceeded for IP: {client_ip}")

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many requests",
                    "detail": f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds} seconds.",
                    "status": "error",
                    "timestamp": datetime.now().isoformat(),
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(current_time + self.window_seconds)),
                },
            )

        # 记录本次请求
        self._record_request(client_ip, current_time)

        # 处理请求
        response = await call_next(request)

        # 添加限流信息到响应头
        remaining = self.max_requests - len(self.request_counts.get(client_ip, []))
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window_seconds))

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 使用直接连接的IP
        if request.client:
            return request.client.host

        return "unknown"

    def _cleanup_old_requests(self, current_time: float) -> None:
        """清理过期的请求记录"""
        cutoff_time = current_time - self.window_seconds

        for ip in list(self.request_counts.keys()):
            # 保留在时间窗口内的请求
            self.request_counts[ip] = [
                req_time for req_time in self.request_counts[ip] if req_time > cutoff_time
            ]

            # 如果没有请求记录，删除该IP
            if not self.request_counts[ip]:
                del self.request_counts[ip]

    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """检查是否超过限流"""
        request_times = self.request_counts.get(client_ip, [])

        # 计算时间窗口内的请求数
        cutoff_time = current_time - self.window_seconds
        recent_requests = [t for t in request_times if t > cutoff_time]

        return len(recent_requests) >= self.max_requests

    def _record_request(self, client_ip: str, current_time: float) -> None:
        """记录请求"""
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []

        self.request_counts[client_ip].append(current_time)


class SecurityHeadersMiddleware(ManagedMiddleware):
    """
    安全头中间件

    添加安全相关的HTTP响应头
    """

    async def process_request(self, request: Request, call_next: Callable) -> Response:
        """添加安全头"""
        response = await call_next(request)

        # 添加安全头
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        # 可以通过配置覆盖默认安全头
        custom_headers = self.options.get("security_headers", {})
        security_headers.update(custom_headers)

        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value

        return response


class CORSMiddleware(ManagedMiddleware):
    """
    CORS中间件

    处理跨域资源共享
    """

    async def process_request(self, request: Request, call_next: Callable) -> Response:
        """处理CORS"""
        response = await call_next(request)

        # 获取CORS配置
        allowed_origins = self.options.get("allowed_origins", ["*"])
        allowed_methods = self.options.get(
            "allowed_methods", ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
        allowed_headers = self.options.get("allowed_headers", ["*"])
        allow_credentials = self.options.get("allow_credentials", True)
        max_age = self.options.get("max_age", 3600)

        # 设置CORS头
        origin = request.headers.get("Origin")

        if origin and (allowed_origins == ["*"] or origin in allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = str(allow_credentials).lower()
            response.headers["Access-Control-Allow-Methods"] = ", ".join(allowed_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(allowed_headers)
            response.headers["Access-Control-Max-Age"] = str(max_age)

        return response


class MiddlewareManager:
    """
    中间件管理器

    统一管理所有中间件的注册、排序和生命周期
    """

    def __init__(self):
        """初始化中间件管理器"""
        self.middleware_configs: Dict[str, MiddlewareConfig] = {}
        self.middleware_factories: Dict[str, Callable] = {}
        self._initialized = False

    def register_middleware(
        self, name: str, factory: Callable, config: Optional[MiddlewareConfig] = None
    ) -> None:
        """
        注册中间件

        Args:
            name: 中间件名称
            factory: 中间件工厂函数
            config: 中间件配置
        """
        if config is None:
            config = MiddlewareConfig(name=name)

        self.middleware_configs[name] = config
        self.middleware_factories[name] = factory
        logger.info(f"Registered middleware: {name}")

    def unregister_middleware(self, name: str) -> None:
        """
        注销中间件

        Args:
            name: 中间件名称
        """
        self.middleware_configs.pop(name, None)
        self.middleware_factories.pop(name, None)
        logger.info(f"Unregistered middleware: {name}")

    def enable_middleware(self, name: str) -> None:
        """启用中间件"""
        if name in self.middleware_configs:
            self.middleware_configs[name].enabled = True
            logger.info(f"Enabled middleware: {name}")

    def disable_middleware(self, name: str) -> None:
        """禁用中间件"""
        if name in self.middleware_configs:
            self.middleware_configs[name].enabled = False
            logger.info(f"Disabled middleware: {name}")

    def get_middleware_config(self, name: str) -> Optional[MiddlewareConfig]:
        """获取中间件配置"""
        return self.middleware_configs.get(name)

    def get_sorted_configs(self) -> List[MiddlewareConfig]:
        """获取排序后的中间件配置"""
        enabled_configs = [config for config in self.middleware_configs.values() if config.enabled]
        return sorted(enabled_configs)

    async def apply_to_app(self, app: "FastAPI") -> None:
        """
        将所有中间件应用到FastAPI应用

        Args:
            app: FastAPI应用实例
        """
        if self._initialized:
            logger.warning("Middleware already initialized")
            return

        sorted_configs = self.get_sorted_configs()

        logger.info(f"Applying {len(sorted_configs)} middleware(s) to application")

        # 按顺序应用中间件
        for config in reversed(sorted_configs):  # 反向顺序，因为中间件是按栈顺序执行的
            if config.name in self.middleware_factories:
                factory = self.middleware_factories[config.name]
                middleware = factory(app, config)
                app.add_middleware(middleware.__class__)
                logger.info(f"Applied middleware: {config.name} (order: {config.order.value})")

        self._initialized = True
        logger.info("All middleware applied successfully")


# 全局中间件管理器实例
_global_middleware_manager: Optional[MiddlewareManager] = None


def get_middleware_manager() -> MiddlewareManager:
    """
    获取全局中间件管理器实例

    Returns:
        全局中间件管理器
    """
    global _global_middleware_manager
    if _global_middleware_manager is None:
        _global_middleware_manager = MiddlewareManager()
    return _global_middleware_manager


def reset_middleware_manager() -> None:
    """重置全局中间件管理器（主要用于测试）"""
    global _global_middleware_manager
    _global_middleware_manager = None


def create_default_middlewares() -> None:
    """
    创建默认的中间件配置

    注册系统默认的中间件及其配置
    """
    manager = get_middleware_manager()

    # 请求日志中间件
    manager.register_middleware(
        name="request_logging",
        factory=lambda app, config: RequestLoggingMiddleware(app, config),
        config=MiddlewareConfig(
            name="request_logging", enabled=True, order=MiddlewareOrder.FIRST, priority=1
        ),
    )

    # 错误处理中间件
    manager.register_middleware(
        name="error_handling",
        factory=lambda app, config: ErrorHandlingMiddleware(app, config),
        config=MiddlewareConfig(
            name="error_handling",
            enabled=True,
            order=MiddlewareOrder.EARLY,
            priority=1,
            options={"debug": False},
        ),
    )

    # 限流中间件
    manager.register_middleware(
        name="rate_limit",
        factory=lambda app, config: RateLimitMiddleware(app, config),
        config=MiddlewareConfig(
            name="rate_limit",
            enabled=True,
            order=MiddlewareOrder.NORMAL,
            priority=1,
            options={"max_requests": 100, "window_seconds": 60},
        ),
    )

    # 安全头中间件
    manager.register_middleware(
        name="security_headers",
        factory=lambda app, config: SecurityHeadersMiddleware(app, config),
        config=MiddlewareConfig(
            name="security_headers", enabled=True, order=MiddlewareOrder.LATE, priority=1
        ),
    )

    # CORS中间件
    manager.register_middleware(
        name="cors",
        factory=lambda app, config: CORSMiddleware(app, config),
        config=MiddlewareConfig(
            name="cors",
            enabled=True,
            order=MiddlewareOrder.LATE,
            priority=2,
            options={
                "allowed_origins": ["*"],
                "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_credentials": True,
            },
        ),
    )
