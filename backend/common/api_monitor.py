"""
API监控和告警模块

实时监控API调用情况，追踪速率限制错误，提供告警功能
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class APICallStats:
    """API调用统计数据"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rate_limit_hits: int = 0
    total_tokens: int = 0
    total_response_time: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """转换为字典"""
        uptime = (datetime.now() - self.start_time).total_seconds()

        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rate_limit_hits": self.rate_limit_hits,
            "total_tokens": self.total_tokens,
            "success_rate": (
                f"{(self.successful_calls / self.total_calls * 100):.2f}%"
                if self.total_calls > 0
                else "0%"
            ),
            "hit_rate": (
                f"{(self.rate_limit_hits / self.total_calls * 100):.2f}%"
                if self.total_calls > 0
                else "0%"
            ),
            "uptime_seconds": uptime,
            "calls_per_minute": self.total_calls / (uptime / 60) if uptime > 0 else 0,
            "avg_tokens_per_call": (
                self.total_tokens / self.total_calls if self.total_calls > 0 else 0
            ),
            "avg_response_time": (
                self.total_response_time / self.total_calls if self.total_calls > 0 else 0
            ),
        }


class APIMonitor:
    """API监控器"""

    def __init__(self):
        """初始化监控器"""
        self.stats = APICallStats()
        self.rate_limit_history: list = []  # 最近1小时的速率限制记录
        self.lock = threading.Lock()

    def record_call(
        self,
        success: bool,
        is_rate_limit: bool = False,
        tokens_used: int = 0,
        response_time: float = 0.0,
    ):
        """
        记录一次API调用

        Args:
            success: 是否成功
            is_rate_limit: 是否是速率限制错误
            tokens_used: 使用的token数
            response_time: 响应时间（秒）
        """
        with self.lock:
            self.stats.total_calls += 1

            if success:
                self.stats.successful_calls += 1
                self.stats.total_tokens += tokens_used
                self.stats.total_response_time += response_time
            else:
                self.stats.failed_calls += 1

            if is_rate_limit:
                self.stats.rate_limit_hits += 1
                # 记录时间
                self.rate_limit_history.append(datetime.now())

                # 清理1小时前的记录
                one_hour_ago = datetime.now() - timedelta(hours=1)
                self.rate_limit_history = [t for t in self.rate_limit_history if t > one_hour_ago]

    def get_stats(self) -> Dict[str, Any]:
        """获取当前统计"""
        with self.lock:
            return self.stats.to_dict()

    def get_rate_limit_stats(self, window_minutes: int = 60) -> Dict[str, Any]:
        """
        获取速率限制统计

        Args:
            window_minutes: 统计时间窗口（分钟）

        Returns:
            速率限制统计信息
        """
        with self.lock:
            window_start = datetime.now() - timedelta(minutes=window_minutes)
            recent_hits = [t for t in self.rate_limit_history if t > window_start]

            return {
                "window_minutes": window_minutes,
                "rate_limit_hits": len(recent_hits),
                "hits_per_hour": (
                    len(recent_hits) * (60 / window_minutes) if window_minutes > 0 else 0
                ),
                "last_hit": recent_hits[-1].isoformat() if recent_hits else None,
                "first_hit": recent_hits[0].isoformat() if recent_hits else None,
            }

    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.stats = APICallStats()
            self.rate_limit_history = []


class APIAlertManager:
    """API告警管理器"""

    def __init__(self, threshold_per_hour: int = 20, alert_cooldown_minutes: int = 30):
        """
        初始化告警管理器

        Args:
            threshold_per_hour: 每小时告警阈值
            alert_cooldown_minutes: 告警冷却时间（分钟）
        """
        self.threshold = threshold_per_hour
        self.cooldown = timedelta(minutes=alert_cooldown_minutes)
        self.last_alert_time = None
        self.alert_handlers: list = []

    def check_and_alert(self, rate_limit_hits: int, window_minutes: int = 60) -> bool:
        """
        检查并发送告警

        Args:
            rate_limit_hits: 速率限制命中次数
            window_minutes: 统计窗口（分钟）

        Returns:
            是否发送了告警
        """
        # 计算每小时的速率
        hits_per_hour = rate_limit_hits * (60 / window_minutes) if window_minutes > 0 else 0

        # 检查是否超过阈值
        if hits_per_hour >= self.threshold:
            # 检查冷却时间
            now = datetime.now()

            if self.last_alert_time is None or (now - self.last_alert_time) >= self.cooldown:
                # 发送告警
                self._send_alert(rate_limit_hits, hits_per_hour)
                self.last_alert_time = now
                return True

        return False

    def _send_alert(self, recent_hits: int, hits_per_hour: float):
        """发送告警"""
        alert_message = f"""
⚠️ API Rate Limit Alert

Rate limit errors detected:
- Recent hits (last hour): {recent_hits}
- Projected hourly rate: {hits_per_hour:.1f}/hour
- Threshold: {self.threshold}/hour
- Time: {datetime.now().isoformat()}

Recommendations:
1. Check if there are too many concurrent processes
2. Consider reducing max_calls_per_minute
3. Check for any runaway processes
4. Review API usage patterns
"""

        # 记录到日志
        logger.warning(alert_message)

        # 调用所有注册的告警处理器
        for handler in self.alert_handlers:
            try:
                handler(alert_message)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    def add_alert_handler(self, handler: Callable[[str], None]):
        """添加告警处理器"""
        self.alert_handlers.append(handler)


class GlobalAPIMonitor:
    """全局API监控器（单例模式）"""

    _instance: Optional["GlobalAPIMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化全局监控器（只执行一次）"""
        if not hasattr(self, "_initialized"):
            self.monitor = APIMonitor()
            self.alert_manager = APIAlertManager(
                threshold_per_hour=20, alert_cooldown_minutes=30  # 每小时20次告警阈值
            )
            self._initialized = True

    def record_call(
        self,
        success: bool,
        is_rate_limit: bool = False,
        tokens_used: int = 0,
        response_time: float = 0.0,
    ):
        """记录API调用"""
        self.monitor.record_call(success, is_rate_limit, tokens_used, response_time)

        # 检查是否需要告警
        stats = self.monitor.get_rate_limit_stats(window_minutes=60)
        self.alert_manager.check_and_alert(
            rate_limit_hits=stats["rate_limit_hits"], window_minutes=60
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.monitor.get_stats()

    def get_rate_limit_stats(self, window_minutes: int = 60) -> Dict[str, Any]:
        """获取速率限制统计"""
        return self.monitor.get_rate_limit_stats(window_minutes)

    def reset_stats(self):
        """重置统计"""
        self.monitor.reset_stats()


# ==================== 全局函数 ====================

_global_monitor: Optional[GlobalAPIMonitor] = None


def get_api_monitor() -> GlobalAPIMonitor:
    """获取全局API监控器"""
    global _global_monitor

    if _global_monitor is None:
        _global_monitor = GlobalAPIMonitor()

    return _global_monitor


def record_api_call(
    success: bool, is_rate_limit: bool = False, tokens_used: int = 0, response_time: float = 0.0
):
    """
    记录API调用（便捷函数）

    Args:
        success: 是否成功
        is_rate_limit: 是否是速率限制
        tokens_used: token使用量
        response_time: 响应时间
    """
    monitor = get_api_monitor()
    monitor.record_call(success, is_rate_limit, tokens_used, response_time)


def get_api_stats() -> Dict[str, Any]:
    """获取API统计信息"""
    monitor = get_api_monitor()
    return monitor.get_stats()


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例：使用监控器

    # 记录一次成功的API调用
    record_api_call(success=True, is_rate_limit=False, tokens_used=150, response_time=2.5)

    # 记录一次速率限制
    record_api_call(success=False, is_rate_limit=True, tokens_used=0, response_time=0)

    # 获取统计
    stats = get_api_stats()
    print("API Stats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 获取速率限制统计
    rate_limit_stats = get_api_monitor().get_rate_limit_stats(window_minutes=60)
    print("\nRate Limit Stats:")
    for key, value in rate_limit_stats.items():
        print(f"  {key}: {value}")
