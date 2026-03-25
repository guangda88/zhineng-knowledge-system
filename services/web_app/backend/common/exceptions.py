# -*- coding: utf-8 -*-
"""
自定义异常类型
Custom Exception Types

定义项目中使用的自定义异常类
"""

from typing import Any, Dict, Optional


class CommonException(Exception):
    """
    基础异常类

    所有自定义异常的基类，提供统一的错误处理接口
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            code: 错误代码
            details: 额外的错误详情
        """
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - {self.details}"
        return self.message


class ValidationError(CommonException):
    """
    验证错误

    当输入验证失败时抛出
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, code="VALIDATION_ERROR", details=details)
        self.field = field
        self.value = value


class FileProcessingError(CommonException):
    """
    文件处理错误

    当文件处理过程中发生错误时抛出
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        details = {}
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation
        super().__init__(message, code="FILE_PROCESSING_ERROR", details=details)
        self.file_path = file_path
        self.operation = operation


class ModelNotFoundError(CommonException):
    """
    模型未找到错误

    当请求的模型不存在或无法加载时抛出
    """

    def __init__(
        self,
        model_name: str,
        model_type: Optional[str] = None,
        expected_path: Optional[str] = None,
    ):
        message = f"Model not found: {model_name}"
        details = {"model_name": model_name}
        if model_type:
            details["model_type"] = model_type
            message = f"{message} (type: {model_type})"
        if expected_path:
            details["expected_path"] = expected_path
        super().__init__(message, code="MODEL_NOT_FOUND", details=details)
        self.model_name = model_name
        self.model_type = model_type
        self.expected_path = expected_path


class ConfigurationError(CommonException):
    """
    配置错误

    当配置无效或缺失时抛出
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
    ):
        details = {}
        if config_key:
            details["config_key"] = config_key
        if config_file:
            details["config_file"] = config_file
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)
        self.config_key = config_key
        self.config_file = config_file


class AuthenticationError(CommonException):
    """
    认证错误

    当API认证失败时抛出
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        provider: Optional[str] = None,
    ):
        details = {}
        if provider:
            details["provider"] = provider
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details)
        self.provider = provider


class RateLimitError(CommonException):
    """
    速率限制错误

    当API请求超过速率限制时抛出
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[str] = None,
    ):
        details = {}
        if limit:
            details["limit"] = limit
        if window:
            details["window"] = window
        super().__init__(message, code="RATE_LIMIT_ERROR", details=details)
        self.limit = limit
        self.window = window


class ServiceUnavailableError(CommonException):
    """
    服务不可用错误

    当外部服务不可用时抛出
    """

    def __init__(
        self,
        message: str = "Service unavailable",
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None,
    ):
        details = {}
        if service_name:
            details["service"] = service_name
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, code="SERVICE_UNAVAILABLE", details=details)
        self.service_name = service_name
        self.retry_after = retry_after


class TimeoutError(CommonException):
    """
    超时错误

    当操作超时时抛出
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout: Optional[float] = None,
        operation: Optional[str] = None,
    ):
        details = {}
        if timeout:
            details["timeout"] = timeout
        if operation:
            details["operation"] = operation
        super().__init__(message, code="TIMEOUT_ERROR", details=details)
        self.timeout = timeout
        self.operation = operation


class ResourceExhaustedError(CommonException):
    """
    资源耗尽错误

    当系统资源（如内存、磁盘空间）不足时抛出
    """

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        threshold: Optional[float] = None,
        current: Optional[float] = None,
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if threshold is not None:
            details["threshold"] = threshold
        if current is not None:
            details["current"] = current
        super().__init__(message, code="RESOURCE_EXHAUSTED", details=details)
        self.resource_type = resource_type
        self.threshold = threshold
        self.current = current


class ModelInitError(CommonException):
    """
    模型初始化错误

    当AI模型加载或初始化失败时抛出
    """

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        model_type: Optional[str] = None,
        model_path: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        """
        初始化模型初始化错误

        Args:
            message: 错误消息
            model_name: 模型名称
            model_type: 模型类型（如 embedding, ocr, asr）
            model_path: 模型路径
            suggestion: 解决建议
        """
        details = {}
        if model_name:
            details["model_name"] = model_name
        if model_type:
            details["model_type"] = model_type
        if model_path:
            details["model_path"] = model_path
        if suggestion:
            details["suggestion"] = suggestion

        # 构建可操作的错误消息
        full_message = message
        if model_name:
            full_message = f"{message} (model: {model_name})"
        if model_type:
            full_message = f"{full_message} (type: {model_type})"
        if suggestion:
            full_message = f"{full_message}. Suggestion: {suggestion}"

        super().__init__(full_message, code="MODEL_INIT_ERROR", details=details)
        self.model_name = model_name
        self.model_type = model_type
        self.model_path = model_path
        self.suggestion = suggestion


class FileValidationError(ValidationError):
    """
    文件验证错误

    专门用于文件验证失败的场景
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_type: Optional[str] = None,
        validation_type: Optional[str] = None,
    ):
        """
        初始化文件验证错误

        Args:
            message: 错误消息
            file_path: 文件路径
            file_name: 文件名
            file_size: 文件大小
            file_type: 文件类型/MIME类型
            validation_type: 验证类型（size, type, format等）
        """
        details = {}
        if file_path:
            details["file_path"] = file_path
        if file_name:
            details["file_name"] = file_name
        if file_size is not None:
            details["file_size"] = file_size
        if file_type:
            details["file_type"] = file_type
        if validation_type:
            details["validation_type"] = validation_type

        full_message = message
        if file_name:
            full_message = f"{message}: {file_name}"
        if validation_type:
            full_message = f"File {validation_type} validation failed: {message}"

        super().__init__(full_message, code="FILE_VALIDATION_ERROR", details=details)
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.file_type = file_type
        self.validation_type = validation_type


class APIRequestError(CommonException):
    """
    API请求错误

    当外部API请求失败时抛出
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """
        初始化API请求错误

        Args:
            message: 错误消息
            provider: API提供者
            status_code: HTTP状态码
            response_body: 响应体
            endpoint: 请求端点
        """
        details = {}
        if provider:
            details["provider"] = provider
        if status_code:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body[:500]  # 限制长度
        if endpoint:
            details["endpoint"] = endpoint

        full_message = message
        if provider:
            full_message = f"{provider} API error: {message}"
        if status_code:
            full_message = f"{full_message} (HTTP {status_code})"

        super().__init__(full_message, code="API_REQUEST_ERROR", details=details)
        self.provider = provider
        self.status_code = status_code
        self.response_body = response_body
        self.endpoint = endpoint


class ParsingError(FileProcessingError):
    """
    文件解析错误

    当文档解析失败时抛出
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        file_type: Optional[str] = None,
        parser_name: Optional[str] = None,
    ):
        """
        初始化解析错误

        Args:
            message: 错误消息
            file_path: 文件路径
            file_type: 文件类型
            parser_name: 解析器名称
        """
        details = {}
        if file_path:
            details["file_path"] = file_path
        if file_type:
            details["file_type"] = file_type
        if parser_name:
            details["parser"] = parser_name
        else:
            details["parser"] = "unknown"

        super().__init__(message, file_path=file_path, operation="parse")
        self.details.update(details)
        self.file_type = file_type
        self.parser_name = parser_name

        # 更新错误代码
        self.code = "PARSING_ERROR"


class ChunkingError(FileProcessingError):
    """
    文本分块错误

    当文本分块处理失败时抛出
    """

    def __init__(
        self,
        message: str,
        text_length: Optional[int] = None,
        chunk_size: Optional[int] = None,
        chunk_count: Optional[int] = None,
    ):
        """
        初始化分块错误

        Args:
            message: 错误消息
            text_length: 文本长度
            chunk_size: 配置的块大小
            chunk_count: 实际生成的块数量
        """
        details = {}
        if text_length is not None:
            details["text_length"] = text_length
        if chunk_size is not None:
            details["chunk_size"] = chunk_size
        if chunk_count is not None:
            details["chunk_count"] = chunk_count

        full_message = message
        if text_length:
            full_message = f"{message} (text length: {text_length})"
        if chunk_size:
            full_message = f"{full_message}, chunk_size: {chunk_size}"

        super().__init__(full_message, operation="chunk")
        self.details.update(details)
        self.text_length = text_length
        self.chunk_size = chunk_size
        self.chunk_count = chunk_count

        # 更新错误代码
        self.code = "CHUNKING_ERROR"
