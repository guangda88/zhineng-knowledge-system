"""
pytest 配置文件
遵循开发规则测试规范
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator

# 测试数据库配置
TEST_DATABASE_URL = "postgresql://zhineng:zhineng123@localhost:5436/zhineng_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db() -> AsyncGenerator:
    """测试数据库连接"""
    import asyncpg

    pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=2, max_size=10)
    yield pool
    await pool.close()


@pytest.fixture
def test_client():
    """测试客户端"""
    from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)
