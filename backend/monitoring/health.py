"""健康检查模块

提供系统健康状态检查
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""

    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "duration": self.duration,
        }


class HealthChecker:
    """健康检查器

    管理和执行各种健康检查
    """

    def __init__(self):
        """初始化健康检查器"""
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._check_intervals: Dict[str, float] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register(self, name: str, check_func: Callable, interval: float = 30.0) -> None:
        """注册健康检查

        Args:
            name: 检查名称
            check_func: 检查函数，返回HealthCheckResult
            interval: 检查间隔（秒）
        """
        self._checks[name] = check_func
        self._check_intervals[name] = interval
        logger.info(f"注册健康检查: {name}, 间隔: {interval}s")

    def unregister(self, name: str) -> None:
        """注销健康检查

        Args:
            name: 检查名称
        """
        if name in self._checks:
            del self._checks[name]
            del self._check_intervals[name]
            logger.info(f"注销健康检查: {name}")

    async def check(self, name: str) -> HealthCheckResult:
        """执行单个健康检查

        Args:
            name: 检查名称

        Returns:
            检查结果
        """
        if name not in self._checks:
            return HealthCheckResult(
                name=name, status=HealthStatus.UNKNOWN, message=f"检查 {name} 不存在"
            )

        check_func = self._checks[name]
        start_time = time.time()

        try:
            result = await check_func() if asyncio.iscoroutinefunction(check_func) else check_func()
            result.duration = time.time() - start_time
            self._last_results[name] = result
            return result
        except Exception as e:
            logger.error(f"健康检查 {name} 执行失败: {e}")
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"检查执行失败: {str(e)}",
                duration=time.time() - start_time,
            )
            self._last_results[name] = result
            return result

    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """执行所有健康检查

        Returns:
            所有检查结果
        """
        results = {}
        tasks = []

        for name in self._checks:
            tasks.append(self.check(name))

        if tasks:
            check_results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(self._checks.keys(), check_results):
                if isinstance(result, Exception):
                    results[name] = HealthCheckResult(
                        name=name, status=HealthStatus.UNHEALTHY, message=str(result)
                    )
                else:
                    results[name] = result

        return results

    def get_overall_status(self) -> HealthStatus:
        """获取整体健康状态

        Returns:
            整体状态
        """
        if not self._last_results:
            return HealthStatus.UNKNOWN

        statuses = [r.status for r in self._last_results.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif HealthStatus.HEALTHY in statuses:
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

    def get_summary(self) -> Dict[str, Any]:
        """获取健康检查摘要

        Returns:
            摘要信息
        """
        overall = self.get_overall_status()

        return {
            "status": overall.value,
            "timestamp": time.time(),
            "checks": {name: result.to_dict() for name, result in self._last_results.items()},
        }

    async def start_background_checks(self) -> None:
        """启动后台健康检查

        定期执行所有检查
        """
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._background_loop())
        logger.info("后台健康检查已启动")

    async def stop_background_checks(self) -> None:
        """停止后台健康检查"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("后台健康检查已停止")

    async def _background_loop(self) -> None:
        """后台检查循环"""
        while self._running:
            try:
                await self.check_all()
                # 等待最短的检查间隔
                min_interval = min(self._check_intervals.values()) if self._check_intervals else 30
                await asyncio.sleep(min_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"后台检查出错: {e}")
                await asyncio.sleep(5)


# 全局健康检查器
_global_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    global _global_checker
    if _global_checker is None:
        _global_checker = HealthChecker()
    return _global_checker


# 预定义的健康检查函数
async def database_health_check(db_pool) -> HealthCheckResult:
    """数据库健康检查"""
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return HealthCheckResult(
            name="database", status=HealthStatus.HEALTHY, message="数据库连接正常"
        )
    except Exception as e:
        return HealthCheckResult(
            name="database", status=HealthStatus.UNHEALTHY, message=f"数据库连接失败: {str(e)}"
        )


async def redis_health_check(redis_url: str) -> HealthCheckResult:
    """Redis健康检查"""
    try:
        from redis.asyncio import from_url as async_from_url

        redis = await async_from_url(redis_url)
        await redis.ping()
        await redis.close()
        return HealthCheckResult(name="redis", status=HealthStatus.HEALTHY, message="Redis连接正常")
    except (ImportError, OSError, RuntimeError, ConnectionError) as e:
        return HealthCheckResult(
            name="redis", status=HealthStatus.DEGRADED, message=f"Redis连接失败: {str(e)}"
        )


def memory_health_check(threshold_mb: int = 1000) -> HealthCheckResult:
    """内存健康检查"""
    import psutil

    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024

    if memory_mb > threshold_mb:
        return HealthCheckResult(
            name="memory",
            status=HealthStatus.DEGRADED,
            message=f"内存使用较高: {memory_mb:.1f}MB",
            details={"memory_mb": memory_mb, "threshold_mb": threshold_mb},
        )

    return HealthCheckResult(
        name="memory",
        status=HealthStatus.HEALTHY,
        message=f"内存使用正常: {memory_mb:.1f}MB",
        details={"memory_mb": memory_mb},
    )
