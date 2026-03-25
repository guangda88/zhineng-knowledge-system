# -*- coding: utf-8 -*-
"""
统一文件处理模块
Unified File Handler Module

提供临时文件处理、文件管理等通用功能
"""

import os
import hashlib
import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union, List, IO, Generator, Callable
import uuid

from .exceptions import FileProcessingError
from .validators import sanitize_filename

logger = logging.getLogger(__name__)


class TempFileHandler:
    """
    临时文件处理器

    提供临时文件的创建、清理和管理功能
    """

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        prefix: str = "tmp_",
        suffix: str = "",
        auto_cleanup: bool = True,
    ) -> None:
        """
        初始化临时文件处理器

        Args:
            base_dir: 基础目录，默认为系统临时目录
            prefix: 文件名前缀
            suffix: 文件名后缀（扩展名）
            auto_cleanup: 是否自动清理临时文件
        """
        self.base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir())
        self.prefix = prefix
        self.suffix = suffix
        self.auto_cleanup = auto_cleanup
        self._managed_files: List[Path] = []

    def create_temp_file(
        self,
        content: Optional[bytes] = None,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> Path:
        """
        创建临时文件

        Args:
            content: 文件内容
            prefix: 文件名前缀（覆盖默认值）
            suffix: 文件名后缀（覆盖默认值）

        Returns:
            临时文件路径
        """
        prefix = prefix or self.prefix
        suffix = suffix or self.suffix

        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)

        fd, path = tempfile.mkstemp(
            prefix=prefix, suffix=suffix, dir=str(self.base_dir)
        )
        os.close(fd)

        temp_path = Path(path)

        if content:
            try:
                temp_path.write_bytes(content)
            except Exception as e:
                temp_path.unlink(missing_ok=True)
                raise FileProcessingError(
                    f"Failed to write temp file: {e}",
                    file_path=str(temp_path),
                    operation="write",
                )

        if self.auto_cleanup:
            self._managed_files.append(temp_path)

        logger.debug(f"Created temp file: {temp_path}")
        return temp_path

    def create_temp_dir(
        self,
        prefix: Optional[str] = None,
    ) -> Path:
        """
        创建临时目录

        Args:
            prefix: 目录名前缀

        Returns:
            临时目录路径
        """
        prefix = prefix or self.prefix

        self.base_dir.mkdir(parents=True, exist_ok=True)

        temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=str(self.base_dir)))

        if self.auto_cleanup:
            self._managed_files.append(temp_dir)

        logger.debug(f"Created temp dir: {temp_dir}")
        return temp_dir

    def from_upload(
        self,
        filename: str,
        content: bytes,
        prefix: Optional[str] = None,
    ) -> Path:
        """
        从上传内容创建临时文件

        Args:
            filename: 原始文件名
            content: 文件内容
            prefix: 文件名前缀

        Returns:
            临时文件路径
        """
        # 获取原始扩展名
        original_suffix = Path(filename).suffix
        suffix = original_suffix or self.suffix

        # 清理文件名
        safe_name = sanitize_filename(filename)

        # 创建临时文件
        temp_path = self.create_temp_file(
            content=content, prefix=prefix or self.prefix, suffix=suffix
        )

        logger.debug(f"Created temp file from upload: {safe_name} -> {temp_path}")
        return temp_path

    def cleanup(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """
        清理临时文件

        Args:
            file_path: 要清理的文件路径，如果为 None 则清理所有托管文件
        """
        if file_path:
            path = Path(file_path)
            safe_delete(path)
            if path in self._managed_files:
                self._managed_files.remove(path)
        else:
            # 清理所有托管文件
            for path in list(self._managed_files):
                safe_delete(path)
            self._managed_files.clear()

        logger.debug("Cleanup completed")

    def cleanup_all(self) -> None:
        """清理所有托管的临时文件"""
        self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.auto_cleanup:
            self.cleanup_all()


class FileManager:
    """
    文件管理器

    提供文件操作的统一接口
    """

    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        """
        初始化文件管理器

        Args:
            base_dir: 基础目录
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

    def ensure_dir(self, path: Optional[Union[str, Path]] = None) -> Path:
        """
        确保目录存在

        Args:
            path: 目录路径，默认为基础目录

        Returns:
            目录路径
        """
        dir_path = self.base_dir / path if path else self.base_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    def save_file(
        self,
        content: Union[bytes, str],
        filename: str,
        sub_dir: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
    ) -> Path:
        """
        保存文件

        Args:
            content: 文件内容
            filename: 文件名
            sub_dir: 子目录
            overwrite: 是否覆盖已存在的文件

        Returns:
            保存的文件路径
        """
        # 确保目录存在
        if sub_dir:
            target_dir = self.base_dir / sub_dir
        else:
            target_dir = self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # 清理文件名
        safe_name = sanitize_filename(filename)
        target_path = target_dir / safe_name

        # 检查文件是否存在
        if target_path.exists() and not overwrite:
            # 添加唯一后缀
            stem = target_path.stem
            suffix = target_path.suffix
            target_path = target_dir / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"

        # 写入文件
        try:
            if isinstance(content, str):
                target_path.write_text(content, encoding="utf-8")
            else:
                target_path.write_bytes(content)
            logger.info(f"File saved: {target_path}")
            return target_path
        except Exception as e:
            raise FileProcessingError(
                f"Failed to save file: {e}",
                file_path=str(target_path),
                operation="save",
            )

    def move_file(
        self,
        src: Union[str, Path],
        dst: Union[str, Path],
    ) -> Path:
        """
        移动文件

        Args:
            src: 源文件路径
            dst: 目标路径（可以是目录或新文件名）

        Returns:
            目标文件路径
        """
        src_path = Path(src)
        dst_path = Path(dst)

        if not src_path.exists():
            raise FileProcessingError(
                f"Source file does not exist: {src}",
                file_path=str(src_path),
                operation="move",
            )

        # 确保目标目录存在
        if dst_path.is_dir() or dst_path.suffix == "":
            dst_path.mkdir(parents=True, exist_ok=True)
            dst_path = dst_path / src_path.name

        try:
            shutil.move(str(src_path), str(dst_path))
            logger.info(f"File moved: {src_path} -> {dst_path}")
            return dst_path
        except Exception as e:
            raise FileProcessingError(
                f"Failed to move file: {e}", file_path=str(src_path), operation="move"
            )

    def copy_file(
        self,
        src: Union[str, Path],
        dst: Union[str, Path],
    ) -> Path:
        """
        复制文件

        Args:
            src: 源文件路径
            dst: 目标路径

        Returns:
            目标文件路径
        """
        src_path = Path(src)
        dst_path = Path(dst)

        if not src_path.exists():
            raise FileProcessingError(
                f"Source file does not exist: {src}",
                file_path=str(src_path),
                operation="copy",
            )

        # 确保目标目录存在
        if dst_path.is_dir() or dst_path.suffix == "":
            dst_path.mkdir(parents=True, exist_ok=True)
            dst_path = dst_path / src_path.name

        try:
            shutil.copy2(str(src_path), str(dst_path))
            logger.info(f"File copied: {src_path} -> {dst_path}")
            return dst_path
        except Exception as e:
            raise FileProcessingError(
                f"Failed to copy file: {e}", file_path=str(src_path), operation="copy"
            )

    def delete_file(self, path: Union[str, Path]) -> None:
        """
        删除文件

        Args:
            path: 文件路径
        """
        safe_delete(path)

    def list_files(
        self,
        dir_path: Optional[Union[str, Path]] = None,
        pattern: str = "*",
        recursive: bool = False,
    ) -> List[Path]:
        """
        列出目录中的文件

        Args:
            dir_path: 目录路径
            pattern: 文件匹配模式
            recursive: 是否递归

        Returns:
            文件路径列表
        """
        if dir_path:
            search_dir = Path(dir_path)
        else:
            search_dir = self.base_dir

        if not search_dir.exists():
            return []

        if recursive:
            files = list(search_dir.rglob(pattern))
        else:
            files = list(search_dir.glob(pattern))

        # 只返回文件
        return [f for f in files if f.is_file()]

    def get_file_hash(
        self,
        file_path: Union[str, Path],
        algorithm: str = "sha256",
    ) -> str:
        """
        计算文件哈希值

        Args:
            file_path: 文件路径
            algorithm: 哈希算法

        Returns:
            哈希值（十六进制字符串）
        """
        return get_file_hash(file_path, algorithm)


@contextmanager
def temp_file(
    content: Optional[bytes] = None,
    suffix: str = "",
    prefix: str = "tmp_",
) -> Generator[Path, None, None]:
    """
    临时文件上下文管理器

    Args:
        content: 文件内容
        suffix: 文件后缀
        prefix: 文件前缀

    Yields:
        临时文件路径
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)

    temp_path = Path(path)

    try:
        if content:
            temp_path.write_bytes(content)
        yield temp_path
    finally:
        safe_delete(temp_path)


@contextmanager
def temp_directory(prefix: str = "tmp_") -> Generator[Path, None, None]:
    """
    临时目录上下文管理器

    Args:
        prefix: 目录名前缀

    Yields:
        临时目录路径
    """
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix))

    try:
        yield temp_dir
    finally:
        safe_delete(temp_dir)


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    确保目录存在

    Args:
        path: 目录路径

    Returns:
        目录路径
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def safe_delete(path: Union[str, Path]) -> None:
    """
    安全删除文件或目录

    Args:
        path: 文件或目录路径
    """
    path = Path(path)

    if not path.exists():
        return

    try:
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        logger.debug(f"Deleted: {path}")
    except Exception as e:
        logger.warning(f"Failed to delete {path}: {e}")


def get_file_hash(
    file_path: Union[str, Path],
    algorithm: str = "sha256",
    chunk_size: int = 8192,
) -> str:
    """
    计算文件哈希值

    Args:
        file_path: 文件路径
        algorithm: 哈希算法 (md5, sha1, sha256, sha512)
        chunk_size: 读取块大小

    Returns:
        哈希值（十六进制字符串）
    """
    path = Path(file_path)

    if not path.exists():
        raise FileProcessingError(
            f"File does not exist: {file_path}", file_path=str(path), operation="hash"
        )

    try:
        hasher = hashlib.new(algorithm)
        with path.open("rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except ValueError as e:
        raise FileProcessingError(
            f"Invalid hash algorithm: {algorithm}",
            file_path=str(path),
            operation="hash",
        )
    except Exception as e:
        raise FileProcessingError(
            f"Failed to compute hash: {e}", file_path=str(path), operation="hash"
        )


def get_file_size(file_path: Union[str, Path]) -> int:
    """
    获取文件大小

    Args:
        file_path: 文件路径

    Returns:
        文件大小（字节）
    """
    path = Path(file_path)

    if not path.exists():
        raise FileProcessingError(
            f"File does not exist: {file_path}", file_path=str(path)
        )

    return path.stat().st_size


def format_size(size_bytes: int) -> str:
    """
    格式化文件大小

    Args:
        size_bytes: 字节数

    Returns:
        格式化后的字符串
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def find_files_by_extension(
    directory: Union[str, Path],
    extensions: Union[str, List[str]],
    recursive: bool = True,
) -> List[Path]:
    """
    根据扩展名查找文件

    Args:
        directory: 搜索目录
        extensions: 文件扩展名（如 ".txt" 或 [".txt", ".md"]）
        recursive: 是否递归搜索

    Returns:
        文件路径列表
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        return []

    if isinstance(extensions, str):
        extensions = [extensions]

    # 确保扩展名以点开头
    extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

    if recursive:
        files = [f for f in dir_path.rglob("*") if f.is_file()]
    else:
        files = [f for f in dir_path.glob("*") if f.is_file()]

    return [f for f in files if f.suffix.lower() in extensions]
