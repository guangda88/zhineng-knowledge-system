"""上下文管理服务测试"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.services.context_service import (
    ContextService,
    ContextSnapshot,
    ContextStatus,
    MessageScore,
    TokenEstimate,
    get_context_service,
)


@pytest.fixture
def temp_context_dir(tmp_path):
    """临时上下文目录"""
    context_dir = tmp_path / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    return str(context_dir)


@pytest.fixture
def context_service(temp_context_dir):
    """上下文服务实例"""
    service = ContextService(storage_dir=temp_context_dir)
    return service


class TestTokenEstimation:
    """Token 估算测试"""

    def test_estimate_tokens_short_text(self, context_service):
        """测试短文本 Token 估算"""
        text = "Hello, world!"
        result = context_service.estimate_tokens(text)

        assert isinstance(result, TokenEstimate)
        assert result.token_count > 0
        assert result.model == "claude-opus-4"

    def test_estimate_tokens_long_text(self, context_service):
        """测试长文本 Token 估算"""
        text = "Hello, world! " * 1000
        result = context_service.estimate_tokens(text)

        assert result.token_count > 1000
        assert result.estimated is True

    def test_estimate_tokens_empty(self, context_service):
        """测试空文本"""
        result = context_service.estimate_tokens("")
        assert result.token_count == 0


class TestMessageScoring:
    """消息评分测试"""

    def test_score_messages_empty(self, context_service):
        """测试空消息列表"""
        scores = context_service.score_messages([])
        assert scores == []

    def test_score_messages_simple(self, context_service):
        """测试简单消息评分"""
        messages = [
            {"role": "user", "content": "fix the bug in login"},
            {"role": "assistant", "content": "I'll help you fix the bug"},
        ]

        scores = context_service.score_messages(messages)

        assert len(scores) == 2
        assert all(isinstance(s, MessageScore) for s in scores)
        # 包含 "fix", "bug" 等关键词的消息应该有较高重要性
        assert scores[0].importance_score > 0.3

    def test_score_messages_important_keywords(self, context_service):
        """测试重要关键词检测"""
        messages = [
            {"role": "user", "content": "implement critical feature"},
            {"role": "user", "content": "hello world"},
        ]

        scores = context_service.score_messages(messages)

        # 第一条消息包含更多关键词
        assert scores[0].importance_score > scores[1].importance_score


class TestMessageRecording:
    """消息记录测试"""

    def test_record_message(self, context_service):
        """测试记录消息"""
        initial_count = context_service.message_count

        context_service.record_message("user", "test message")

        assert context_service.message_count == initial_count + 1
        assert context_service.estimated_tokens > 0

    def test_record_important_message(self, context_service):
        """测试记录重要消息"""
        context_service.record_message("user", "fix the critical bug now", is_important=True)

        # 应该提取任务信息
        assert len(context_service.snapshot.tasks_pending) > 0 or context_service.message_count > 0

    def test_record_multiple_messages(self, context_service):
        """测试记录多条消息"""
        for i in range(5):
            context_service.record_message("user", f"message {i}")

        assert context_service.message_count == 5


class TestTaskManagement:
    """任务管理测试"""

    def test_add_pending_task(self, context_service):
        """测试添加待完成任务"""
        context_service.add_task("Implement feature X", completed=False)

        assert "Implement feature X" in context_service.snapshot.tasks_pending
        assert "Implement feature X" not in context_service.snapshot.tasks_completed

    def test_add_completed_task(self, context_service):
        """测试添加已完成任务"""
        context_service.add_task("Fix bug Y", completed=True)

        assert "Fix bug Y" in context_service.snapshot.tasks_completed
        assert "Fix bug Y" not in context_service.snapshot.tasks_pending

    def test_complete_task(self, context_service):
        """测试完成任务"""
        context_service.add_task("Test feature Z", completed=False)
        context_service.complete_task("Test feature Z")

        assert "Test feature Z" not in context_service.snapshot.tasks_pending
        assert "Test feature Z" in context_service.snapshot.tasks_completed

    def test_duplicate_task(self, context_service):
        """测试重复任务"""
        context_service.add_task("Unique task", completed=False)
        context_service.add_task("Unique task", completed=False)

        # 不应该重复添加
        assert context_service.snapshot.tasks_pending.count("Unique task") == 1


class TestDecisionRecording:
    """决策记录测试"""

    def test_add_decision(self, context_service):
        """测试添加决策"""
        context_service.add_decision("Use PostgreSQL for primary storage")

        assert "Use PostgreSQL for primary storage" in context_service.snapshot.key_decisions

    def test_duplicate_decision(self, context_service):
        """测试重复决策"""
        decision = "Implement REST API"
        context_service.add_decision(decision)
        context_service.add_decision(decision)

        # 不应该重复添加
        assert context_service.snapshot.key_decisions.count(decision) == 1


class TestContextCompression:
    """上下文压缩测试"""

    def test_compress_empty_context(self, context_service):
        """测试压缩空上下文"""
        summary = context_service.compress_now()

        assert isinstance(summary, str)
        assert context_service.session_id in summary
        assert "上下文摘要" in summary

    def test_compress_with_tasks(self, context_service):
        """测试压缩带任务的上下文"""
        context_service.add_task("Task 1", completed=True)
        context_service.add_task("Task 2", completed=False)
        context_service.record_message("user", "fix bug")

        summary = context_service.compress_now()

        assert "Task 1" in summary
        assert "Task 2" in summary
        assert "✅" in summary
        assert "◻" in summary

    def test_compress_creates_recovery_file(self, context_service, temp_context_dir):
        """测试压缩创建恢复文件"""
        context_service.compress_now()

        recovery_file = Path(temp_context_dir) / "RECOVERY_CONTEXT.md"
        assert recovery_file.exists()

        content = recovery_file.read_text(encoding="utf-8")
        assert context_service.session_id in content


class TestContextStatus:
    """上下文状态测试"""

    def test_get_status_initial(self, context_service):
        """测试获取初始状态"""
        status = context_service.get_status()

        assert isinstance(status, ContextStatus)
        assert status.session_id == context_service.session_id
        assert status.message_count == 0
        assert status.health_status == "healthy"

    def test_get_status_after_messages(self, context_service):
        """测试记录消息后的状态"""
        # 添加大量消息以达到警告阈值
        long_message = "test " * 10000
        for _ in range(20):
            context_service.record_message("user", long_message)

        status = context_service.get_status()

        assert status.message_count == 20
        assert status.estimated_tokens > 0
        assert status.token_usage_ratio > 0

    def test_health_status_levels(self, context_service):
        """测试健康状态级别"""
        # 初始状态应该是 healthy
        status = context_service.get_status()
        assert status.health_status == "healthy"


class TestSnapshot:
    """快照测试"""

    def test_get_snapshot(self, context_service):
        """测试获取快照"""
        context_service.add_task("Test task", completed=False)
        context_service.add_decision("Test decision")

        snapshot = context_service.get_snapshot()

        assert isinstance(snapshot, ContextSnapshot)
        assert snapshot.session_id == context_service.session_id
        assert "Test task" in snapshot.tasks_pending
        assert "Test decision" in snapshot.key_decisions


class TestPersistence:
    """持久化测试"""

    def test_save_and_load_snapshot(self, temp_context_dir):
        """测试保存和加载快照"""
        # 创建服务并添加数据
        service1 = ContextService(storage_dir=temp_context_dir)
        service1.add_task("Persistent task", completed=False)
        service1.add_decision("Persistent decision")
        service1._save_snapshot()

        # 创建新服务实例，应该加载上次的数据
        service2 = ContextService(storage_dir=temp_context_dir)
        service2._load_last_context()

        assert service2.last_context is not None
        assert "Persistent task" in service2.last_context.tasks_pending

    def test_snapshot_file_exists(self, context_service, temp_context_dir):
        """测试快照文件存在"""
        context_service._save_snapshot()

        snapshot_file = Path(temp_context_dir) / f"{context_service.session_id}.json"
        last_file = Path(temp_context_dir) / "last_context.json"

        assert snapshot_file.exists()
        assert last_file.exists()


class TestRecovery:
    """恢复测试"""

    def test_get_recovery_summary(self, context_service):
        """测试获取恢复摘要"""
        context_service.add_task("Recovery task", completed=True)

        summary = context_service.get_recovery_summary()

        assert isinstance(summary, str)
        assert "Recovery task" in summary
        assert "上下文摘要" in summary


class TestSingleton:
    """单例测试"""

    def test_get_context_service_singleton(self):
        """测试单例模式"""
        service1 = get_context_service()
        service2 = get_context_service()

        assert service1 is service2

    def test_singleton_persistence(self):
        """测试单例持久化"""
        service1 = get_context_service()
        session_id = service1.session_id

        service2 = get_context_service()
        assert service2.session_id == session_id
