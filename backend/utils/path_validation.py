"""文件路径安全验证工具

防止路径遍历攻击，确保文件访问限制在允许的目录内。
"""

import os
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple

ALLOWED_EXTENSIONS = frozenset({".txt", ".pdf", ".md", ".json", ".csv", ".epub", ".html", ".htm"})

ALLOWED_BASE_DIRS: List[str] = [
    "data/textbooks",
    "data/uploaded/textbooks",
    "data/processed/textbooks",
    "data/processed/textbooks_v2",
    "data/processed",
    "data",
]


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _is_under_allowed_dir(
    resolved_path: Path, allowed_base_dirs: List[str], project_root: Path
) -> bool:
    for base_dir in allowed_base_dirs:
        allowed_root = (project_root / base_dir).resolve()
        try:
            resolved_path.relative_to(allowed_root)
            return True
        except ValueError:
            continue
    return False


def validate_file_path(
    user_path: str,
    allowed_base_dirs: Optional[List[str]] = None,
    allowed_extensions: Optional[frozenset] = None,
) -> Tuple[Path, str]:
    """验证用户提供的文件路径是否安全。

    Args:
        user_path: 用户提供的路径字符串
        allowed_base_dirs: 允许的基目录列表（相对于项目根目录）。
                          为 None 则使用默认值。
        allowed_extensions: 允许的文件扩展名。为 None 则使用默认值。

    Returns:
        (resolved_path, error_message) — error_message 为空字符串表示验证通过。

    Raises:
        ValueError: 路径不合法时抛出。
    """
    if allowed_base_dirs is None:
        allowed_base_dirs = ALLOWED_BASE_DIRS
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS

    if not user_path or not user_path.strip():
        raise ValueError("文件路径不能为空")

    normalized_input = os.path.normpath(user_path)

    if ".." in PurePosixPath(normalized_input).parts:
        raise ValueError("路径中不允许包含父目录引用 (..)")

    if os.path.isabs(normalized_input):
        raise ValueError("不允许使用绝对路径")

    project_root = get_project_root()
    resolved = (project_root / normalized_input).resolve()

    if not _is_under_allowed_dir(resolved, allowed_base_dirs, project_root):
        raise ValueError(f"文件路径不在允许的目录内。允许的目录: {', '.join(allowed_base_dirs)}")

    if resolved.is_symlink():
        real_target = resolved.resolve()
        if not _is_under_allowed_dir(real_target, allowed_base_dirs, project_root):
            raise ValueError("符号链接目标不在允许的目录内")

    ext = resolved.suffix.lower()
    if ext not in allowed_extensions:
        raise ValueError(
            f"不支持的文件类型: {ext}。允许的类型: {', '.join(sorted(allowed_extensions))}"
        )

    return resolved, ""


def is_safe_path(user_path: str) -> bool:
    """快速检查路径是否安全（不抛异常）。"""
    try:
        validate_file_path(user_path)
        return True
    except (ValueError, OSError):
        return False
