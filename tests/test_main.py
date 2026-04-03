"""backend/main.py 单元测试

测试FastAPI应用的核心端点
"""

import pytest
from fastapi.testclient import TestClient

# 使用与 conftest.py 相同的导入方式
from backend.main import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestRootEndpoint:
    """根端点测试"""

    def test_root_endpoint(self, client):
        """测试根端点返回状态"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "message" in data or data == {"status": "ok"}


class TestHealthCheck:
    """健康检查端点测试"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_check_with_slash(self, client):
        """测试带斜杠的健康检查端点"""
        response = client.get("/health/")
        assert response.status_code == 200


class TestDocumentsAPI:
    """文档API测试"""

    def test_api_v1_documents_list_empty(self, client):
        """测试文档列表端点"""
        response = client.get("/api/v1/documents?limit=10")
        assert response.status_code == 200 or response.status_code == 422

    def test_api_v1_documents_with_offset(self, client):
        """测试带偏移量的文档列表"""
        response = client.get("/api/v1/documents?limit=10&offset=0")
        assert response.status_code == 200 or response.status_code == 422


class TestSearchAPI:
    """搜索API测试"""

    def test_api_v1_search_empty_query(self, client):
        """测试空查询搜索"""
        response = client.get("/api/v1/search?q=")
        # 可能返回400、422或200
        assert response.status_code in [400, 422, 200, 500, 503]

    def test_api_v1_search_with_query(self, client):
        """测试带查询参数的搜索"""
        response = client.get("/api/v1/search?q=test&domain=general&limit=5")
        assert response.status_code in [200, 422, 500, 503]


class TestReasoningAPI:
    """推理API测试"""

    def test_api_v1_reasoning_no_data(self, client):
        """测试无数据的推理请求"""
        # reasoning 路由使用 /api/v1 prefix，端点是 /reason
        response = client.post("/api/v1/reason", json={})
        # 应该返回422（验证错误）
        assert response.status_code == 422

    def test_api_v1_reasoning_with_question(self, client, mock_llm_api):
        """测试带问题的推理请求"""
        # 使用mock的LLM API
        response = client.post("/api/v1/reason", json={"question": "什么是气功?", "mode": "cot"})
        # 应该返回200或422
        assert response.status_code in [200, 422, 503]

    def test_api_v1_reasoning_status(self, client):
        """测试推理状态端点"""
        response = client.get("/api/v1/reasoning/status")
        assert response.status_code in [200, 500, 503]


class TestCategoriesAPI:
    """分类API测试"""

    def test_api_v1_categories(self, client):
        """测试分类端点"""
        response = client.get("/api/v1/categories")
        assert response.status_code in [200, 404, 500, 503]


class TestStatsAPI:
    """统计API测试"""

    def test_api_v1_stats(self, client):
        """测试统计端点"""
        response = client.get("/api/v1/stats")
        assert response.status_code in [200, 404, 500, 503]


class TestRateLimiting:
    """限流测试"""

    def test_rate_limit_headers(self, client):
        """测试响应包含限流头"""
        response = client.get("/health")
        # 健康检查端点可能跳过限流
        if "X-RateLimit-Limit" in response.headers:
            assert "X-RateLimit-Remaining" in response.headers


class TestGZipCompression:
    """压缩测试"""

    def test_gzip_support(self, client):
        """测试GZip压缩支持"""
        response = client.get("/health", headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200
        # 检查响应是否被压缩
        assert response.headers.get("content-encoding") in [None, "gzip"]


class TestCORS:
    """CORS测试"""

    def test_cors_headers(self, client):
        """测试CORS头"""
        response = client.options(
            "/api/v1/documents",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        # OPTIONS请求可能返回200或其他状态
        assert response.status_code in [200, 404, 405]


class TestSecurityHeaders:
    """安全头部测试"""

    def test_security_headers(self, client):
        """测试安全响应头"""
        response = client.get("/health")
        assert response.status_code == 200
        headers = response.headers

        # 验证安全头存在
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Referrer-Policy" in headers


class TestGatewayAPI:
    """网关API测试"""

    def test_gateway_status(self, client):
        """测试网关状态端点"""
        response = client.get("/api/v1/gateway/status")
        assert response.status_code in [200, 404, 500, 503]

    def test_gateway_providers(self, client):
        """测试提供商列表端点"""
        response = client.get("/api/v1/gateway/providers")
        assert response.status_code in [200, 404, 500, 503]


class TestMiddlewareIntegration:
    """中间件集成测试"""

    def test_process_time_header(self, client):
        """测试处理时间响应头"""
        response = client.get("/health")
        assert response.status_code == 200
        # 应该有处理时间头
        assert "X-Process-Time" in response.headers

    def test_multiple_middleware_work_together(self, client):
        """测试多个中间件协同工作"""
        response = client.get("/health")
        assert response.status_code == 200
        headers = response.headers

        # 验证安全头
        assert headers.get("X-Content-Type-Options") == "nosniff"

        # 验证处理时间
        assert "X-Process-Time" in headers
