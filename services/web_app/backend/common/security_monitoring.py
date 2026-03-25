# -*- coding: utf-8 -*-
"""
安全监控和告警系统
Security Monitoring and Alerting System

收集、分析和报告安全事件：
- 认证失败
- 速率限制触发
- 可疑活动
- 异常模式
- 安全违规
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class SecurityEventSeverity(Enum):
    """安全事件严重性"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventType(Enum):
    """安全事件类型"""
    # 认证事件
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGIN_SUCCESS_NEW_DEVICE = "login_success_new_device"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_CHANGE_FAILED = "password_change_failed"

    # 速率限制事件
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    BRUTE_FORCE_DETECTED = "brute_force_detected"

    # 授权事件
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    FORBIDDEN_ACCESS = "forbidden_access"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"

    # 数据安全事件
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"

    # 可疑活动
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    MULTIPLE_FAILED_REQUESTS = "multiple_failed_requests"

    # 配置事件
    SECURITY_CONFIG_CHANGE = "security_config_change"
    USER_ROLE_CHANGE = "user_role_change"


@dataclass
class SecurityEvent:
    """安全事件数据类"""
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    location: Optional[Dict[str, float]] = None  # latitude, longitude
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_path": self.request_path,
            "request_method": self.request_method,
            "details": self.details or {},
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "location": self.location,
            "session_id": self.session_id,
        }


class SecurityAlertConfig:
    """告警配置"""

    # 告警阈值
    FAILED_LOGIN_THRESHOLD: int = 5  # 5分钟内
    RATE_LIMIT_THRESHOLD: int = 10  # 1小时内
    SUSPICIOUS_PATTERN_THRESHOLD: int = 3  # 10分钟内

    # 告警时间窗口（秒）
    FAILED_LOGIN_WINDOW: int = 300  # 5分钟
    RATE_LIMIT_WINDOW: int = 3600  # 1小时
    SUSPICIOUS_PATTERN_WINDOW: int = 600  # 10分钟

    # 告警冷却时间（秒）
    ALERT_COOLDOWN: int = 600  # 10分钟


@dataclass
class SecurityAlert:
    """安全告警"""
    alert_id: str
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    message: str
    events: List[SecurityEvent] = field(default_factory=list)
    triggered_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolved_at: Optional[float] = None
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "alert_id": self.alert_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "events": [e.to_dict() for e in self.events],
            "triggered_at": self.triggered_at,
            "datetime": datetime.fromtimestamp(self.triggered_at).isoformat(),
            "event_count": len(self.events),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "resolution_notes": self.resolution_notes,
        }


class SecurityMonitor:
    """
    安全监控器

    收集、分析和报告安全事件。

    Features:
    - 事件收集和存储
    - 告警生成和去重
    - 模式检测
    - 指标计算
    - 告警冷却
    """

    def __init__(self, config: Optional[SecurityAlertConfig] = None):
        """
        初始化安全监控器

        Args:
            config: 告警配置
        """
        self.config = config or SecurityAlertConfig()
        self.events: List[SecurityEvent] = []
        self.alerts: List[SecurityAlert] = []
        self.active_alerts: Dict[str, float] = {}  # alert_id -> last_triggered_time
        self.event_counts: Dict[SecurityEventType, int] = defaultdict(int)
        self.ip_events: Dict[str, List[SecurityEvent]] = defaultdict(list)
        self.user_events: Dict[int, List[SecurityEvent]] = defaultdict(list)

        logger.info("Security Monitor initialized")

    def log_event(self, event: SecurityEvent):
        """
        记录安全事件

        Args:
            event: 安全事件
        """
        self.events.append(event)
        self.event_counts[event.event_type] += 1

        if event.ip_address:
            self.ip_events[event.ip_address].append(event)

        if event.user_id:
            self.user_events[event.user_id].append(event)

        logger.info(
            f"Security event logged: {event.event_type.value} "
            f"(severity: {event.severity.value}, "
            f"user: {event.username or event.user_id}, "
            f"ip: {event.ip_address})"
        )

    def check_alerts(self) -> List[SecurityAlert]:
        """
        检查并生成告警

        Returns:
            新生成的告警列表
        """
        new_alerts = []
        now = time.time()

        # 检查暴力破解
        brute_force_alert = self._check_brute_force_attack(now)
        if brute_force_alert:
            new_alerts.append(brute_force_alert)

        # 检查可疑IP
        suspicious_ip_alert = self._check_suspicious_ip_activity(now)
        if suspicious_ip_alert:
            new_alerts.append(suspicious_ip_alert)

        # 检查异常用户行为
        anomalous_user_alert = self._check_anomalous_user_behavior(now)
        if anomalous_user_alert:
            new_alerts.append(anomalous_user_alert)

        # 检查SQL注入尝试
        sql_injection_alert = self._check_sql_injection_attempts(now)
        if sql_injection_alert:
            new_alerts.append(sql_injection_alert)

        # 检查XSS尝试
        xss_alert = self._check_xss_attempts(now)
        if xss_alert:
            new_alerts.append(xss_alert)

        self.alerts.extend(new_alerts)

        if new_alerts:
            logger.warning(f"Generated {len(new_alerts)} security alerts")

        return new_alerts

    def _check_brute_force_attack(
        self, now: float
    ) -> Optional[SecurityAlert]:
        """检查暴力破解攻击"""
        # 统计每个IP的失败登录
        ip_failures: Dict[str, List[SecurityEvent]] = defaultdict(list)
        window_start = now - self.config.FAILED_LOGIN_WINDOW

        for event in self.events:
            if event.event_type == SecurityEventType.LOGIN_FAILURE:
                if event.timestamp >= window_start:
                    if event.ip_address:
                        ip_failures[event.ip_address].append(event)

        # 检查是否有IP超过阈值
        for ip, failures in ip_failures.items():
            if len(failures) >= self.config.FAILED_LOGIN_THRESHOLD:
                alert_key = f"brute_force_{ip}"
                last_triggered = self.active_alerts.get(alert_key, 0)

                # 检查冷却时间
                if now - last_triggered > self.config.ALERT_COOLDOWN:
                    alert = SecurityAlert(
                        alert_id=self._generate_alert_id(),
                        event_type=SecurityEventType.BRUTE_FORCE_DETECTED,
                        severity=SecurityEventSeverity.HIGH,
                        message=f"Brute force attack detected from IP {ip} ({len(failures)} failed logins in {self.config.FAILED_LOGIN_WINDOW}s)",
                        events=failures,
                    )
                    self.active_alerts[alert_key] = now
                    return alert

        return None

    def _check_suspicious_ip_activity(
        self, now: float
    ) -> Optional[SecurityAlert]:
        """检查可疑IP活动"""
        window_start = now - self.config.RATE_LIMIT_WINDOW

        for ip, events in self.ip_events.items():
            # 检查速率限制事件
            rate_limit_events = [
                e for e in events
                if e.timestamp >= window_start
                and e.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED
            ]

            if len(rate_limit_events) >= self.config.RATE_LIMIT_THRESHOLD:
                alert_key = f"suspicious_ip_{ip}"
                last_triggered = self.active_alerts.get(alert_key, 0)

                if now - last_triggered > self.config.ALERT_COOLDOWN:
                    alert = SecurityAlert(
                        alert_id=self._generate_alert_id(),
                        event_type=SecurityEventType.SUSPICIOUS_PATTERN,
                        severity=SecurityEventSeverity.MEDIUM,
                        message=f"Suspicious activity from IP {ip} ({len(rate_limit_events)} rate limit violations in {self.config.RATE_LIMIT_WINDOW}s)",
                        events=rate_limit_events,
                    )
                    self.active_alerts[alert_key] = now
                    return alert

        return None

    def _check_anomalous_user_behavior(
        self, now: float
    ) -> Optional[SecurityAlert]:
        """检查异常用户行为"""
        window_start = now - self.config.SUSPICIOUS_PATTERN_WINDOW

        for user_id, events in self.user_events.items():
            # 检查特权提升尝试
            privilege_events = [
                e for e in events
                if e.timestamp >= window_start
                and e.event_type == SecurityEventType.PRIVILEGE_ESCALATION_ATTEMPT
            ]

            if len(privilege_events) >= 2:
                alert_key = f"anomalous_user_{user_id}"
                last_triggered = self.active_alerts.get(alert_key, 0)

                if now - last_triggered > self.config.ALERT_COOLDOWN:
                    alert = SecurityAlert(
                        alert_id=self._generate_alert_id(),
                        event_type=SecurityEventType.ANOMALOUS_BEHAVIOR,
                        severity=SecurityEventSeverity.HIGH,
                        message=f"Anomalous behavior detected for user {user_id} (multiple privilege escalation attempts)",
                        events=privilege_events,
                    )
                    self.active_alerts[alert_key] = now
                    return alert

        return None

    def _check_sql_injection_attempts(
        self, now: float
    ) -> Optional[SecurityAlert]:
        """检查SQL注入尝试"""
        window_start = now - 600  # 10分钟

        sql_events = [
            e for e in self.events
            if e.timestamp >= window_start
            and e.event_type == SecurityEventType.SQL_INJECTION_ATTEMPT
        ]

        if len(sql_events) >= 3:
            alert_key = "sql_injection_attacks"
            last_triggered = self.active_alerts.get(alert_key, 0)

            if now - last_triggered > self.config.ALERT_COOLDOWN:
                # 按IP分组
                ip_counts: Dict[str, int] = defaultdict(int)
                for event in sql_events:
                    if event.ip_address:
                        ip_counts[event.ip_address] += 1

                top_ip = max(ip_counts, key=ip_counts.get) if ip_counts else None

                alert = SecurityAlert(
                    alert_id=self._generate_alert_id(),
                    event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                    severity=SecurityEventSeverity.CRITICAL,
                    message=f"SQL injection attack detected ({len(sql_events)} attempts in 10 minutes, top IP: {top_ip})",
                    events=sql_events,
                )
                self.active_alerts[alert_key] = now
                return alert

        return None

    def _check_xss_attempts(
        self, now: float
    ) -> Optional[SecurityAlert]:
        """检查XSS尝试"""
        window_start = now - 600  # 10分钟

        xss_events = [
            e for e in self.events
            if e.timestamp >= window_start
            and e.event_type == SecurityEventType.XSS_ATTEMPT
        ]

        if len(xss_events) >= 5:
            alert_key = "xss_attacks"
            last_triggered = self.active_alerts.get(alert_key, 0)

            if now - last_triggered > self.config.ALERT_COOLDOWN:
                alert = SecurityAlert(
                    alert_id=self._generate_alert_id(),
                    event_type=SecurityEventType.XSS_ATTEMPT,
                    severity=SecurityEventSeverity.HIGH,
                    message=f"XSS attack detected ({len(xss_events)} attempts in 10 minutes)",
                    events=xss_events,
                )
                self.active_alerts[alert_key] = now
                return alert

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取安全统计信息

        Returns:
            安全统计字典
        """
        now = time.time()
        last_hour = now - 3600
        last_day = now - 86400

        # 统计事件
        events_last_hour = [e for e in self.events if e.timestamp >= last_hour]
        events_last_day = [e for e in self.events if e.timestamp >= last_day]

        # 统计告警
        active_alerts = [
            a for a in self.alerts
            if not a.resolved
        ]

        return {
            "total_events": len(self.events),
            "total_alerts": len(self.alerts),
            "active_alerts": len(active_alerts),
            "events_last_hour": len(events_last_hour),
            "events_last_day": len(events_last_day),
            "event_type_counts": {
                event_type.value: count
                for event_type, count in self.event_counts.items()
            },
            "critical_events": len([
                e for e in self.events
                if e.severity == SecurityEventSeverity.CRITICAL
            ]),
            "high_events": len([
                e for e in self.events
                if e.severity == SecurityEventSeverity.HIGH
            ]),
            "recent_critical_alerts": [
                a.to_dict() for a in active_alerts
                if a.severity == SecurityEventSeverity.CRITICAL
            ],
        }

    def resolve_alert(self, alert_id: str, resolution_notes: Optional[str] = None):
        """
        解决告警

        Args:
            alert_id: 告警ID
            resolution_notes: 解决说明
        """
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = time.time()
                alert.resolution_notes = resolution_notes
                logger.info(f"Alert {alert_id} resolved")
                return

        logger.warning(f"Alert {alert_id} not found")

    def _generate_alert_id(self) -> str:
        """生成告警ID"""
        import uuid
        return f"alert_{uuid.uuid4().hex[:12]}"


# 全局安全监控器实例
security_monitor = SecurityMonitor()


def log_security_event(
    event_type: SecurityEventType,
    severity: SecurityEventSeverity = SecurityEventSeverity.LOW,
    **kwargs
):
    """
    记录安全事件的便捷函数

    Args:
        event_type: 事件类型
        severity: 事件严重性
        **kwargs: 事件属性
    """
    event = SecurityEvent(
        event_type=event_type,
        severity=severity,
        **kwargs
    )
    security_monitor.log_event(event)


def check_security_alerts() -> List[SecurityAlert]:
    """
    检查安全告警的便捷函数

    Returns:
        新告警列表
    """
    return security_monitor.check_alerts()


def get_security_statistics() -> Dict[str, Any]:
    """
    获取安全统计的便捷函数

    Returns:
        安全统计字典
    """
    return security_monitor.get_statistics()


__all__ = [
    "SecurityEventSeverity",
    "SecurityEventType",
    "SecurityEvent",
    "SecurityAlert",
    "SecurityAlertConfig",
    "SecurityMonitor",
    "security_monitor",
    "log_security_event",
    "check_security_alerts",
    "get_security_statistics",
]
