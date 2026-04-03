"""
pytest 配置文件
遵循开发规则测试规范
"""
import os
import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

# 设置测试环境变量 - 使用现有数据库
os.environ.setdefault("DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6381/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_api_key_for_testing")
os.environ.setdefault("ALLOWED_ORIGINS", '["http://localhost:3000","http://localhost:8008","http://localhost:8000"]')

# 在测试环境中禁用限流或设置高限制
os.environ["RATE_LIMIT_REQUESTS"] = "10000"  # 大幅提高限流阈值
os.environ["RATE_LIMIT_WHITELIST"] = "127.0.0.1,::1"  # 添加本地IP到白名单

# 测试数据库配置
TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture
async def test_db() -> AsyncGenerator:
    """测试数据库连接"""
    import asyncpg

    # asyncpg.create_pool doesn't accept connect_timeout, use timeout instead
    pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=2, max_size=10, timeout=10)
    yield pool
    await pool.close()


@pytest.fixture
def test_client():
    """测试客户端（function级别，确保测试隔离）"""
    from fastapi.testclient import TestClient
    from backend.main import app

    # 使用 raise_server_exceptions=False 避免 event loop 问题
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def mock_llm_api():
    """Mock LLM API调用 - 简化版本，直接mock推理API响应"""
    # Mock整个推理服务，让它返回模拟数据
    with patch("backend.api.v1.reasoning.ReasoningService.reason", return_value={
        "answer": "这是测试回答",
        "query_type": "factual",
        "steps": [],
        "sources": [],
        "confidence": 0.9,
        "reasoning_time": 1.0,
        "model_used": "test-model"
    }):
        yield


@pytest.fixture
def mock_redis():
    """Mock Redis连接（用于需要Redis但不需要真实连接的测试）"""
    import redis
    from unittest.mock import MagicMock

    # 创建一个mock Redis客户端
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = 0
    mock_redis.ttl.return_value = 0
    mock_redis.expire.return_value = True
    mock_redis.ping.return_value = True

    return mock_redis
