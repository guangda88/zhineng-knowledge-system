# -*- coding: utf-8 -*-
"""
输入验证模块
Input Validation Module

提供文件大小、类型、格式等输入验证功能
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Union, Set
import mimetypes

from .exceptions import FileValidationError

logger = logging.getLogger(__name__)


# 常用文件类型定义
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus"}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"}

DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".pdf",
    ".djvu",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".rtf",
}

# 默认文件大小限制 (字节)
DEFAULT_MAX_FILE_SIZE = 5368709120  # 5GB
DEFAULT_MAX_IMAGE_SIZE = 104857600  # 100MB
DEFAULT_MAX_AUDIO_SIZE = 536870912  # 500MB
DEFAULT_MAX_VIDEO_SIZE = 2147483648  # 2GB


class ValidationResult:
    """
    验证结果类

    封装验证操作的结果
    """

    def __init__(
        self, is_valid: bool, message: str = "", details: Optional[dict] = None
    ):
        self.is_valid = is_valid
        self.message = message
        self.details = details or {}

    def __bool__(self) -> bool:
        return self.is_valid

    def __str__(self) -> str:
        return (
            self.message if self.message else ("Valid" if self.is_valid else "Invalid")
        )


def validate_file_size(
    file_path: Union[str, Path],
    max_size: Optional[int] = None,
) -> ValidationResult:
    """
    验证文件大小

    Args:
        file_path: 文件路径
        max_size: 最大允许大小（字节），默认为 5GB

    Returns:
        验证结果对象
    """
    if max_size is None:
        max_size = DEFAULT_MAX_FILE_SIZE

    path = Path(file_path)

    if not path.exists():
        return ValidationResult(
            False, f"File does not exist: {file_path}", {"file_path": str(path)}
        )

    if not path.is_file():
        return ValidationResult(
            False, f"Path is not a file: {file_path}", {"file_path": str(path)}
        )

    try:
        file_size = path.stat().st_size
    except OSError as e:
        return ValidationResult(
            False, f"Cannot get file size: {e}", {"file_path": str(path)}
        )

    if file_size > max_size:
        size_mb = file_size / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        return ValidationResult(
            False,
            f"File size {size_mb:.2f}MB exceeds maximum {max_mb:.2f}MB",
            {"file_size": file_size, "max_size": max_size},
        )

    return ValidationResult(
        True, f"File size OK: {file_size} bytes", {"file_size": file_size}
    )


def validate_file_type(
    file_path: Union[str, Path],
    allowed_extensions: Optional[set] = None,
    allowed_mime_types: Optional[set] = None,
) -> ValidationResult:
    """
    验证文件类型

    Args:
        file_path: 文件路径
        allowed_extensions: 允许的文件扩展名集合
        allowed_mime_types: 允许的 MIME 类型集合

    Returns:
        验证结果对象
    """
    path = Path(file_path)

    if not path.exists():
        return ValidationResult(
            False, f"File does not exist: {file_path}", {"file_path": str(path)}
        )

    extension = path.suffix.lower()

    # 检查扩展名
    if allowed_extensions is not None:
        if extension not in allowed_extensions:
            allowed_str = ", ".join(allowed_extensions)
            return ValidationResult(
                False,
                f"File extension '{extension}' not allowed. Allowed: {allowed_str}",
                {"extension": extension, "allowed": list(allowed_extensions)},
            )

    # 检查 MIME 类型
    if allowed_mime_types is not None:
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type not in allowed_mime_types:
            allowed_str = ", ".join(allowed_mime_types)
            return ValidationResult(
                False,
                f"MIME type '{mime_type}' not allowed. Allowed: {allowed_str}",
                {"mime_type": mime_type, "allowed": list(allowed_mime_types)},
            )

    return ValidationResult(
        True, f"File type OK: {extension}", {"extension": extension}
    )


def validate_file_path(
    file_path: Union[str, Path],
    must_exist: bool = True,
    allow_symlinks: bool = True,
) -> ValidationResult:
    """
    验证文件路径

    Args:
        file_path: 文件路径
        must_exist: 文件必须存在
        allow_symlinks: 是否允许符号链接

    Returns:
        验证结果对象
    """
    path = Path(file_path).resolve()

    if must_exist and not path.exists():
        return ValidationResult(
            False, f"Path does not exist: {file_path}", {"resolved_path": str(path)}
        )

    if not allow_symlinks and path.is_symlink():
        return ValidationResult(
            False,
            f"Symbolic links not allowed: {file_path}",
            {"resolved_path": str(path)},
        )

    return ValidationResult(True, f"Path OK: {path}", {"resolved_path": str(path)})


def validate_audio_file(
    file_path: Union[str, Path],
    max_size: Optional[int] = None,
) -> ValidationResult:
    """
    验证音频文件

    Args:
        file_path: 文件路径
        max_size: 最大文件大小（字节）

    Returns:
        验证结果对象
    """
    if max_size is None:
        max_size = DEFAULT_MAX_AUDIO_SIZE

    # 验证文件类型
    type_result = validate_file_type(file_path, AUDIO_EXTENSIONS)
    if not type_result:
        return type_result

    # 验证文件大小
    size_result = validate_file_size(file_path, max_size)
    if not size_result:
        return size_result

    return ValidationResult(
        True,
        f"Audio file OK: {file_path}",
        {"extension": Path(file_path).suffix.lower()},
    )


def validate_image_file(
    file_path: Union[str, Path],
    max_size: Optional[int] = None,
) -> ValidationResult:
    """
    验证图像文件

    Args:
        file_path: 文件路径
        max_size: 最大文件大小（字节）

    Returns:
        验证结果对象
    """
    if max_size is None:
        max_size = DEFAULT_MAX_IMAGE_SIZE

    # 验证文件类型
    type_result = validate_file_type(file_path, IMAGE_EXTENSIONS)
    if not type_result:
        return type_result

    # 验证文件大小
    size_result = validate_file_size(file_path, max_size)
    if not size_result:
        return size_result

    # 可选：尝试验证图像内容
    try:
        from PIL import Image

        with Image.open(file_path) as img:
            img.verify()
        return ValidationResult(
            True,
            f"Image file OK: {file_path}",
            {"extension": Path(file_path).suffix.lower()},
        )
    except Exception as e:
        return ValidationResult(
            False, f"Image verification failed: {e}", {"error": str(e)}
        )


def validate_video_file(
    file_path: Union[str, Path],
    max_size: Optional[int] = None,
) -> ValidationResult:
    """
    验证视频文件

    Args:
        file_path: 文件路径
        max_size: 最大文件大小（字节）

    Returns:
        验证结果对象
    """
    if max_size is None:
        max_size = DEFAULT_MAX_VIDEO_SIZE

    # 验证文件类型
    type_result = validate_file_type(file_path, VIDEO_EXTENSIONS)
    if not type_result:
        return type_result

    # 验证文件大小
    size_result = validate_file_size(file_path, max_size)
    if not size_result:
        return size_result

    return ValidationResult(
        True,
        f"Video file OK: {file_path}",
        {"extension": Path(file_path).suffix.lower()},
    )


def validate_document_file(
    file_path: Union[str, Path],
    max_size: Optional[int] = None,
) -> ValidationResult:
    """
    验证文档文件

    Args:
        file_path: 文件路径
        max_size: 最大文件大小（字节）

    Returns:
        验证结果对象
    """
    if max_size is None:
        max_size = DEFAULT_MAX_FILE_SIZE

    # 验证文件类型
    type_result = validate_file_type(file_path, DOCUMENT_EXTENSIONS)
    if not type_result:
        return type_result

    # 验证文件大小
    size_result = validate_file_size(file_path, max_size)
    if not size_result:
        return size_result

    return ValidationResult(
        True,
        f"Document file OK: {file_path}",
        {"extension": Path(file_path).suffix.lower()},
    )


def get_file_mimetype(file_path: Union[str, Path]) -> str:
    """
    获取文件的 MIME 类型

    Args:
        file_path: 文件路径

    Returns:
        MIME 类型字符串
    """
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


def get_file_extension(file_path: Union[str, Path]) -> str:
    """
    获取文件扩展名（小写）

    Args:
        file_path: 文件路径

    Returns:
        扩展名（含点号，如 ".txt"）
    """
    return Path(file_path).suffix.lower()


def is_audio_file(file_path: Union[str, Path]) -> bool:
    """检查是否为音频文件"""
    return get_file_extension(file_path) in AUDIO_EXTENSIONS


def is_image_file(file_path: Union[str, Path]) -> bool:
    """检查是否为图像文件"""
    return get_file_extension(file_path) in IMAGE_EXTENSIONS


def is_video_file(file_path: Union[str, Path]) -> bool:
    """检查是否为视频文件"""
    return get_file_extension(file_path) in VIDEO_EXTENSIONS


def is_document_file(file_path: Union[str, Path]) -> bool:
    """检查是否为文档文件"""
    return get_file_extension(file_path) in DOCUMENT_EXTENSIONS


def validate_upload(
    filename: str,
    file_size: int,
    allowed_extensions: Optional[set] = None,
    max_size: Optional[int] = None,
) -> ValidationResult:
    """
    验证上传文件

    Args:
        filename: 文件名
        file_size: 文件大小
        allowed_extensions: 允许的扩展名
        max_size: 最大文件大小

    Returns:
        验证结果对象
    """
    if max_size is None:
        max_size = DEFAULT_MAX_FILE_SIZE

    # 检查文件名
    if not filename:
        return ValidationResult(False, "Empty filename")

    # 检查文件大小
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        size_mb = file_size / (1024 * 1024)
        return ValidationResult(
            False, f"File size {size_mb:.2f}MB exceeds maximum {max_mb:.2f}MB"
        )

    # 检查扩展名
    if allowed_extensions is not None:
        ext = Path(filename).suffix.lower()
        if ext not in allowed_extensions:
            return ValidationResult(False, f"File extension '{ext}' not allowed")

    return ValidationResult(True, "Upload validation passed")


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除不安全字符

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    # 移除路径分隔符
    filename = filename.replace("/", "").replace("\\", "")

    # 保留安全字符：字母、数字、中文、下划线、点号、连字符、空格
    safe_chars = set(
        "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "._- "
    )

    # 添加中文字符范围
    safe_filename = []
    for char in filename:
        if char in safe_chars or ord(char) > 127:
            safe_filename.append(char)
        else:
            safe_filename.append("_")

    result = "".join(safe_filename)

    # 移除开头的点和空格
    result = result.lstrip(". ")

    # 确保不为空
    if not result:
        result = "unnamed"

    return result
