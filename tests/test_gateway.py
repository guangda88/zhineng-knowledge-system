"""Gateway模块单元测试

测试路由器、限流器和熔断器的功能
"""

import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.gateway.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
)
from backend.gateway.rate_limiter import (
    DEFAULT_REQUEST_LIMIT,
    DEFAULT_WINDOW_SECONDS,
    InMemoryRateLimiter,
    RateLimit,
    RateLimiter,
    TokenBucketRateLimiter,
)
from backend.gateway.router import APIGateway, RoutingResult, RoutingStrategy, ServiceEndpoint

# ============================================================================
# Mock Domain类
# ============================================================================


@dataclass
class MockDomain:
    """模拟领域类"""

    name: str
    enabled: bool = True
    priority: int = 0

    async def query(self, question: str, **kwargs):
        """模拟查询方法"""
        return f"Answer from {self.name} for: {question}"

    async def health_check(self):
        """模拟健康检查"""
        return {"domain": self.name, "status": "healthy"}


# ============================================================================
# APIGateway测试
# ============================================================================


class TestAPIGateway:
    """API网关测试套件"""

    @pytest.fixture
    def mock_registry(self):
        """创建模拟的领域注册表"""
        registry = MagicMock()
        registry.get = MagicMock(side_effect=self._get_domain)
        registry.get_enabled = MagicMock(
            return_value=[
                MockDomain("qigong", enabled=True),
                MockDomain("tcm", enabled=True),
                MockDomain("general", enabled=True),
            ]
        )
        registry.health_check = AsyncMock(
            return_value={
                "total_domains": 3,
                "domains": [{"domain": "qigong", "status": "healthy"}],
            }
        )
        return registry

    def _get_domain(self, name):
        """模拟get方法"""
        domains = {
            "qigong": MockDomain("qigong", enabled=True),
            "tcm": MockDomain("tcm", enabled=True),
            "general": MockDomain("general", enabled=True),
            "disabled": MockDomain("disabled", enabled=False),
        }
        return domains.get(name)

    @pytest.fixture
    def gateway(self, mock_registry):
        """创建网关实例"""
        return APIGateway(domain_registry=mock_registry)

    def test_init_default_registry(self):
        """测试使用默认注册表初始化"""
        with patch("backend.gateway.router.get_registry") as mock_get:
            mock_reg = MagicMock()
            mock_get.return_value = mock_reg

            gw = APIGateway()
            assert gw._registry == mock_reg
            assert gw._strategy == RoutingStrategy.DOMAIN_MATCH

    def test_init_custom_registry(self, mock_registry):
        """测试使用自定义注册表初始化"""
        gw = APIGateway(domain_registry=mock_registry)
        assert gw._registry == mock_registry

    def test_add_endpoint(self, gateway):
        """测试添加服务端点"""
        endpoint = ServiceEndpoint(name="test_service", url="http://localhost:8001")
        gateway.add_endpoint("qigong", endpoint)

        assert "qigong" in gateway._endpoints
        assert len(gateway._endpoints["qigong"]) == 1
        assert gateway._endpoints["qigong"][0].name == "test_service"

    def test_remove_endpoint(self, gateway):
        """测试移除服务端点"""
        endpoint1 = ServiceEndpoint(name="svc1", url="http://localhost:8001")
        endpoint2 = ServiceEndpoint(name="svc2", url="http://localhost:8002")

        gateway.add_endpoint("qigong", endpoint1)
        gateway.add_endpoint("qigong", endpoint2)
        gateway.remove_endpoint("qigong", "http://localhost:8001")

        assert len(gateway._endpoints["qigong"]) == 1
        assert gateway._endpoints["qigong"][0].url == "http://localhost:8002"

    def test_set_routing_strategy(self, gateway):
        """测试设置路由策略"""
        gateway.set_routing_strategy(RoutingStrategy.ROUND_ROBIN)
        assert gateway._strategy == RoutingStrategy.ROUND_ROBIN

    def test_detect_domain_qigong(self, gateway):
        """测试检测气功领域"""
        question = "什么是八段锦气功？"
        domain = gateway.detect_domain(question)
        assert domain == "qigong"

    def test_detect_domain_tcm(self, gateway):
        """测试检测中医领域"""
        question = "针灸和经络有什么关系？"
        domain = gateway.detect_domain(question)
        assert domain == "tcm"

    def test_detect_domain_confucian(self, gateway):
        """测试检测儒家领域"""
        question = "孔子论语中的仁义礼智是什么？"
        domain = gateway.detect_domain(question)
        assert domain == "confucian"

    def test_detect_domain_general(self, gateway):
        """测试检测默认通用领域"""
        question = "今天天气怎么样？"
        domain = gateway.detect_domain(question)
        assert domain == "general"

    def test_detect_domain_case_insensitive(self, gateway):
        """测试领域检测不区分大小写"""
        question = "太极拳和气功有什么区别？"
        domain = gateway.detect_domain(question)
        assert domain == "qigong"

    @pytest.mark.asyncio
    async def test_route_to_qigong(self, gateway, mock_registry):
        """测试路由到气功领域"""
        result = await gateway.route("八段锦怎么练？")

        assert result.domain == "qigong"
        assert callable(result.handler)
        assert result.strategy == "domain_match"

    @pytest.mark.asyncio
    async def test_route_to_disabled_domain_fallback(self, mock_registry):
        """测试禁用领域降级到通用领域"""
        mock_registry.get = MagicMock(return_value=MockDomain("disabled", enabled=False))
        mock_registry.get.side_effect = None

        gateway = APIGateway(domain_registry=mock_registry)

        # 修改get的第二次调用返回general
        def get_with_fallback(name):
            if name == "general":
                return MockDomain("general", enabled=True)
            return MockDomain("disabled", enabled=False)

        mock_registry.get.side_effect = get_with_fallback

        result = await gateway.route("八段锦怎么练？")
        assert result.domain == "general"

    @pytest.mark.asyncio
    async def test_route_no_available_domain(self, mock_registry):
        """测试没有可用领域时抛出异常"""
        mock_registry.get = MagicMock(return_value=None)

        gateway = APIGateway(domain_registry=mock_registry)

        with pytest.raises(RuntimeError, match="没有可用的领域处理器"):
            await gateway.route("test question")

    @pytest.mark.asyncio
    async def test_route_increments_connection(self, gateway):
        """测试路由增加连接数"""
        endpoint = ServiceEndpoint(
            name="test", url="http://localhost:8001", health=True, connections=5
        )
        gateway.add_endpoint("qigong", endpoint)

        await gateway.route("八段锦")

        assert endpoint.connections == 6

    def test_select_endpoint_least_connections(self, gateway):
        """测试最少连接策略选择端点"""
        ep1 = ServiceEndpoint("e1", "http://localhost:8001", connections=10)
        ep2 = ServiceEndpoint("e2", "http://localhost:8002", connections=2)
        ep3 = ServiceEndpoint("e3", "http://localhost:8003", connections=5)

        gateway.add_endpoint("qigong", ep1)
        gateway.add_endpoint("qigong", ep2)
        gateway.add_endpoint("qigong", ep3)
        gateway.set_routing_strategy(RoutingStrategy.LEAST_CONNECTIONS)

        selected = gateway._select_endpoint("qigong")
        assert selected.name == "e2"

    def test_select_endpoint_round_robin(self, gateway):
        """测试轮询策略"""
        ep1 = ServiceEndpoint("e1", "http://localhost:8001")
        ep2 = ServiceEndpoint("e2", "http://localhost:8002")

        gateway.add_endpoint("qigong", ep1)
        gateway.add_endpoint("qigong", ep2)
        gateway.set_routing_strategy(RoutingStrategy.ROUND_ROBIN)

        # 第一次轮询
        selected1 = gateway._select_endpoint("qigong")
        assert selected1.name == "e1"

        # 更新索引
        gateway._metrics["round_robin_index"] = 1

        # 第二次轮询
        selected2 = gateway._select_endpoint("qigong")
        assert selected2.name == "e2"

    def test_select_endpoint_filters_unhealthy(self, gateway):
        """测试过滤不健康的端点"""
        ep1 = ServiceEndpoint("e1", "http://localhost:8001", health=False)
        ep2 = ServiceEndpoint("e2", "http://localhost:8002", health=True)

        gateway.add_endpoint("qigong", ep1)
        gateway.add_endpoint("qigong", ep2)

        selected = gateway._select_endpoint("qigong")
        assert selected.name == "e2"

    def test_select_endpoint_no_healthy(self, gateway):
        """测试没有健康端点时返回None"""
        ep1 = ServiceEndpoint("e1", "http://localhost:8001", health=False)
        gateway.add_endpoint("qigong", ep1)

        selected = gateway._select_endpoint("qigong")
        assert selected is None

    def test_select_endpoint_no_endpoints(self, gateway):
        """测试没有端点时返回None"""
        selected = gateway._select_endpoint("nonexistent")
        assert selected is None

    @pytest.mark.asyncio
    async def test_route_multi_specific_domains(self, gateway):
        """测试多领域路由指定领域"""
        results = await gateway.route_multi("test question", domains=["qigong", "tcm"])

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_route_multi_all_domains(self, gateway, mock_registry):
        """测试多领域路由所有启用领域"""
        results = await gateway.route_multi("test question")

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_route_multi_handles_exceptions(self, gateway, mock_registry):
        """测试多领域路由处理异常"""
        # 创建一个会抛异常的领域
        failing_domain = MockDomain("failing", enabled=True)
        failing_domain.query = AsyncMock(side_effect=Exception("Test error"))

        mock_registry.get_enabled = MagicMock(
            return_value=[
                MockDomain("qigong", enabled=True),
                failing_domain,
            ]
        )

        results = await gateway.route_multi("test question")

        # 应该只返回成功的结果
        assert len(results) == 1

    def test_get_metrics(self, gateway):
        """测试获取网关指标"""
        gateway._metrics["domain_qigong"] = 10
        gateway._metrics["domain_tcm"] = 5
        gateway._metrics["routing_time"] = 0.5

        metrics = gateway.get_metrics()

        assert metrics["strategy"] == "domain_match"
        assert metrics["total_requests"] == 15
        assert metrics["domain_distribution"]["domain_qigong"] == 10
        assert metrics["avg_routing_time"] == pytest.approx(0.5 / 15)

    @pytest.mark.asyncio
    async def test_health_check(self, gateway, mock_registry):
        """测试网关健康检查"""
        health = await gateway.health_check()

        assert health["status"] == "healthy"
        assert health["strategy"] == "domain_match"
        assert "domains" in health

    def test_reset_metrics(self, gateway):
        """测试重置指标"""
        gateway._metrics["domain_qigong"] = 10
        gateway.reset_metrics()

        assert len(gateway._metrics) == 0


# ============================================================================
# ServiceEndpoint测试
# ============================================================================


class TestServiceEndpoint:
    """服务端点测试套件"""

    def test_to_dict(self):
        """测试转换为字典"""
        endpoint = ServiceEndpoint(
            name="test",
            url="http://localhost:8001",
            health=True,
            connections=5,
            response_time=0.1,
            error_count=2,
        )

        data = endpoint.to_dict()

        assert data["name"] == "test"
        assert data["url"] == "http://localhost:8001"
        assert data["health"] is True
        assert data["connections"] == 5
        assert data["response_time"] == 0.1
        assert data["error_count"] == 2


# ============================================================================
# RateLimiter测试
# ============================================================================


class TestRateLimit:
    """RateLimit配置测试套件"""

    def test_default_values(self):
        """测试默认值"""
        limit = RateLimit(requests=100, window=60)

        assert limit.requests == 100
        assert limit.window == 60

    def test_to_dict(self):
        """测试转换为字典"""
        limit = RateLimit(requests=100, window=60)
        data = limit.to_dict()

        assert data["requests"] == 100
        assert data["window"] == 60
        assert data["rate"] == "100/60s"


class TestInMemoryRateLimiter:
    """内存速率限制器测试套件"""

    @pytest.fixture
    def limiter(self):
        """创建限流器实例"""
        return InMemoryRateLimiter(default_limit=RateLimit(requests=5, window=10))

    def test_init_default_limit(self):
        """测试初始化默认限制"""
        limiter = InMemoryRateLimiter()

        assert limiter.default_limit.requests == DEFAULT_REQUEST_LIMIT
        assert limiter.default_limit.window == DEFAULT_WINDOW_SECONDS

    def test_init_custom_limit(self):
        """测试初始化自定义限制"""
        limit = RateLimit(requests=10, window=30)
        limiter = InMemoryRateLimiter(default_limit=limit)

        assert limiter.default_limit == limit

    def test_set_limit(self, limiter):
        """测试设置特定限制"""
        custom_limit = RateLimit(requests=20, window=60)
        limiter.set_limit("user1", custom_limit)

        assert limiter._limits["user1"] == custom_limit

    def test_whitelist_operations(self, limiter):
        """测试白名单操作"""
        limiter.whitelist = ["192.168.1.1", "127.0.0.1"]

        assert limiter.is_whitelisted("192.168.1.1")
        assert limiter.is_whitelisted("127.0.0.1")
        assert not limiter.is_whitelisted("10.0.0.1")

    @pytest.mark.asyncio
    async def test_whitelist_bypass(self, limiter):
        """测试白名单绕过限制"""
        limiter.whitelist = ["trusted_client"]

        allowed, info = await limiter.check("trusted_client")

        assert allowed is True
        assert info["whitelisted"] is True
        assert info["limit"] is None

    @pytest.mark.asyncio
    async def test_check_first_request(self, limiter):
        """测试首次请求通过"""
        allowed, info = await limiter.check("user1")

        assert allowed is True
        assert info["allowed"] is True
        assert info["current"] == 1
        assert info["remaining"] == 4

    @pytest.mark.asyncio
    async def test_check_within_limit(self, limiter):
        """测试在限制内的请求"""
        for i in range(3):
            allowed, info = await limiter.check("user1")
            assert allowed is True
            assert info["current"] == i + 1

    @pytest.mark.asyncio
    async def test_check_exceeds_limit(self, limiter):
        """测试超过限制的请求"""
        # 发送5个请求（达到限制）
        for _ in range(5):
            await limiter.check("user1")

        # 第6个请求应该被拒绝
        allowed, info = await limiter.check("user1")

        assert allowed is False
        assert info["allowed"] is False
        assert info["current"] >= 5
        assert "retry_after" in info

    @pytest.mark.asyncio
    async def test_check_sliding_window(self, limiter):
        """测试滑动窗口清理"""
        import time

        # 发送5个请求
        for _ in range(5):
            await limiter.check("user1")

        # 等待窗口过期
        time.sleep(0.2)
        limiter._requests["user1"] = [(time.time() - 20, 1)]  # 旧请求

        # 应该允许新请求
        allowed, info = await limiter.check("user1")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_reset(self, limiter):
        """测试重置限制"""
        # 发送几个请求
        for _ in range(3):
            await limiter.check("user1")

        # 重置
        await limiter.reset("user1")

        # 应该从零开始
        allowed, info = await limiter.check("user1")
        assert allowed is True
        assert info["current"] == 1

    @pytest.mark.asyncio
    async def test_reset_nonexistent_key(self, limiter):
        """测试重置不存在的键不应报错"""
        await limiter.reset("nonexistent")
        # 不应该抛出异常

    def test_get_stats(self, limiter):
        """测试获取统计信息"""
        limiter._limits["user1"] = RateLimit(10, 60)
        limiter._requests["user1"] = [(time.time(), 1)]
        limiter._requests["user2"] = [(time.time(), 1)]
        limiter.whitelist = ["192.168.1.1"]

        stats = limiter.get_stats()

        assert stats["total_keys"] == 2
        assert stats["whitelisted_keys"] == 1
        assert stats["custom_limits"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, limiter):
        """测试并发请求"""

        async def make_requests(user_id, count):
            results = []
            for _ in range(count):
                result = await limiter.check(user_id)
                results.append(result)
            return results

        # 并发发送请求
        results = await asyncio.gather(make_requests("user1", 3), make_requests("user2", 3))

        assert all(r[0][0] for r in results)
        assert all(r[1][0] for r in results)


class TestTokenBucketRateLimiter:
    """令牌桶速率限制器测试套件"""

    @pytest.fixture
    def limiter(self):
        """创建令牌桶限流器"""
        return TokenBucketRateLimiter(
            default_limit=RateLimit(requests=10, window=10), burst_multiplier=2.0
        )

    def test_init_default_burst(self):
        """测试默认突发倍数"""
        limiter = TokenBucketRateLimiter()
        assert limiter.burst_multiplier == 2.0

    def test_refill_rate(self, limiter):
        """测试令牌补充速率计算"""
        limit = RateLimit(requests=100, window=60)
        rate = limiter._refill_rate(limit)

        assert rate == pytest.approx(100 / 60)

    @pytest.mark.asyncio
    async def test_whitelist_bypass(self, limiter):
        """测试白名单绕过"""
        limiter.whitelist = ["trusted"]

        allowed, info = await limiter.check("trusted")

        assert allowed is True
        assert info["whitelisted"] is True

    @pytest.mark.asyncio
    async def test_first_request_creates_bucket(self, limiter):
        """测试首次请求创建令牌桶"""
        allowed, info = await limiter.check("user1")

        assert allowed is True
        assert "user1" in limiter._buckets
        # 初始令牌数应该是 limit * burst_multiplier
        tokens, _ = limiter._buckets["user1"]
        assert tokens == pytest.approx(10 * 2.0 - 1)  # 消耗了1个

    @pytest.mark.asyncio
    async def test_bucket_refill_over_time(self, limiter):
        """测试令牌随时间补充"""
        # 快速消耗一些令牌
        for _ in range(15):
            await limiter.check("user1")

        # 等待令牌补充
        await asyncio.sleep(0.5)

        # 现在应该允许一些请求
        allowed, _ = await limiter.check("user1")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_bucket_exhaustion(self, limiter):
        """测试令牌桶耗尽"""
        # 消耗所有令牌（初始20个）
        for _ in range(20):
            allowed, _ = await limiter.check("user1")
            assert allowed is True

        # 下一个请求应该被拒绝
        allowed, info = await limiter.check("user1")
        assert allowed is False
        assert "refill_in" in info

    @pytest.mark.asyncio
    async def test_burst_capacity(self, limiter):
        """测试突发容量"""
        # 允许突发超过基础速率
        limit = RateLimit(requests=5, window=10)
        limiter = TokenBucketRateLimiter(default_limit=limit, burst_multiplier=3.0)

        # 应该能处理 5 * 3 = 15 个突发请求
        for _ in range(15):
            allowed, _ = await limiter.check("user1")
            assert allowed is True

        # 第16个应该被拒绝
        allowed, _ = await limiter.check("user1")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_reset(self, limiter):
        """测试重置令牌桶"""
        await limiter.check("user1")
        assert "user1" in limiter._buckets

        await limiter.reset("user1")
        assert "user1" not in limiter._buckets


# ============================================================================
# CircuitBreaker测试
# ============================================================================


class TestCircuitBreakerConfig:
    """熔断器配置测试套件"""

    def test_default_values(self):
        """测试默认配置值"""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60.0
        assert config.half_open_max_calls == 3


class TestCircuitBreaker:
    """熔断器测试套件"""

    @pytest.fixture
    def breaker(self):
        """创建熔断器实例"""
        return CircuitBreaker("test_service")

    @pytest.fixture
    def sensitive_breaker(self):
        """创建敏感的熔断器（低阈值）"""
        return CircuitBreaker(
            "sensitive_service",
            config=CircuitBreakerConfig(failure_threshold=2, success_threshold=1, timeout=1.0),
        )

    def test_init(self, breaker):
        """测试初始化"""
        assert breaker.name == "test_service"
        assert breaker.state == CircuitState.CLOSED
        assert breaker._stats.total_calls == 0

    def test_state_property(self, breaker):
        """测试状态属性"""
        assert breaker.state == CircuitState.CLOSED

    def test_open_until_when_closed(self, breaker):
        """测试关闭状态时open_until为None"""
        assert breaker.open_until is None

    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        """测试成功调用"""

        async def success_func():
            return "success"

        result = await breaker.call(success_func)

        assert result == "success"
        assert breaker._stats.successful_calls == 1
        assert breaker._stats.total_calls == 1
        assert breaker._stats.failed_calls == 0

    @pytest.mark.asyncio
    async def test_failing_call(self, breaker):
        """测试失败调用"""

        async def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker._stats.failed_calls == 1
        assert breaker._stats.total_calls == 1
        assert breaker._stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_circuit_opens_on_threshold(self, sensitive_breaker):
        """测试达到失败阈值后熔断器打开"""

        async def fail_func():
            raise ValueError("test error")

        # 触发失败达到阈值
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)

        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)

        # 现在熔断器应该是打开状态
        assert sensitive_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self, sensitive_breaker):
        """测试打开状态拒绝调用"""

        async def fail_func():
            raise ValueError("test error")

        # 触发熔断
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)

        # 现在应该抛出熔断异常
        with pytest.raises(CircuitBreakerOpenError):
            await sensitive_breaker.call(fail_func)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, sensitive_breaker):
        """测试超时后进入半开状态"""

        async def fail_func():
            raise ValueError("test error")

        # 触发熔断
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)

        assert sensitive_breaker.state == CircuitState.OPEN

        # 等待超时
        await asyncio.sleep(1.1)

        # 下一次调用应该触发半开状态
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)

        assert sensitive_breaker.state == CircuitState.OPEN  # 失败后又打开

    @pytest.mark.asyncio
    async def test_recovery_from_half_open(self, sensitive_breaker):
        """测试从半开状态恢复"""

        async def success_func():
            return "success"

        async def fail_func():
            raise ValueError("test error")

        # 触发熔断
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)
        with pytest.raises(ValueError):
            await sensitive_breaker.call(fail_func)

        assert sensitive_breaker.state == CircuitState.OPEN

        # 等待超时
        await asyncio.sleep(1.1)

        # 成功调用应该触发恢复
        result = await sensitive_breaker.call(success_func)
        assert result == "success"
        assert sensitive_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_synchronous_function(self, breaker):
        """测试同步函数调用"""

        def sync_func():
            return "sync_result"

        result = await breaker.call(sync_func)
        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_multiple_success_threshold(self, breaker):
        """测试多个成功才能恢复"""
        breaker.config = CircuitBreakerConfig(failure_threshold=2, success_threshold=3, timeout=1.0)

        async def fail_func():
            raise ValueError("test")

        async def success_func():
            return "ok"

        # 触发熔断
        with pytest.raises(ValueError):
            await breaker.call(fail_func)
        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        # 等待超时
        await asyncio.sleep(1.1)

        # 需要多次成功才能恢复
        for _ in range(3):
            result = await breaker.call(success_func)
            assert result == "ok"

        assert breaker.state == CircuitState.CLOSED

    def test_get_stats(self, breaker):
        """测试获取统计信息"""
        breaker._stats.failed_calls = 3
        breaker._stats.total_calls = 10

        stats = breaker.get_stats()

        assert stats["name"] == "test_service"
        assert stats["state"] == "closed"
        assert stats["config"]["failure_threshold"] == 5
        assert stats["stats"]["failed_calls"] == 3
        assert stats["stats"]["failure_rate"] == 0.3

    def test_reset(self, breaker):
        """测试重置熔断器"""
        breaker._stats.failed_calls = 10
        breaker._state = CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker._stats.total_calls == 0
        assert breaker._stats.failed_calls == 0

    def test_state_transitions_recorded(self, sensitive_breaker):
        """测试状态转换被记录"""
        # 手动触发状态转换
        sensitive_breaker._transition_to(CircuitState.OPEN)
        sensitive_breaker._transition_to(CircuitState.HALF_OPEN)
        sensitive_breaker._transition_to(CircuitState.CLOSED)

        assert len(sensitive_breaker._stats.state_transitions) == 3
        assert sensitive_breaker._stats.state_transitions[0]["from"] == "closed"
        assert sensitive_breaker._stats.state_transitions[0]["to"] == "open"

    def test_open_until_property(self, sensitive_breaker):
        """测试open_until属性"""
        sensitive_breaker._state = CircuitState.OPEN
        sensitive_breaker._last_state_change = time.time()

        open_until = sensitive_breaker.open_until
        assert open_until is not None
        assert open_until > time.time()


class TestCircuitBreakerOpenError:
    """熔断器异常测试套件"""

    def test_exception_creation(self):
        """测试创建异常"""
        error = CircuitBreakerOpenError("Circuit is open", open_until=1234567890.0)

        assert str(error) == "Circuit is open"
        assert error.open_until == 1234567890.0

    def test_to_dict(self):
        """测试转换为字典"""
        error = CircuitBreakerOpenError("Circuit is open", open_until=time.time() + 60)

        data = error.to_dict()

        assert data["error"] == "circuit_breaker_open"
        assert "message" in data
        assert "open_until" in data
        assert "retry_after" in data


class TestCircuitBreakerRegistry:
    """熔断器注册表测试套件"""

    @pytest.fixture
    def registry(self):
        """创建注册表"""
        return CircuitBreakerRegistry()

    def test_get_or_create_new(self, registry):
        """测试获取或创建新的熔断器"""
        breaker = registry.get_or_create("service1")

        assert breaker.name == "service1"
        assert "service1" in registry._breakers

    def test_get_or_create_existing(self, registry):
        """测试获取已存在的熔断器"""
        breaker1 = registry.get_or_create("service1")
        breaker2 = registry.get_or_create("service1")

        assert breaker1 is breaker2

    def test_get_or_create_with_config(self, registry):
        """测试使用配置创建熔断器"""
        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = registry.get_or_create("service1", config=config)

        assert breaker.config.failure_threshold == 10

    def test_get_all_stats(self, registry):
        """测试获取所有熔断器统计"""
        registry.get_or_create("service1")
        registry.get_or_create("service2")

        stats = registry.get_all_stats()

        assert len(stats) == 2
        assert stats[0]["name"] in ["service1", "service2"]
        assert stats[1]["name"] in ["service1", "service2"]

    def test_reset_all(self, registry):
        """测试重置所有熔断器"""
        breaker1 = registry.get_or_create("service1")
        breaker1._stats.failed_calls = 10
        breaker1._state = CircuitState.OPEN

        registry.reset_all()

        assert breaker1.state == CircuitState.CLOSED
        assert breaker1._stats.failed_calls == 0
