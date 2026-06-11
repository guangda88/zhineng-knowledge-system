"""应用生命周期管理模块

提供FastAPI应用的启动和关闭逻辑，管理资源生命周期。
集成了服务管理器来统一管理所有服务的生命周期。
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.config import get_config
from backend.core.service_manager import get_service_manager
from backend.core.services import CacheService, DatabaseService, MonitoringService, VectorService

logger = logging.getLogger(__name__)


def _safe_init(label: str):
    """装饰器：安全初始化子系统，ImportError 不警告，其他异常记录警告。"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ImportError:
                logger.debug(f"{label} not available")
                return None
            except Exception as e:
                logger.warning(f"{label} initialization failed: {e}")
                return None

        return wrapper

    return decorator


async def _init_config_watcher(app, config):
    """初始化配置热更新监视器"""
    from backend.core.config_watcher import ConfigReloadHandler, get_config_watcher

    config_watcher = get_config_watcher()
    if config_watcher.enabled:
        reload_handler = ConfigReloadHandler()
        config_watcher.add_handler(reload_handler)
        await config_watcher.start()
        app.state.config_watcher = config_watcher
        logger.info("Configuration watcher initialized")
    else:
        logger.info("Configuration watcher is disabled")


async def _init_cache_system(config, cache_service):
    """初始化缓存系统"""
    from backend.cache import get_cache_manager

    cache_manager = get_cache_manager(redis_url=config.REDIS_URL)
    if cache_service and cache_service.client:
        from backend.cache.redis_cache import RedisCache

        cache_manager._l2_cache = RedisCache(url=config.REDIS_URL)
    logger.info("Cache system initialized")


async def _warm_up_cache(config, db_service):
    """缓存预热：预加载常用查询结果到 Redis"""
    if not db_service or not db_service.pool:
        return
    try:
        from backend.cache import get_cache_manager

        cache_manager = get_cache_manager()
        if not cache_manager._l2_cache:
            return

        db_pool = db_service.pool

        async def _preload_categories():
            rows = await db_pool.fetch(
                "SELECT category, count(*) as cnt FROM documents GROUP BY category ORDER BY cnt DESC"
            )
            data = {row["category"]: row["cnt"] for row in rows}
            await cache_manager.set("categories", data, namespace="api_categories", ttl=1800)
            return len(data)

        async def _preload_domain_stats():
            rows = await db_pool.fetch(
                "SELECT category, count(*) as total, "
                "count(embedding) as embedded, "
                "avg(length(content))::int as avg_len "
                "FROM documents GROUP BY category"
            )
            data = {row["category"]: dict(row) for row in rows}
            await cache_manager.set("domain_stats", data, namespace="api_domain_stats", ttl=600)
            return len(data)

        async def _preload_total_stats():
            total = await db_pool.fetchval("SELECT count(*) FROM documents")
            embedded = await db_pool.fetchval(
                "SELECT count(*) FROM documents WHERE embedding IS NOT NULL"
            )
            data = {"total": total, "embedded": embedded}
            await cache_manager.set("stats", data, namespace="api_stats", ttl=300)
            return 1

        import asyncio

        results = await asyncio.gather(
            _preload_categories(),
            _preload_domain_stats(),
            _preload_total_stats(),
            return_exceptions=True,
        )
        ok = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"Cache warm-up: {ok} groups preloaded")
    except Exception as e:
        logger.warning(f"Cache warm-up skipped: {e}")


async def _init_domains(db_service):
    """初始化领域系统"""
    from domains import setup_domains

    db_pool = db_service.pool
    if db_pool:
        await setup_domains(db_pool)
        logger.info("Domains initialized")


async def _init_embedding_service_check():
    """检查远程嵌入服务可达性"""
    import os

    url = os.getenv("EMBEDDING_SERVICE_URL", "")
    if not url:
        logger.info("EMBEDDING_SERVICE_URL not set, skipping embedding health check")
        return

    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{url}/health")
            if resp.status_code == 200:
                logger.info(f"Embedding service reachable at {url}")
            else:
                logger.warning(f"Embedding service at {url} returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Embedding service at {url} unreachable: {e}")


async def _init_health_checks(db_service):
    """初始化健康检查"""
    from monitoring import get_health_checker

    health_checker = get_health_checker()
    db_pool = db_service.pool
    if db_pool:

        async def check_database():
            from backend.monitoring.health import HealthCheckResult, HealthStatus

            try:
                async with db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return HealthCheckResult(
                    name="database", status=HealthStatus.HEALTHY, message="数据库连接正常"
                )
            except Exception:
                logger.error("数据库连接失败", exc_info=True)
                return HealthCheckResult(
                    name="database", status=HealthStatus.UNHEALTHY, message="数据库连接失败"
                )

        health_checker.register("database", check_database, interval=30)

        async def check_embedding_service():
            from backend.monitoring.health import HealthCheckResult, HealthStatus

            url = os.getenv("EMBEDDING_SERVICE_URL", "")
            if not url:
                return HealthCheckResult(
                    name="embedding", status=HealthStatus.HEALTHY, message="未配置远程嵌入服务"
                )
            try:
                import httpx

                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{url}/health")
                if resp.status_code == 200:
                    return HealthCheckResult(
                        name="embedding", status=HealthStatus.HEALTHY, message="嵌入服务正常"
                    )
                return HealthCheckResult(
                    name="embedding",
                    status=HealthStatus.UNHEALTHY,
                    message=f"嵌入服务返回 {resp.status_code}",
                )
            except Exception as e:
                return HealthCheckResult(
                    name="embedding",
                    status=HealthStatus.UNHEALTHY,
                    message=f"嵌入服务不可达: {e}",
                )

        health_checker.register("embedding", check_embedding_service, interval=60)

        async def check_data_quality():
            from backend.monitoring.health import HealthCheckResult, HealthStatus

            try:
                total = await db_pool.fetchval("SELECT count(*) FROM documents")
                has_content = await db_pool.fetchval(
                    "SELECT count(*) FROM documents "
                    "WHERE length(content) > 100 "
                    "AND content NOT LIKE '来源: %' "
                    "AND content NOT LIKE '文件名: %'"
                )
                ratio = has_content / total if total > 0 else 0
                msg = f"有效内容: {has_content}/{total} ({ratio:.1%})"
                status = (
                    HealthStatus.HEALTHY
                    if ratio > 0.3
                    else (HealthStatus.DEGRADED if ratio > 0.05 else HealthStatus.UNHEALTHY)
                )
                return HealthCheckResult(name="data_quality", status=status, message=msg)
            except Exception as e:
                return HealthCheckResult(
                    name="data_quality",
                    status=HealthStatus.UNHEALTHY,
                    message=f"数据质量检查失败: {e}",
                )

        health_checker.register("data_quality", check_data_quality, interval=300)

        await health_checker.start_background_checks()
        logger.info("Health checks started")


async def _warmup_bm25(db_service):
    """预热 BM25 索引，消除首次查询冷启动延迟"""
    try:
        from backend.services.retrieval.bm25 import BM25Retriever

        retriever = BM25Retriever(db_service.pool)
        await retriever.initialize()
        logger.info("BM25 index pre-warmed")
    except Exception as e:
        logger.warning(f"BM25 warm-up skipped: {e}")


async def _init_metrics():
    """初始化指标收集"""
    from monitoring import get_metrics_collector

    metrics = get_metrics_collector()
    metrics.increment_counter("app_startup")
    logger.info("Metrics initialized")


async def _init_anomaly_detector():
    """初始化异常检测器"""
    from backend.monitoring.anomaly_detector import get_anomaly_detector

    detector = get_anomaly_detector()

    async def _alert_to_lingbus(alert):
        try:
            from backend.monitoring.anomaly_detector import AlertLevel

            level = "🟡" if alert.level == AlertLevel.WARNING else "🔴"
            subject = f"{level} 异常检测: {alert.rule_name}"
            body = f"{alert.message}\nvalue={alert.value:.1f} threshold={alert.threshold:.1f}"
            logger.warning(f"ANOMALY: {subject} — {body}")

            try:
                from mcp_lingbus import open_thread

                await open_thread(
                    topic=subject[:200],
                    sender="lingzhi",
                    recipients="all",
                    body=body,
                    channel="ecosystem",
                )
            except ImportError:
                pass
            except Exception as bus_err:
                logger.debug(f"LingBus通知跳过(非阻塞): {bus_err}")
        except Exception as e:
            logger.error(f"告警通知失败: {e}")

    detector.add_callback(_alert_to_lingbus)
    await detector.start()
    logger.info("Anomaly detector started")


async def _init_learning_scheduler(app):
    """初始化自学习调度器"""
    from backend.services.learning.scheduler import get_learning_scheduler

    learning_config = get_config()
    if getattr(learning_config, "ENABLE_AUTO_LEARNING", False):
        learning_scheduler = get_learning_scheduler()
        await learning_scheduler.start()
        app.state.learning_scheduler = learning_scheduler
        logger.info("Learning scheduler started")
    else:
        logger.info("Auto-learning is disabled")


async def _shutdown_anomaly_detector():
    """停止异常检测器"""
    from backend.monitoring.anomaly_detector import get_anomaly_detector

    await get_anomaly_detector().stop()
    logger.info("Anomaly detector stopped")


async def _shutdown_health_checks():
    """停止健康检查"""
    from monitoring import get_health_checker

    health_checker = get_health_checker()
    await health_checker.stop_background_checks()
    logger.info("Health checks stopped")


async def _shutdown_domains():
    """关闭领域系统"""
    from domains import get_registry

    registry = get_registry()
    await registry.shutdown_all()
    logger.info("Domains shutdown")


async def _shutdown_config_watcher(app):
    """停止配置监视器"""
    if hasattr(app.state, "config_watcher") and app.state.config_watcher:
        await app.state.config_watcher.stop()
        logger.info("Configuration watcher stopped")


async def _shutdown_learning_scheduler(app):
    """停止自学习调度器"""
    if hasattr(app.state, "learning_scheduler") and app.state.learning_scheduler:
        await app.state.learning_scheduler.stop()
        logger.info("Learning scheduler stopped")


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

    service_manager = get_service_manager()

    try:
        db_service = service_manager.register_service_class(DatabaseService, name="database")
        cache_service = service_manager.register_service_class(CacheService, name="cache")
        vector_service = service_manager.register_service_class(VectorService, name="vector")
        monitoring_service = service_manager.register_service_class(
            MonitoringService, name="monitoring"
        )

        logger.info(f"Registered {service_manager.service_count} services")

        await _safe_init("Config watcher")(_init_config_watcher)(app, config)
        await service_manager.start_all()

        app.state.service_manager = service_manager
        app.state.db_service = db_service
        app.state.cache_service = cache_service
        app.state.vector_service = vector_service
        app.state.monitoring_service = monitoring_service

        if db_service.pool:
            app.state.db_pool = db_service.pool
        if cache_service.client:
            app.state.redis_client = cache_service.client

    except Exception as e:
        logger.error(f"Failed to start services: {e}")
        try:
            await service_manager.stop_all()
        except Exception as cleanup_error:
            logger.error(f"Error during service cleanup: {cleanup_error}")
        raise

    await _safe_init("Cache system")(_init_cache_system)(config, cache_service)
    await _safe_init("Cache warm-up")(_warm_up_cache)(config, db_service)
    await _safe_init("BM25 index warm-up")(_warmup_bm25)(db_service)
    await _safe_init("Domains")(_init_domains)(db_service)
    await _safe_init("Health checks")(_init_health_checks)(db_service)
    await _safe_init("Embedding service check")(_init_embedding_service_check)()
    await _safe_init("Metrics")(_init_metrics)()
    await _safe_init("Anomaly detector")(_init_anomaly_detector)()
    await _safe_init("Learning scheduler")(_init_learning_scheduler)(app)

    logger.info("Application started successfully")

    yield

    # ========== 关闭阶段 ==========

    logger.info("Shutting down application...")

    await _safe_init("Health checks shutdown")(_shutdown_health_checks)()
    await _safe_init("Anomaly detector shutdown")(_shutdown_anomaly_detector)()
    await _safe_init("Domains shutdown")(_shutdown_domains)()
    await _safe_init("Config watcher shutdown")(_shutdown_config_watcher)(app)
    await _safe_init("Learning scheduler shutdown")(_shutdown_learning_scheduler)(app)

    try:
        await service_manager.stop_all()
        logger.info("All services stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping services: {e}")

    logger.info("Application shutdown complete")
