"""
规则修改检查器
检查规则修改操作是否符合流程
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RulesChecker:
    """
    规则修改检查器

    负责检查规则修改操作是否符合以下要求：
    1. 是否已讨论（规则 4.4.1）
    2. 基于真实数据（规则 4.4.2）
    3. 是否达成共识（规则 4.4.3）
    """

    def __init__(self):
        """初始化检查器"""
        self.required_fields = {
            "discussed": "规则修改前必须经过讨论（规则 4.4.1）",
            "data_source": "必须基于真实测量数据修改规则（规则 4.4.2）",
            "consensus": "规则修改必须获得团队共识（规则 4.4.3）"
        }

        logger.info("RulesChecker initialized")

    def check_modify_rules(self, action_data: Dict[str, Any]) -> bool:
        """
        检查规则修改操作

        Args:
            action_data: 操作数据，应包含:
                - discussed: bool, 是否已讨论
                - data_source: str, 数据来源（不能是"assumption"）
                - consensus: bool, 是否达成共识
                - discussion_summary: str, 讨论摘要（可选）
                - participants: list, 参与者（可选）

        Returns:
            bool: 检查通过返回True

        Raises:
            PermissionError: 如果检查失败
        """
        logger.info("Checking rules modification...")

        # 检查 4.4.1: 是否已讨论
        if not action_data.get("discussed"):
            raise PermissionError(
                "违反规则 4.4.1: 规则修改前必须经过讨论。\n"
                "请先使用 AskUserQuestion 组织讨论，收集各方意见。"
            )

        # 检查 4.4.2: 基于真实数据
        data_source = action_data.get("data_source")
        if not data_source:
            raise PermissionError(
                "违反规则 4.4.2: 必须基于真实测量数据修改规则。\n"
                "请在 action_data 中提供 data_source 字段。"
            )

        if data_source == "assumption":
            raise PermissionError(
                "违反规则 4.4.2: 禁止基于假设修改规则。\n"
                "data_source 不能是 'assumption'。\n"
                "有效值包括: 'static_analysis', 'runtime_test', 'metrics', 'user_feedback' 等。"
            )

        # 检查 4.4.3: 是否达成共识
        if not action_data.get("consensus"):
            raise PermissionError(
                "违反规则 4.4.3: 规则修改必须获得团队共识。\n"
                "请在 action_data 中提供 consensus=True，并记录讨论结果。"
            )

        # 记录检查通过
        logger.info("Rules modification check passed")

        # 可选：记录详细信息
        if "discussion_summary" in action_data:
            logger.info(f"Discussion summary: {action_data['discussion_summary']}")

        if "participants" in action_data:
            logger.info(f"Participants: {action_data['participants']}")

        return True

    def validate_action_data(self, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证操作数据的完整性

        Returns:
            dict: {valid: bool, errors: list, warnings: list}
        """
        errors = []
        warnings = []

        # 检查必需字段
        for field, description in self.required_fields.items():
            if field not in action_data:
                errors.append(f"缺少必需字段: {field} - {description}")

        # 检查数据来源
        data_source = action_data.get("data_source")
        if data_source == "assumption":
            errors.append("data_source 不能是 'assumption'")

        # 可选字段警告
        if "discussion_summary" not in action_data:
            warnings.append("建议提供 discussion_summary 字段，记录讨论摘要")

        if "participants" not in action_data:
            warnings.append("建议提供 participants 字段，记录参与者")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def get_required_fields(self) -> Dict[str, str]:
        """获取必需字段及其说明"""
        return self.required_fields.copy()
