"""异常检测器

自进化计划 E1: 基于阈值的异常检测
监控：检索延迟、API错误率、429频率、数据库连接、磁盘空间
超过阈值时记录告警，连续触发时回调通知（可接灵信/LingBus）

用法:
    from backend.monitoring.anomaly_detector import get_anomaly_detector
    detector = get_anomaly_detector()
    await detector.start()
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Deque, Dict, List, Optional

from .health import HealthStatus

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    level: AlertLevel
    rule_name: str
    message: str
    value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "rule_name": self.rule_name,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class ThresholdRule:
    name: str
    metric: str
    warning_threshold: float
    critical_threshold: float
    window_seconds: float = 60.0
    min_samples: int = 3
    description: str = ""


class AnomalyDetector:
    def __init__(self):
        self._rules: Dict[str, ThresholdRule] = {}
        self._buffers: Dict[str, Deque[tuple]] = {}
        self._callbacks: List[Callable[[Alert], Coroutine]] = []
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: Deque[Alert] = deque(maxlen=200)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 30.0

    def add_rule(self, rule: ThresholdRule) -> None:
        self._rules[rule.name] = rule
        if rule.name not in self._buffers:
            self._buffers[rule.name] = deque(maxlen=500)

    def remove_rule(self, name: str) -> None:
        self._rules.pop(name, None)
        self._buffers.pop(name, None)
        self._active_alerts.pop(name, None)

    def add_callback(self, callback: Callable[[Alert], Coroutine]) -> None:
        self._callbacks.append(callback)

    def observe(self, metric: str, value: float, **details: Any) -> None:
        now = time.time()
        for rule_name, rule in self._rules.items():
            if rule.metric == metric:
                self._buffers[rule_name].append((now, value, details))

    def check_rule(self, rule_name: str) -> Optional[Alert]:
        if rule_name not in self._rules:
            return None

        rule = self._rules[rule_name]
        buf = self._buffers.get(rule_name, deque())
        now = time.time()
        cutoff = now - rule.window_seconds

        samples = [(ts, val) for ts, val, _ in buf if ts >= cutoff]
        if len(samples) < rule.min_samples:
            return None

        values = [v for _, v in samples]
        avg = sum(values) / len(values)
        max_val = max(values)

        if max_val >= rule.critical_threshold:
            return Alert(
                level=AlertLevel.CRITICAL,
                rule_name=rule_name,
                message=f"{rule.description or rule.metric}: {max_val:.1f} >= {rule.critical_threshold:.1f} (CRITICAL, avg={avg:.1f})",
                value=max_val,
                threshold=rule.critical_threshold,
                details={"avg": avg, "samples": len(samples), "window_s": rule.window_seconds},
            )
        if avg >= rule.warning_threshold:
            return Alert(
                level=AlertLevel.WARNING,
                rule_name=rule_name,
                message=f"{rule.description or rule.metric}: {avg:.1f} >= {rule.warning_threshold:.1f} (WARNING, max={max_val:.1f})",
                value=avg,
                threshold=rule.warning_threshold,
                details={"max": max_val, "samples": len(samples), "window_s": rule.window_seconds},
            )

        self._active_alerts.pop(rule_name, None)
        return None

    async def check_all(self) -> List[Alert]:
        new_alerts = []
        for rule_name in list(self._rules.keys()):
            alert = self.check_rule(rule_name)
            if alert is None:
                continue

            prev = self._active_alerts.get(rule_name)
            if prev and prev.level == alert.level:
                continue

            self._active_alerts[rule_name] = alert
            self._alert_history.append(alert)
            new_alerts.append(alert)

            for cb in self._callbacks:
                try:
                    await cb(alert)
                except Exception as e:
                    logger.error(f"告警回调失败: {e}")

        return new_alerts

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("异常检测器已启动")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("异常检测器已停止")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"异常检测循环出错: {e}")
                await asyncio.sleep(5)

    def get_active_alerts(self) -> Dict[str, Alert]:
        return dict(self._active_alerts)

    def get_history(self, limit: int = 50) -> List[Alert]:
        return list(self._alert_history)[-limit:]

    def get_status(self) -> Dict[str, Any]:
        active = self.get_active_alerts()
        if any(a.level == AlertLevel.CRITICAL for a in active.values()):
            status = HealthStatus.UNHEALTHY.value
        elif active:
            status = HealthStatus.DEGRADED.value
        else:
            status = HealthStatus.HEALTHY.value
        return {
            "status": status,
            "rules": len(self._rules),
            "active_alerts": {k: v.to_dict() for k, v in active.items()},
            "history_size": len(self._alert_history),
            "running": self._running,
        }


DEFAULT_RULES = [
    ThresholdRule(
        name="search_latency",
        metric="search_latency_ms",
        warning_threshold=2000.0,
        critical_threshold=5000.0,
        window_seconds=120.0,
        min_samples=3,
        description="检索延迟",
    ),
    ThresholdRule(
        name="api_latency",
        metric="api_latency_ms",
        warning_threshold=1000.0,
        critical_threshold=3000.0,
        window_seconds=60.0,
        min_samples=5,
        description="API响应延迟",
    ),
    ThresholdRule(
        name="http_429_rate",
        metric="429_count",
        warning_threshold=3.0,
        critical_threshold=10.0,
        window_seconds=60.0,
        min_samples=1,
        description="429频率(次/分钟)",
    ),
    ThresholdRule(
        name="db_latency",
        metric="db_latency_ms",
        warning_threshold=200.0,
        critical_threshold=500.0,
        window_seconds=60.0,
        min_samples=3,
        description="数据库延迟",
    ),
    ThresholdRule(
        name="disk_usage_pct",
        metric="disk_usage_pct",
        warning_threshold=85.0,
        critical_threshold=95.0,
        window_seconds=300.0,
        min_samples=1,
        description="磁盘使用率",
    ),
]


_global_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    global _global_detector
    if _global_detector is None:
        _global_detector = AnomalyDetector()
        for rule in DEFAULT_RULES:
            _global_detector.add_rule(rule)
    return _global_detector
