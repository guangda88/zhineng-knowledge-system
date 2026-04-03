"""
AI操作包装器
统一入口，拦截所有AI操作，应用各种Hook检查
"""

import logging
from typing import Any, Dict, Optional

from .data_verification_gate import DataVerificationGate
from .rules_checker import RulesChecker
from .urgency_guard import UrgencyGuard

logger = logging.getLogger(__name__)


class AIActionWrapper:
    """
    AI操作包装器

    这是所有AI操作的统一入口，负责：
    1. 拦截操作
    2. 应用各种Hook检查
    3. 执行操作
    4. 记录日志
    """

    def __init__(self):
        """初始化包装器"""
        self.rules_checker = RulesChecker()
        self.urgency_guard = UrgencyGuard()
        self.data_verification_gate = DataVerificationGate()

        logger.info("AIActionWrapper initialized")

    async def execute_action(
        self,
        action_type: str,
        action_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行AI操作的统一入口

        Args:
            action_type: 操作类型（如 "modify_rules", "generate_report", "fix_urgent_issue"）
            action_data: 操作数据
            context: 上下文信息

        Returns:
            操作结果字典

        Raises:
            PermissionError: 如果操作被Hook阻止
            ValueError: 如果操作数据无效
        """
        if action_data is None:
            action_data = {}
        if context is None:
            context = {}

        logger.info(f"Executing action: {action_type}")

        try:
            # 1. 紧急问题检查（所有操作都要检查）
            await self.urgency_guard.check_and_intercept(action_type, action_data)

            # 2. 规则修改检查（特定操作）
            if action_type == "modify_rules":
                self.rules_checker.check_modify_rules(action_data)

            # 3. 数据验证检查（特定操作）
            if action_type == "generate_report":
                self.data_verification_gate.verify_report_data(action_data)

            # 4. 执行操作
            result = await self._execute_action(action_type, action_data, context)

            logger.info(f"Action {action_type} completed successfully")
            return result

        except PermissionError as e:
            logger.error(f"Action {action_type} blocked: {e}")
            raise
        except ValueError as e:
            logger.error(f"Action {action_type} validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}", exc_info=True)
            raise

    async def _execute_action(
        self, action_type: str, action_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行具体操作

        这个方法应该被子类扩展，实现具体的操作逻辑
        """
        # 这里是示例实现
        # 实际使用时，应该根据action_type执行相应的操作

        if action_type == "modify_rules":
            return await self._modify_rules(action_data, context)
        elif action_type == "generate_report":
            return await self._generate_report(action_data, context)
        elif action_type == "fix_urgent_issue":
            return await self._fix_urgent_issue(action_data, context)
        else:
            raise ValueError(f"Unknown action type: {action_type}")

    async def _modify_rules(self, action_data: Dict, context: Dict) -> Dict:
        """修改规则"""
        # 实际实现
        return {"status": "success", "action": "modify_rules"}

    async def _generate_report(self, action_data: Dict, context: Dict) -> Dict:
        """生成报告"""
        # 实际实现
        return {"status": "success", "action": "generate_report"}

    async def _fix_urgent_issue(self, action_data: Dict, context: Dict) -> Dict:
        """修复紧急问题"""
        # 实际实现
        return {"status": "success", "action": "fix_urgent_issue"}

    def get_current_emergencies(self) -> list:
        """获取当前紧急问题列表"""
        return self.urgency_guard.get_current_emergencies()

    def is_emergency_mode(self) -> bool:
        """检查是否处于紧急模式"""
        return self.urgency_guard.is_emergency_mode()
