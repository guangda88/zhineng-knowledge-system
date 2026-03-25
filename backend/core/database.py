"""数据库连接管理模块

将数据库连接池逻辑从main.py中分离出来
"""

import logging
import os
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# 数据库连接池
db_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """初始化数据库连接池"""
    global db_pool
    if db_pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Please set it before starting the application."
            )
        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=10,
            max_size=50,
            command_timeout=30,
            max_inactive_connection_lifetime=300
        )
        logger.info("Database pool initialized")
    return db_pool


async def close_db_pool() -> None:
    """关闭数据库连接池"""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logger.info("Database pool closed")


def get_db_pool() -> Optional[asyncpg.Pool]:
    """获取当前数据库连接池（不初始化）"""
    return db_pool
