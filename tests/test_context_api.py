"""上下文管理 API 测试"""

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client():
    """测试客户端"""
    app = create_app()
    return TestClient(app)


class TestContextHealth:
    """上下文健康检查测试"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/v1/context/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "session_id" in data
        assert "lingflow_available" in data
        assert "storage_dir" in data


class TestTokenEstimation:
    """Token 估算 API 测试"""

    def test_estimate_tokens_short(self, client):
        """测试短文本估算"""
        response = client.post(
            "/api/v1/context/estimate",
            json={"text": "Hello, world!", "model": "claude-opus-4"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["token_count"] > 0
        assert data["model"] == "claude-opus-4"
        assert "encoding" in data

    def test_estimate_tokens_long(self, client):
        """测试长文本估算"""
        long_text = "This is a test message. " * 100
        response = client.post(
            "/api/v1/context/estimate",
            json={"text": long_text}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["token_count"] > 100

    def test_estimate_tokens_empty(self, client):
        """测试空文本"""
        response = client.post(
            "/api/v1/context/estimate",
            json={"text": ""}
        )

        # 应该返回 422 验证错误
        assert response.status_code == 422

    def test_estimate_tokens_default_model(self, client):
        """测试默认模型"""
        response = client.post(
            "/api/v1/context/estimate",
            json={"text": "test message"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "claude-opus-4"


class TestMessageScoring:
    """消息评分 API 测试"""

    def test_score_messages(self, client):
        """测试消息评分"""
        messages = [
            {"role": "user", "content": "fix the critical bug"},
            {"role": "assistant", "content": "I'll help you fix that bug"}
        ]

        response = client.post(
            "/api/v1/context/messages/score",
            json={"messages": messages}
        )

        assert response.status_code == 200
        data = response.json()
        assert "scores" in data
        assert data["total_messages"] == 2
        assert "average_importance" in data
        assert len(data["scores"]) == 2

    def test_score_messages_empty(self, client):
        """测试空消息列表"""
        response = client.post(
            "/api/v1/context/messages/score",
            json={"messages": []}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_messages"] == 0
        assert data["scores"] == []


class TestMessageRecording:
    """消息记录 API 测试"""

    def test_record_message(self, client):
        """测试记录消息"""
        response = client.post(
            "/api/v1/context/messages/record",
            json={
                "role": "user",
                "content": "test message",
                "is_important": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "current_status" in data
        assert data["current_status"]["message_count"] > 0

    def test_record_important_message(self, client):
        """测试记录重要消息"""
        response = client.post(
            "/api/v1/context/messages/record",
            json={
                "role": "user",
                "content": "fix critical bug",
                "is_important": True
            }
        )

        assert response.status_code == 200


class TestTaskManagement:
    """任务管理 API 测试"""

    def test_add_pending_task(self, client):
        """测试添加待完成任务"""
        response = client.post(
            "/api/v1/context/tasks",
            json={"task": "Implement new feature", "completed": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task"] == "Implement new feature"
        assert data["completed"] is False
        assert data["total_pending"] > 0

    def test_add_completed_task(self, client):
        """测试添加已完成任务"""
        response = client.post(
            "/api/v1/context/tasks",
            json={"task": "Fixed bug", "completed": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is True

    def test_complete_task(self, client):
        """测试完成任务"""
        # 先添加任务
        client.post(
            "/api/v1/context/tasks",
            json={"task": "Test completion", "completed": False}
        )

        # 完成任务
        response = client.put("/api/v1/context/tasks/Test%20completion")

        assert response.status_code == 200
        data = response.json()
        assert data["task"] == "Test completion"


class TestDecisionRecording:
    """决策记录 API 测试"""

    def test_add_decision(self, client):
        """测试添加决策"""
        response = client.post(
            "/api/v1/context/decisions",
            json={"decision": "Use PostgreSQL for primary storage"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "Use PostgreSQL for primary storage"
        assert data["total_decisions"] > 0


class TestContextStatus:
    """上下文状态 API 测试"""

    def test_get_status(self, client):
        """测试获取状态"""
        response = client.get("/api/v1/context/status")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "message_count" in data
        assert "estimated_tokens" in data
        assert "token_limit" in data
        assert "token_usage_ratio" in data
        assert "health_status" in data
        assert data["health_status"] in ["healthy", "warning", "critical"]


class TestContextSnapshot:
    """上下文快照 API 测试"""

    def test_get_snapshot(self, client):
        """测试获取快照"""
        response = client.get("/api/v1/context/snapshot")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "timestamp" in data
        assert "tasks_completed" in data
        assert "tasks_pending" in data
        assert "key_decisions" in data
        assert "important_files" in data


class TestContextCompression:
    """上下文压缩 API 测试"""

    def test_compress_context(self, client):
        """测试压缩上下文"""
        response = client.post("/api/v1/context/compress", json={})

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "session_id" in data
        assert "timestamp" in data
        assert "上下文摘要" in data["summary"]


class TestRecovery:
    """恢复 API 测试"""

    def test_get_recovery_summary(self, client):
        """测试获取恢复摘要"""
        response = client.get("/api/v1/context/recovery")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "recovery_summary" in data


class TestContextReset:
    """上下文重置 API 测试"""

    def test_reset_context(self, client):
        """测试重置上下文"""
        # 先添加一些数据
        client.post(
            "/api/v1/context/tasks",
            json={"task": "Test task", "completed": False}
        )

        # 获取旧 session ID
        status_before = client.get("/api/v1/context/status").json()
        old_session_id = status_before["session_id"]

        # 重置
        response = client.post("/api/v1/context/reset")

        assert response.status_code == 200
        data = response.json()
        assert "new_session_id" in data
        assert data["old_session_id"] == old_session_id
        assert data["new_session_id"] != old_session_id
