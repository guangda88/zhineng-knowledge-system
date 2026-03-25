"""智能知识系统 API 测试
遵循开发规则：测试覆盖核心API功能
"""

import pytest
import httpx

BASE_URL = "http://localhost:8001"


class TestAPI:
    """API 测试套件"""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "categories" in data

    @pytest.mark.asyncio
    async def test_list_documents(self):
        """测试获取文档列表"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/documents")
            assert response.status_code == 200
            data = response.json()
            assert "documents" in data
            assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_search(self):
        """测试搜索功能"""
        async with httpx.AsyncClient() as client:
            from urllib.parse import quote
            query = quote("气功")
            response = await client.get(f"{BASE_URL}/api/v1/search?q={query}")
            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    @pytest.mark.asyncio
    async def test_ask_question(self):
        """测试问答功能"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/ask",
                json={"question": "什么是气功？"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "session_id" in data

    @pytest.mark.asyncio
    async def test_categories(self):
        """测试分类列表"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/categories")
            assert response.status_code == 200
            data = response.json()
            assert "categories" in data

    @pytest.mark.asyncio
    async def test_create_document(self):
        """测试创建文档"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/documents",
                json={
                    "title": "测试文档",
                    "content": "这是一个测试内容",
                    "category": "气功",
                    "tags": ["测试"]
                }
            )
            assert response.status_code in [201, 200]

    @pytest.mark.asyncio
    async def test_create_document_invalid_category(self):
        """测试无效分类"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/documents",
                json={
                    "title": "测试",
                    "content": "内容",
                    "category": "无效分类"
                }
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_retrieval_status(self):
        """测试检索服务状态"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/retrieval/status")
            assert response.status_code == 200
            data = response.json()
            assert "vector_enabled" in data

    @pytest.mark.asyncio
    async def test_hybrid_search(self):
        """测试混合搜索"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/search/hybrid",
                json={
                    "query": "气功",
                    "top_k": 5,
                    "use_vector": True,
                    "use_bm25": True
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    @pytest.mark.asyncio
    async def test_stats(self):
        """测试系统统计"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/stats")
            assert response.status_code == 200
            data = response.json()
            assert "document_count" in data


class TestPerformance:
    """性能测试套件"""

    @pytest.mark.asyncio
    async def test_response_time(self):
        """测试响应时间"""
        import time
        async with httpx.AsyncClient() as client:
            start = time.time()
            response = await client.get(f"{BASE_URL}/api/v1/documents")
            elapsed = time.time() - start
            assert response.status_code == 200
            assert elapsed < 2.0  # 2秒内响应


class TestValidation:
    """输入验证测试套件"""

    @pytest.mark.asyncio
    async def test_empty_question(self):
        """测试空问题"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/ask",
                json={"question": ""}
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_long_question(self):
        """测试超长问题"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/ask",
                json={"question": "问" * 500}
            )
            assert response.status_code == 422
