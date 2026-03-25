"""缓存监控指标

提供缓存命中率、性能等监控指标，与Prometheus集成
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from .metrics import MetricsCollector, MetricType, get_metrics_collector

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """缓存层级"""

    L1 = "memory"
    L2 = "redis"


@dataclass
class CacheMetricData:
    """缓存指标数据"""

    # 命中统计
    hits: int = 0
    misses: int = 0

    # 分层命中统计
    l1_hits: int = 0
    l2_hits: int = 0

    # 操作统计
    sets: int = 0
    deletes: int = 0
    errors: int = 0

    # 性能统计
    total_latency: float = 0.0
    operation_count: int = 0

    # 时间窗口
    window_start: float = field(default_factory=time.time)

    @property
    def total_requests(self) -> int:
        """总请求数"""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def miss_rate(self) -> float:
        """未命中率"""
        return 1.0 - self.hit_rate

    @property
    def l1_hit_rate(self) -> float:
        """L1命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.l1_hits / self.total_requests

    @property
    def l2_hit_rate(self) -> float:
        """L2命中率"""
        if self.total_requests == 0:
            return 0.0
        return self.l2_hits / self.total_requests

    @property
    def avg_latency(self) -> float:
        """平均延迟"""
        if self.operation_count == 0:
            return 0.0
        return self.total_latency / self.operation_count

    def reset(self) -> None:
        """重置指标"""
        self.hits = 0
        self.misses = 0
        self.l1_hits = 0
        self.l2_hits = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
        self.total_latency = 0.0
        self.operation_count = 0
        self.window_start = time.time()


class CacheMetricsCollector:
    """缓存指标收集器

    收集并上报缓存相关指标到监控系统
    """

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        enabled: bool = True,
        export_interval: int = 60,
    ):
        """初始化缓存指标收集器

        Args:
            metrics_collector: 指标收集器
            enabled: 是否启用
            export_interval: 导出间隔（秒）
        """
        self._metrics = metrics_collector or get_metrics_collector()
        self._enabled = enabled

        # 分层指标
        self._l1_metrics = CacheMetricData()
        self._l2_metrics = CacheMetricData()
        self._combined_metrics = CacheMetricData()

        # 命名空间指标
        self._namespace_metrics: Dict[str, CacheMetricData] = {}

        # 操作类型指标
        self._operation_metrics: Dict[str, CacheMetricData] = {
            "get": CacheMetricData(),
            "set": CacheMetricData(),
            "delete": CacheMetricData(),
            "search": CacheMetricData(),
        }

        # 导出配置
        self._export_interval = export_interval
        self._last_export = time.time()

        # 锁
        self._lock = asyncio.Lock()

    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self._enabled

    def record_hit(
        self, level: CacheLevel = CacheLevel.L1, namespace: str = "", operation: str = "get"
    ) -> None:
        """记录缓存命中

        Args:
            level: 缓存层级
            namespace: 命名空间
            operation: 操作类型
        """
        if not self._enabled:
            return

        self._combined_metrics.hits += 1

        if level == CacheLevel.L1:
            self._l1_metrics.hits += 1
            self._combined_metrics.l1_hits += 1
        else:
            self._l2_metrics.hits += 1
            self._combined_metrics.l2_hits += 1

        # 命名空间指标
        if namespace:
            if namespace not in self._namespace_metrics:
                self._namespace_metrics[namespace] = CacheMetricData()
            self._namespace_metrics[namespace].hits += 1

        # 操作指标
        if operation in self._operation_metrics:
            self._operation_metrics[operation].hits += 1

        # Prometheus指标
        self._metrics.increment_counter(
            "cache_hits_total",
            labels={
                "level": level.value,
                "namespace": namespace or "default",
                "operation": operation,
            },
        )

    def record_miss(self, namespace: str = "", operation: str = "get") -> None:
        """记录缓存未命中

        Args:
            namespace: 命名空间
            operation: 操作类型
        """
        if not self._enabled:
            return

        self._combined_metrics.misses += 1

        # 命名空间指标
        if namespace:
            if namespace not in self._namespace_metrics:
                self._namespace_metrics[namespace] = CacheMetricData()
            self._namespace_metrics[namespace].misses += 1

        # 操作指标
        if operation in self._operation_metrics:
            self._operation_metrics[operation].misses += 1

        # Prometheus指标
        self._metrics.increment_counter(
            "cache_misses_total",
            labels={
                "namespace": namespace or "default",
                "operation": operation,
            },
        )

    def record_set(self, namespace: str = "") -> None:
        """记录缓存设置

        Args:
            namespace: 命名空间
        """
        if not self._enabled:
            return

        self._combined_metrics.sets += 1

        if namespace:
            if namespace not in self._namespace_metrics:
                self._namespace_metrics[namespace] = CacheMetricData()
            self._namespace_metrics[namespace].sets += 1

        self._metrics.increment_counter(
            "cache_sets_total", labels={"namespace": namespace or "default"}
        )

    def record_delete(self, namespace: str = "") -> None:
        """记录缓存删除

        Args:
            namespace: 命名空间
        """
        if not self._enabled:
            return

        self._combined_metrics.deletes += 1

        if namespace:
            if namespace not in self._namespace_metrics:
                self._namespace_metrics[namespace] = CacheMetricData()
            self._namespace_metrics[namespace].deletes += 1

        self._metrics.increment_counter(
            "cache_deletes_total", labels={"namespace": namespace or "default"}
        )

    def record_error(self, level: CacheLevel = CacheLevel.L1, error_type: str = "unknown") -> None:
        """记录缓存错误

        Args:
            level: 缓存层级
            error_type: 错误类型
        """
        if not self._enabled:
            return

        self._combined_metrics.errors += 1

        if level == CacheLevel.L1:
            self._l1_metrics.errors += 1
        else:
            self._l2_metrics.errors += 1

        self._metrics.increment_counter(
            "cache_errors_total", labels={"level": level.value, "type": error_type}
        )

    def record_latency(self, duration: float, operation: str = "get") -> None:
        """记录操作延迟

        Args:
            duration: 延迟时间（秒）
            operation: 操作类型
        """
        if not self._enabled:
            return

        self._combined_metrics.total_latency += duration
        self._combined_metrics.operation_count += 1

        if operation in self._operation_metrics:
            self._operation_metrics[operation].total_latency += duration
            self._operation_metrics[operation].operation_count += 1

        # Prometheus直方图（使用字符串键而非字典）
        try:
            self._metrics.observe_histogram(
                "cache_operation_duration_seconds", duration, labels={"operation": operation}
            )
        except Exception as e:
            # 如果直方图记录失败，只记录日志，不影响主流程
            logger.debug(f"记录延迟直方图失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息字典
        """
        return {
            "combined": {
                "hits": self._combined_metrics.hits,
                "misses": self._combined_metrics.misses,
                "hit_rate": round(self._combined_metrics.hit_rate, 4),
                "miss_rate": round(self._combined_metrics.miss_rate, 4),
                "sets": self._combined_metrics.sets,
                "deletes": self._combined_metrics.deletes,
                "errors": self._combined_metrics.errors,
                "avg_latency_ms": round(self._combined_metrics.avg_latency * 1000, 2),
            },
            "l1": {
                "hits": self._l1_metrics.hits,
                "hit_rate": round(self._l1_metrics.hit_rate, 4),
                "errors": self._l1_metrics.errors,
            },
            "l2": {
                "hits": self._l2_metrics.hits,
                "hit_rate": round(self._l2_metrics.hit_rate, 4),
                "errors": self._l2_metrics.errors,
            },
            "namespaces": {
                ns: {
                    "hits": metrics.hits,
                    "misses": metrics.misses,
                    "hit_rate": round(metrics.hit_rate, 4),
                }
                for ns, metrics in self._namespace_metrics.items()
            },
            "operations": {
                op: {
                    "hits": metrics.hits,
                    "misses": metrics.misses,
                    "hit_rate": round(metrics.hit_rate, 4),
                    "avg_latency_ms": round(metrics.avg_latency * 1000, 2),
                }
                for op, metrics in self._operation_metrics.items()
            },
        }

    def get_prometheus_metrics(self) -> str:
        """获取Prometheus格式的指标

        Returns:
            Prometheus格式文本
        """
        lines = []
        stats = self.get_stats()

        # 命中率Gauge
        lines.append("# TYPE cache_hit_rate gauge")
        lines.append(f"cache_hit_rate {{level=\"combined\"}} {stats['combined']['hit_rate']}")
        lines.append(f"cache_hit_rate {{level=\"l1\"}} {stats['l1']['hit_rate']}")
        lines.append(f"cache_hit_rate {{level=\"l2\"}} {stats['l2']['hit_rate']}")

        # 未命中率Gauge
        lines.append("# TYPE cache_miss_rate gauge")
        lines.append(f"cache_miss_rate {stats['combined']['miss_rate']}")

        # 总请求数Gauge
        lines.append("# TYPE cache_requests_total gauge")
        lines.append(
            f"cache_requests_total {stats['combined']['hits'] + stats['combined']['misses']}"
        )

        # 平均延迟Gauge
        lines.append("# TYPE cache_avg_latency_seconds gauge")
        lines.append(f"cache_avg_latency_seconds {self._combined_metrics.avg_latency}")

        # 命名空间指标
        for ns, ns_stats in stats.get("namespaces", {}).items():
            lines.append(f"cache_namespace_hit_rate {{namespace=\"{ns}\"}} {ns_stats['hit_rate']}")

        return "\n".join(lines)

    def reset(self) -> None:
        """重置所有指标"""
        self._l1_metrics.reset()
        self._l2_metrics.reset()
        self._combined_metrics.reset()
        self._namespace_metrics.clear()
        for metrics in self._operation_metrics.values():
            metrics.reset()

    async def start_periodic_export(self) -> None:
        """启动定期导出任务"""
        if not self._enabled:
            return

        async def export_loop():
            while True:
                await asyncio.sleep(self._export_interval)
                await self.export_metrics()

        asyncio.create_task(export_loop())
        logger.info(f"缓存指标定期导出已启动，间隔: {self._export_interval}秒")

    async def export_metrics(self) -> None:
        """导出指标到监控系统"""
        if not self._enabled:
            return

        stats = self.get_stats()

        # 导出命中率Gauge
        self._metrics.set_gauge(
            "cache_hit_rate", stats["combined"]["hit_rate"], labels={"level": "combined"}
        )
        self._metrics.set_gauge("cache_hit_rate", stats["l1"]["hit_rate"], labels={"level": "l1"})
        self._metrics.set_gauge("cache_hit_rate", stats["l2"]["hit_rate"], labels={"level": "l2"})

        # 导出平均延迟
        self._metrics.set_gauge("cache_avg_latency_ms", stats["combined"]["avg_latency_ms"])

        self._last_export = time.time()
        logger.debug("缓存指标已导出到监控系统")


class CacheMetricsMiddleware:
    """缓存指标中间件

    自动记录缓存操作的指标
    """

    def __init__(self, collector: CacheMetricsCollector):
        """初始化中间件

        Args:
            collector: 缓存指标收集器
        """
        self._collector = collector

    async def track_get(
        self, key: str, namespace: str, get_fn, level: CacheLevel = CacheLevel.L1
    ) -> Any:
        """追踪GET操作

        Args:
            key: 缓存键
            namespace: 命名空间
            get_fn: 获取函数
            level: 缓存层级

        Returns:
            缓存值或None
        """
        start_time = time.time()
        try:
            value = await get_fn()
            duration = time.time() - start_time

            if value is not None:
                self._collector.record_hit(level, namespace, "get")
            else:
                self._collector.record_miss(namespace, "get")

            self._collector.record_latency(duration, "get")
            return value

        except Exception as e:
            self._collector.record_error(level, type(e).__name__)
            raise

    async def track_set(
        self,
        key: str,
        value: Any,
        namespace: str,
        set_fn,
    ) -> bool:
        """追踪SET操作

        Args:
            key: 缓存键
            value: 缓存值
            namespace: 命名空间
            set_fn: 设置函数

        Returns:
            是否成功
        """
        start_time = time.time()
        try:
            result = await set_fn()
            duration = time.time() - start_time

            if result:
                self._collector.record_set(namespace)
            else:
                self._collector.record_error(CacheLevel.L1, "set_failed")

            self._collector.record_latency(duration, "set")
            return result

        except Exception as e:
            self._collector.record_error(CacheLevel.L1, type(e).__name__)
            raise


# 全局缓存指标收集器
_global_cache_metrics: Optional[CacheMetricsCollector] = None


def get_cache_metrics_collector() -> CacheMetricsCollector:
    """获取全局缓存指标收集器

    Returns:
        缓存指标收集器实例
    """
    global _global_cache_metrics
    if _global_cache_metrics is None:
        _global_cache_metrics = CacheMetricsCollector()
    return _global_cache_metrics


def setup_cache_metrics(
    enabled: bool = True,
    export_interval: int = 60,
) -> CacheMetricsCollector:
    """设置缓存指标收集

    Args:
        enabled: 是否启用
        export_interval: 导出间隔

    Returns:
        缓存指标收集器
    """
    global _global_cache_metrics
    _global_cache_metrics = CacheMetricsCollector(
        enabled=enabled,
        export_interval=export_interval,
    )
    logger.info(f"缓存指标收集器已初始化: enabled={enabled}")
    return _global_cache_metrics
