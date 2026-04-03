"""
服务管理器系统

提供统一的服务生命周期管理、健康检查和依赖注入
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="Service")


class ServiceStatus(str, Enum):
    """服务状态"""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceHealth:
    """服务健康状态"""

    service_name: str
    status: ServiceStatus
    healthy: bool
    message: str = ""
    last_check: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Service(ABC):
    """
    服务基类

    所有服务都应该继承这个类并实现相应的生命周期方法
    """

    def __init__(self, name: str, dependencies: Optional[List[str]] = None):
        """
        初始化服务

        Args:
            name: 服务名称
            dependencies: 依赖的服务名称列表
        """
        self.name = name
        self.dependencies = dependencies or []
        self.status = ServiceStatus.STOPPED
        self._health = ServiceHealth(
            service_name=name,
            status=ServiceStatus.STOPPED,
            healthy=False,
            message="Service initialized",
        )

    @abstractmethod
    async def start(self) -> None:
        """启动服务"""

    @abstractmethod
    async def stop(self) -> None:
        """停止服务"""

    async def health_check(self) -> ServiceHealth:
        """
        健康检查

        Returns:
            服务健康状态
        """
        self._health.status = self.status
        self._health.healthy = self.status == ServiceStatus.RUNNING
        self._health.last_check = datetime.now()
        return self._health

    async def restart(self) -> None:
        """重启服务"""
        await self.stop()
        await self.start()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, status={self.status.value})>"


class ServiceManager:
    """
    服务管理器

    负责管理所有服务的生命周期、依赖关系和健康检查
    """

    def __init__(self):
        """初始化服务管理器"""
        self._services: Dict[str, Service] = {}
        self._startup_order: List[str] = []
        self._lock = asyncio.Lock()
        self._running = False

    def register_service(self, service: Service) -> None:
        """
        注册服务

        Args:
            service: 服务实例
        """
        if service.name in self._services:
            existing = self._services[service.name]
            if existing.status == ServiceStatus.RUNNING:
                logger.debug(f"Service {service.name} already registered and running, skipping")
                return
            logger.warning(
                f"Service {service.name} already registered with status {existing.status}, replacing"
            )
            self._services[service.name] = service
            return

        self._services[service.name] = service
        logger.info(f"Registered service: {service.name}")

    def register_service_class(
        self, service_class: Type[T], name: Optional[str] = None, **kwargs: Any
    ) -> T:
        """
        注册服务类并自动实例化

        Args:
            service_class: 服务类
            name: 服务名称（默认使用类名）
            **kwargs: 传递给服务类的参数

        Returns:
            服务实例
        """
        service_name = name or service_class.__name__
        service = service_class(service_name, **kwargs)
        self.register_service(service)
        return service

    def get_service(self, name: str) -> Optional[Service]:
        """
        获取服务实例

        Args:
            name: 服务名称

        Returns:
            服务实例或None
        """
        return self._services.get(name)

    def _resolve_startup_order(self) -> List[str]:
        """
        解析服务启动顺序（基于依赖关系）

        Returns:
            按依赖顺序排列的服务名称列表
        """
        order = []
        visited = set()
        temp_visited = set()

        def visit(service_name: str) -> None:
            if service_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {service_name}")
            if service_name in visited:
                return

            temp_visited.add(service_name)
            service = self._services.get(service_name)
            if service:
                for dep in service.dependencies:
                    visit(dep)
            temp_visited.remove(service_name)
            visited.add(service_name)
            order.append(service_name)

        for service_name in self._services:
            visit(service_name)

        return order

    async def start_all(self) -> None:
        """启动所有服务"""
        async with self._lock:
            if self._running:
                logger.warning("Service manager is already running")
                return

            logger.info("Starting service manager...")

            # 解析启动顺序
            self._startup_order = self._resolve_startup_order()
            logger.info(f"Service startup order: {self._startup_order}")

            # 按顺序启动服务
            for service_name in self._startup_order:
                service = self._services.get(service_name)
                if service:
                    try:
                        service.status = ServiceStatus.STARTING
                        logger.info(f"Starting service: {service_name}")

                        await service.start()

                        service.status = ServiceStatus.RUNNING
                        logger.info(f"Service started: {service_name}")

                    except Exception as e:
                        service.status = ServiceStatus.ERROR
                        logger.error(f"Failed to start service {service_name}: {e}")
                        raise

            self._running = True
            logger.info("Service manager started successfully")

    async def stop_all(self) -> None:
        """停止所有服务"""
        async with self._lock:
            if not self._running:
                logger.warning("Service manager is not running")
                return

            logger.info("Stopping service manager...")

            # 按相反顺序停止服务
            for service_name in reversed(self._startup_order):
                service = self._services.get(service_name)
                if service:
                    try:
                        service.status = ServiceStatus.STOPPING
                        logger.info(f"Stopping service: {service_name}")

                        await service.stop()

                        service.status = ServiceStatus.STOPPED
                        logger.info(f"Service stopped: {service_name}")

                    except Exception as e:
                        logger.error(f"Error stopping service {service_name}: {e}")

            self._running = False
            logger.info("Service manager stopped")

    async def restart_service(self, name: str) -> None:
        """
        重启指定服务

        Args:
            name: 服务名称
        """
        service = self.get_service(name)
        if not service:
            raise ValueError(f"Service {name} not found")

        logger.info(f"Restarting service: {name}")
        await service.restart()
        logger.info(f"Service restarted: {name}")

    async def health_check_all(self) -> Dict[str, ServiceHealth]:
        """
        检查所有服务的健康状态

        Returns:
            服务名称到健康状态的映射
        """
        results = {}
        for service_name, service in self._services.items():
            try:
                health = await service.health_check()
                results[service_name] = health
            except Exception as e:
                logger.error(f"Health check failed for {service_name}: {e}")
                results[service_name] = ServiceHealth(
                    service_name=service_name,
                    status=service.status,
                    healthy=False,
                    message=f"Health check failed: {e}",
                )
        return results

    async def get_unhealthy_services(self) -> List[str]:
        """
        获取不健康的服务列表

        Returns:
            不健康服务的名称列表
        """
        health_results = await self.health_check_all()
        return [name for name, health in health_results.items() if not health.healthy]

    @property
    def is_running(self) -> bool:
        """服务管理器是否正在运行"""
        return self._running

    @property
    def service_count(self) -> int:
        """已注册的服务数量"""
        return len(self._services)


# 全局服务管理器实例
_global_service_manager: Optional[ServiceManager] = None
_service_manager_lock = threading.Lock()


def get_service_manager() -> ServiceManager:
    """
    获取全局服务管理器实例（线程安全）

    Returns:
        全局服务管理器
    """
    global _global_service_manager
    if _global_service_manager is None:
        with _service_manager_lock:
            if _global_service_manager is None:
                _global_service_manager = ServiceManager()
    return _global_service_manager


def reset_service_manager() -> None:
    """重置全局服务管理器（主要用于测试）"""
    global _global_service_manager
    _global_service_manager = None
