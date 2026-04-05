"""
pytest 配置文件
遵循开发规则测试规范
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# 设置测试环境变量 - 必须在导入 backend 之前
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6381/0")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_api_key_for_testing")
os.environ.setdefault(
    "ALLOWED_ORIGINS", '["http://localhost:3000","http://localhost:8008","http://localhost:8000"]'
)
os.environ["RATE_LIMIT_REQUESTS"] = "10000"
os.environ["RATE_LIMIT_WHITELIST"] = "127.0.0.1,::1"

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    yield


@pytest.fixture
async def test_db() -> AsyncGenerator:
    """测试数据库连接"""
    import asyncpg

    pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=2, max_size=10, timeout=10)
    yield pool
    await pool.close()


@pytest.fixture
def test_client():
    """测试客户端 — 测试环境跳过认证和lifespan"""
    from fastapi.testclient import TestClient

    from backend.main import create_app

    app = create_app(lifespan_ctx=_noop_lifespan)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def mock_llm_api():
    """Mock LLM API调用"""
    with patch(
        "backend.api.v1.reasoning.reasoning_answer",
        return_value=JSONResponse(
            content={
                "answer": "这是测试回答",
                "query_type": "factual",
                "steps": [],
                "sources": [],
                "confidence": 0.9,
                "reasoning_time": 1.0,
                "model_used": "test-model",
            }
        ),
    ):
        yield


@pytest.fixture
def mock_redis():
    """Mock Redis连接"""
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = 0
    mock_redis.ttl.return_value = 0
    mock_redis.expire.return_value = True
    mock_redis.ping.return_value = True

    return mock_redis
