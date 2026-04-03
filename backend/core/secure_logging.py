"""
安全日志模块

提供日志敏感数据过滤功能，防止密码、token、API密钥等敏感信息泄露
"""

import logging
import re
from pathlib import Path
from typing import Optional

# 敏感信息匹配模式
SENSITIVE_PATTERNS = [
    # 密码相关
    r'password["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'passwd["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'pwd["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    # Token相关
    r'token["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'access_token["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'refresh_token["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'auth_token["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r"bearer\s+[a-zA-Z0-9\-._~+/]+=*",
    # API密钥
    r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'apikey["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'secret[_-]?key["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    r'private[_-]?key["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    # JWT Token
    r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",
    # Session ID
    r'session[_-]?id["\']?\s*[:=]\s*["\']?[^"\']+\s*["\"]?',
    r'sessionid["\']?\s*[:=]\s*["\']?[^"\']+\s*["\']?',
    # Credit Card
    r'credit[_-]?card["\']?\s*[:=]\s*["\']?[\d\s-]+\s*["\']?',
    r'card[_-]?number["\']?\s*[:=]\s*["\']?[\d\s-]+\s*["\']?',
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
    # SSN (美国社会安全号)
    r"\b\d{3}-\d{2}-\d{4}\b",
    # Email (可选，根据需求)
    # r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    # Phone numbers (可选，根据需求)
    # r'\b\d{3}-\d{3}-\d{4}\b',
    # r'\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
]

# 编译正则表达式以提高性能
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS]

# 敏感字段名称列表（用于JSON日志过滤）
SENSITIVE_FIELD_NAMES = {
    "password",
    "passwd",
    "pwd",
    "token",
    "access_token",
    "refresh_token",
    "auth_token",
    "bearer_token",
    "api_key",
    "apikey",
    "secret",
    "secret_key",
    "private_key",
    "session_id",
    "sessionid",
    "credit_card",
    "card_number",
    "cvv",
    "cvc",
    "ssn",
    "social_security",
    "authorization",
    "auth",
}


class SensitiveDataFilter(logging.Filter):
    """
    敏感数据过滤器

    自动过滤日志中的敏感信息

    Example:
        logger = logging.getLogger(__name__)
        logger.addFilter(SensitiveDataFilter())
        logger.info("User logged in with password=secret123")
        # 输出: User logged in with password=[REDACTED]
    """

    def __init__(self, redaction_string: str = "[REDACTED]"):
        """
        初始化过滤器

        Args:
            redaction_string: 用于替换敏感信息的字符串
        """
        super().__init__()
        self.redaction_string = redaction_string

    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录中的敏感信息

        Args:
            record: 日志记录对象

        Returns:
            bool: 总是返回True（允许记录日志）
        """
        # 过滤消息
        if hasattr(record, "msg"):
            record.msg = self._sanitize(str(record.msg))

        # 过滤参数
        if hasattr(record, "args") and record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_args.append(self._sanitize(arg))
                elif isinstance(arg, dict):
                    sanitized_args.append(self._sanitize_dict(arg))
                elif isinstance(arg, (list, tuple)):
                    sanitized_args.append(self._sanitize_sequence(arg))
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)

        return True

    def _sanitize(self, text: str) -> str:
        """
        清理文本中的敏感信息

        Args:
            text: 原始文本

        Returns:
            str: 清理后的文本
        """
        for pattern in COMPILED_PATTERNS:
            text = pattern.sub(self.redaction_string, text)
        return text

    def _sanitize_dict(self, data: dict) -> dict:
        """
        清理字典中的敏感字段

        Args:
            data: 原始字典

        Returns:
            dict: 清理后的字典
        """
        sanitized = {}
        for key, value in data.items():
            # 检查键名是否敏感
            if key.lower() in SENSITIVE_FIELD_NAMES:
                sanitized[key] = self.redaction_string
            elif isinstance(value, str):
                sanitized[key] = self._sanitize(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = self._sanitize_sequence(value)
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_sequence(self, data) -> list:
        """
        清理序列中的敏感信息

        Args:
            data: 原始序列（list或tuple）

        Returns:
            list: 清理后的列表
        """
        sanitized = []
        for item in data:
            if isinstance(item, str):
                sanitized.append(self._sanitize(item))
            elif isinstance(item, dict):
                sanitized.append(self._sanitize_dict(item))
            elif isinstance(item, (list, tuple)):
                sanitized.append(self._sanitize_sequence(item))
            else:
                sanitized.append(item)
        return sanitized


def setup_secure_logging(
    level: int = logging.INFO, log_file: Optional[str] = None, redaction_string: str = "[REDACTED]"
) -> logging.Logger:
    """
    配置安全日志系统

    Args:
        level: 日志级别
        log_file: 日志文件路径（可选）
        redaction_string: 敏感信息替换字符串

    Returns:
        logging.Logger: 配置好的logger实例

    Example:
        logger = setup_secure_logging(
            level=logging.INFO,
            log_file="app.log"
        )
        logger.info("User logged in", extra={"user_id": 1})
    """
    # 创建logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # 清除现有handlers
    logger.handlers.clear()

    # 创建formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 添加敏感数据过滤器
    sensitive_filter = SensitiveDataFilter(redaction_string)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    logger.addHandler(console_handler)

    # File handler (如果指定)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取带有安全过滤的logger

    Args:
        name: logger名称

    Returns:
        logging.Logger: 配置好的logger实例

    Example:
        logger = get_logger(__name__)
        logger.info("API request", extra={"user_id": user.id})
    """
    logger = logging.getLogger(name)

    # 如果logger还没有过滤器，添加敏感数据过滤器
    if not any(isinstance(f, SensitiveDataFilter) for f in logger.filters):
        logger.addFilter(SensitiveDataFilter())

    return logger


# 便捷函数
def sanitize_log_message(message: str, redaction_string: str = "[REDACTED]") -> str:
    """
    快速清理单条日志消息

    Args:
        message: 原始消息
        redaction_string: 替换字符串

    Returns:
        str: 清理后的消息

    Example:
        clean_msg = sanitize_log_message("User password=secret123 logged in")
        # 返回: "User password=[REDACTED] logged in"
    """
    filter_obj = SensitiveDataFilter(redaction_string)
    return filter_obj._sanitize(message)
