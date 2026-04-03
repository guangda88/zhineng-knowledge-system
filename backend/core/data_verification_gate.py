"""
数据验证门禁
验证报告和决策的数据来源
"""

import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class DataVerificationGate:
    """
    数据验证门禁

    负责验证报告和决策的数据来源是否符合要求：
    1. 数据是真实的（基于静态分析或运行测试）
    2. 数据是准确的（经过二次验证）
    3. 数据是完整的（覆盖所有范围）
    """

    def __init__(self):
        """初始化门禁"""
        self.valid_data_sources = [
            "static_analysis",
            "runtime_test",
            "metrics",
            "user_feedback",
            "manual_review",
        ]

        # 日志文件路径
        self.flake8_log = "/tmp/flake8_last_run.log"
        self.pytest_log = "/tmp/pytest_last_run.log"

        logger.info("DataVerificationGate initialized")

    def verify_report_data(self, report: Dict[str, Any]) -> bool:
        """
        验证报告数据

        Args:
            report: 报告数据，应包含:
                - metadata: dict, 元数据
                    - data_source: str, 数据来源
                    - timestamp: str, 时间戳（可选）
                    - verified: bool, 是否已验证（可选）

        Returns:
            bool: 验证通过返回True

        Raises:
            ValueError: 如果验证失败
        """
        logger.info("Verifying report data...")

        # 检查metadata
        if "metadata" not in report:
            raise ValueError(
                "违反规则 12.1: 报告必须包含 metadata 字段。\n"
                "请在报告中提供 metadata 字典，包含数据来源等信息。"
            )

        metadata = report["metadata"]

        # 检查数据来源
        data_source = metadata.get("data_source")
        if not data_source:
            raise ValueError(
                "违反规则 12.1: 报告必须声明数据来源。\n"
                "请在 metadata 中添加 data_source 字段。\n"
                f"有效值: {', '.join(self.valid_data_sources)}"
            )

        # 禁止基于假设
        if data_source == "assumption":
            raise ValueError(
                "违反规则 12.1: 禁止基于假设生成决策报告。\n"
                "data_source 不能是 'assumption'。\n"
                "请使用真实数据来源。"
            )

        # 验证数据来源是否有效
        if data_source not in self.valid_data_sources:
            logger.warning(f"Unknown data_source: {data_source}")
            # 不阻止，但记录警告

        # 根据数据来源进行特定验证
        if data_source == "static_analysis":
            self._verify_static_analysis()
        elif data_source == "runtime_test":
            self._verify_runtime_test()

        # 记录验证通过
        logger.info(f"Report data verification passed (source: {data_source})")

        return True

    def _verify_static_analysis(self):
        """
        验证静态分析数据

        检查是否有近期的静态分析记录
        """
        if not os.path.exists(self.flake8_log):
            raise ValueError(
                "违反规则 12.1: 数据来源声称是静态分析，但未发现分析记录。\n"
                f"请先运行静态分析，并确保日志写入 {self.flake8_log}\n\n"
                "示例命令:\n"
                "python -m flake8 backend --select=F821 --output=/tmp/flake8_last_run.log"
            )

        # 检查日志时间戳（最近24小时内）
        mtime = os.path.getmtime(self.flake8_log)
        age_hours = (time.time() - mtime) / 3600

        if age_hours > 24:
            raise ValueError(
                f"违反规则 12.1: 静态分析记录过期（{age_hours:.1f}小时前）。\n"
                "请重新运行静态分析，确保数据是最新的。"
            )

        logger.info(f"Static analysis verified (age: {age_hours:.1f}h)")

    def _verify_runtime_test(self):
        """
        验证测试数据

        检查是否有近期的测试运行记录
        """
        if not os.path.exists(self.pytest_log):
            raise ValueError(
                "违反规则 12.1: 数据来源声称是测试，但未发现测试记录。\n"
                f"请先运行测试，并确保日志写入 {self.pytest_log}\n\n"
                "示例命令:\n"
                "python -m pytest tests/ --junitxml=/tmp/pytest_last_run.log"
            )

        # 检查日志时间戳（最近24小时内）
        mtime = os.path.getmtime(self.pytest_log)
        age_hours = (time.time() - mtime) / 3600

        if age_hours > 24:
            raise ValueError(
                f"违反规则 12.1: 测试记录过期（{age_hours:.1f}小时前）。\n"
                "请重新运行测试，确保数据是最新的。"
            )

        logger.info(f"Runtime test verified (age: {age_hours:.1f}h)")

    def validate_report_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证报告元数据的完整性

        Returns:
            dict: {valid: bool, errors: list, warnings: list}
        """
        errors = []
        warnings = []

        # 检查必需字段
        if "data_source" not in metadata:
            errors.append("metadata 中缺少 data_source 字段")

        # 检查数据来源
        data_source = metadata.get("data_source")
        if data_source == "assumption":
            errors.append("data_source 不能是 'assumption'")
        elif data_source and data_source not in self.valid_data_sources:
            warnings.append(f"未知的数据来源: {data_source}")

        # 可选字段警告
        if "timestamp" not in metadata:
            warnings.append("建议提供 timestamp 字段")

        if "verified" not in metadata:
            warnings.append("建议提供 verified 字段，说明是否已二次验证")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def get_valid_data_sources(self) -> list:
        """获取有效的数据来源列表"""
        return self.valid_data_sources.copy()

    def set_log_paths(self, flake8_log: str = None, pytest_log: str = None):
        """
        设置日志文件路径

        Args:
            flake8_log: flake8日志路径
            pytest_log: pytest日志路径
        """
        if flake8_log:
            self.flake8_log = flake8_log
        if pytest_log:
            self.pytest_log = pytest_log

        logger.info(f"Log paths updated: flake8={self.flake8_log}, pytest={self.pytest_log}")
