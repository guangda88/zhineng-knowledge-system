"""路径遍历防护测试

验证 backend/utils/path_validation.py 的安全逻辑。
"""

import os

import pytest

from backend.utils.path_validation import (
    ALLOWED_BASE_DIRS,
    get_project_root,
    is_safe_path,
    validate_file_path,
)


class TestValidateFilePath:
    """validate_file_path 核心逻辑测试"""

    def test_empty_path_rejected(self):
        with pytest.raises(ValueError, match="不能为空"):
            validate_file_path("")

    def test_whitespace_path_rejected(self):
        with pytest.raises(ValueError, match="不能为空"):
            validate_file_path("   ")

    def test_absolute_path_rejected(self):
        with pytest.raises(ValueError, match="绝对路径"):
            validate_file_path("/etc/passwd")

    def test_parent_traversal_rejected(self):
        with pytest.raises(ValueError, match="父目录"):
            validate_file_path("data/textbooks/../../../etc/passwd")

    def test_double_dot_in_middle_rejected(self):
        with pytest.raises(ValueError):
            validate_file_path("data/textbooks/../../etc/shadow")

    def test_disallowed_directory_rejected(self):
        with pytest.raises(ValueError, match="允许的目录"):
            validate_file_path("backend/config/security.py")

    def test_disallowed_extension_rejected(self):
        with pytest.raises(ValueError, match="不支持的文件类型"):
            validate_file_path("data/textbooks/malware.exe")

    def test_allowed_txt_path_accepted(self):
        path, err = validate_file_path("data/textbooks/test.txt")
        assert err == ""
        assert path.name == "test.txt"

    def test_allowed_md_path_accepted(self):
        path, err = validate_file_path("data/textbooks/readme.md")
        assert err == ""
        assert path.name == "readme.md"

    def test_allowed_pdf_path_accepted(self):
        path, err = validate_file_path("data/uploaded/textbooks/book.pdf")
        assert err == ""
        assert path.name == "book.pdf"

    def test_allowed_json_path_accepted(self):
        path, err = validate_file_path("data/processed/result.json")
        assert err == ""

    def test_case_insensitive_extension(self):
        path, err = validate_file_path("data/textbooks/book.TXT")
        assert err == ""

    def test_allowed_base_dirs_cover_data_tree(self):
        for base_dir in ALLOWED_BASE_DIRS:
            path, err = validate_file_path(f"{base_dir}/test.txt")
            assert err == "", f"Expected {base_dir} to be allowed"

    def test_normpath_traversal_rejected(self):
        with pytest.raises(ValueError):
            validate_file_path("data/textbooks/./../../etc/passwd")


class TestSymlinkProtection:
    """符号链接安全测试"""

    def test_symlink_escape_rejected(self, tmp_path):
        project_root = get_project_root()
        data_dir = project_root / "data" / "textbooks"
        data_dir.mkdir(parents=True, exist_ok=True)

        target = tmp_path / "secret.txt"
        target.write_text("secret")

        link = data_dir / "evil_link.txt"
        try:
            os.symlink(str(target), str(link))
            with pytest.raises(ValueError):
                validate_file_path("data/textbooks/evil_link.txt")
        except FileExistsError:
            pass
        finally:
            try:
                link.unlink()
            except FileNotFoundError:
                pass

    def test_symlink_within_allowed_dir_accepted(self, tmp_path):
        project_root = get_project_root()
        data_dir = project_root / "data" / "textbooks"
        data_dir.mkdir(parents=True, exist_ok=True)

        real_file = data_dir / "real_file.txt"
        real_file.write_text("content")

        link = data_dir / "good_link.txt"
        try:
            os.symlink(str(real_file), str(link))
            path, err = validate_file_path("data/textbooks/good_link.txt")
            assert err == ""
        except FileExistsError:
            pass
        finally:
            try:
                link.unlink(missing_ok=True)
            except FileNotFoundError:
                pass


class TestIsSafePath:
    """is_safe_path 快速检查测试"""

    def test_safe_path_returns_true(self):
        assert is_safe_path("data/textbooks/test.txt") is True

    def test_traversal_returns_false(self):
        assert is_safe_path("../../../etc/passwd") is False

    def test_absolute_returns_false(self):
        assert is_safe_path("/etc/passwd") is False

    def test_wrong_ext_returns_false(self):
        assert is_safe_path("data/textbooks/test.exe") is False

    def test_wrong_dir_returns_false(self):
        assert is_safe_path("backend/main.py") is False


class TestEdgeCases:
    """边界情况测试"""

    def test_null_bytes_rejected(self):
        with pytest.raises((ValueError, OSError)):
            validate_file_path("data/textbooks/test\x00.txt")

    def test_unicode_path(self):
        path, err = validate_file_path("data/textbooks/中医药教材.txt")
        assert err == ""
        assert "中医药教材.txt" in str(path)

    def test_deeply_nested_allowed(self):
        path, err = validate_file_path("data/textbooks/sub/dir/deep/test.txt")
        assert err == ""

    def test_custom_allowed_dirs(self):
        custom_dirs = ["backend/config"]
        path, err = validate_file_path(
            "backend/config/security.py",
            allowed_base_dirs=custom_dirs,
            allowed_extensions=frozenset({".py"}),
        )
        assert err == ""
        assert path.name == "security.py"

    def test_custom_allowed_dirs_rejects_default(self):
        custom_dirs = ["backend/config"]
        with pytest.raises(ValueError, match="允许的目录"):
            validate_file_path(
                "data/textbooks/test.txt",
                allowed_base_dirs=custom_dirs,
                allowed_extensions=frozenset({".txt"}),
            )
