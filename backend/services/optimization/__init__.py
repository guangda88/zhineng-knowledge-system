"""LingMinOpt自优化系统

⚠️ 实验性功能 - 未完成，不建议生产使用

提供系统自优化功能，包括反馈收集、错误分析、审计和优化执行。
详见: backend/services/optimization/README.md
"""

import warnings

from .auditor import SystemAuditor
from .error_analyzer import ErrorAnalyzer
from .feedback_collector import FeedbackCollector
from .lingminopt import LingMinOptOptimizer

# 发出实验性功能警告
warnings.warn(
    "LingMinOpt optimization system is experimental and incomplete. "
    "Not recommended for production use. "
    "See: backend/services/optimization/README.md",
    UserWarning,
    stacklevel=2,
)

__all__ = [
    "LingMinOptOptimizer",
    "FeedbackCollector",
    "ErrorAnalyzer",
    "SystemAuditor",
]
