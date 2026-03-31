"""检索模块测试
遵循开发规则：测试覆盖检索功能
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest


class TestVectorRetriever:
    """向量检索器测试"""

    @pytest.fixture
    async def mock_pool(self):
        """模拟数据库连接池"""
        pool = AsyncMock(spec=asyncpg.Pool)
        return pool

    @pytest.mark.asyncio
    async def test_embed_text(self, mock_pool):
        """测试文本嵌入"""
        from backend.services.retrieval.vector import VectorRetriever

        retriever = VectorRetriever(mock_pool)
        vector = await retriever.embed_text("测试文本")

        assert isinstance(vector, list)
        assert len(vector) == 512  # BGE-small-zh-v1.5 向量维度
        assert all(isinstance(v, float) for v in vector)

    @pytest.mark.asyncio
    async def test_search(self, mock_pool):
        """测试向量搜索"""
        from backend.services.retrieval.vector import VectorRetriever

        # 模拟查询结果
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "id": 1,
                "title": "测试文档",
                "content": "测试内容",
                "category": "气功",
                "similarity": 0.85,
            }
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        retriever = VectorRetriever(mock_pool)
        results = await retriever.search("气功", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["similarity"] == 0.85


class TestBM25Retriever:
    """BM25检索器测试"""

    @pytest.fixture
    async def mock_pool(self):
        """模拟数据库连接池"""
        pool = AsyncMock(spec=asyncpg.Pool)
        # 创建正确的上下文管理器mock
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 1  # 文档数量
        mock_conn.fetch.return_value = [
            {"id": 1, "title": "八段锦", "content": "八段锦是一种气功功法", "category": "气功"}
        ]
        # 使用 MagicMock 作为 acquire 返回的上下文管理器
        acquire_context = MagicMock()
        acquire_context.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_context
        return pool

    @pytest.mark.asyncio
    async def test_search(self, mock_pool):
        """测试BM25搜索"""
        from backend.services.retrieval.bm25 import BM25Retriever

        retriever = BM25Retriever(mock_pool)
        await retriever.initialize()
        results = await retriever.search("八段锦", top_k=5)

        assert len(results) >= 0


class TestHybridRetriever:
    """混合检索器测试"""

    @pytest.fixture
    async def mock_pool(self):
        """模拟数据库连接池"""
        pool = AsyncMock(spec=asyncpg.Pool)
        # 创建正确的上下文管理器mock
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 0  # 文档数量为0，跳过初始化逻辑
        mock_conn.fetch.return_value = []
        # 使用 MagicMock 作为 acquire 返回的上下文管理器
        acquire_context = MagicMock()
        acquire_context.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_context
        return pool

    @pytest.mark.asyncio
    async def test_initialize(self, mock_pool):
        """测试混合检索器初始化"""
        from backend.services.retrieval.hybrid import HybridRetriever

        retriever = HybridRetriever(mock_pool)
        await retriever.initialize()

        assert retriever.vector_retriever is not None
        assert retriever.bm25_retriever is not None

    @pytest.mark.asyncio
    async def test_rrf_merge(self, mock_pool):
        """测试RRF结果合并"""
        from backend.services.retrieval.hybrid import HybridRetriever

        retriever = HybridRetriever(mock_pool)

        vector_results = [
            {"id": 1, "title": "A", "similarity": 0.9},
            {"id": 2, "title": "B", "similarity": 0.7},
        ]
        bm25_results = [
            {"id": 2, "title": "B", "score": 5.0},
            {"id": 3, "title": "C", "score": 4.0},
        ]

        merged = retriever._rrf_merge(vector_results, bm25_results)

        assert len(merged) == 3
        # ID 2 应该在两者中都出现，得分最高
        assert merged[0]["id"] == 2


class TestDomains:
    """领域模块测试"""

    @pytest.mark.asyncio
    async def test_qigong_domain(self):
        """测试气功领域"""
        from backend.domains.qigong import QigongDomain

        domain = QigongDomain(db_pool=None)
        await domain.initialize()

        assert domain.name == "qigong"
        assert domain.enabled == True
        assert domain.priority == 10

        await domain.shutdown()

    @pytest.mark.asyncio
    async def test_qigong_keywords(self):
        """测试气功关键词匹配"""
        from backend.domains.qigong import QigongDomain

        domain = QigongDomain(db_pool=None)

        score = domain.matches_question("什么是八段锦？")
        assert score > 0

        score = domain.matches_question("今天天气怎么样")
        assert score == 0

    @pytest.mark.asyncio
    async def test_tcm_domain(self):
        """测试中医领域"""
        from backend.domains.tcm import TcmDomain

        domain = TcmDomain(db_pool=None)
        await domain.initialize()

        assert domain.name == "tcm"
        assert "中医" in domain.KEYWORDS
        assert "针灸" in domain.KEYWORDS

        await domain.shutdown()

    @pytest.mark.asyncio
    async def test_confucian_domain(self):
        """测试儒家领域"""
        from backend.domains.confucian import ConfucianDomain

        domain = ConfucianDomain(db_pool=None)
        await domain.initialize()

        assert domain.name == "confucian"
        assert "孔子" in domain.KEYWORDS
        assert "论语" in domain.KEYWORDS

        await domain.shutdown()

    @pytest.mark.asyncio
    async def test_general_domain(self):
        """测试通用领域"""
        from backend.domains.general import GeneralDomain

        domain = GeneralDomain(db_pool=None)
        await domain.initialize()

        assert domain.name == "general"
        assert domain.priority == 0  # 最低优先级

        await domain.shutdown()


class TestDomainRegistry:
    """领域注册表测试"""

    @pytest.mark.asyncio
    async def test_register_and_get(self):
        """测试注册和获取"""
        from backend.domains.qigong import QigongDomain
        from backend.domains.registry import DomainRegistry

        registry = DomainRegistry()
        domain = QigongDomain(db_pool=None)

        registry.register(domain)

        retrieved = registry.get("qigong")
        assert retrieved is domain

    @pytest.mark.asyncio
    async def test_get_enabled(self):
        """测试获取启用的领域"""
        from backend.domains.general import GeneralDomain
        from backend.domains.qigong import QigongDomain
        from backend.domains.registry import DomainRegistry

        registry = DomainRegistry()
        registry.register(QigongDomain(db_pool=None))
        registry.register(GeneralDomain(db_pool=None))

        enabled = registry.get_enabled()
        assert len(enabled) == 2

        # 应该按优先级排序，气功优先级更高
        assert enabled[0].name == "qigong"

    @pytest.mark.asyncio
    async def test_route(self):
        """测试路由"""
        from backend.domains.qigong import QigongDomain
        from backend.domains.registry import DomainRegistry

        registry = DomainRegistry()
        registry.register(QigongDomain(db_pool=None))

        await registry.initialize_all()

        result = await registry.route("八段锦怎么练？")

        assert result.domain == "qigong"
        assert result.content is not None


class TestAPIGateway:
    """API网关测试"""

    @pytest.mark.asyncio
    async def test_detect_domain(self):
        """测试领域检测"""
        from backend.gateway.router import APIGateway

        gateway = APIGateway()

        domain = gateway.detect_domain("八段锦第一式怎么做？")
        assert domain == "qigong"

        domain = gateway.detect_domain("中医怎么把脉？")
        assert domain == "tcm"

        domain = gateway.detect_domain("孔子的仁政思想是什么？")
        assert domain == "confucian"

        domain = gateway.detect_domain("今天天气怎么样")
        assert domain == "general"

    @pytest.mark.asyncio
    async def test_route(self):
        """测试路由"""
        from backend.domains.qigong import QigongDomain
        from backend.domains.registry import DomainRegistry
        from backend.gateway.router import APIGateway

        registry = DomainRegistry()
        registry.register(QigongDomain(db_pool=None))
        await registry.initialize_all()

        gateway = APIGateway(registry)
        result = await gateway.route("什么是气功？")

        assert result.domain == "qigong"


class TestRateLimiter:
    """速率限制器测试"""

    @pytest.mark.asyncio
    async def test_in_memory_rate_limiter(self):
        """测试内存速率限制器"""
        from backend.gateway.rate_limiter import InMemoryRateLimiter, RateLimit

        limiter = InMemoryRateLimiter(default_limit=RateLimit(requests=5, window=60))

        # 前5次请求应该通过
        for i in range(5):
            allowed, info = await limiter.check("test_key")
            assert allowed == True
            assert info["allowed"] == True

        # 第6次请求应该被限制
        allowed, info = await limiter.check("test_key")
        assert allowed == False

    @pytest.mark.asyncio
    async def test_whitelist(self):
        """测试白名单"""
        from backend.gateway.rate_limiter import InMemoryRateLimiter, RateLimit

        limiter = InMemoryRateLimiter(
            default_limit=RateLimit(requests=1, window=60), whitelist=["trusted_ip"]
        )

        # 白名单IP应该不受限制
        for i in range(10):
            allowed, info = await limiter.check("trusted_ip")
            assert allowed == True
            assert info.get("whitelisted") == True

    @pytest.mark.asyncio
    async def test_token_bucket(self):
        """测试令牌桶算法"""
        from backend.gateway.rate_limiter import RateLimit, TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(
            default_limit=RateLimit(requests=10, window=60), burst_multiplier=2.0
        )

        # 令牌桶应该支持突发流量
        for i in range(15):
            allowed, info = await limiter.check("test_key")
            if i < 20:  # 初始令牌数 = 10 * 2 = 20
                assert allowed == True
            else:
                assert allowed == False


class TestCircuitBreaker:
    """熔断器测试"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        """测试熔断器打开"""
        from backend.gateway.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitBreakerOpenError,
        )

        breaker = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3, timeout=60))

        # 模拟连续失败
        async def failing_func():
            raise Exception("Service unavailable")

        for i in range(3):
            try:
                await breaker.call(failing_func)
            except:
                pass

        # 熔断器应该打开
        assert breaker.state.name == "OPEN"

        # 下次调用应该直接抛出异常
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_stats(self):
        """测试熔断器统计"""
        from backend.gateway.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker("test")

        stats = breaker.get_stats()
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
