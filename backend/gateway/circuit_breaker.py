"""熔断器

实现服务熔断，防止级联故障
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    failure_threshold: int = 5  # 失败阈值
    success_threshold: int = 2  # 成功阈值（用于半开状态恢复）
    timeout: float = 60.0  # 熔断超时（秒）
    half_open_max_calls: int = 3  # 半开状态最大尝试次数


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_transitions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "failure_rate": (self.failed_calls / self.total_calls if self.total_calls > 0 else 0),
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
        }


class CircuitBreaker:
    """熔断器

    防止服务故障级联传播
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """初始化熔断器

        Args:
            name: 熔断器名称
            config: 熔断器配置
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._last_state_change = time.time()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        return self._state

    @property
    def open_until(self) -> Optional[float]:
        """获取熔断恢复时间"""
        if self._state == CircuitState.OPEN:
            return self._last_state_change + self.config.timeout
        return None

    async def call(self, func: Callable, *args, **kwargs):
        """通过熔断器调用函数

        Args:
            func: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器开启时
        """
        if self._state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            if time.time() - self._last_state_change >= self.config.timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                logger.info(f"熔断器 {self.name} 进入半开状态")
            else:
                raise CircuitBreakerOpenError(
                    f"熔断器 {self.name} 处于开启状态", open_until=self.open_until
                )

        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """处理成功调用"""
        self._stats.successful_calls += 1
        self._stats.total_calls += 1
        self._stats.last_success_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            # 达到成功阈值，恢复到关闭状态
            if self._half_open_calls >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                self._half_open_calls = 0
                logger.info(f"熔断器 {self.name} 恢复到关闭状态")

    def _on_failure(self) -> None:
        """处理失败调用"""
        self._stats.failed_calls += 1
        self._stats.total_calls += 1
        self._stats.last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # 半开状态失败，重新打开
            self._transition_to(CircuitState.OPEN)
            self._half_open_calls = 0
            logger.warning(f"熔断器 {self.name} 从半开状态重新打开")
        else:
            # 达到失败阈值，打开熔断器
            recent_failures = self._count_recent_failures()
            if recent_failures >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.warning(f"熔断器 {self.name} 打开，" f"最近失败次数: {recent_failures}")

    def _count_recent_failures(self) -> int:
        """计算最近的失败次数"""
        # 简化实现，实际应该记录每次失败时间
        return self._stats.failed_calls

    def _transition_to(self, new_state: CircuitState) -> None:
        """转换状态

        Args:
            new_state: 新状态
        """
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        self._stats.state_transitions.append(
            {"from": old_state.value, "to": new_state.value, "at": time.time()}
        )

    def get_stats(self) -> dict:
        """获取熔断器统计"""
        return {
            "name": self.name,
            "state": self._state.value,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "timeout": self.config.timeout,
            },
            "stats": self._stats.to_dict(),
            "open_until": self.open_until,
        }

    def reset(self) -> None:
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._last_state_change = time.time()
        self._half_open_calls = 0
        logger.info(f"熔断器 {self.name} 已重置")


class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""

    def __init__(self, message: str, open_until: Optional[float] = None):
        super().__init__(message)
        self.open_until = open_until

    def to_dict(self) -> dict:
        return {
            "error": "circuit_breaker_open",
            "message": str(self),
            "open_until": self.open_until,
            "retry_after": int(self.open_until - time.time()) if self.open_until else None,
        }


# 熔断器管理器
class CircuitBreakerRegistry:
    """熔断器注册表"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self, name: str, config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """获取或创建熔断器

        Args:
            name: 熔断器名称
            config: 熔断器配置

        Returns:
            熔断器实例
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get_all_stats(self) -> list:
        """获取所有熔断器统计"""
        return [breaker.get_stats() for breaker in self._breakers.values()]

    def reset_all(self) -> None:
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            breaker.reset()
