"""健康检查API路由"""

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, Response

from backend.core.database import init_db_pool
from backend.core.dependency_injection import require_admin_api_key
from backend.domains import get_registry
from backend.monitoring import get_health_checker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


# ========== 路由 ==========


@router.get("/")
async def root() -> Dict[str, Any]:
    """根路径 - 系统信息"""
    from backend.core.request_stats import get_request_stats

    request_stats = get_request_stats()

    return {
        "status": "ok",
        "message": "智能知识系统运行中",
        "categories": ["气功", "中医", "儒家"],
        "version": "1.0.0",
        "stats": request_stats,
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查端点"""
    db_status = "ok"
    try:
        pool = await init_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/api/v1/health")
async def api_v1_health_check(detailed: bool = False) -> Dict[str, Any]:
    """
    系统健康检查

    Args:
        detailed: 是否返回详细信息

    Returns:
        健康状态
    """
    health_checker = get_health_checker()
    registry = get_registry()

    # 获取整体状态
    summary = health_checker.get_summary()
    domain_health = await registry.health_check()

    if not detailed:
        return {"status": summary["status"], "timestamp": summary["timestamp"]}

    return {
        "status": summary["status"],
        "timestamp": summary["timestamp"],
        "domains": domain_health,
        "checks": summary["checks"],
    }


@router.get("/api/v1/health/{check_name}")
async def health_check_detail(check_name: str) -> Dict[str, Any]:
    """
    获取特定健康检查的详细信息

    Args:
        check_name: 检查名称

    Returns:
        检查结果详情
    """
    health_checker = get_health_checker()
    result = await health_checker.check(check_name)

    return result.to_dict()


@router.get("/api/v1/cache/stats")
async def cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息

    Returns:
        缓存统计信息，包括命中率、操作次数等
    """
    from cache import get_cache_manager

    try:
        cache_manager = get_cache_manager()
        return cache_manager.get_stats()
    except (ImportError, AttributeError, RuntimeError, ConnectionError) as e:
        logger.error(f"获取缓存统计失败: {e}")
        return {"error": str(e), "enabled": False}


@router.get("/api/v1/cache/metrics")
async def cache_metrics() -> Dict[str, Any]:
    """
    获取缓存性能指标

    Returns:
        缓存性能指标，包括命中率、延迟等
    """
    try:
        from monitoring import get_cache_metrics_collector

        collector = get_cache_metrics_collector()
        return collector.get_stats()
    except (ImportError, AttributeError, RuntimeError) as e:
        logger.error(f"获取缓存指标失败: {e}")
        return {"error": str(e), "enabled": False}


@router.get("/api/v1/cache/prometheus", response_class=Response)
async def cache_prometheus_metrics() -> Response:
    """
    获取Prometheus格式的缓存指标

    Returns:
        Prometheus文本格式的缓存指标
    """
    try:
        from monitoring import get_cache_metrics_collector

        collector = get_cache_metrics_collector()
        prometheus_text = collector.get_prometheus_metrics()

        return Response(
            content=prometheus_text,
            media_type="text/plain",
        )
    except (ImportError, AttributeError, RuntimeError) as e:
        logger.error(f"导出缓存指标失败: {e}")
        return Response(
            content=f"# Error: {str(e)}",
            media_type="text/plain",
        )


@router.post("/api/v1/cache/reset")
async def reset_cache_stats(admin: bool = Depends(require_admin_api_key)) -> Dict[str, Any]:
    """
    重置缓存统计信息

    Returns:
        操作结果
    """
    from cache import get_cache_manager

    try:
        cache_manager = get_cache_manager()
        cache_manager.reset_stats()

        # 同时重置指标收集器
        try:
            from monitoring import get_cache_metrics_collector

            collector = get_cache_metrics_collector()
            collector.reset()
        except (ImportError, AttributeError):  # 指标收集器可能不可用
            pass  # 指标收集器是可选的，失败时忽略

        return {"status": "success", "message": "缓存统计已重置"}
    except (ImportError, AttributeError, RuntimeError, ConnectionError) as e:
        logger.error(f"重置缓存统计失败: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/v1/cache/clear")
async def clear_cache(admin: bool = Depends(require_admin_api_key)) -> Dict[str, Any]:
    """
    清空所有缓存

    Returns:
        操作结果
    """
    from cache import get_cache_manager

    try:
        cache_manager = get_cache_manager()
        await cache_manager.clear()

        return {"status": "success", "message": "所有缓存已清空"}
    except (ImportError, AttributeError, RuntimeError, ConnectionError) as e:
        logger.error(f"清空缓存失败: {e}")
        return {"status": "error", "message": str(e)}
