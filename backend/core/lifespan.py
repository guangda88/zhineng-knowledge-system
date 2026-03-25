"""应用生命周期管理模块"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import close_db_pool, init_db_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    pool = await init_db_pool()
    logger.info("Database pool initialized")

    # 初始化缓存系统
    from cache import setup_cache
    from config import Config

    await setup_cache(redis_url=Config.REDIS_URL, config=None)  # 使用默认配置
    logger.info("Cache system initialized")

    # P5: 初始化领域系统
    from domains import setup_domains

    await setup_domains(pool)
    logger.info("Domains initialized")

    # P5: 初始化健康检查
    from monitoring import get_health_checker

    health_checker = get_health_checker()

    async def check_database():
        """数据库健康检查包装"""
        from monitoring.health import database_health_check

        return await database_health_check(pool)

    health_checker.register("database", check_database, interval=30)
    await health_checker.start_background_checks()
    logger.info("Health checks started")

    # P5: 初始化指标收集
    from monitoring import get_metrics_collector

    metrics = get_metrics_collector()
    metrics.increment_counter("app_startup")
    logger.info("Metrics initialized")

    # 初始化缓存指标收集
    try:
        from monitoring import setup_cache_metrics

        setup_cache_metrics(enabled=True, export_interval=60)
        logger.info("Cache metrics initialized")
    except Exception as e:
        logger.warning(f"缓存指标初始化失败: {e}")

    logger.info("Application started (P5: System Integration)")
    yield

    # 关闭时清理
    await close_db_pool()
    logger.info("Database pool closed")

    # P5: 清理领域系统
    from domains import get_registry

    registry = get_registry()
    await registry.shutdown_all()
    logger.info("Domains shutdown")

    # P5: 停止健康检查
    await health_checker.stop_background_checks()
    logger.info("Health checks stopped")

    logger.info("Application shutdown")
