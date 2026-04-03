"""错误分析器

分析系统错误，识别优化机会
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .lingminopt import OptimizationOpportunity, OptimizationPriority, OptimizationSource

logger = logging.getLogger(__name__)


class ErrorAnalyzer:
    """错误分析器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 模拟错误数据
        self.error_log = []

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: str,
        context: Dict = None,
        severity: str = "error",
    ) -> str:
        """
        记录系统错误

        Args:
            error_type: 错误类型
            error_message: 错误消息
            stack_trace: 堆栈跟踪
            context: 上下文信息
            severity: 严重程度（error, warning, critical）

        Returns:
            str: 错误ID
        """
        error_id = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        error_entry = {
            "error_id": error_id,
            "type": error_type,
            "message": error_message,
            "stack_trace": stack_trace,
            "context": context or {},
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "occurrences": 1,
        }

        self.error_log.append(error_entry)
        logger.error(f"记录错误: {error_id} - {error_message}")

        return error_id

    async def analyze_errors(self) -> Dict[str, Any]:
        """
        分析错误日志

        生成错误统计和洞察
        """
        if not self.error_log:
            return {"message": "暂无错误数据"}

        # 按类型统计
        type_counts = Counter(e["type"] for e in self.error_log)

        # 按严重程度统计
        severity_counts = Counter(e["severity"] for e in self.error_log)

        # 最近24小时的错误
        cutoff = datetime.now() - timedelta(hours=24)
        recent_errors = [
            e for e in self.error_log if datetime.fromisoformat(e["timestamp"]) > cutoff
        ]

        # 识别高频错误
        high_frequency_errors = self._identify_high_frequency_errors(threshold=5)

        # 识别错误趋势
        error_trend = self._analyze_error_trend()

        return {
            "total_errors": len(self.error_log),
            "by_type": dict(type_counts.most_common(10)),
            "by_severity": dict(severity_counts),
            "last_24h_count": len(recent_errors),
            "high_frequency_errors": high_frequency_errors,
            "error_trend": error_trend,
        }

    async def identify_optportunities(self) -> List[OptimizationOpportunity]:
        """
        从错误中识别优化机会
        """
        opportunities = []

        # 1. 高频错误
        high_freq_errors = self._identify_high_frequency_errors(threshold=5)
        for error_info in high_freq_errors:
            opportunity = OptimizationOpportunity(
                id=f"opt_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                title=f"修复高频错误: {error_info['type']}",
                description=f"该错误在过去24小时内发生了{error_info['count']}次",
                source=OptimizationSource.SYSTEM_ERROR,
                priority=(
                    OptimizationPriority.CRITICAL
                    if error_info["count"] > 20
                    else OptimizationPriority.HIGH
                ),
                category="functionality",
                current_state={"error_count": error_info["count"]},
                desired_state={"error_count": 0},
                impact_estimate="显著提升系统稳定性",
                effort_estimate="medium",
            )
            opportunities.append(opportunity)

        # 2. 性能错误
        performance_errors = [
            e
            for e in self.error_log
            if "timeout" in e["type"].lower() or "slow" in e["type"].lower()
        ]
        if len(performance_errors) >= 10:
            opportunity = OptimizationOpportunity(
                id=f"opt_perf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                title="优化系统性能",
                description=f"检测到{len(performance_errors)}次性能相关错误",
                source=OptimizationSource.SYSTEM_ERROR,
                priority=OptimizationPriority.HIGH,
                category="performance",
                current_state={"performance_errors": len(performance_errors)},
                desired_state={"performance_errors": 0},
                impact_estimate="提升响应速度",
                effort_estimate="high",
            )
            opportunities.append(opportunity)

        # 3. 内存泄漏
        memory_errors = [
            e for e in self.error_log if "memory" in e["type"].lower() or "oom" in e["type"].lower()
        ]
        if len(memory_errors) >= 3:
            opportunity = OptimizationOpportunity(
                id=f"opt_memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                title="修复内存泄漏",
                description=f"检测到{len(memory_errors)}次内存相关错误",
                source=OptimizationSource.SYSTEM_ERROR,
                priority=OptimizationPriority.CRITICAL,
                category="performance",
                current_state={"memory_errors": len(memory_errors)},
                desired_state={"memory_errors": 0},
                impact_estimate="防止系统崩溃",
                effort_estimate="high",
            )
            opportunities.append(opportunity)

        return opportunities

    def _identify_high_frequency_errors(self, threshold: int = 5) -> List[Dict[str, Any]]:
        """识别高频错误"""
        # 按类型分组
        errors_by_type = defaultdict(list)
        for error in self.error_log:
            errors_by_type[error["type"]].append(error)

        # 筛选高频错误
        high_freq = []
        cutoff = datetime.now() - timedelta(hours=24)

        for error_type, errors in errors_by_type.items():
            # 统计最近24小时的发生次数
            recent_count = sum(1 for e in errors if datetime.fromisoformat(e["timestamp"]) > cutoff)

            if recent_count >= threshold:
                high_freq.append(
                    {
                        "type": error_type,
                        "count": recent_count,
                        "total": len(errors),
                        "last_occurrence": max(e["timestamp"] for e in errors),
                    }
                )

        # 按发生次数排序
        high_freq.sort(key=lambda x: x["count"], reverse=True)

        return high_freq

    def _analyze_error_trend(self) -> str:
        """分析错误趋势"""
        if len(self.error_log) < 10:
            return "insufficient_data"

        # 简单趋势分析：比较前后两个时间段
        mid_point = len(self.error_log) // 2
        first_half = self.error_log[:mid_point]
        second_half = self.error_log[mid_point:]

        # 计算平均每小时错误数
        def get_hour_span(errors):
            if len(errors) < 2:
                return 1
            times = [datetime.fromisoformat(e["timestamp"]) for e in errors]
            return max(1, (max(times) - min(times)).total_seconds() / 3600)

        first_rate = len(first_half) / get_hour_span(first_half)
        second_rate = len(second_half) / get_hour_span(second_half)

        if second_rate > first_rate * 1.5:
            return "increasing"
        elif second_rate < first_rate * 0.5:
            return "decreasing"
        else:
            return "stable"
