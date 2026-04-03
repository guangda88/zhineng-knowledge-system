# -*- coding: utf-8 -*-
"""
错误处理中间件 - Backend模块
Error Handler Middleware - Backend Module

此模块从顶层middleware.error_handler导入错误处理功能
提供backend服务使用的统一错误处理接口
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 从顶层middleware导入所有错误处理函数和类
try:
    from middleware.error_handler import (
        ErrorDetails,
        SafeErrorHandler,
        create_error_response,
        create_success_response,
        get_error_code_for_exception,
        get_status_code_for_exception,
        init_error_handling,
        log_exception,
    )

    __all__ = [
        "create_error_response",
        "create_success_response",
        "log_exception",
        "get_status_code_for_exception",
        "get_error_code_for_exception",
        "ErrorDetails",
        "SafeErrorHandler",
        "init_error_handling",
    ]

except ImportError as e:
    # 如果顶层middleware不可用，提供基本的实现
    import logging
    from datetime import datetime
    from typing import Any, Dict, Optional, Union

    from fastapi import Request, Response
    from fastapi.responses import JSONResponse

    logger = logging.getLogger(__name__)

    def create_error_response(
        error: Union[Exception, str],
        request_id: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> JSONResponse:
        """创建错误响应（基本实现）"""
        if isinstance(error, str):
            message = error
            http_status = status_code or 500
            code = "ERROR"
        else:
            message = str(error)
            http_status = status_code or getattr(error, "http_status", 500)
            code = getattr(error, "code", type(error).__name__.upper())

        response_data = {
            "error": message,
            "code": code,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if request_id:
            response_data["request_id"] = request_id

        return JSONResponse(status_code=http_status, content=response_data)

    def create_success_response(
        data: Any,
        message: str = "Success",
        code: str = "SUCCESS",
        request_id: Optional[str] = None,
    ) -> JSONResponse:
        """创建成功响应（基本实现）"""
        response_data = {
            "success": True,
            "message": message,
            "code": code,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if request_id:
            response_data["request_id"] = request_id

        if data is not None:
            response_data["data"] = data

        return JSONResponse(status_code=200, content=response_data)

    def log_exception(
        exc: Exception,
        request: Optional[Request] = None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录异常（基本实现）"""
        log_data = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }

        if request:
            log_data["request"] = {
                "method": request.method,
                "path": request.url.path,
            }

        if additional_info:
            log_data["additional"] = additional_info

        logger.error(
            f"Exception occurred: {str(exc)}",
            extra=log_data,
            exc_info=True,
        )

    def get_status_code_for_exception(exc: Exception) -> int:
        """根据异常类型获取HTTP状态码"""
        if hasattr(exc, "http_status"):
            return exc.http_status

        exception_type = type(exc).__name__
        status_map = {
            "ValidationError": 400,
            "AuthenticationError": 401,
            "AuthorizationError": 403,
            "NotFoundError": 404,
            "ConflictError": 409,
            "FileUploadError": 413,
            "RateLimitError": 429,
        }
        return status_map.get(exception_type, 500)

    def get_error_code_for_exception(exc: Exception) -> str:
        """根据异常类型获取错误代码"""
        if hasattr(exc, "code"):
            return exc.code
        return type(exc).__name__.upper()

    # 占位符类
    class ErrorDetails:
        def __init__(self, *args, **kwargs):
            pass

    class SafeErrorHandler:
        def configure_handlers(self, app):
            pass

    def init_error_handling(app):
        logger.warning("Using basic error handling (enhanced version not available)")

    __all__ = [
        "create_error_response",
        "create_success_response",
        "log_exception",
        "get_status_code_for_exception",
        "get_error_code_for_exception",
        "ErrorDetails",
        "SafeErrorHandler",
        "init_error_handling",
    ]
