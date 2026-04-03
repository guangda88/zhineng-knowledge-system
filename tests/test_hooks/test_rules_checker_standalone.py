"""
测试规则检查器功能（独立版本，避免导入问题）
"""

import os
import sys
import unittest

# 添加backend路径
backend_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_path)

# 直接导入RulesChecker模块，避免通过__init__.py
import importlib.util

# 加载RulesChecker模块
spec = importlib.util.spec_from_file_location(
    "rules_checker", os.path.join(backend_path, "backend", "core", "rules_checker.py")
)
rules_checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules_checker)

RulesChecker = rules_checker.RulesChecker


class TestRulesCheckerStandalone(unittest.TestCase):
    """测试规则检查器（独立版本）"""

    def setUp(self):
        """测试前设置"""
        self.checker = RulesChecker()

    def test_check_modify_rules_success(self):
        """测试成功的规则修改检查"""
        action_data = {
            "discussed": True,
            "data_source": "static_analysis",
            "consensus": True,
            "discussion_summary": "团队讨论结果",
            "participants": ["AI", "User"],
        }

        # 应该不抛出异常
        result = self.checker.check_modify_rules(action_data)
        self.assertTrue(result)

    def test_check_modify_rules_not_discussed(self):
        """测试未讨论的规则修改"""
        action_data = {"discussed": False, "data_source": "static_analysis", "consensus": True}

        with self.assertRaises(PermissionError) as context:
            self.checker.check_modify_rules(action_data)

        self.assertIn("4.4.1", str(context.exception))
        self.assertIn("讨论", str(context.exception))

    def test_check_modify_rules_assumption_data(self):
        """测试基于假设的规则修改"""
        action_data = {"discussed": True, "data_source": "assumption", "consensus": True}

        with self.assertRaises(PermissionError) as context:
            self.checker.check_modify_rules(action_data)

        self.assertIn("4.4.2", str(context.exception))
        self.assertIn("假设", str(context.exception))

    def test_check_modify_rules_no_consensus(self):
        """测试未达成共识的规则修改"""
        action_data = {"discussed": True, "data_source": "static_analysis", "consensus": False}

        with self.assertRaises(PermissionError) as context:
            self.checker.check_modify_rules(action_data)

        self.assertIn("4.4.3", str(context.exception))
        self.assertIn("共识", str(context.exception))

    def test_validate_action_data_valid(self):
        """测试验证有效的操作数据"""
        action_data = {"discussed": True, "data_source": "static_analysis", "consensus": True}

        result = self.checker.validate_action_data(action_data)

        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_validate_action_data_missing_fields(self):
        """测试验证缺失字段的操作数据"""
        action_data = {}

        result = self.checker.validate_action_data(action_data)

        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

    def test_get_required_fields(self):
        """测试获取必需字段"""
        fields = self.checker.get_required_fields()

        self.assertIn("discussed", fields)
        self.assertIn("data_source", fields)
        self.assertIn("consensus", fields)


if __name__ == "__main__":
    unittest.main()
