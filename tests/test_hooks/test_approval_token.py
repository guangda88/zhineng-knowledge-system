"""
测试批准令牌功能
"""

import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.hooks.claude_code.approval_token import ApprovalToken


class TestApprovalToken(unittest.TestCase):
    """测试批准令牌"""

    def setUp(self):
        """测试前清理"""
        if os.path.exists(ApprovalToken.TOKEN_FILE):
            os.remove(ApprovalToken.TOKEN_FILE)

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(ApprovalToken.TOKEN_FILE):
            os.remove(ApprovalToken.TOKEN_FILE)

    def test_create_token(self):
        """测试创建令牌"""
        token = ApprovalToken.create("db_write")

        self.assertTrue(os.path.exists(ApprovalToken.TOKEN_FILE))
        self.assertEqual(token["operation"], "db_write")
        self.assertTrue(token["approved"])

    def test_validate_valid_token(self):
        """测试验证有效令牌"""
        ApprovalToken.create("db_write")
        valid, message = ApprovalToken.validate("db_write")

        self.assertTrue(valid)
        self.assertIn("✅", message)

    def test_validate_missing_token(self):
        """测试验证缺失令牌"""
        valid, message = ApprovalToken.validate("db_write")

        self.assertFalse(valid)
        self.assertIn("未找到", message)

    def test_validate_wrong_operation(self):
        """测试验证错误操作类型"""
        ApprovalToken.create("db_write")
        valid, message = ApprovalToken.validate("file_delete")

        self.assertFalse(valid)
        self.assertIn("类型不匹配", message)

    def test_validate_expired_token(self):
        """测试验证过期令牌"""
        # 创建一个1秒有效期的令牌
        ApprovalToken.create("db_write", duration_minutes=0.016)  # 1秒

        # 等待令牌过期
        time.sleep(2)

        valid, message = ApprovalToken.validate("db_write")

        self.assertFalse(valid)
        self.assertIn("已过期", message)

    def test_clear_token(self):
        """测试清除令牌"""
        ApprovalToken.create("db_write")
        self.assertTrue(os.path.exists(ApprovalToken.TOKEN_FILE))

        ApprovalToken.clear()
        self.assertFalse(os.path.exists(ApprovalToken.TOKEN_FILE))

    def test_get_token_info(self):
        """测试获取令牌信息"""
        token = ApprovalToken.create("db_write")
        info = ApprovalToken.get_token_info()

        self.assertIsNotNone(info)
        self.assertEqual(info["operation"], "db_write")
        self.assertTrue(info["approved"])


if __name__ == "__main__":
    unittest.main()
