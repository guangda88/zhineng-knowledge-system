# -*- coding: utf-8 -*-
"""
Structured Logging Configuration
结构化日志配置

Provides comprehensive logging configuration using structlog with:
- Structured JSON logging for production
- Human-readable console logging for development
- Log rotation with compression
- Correlation ID support
- Sensitive data filtering integration
- Performance metrics tracking
"""

import logging
import sys
import logging.handlers
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import json

import structlog
from structlog.types import Processor

from .sensitive_data_filter import (
    SensitiveDataFilter,
    get_sensitive_filter,
)


# Environment detection
def _is_development() -> bool:
    """Check if running in development environment"""
    import os

    return os.getenv("ENVIRONMENT", "development").lower() in (
        "development",
        "dev",
        "local",
    )


class LogConfig:
    """
    日志配置类
    Central logging configuration
    """

    # Log levels
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    # Log file configuration
    LOG_DIR = Path("/var/log/zbox")
    LOG_FILE = LOG_DIR / "app.log"
    LOG_FILE_MAX_BYTES = 100 * 1024 * 1024  # 100MB
    LOG_FILE_BACKUP_COUNT = 10

    # JSON log file (for structured logging)
    JSON_LOG_FILE = LOG_DIR / "app.json.log"

    # Log level from environment
    DEFAULT_LEVEL = logging.INFO
    LOG_LEVEL = logging.getLevelName(
        logging._nameToLevel.get(
            logging._levelToName.get(
                int(__import__("os").getenv("LOG_LEVEL", str(DEFAULT_LEVEL)))
            ),
            DEFAULT_LEVEL,
        )
    )

    # Sensitive fields to filter
    SENSITIVE_FIELDS = SensitiveDataFilter.SENSITIVE_FIELD_NAMES


class SensitiveDataProcessor:
    """
    Structlog processor for filtering sensitive data
    Structlog 敏感数据过滤处理器
    """

    def __init__(self):
        self.filter = get_sensitive_filter()

    def __call__(
        self, logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter sensitive data from log entries"""
        # Filter the event message
        if "event" in event_dict:
            event_dict["event"] = self.filter.filter_log_message(event_dict["event"])

        # Filter all string values in the event dict
        for key, value in event_dict.items():
            if isinstance(value, str):
                event_dict[key] = self.filter._mask_string(value)
            elif isinstance(value, dict):
                event_dict[key] = self.filter.filter_dict(value)
            elif isinstance(value, list):
                event_dict[key] = [
                    (
                        self.filter.filter_dict(item)
                        if isinstance(item, dict)
                        else (
                            self.filter._mask_string(item)
                            if isinstance(item, str)
                            else item
                        )
                    )
                    for item in value
                ]

        return event_dict


class CorrelationIdProcessor:
    """
    Add correlation ID to log entries
    关联ID处理器
    """

    def __call__(
        self, logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add correlation_id from context if present"""
        # Try to get correlation_id from context
        if "correlation_id" in event_dict:
            return event_dict

        # Generate from request_id if available
        if "request_id" in event_dict:
            event_dict["correlation_id"] = event_dict["request_id"]

        return event_dict


class TimestampProcessor:
    """
    Add ISO format timestamp to log entries
    时间戳处理器
    """

    def __call__(
        self, logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add ISO format timestamp"""
        if "timestamp" not in event_dict:
            event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return event_dict


class PerformanceMetricsProcessor:
    """
    Add performance metrics to log entries
    性能指标处理器
    """

    def __call__(
        self, logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract and format performance metrics"""
        # Format duration_ms if present
        if "duration_ms" in event_dict:
            duration = event_dict["duration_ms"]
            if isinstance(duration, (int, float)):
                event_dict["duration_ms"] = round(duration, 2)

                # Add performance category
                if duration < 100:
                    event_dict["performance"] = "fast"
                elif duration < 500:
                    event_dict["performance"] = "normal"
                elif duration < 1000:
                    event_dict["performance"] = "slow"
                else:
                    event_dict["performance"] = "very_slow"

        return event_dict


def _add_app_context(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add application context to log entries"""
    import os

    event_dict["app"] = os.getenv("APP_NAME", "zbox-kb")
    event_dict["environment"] = os.getenv("ENVIRONMENT", "development")
    event_dict["service"] = os.getenv("SERVICE_NAME", "api")
    return event_dict


def _extract_logger_name(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract logger name"""
    if "logger_name" not in event_dict:
        event_dict["logger_name"] = logger.name
    return event_dict


def _rename_message(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Rename event to message for compatibility"""
    if "event" in event_dict and "message" not in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def _sanitize_log_record(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Sanitize log record for JSON serialization"""
    # Remove non-serializable items
    for key in list(event_dict.keys()):
        try:
            json.dumps(event_dict[key])
        except (TypeError, ValueError):
            event_dict[key] = str(event_dict[key])
    return event_dict


def _get_dev_processors() -> list[Processor]:
    """Get processors for development environment"""
    return [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimestampProcessor(),
        structlog.dev.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        CorrelationIdProcessor(),
        PerformanceMetricsProcessor(),
        SensitiveDataProcessor(),
        _add_app_context,
        _extract_logger_name,
        structlog.processors.UnicodeDecoder(),
        # Console renderer for development - human readable
        structlog.dev.ConsoleRenderer(
            colors=True, exception_formatter=structlog.dev.plain_traceback
        ),
    ]


def _get_prod_processors() -> list[Processor]:
    """Get processors for production environment"""
    return [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimestampProcessor(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        CorrelationIdProcessor(),
        PerformanceMetricsProcessor(),
        SensitiveDataProcessor(),
        _add_app_context,
        _extract_logger_name,
        _sanitize_log_record,
        structlog.processors.UnicodeDecoder(),
        # JSON renderer for production - machine readable
        structlog.processors.JSONRenderer(),
    ]


def _setup_log_file_handlers() -> list:
    """
    Setup rotating file handlers
    配置日志文件处理器（带轮转）
    """
    # Ensure log directory exists
    LogConfig.LOG_DIR.mkdir(parents=True, exist_ok=True)

    handlers = []

    # Text log handler with rotation
    text_handler = logging.handlers.RotatingFileHandler(
        filename=str(LogConfig.LOG_FILE),
        maxBytes=LogConfig.LOG_FILE_MAX_BYTES,
        backupCount=LogConfig.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    text_handler.setLevel(LogConfig.LOG_LEVEL)
    text_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handlers.append(text_handler)

    # JSON log handler with rotation
    json_handler = logging.handlers.RotatingFileHandler(
        filename=str(LogConfig.JSON_LOG_FILE),
        maxBytes=LogConfig.LOG_FILE_MAX_BYTES,
        backupCount=LogConfig.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    json_handler.setLevel(LogConfig.LOG_LEVEL)
    # JSON formatter will be handled by structlog
    json_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(json_handler)

    return handlers


def configure_logging(
    log_level: Optional[int] = None,
    log_file: Optional[Path] = None,
    json_output: Optional[bool] = None,
    enable_file_logging: bool = True,
) -> None:
    """
    Configure structured logging for the application
    配置结构化日志

    Args:
        log_level: Override default log level
        log_file: Override default log file path
        json_output: Force JSON output (auto-detected if None)
        enable_file_logging: Enable file logging with rotation
    """
    is_dev = _is_development()
    should_use_json = json_output if json_output is not None else not is_dev

    # Determine log level
    level = log_level or LogConfig.LOG_LEVEL

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,  # Override any existing configuration
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)

    # Add file handlers if enabled
    if enable_file_logging:
        for handler in _setup_log_file_handlers():
            root_logger.addHandler(handler)

    # Configure structlog
    processors = _get_prod_processors() if should_use_json else _get_dev_processors()

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Log initialization
    logger = structlog.get_logger()
    logger.info(
        "Logging configured",
        environment="development" if is_dev else "production",
        output_format="json" if should_use_json else "console",
        log_level=logging.getLevelName(level),
        file_logging=enable_file_logging,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structured logger
    获取结构化日志记录器

    Args:
        name: Logger name (defaults to calling module)

    Returns:
        Configured structlog bound logger
    """
    return structlog.get_logger(name)


class LogContext:
    """
    Log context manager for adding contextual information
    日志上下文管理器
    """

    def __init__(self, **kwargs):
        self.context = kwargs
        self._logger = None

    def __enter__(self):
        self._logger = structlog.get_logger().bind(**self.context)
        return self._logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._logger.error(
                "Exception in context",
                exception_type=exc_type.__name__ if exc_type else None,
                exception_message=str(exc_val) if exc_val else None,
            )


def bind_context(**kwargs) -> structlog.stdlib.BoundLogger:
    """
    Bind context to the current logger
    绑定上下文到当前日志记录器

    Args:
        **kwargs: Context key-value pairs

    Returns:
        Logger with bound context

    Example:
        logger = bind_context(user_id="123", document_id="456")
        logger.info("Document processed")
    """
    return structlog.get_logger().bind(**kwargs)


def unbind_context(*keys: str) -> structlog.stdlib.BoundLogger:
    """
    Unbind context from the current logger
    解绑上下文

    Args:
        *keys: Context keys to unbind

    Returns:
        Logger with specified context removed
    """
    return structlog.get_logger().unbind(*keys)


def clear_context() -> structlog.stdlib.BoundLogger:
    """
    Clear all context from the current logger
    清除所有上下文

    Returns:
        Logger with clean context
    """
    return structlog.get_logger().new()


# Convenience functions for common logging scenarios
def log_request(
    method: str, path: str, status_code: int, duration_ms: float, **kwargs
) -> None:
    """Log HTTP request with standard fields"""
    logger = get_logger("api.request")
    log_data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        **kwargs,
    }

    # Log level based on status code
    if status_code >= 500:
        logger.error("request_completed", **log_data)
    elif status_code >= 400:
        logger.warning("request_completed", **log_data)
    else:
        logger.info("request_completed", **log_data)


def log_database_query(
    query: str, duration_ms: float, row_count: Optional[int] = None, **kwargs
) -> None:
    """Log database query with performance metrics"""
    logger = get_logger("database.query")
    log_data = {
        "query": query[:500] + "..." if len(query) > 500 else query,
        "duration_ms": round(duration_ms, 2),
        "row_count": row_count,
        **kwargs,
    }

    # Warn slow queries
    if duration_ms > 1000:
        logger.warning("slow_query", **log_data)
    else:
        logger.debug("query_executed", **log_data)


def log_external_api_call(
    service: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    **kwargs,
) -> None:
    """Log external API call"""
    logger = get_logger("external_api")
    log_data = {
        "service": service,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        **kwargs,
    }

    if status_code >= 500 or duration_ms > 5000:
        logger.warning("external_api_call", **log_data)
    else:
        logger.info("external_api_call", **log_data)


def log_document_operation(
    operation: str, document_id: str, user_id: Optional[str] = None, **kwargs
) -> None:
    """Log document-related operations"""
    logger = get_logger("document.operation")
    log_data = {
        "operation": operation,
        "document_id": document_id,
        "user_id": user_id,
        **kwargs,
    }
    logger.info("document_operation", **log_data)


def log_search_query(
    query: str,
    results_count: int,
    duration_ms: float,
    search_type: str = "hybrid",
    **kwargs,
) -> None:
    """Log search query with metrics"""
    logger = get_logger("search.query")
    log_data = {
        "query": query[:200],  # Truncate long queries
        "results_count": results_count,
        "duration_ms": round(duration_ms, 2),
        "search_type": search_type,
        **kwargs,
    }
    logger.info("search_executed", **log_data)


def log_authentication_event(
    event_type: str, user_id: Optional[str] = None, success: bool = True, **kwargs
) -> None:
    """Log authentication events"""
    logger = get_logger("auth.event")
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "success": success,
        **kwargs,
    }

    if not success:
        logger.warning("auth_event", **log_data)
    else:
        logger.info("auth_event", **log_data)


def log_error(
    error: Exception, context: Optional[Dict[str, Any]] = None, **kwargs
) -> None:
    """Log error with context"""
    logger = get_logger("error")
    log_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {}),
        **kwargs,
    }
    logger.error("error_occurred", **log_data, exc_info=error)


# Request context management
class RequestContext:
    """
    Request-scoped log context
    请求作用域日志上下文
    """

    _context: Dict[str, Any] = {}

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a context value"""
        cls._context[key] = value

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get a context value"""
        return cls._context.get(key, default)

    @classmethod
    def update(cls, **kwargs) -> None:
        """Update multiple context values"""
        cls._context.update(kwargs)

    @classmethod
    def clear(cls) -> None:
        """Clear all context"""
        cls._context.clear()

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Get all context as dictionary"""
        return cls._context.copy()

    @classmethod
    def bind_to_logger(
        cls, logger: Optional[structlog.stdlib.BoundLogger] = None
    ) -> structlog.stdlib.BoundLogger:
        """Bind all context to a logger"""
        if logger is None:
            logger = structlog.get_logger()
        return logger.bind(**cls._context)


# Initialize logging on import
configure_logging()
