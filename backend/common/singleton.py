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

# 存储所有使用 async_singleton 装饰的函数所在模块和变量名
_singleton_registrations: list[tuple[str, str]] = []


def _get_lock(key: str) -> threading.Lock:
    """获取指定key的锁，线程安全"""
    if key not in _init_locks:
        with _lock_for_locks:
            if key not in _init_locks:
                _init_locks[key] = threading.Lock()
    return _init_locks[key]


# 初始化失败标记
_INIT_FAILED_SENTINEL = object()


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
        import sys

        module = sys.modules.get(func.__module__)
        var_name = instance_var_name or f"_{func.__name__}"
        lock_key = f"{func.__module__}.{var_name}"

        _singleton_registrations.append((func.__module__, var_name))

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # 检查是否已初始化
            instance = getattr(module, var_name, None)
            if instance is not None and instance is not _INIT_FAILED_SENTINEL:
                return instance
            if instance is _INIT_FAILED_SENTINEL:
                raise RuntimeError(
                    f"Singleton {var_name} previously failed to initialize"
                )

            # 使用锁确保线程安全的初始化
            lock = _get_lock(lock_key)

            # 双重检查锁定模式
            if lock.acquire(blocking=False):
                try:
                    # 再次检查，可能在等待锁时已被其他线程初始化
                    instance = getattr(module, var_name, None)
                    if instance is None:
                        try:
                            if init_func is not None:
                                instance = await init_func(*args, **kwargs)
                            else:
                                instance = await func(*args, **kwargs)
                        except Exception:
                            setattr(module, var_name, _INIT_FAILED_SENTINEL)
                            raise
                        setattr(module, var_name, instance)
                    elif instance is _INIT_FAILED_SENTINEL:
                        raise RuntimeError(
                            f"Singleton {var_name} previously failed to initialize"
                        )
                    return instance
                finally:
                    lock.release()
            else:
                # 锁已被占用，等待初始化完成
                for _ in range(300):  # 最多等待30秒
                    await asyncio.sleep(0.1)
                    instance = getattr(module, var_name, None)
                    if instance is not None:
                        if instance is _INIT_FAILED_SENTINEL:
                            raise RuntimeError(
                                f"Singleton {var_name} previously failed to initialize"
                            )
                        return instance
                raise TimeoutError(
                    f"Timeout waiting for singleton {var_name} initialization"
                )

        return wrapper

    return decorator


# 初始化失败标记
_INIT_FAILED_SENTINEL = object()


