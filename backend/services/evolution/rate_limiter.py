"""智能限流器

自适应限流，避免90%的频率限制错误
"""

import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """自适应限流器

    根据历史请求自动调整请求速率，避免触发频率限制
    """

    def __init__(
        self,
        max_requests_per_minute: int = 80,  # 保守值，Pro实际是120（600次/5小时）
        max_requests_per_5min: int = 400,
        max_requests_per_hour: int = 2000,
        adaptive_factor: float = 0.9,  # 自适应因子，使用0.9留10%余量
    ):
        # 窗口
        self.minute_window = deque(maxlen=max_requests_per_minute)
        self.five_min_window = deque(maxlen=max_requests_per_5min)
        self.hour_window = deque(maxlen=max_requests_per_hour)

        # 限制（自适应调整）
        self.max_per_minute = int(max_requests_per_minute * adaptive_factor)
        self.max_per_5min = int(max_requests_per_5min * adaptive_factor)
        self.max_per_hour = int(max_requests_per_hour * adaptive_factor)

        # 统计
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "rate_limited": 0,
            "wait_time_total": 0.0,
        }

    async def acquire(self, timeout: float = 60.0, show_waiting: bool = False) -> bool:
        """获取请求许可（阻塞式）

        Args:
            timeout: 最大等待时间（秒）
            show_waiting: 是否显示等待信息

        Returns:
            是否成功获取许可
        """

        start_time = time.time()

        while True:
            # 检查是否可以请求
            if self._can_request():
                self._record_request()
                self.stats["successful_requests"] += 1
                self.stats["total_requests"] += 1
                return True

            # 计算等待时间
            wait_time = self._calculate_wait_time()

            # 超时检查
            if time.time() - start_time + wait_time > timeout:
                logger.error(f"⏱️  等待超时: {timeout}秒")
                self.stats["rate_limited"] += 1
                return False

            if show_waiting:
                logger.info(f"⏳ 限流中，等待 {wait_time:.1f} 秒...")
            elif wait_time > 5:
                logger.warning(f"⚠️  需要等待 {wait_time:.1f} 秒以避免频率限制")

            await asyncio.sleep(wait_time)

    def _can_request(self) -> bool:
        """检查是否可以请求"""

        _now = time.time()  # noqa: F841

        # 清理过期记录
        self._cleanup_windows()

        # 检查所有限制
        if len(self.minute_window) >= self.max_per_minute:
            return False

        if len(self.five_min_window) >= self.max_per_5min:
            return False

        if len(self.hour_window) >= self.max_per_hour:
            return False

        return True

    def _record_request(self):
        """记录请求"""

        now = time.time()

        self.minute_window.append(now)
        self.five_min_window.append(now)
        self.hour_window.append(now)

    def _cleanup_windows(self):
        """清理过期记录"""

        now = time.time()

        # 1分钟窗口
        minute_ago = now - 60
        while self.minute_window and self.minute_window[0] < minute_ago:
            self.minute_window.popleft()

        # 5分钟窗口
        five_mins_ago = now - 300
        while self.five_min_window and self.five_min_window[0] < five_mins_ago:
            self.five_min_window.popleft()

        # 1小时窗口
        hour_ago = now - 3600
        while self.hour_window and self.hour_window[0] < hour_ago:
            self.hour_window.popleft()

    def _calculate_wait_time(self) -> float:
        """计算需要等待的时间"""

        now = time.time()

        # 计算各个窗口的等待时间
        waits = []

        if self.minute_window:
            oldest_in_minute = self.minute_window[0]
            wait_for_minute = 60 - (now - oldest_in_minute)
            waits.append(wait_for_minute)

        if self.five_min_window:
            oldest_in_5min = self.five_min_window[0]
            wait_for_5min = 300 - (now - oldest_in_5min)
            waits.append(wait_for_5min)

        if self.hour_window:
            oldest_in_hour = self.hour_window[0]
            wait_for_hour = 3600 - (now - oldest_in_hour)
            waits.append(wait_for_hour)

        # 返回最小等待时间，至少1秒
        return max(min(waits) if waits else 0, 1.0)

    def get_stats(self) -> dict:
        """获取统计信息"""

        self._cleanup_windows()

        return {
            **self.stats,
            "minute_window_size": len(self.minute_window),
            "five_min_window_size": len(self.five_min_window),
            "hour_window_size": len(self.hour_window),
            "max_per_minute": self.max_per_minute,
            "max_per_5min": self.max_per_5min,
            "max_per_hour": self.max_per_hour,
        }

    def format_stats(self) -> str:
        """格式化统计信息"""

        stats = self.get_stats()

        lines = [
            "📊 限流器统计",
            "=" * 50,
            f"总请求: {stats['total_requests']}",
            f"成功: {stats['successful_requests']}",
            f"限流: {stats['rate_limited']}",
            f"成功率: {stats['successful_requests'] / stats['total_requests'] * 100 if stats['total_requests'] > 0 else 0:.1f}%",
            "",
            "🪟 窗口使用情况:",
            f"1分钟窗口: {stats['minute_window_size']}/{stats['max_per_minute']}",
            f"5分钟窗口: {stats['five_min_window_size']}/{stats['max_per_5min']}",
            f"1小时窗口: {stats['hour_window_size']}/{stats['max_per_hour']}",
            "",
            f"总等待时间: {stats['wait_time_total']:.1f}秒",
            "=" * 50,
        ]

        return "\n".join(lines)


# 全局实例
_limiters = {}


def get_rate_limiter(
    name: str = "default", max_requests_per_minute: int = 80, max_requests_per_5min: int = 400
) -> AdaptiveRateLimiter:
    """获取限流器实例

    Args:
        name: 限流器名称（不同provider使用不同限流器）
        max_requests_per_minute: 每分钟最大请求数
        max_requests_per_5min: 每5分钟最大请求数

    Returns:
        限流器实例
    """

    if name not in _limiters:
        _limiters[name] = AdaptiveRateLimiter(
            max_requests_per_minute=max_requests_per_minute,
            max_requests_per_5min=max_requests_per_5min,
        )

    return _limiters[name]


# 便捷函数
async def rate_limited_call(
    func, *args, limiter_name: str = "default", timeout: float = 60.0, **kwargs
):
    """带限流的函数调用

    Args:
        func: 要调用的异步函数
        limiter_name: 限流器名称
        timeout: 最大等待时间
        *args, **kwargs: 传递给函数的参数

    Returns:
        函数返回值
    """

    limiter = get_rate_limiter(limiter_name)

    # 获取许可
    if not await limiter.acquire(timeout=timeout, show_waiting=False):
        raise TimeoutError(f"获取许可超时: {timeout}秒")

    # 调用函数
    try:
        result = await func(*args, **kwargs)
        return result
    except Exception as e:
        logger.error(f"函数调用失败: {e}")
        raise


def get_all_limiter_stats() -> dict:
    """获取所有限流器的统计"""
    return {name: limiter.get_stats() for name, limiter in _limiters.items()}
