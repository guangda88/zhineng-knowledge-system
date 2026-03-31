"""应用生命周期管理模块

提供FastAPI应用的启动和关闭逻辑，管理资源生命周期。
集成了服务管理器来统一管理所有服务的生命周期。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.config import get_config
from backend.core.service_manager import get_service_manager
from backend.core.services import DatabaseService, CacheService, VectorService, MonitoringService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    使用服务管理器统一管理应用启动和关闭时的资源初始化和清理。

    Args:
        app: FastAPI应用实例
    """
    config = get_config()

    logger.info(f"Starting application in {config.ENVIRONMENT} mode")

    # ========== 启动阶段 ==========

    # 获取服务管理器
    service_manager = get_service_manager()

    # 注册核心服务
    try:
        # 数据库服务（核心依赖）
        db_service = service_manager.register_service_class(
            DatabaseService,
            name="database"
        )

        # 缓存服务（可选依赖）
        cache_service = service_manager.register_service_class(
            CacheService,
            name="cache"
        )

        # 向量服务（依赖数据库）
        vector_service = service_manager.register_service_class(
            VectorService,
            name="vector"
        )

        # 监控服务
        monitoring_service = service_manager.register_service_class(
            MonitoringService,
            name="monitoring"
        )

        logger.info(f"Registered {service_manager.service_count} services")

        # 初始化配置监视器（如果启用）
        try:
            from backend.core.config_watcher import get_config_watcher, ConfigReloadHandler

            config_watcher = get_config_watcher()
            if config_watcher.enabled:
                # 添加配置重新加载处理器
                reload_handler = ConfigReloadHandler()
                config_watcher.add_handler(reload_handler)

                # 启动配置监视器
                await config_watcher.start()

                app.state.config_watcher = config_watcher
                logger.info("Configuration watcher initialized")
            else:
                logger.info("Configuration watcher is disabled")

        except Exception as e:
            logger.warning(f"Failed to initialize configuration watcher: {e}")

        # 启动所有服务
        await service_manager.start_all()

        # 将服务实例存储到app.state供其他模块使用
        app.state.service_manager = service_manager
        app.state.db_service = db_service
        app.state.cache_service = cache_service
        app.state.vector_service = vector_service
        app.state.monitoring_service = monitoring_service

        # 兼容性：保留原有的连接引用
        if db_service.pool:
            app.state.db_pool = db_service.pool
        if cache_service.client:
            app.state.redis_client = cache_service.client

    except Exception as e:
        logger.error(f"Failed to start services: {e}")
        # 清理已启动的服务
        try:
            await service_manager.stop_all()
        except Exception as cleanup_error:
            logger.error(f"Error during service cleanup: {cleanup_error}")
        raise

    # 初始化缓存系统（使用 CacheService 的 Redis 连接）
    try:
        from backend.cache import get_cache_manager

        cache_manager = get_cache_manager(redis_url=config.REDIS_URL)
        if cache_service and cache_service.client:
            from backend.cache.redis_cache import RedisCache
            cache_manager._l2_cache = RedisCache(url=config.REDIS_URL)
        logger.info("Cache system initialized")
    except Exception as e:
        logger.warning(f"Cache initialization failed (continuing without cache): {e}")

    # 初始化 SQLAlchemy ORM
    try:
        from backend.core.database import init_async_engine
        await init_async_engine()
        logger.info("SQLAlchemy ORM initialized")
    except Exception as e:
        logger.warning(f"SQLAlchemy initialization failed: {e}")

    # 初始化领域系统（如果存在）
    try:
        from domains import setup_domains
        db_pool = db_service.pool
        if db_pool:
            await setup_domains(db_pool)
            logger.info("Domains initialized")
    except ImportError:
        logger.debug("Domains module not available")
    except Exception as e:
        logger.warning(f"Domains initialization failed: {e}")

    # 初始化健康检查（如果存在）
    try:
        from monitoring import get_health_checker

        health_checker = get_health_checker()
        db_pool = db_service.pool
        if db_pool:

            async def check_database():
                """数据库健康检查"""
                from monitoring.health import HealthCheckResult, HealthStatus
                try:
                    async with db_pool.acquire() as conn:
                        await conn.fetchval("SELECT 1")
                    return HealthCheckResult(
                        name="database",
                        status=HealthStatus.HEALTHY,
                        message="数据库连接正常"
                    )
                except Exception as e:
                    logger.error("数据库连接失败", exc_info=True)
                    return HealthCheckResult(
                        name="database",
                        status=HealthStatus.UNHEALTHY,
                        message="数据库连接失败"
                    )

            health_checker.register("database", check_database, interval=30)
            await health_checker.start_background_checks()
            logger.info("Health checks started")
    except ImportError:
        logger.debug("Monitoring module not available")
    except Exception as e:
        logger.warning(f"Health checks initialization failed: {e}")

    # 初始化指标收集（如果存在）
    try:
        from monitoring import get_metrics_collector

        metrics = get_metrics_collector()
        metrics.increment_counter("app_startup")
        logger.info("Metrics initialized")
    except ImportError:
        logger.debug("Monitoring module not available")
    except Exception as e:
        logger.warning(f"Metrics initialization failed: {e}")

    # 初始化自学习调度器（如果启用）
    try:
        from backend.services.learning.scheduler import get_learning_scheduler
        from backend.config import get_config

        config = get_config()
        if getattr(config, 'ENABLE_AUTO_LEARNING', False):
            learning_scheduler = get_learning_scheduler()
            await learning_scheduler.start()
            app.state.learning_scheduler = learning_scheduler
            logger.info("Learning scheduler started")
        else:
            logger.info("Auto-learning is disabled")
    except ImportError:
        logger.debug("Learning scheduler not available")
    except Exception as e:
        logger.warning(f"Learning scheduler initialization failed: {e}")

    logger.info("Application started successfully")

    yield

    # ========== 关闭阶段 ==========

    logger.info("Shutting down application...")

    # 停止健康检查（如果存在）
    try:
        from monitoring import get_health_checker

        health_checker = get_health_checker()
        await health_checker.stop_background_checks()
        logger.info("Health checks stopped")
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Error stopping health checks: {e}")

    # 关闭领域系统（如果存在）
    try:
        from domains import get_registry

        registry = get_registry()
        await registry.shutdown_all()
        logger.info("Domains shutdown")
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Error shutting down domains: {e}")

    # 停止配置监视器（如果存在）
    try:
        if hasattr(app.state, 'config_watcher') and app.state.config_watcher:
            await app.state.config_watcher.stop()
            logger.info("Configuration watcher stopped")
    except Exception as e:
        logger.error(f"Error stopping configuration watcher: {e}")

    # 停止自学习调度器（如果存在）
    try:
        if hasattr(app.state, 'learning_scheduler') and app.state.learning_scheduler:
            await app.state.learning_scheduler.stop()
            logger.info("Learning scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping learning scheduler: {e}")

    # 通过服务管理器停止所有服务
    try:
        await service_manager.stop_all()
        logger.info("All services stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping services: {e}")

    # 关闭 SQLAlchemy ORM
    try:
        from backend.core.database import close_async_engine
        await close_async_engine()
        logger.info("SQLAlchemy ORM closed")
    except Exception as e:
        logger.error(f"Error closing SQLAlchemy: {e}")

    logger.info("Application shutdown complete")
