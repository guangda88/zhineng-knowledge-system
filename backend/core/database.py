"""数据库连接管理模块

将数据库连接池逻辑从main.py中分离出来。
仅使用 asyncpg 连接池，不再维护 SQLAlchemy 引擎。

Import direction: database imports from config only.
It must NOT import from services, api, or higher-level core modules.
"""

import asyncio
import logging
import os
from typing import Optional

import asyncpg
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# 数据库连接池 (asyncpg)
db_pool: Optional[asyncpg.Pool] = None

# 异步安全锁
_db_pool_lock = asyncio.Lock()


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
            max_size = getattr(config, "DB_MAX_CONNECTIONS", 10) or 10
            min_size = max(2, max_size // 5)
        except (ImportError, AttributeError, ValueError, TypeError):
            max_size = 10
            min_size = 2
        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=30,
            timeout=5,
            max_inactive_connection_lifetime=60,
        )
        logger.info(
            f"Database pool initialized (min={min_size}, max={max_size}, "
            f"command_timeout=30s, timeout=5s)"
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


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for ORM models"""
    pass
