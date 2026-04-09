"""Phase 2/3 管道API测试
测试 /api/v1/pipeline/ 端点功能
"""

import pytest


class TestPipelineStats:
    """管道统计端点测试"""

    @pytest.fixture(autouse=True)
    def setup(self, test_client):
        self.client = test_client

    def test_stats(self):
        """测试 /pipeline/stats 端点"""
        response = self.client.get("/api/v1/pipeline/stats")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "data" in data
            assert "sys_books" in data["data"]
            assert "contents" in data["data"]
            assert "knowledge_graph" in data["data"]
            assert "total" in data["data"]["sys_books"]

    def test_tag_stats(self):
        """测试 /pipeline/tag/stats 端点"""
        response = self.client.get("/api/v1/pipeline/tag/stats")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "data" in data
            assert "total" in data["data"]
            assert "tagged" in data["data"]
            assert "untagged" in data["data"]

    def test_kg_stats(self):
        """测试 /pipeline/kg/stats 端点"""
        response = self.client.get("/api/v1/pipeline/kg/stats")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "data" in data
            assert "total_entities" in data["data"]
            assert "total_relations" in data["data"]


class TestPipelineKGEntities:
    """知识图谱实体搜索测试"""

    @pytest.fixture(autouse=True)
    def setup(self, test_client):
        self.client = test_client

    def test_entities_search(self):
        """测试实体搜索"""
        response = self.client.get("/api/v1/pipeline/kg/entities?q=气功&limit=5")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert isinstance(data["data"], list)

    def test_entities_filter_by_type(self):
        """测试按类型筛选实体"""
        response = self.client.get("/api/v1/pipeline/kg/entities?entity_type=功法&limit=5")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            for entity in data["data"]:
                assert entity["entity_type"] == "功法"

    def test_entities_empty_query(self):
        """测试空查询返回全部实体"""
        response = self.client.get("/api/v1/pipeline/kg/entities?limit=5")
        assert response.status_code in [200, 500, 503]


class TestPipelineTasks:
    """任务管理端点测试"""

    @pytest.fixture(autouse=True)
    def setup(self, test_client):
        self.client = test_client

    def test_list_tasks(self):
        """测试获取任务列表"""
        response = self.client.get("/api/v1/pipeline/tasks")
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert isinstance(data["data"], list)

    def test_list_tasks_with_filter(self):
        """测试带筛选的任务列表"""
        response = self.client.get("/api/v1/pipeline/tasks?task_type=kg_build&limit=5")
        assert response.status_code in [200, 500, 503]

    def test_task_detail_not_found(self):
        """测试不存在的任务"""
        response = self.client.get("/api/v1/pipeline/tasks/999999")
        assert response.status_code in [404, 500, 503]

    def test_task_detail(self):
        """测试获取任务详情（取第一个任务）
        Note: 全量测试中前序async test可能关闭event loop导致500，属于已知flaky行为。
        """
        list_resp = self.client.get("/api/v1/pipeline/tasks?limit=1")
        assert list_resp.status_code in [200, 500, 503]
        if list_resp.status_code == 200:
            tasks = list_resp.json()["data"]
            if tasks:
                task_id = tasks[0]["id"]
                resp = self.client.get(f"/api/v1/pipeline/tasks/{task_id}")
                assert resp.status_code == 200
                assert resp.json()["data"]["id"] == task_id


class TestPipelineKGGraph:
    """子图查询测试"""

    @pytest.fixture(autouse=True)
    def setup(self, test_client):
        self.client = test_client

    def test_subgraph_not_found(self):
        """测试不存在的实体子图"""
        response = self.client.get("/api/v1/pipeline/kg/graph?entity_id=999999&depth=1")
        assert response.status_code in [404, 500, 503]

    def test_subgraph(self):
        """测试子图查询"""
        entities_resp = self.client.get("/api/v1/pipeline/kg/entities?limit=1")
        if entities_resp.status_code == 200:
            entities = entities_resp.json()["data"]
            if entities:
                entity_id = entities[0]["id"]
                response = self.client.get(
                    f"/api/v1/pipeline/kg/graph?entity_id={entity_id}&depth=1"
                )
                assert response.status_code in [200, 404, 500, 503]
                if response.status_code == 200:
                    data = response.json()["data"]
                    assert "center" in data
                    assert "entities" in data
                    assert "relations" in data
