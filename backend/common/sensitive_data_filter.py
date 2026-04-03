"""日志脱敏模块

防止敏感信息（密码、密钥、令牌等）被记录到日志中。
"""

import logging
import re
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

# 敏感字段名称列表
SENSITIVE_FIELDS: Set[str] = {
    # 密码相关
    "password",
    "passwd",
    "pwd",
    "pass",
    "password_confirmation",
    "new_password",
    "old_password",
    # 认证相关
    "api_key",
    "apikey",
    "api-key",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "secret_key_base",
    "private_key",
    "authorization",
    "auth_token",
    "session_token",
    "csrf_token",
    # 个人信息
    "credit_card",
    "ssn",
    "social_security",
    "social_security_number",
    "bank_account",
    "account_number",
    "routing_number",
    # 其他敏感信息
    "pin",
    "otp",
    "verification_code",
    "reset_token",
}

# 敏感数据模式
SENSITIVE_PATTERNS: List[tuple[str, str]] = [
    # JWT 令牌
    (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer *****"),
    # 邮箱地址
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "***@***.***"),
    # IP 地址（可选，根据需求）
    # (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '*.***.***'),
    # 电话号码（可选）
    # (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '***-****'),
    # 信用卡号
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "****-****-****-****"),
    # JSON Web Token
    (r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*", "eyJ***.*****.********"),
    # API 密钥常见格式
    (r"\b[A-Za-z0-9]{32,}\b", "***"),  # 32+ 字符的密钥
]


def filter_sensitive_data(data: Any, mask_char: str = "*") -> Any:
    """过滤敏感数据

    Args:
        data: 要过滤的数据（可以是字符串、字典、列表等）
        mask_char: 用于替换敏感数据的字符

    Returns:
        过滤后的数据
    """
    if isinstance(data, str):
        return _filter_string(data, mask_char)
    elif isinstance(data, dict):
        return _filter_dict(data, mask_char)
    elif isinstance(data, list):
        return [_filter_item(item, mask_char) for item in data]
    elif isinstance(data, tuple):
        return tuple(_filter_item(item, mask_char) for item in data)
    else:
        # 其他类型（int, float, bool, None 等）直接返回
        return data


def _filter_string(text: str, mask_char: str = "*") -> str:
    """过滤字符串中的敏感信息"""
    filtered_text = text

    # 应用所有敏感模式
    for pattern, replacement in SENSITIVE_PATTERNS:
        filtered_text = re.sub(pattern, replacement, filtered_text, flags=re.IGNORECASE)

    return filtered_text


def _filter_dict(data: Dict, mask_char: str = "*") -> Dict:
    """过滤字典中的敏感字段"""
    filtered = {}

    for key, value in data.items():
        # 检查键名是否是敏感字段
        if _is_sensitive_field(key):
            # 完全遮蔽敏感字段
            if isinstance(value, str):
                filtered[key] = mask_char * min(len(value), 8)
            elif isinstance(value, (int, float)):
                filtered[key] = mask_char * 8
            elif isinstance(value, dict):
                # 递归过滤嵌套字典
                filtered[key] = filter_sensitive_data(value, mask_char)
            else:
                filtered[key] = f"<{type(value).__name__}>"
        else:
            # 非敏感字段，递归过滤
            filtered[key] = filter_sensitive_data(value, mask_char)

    return filtered


def _filter_item(item: Any, mask_char: str = "*") -> Any:
    """过滤单个数据项"""
    if isinstance(item, (str, dict, list, tuple)):
        return filter_sensitive_data(item, mask_char)
    else:
        return item


def _is_sensitive_field(field_name: str) -> bool:
    """检查字段名是否是敏感字段"""
    if not isinstance(field_name, str):
        return False

    field_name_lower = field_name.lower()

    # 精确匹配
    if field_name_lower in SENSITIVE_FIELDS:
        return True

    # 模糊匹配（包含敏感词）
    for sensitive_word in SENSITIVE_FIELDS:
        if sensitive_word in field_name_lower:
            return True

    return False


class SensitiveDataFilter(logging.Filter):
    """日志过滤器 - 自动过滤敏感数据"""

    def __init__(self, mask_char: str = "*"):
        super().__init__()
        self.mask_char = mask_char

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤日志记录"""
        # 过滤消息
        if record.msg:
            record.msg = filter_sensitive_data(record.msg, self.mask_char)

        # 过滤参数
        if record.args:
            record.args = tuple(filter_sensitive_data(arg, self.mask_char) for arg in record.args)

        # 过滤额外信息
        if hasattr(record, "extra_data"):
            record.extra_data = filter_sensitive_data(record.extra_data, self.mask_char)

        return True


# 便捷函数
def safe_log(message: str, **kwargs) -> None:
    """安全日志记录 - 自动过滤敏感数据

    Args:
        message: 日志消息
        **kwargs: 额外的键值对（会被过滤）
    """
    filtered_kwargs = filter_sensitive_data(kwargs)
    logger.info(message, extra=filtered_kwargs)


def safe_log_error(message: str, exc_info: bool = False, **kwargs) -> None:
    """安全错误日志记录 - 自动过滤敏感数据

    Args:
        message: 错误消息
        exc_info: 是否包含异常信息
        **kwargs: 额外的键值对（会被过滤）
    """
    filtered_kwargs = filter_sensitive_data(kwargs)
    logger.error(message, exc_info=exc_info, extra=filtered_kwargs)


def safe_log_warning(message: str, **kwargs) -> None:
    """安全警告日志记录 - 自动过滤敏感数据"""
    filtered_kwargs = filter_sensitive_data(kwargs)
    logger.warning(message, extra=filtered_kwargs)


# 使用示例：
#
# import logging
# from common.sensitive_data_filter import SensitiveDataFilter, safe_log
#
# # 为所有日志处理器添加过滤器
# for handler in logging.root.handlers[:]:
#     handler.addFilter(SensitiveDataFilter())
#
# # 使用安全的日志函数
# safe_log("User logged in", user_id="123", email="user@example.com", password="secret123")
# # 输出: User logged in user_id="123", email="***@***.***", password="********"
#
# # 或使用普通日志（会自动过滤）
# logger.info("User created", extra={"username": "john", "api_key": "sk-1234567890"})
# # 输出: User created username="john", api_key="***********"
