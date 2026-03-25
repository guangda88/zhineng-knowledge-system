# -*- coding: utf-8 -*-
"""
分布式追踪系统 V2
Distributed Tracing System V2
"""

import logging
import time
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from contextlib import contextmanager
from functools import wraps
import uuid
import json

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """Span类型"""
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"


class StatusCode(str, Enum):
    """状态码"""
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


@dataclass
class TraceConfig:
    """追踪配置"""
    service_name: str = "zbox-knowledge-system"
    service_version: str = "1.0.0"
    sample_rate: float = 1.0
    slow_threshold_ms: int = 1000
    otlp_endpoint: str = "http://localhost:4317"


@dataclass
class SpanContext:
    """Span上下文"""
    span_id: str
    parent_span_id: Optional[str] = None
    trace_id: str
    start_time: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)


class SimpleDistributedTracer:
    """
    简化的分布式追踪器
    """
    
    def __init__(self, config: Optional[TraceConfig] = None):
        self.config = config or TraceConfig()
        self.active_spans: Dict[str, SpanContext] = {}
        self.stats = {
            "total_spans": 0,
            "total_errors": 0,
            "avg_duration_ms": 0.0,
            "slow_requests": 0,
        }
        logger.info("Simple Distributed Tracer initialized")
    
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.SERVER,
        parent: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """开始Span"""
        span_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        
        span_context = SpanContext(
            span_id=span_id,
            parent_span_id=parent,
            trace_id=trace_id,
            start_time=time.time(),
            attributes=attributes or {},
        )
        
        self.active_spans[span_id] = span_context
        self.stats["total_spans"] += 1
        
        logger.debug(f"Span started: {name} (id: {span_id})")
        return span_id
    
    def end_span(
        self,
        span_id: str,
        status: StatusCode = StatusCode.OK,
        error: Optional[Exception] = None,
    ):
        """结束Span"""
        if span_id not in self.active_spans:
            return
        
        span = self.active_spans[span_id]
        duration_ms = (time.time() - span.start_time) * 1000
        
        # 更新统计
        if status == StatusCode.ERROR:
            self.stats["total_errors"] += 1
        
        if duration_ms > self.config.slow_threshold_ms:
            self.stats["slow_requests"] += 1
        
        # 更新平均持续时间
        n = self.stats["total_spans"]
        old_avg = self.stats["avg_duration_ms"]
        new_avg = (old_avg * (n - 1) + duration_ms) / n
        self.stats["avg_duration_ms"] = new_avg
        
        # 移除活跃Span
        del self.active_spans[span_id]
        
        logger.debug(f"Span ended: {span_id} (duration: {duration_ms:.2f}ms)")
    
    @contextmanager
    def trace(
        self,
        name: str,
        kind: SpanKind = SpanKind.SERVER,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """追踪上下文管理器"""
        span_id = self.start_span(name, kind, attributes=attributes)
        
        try:
            yield span_id
        except Exception as e:
            self.end_span(span_id, status=StatusCode.ERROR, error=e)
            raise
        else:
            self.end_span(span_id, status=StatusCode.OK)
    
    def trace_function(self, name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
        """函数追踪装饰器"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                span_name = name or f"{func.__module__}.{func.__name__}"
                with self.trace(span_name, attributes=attributes):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_trace_id(self, span_id: str) -> Optional[str]:
        """获取Trace ID"""
        if span_id in self.active_spans:
            return self.active_spans[span_id].trace_id
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_spans": len(self.active_spans),
            **self.stats,
        }


# 全局追踪器实例
simple_tracer: Optional[SimpleDistributedTracer] = None


def init_simple_tracer(config: Optional[TraceConfig] = None) -> SimpleDistributedTracer:
    """初始化简单追踪器"""
    global simple_tracer
    simple_tracer = SimpleDistributedTracer(config=config)
    logger.info("Simple Tracer initialized")
    return simple_tracer


__all__ = [
    "SpanKind",
    "StatusCode",
    "TraceConfig",
    "SpanContext",
    "SimpleDistributedTracer",
    "simple_tracer",
    "init_simple_tracer",
]
