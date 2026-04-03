"""数据库连接管理模块

将数据库连接池逻辑从main.py中分离出来
包含 asyncpg 连接池和 SQLAlchemy ORM 支持

Import direction: database imports from config only.
It must NOT import from services, api, or higher-level core modules.
"""

import asyncio
import logging
import os
from typing import Optional

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# 数据库连接池 (asyncpg)
db_pool: Optional[asyncpg.Pool] = None

# SQLAlchemy ORM 引擎
async_engine = None
async_session_factory = None

# 异步安全锁
_db_pool_lock = asyncio.Lock()
_engine_lock = asyncio.Lock()

# SQLAlchemy 声明式基类
Base = declarative_base()


async def init_db_pool() -> asyncpg.Pool:
    """初始化数据库连接池"""
    global db_pool
    if db_pool is not None:
        return db_pool
    async with _db_pool_lock:
        if db_pool is not None:
            return db_pool
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Please set it before starting the application."
            )
        try:
            from backend.config import get_config

            config = get_config()
            max_size = getattr(config, "DB_MAX_CONNECTIONS", 50) or 50
            min_size = max(2, max_size // 5)
        except (ImportError, AttributeError, ValueError, TypeError):
            max_size = 50
            min_size = 10
        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=10,
            timeout=5,
            max_inactive_connection_lifetime=300,
        )
        logger.info(
            f"Database pool initialized (min={min_size}, max={max_size}, "
            f"command_timeout=10s, timeout=5s)"
        )
    return db_pool


async def close_db_pool() -> None:
    """关闭数据库连接池"""
    global db_pool
    try:
        if db_pool:
            await db_pool.close()
            db_pool = None
            logger.info("Database pool closed")
    except Exception as e:
        logger.error(f"关闭数据库连接池失败: {e}")
        db_pool = None


def get_db_pool() -> Optional[asyncpg.Pool]:
    """获取当前数据库连接池（不初始化）"""
    return db_pool


# ============== SQLAlchemy ORM 支持 ==============


async def init_async_engine():
    """初始化 SQLAlchemy 异步引擎"""
    global async_engine, async_session_factory

    if async_engine is not None:
        return
    async with _engine_lock:
        if async_engine is not None:
            return
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # 将 postgresql:// 转换为 postgresql+asyncpg://
        if database_url.startswith("postgresql://"):
            async_database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            async_database_url = database_url

        async_engine = create_async_engine(
            async_database_url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True
        )

        async_session_factory = sessionmaker(
            async_engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info("SQLAlchemy async engine initialized")


async def close_async_engine():
    """关闭 SQLAlchemy 异步引擎"""
    global async_engine, async_session_factory

    try:
        if async_engine:
            await async_engine.dispose()
            async_engine = None
            async_session_factory = None
            logger.info("SQLAlchemy async engine closed")
    except Exception as e:
        logger.error(f"关闭SQLAlchemy引擎失败: {e}")
        async_engine = None
        async_session_factory = None


async def get_async_session() -> AsyncSession:
    """获取 SQLAlchemy 异步会话（依赖注入）"""
    if async_session_factory is None:
        await init_async_engine()

    async with async_session_factory() as session:
        yield session
