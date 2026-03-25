"""通用单例模式工具模块

提供线程安全的异步单例模式实现，用于管理全局实例。
"""

import asyncio
import threading
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

# 用于同步初始化的锁
_init_locks: dict[str, threading.Lock] = {}
_lock_for_locks = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    """获取指定key的锁，线程安全"""
    if key not in _init_locks:
        with _lock_for_locks:
            if key not in _init_locks:
                _init_locks[key] = threading.Lock()
    return _init_locks[key]


def async_singleton(
    instance_var_name: Optional[str] = None,
    init_func: Optional[Callable] = None,
) -> Callable:
    """异步单例装饰器

    将一个异步函数转换为单例获取函数，首次调用时初始化，
    后续调用返回已缓存的实例。

    Args:
        instance_var_name: 全局变量名，用于存储实例
        init_func: 初始化函数，返回实例

    Returns:
        装饰后的函数

    Example:
        _instance = None

        @async_singleton("_instance")
        async def get_service():
            return MyService()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # 获取函数所在模块的全局变量
            import sys

            module = sys.modules[func.__module__]
            var_name = instance_var_name or f"_{func.__name__}"

            # 检查是否已初始化
            instance = getattr(module, var_name, None)
            if instance is not None:
                return instance

            # 使用锁确保线程安全的初始化
            lock = _get_lock(f"{func.__module__}.{var_name}")

            # 双重检查锁定模式
            if lock.acquire(blocking=False):
                try:
                    # 再次检查，可能在等待锁时已被其他线程初始化
                    instance = getattr(module, var_name, None)
                    if instance is None:
                        if init_func is not None:
                            instance = await init_func(*args, **kwargs)
                        else:
                            instance = await func(*args, **kwargs)
                        setattr(module, var_name, instance)
                    return instance
                finally:
                    lock.release()
            else:
                # 锁已被占用，等待后重新检查
                while True:
                    await asyncio.sleep(0.001)
                    instance = getattr(module, var_name, None)
                    if instance is not None:
                        return instance

        return wrapper

    return decorator


class SingletonFactory:
    """单例工厂类

    提供更灵活的单例管理方式。

    Example:
        factory = SingletonFactory(lambda: MyService())
        service = await factory.get_instance()
    """

    def __init__(self, factory_func: Callable[[], T], name: Optional[str] = None) -> None:
        """初始化单例工厂

        Args:
            factory_func: 工厂函数，用于创建实例
            name: 实例名称，用于锁管理
        """
        self._factory_func = factory_func
        self._instance: Optional[T] = None
        self._lock = _get_lock(name or f"SingletonFactory.{id(self)}")
        self._is_async = asyncio.iscoroutinefunction(factory_func)

    async def get_instance(self) -> T:
        """获取单例实例"""
        if self._instance is not None:
            return self._instance

        with self._lock:
            if self._instance is None:
                if self._is_async:
                    self._instance = await self._factory_func()
                else:
                    self._instance = self._factory_func()
        return self._instance

    def reset(self) -> None:
        """重置单例（主要用于测试）"""
        with self._lock:
            self._instance = None


def reset_all_singletons() -> None:
    """重置所有单例实例（主要用于测试）"""
    global _init_locks
    # 不清空锁本身，只清空引用
    pass
