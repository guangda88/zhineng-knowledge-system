"""
统一错误处理模块

提供HTTP异常和通用异常的统一处理，确保生产环境不泄露内部信息
"""

import logging

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    统一HTTP异常处理

    在生产环境中，500+错误不暴露内部详情，只记录到日志

    Args:
        request: FastAPI请求对象
        exc: HTTPException异常

    Returns:
        JSONResponse: 标准化的错误响应
    """
    # 获取请求路径
    path = request.url.path
    method = request.method

    # 提取错误详情
    detail = exc.detail

    # 生产环境：500+错误不暴露内部信息
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code} error on {method} {path}: {detail}", exc_info=True)
        detail = "Internal server error"
    elif exc.status_code >= 400:
        # 客户端错误记录为warning级别
        logger.warning(f"HTTP {exc.status_code} error on {method} {path}: {detail}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": detail,
                "status_code": exc.status_code,
            }
        },
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Pydantic验证异常处理

    处理请求验证失败的情况

    Args:
        request: FastAPI请求对象
        exc: ValidationException异常

    Returns:
        JSONResponse: 标准化的验证错误响应
    """
    path = request.url.path
    method = request.method

    logger.warning(f"Validation error on {method} {path}: {exc}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": str(exc),
                "status_code": 422,
            }
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    通用异常处理器

    捕获所有未处理的异常，防止敏感信息泄露

    Args:
        request: FastAPI请求对象
        exc: 未捕获的异常

    Returns:
        JSONResponse: 标准化的错误响应
    """
    # 获取请求信息
    path = request.url.path
    method = request.method

    # 记录完整的异常信息到日志
    logger.exception(f"Unhandled exception on {method} {path}: {type(exc).__name__}: {str(exc)}")

    # 生产环境：返回通用错误消息
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "status_code": 500,
            }
        },
    )


async def not_found_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    404 Not Found异常处理

    Args:
        request: FastAPI请求对象
        exc: 异常

    Returns:
        JSONResponse: 404错误响应
    """
    path = request.url.path
    logger.info(f"404 Not Found: {path}")

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource was not found",
                "status_code": 404,
            }
        },
    )


async def authentication_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    认证异常处理

    处理JWT认证失败、token过期等情况

    Args:
        request: FastAPI请求对象
        exc: 异常

    Returns:
        JSONResponse: 401认证错误响应
    """
    path = request.url.path
    method = request.method

    logger.warning(f"Authentication failed on {method} {path}: {exc}")

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "AUTHENTICATION_FAILED",
                "message": "Authentication is required to access this resource",
                "status_code": 401,
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    授权异常处理

    处理权限不足的情况

    Args:
        request: FastAPI请求对象
        exc: 异常

    Returns:
        JSONResponse: 403权限错误响应
    """
    path = request.url.path
    method = request.method

    logger.warning(f"Authorization failed on {method} {path}: {exc}")

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": {
                "code": "INSUFFICIENT_PERMISSIONS",
                "message": "You do not have permission to access this resource",
                "status_code": 403,
            }
        },
    )


async def rate_limit_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    速率限制异常处理

    处理请求超过速率限制的情况

    Args:
        request: FastAPI请求对象
        exc: 异常

    Returns:
        JSONResponse: 429速率限制错误响应
    """
    path = request.url.path
    logger.warning(f"Rate limit exceeded on {path}: {exc}")

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "status_code": 429,
            }
        },
    )


class APIError(Exception):
    """
    自定义API错误基类

    用于业务逻辑中抛出可控的API错误
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "API_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class ValidationError(APIError):
    """验证错误"""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(
            message=message, status_code=status.HTTP_400_BAD_REQUEST, code="VALIDATION_ERROR"
        )


class NotFoundError(APIError):
    """资源未找到错误"""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND")


class AuthenticationError(APIError):
    """认证错误"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message, status_code=status.HTTP_401_UNAUTHORIZED, code="AUTHENTICATION_FAILED"
        )


class AuthorizationError(APIError):
    """授权错误"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message, status_code=status.HTTP_403_FORBIDDEN, code="INSUFFICIENT_PERMISSIONS"
        )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    自定义API错误处理器

    处理业务逻辑中抛出的APIError及其子类

    Args:
        request: FastAPI请求对象
        exc: APIError异常

    Returns:
        JSONResponse: 标准化的API错误响应
    """
    path = request.url.path
    method = request.method

    logger.info(f"API error on {method} {path}: {exc.code} - {exc.message}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "status_code": exc.status_code}
        },
    )


def setup_error_handlers(app):
    """
    为FastAPI应用注册所有异常处理器

    Args:
        app: FastAPI应用实例

    Example:
        from fastapi import FastAPI
        from backend.core.error_handlers import setup_error_handlers

        app = FastAPI()
        setup_error_handlers(app)
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    # HTTP异常
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # 请求验证异常
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # 通用异常
    app.add_exception_handler(Exception, general_exception_handler)

    # 自定义API错误
    app.add_exception_handler(APIError, api_error_handler)

    logger.info("All error handlers registered successfully")
