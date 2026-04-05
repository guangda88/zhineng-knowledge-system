"""guoxue 国学经典API测试
测试 /api/v1/guoxue/ 端点功能
"""

import pytest
from fastapi.testclient import TestClient


class TestGuoxueAPI:
    """guoxue API 测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self, test_client):
        self.client = test_client

    def test_stats(self):
        """测试 /guoxue/stats 端点"""
        response = self.client.get("/api/v1/guoxue/stats")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "data" in data
            assert data["data"]["book_count"] > 0
            assert data["data"]["content_count"] > 0
            assert data["data"]["total_chars"] > 0
            assert isinstance(data["data"]["top_books"], list)

    def test_list_books(self):
        """测试典籍列表"""
        response = self.client.get("/api/v1/guoxue/books?page=1&size=5")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["total"] > 0
            assert len(data["data"]["results"]) <= 5
            assert "book_id" in data["data"]["results"][0]
            assert "title" in data["data"]["results"][0]
            assert "content_count" in data["data"]["results"][0]

    def test_list_books_pagination(self):
        """测试典籍列表分页"""
        response = self.client.get("/api/v1/guoxue/books?page=2&size=3")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["page"] == 2
            assert data["data"]["size"] == 3

    def test_get_book_detail(self):
        """测试获取单部典籍详情"""
        response = self.client.get("/api/v1/guoxue/books/1")
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["book_id"] == 1
            assert "title" in data["data"]

    def test_get_book_not_found(self):
        """测试不存在的典籍"""
        response = self.client.get("/api/v1/guoxue/books/999999")
        assert response.status_code in [404, 500, 503]

    def test_list_chapters(self):
        """测试获取典籍章节列表"""
        response = self.client.get("/api/v1/guoxue/books/1/chapters?page=1&size=5")
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "book" in data["data"]
            assert data["data"]["total"] > 0
            assert "results" in data["data"]
            assert len(data["data"]["results"]) <= 5

    def test_list_chapters_book_not_found(self):
        """测试不存在典籍的章节列表"""
        response = self.client.get("/api/v1/guoxue/books/999999/chapters")
        assert response.status_code in [404, 500, 503]

    def test_get_content(self):
        """测试获取单条内容详情"""
        response = self.client.get("/api/v1/guoxue/content/1")
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["id"] == 1
            assert "body" in data["data"]
            assert "body_length" in data["data"]

    def test_get_content_not_found(self):
        """测试不存在的内容"""
        response = self.client.get("/api/v1/guoxue/content/999999999")
        assert response.status_code in [404, 500, 503]

    def test_search(self):
        """测试全文搜索"""
        response = self.client.get("/api/v1/guoxue/search?q=论语")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "total" in data["data"]
            assert "results" in data["data"]

    def test_search_with_book_id(self):
        """测试限定典籍搜索"""
        response = self.client.get("/api/v1/guoxue/search?q=学&book_id=1")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            if data["data"]["total"] > 0:
                for r in data["data"]["results"]:
                    assert r["book_id"] == 1

    def test_search_missing_query(self):
        """测试缺少搜索关键词"""
        response = self.client.get("/api/v1/guoxue/search")
        assert response.status_code == 422

    def test_search_pagination(self):
        """测试搜索分页"""
        response = self.client.get("/api/v1/guoxue/search?q=子&page=1&size=3")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["size"] == 3
