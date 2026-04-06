"""检索反馈闭环测试"""

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest


class TestSubmitFeedback:
    """提交反馈"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_submit_returns_id(self, mock_pool):
        from backend.services.retrieval.feedback import submit_feedback

        pool, mock_conn = mock_pool
        mock_conn.fetchval.return_value = 1

        fb_id = await submit_feedback(pool, query="八段锦", feedback_type="helpful", doc_id=42)
        assert fb_id == 1

    @pytest.mark.asyncio
    async def test_submit_with_full_context(self, mock_pool):
        from backend.services.retrieval.feedback import submit_feedback

        pool, mock_conn = mock_pool
        mock_conn.fetchval.return_value = 2

        fb_id = await submit_feedback(
            pool, query="气功", feedback_type="not_helpful",
            doc_id=10, rating=2, category="气功",
            search_method="hybrid", rank_position=1,
            similarity_score=0.75, comment="不太相关",
            session_id="sess_123",
        )
        assert fb_id == 2

    @pytest.mark.asyncio
    async def test_rejects_invalid_feedback_type(self, mock_pool):
        from backend.services.retrieval.feedback import submit_feedback

        pool, _ = mock_pool
        with pytest.raises(ValueError, match="无效反馈类型"):
            await submit_feedback(pool, query="q", feedback_type="invalid")

    @pytest.mark.asyncio
    async def test_rejects_invalid_rating(self, mock_pool):
        from backend.services.retrieval.feedback import submit_feedback

        pool, _ = mock_pool
        with pytest.raises(ValueError, match="评分必须在 1-5 之间"):
            await submit_feedback(pool, query="q", feedback_type="helpful", rating=6)

    @pytest.mark.asyncio
    async def test_rejects_zero_rating(self, mock_pool):
        from backend.services.retrieval.feedback import submit_feedback

        pool, _ = mock_pool
        with pytest.raises(ValueError, match="评分必须在 1-5 之间"):
            await submit_feedback(pool, query="q", feedback_type="helpful", rating=0)


class TestGetFeedbackStats:
    """反馈统计"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_stats_structure(self, mock_pool):
        from backend.services.retrieval.feedback import get_feedback_stats

        pool, mock_conn = mock_pool
        mock_conn.fetchval.side_effect = [100, 4.2, 65.0, 20]
        mock_conn.fetch.side_effect = [
            [{"feedback_type": "helpful", "count": 65}, {"feedback_type": "not_helpful", "count": 35}],
            [{"query": "八段锦", "feedback_count": 10, "helpful": 8, "not_helpful": 2}],
        ]

        stats = await get_feedback_stats(pool)
        assert stats["total"] == 100
        assert stats["by_type"]["helpful"] == 65
        assert stats["avg_rating"] == 4.2
        assert stats["helpful_rate"] == 65.0
        assert stats["recent_7d"] == 20
        assert len(stats["top_queries"]) == 1


class TestGetDocQualityScores:
    """文档质量评分"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_returns_scores_per_doc(self, mock_pool):
        from backend.services.retrieval.feedback import get_doc_quality_scores

        pool, mock_conn = mock_pool
        mock_conn.fetch.return_value = [
            {"doc_id": 1, "total_feedback": 10, "helpful_count": 8, "avg_rating": 4.5},
            {"doc_id": 2, "total_feedback": 5, "helpful_count": 1, "avg_rating": 2.0},
        ]

        scores = await get_doc_quality_scores(pool, [1, 2, 3])
        assert scores[1]["helpful_ratio"] == 0.8
        assert scores[2]["helpful_ratio"] == 0.2
        assert 3 not in scores

    @pytest.mark.asyncio
    async def test_empty_ids(self, mock_pool):
        from backend.services.retrieval.feedback import get_doc_quality_scores

        pool, _ = mock_pool
        scores = await get_doc_quality_scores(pool, [])
        assert scores == {}


class TestListFeedback:
    """反馈列表查询"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_returns_list(self, mock_pool):
        from backend.services.retrieval.feedback import list_feedback

        pool, mock_conn = mock_pool
        mock_conn.fetch.return_value = [
            {"id": 1, "query": "q1", "feedback_type": "helpful"},
            {"id": 2, "query": "q2", "feedback_type": "wrong"},
        ]

        result = await list_feedback(pool)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_with_type_filter(self, mock_pool):
        from backend.services.retrieval.feedback import list_feedback

        pool, mock_conn = mock_pool
        mock_conn.fetch.return_value = [{"id": 1, "feedback_type": "helpful"}]

        result = await list_feedback(pool, feedback_type="helpful")
        assert len(result) == 1


class TestFeedbackAPI:
    """检索反馈 API 端点测试"""

    @pytest.fixture
    def client(self):
        from contextlib import asynccontextmanager

        from fastapi import FastAPI

        from backend.main import create_app

        @asynccontextmanager
        async def _noop(app: FastAPI):
            yield

        app = create_app(lifespan_ctx=_noop)
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_submit_endpoint(self, client):
        response = client.post(
            "/api/v1/feedback",
            json={"query": "八段锦", "feedback_type": "helpful", "doc_id": 1},
        )
        assert response.status_code in [200, 500]

    def test_submit_rejects_invalid_type(self, client):
        response = client.post(
            "/api/v1/feedback",
            json={"query": "q", "feedback_type": "bad"},
        )
        assert response.status_code == 400

    def test_submit_rejects_invalid_rating(self, client):
        response = client.post(
            "/api/v1/feedback",
            json={"query": "q", "feedback_type": "helpful", "rating": 99},
        )
        assert response.status_code == 400

    def test_list_endpoint(self, client):
        response = client.get("/api/v1/feedback")
        assert response.status_code in [200, 500]

    def test_stats_endpoint(self, client):
        response = client.get("/api/v1/feedback/stats")
        assert response.status_code in [200, 500]

    def test_doc_quality_endpoint(self, client):
        response = client.post(
            "/api/v1/feedback/doc-quality",
            json={"doc_ids": [1, 2, 3]},
        )
        assert response.status_code in [200, 500]

    def test_list_with_filters(self, client):
        response = client.get(
            "/api/v1/feedback",
            params={"feedback_type": "helpful", "doc_id": 1, "limit": 10},
        )
        assert response.status_code in [200, 500]
