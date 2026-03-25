# -*- coding: utf-8 -*-
"""
TCM Custom Exception Hierarchy
自定义异常层次结构

Defines a comprehensive exception hierarchy for the TCM Knowledge Base application.
All exceptions inherit from TCMBaseException for consistent error handling.
"""

from typing import Any, Dict, Optional
from datetime import datetime


class TCMBaseException(Exception):
    """
    Base exception class for all TCM Knowledge Base exceptions.

    All custom exceptions should inherit from this class to ensure
    consistent error handling, logging, and response formatting.

    Attributes:
        message: Human-readable error message
        code: Unique error code for programmatic handling
        http_status: HTTP status code to return
        details: Additional error context (filtered for sensitive data)
        request_id: Unique request identifier for tracing
        timestamp: When the exception occurred
    """

    def __init__(
        self,
        message: str,
        code: str,
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.details = details or {}
        self.request_id = request_id
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for JSON response.

        Returns:
            Dictionary representation of the exception
        """
        result = {
            "error": self.message,
            "code": self.code,
            "http_status": self.http_status,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.request_id:
            result["request_id"] = self.request_id

        if self.details:
            result["details"] = self.details

        return result

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class AuthenticationError(TCMBaseException):
    """
    Authentication failure exception.

    Raised when user authentication fails (invalid credentials, expired tokens, etc.)
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTH_FAILED",
        http_status: int = 401,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        auth_method: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if user_id:
            details["user_id"] = user_id
        if auth_method:
            details["auth_method"] = auth_method

        super().__init__(message, code, http_status, details, request_id)


class AuthorizationError(TCMBaseException):
    """
    Authorization failure exception.

    Raised when an authenticated user lacks permission for an action.
    """

    def __init__(
        self,
        message: str = "Insufficient permissions",
        code: str = "AUTHORIZATION_FAILED",
        http_status: int = 403,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        required_role: Optional[str] = None,
        user_role: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if required_role:
            details["required_role"] = required_role
        if user_role:
            details["user_role"] = user_role

        super().__init__(message, code, http_status, details, request_id)


class ValidationError(TCMBaseException):
    """
    Input validation failure exception.

    Raised when user input fails validation.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        code: str = "VALIDATION_ERROR",
        http_status: int = 400,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = (
                str(value) if len(str(value)) < 100 else str(value)[:100] + "..."
            )

        super().__init__(message, code, http_status, details, request_id)


class NotFoundError(TCMBaseException):
    """
    Resource not found exception.

    Raised when a requested resource doesn't exist.
    """

    def __init__(
        self,
        message: str,
        resource_type: str = "resource",
        resource_id: Optional[Any] = None,
        code: str = "NOT_FOUND",
        http_status: int = 404,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        details["resource_type"] = resource_type
        if resource_id is not None:
            details["resource_id"] = str(resource_id)

        super().__init__(message, code, http_status, details, request_id)


class ConflictError(TCMBaseException):
    """
    Resource conflict exception.

    Raised when a request conflicts with existing state.
    """

    def __init__(
        self,
        message: str,
        conflicting_field: Optional[str] = None,
        existing_value: Optional[Any] = None,
        code: str = "CONFLICT",
        http_status: int = 409,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if conflicting_field:
            details["conflicting_field"] = conflicting_field
        if existing_value is not None:
            details["existing_value"] = str(existing_value)

        super().__init__(message, code, http_status, details, request_id)


class DocumentProcessingError(TCMBaseException):
    """
    Document processing failure exception.

    Raised when document processing fails (parsing, embedding, indexing, etc.)
    """

    def __init__(
        self,
        message: str,
        document_id: Optional[str] = None,
        processing_stage: Optional[str] = None,
        code: str = "DOCUMENT_PROCESSING_ERROR",
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if document_id:
            details["document_id"] = document_id
        if processing_stage:
            details["processing_stage"] = processing_stage

        super().__init__(message, code, http_status, details, request_id)


class FileUploadError(TCMBaseException):
    """
    File upload failure exception.

    Raised when file upload fails (size limits, invalid type, etc.)
    """

    def __init__(
        self,
        message: str,
        filename: Optional[str] = None,
        file_size: Optional[int] = None,
        max_size: Optional[int] = None,
        allowed_types: Optional[list] = None,
        code: str = "FILE_UPLOAD_ERROR",
        http_status: int = 413,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if filename:
            details["filename"] = filename
        if file_size is not None:
            details["file_size"] = file_size
        if max_size is not None:
            details["max_size"] = max_size
        if allowed_types:
            details["allowed_types"] = allowed_types

        super().__init__(message, code, http_status, details, request_id)


class RateLimitError(TCMBaseException):
    """
    Rate limit exceeded exception.

    Raised when request rate limits are exceeded.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[str] = None,
        retry_after: Optional[int] = None,
        code: str = "RATE_LIMIT_EXCEEDED",
        http_status: int = 429,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if limit:
            details["limit"] = limit
        if window:
            details["window"] = window
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(message, code, http_status, details, request_id)


class ServiceUnavailableError(TCMBaseException):
    """
    Service unavailable exception.

    Raised when an external service is unavailable or fails.
    """

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None,
        circuit_open: bool = False,
        code: str = "SERVICE_UNAVAILABLE",
        http_status: int = 503,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if service_name:
            details["service"] = service_name
        if retry_after:
            details["retry_after"] = retry_after
        if circuit_open:
            details["circuit_breaker"] = "open"

        super().__init__(message, code, http_status, details, request_id)


class TimeoutError(TCMBaseException):
    """
    Operation timeout exception.

    Raised when an operation times out.
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        code: str = "TIMEOUT",
        http_status: int = 504,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        if operation:
            details["operation"] = operation

        super().__init__(message, code, http_status, details, request_id)


class DatabaseError(TCMBaseException):
    """
    Database operation failure exception.

    Raised when database operations fail.
    """

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        table: Optional[str] = None,
        code: str = "DATABASE_ERROR",
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if query:
            details["query"] = query[:200] + "..." if len(query) > 200 else query
        if table:
            details["table"] = table

        super().__init__(message, code, http_status, details, request_id)


class VectorStoreError(TCMBaseException):
    """
    Vector store (Milvus) operation failure exception.
    """

    def __init__(
        self,
        message: str,
        collection: Optional[str] = None,
        operation: Optional[str] = None,
        code: str = "VECTOR_STORE_ERROR",
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if collection:
            details["collection"] = collection
        if operation:
            details["operation"] = operation

        super().__init__(message, code, http_status, details, request_id)


class SearchEngineError(TCMBaseException):
    """
    Search engine (Elasticsearch) operation failure exception.
    """

    def __init__(
        self,
        message: str,
        index: Optional[str] = None,
        query: Optional[str] = None,
        code: str = "SEARCH_ENGINE_ERROR",
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if index:
            details["index"] = index
        if query:
            details["query"] = query[:200] + "..." if len(query) > 200 else query

        super().__init__(message, code, http_status, details, request_id)


class AIModelError(TCMBaseException):
    """
    AI model operation failure exception.

    Raised when AI model inference or operations fail.
    """

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        model_type: Optional[str] = None,
        code: str = "AI_MODEL_ERROR",
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if model_name:
            details["model"] = model_name
        if model_type:
            details["model_type"] = model_type

        super().__init__(message, code, http_status, details, request_id)


class ConfigurationError(TCMBaseException):
    """
    Configuration error exception.

    Raised when application configuration is invalid or missing.
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
        code: str = "CONFIGURATION_ERROR",
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        if details is None:
            details = {}
        if config_key:
            details["config_key"] = config_key
        if config_file:
            details["config_file"] = config_file

        super().__init__(message, code, http_status, details, request_id)


# Exception mapping for backward compatibility
LEGACY_EXCEPTION_MAP = {
    "ValidationError": ValidationError,
    "AuthenticationError": AuthenticationError,
    "AuthorizationError": AuthorizationError,
    "NotFoundError": NotFoundError,
    "ConflictError": ConflictError,
    "FileUploadError": FileUploadError,
    "RateLimitError": RateLimitError,
}


def get_exception_class_by_name(name: str) -> type:
    """Get exception class by name for backward compatibility."""
    return LEGACY_EXCEPTION_MAP.get(name, TCMBaseException)


__all__ = [
    "TCMBaseException",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "DocumentProcessingError",
    "FileUploadError",
    "RateLimitError",
    "ServiceUnavailableError",
    "TimeoutError",
    "DatabaseError",
    "VectorStoreError",
    "SearchEngineError",
    "AIModelError",
    "ConfigurationError",
    "LEGACY_EXCEPTION_MAP",
    "get_exception_class_by_name",
]
