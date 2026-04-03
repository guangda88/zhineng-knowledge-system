"""
输入验证和安全模块

提供安全的输入验证类型和验证器，防止XSS、SQL注入等攻击
"""

import re
from typing import ClassVar, List, Optional

from pydantic import BaseModel, Field, field_validator

# XSS攻击模式检测
XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"onerror\s*=",
    r"onload\s*=",
    r"onclick\s*=",
    r"onmouseover\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
    r"<link[^>]*>",
    r"<meta[^>]*>",
    r"<style[^>]*>.*?</style>",
    r"<img[^>]*onerror[^>]*>",
]

# SQL注入模式检测
SQL_INJECTION_PATTERNS = [
    r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
    r"(\bor\b|\band\b).*?=.*?",
    r"exec(\s|\+)+(s|x)p\w+",
    r"union(\s|\+)*(all(\s|\+)*select|select)",
    r"insert(\s|\+)*(into|value)",
    r"delete(\s|\+)*(from|where)",
    r"update(\s|\+)*(set|where)",
    r"drop(\s|\+)*(table|database)",
    r"create(\s|\+)*(table|database)",
    r"alter(\s|\+)*(table|database)",
]

# 编译正则表达式
XSS_REGEX = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in XSS_PATTERNS]
SQL_INJECTION_REGEX = [re.compile(pattern, re.IGNORECASE) for pattern in SQL_INJECTION_PATTERNS]


class SafeString(str):
    """
    安全字符串类型

    自动检测和拒绝包含潜在恶意内容的字符串

    Example:
        class UserInput(BaseModel):
            username: SafeString
            comment: SafeString
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Pydantic v2核心schema"""
        from pydantic_core import core_schema

        python_schema = core_schema.with_info_plain_validator_function(
            cls.validate, serialization=core_schema.plain_serializer_function_ser_schema(str)
        )
        return core_schema.json_or_python_schema(
            json_schema=python_schema,
            python_schema=python_schema,
        )

    @classmethod
    def __get_validators__(cls):
        """Pydantic v1兼容"""
        yield cls.validate

    @classmethod
    def validate(cls, v):
        """
        验证字符串安全性

        Args:
            v: 待验证的值

        Returns:
            str: 验证通过的安全字符串

        Raises:
            ValueError: 如果检测到恶意内容
        """
        if not isinstance(v, str):
            raise TypeError("string required")

        # 检查长度
        if len(v) > 10000:
            raise ValueError("Input too long (max 10000 characters)")

        # 检查XSS攻击模式
        for pattern in XSS_REGEX:
            if pattern.search(v):
                raise ValueError("Potentially dangerous content detected (XSS)")

        # 检查SQL注入模式
        for pattern in SQL_INJECTION_REGEX:
            if pattern.search(v):
                raise ValueError("Potentially dangerous content detected (SQL Injection)")

        return v


class SearchQuery(BaseModel):
    """
    搜索查询验证模型

    用于验证搜索API的输入参数
    """

    q: SafeString = Field(..., min_length=1, max_length=200, description="搜索关键词")
    category: Optional[SafeString] = Field(
        None, pattern=r"^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$", description="分类筛选"
    )
    dynasty: Optional[SafeString] = Field(
        None, pattern=r"^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$", description="朝代筛选"
    )
    author: Optional[SafeString] = Field(None, max_length=100, description="作者筛选")
    page: int = Field(1, ge=1, le=1000, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页数量")

    @field_validator("q")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """
        验证搜索查询

        Args:
            v: 查询字符串

        Returns:
            str: 清理后的查询字符串
        """
        # 移除多余空格
        v = " ".join(v.split())

        # 限制特殊字符
        if not re.match(r"^[\w\s\u4e00-\u9fa5\-\.?:;,，。？！、…—\-]+$", v):
            raise ValueError("Query contains invalid characters")

        return v


class FileUploadValidator(BaseModel):
    """
    文件上传验证模型

    用于验证文件上传的安全性
    """

    filename: SafeString = Field(..., max_length=255)
    content_type: str = Field(..., pattern=r"^(application|image|text)/[a-zA-Z0-9\-\+]+$")
    file_size: int = Field(..., ge=1, le=10 * 1024 * 1024)  # 最大10MB

    # 允许的文件扩展名
    ALLOWED_EXTENSIONS: ClassVar[set[str]] = {
        ".txt",
        ".md",
        ".pdf",
        ".doc",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
    }

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """
        验证文件名安全性

        Args:
            v: 文件名

        Returns:
            str: 安全的文件名

        Raises:
            ValueError: 如果文件名不安全
        """
        # 检查路径遍历攻击
        if ".." in v or v.startswith("/"):
            raise ValueError("Invalid filename (path traversal detected)")

        # 检查文件扩展名
        import os

        ext = os.path.splitext(v)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"File type {ext} is not allowed")

        return v

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """
        验证Content-Type

        Args:
            v: Content-Type字符串

        Returns:
            str: 验证通过的Content-Type
        """
        # 危险的MIME类型黑名单
        DANGEROUS_TYPES = {
            "application/x-msdownload",
            "application/x-msdos-program",
            "application/x-msi",
            "application/x-ms-shortcut",
            "application/x-executable",
        }

        if v.lower() in DANGEROUS_TYPES:
            raise ValueError("Dangerous file type detected")

        return v


class UserInputValidator(BaseModel):
    """
    用户输入验证模型

    用于验证用户提交的各种输入
    """

    username: SafeString = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$")
    email: Optional[str] = Field(
        None, pattern=r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    )
    bio: Optional[SafeString] = Field(None, max_length=500)
    website: Optional[SafeString] = Field(
        None, pattern=r"^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$"
    )


class TextInputValidator(BaseModel):
    """
    文本输入验证模型

    用于验证长文本输入（如文章、评论等）
    """

    title: SafeString = Field(..., min_length=1, max_length=200)
    content: SafeString = Field(..., min_length=1, max_length=50000)
    tags: Optional[List[SafeString]] = Field(None, max_length=10)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """
        验证标签列表

        Args:
            v: 标签列表

        Returns:
            List[str]: 验证通过的标签列表
        """
        if v is None:
            return v

        # 去重并验证每个标签
        seen = set()
        validated_tags = []
        for tag in v:
            if len(tag) > 50:
                raise ValueError(f"Tag too long: {tag}")
            if tag in seen:
                continue
            seen.add(tag)
            validated_tags.append(tag)

        return validated_tags


def sanitize_html(html: str) -> str:
    """
    清理HTML中的危险标签和属性

    Args:
        html: 原始HTML字符串

    Returns:
        str: 清理后的HTML

    Example:
        clean_html = sanitize_html('<script>alert("xss")</script><p>Hello</p>')
        # 返回: '<p>Hello</p>'
    """
    # 移除危险标签
    for pattern in XSS_REGEX:
        html = pattern.sub("", html)

    # 移除事件处理器属性
    html = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', "", html, flags=re.IGNORECASE)

    return html


def validate_file_path(file_path: str, allowed_dir: str) -> bool:
    """
    验证文件路径安全性，防止路径遍历攻击

    Args:
        file_path: 待验证的文件路径
        allowed_dir: 允许的基础目录

    Returns:
        bool: 路径是否安全

    Example:
        if validate_file_path("../etc/passwd", "/var/uploads"):
            raise ValueError("Invalid file path")
    """
    from pathlib import Path

    try:
        # 解析路径
        allowed = Path(allowed_dir).resolve()
        requested = Path(file_path).resolve()

        # 检查是否在允许的目录内
        requested.relative_to(allowed)
        return True
    except (ValueError, RuntimeError):
        return False


class ValidationException(Exception):
    """验证异常"""

    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_pagination(page: int, size: int, max_size: int = 100) -> tuple[int, int]:
    """
    验证分页参数

    Args:
        page: 页码
        size: 每页数量
        max_size: 最大每页数量

    Returns:
        tuple[int, int]: (offset, limit)

    Raises:
        ValidationException: 参数无效
    """
    if page < 1:
        raise ValidationException("Page must be >= 1", "page")
    if size < 1:
        raise ValidationException("Size must be >= 1", "size")
    if size > max_size:
        raise ValidationException(f"Size must be <= {max_size}", "size")

    offset = (page - 1) * size
    limit = size

    return offset, limit
