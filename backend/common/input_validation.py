"""输入验证模块 - 防止 XSS、SQL 注入等攻击

提供全面的输入验证和数据清理功能。
"""

import logging
import re
from typing import Any, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 可疑模式列表
SUSPICIOUS_PATTERNS = {
    "xss": [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe",
        r"<object",
        r"<embed",
    ],
    "sql_injection": [
        r"('\s*(OR|AND)\s*')",
        r";\s*DROP\s+TABLE",
        r";\s*DELETE\s+FROM",
        r";\s*INSERT\s+INTO",
        r";\s*UPDATE\s+\w+\s+SET",
        r"UNION\s+SELECT",
        r"--\s*$",
        r"/\*.*\*/",
    ],
    "path_traversal": [
        r"\.\./",
        r"\.\*",
        r"~/",
        r"%2e%2e",
    ],
    "code_injection": [
        r"eval\s*\(",
        r"exec\s*\(",
        r"system\s*\(",
        r"passthru\s*\(",
        r"popen\s*\(",
        r"\${",
    ],
    "command_injection": [
        r";\s*\w+",
        r"\|\s*\w+",
        r"&\s*\w+",
        r"`[^`]*`",
        r"\$[^$]*\$",
    ],
}


class InputValidator:
    """输入验证器"""

    def __init__(self):
        self.patterns = SUSPICIOUS_PATTERNS

    def validate_string(
        self,
        input_str: str,
        max_length: int = 1000,
        field_name: str = "input",
        allow_empty: bool = False,
    ) -> str:
        """验证字符串输入

        Args:
            input_str: 输入字符串
            max_length: 最大长度
            field_name: 字段名称
            allow_empty: 是否允许空值

        Returns:
            清理后的字符串

        Raises:
            HTTPException: 如果输入验证失败
        """
        if not isinstance(input_str, str):
            raise HTTPException(status_code=400, detail=f"{field_name} must be a string")

        if not input_str and not allow_empty:
            raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")

        if len(input_str) > max_length:
            raise HTTPException(
                status_code=400, detail=f"{field_name} exceeds maximum length of {max_length}"
            )

        # 检查可疑模式
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, input_str, re.IGNORECASE | re.MULTILINE | re.DOTALL):
                    logger.warning(
                        f"Suspicious input detected in {field_name}: "
                        f"category={category}, pattern={pattern[:50]}"
                    )
                    raise HTTPException(
                        status_code=400, detail=f"{field_name} contains suspicious content"
                    )

        return input_str.strip()

    def sanitize_query(self, query: str) -> str:
        """清理搜索查询

        Args:
            query: 搜索查询字符串

        Returns:
            清理后的查询字符串
        """
        if not query:
            return ""

        # 移除特殊字符（保留中文、字母、数字、常用标点）
        # 保留: 中文字符、字母、数字、空格、基本标点
        sanitized = re.sub(r'[^\w\s\u4e00-\u9fff.,?!:;()\-"\'+%]', "", query)

        # 限制长度
        return sanitized[:500]

    def validate_email(self, email: str) -> str:
        """验证邮箱地址

        Args:
            email: 邮箱地址

        Returns:
            清理后的邮箱地址
        """
        if not email:
            raise HTTPException(status_code=400, detail="Email cannot be empty")

        # 简单的邮箱格式验证
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise HTTPException(status_code=400, detail="Invalid email format")

        return email.strip().lower()

    def validate_url(self, url: str) -> str:
        """验证 URL

        Args:
            url: URL 字符串

        Returns:
            清理后的 URL
        """
        if not url:
            raise HTTPException(status_code=400, detail="URL cannot be empty")

        # 检查协议
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

        # 限制长度
        if len(url) > 2048:
            raise HTTPException(status_code=400, detail="URL exceeds maximum length")

        return url.strip()

    def validate_positive_int(
        self, value: int, field_name: str = "value", max_value: Optional[int] = None
    ) -> int:
        """验证正整数

        Args:
            value: 整数值
            field_name: 字段名称
            max_value: 最大值

        Returns:
            验证后的整数值
        """
        if not isinstance(value, int):
            raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")

        if value <= 0:
            raise HTTPException(status_code=400, detail=f"{field_name} must be positive")

        if max_value and value > max_value:
            raise HTTPException(status_code=400, detail=f"{field_name} must be <= {max_value}")

        return value

    def validate_json_string(self, json_str: str) -> Any:
        """验证并解析 JSON 字符串

        Args:
            json_str: JSON 字符串

        Returns:
            解析后的 Python 对象

        Raises:
            HTTPException: 如果 JSON 无效
        """
        import json

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    def check_sql_keywords(self, value: str) -> bool:
        """检查是否包含 SQL 关键字

        Args:
            value: 输入值

        Returns:
            True 如果包含 SQL 关键字，否则 False
        """
        sql_keywords = [
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "CREATE",
            "ALTER",
            "TRUNCATE",
            "UNION",
            "OR",
            "AND",
        ]

        upper_value = value.upper()
        return any(keyword in upper_value for keyword in sql_keywords)


# 全局验证器实例
validator = InputValidator()


# Pydantic 验证器
def validate_question(value: str) -> str:
    """Pydantic 验证器 - 验证问题输入"""
    return validator.validate_string(value, max_length=500, field_name="question")


def sanitize_search_query(value: str) -> str:
    """Pydantic 验证器 - 清理搜索查询"""
    return validator.sanitize_query(value)
