"""指标收集器

收集和聚合系统指标
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""

    COUNTER = "counter"  # 计数器，只增不减
    GAUGE = "gauge"  # 仪表，可增可减
    HISTOGRAM = "histogram"  # 直方图，分布统计
    SUMMARY = "summary"  # 摘要，百分位统计


@dataclass
class Metric:
    """指标数据"""

    name: str
    type: MetricType
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    help: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp,
            "help": self.help,
        }


@dataclass
class HistogramBucket:
    """直方图桶"""

    upper_bound: float
    count: int = 0


class MetricsCollector:
    """指标收集器

    收集和管理系统指标
    """

    def __init__(self):
        """初始化指标收集器"""
        self._counters: Dict[str, Dict[tuple, float]] = defaultdict(dict)
        self._gauges: Dict[str, Dict[tuple, float]] = defaultdict(dict)
        self._histograms: Dict[str, Dict[tuple, List[HistogramBucket]]] = defaultdict(dict)
        self._histogram_sums: Dict[str, Dict[tuple, float]] = defaultdict(dict)
        self._histogram_counts: Dict[str, Dict[tuple, int]] = defaultdict(dict)

    def increment_counter(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None, help: str = ""
    ) -> None:
        """增加计数器

        Args:
            name: 指标名称
            value: 增加值
            labels: 标签
            help: 帮助信息
        """
        key = self._make_key(labels)
        if key not in self._counters[name]:
            self._counters[name][key] = 0.0
        self._counters[name][key] += value
        logger.debug(f"Counter {name} += {value}, labels={labels}")

    def set_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None, help: str = ""
    ) -> None:
        """设置仪表值

        Args:
            name: 指标名称
            value: 设置值
            labels: 标签
            help: 帮助信息
        """
        key = self._make_key(labels)
        self._gauges[name][key] = value
        logger.debug(f"Gauge {name} = {value}, labels={labels}")

    def observe_histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None, help: str = ""
    ) -> None:
        """观察直方图值

        Args:
            name: 指标名称
            value: 观察值
            labels: 标签
            help: 帮助信息
        """
        key = self._make_key(labels)

        # 如果key不存在，初始化直方图桶
        if key not in self._histograms[name]:
            self._histograms[name][key] = [
                HistogramBucket(0.5),
                HistogramBucket(1.0),
                HistogramBucket(2.5),
                HistogramBucket(5.0),
                HistogramBucket(10.0),
                HistogramBucket(float("inf")),
            ]

        buckets = self._histograms[name][key]

        # 更新桶计数
        for bucket in buckets:
            if value <= bucket.upper_bound:
                bucket.count += 1

        # 更新总和和计数
        if key not in self._histogram_sums[name]:
            self._histogram_sums[name][key] = 0.0
        if key not in self._histogram_counts[name]:
            self._histogram_counts[name][key] = 0

        self._histogram_sums[name][key] += value
        self._histogram_counts[name][key] += 1

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """获取计数器值

        Args:
            name: 指标名称
            labels: 标签

        Returns:
            计数值
        """
        key = self._make_key(labels)
        return self._counters[name][key]

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """获取仪表值

        Args:
            name: 指标名称
            labels: 标签

        Returns:
            仪表值
        """
        key = self._make_key(labels)
        return self._gauges[name][key]

    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """获取所有指标

        Returns:
            指标列表
        """
        metrics = []

        # 计数器
        for name, label_dict in self._counters.items():
            for label_key, value in label_dict.items():
                labels = self._parse_key(label_key)
                metrics.append({"name": name, "type": "counter", "value": value, "labels": labels})

        # 仪表
        for name, label_dict in self._gauges.items():
            for label_key, value in label_dict.items():
                labels = self._parse_key(label_key)
                metrics.append({"name": name, "type": "gauge", "value": value, "labels": labels})

        # 直方图
        for name, label_dict in self._histograms.items():
            for label_key, buckets in label_dict.items():
                labels = self._parse_key(label_key)
                metrics.append(
                    {
                        "name": name,
                        "type": "histogram",
                        "buckets": [
                            {"upper_bound": b.upper_bound, "count": b.count} for b in buckets
                        ],
                        "sum": self._histogram_sums[name][label_key],
                        "count": self._histogram_counts[name][label_key],
                        "labels": labels,
                    }
                )

        return metrics

    def reset(self) -> None:
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._histogram_sums.clear()
        self._histogram_counts.clear()
        logger.info("所有指标已重置")

    def _make_key(self, labels: Optional[Dict[str, str]]) -> tuple:
        """创建标签键"""
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def _parse_key(self, key: tuple) -> Dict[str, str]:
        """解析标签键"""
        return dict(key) if key else {}


# 全局指标收集器
_global_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


# 装饰器：自动记录函数调用指标
def track_metrics(metric_name: str, metric_type: MetricType = MetricType.COUNTER):
    """函数指标追踪装饰器

    Args:
        metric_name: 指标名称
        metric_type: 指标类型
    """

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                # 记录成功
                if metric_type == MetricType.COUNTER:
                    collector.increment_counter(f"{metric_name}_success")
                else:
                    duration = time.time() - start_time
                    collector.observe_histogram(f"{metric_name}_duration", duration)

                return result
            except Exception as e:
                collector.increment_counter(f"{metric_name}_error")
                raise e

        def sync_wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                if metric_type == MetricType.COUNTER:
                    collector.increment_counter(f"{metric_name}_success")
                else:
                    duration = time.time() - start_time
                    collector.observe_histogram(f"{metric_name}_duration", duration)

                return result
            except Exception as e:
                collector.increment_counter(f"{metric_name}_error")
                raise e

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
