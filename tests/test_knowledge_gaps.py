"""知识缺口感知测试

测试缺口记录、聚合、查询和API端点。
"""

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest


# ---------------------------------------------------------------------------
# Unit tests for gap_tracker service (mocked pool)
# ---------------------------------------------------------------------------


class TestRecordGap:
    """缺口记录核心逻辑测试"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_no_gap_when_results_good(self, mock_pool):
        """高置信度结果不应记录缺口"""
        from backend.services.retrieval.gap_tracker import record_gap

        pool, _ = mock_pool
        result = await record_gap(
            pool, query="八段锦", category="气功", result_count=5, best_score=0.85
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_gap_created_zero_results(self, mock_pool):
        """零结果应创建新缺口"""
        from backend.services.retrieval.gap_tracker import record_gap

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = None  # 无已有记录
        mock_conn.fetchval.return_value = 42  # 新建返回 ID

        result = await record_gap(
            pool, query="不存在的功法", category="气功", result_count=0, best_score=None
        )
        assert result == 42
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_gap_created_low_score(self, mock_pool):
        """低分结果应创建缺口"""
        from backend.services.retrieval.gap_tracker import record_gap

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = None
        mock_conn.fetchval.return_value = 99

        result = await record_gap(
            pool, query="模糊查询", category=None, result_count=3, best_score=0.15
        )
        assert result == 99

    @pytest.mark.asyncio
    async def test_gap_aggregated_existing(self, mock_pool):
        """相似查询应聚合到已有缺口（hit_count+1）"""
        from backend.services.retrieval.gap_tracker import record_gap

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = {"id": 7, "hit_count": 3}
        mock_conn.execute.return_value = "UPDATE 1"

        result = await record_gap(
            pool, query="重复的查询", category="气功", result_count=0, best_score=None
        )
        assert result == 7
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_gap_threshold_boundary(self, mock_pool):
        """best_score 恰好等于阈值 0.3 不应记录"""
        from backend.services.retrieval.gap_tracker import record_gap

        pool, _ = mock_pool
        result = await record_gap(
            pool, query="边界测试", category=None, result_count=1, best_score=0.3
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_gap_just_below_threshold(self, mock_pool):
        """best_score 略低于阈值应记录缺口"""
        from backend.services.retrieval.gap_tracker import record_gap

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = None
        mock_conn.fetchval.return_value = 100

        result = await record_gap(
            pool, query="接近边界", category=None, result_count=1, best_score=0.299
        )
        assert result == 100


class TestRecordSearchOutcome:
    """record_search_outcome 便捷包装测试"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_empty_results_creates_gap(self, mock_pool):
        """空结果列表应记录缺口"""
        from backend.services.retrieval.gap_tracker import record_search_outcome

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = None
        mock_conn.fetchval.return_value = 1

        result = await record_search_outcome(pool, query="无结果", results=[])
        assert result == 1

    @pytest.mark.asyncio
    async def test_good_results_no_gap(self, mock_pool):
        """高相似度结果不应记录缺口"""
        from backend.services.retrieval.gap_tracker import record_search_outcome

        pool, _ = mock_pool
        results = [{"id": 1, "similarity": 0.9, "title": "A"}]
        result = await record_search_outcome(pool, query="有结果", results=results)
        assert result is None

    @pytest.mark.asyncio
    async def test_extracts_best_score_from_similarity(self, mock_pool):
        """应从 similarity 字段提取最高分"""
        from backend.services.retrieval.gap_tracker import record_search_outcome

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = None
        mock_conn.fetchval.return_value = 2

        results = [
            {"id": 1, "similarity": 0.1},
            {"id": 2, "similarity": 0.2},
        ]
        result = await record_search_outcome(pool, query="低分", results=results)
        assert result == 2

    @pytest.mark.asyncio
    async def test_extracts_best_score_from_score_field(self, mock_pool):
        """应从 score 字段提取最高分"""
        from backend.services.retrieval.gap_tracker import record_search_outcome

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = None
        mock_conn.fetchval.return_value = 3

        results = [{"id": 1, "score": 0.1}]
        result = await record_search_outcome(pool, query="低分", results=results)
        assert result == 3


class TestGetGaps:
    """get_gaps 查询测试"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self, mock_pool):
        from backend.services.retrieval.gap_tracker import get_gaps

        pool, mock_conn = mock_pool
        mock_conn.fetch.return_value = [
            {"id": 1, "query": "q1", "hit_count": 3},
            {"id": 2, "query": "q2", "hit_count": 1},
        ]

        result = await get_gaps(pool)
        assert len(result) == 2
        assert result[0]["query"] == "q1"


class TestGetGapsStats:
    """get_gaps_stats 统计测试"""

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
        from backend.services.retrieval.gap_tracker import get_gaps_stats

        pool, mock_conn = mock_pool
        mock_conn.fetchval.side_effect = [10, 3]
        mock_conn.fetch.side_effect = [
            [{"status": "open", "count": 7}, {"status": "resolved", "count": 3}],
            [{"query": "热门缺口", "category": "气功", "hit_count": 5, "best_score": 0.1, "last_seen": None}],
        ]

        stats = await get_gaps_stats(pool)
        assert stats["total"] == 10
        assert stats["by_status"]["open"] == 7
        assert len(stats["top_unresolved"]) == 1
        assert stats["recent_7d"] == 3


class TestUpdateGapStatus:
    """update_gap_status 测试"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_successful_update(self, mock_pool):
        from backend.services.retrieval.gap_tracker import update_gap_status

        pool, mock_conn = mock_pool
        mock_conn.execute.return_value = "UPDATE 1"

        ok = await update_gap_status(pool, gap_id=1, status="resolved", resolved_by=42)
        assert ok is True

    @pytest.mark.asyncio
    async def test_not_found(self, mock_pool):
        from backend.services.retrieval.gap_tracker import update_gap_status

        pool, mock_conn = mock_pool
        mock_conn.execute.return_value = "UPDATE 0"

        ok = await update_gap_status(pool, gap_id=9999, status="resolved")
        assert ok is False


# ---------------------------------------------------------------------------
# API endpoint tests (using TestClient)
# ---------------------------------------------------------------------------


class TestKnowledgeGapsAPI:
    """知识缺口 API 端点测试"""

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

    def test_list_gaps_endpoint_exists(self, client):
        """GET /api/v1/knowledge-gaps 应返回 200 或 500（无 DB）"""
        response = client.get("/api/v1/knowledge-gaps")
        assert response.status_code in [200, 500]

    def test_stats_endpoint_exists(self, client):
        """GET /api/v1/knowledge-gaps/stats 应返回 200 或 500"""
        response = client.get("/api/v1/knowledge-gaps/stats")
        assert response.status_code in [200, 500]

    def test_patch_endpoint_exists(self, client):
        """PATCH /api/v1/knowledge-gaps/{id} 应返回 200/404/500"""
        response = client.patch(
            "/api/v1/knowledge-gaps/99999",
            json={"status": "resolved"},
        )
        assert response.status_code in [200, 404, 500]

    def test_patch_rejects_invalid_status(self, client):
        """无效状态应被 Pydantic 拒绝"""
        response = client.patch(
            "/api/v1/knowledge-gaps/1",
            json={"status": "invalid"},
        )
        assert response.status_code == 422

    def test_list_gaps_with_filters(self, client):
        """带过滤参数的查询应被接受"""
        response = client.get(
            "/api/v1/knowledge-gaps",
            params={"status": "open", "category": "气功", "min_hits": 2, "limit": 10},
        )
        assert response.status_code in [200, 500]
