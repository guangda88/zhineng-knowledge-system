"""Prometheus导出器

将指标导出为Prometheus格式
"""

import time
from typing import Dict, List, Optional
import logging

from .metrics import MetricsCollector, MetricType, get_metrics_collector

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """Prometheus指标导出器

    将指标格式化为Prometheus文本格式
    """

    def __init__(self, collector: Optional[MetricsCollector] = None):
        """初始化导出器

        Args:
            collector: 指标收集器
        """
        self._collector = collector or get_metrics_collector()
        self._prefix = "zhineng_kb_"

    def set_prefix(self, prefix: str) -> None:
        """设置指标前缀

        Args:
            prefix: 前缀字符串
        """
        self._prefix = prefix

    def export(self) -> str:
        """导出Prometheus格式文本

        Returns:
            Prometheus格式的指标文本
        """
        lines = []

        # 添加基础信息
        lines.append(f"# {self._prefix}exported_at {int(time.time())}")
        lines.append("")

        # 获取所有指标
        metrics = self._collector.get_all_metrics()

        for metric in metrics:
            lines.extend(self._format_metric(metric))
            lines.append("")

        return "\n".join(lines)

    def _format_metric(self, metric: Dict) -> List[str]:
        """格式化单个指标

        Args:
            metric: 指标数据

        Returns:
            格式化后的行列表
        """
        lines = []
        name = self._prefix + metric["name"]
        labels = metric.get("labels", {})

        # 标签字符串
        label_str = self._format_labels(labels)

        if metric["type"] == "counter":
            lines.append(f"# TYPE {name} counter")
            if label_str:
                lines.append(f"{name}{{{label_str}}} {metric['value']}")
            else:
                lines.append(f"{name} {metric['value']}")

        elif metric["type"] == "gauge":
            lines.append(f"# TYPE {name} gauge")
            if label_str:
                lines.append(f"{name}{{{label_str}}} {metric['value']}")
            else:
                lines.append(f"{name} {metric['value']}")

        elif metric["type"] == "histogram":
            lines.append(f"# TYPE {name} histogram")
            base_name = name

            # 桶
            for bucket in metric.get("buckets", []):
                bucket_labels = {**labels, "le": str(bucket["upper_bound"])}
                bucket_label_str = self._format_labels(bucket_labels)
                lines.append(f"{base_name}_bucket{{{bucket_label_str}}} {bucket['count']}")

            # 总和和计数
            if label_str:
                lines.append(f"{base_name}_sum{{{label_str}}} {metric['sum']}")
                lines.append(f"{base_name}_count{{{label_str}}} {metric['count']}")
            else:
                lines.append(f"{base_name}_sum {metric['sum']}")
                lines.append(f"{base_name}_count {metric['count']}")

        return lines

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """格式化标签

        Args:
            labels: 标签字典

        Returns:
            格式化的标签字符串
        """
        if not labels:
            return ""

        pairs = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return ",".join(pairs)

    def save_to_file(self, filepath: str) -> None:
        """保存指标到文件

        Args:
            filepath: 文件路径
        """
        content = self.export()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"指标已保存到 {filepath}")
