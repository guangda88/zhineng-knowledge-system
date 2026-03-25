# -*- coding: utf-8 -*-
"""
性能指标收集器
Performance Metrics Collector

提供API请求和系统性能指标收集
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """指标类型"""

    COUNTER = "counter"  # 计数器（只增不减）
    GAUGE = "gauge"  # 仪表盘（可增可减）
    HISTOGRAM = "histogram"  # 直方图（分布统计）
    SUMMARY = "summary"  # 摘要（统计信息）


@dataclass
class MetricValue:
    """指标值"""

    name: str
    type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    help: str = ""


@dataclass
class HistogramBucket:
    """直方图桶"""

    count: int = 0
    sum: float = 0.0
    buckets: Dict[float, int] = field(default_factory=dict)


class MetricsRegistry:
    """
    指标注册表

    管理所有指标的注册和查询
    """

    def __init__(self):
        self._counters: Dict[str, Dict[tuple, float]] = defaultdict(float)
        self._gauges: Dict[str, Dict[tuple, float]] = defaultdict(float)
        self._histograms: Dict[str, Dict[tuple, HistogramBucket]] = defaultdict(
            lambda: HistogramBucket(
                buckets={
                    0.005: 0,
                    0.01: 0,
                    0.025: 0,
                    0.05: 0,
                    0.1: 0,
                    0.25: 0,
                    0.5: 0,
                    1.0: 0,
                    2.5: 0,
                    5.0: 0,
                    10.0: 0,
                    float("inf"): 0,
                }
            )
        )
        self._lock = asyncio.Lock()

    def _make_label_key(self, labels: Dict[str, str]) -> tuple:
        """将标签字典转换为可哈希的元组"""
        return tuple(sorted(labels.items()))

    async def inc(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        增加计数器

        Args:
            name: 指标名称
            value: 增加值（默认1）
            labels: 标签
        """
        async with self._lock:
            key = self._make_label_key(labels or {})
            self._counters[name][key] += value

    async def set(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        设置仪表盘值

        Args:
            name: 指标名称
            value: 设置的值
            labels: 标签
        """
        async with self._lock:
            key = self._make_label_key(labels or {})
            self._gauges[name][key] = value

    async def observe(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        观察直方图值

        Args:
            name: 指标名称
            value: 观察值
            labels: 标签
        """
        async with self._lock:
            key = self._make_label_key(labels or {})
            bucket = self._histograms[name][key]
            bucket.count += 1
            bucket.sum += value

            for threshold in sorted(bucket.buckets.keys()):
                if value <= threshold:
                    bucket.buckets[threshold] += 1

    async def get_counter(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> float:
        """获取计数器值"""
        key = self._make_label_key(labels or {})
        return self._counters.get(name, {}).get(key, 0.0)

    async def get_gauge(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> float:
        """获取仪表盘值"""
        key = self._make_label_key(labels or {})
        return self._gauges.get(name, {}).get(key, 0.0)

    def get_all_metrics(self) -> List[MetricValue]:
        """获取所有指标"""
        metrics = []

        # 添加计数器
        for name, label_dict in self._counters.items():
            for label_tuple, value in label_dict.items():
                metrics.append(
                    MetricValue(
                        name=name,
                        type=MetricType.COUNTER,
                        value=value,
                        labels=dict(label_tuple),
                    )
                )

        # 添加仪表盘
        for name, label_dict in self._gauges.items():
            for label_tuple, value in label_dict.items():
                metrics.append(
                    MetricValue(
                        name=name,
                        type=MetricType.GAUGE,
                        value=value,
                        labels=dict(label_tuple),
                    )
                )

        return metrics

    async def reset(self) -> None:
        """重置所有指标"""
        async with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# 全局指标注册表
registry = MetricsRegistry()


# 预定义的指标
class APIMetrics:
    """API相关指标"""

    # 请求总数
    REQUESTS_TOTAL = "api_requests_total"
    # 请求持续时间
    REQUEST_DURATION = "api_request_duration_seconds"
    # 活动请求数
    ACTIVE_REQUESTS = "api_active_requests"
    # 请求错误数
    ERRORS_TOTAL = "api_errors_total"
    # 重试次数
    RETRIES_TOTAL = "api_retries_total"

    @staticmethod
    async def inc_request(provider: str, endpoint: str, status: str) -> None:
        """增加请求计数"""
        await registry.inc(
            APIMetrics.REQUESTS_TOTAL,
            labels={"provider": provider, "endpoint": endpoint, "status": status},
        )

    @staticmethod
    async def observe_duration(provider: str, duration: float) -> None:
        """观察请求持续时间"""
        await registry.observe(
            APIMetrics.REQUEST_DURATION, duration, labels={"provider": provider}
        )

    @staticmethod
    async def inc_error(provider: str, error_type: str) -> None:
        """增加错误计数"""
        await registry.inc(
            APIMetrics.ERRORS_TOTAL,
            labels={"provider": provider, "error_type": error_type},
        )

    @staticmethod
    async def inc_retry(provider: str) -> None:
        """增加重试计数"""
        await registry.inc(APIMetrics.RETRIES_TOTAL, labels={"provider": provider})


class CacheMetrics:
    """缓存相关指标"""

    HITS = "cache_hits_total"
    MISSES = "cache_misses_total"
    SIZE = "cache_size"
    EVICTIONS = "cache_evictions_total"

    @staticmethod
    async def inc_hit(namespace: str) -> None:
        """增加缓存命中计数"""
        await registry.inc(CacheMetrics.HITS, labels={"namespace": namespace})

    @staticmethod
    async def inc_miss(namespace: str) -> None:
        """增加缓存未命中计数"""
        await registry.inc(CacheMetrics.MISSES, labels={"namespace": namespace})


class ModelMetrics:
    """模型相关指标"""

    LOAD_TIME = "model_load_time_seconds"
    INFERENCE_TIME = "model_inference_time_seconds"
    BATCH_SIZE = "model_batch_size"
    MEMORY_USAGE = "model_memory_usage_bytes"

    @staticmethod
    async def observe_inference(model_name: str, duration: float) -> None:
        """观察推理时间"""
        await registry.observe(
            ModelMetrics.INFERENCE_TIME, duration, labels={"model": model_name}
        )


def track_time(
    metric_name: str,
    labels: Optional[Dict[str, str]] = None,
):
    """
    跟踪函数执行时间的装饰器

    使用示例:
        @track_time("function_duration", {"module": "api"})
        async def my_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                await registry.observe(metric_name, duration, labels)

        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                # 同步版本需要特殊处理
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            registry.observe(metric_name, duration, labels)
                        )
                    else:
                        loop.run_until_complete(
                            registry.observe(metric_name, duration, labels)
                        )
                except RuntimeError:
                    pass  # 没有事件循环，忽略

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class RequestTracker:
    """
    请求跟踪器

    跟踪单个请求的完整生命周期
    """

    def __init__(self, provider: str, endpoint: str):
        self.provider = provider
        self.endpoint = endpoint
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.status: Optional[str] = None
        self.error: Optional[str] = None
        self.retry_count = 0

    async def record_success(self, status: str = "success") -> None:
        """记录请求成功"""
        self.end_time = time.time()
        self.status = status
        duration = self.end_time - self.start_time

        await APIMetrics.inc_request(self.provider, self.endpoint, status)
        await APIMetrics.observe_duration(self.provider, duration)

    async def record_error(self, error: str) -> None:
        """记录请求错误"""
        self.end_time = time.time()
        self.status = "error"
        self.error = error
        duration = self.end_time - self.start_time

        await APIMetrics.inc_request(self.provider, self.endpoint, "error")
        await APIMetrics.inc_error(self.provider, error)
        await APIMetrics.observe_duration(self.provider, duration)

    def record_retry(self) -> None:
        """记录重试"""
        self.retry_count += 1

    @property
    def duration(self) -> Optional[float]:
        """获取请求持续时间"""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def info(self) -> Dict[str, Any]:
        """获取请求信息"""
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "status": self.status,
            "error": self.error,
            "duration": self.duration,
            "retry_count": self.retry_count,
        }


if __name__ == "__main__":
    # 测试代码
    async def test_metrics():
        # 测试计数器
        await APIMetrics.inc_request("openai", "/chat/completions", "success")
        await APIMetrics.inc_request("openai", "/chat/completions", "success")
        await APIMetrics.inc_request("qwen", "/chat/completions", "error")

        # 测试持续时间
        await APIMetrics.observe_duration("openai", 0.5)
        await APIMetrics.observe_duration("openai", 1.2)
        await APIMetrics.observe_duration("qwen", 0.8)

        # 获取所有指标
        metrics = registry.get_all_metrics()
        print(f"Total metrics: {len(metrics)}")
        for metric in metrics[:5]:
            print(f"  {metric.name}: {metric.value}")

        # 测试装饰器
        @track_time("test_function", {"test": "true"})
        async def test_function():
            await asyncio.sleep(0.1)
            return "done"

        await test_function()

        # 查看计数器值
        counter_value = await registry.get_counter(
            APIMetrics.REQUESTS_TOTAL,
            labels={
                "provider": "openai",
                "endpoint": "/chat/completions",
                "status": "success",
            },
        )
        print(f"\nOpenAI success requests: {counter_value}")

    asyncio.run(test_metrics())
