# -*- coding: utf-8 -*-
"""
敏感数据过滤模块
Sensitive Data Filter Module

提供敏感数据脱敏功能，用于日志输出和错误响应中过滤敏感信息
支持的敏感数据类型：
- 密码
- JWT token
- API key
- 手机号
- 身份证号
- 邮箱
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Union
from copy import deepcopy


class SensitiveDataFilter:
    """
    敏感数据过滤器

    提供静态方法用于检测和脱敏各种类型的敏感数据
    """

    # 敏感字段名称列表（用于识别字段名）
    SENSITIVE_FIELD_NAMES = [
        "password",
        "passwd",
        "pwd",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "jwt",
        "api_key",
        "apikey",
        "api-key",
        "secret",
        "private_key",
        "phone",
        "mobile",
        "telephone",
        "cell",
        "id_card",
        "idcard",
        "identity",
        "ssn",
        "email",
        "mail",
        "email_address",
        "credit_card",
        "card_number",
        "cvv",
        "authorization",
        "bearer",
    ]

    # JWT Token 正则表达式
    JWT_PATTERN = re.compile(
        r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", re.IGNORECASE
    )

    # Bearer Token 正则表达式
    BEARER_PATTERN = re.compile(r"Bearer\s+[a-zA-Z0-9_.\-=]+", re.IGNORECASE)

    # API Key 正则表达式 (通用格式)
    API_KEY_PATTERNS = [
        # AWS API Key
        re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
        # Google API Key
        re.compile(r"AIza[a-zA-Z0-9_-]{35}", re.IGNORECASE),
        # 通用 API Key (32+ 字符的字母数字)
        re.compile(r"\b[a-zA-Z0-9]{32,}\b"),
        # Stripe key
        re.compile(r"sk_(live|test)_[a-zA-Z0-9]{24,}", re.IGNORECASE),
    ]

    # 手机号正则表达式 (中国大陆)
    PHONE_PATTERNS = [
        # 1开头的11位数字
        re.compile(r"1[3-9]\d{9}"),
        # 带+86的国际格式
        re.compile(r"\+86\s*1[3-9]\d{9}"),
        # 带86的国际格式
        re.compile(r"86\s*1[3-9]\d{9}"),
        # 带区号分隔的格式 138-1234-5678
        re.compile(r"1[3-9]\d{1}(-)?\d{4}(-)?\d{4}"),
    ]

    # 身份证号正则表达式 (中国大陆)
    ID_CARD_PATTERNS = [
        # 18位身份证号
        re.compile(
            r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]"
        ),
        # 15位身份证号（旧版）
        re.compile(r"[1-9]\d{5}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}"),
    ]

    # 邮箱正则表达式
    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}")

    # 信用卡号正则表达式
    CREDIT_CARD_PATTERNS = [
        # Visa: 4开头，13-19位
        re.compile(r"\b4\d{12}(\d{3}|\d{6})?\b"),
        # MasterCard: 51-55开头，16位
        re.compile(r"\b5[1-5]\d{14}\b"),
        # Amex: 34或37开头，15位
        re.compile(r"\b3[47]\d{13}\b"),
        # 通用16位卡号
        re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    ]

    # 密码相关模式
    PASSWORD_PATTERNS = [
        # JSON 格式: "password": "xxx" 或 password="xxx"
        re.compile(
            r'(["\']?password["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])', re.IGNORECASE
        ),
        # URL 参数: password=xxx (前面可能有 ? 或 & 或空格)
        re.compile(r'([\s?&]password=)([^&\s,"]+)', re.IGNORECASE),
        # 命令行: --password xxx 或 -p xxx
        re.compile(r"(--password[-=]|\s-p\s+)([^\s]+)", re.IGNORECASE),
        # 通用模式: password=xxx 或 password:xxx
        re.compile(r'\b(password|pwd|passwd)\s*[=:]\s*([^\s,"]+)', re.IGNORECASE),
    ]

    # 脱敏占位符
    MASK_PLACEHOLDERS = {
        "password": "***",
        "token": "***TOKEN***",
        "api_key": "***API_KEY***",
        "phone": "***PHONE***",
        "email": "***EMAIL***",
        "id_card": "***ID_CARD***",
        "credit_card": "***CARD***",
        "default": "***REDACTED***",
    }

    @classmethod
    def is_sensitive_field(cls, field_name: str) -> bool:
        """
        检查字段名是否为敏感字段

        Args:
            field_name: 字段名称

        Returns:
            bool: 是否为敏感字段
        """
        field_lower = field_name.lower().strip()
        return any(sensitive in field_lower for sensitive in cls.SENSITIVE_FIELD_NAMES)

    @classmethod
    def mask_value(cls, value: Any, field_name: str = None) -> Any:
        """
        对单个值进行脱敏处理

        Args:
            value: 原始值
            field_name: 字段名（可选，用于判断脱敏类型）

        Returns:
            脱敏后的值
        """
        if value is None:
            return None

        # 如果是字符串，进行字符串脱敏
        if isinstance(value, str):
            return cls._mask_string(value, field_name)

        # 如果是字典，递归处理
        if isinstance(value, dict):
            return cls.filter_dict(value)

        # 如果是列表，递归处理每个元素
        if isinstance(value, list):
            return [cls.mask_value(item, field_name) for item in value]

        # 其他类型，根据字段名判断
        if field_name and cls.is_sensitive_field(field_name):
            return cls.MASK_PLACEHOLDERS.get(
                cls._get_mask_type(field_name), cls.MASK_PLACEHOLDERS["default"]
            )

        return value

    @classmethod
    def _mask_string(cls, value: str, field_name: str = None) -> str:
        """
        对字符串进行脱敏处理

        Args:
            value: 原始字符串
            field_name: 字段名

        Returns:
            脱敏后的字符串
        """
        result = value

        # 1. 首先根据字段名判断
        if field_name:
            field_lower = field_name.lower()

            # 密码字段 - 完全脱敏
            if (
                "password" in field_lower
                or "pwd" in field_lower
                or "passwd" in field_lower
            ):
                return cls.MASK_PLACEHOLDERS["password"]

            # Token 字段 - 完全脱敏
            if "token" in field_lower or "jwt" in field_lower:
                return cls.MASK_PLACEHOLDERS["token"]

            # API Key 字段 - 完全脱敏
            if (
                "api_key" in field_lower
                or "apikey" in field_lower
                or "secret" in field_lower
            ):
                return cls.MASK_PLACEHOLDERS["api_key"]

            # 手机号字段 - 部分脱敏
            if any(x in field_lower for x in ["phone", "mobile", "telephone"]):
                return cls._mask_phone(result)

            # 身份证字段 - 部分脱敏
            if any(x in field_lower for x in ["id_card", "idcard", "identity", "ssn"]):
                return cls._mask_id_card(result)

            # 邮箱字段 - 部分脱敏
            if "email" in field_lower or "mail" in field_lower:
                return cls._mask_email(result)

            # 信用卡字段 - 部分脱敏
            if any(x in field_lower for x in ["credit_card", "card_number", "cvv"]):
                return cls._mask_credit_card(result)

        # 2. 对字符串内容进行模式匹配和脱敏
        result = cls._mask_jwt_tokens(result)
        result = cls._mask_bearer_tokens(result)
        result = cls._mask_api_keys(result)
        result = cls._mask_phones(result)
        result = cls._mask_id_cards(result)
        result = cls._mask_emails(result)
        result = cls._mask_credit_cards(result)
        result = cls._mask_passwords_in_text(result)

        return result

    @classmethod
    def _get_mask_type(cls, field_name: str) -> str:
        """根据字段名获取脱敏类型"""
        field_lower = field_name.lower()
        if "password" in field_lower or "pwd" in field_lower:
            return "password"
        if "token" in field_lower or "jwt" in field_lower:
            return "token"
        if "api_key" in field_lower or "secret" in field_lower:
            return "api_key"
        if "phone" in field_lower or "mobile" in field_lower:
            return "phone"
        if "id_card" in field_lower or "identity" in field_lower:
            return "id_card"
        if "email" in field_lower:
            return "email"
        if "card" in field_lower:
            return "credit_card"
        return "default"

    @classmethod
    def _mask_phone(cls, value: str) -> str:
        """脱敏手机号，保留前3位和后4位"""
        # 匹配 1开头的11位数字
        match = re.search(r"1[3-9]\d{9}", value)
        if match:
            phone = match.group()
            return value.replace(phone, phone[:3] + "****" + phone[-4:])
        # 匹配带+86的格式
        match = re.search(r"\+86\s*1[3-9]\d{9}", value)
        if match:
            phone = match.group()
            digits = re.search(r"1[3-9]\d{9}", phone)
            if digits:
                masked = digits.group()[:3] + "****" + digits.group()[-4:]
                return value.replace(phone, "+86 " + masked)
        return cls.MASK_PLACEHOLDERS["phone"]

    @classmethod
    def _mask_id_card(cls, value: str) -> str:
        """脱敏身份证号，保留前6位和后4位"""
        # 18位身份证
        match = re.search(
            r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]",
            value,
        )
        if match:
            id_card = match.group()
            return value.replace(id_card, id_card[:6] + "********" + id_card[-4:])
        # 15位身份证
        match = re.search(
            r"[1-9]\d{5}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}", value
        )
        if match:
            id_card = match.group()
            return value.replace(id_card, id_card[:6] + "*****" + id_card[-4:])
        return cls.MASK_PLACEHOLDERS["id_card"]

    @classmethod
    def _mask_email(cls, value: str) -> str:
        """脱敏邮箱，保留第一个字符和@后的域名"""
        match = cls.EMAIL_PATTERN.search(value)
        if match:
            email = match.group()
            parts = email.split("@")
            if len(parts) == 2:
                local, domain = parts
                if len(local) > 2:
                    masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
                else:
                    masked_local = local[0] + "*"
                masked_email = masked_local + "@" + domain
                return value.replace(email, masked_email)
        return cls.MASK_PLACEHOLDERS["email"]

    @classmethod
    def _mask_credit_card(cls, value: str) -> str:
        """脱敏信用卡号，只显示后4位"""
        # 去除空格和横线
        cleaned = re.sub(r"[\s-]", "", value)
        # 匹配13-19位数字
        match = re.search(r"\d{13,19}", cleaned)
        if match:
            card = match.group()
            masked = "*" * (len(card) - 4) + card[-4:]
            # 格式化
            if len(card) == 16:
                formatted = f"{masked[:4]} {masked[4:8]} {masked[8:12]} {masked[12:]}"
                return value.replace(card, formatted)
            return value.replace(card, masked)
        return cls.MASK_PLACEHOLDERS["credit_card"]

    @classmethod
    def _mask_jwt_tokens(cls, value: str) -> str:
        """脱敏JWT Token - 完全脱敏"""

        def replace_jwt(match):
            return cls.MASK_PLACEHOLDERS["token"]

        return cls.JWT_PATTERN.sub(replace_jwt, value)

    @classmethod
    def _mask_bearer_tokens(cls, value: str) -> str:
        """脱敏Bearer Token"""

        def replace_bearer(match):
            return "Bearer " + cls.MASK_PLACEHOLDERS["token"]

        return cls.BEARER_PATTERN.sub(replace_bearer, value)

    @classmethod
    def _mask_api_keys(cls, value: str) -> str:
        """脱敏API Key"""
        for pattern in cls.API_KEY_PATTERNS:

            def replace_key(match):
                key = match.group()
                if len(key) > 8:
                    return key[:4] + "***" + key[-4:]
                return cls.MASK_PLACEHOLDERS["api_key"]

            value = pattern.sub(replace_key, value)
        return value

    @classmethod
    def _mask_phones(cls, value: str) -> str:
        """脱敏文本中的手机号"""
        for pattern in cls.PHONE_PATTERNS:

            def replace_phone(match):
                phone = re.sub(r"[^\d]", "", match.group())
                if len(phone) == 11 and phone.startswith("1"):
                    return phone[:3] + "****" + phone[-4:]
                return cls.MASK_PLACEHOLDERS["phone"]

            value = pattern.sub(replace_phone, value)
        return value

    @classmethod
    def _mask_id_cards(cls, value: str) -> str:
        """脱敏文本中的身份证号"""
        for pattern in cls.ID_CARD_PATTERNS:

            def replace_id(match):
                id_card = match.group()
                if len(id_card) == 18:
                    return id_card[:6] + "********" + id_card[-4:]
                return id_card[:6] + "*****" + id_card[-4:]

            value = pattern.sub(replace_id, value)
        return value

    @classmethod
    def _mask_emails(cls, value: str) -> str:
        """脱敏文本中的邮箱"""

        def replace_email(match):
            email = match.group()
            parts = email.split("@")
            if len(parts) == 2:
                local, domain = parts
                if len(local) > 2:
                    masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
                else:
                    masked_local = "*" * len(local)
                return masked_local + "@" + domain
            return cls.MASK_PLACEHOLDERS["email"]

        return cls.EMAIL_PATTERN.sub(replace_email, value)

    @classmethod
    def _mask_credit_cards(cls, value: str) -> str:
        """脱敏文本中的信用卡号"""
        for pattern in cls.CREDIT_CARD_PATTERNS:

            def replace_card(match):
                card = re.sub(r"[\s-]", "", match.group())
                return "*" * (len(card) - 4) + card[-4:]

            value = pattern.sub(replace_card, value)
        return value

    @classmethod
    def _mask_passwords_in_text(cls, value: str) -> str:
        """脱敏文本中的密码字段"""

        def make_replacer(pattern_idx):
            def replace_password(match):
                # 根据模式返回正确的替换结果
                if (
                    pattern_idx == 3
                ):  # 通用模式 \b(password|pwd|passwd)\s*[=:]\s*([^\s,"]+)
                    field_name = match.group(1)
                    return (
                        field_name
                        + match.group(2)[:1]
                        + "="
                        + cls.MASK_PLACEHOLDERS["password"]
                    )
                elif match.lastindex >= 3:
                    return (
                        match.group(1)
                        + cls.MASK_PLACEHOLDERS["password"]
                        + match.group(3)
                    )
                else:
                    return match.group(1) + cls.MASK_PLACEHOLDERS["password"]

            return replace_password

        for idx, pattern in enumerate(cls.PASSWORD_PATTERNS):
            value = pattern.sub(make_replacer(idx), value)
        return value

    @classmethod
    def filter_dict(cls, data: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
        """
        过滤字典中的敏感数据

        Args:
            data: 原始字典
            deep: 是否深度过滤（递归处理嵌套字典和列表）

        Returns:
            过滤后的字典
        """
        if not isinstance(data, dict):
            return data

        result = {}
        for key, value in data.items():
            # 检查键名是否为敏感字段
            if cls.is_sensitive_field(key):
                # 获取脱敏类型
                mask_type = cls._get_mask_type(key)
                result[key] = cls.MASK_PLACEHOLDERS.get(
                    mask_type, cls.MASK_PLACEHOLDERS["default"]
                )
            else:
                # 递归处理值
                if deep and isinstance(value, dict):
                    result[key] = cls.filter_dict(value, deep=True)
                elif deep and isinstance(value, list):
                    result[key] = [
                        (
                            cls.filter_dict(item, deep=True)
                            if isinstance(item, dict)
                            else cls.mask_value(item, key)
                        )
                        for item in value
                    ]
                else:
                    result[key] = cls.mask_value(value, key)

        return result

    @classmethod
    def filter_json(cls, json_str: str) -> str:
        """
        过滤JSON字符串中的敏感数据

        Args:
            json_str: JSON字符串

        Returns:
            过滤后的JSON字符串
        """
        try:
            data = json.loads(json_str)
            filtered = cls.filter_dict(data)
            return json.dumps(filtered, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # 如果不是有效的JSON，返回带敏感信息过滤的原始字符串
            return cls._mask_string(json_str)

    @classmethod
    def filter_log_message(cls, message: Any) -> str:
        """
        过滤日志消息中的敏感数据

        Args:
            message: 日志消息（可以是任意类型）

        Returns:
            过滤后的字符串
        """
        if message is None:
            return ""

        # 如果是字典或列表，先过滤再转换为字符串
        if isinstance(message, (dict, list)):
            filtered = cls.mask_value(message)
            return json.dumps(filtered, ensure_ascii=False, default=str)

        # 如果是字符串，直接进行模式匹配过滤
        if isinstance(message, str):
            return cls._mask_string(message)

        # 其他类型转换为字符串后进行过滤
        str_value = str(message)
        return cls._mask_string(str_value)

    @classmethod
    def filter_exception(cls, exc: Exception) -> Dict[str, Any]:
        """
        过滤异常信息中的敏感数据

        Args:
            exc: 异常对象

        Returns:
            过滤后的异常信息字典
        """
        result = {
            "type": type(exc).__name__,
            "message": cls.filter_log_message(str(exc)),
        }

        # 处理带有 details 属性的异常
        if hasattr(exc, "details") and isinstance(exc.details, dict):
            result["details"] = cls.filter_dict(exc.details)

        # 处理其他常见属性
        for attr in ["code", "http_status", "field", "filename"]:
            if hasattr(exc, attr):
                value = getattr(exc, attr)
                result[attr] = cls.mask_value(value, attr)

        return result


class SensitiveDataFormatter(logging.Formatter):
    """
    带有敏感数据过滤的日志格式化器
    """

    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt, datefmt, style)
        self.filter = SensitiveDataFilter()

    def format(self, record):
        # 过滤日志消息中的敏感数据
        if hasattr(record, "msg"):
            original_msg = record.msg
            record.msg = self.filter.filter_log_message(record.msg)

        # 格式化日志
        formatted = super().format(record)

        # 恢复原始消息（避免重复过滤）
        if hasattr(record, "msg"):
            record.msg = original_msg

        return formatted


class SensitiveLogFilter(logging.Filter):
    """
    日志过滤器 - 自动过滤所有日志记录中的敏感数据
    """

    def __init__(self, name=""):
        super().__init__(name)
        self.data_filter = SensitiveDataFilter()

    def filter(self, record):
        """过滤日志记录"""
        # 过滤消息
        if hasattr(record, "msg"):
            record.msg = self.data_filter.filter_log_message(record.msg)

        # 过滤参数
        if hasattr(record, "args") and record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, (dict, list)):
                    new_args.append(self.data_filter.mask_value(arg))
                elif isinstance(arg, str):
                    new_args.append(self.data_filter._mask_string(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)

        # 过滤额外字段
        for attr_name in list(record.__dict__.keys()):
            if attr_name not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                attr_value = getattr(record, attr_name)
                if isinstance(attr_value, (dict, list, str)):
                    setattr(record, attr_name, self.data_filter.mask_value(attr_value))

        return True


def get_sensitive_filter() -> SensitiveDataFilter:
    """获取敏感数据过滤器实例"""
    return SensitiveDataFilter()


def get_sensitive_log_filter() -> SensitiveLogFilter:
    """获取敏感数据日志过滤器实例"""
    return SensitiveLogFilter()


def get_sensitive_formatter(fmt=None, datefmt=None) -> SensitiveDataFormatter:
    """获取带敏感数据过滤的日志格式化器"""
    return SensitiveDataFormatter(fmt, datefmt)


# 便捷函数
def mask_data(data: Any, field_name: str = None) -> Any:
    """脱敏数据"""
    return SensitiveDataFilter.mask_value(data, field_name)


def filter_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """过滤字典中的敏感数据"""
    return SensitiveDataFilter.filter_dict(data)


def filter_log(message: Any) -> str:
    """过滤日志消息"""
    return SensitiveDataFilter.filter_log_message(message)


def is_sensitive_field(field_name: str) -> bool:
    """检查是否为敏感字段"""
    return SensitiveDataFilter.is_sensitive_field(field_name)
