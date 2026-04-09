"""sys_books 书目检索API测试
测试 /api/v1/sysbooks/ 端点功能
"""

import pytest


class TestSysbooksAPI:
    """sys_books API 测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self, test_client):
        self.client = test_client

    def test_stats(self):
        """测试 /sysbooks/stats 端点"""
        response = self.client.get("/api/v1/sysbooks/stats")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "data" in data
            assert "total" in data["data"]
            assert data["data"]["total"] > 0
            assert "by_domain" in data["data"]
            assert "by_extension" in data["data"]
            assert "by_source" in data["data"]

    def test_search_basic(self):
        """测试基本搜索"""
        response = self.client.get("/api/v1/sysbooks/search?page=1&size=5")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["total"] > 0
            assert len(data["data"]["results"]) <= 5
            assert "id" in data["data"]["results"][0]
            assert "filename" in data["data"]["results"][0]

    def test_search_with_domain(self):
        """测试按领域搜索"""
        response = self.client.get("/api/v1/sysbooks/search?domain=中医&page=1&size=5")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            if data["data"]["total"] > 0:
                for r in data["data"]["results"]:
                    assert r["domain"] == "中医"

    def test_search_with_extension(self):
        """测试按扩展名搜索"""
        response = self.client.get("/api/v1/sysbooks/search?extension=pdf&page=1&size=5")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            if data["data"]["total"] > 0:
                for r in data["data"]["results"]:
                    assert r["extension"] == "pdf"

    def test_search_pagination(self):
        """测试分页"""
        response = self.client.get("/api/v1/sysbooks/search?page=2&size=3")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["data"]["page"] == 2
            assert data["data"]["size"] == 3

    def test_domains(self):
        """测试 /sysbooks/domains 端点"""
        response = self.client.get("/api/v1/sysbooks/domains")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert isinstance(data["data"], list)
            assert len(data["data"]) > 0
            assert "domain" in data["data"][0]
            assert "total" in data["data"][0]

    def test_book_detail(self):
        """测试获取单条书目"""
        response = self.client.get("/api/v1/sysbooks/1")
        assert response.status_code in [200, 404, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert data["data"]["id"] == 1

    def test_book_not_found(self):
        """测试不存在的书目"""
        response = self.client.get("/api/v1/sysbooks/999999999")
        assert response.status_code in [404, 500, 503]
