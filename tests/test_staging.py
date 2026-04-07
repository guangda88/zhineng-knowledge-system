"""知识临时区测试

测试暂存文档的 CRUD、审核流程和 API 端点。
"""

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

# ---------------------------------------------------------------------------
# Unit tests for staging service (mocked pool)
# ---------------------------------------------------------------------------


class TestCreateStagingDoc:
    """创建暂存文档"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_create_returns_id(self, mock_pool):
        from backend.services.staging import create_staging_doc

        pool, mock_conn = mock_pool
        mock_conn.fetchval.return_value = 1

        staging_id = await create_staging_doc(
            pool, title="测试", content="内容", category="气功", source="lingke"
        )
        assert staging_id == 1

    @pytest.mark.asyncio
    async def test_create_rejects_invalid_source(self, mock_pool):
        from backend.services.staging import create_staging_doc

        pool, _ = mock_pool
        with pytest.raises(ValueError, match="无效来源"):
            await create_staging_doc(pool, title="测试", content="内容", source="invalid_source")


class TestListStagingDocs:
    """查询暂存文档列表"""

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
        from backend.services.staging import list_staging_docs

        pool, mock_conn = mock_pool
        mock_conn.fetch.return_value = [
            {"id": 1, "title": "A", "status": "draft"},
            {"id": 2, "title": "B", "status": "submitted"},
        ]

        result = await list_staging_docs(pool)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_with_status_filter(self, mock_pool):
        from backend.services.staging import list_staging_docs

        pool, mock_conn = mock_pool
        mock_conn.fetch.return_value = [{"id": 1, "title": "A", "status": "draft"}]

        result = await list_staging_docs(pool, status="draft")
        assert len(result) == 1
        call_args = mock_conn.fetch.call_args
        assert "draft" in call_args[0]


class TestGetStagingDoc:
    """获取单个暂存文档"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_returns_dict(self, mock_pool):
        from backend.services.staging import get_staging_doc

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = {"id": 1, "title": "A", "content": "B"}

        result = await get_staging_doc(pool, 1)
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_pool):
        from backend.services.staging import get_staging_doc

        pool, mock_conn = mock_pool
        mock_conn.fetchrow.return_value = None

        result = await get_staging_doc(pool, 9999)
        assert result is None


class TestSubmitForReview:
    """提交审核"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_success(self, mock_pool):
        from backend.services.staging import submit_for_review

        pool, mock_conn = mock_pool
        mock_conn.execute.return_value = "UPDATE 1"

        ok = await submit_for_review(pool, 1)
        assert ok is True

    @pytest.mark.asyncio
    async def test_wrong_status(self, mock_pool):
        from backend.services.staging import submit_for_review

        pool, mock_conn = mock_pool
        mock_conn.execute.return_value = "UPDATE 0"

        ok = await submit_for_review(pool, 1)
        assert ok is False


class TestRejectStaging:
    """拒绝暂存文档"""

    @pytest.fixture
    async def mock_pool(self):
        pool = AsyncMock(spec=asyncpg.Pool)
        mock_conn = AsyncMock()
        acquire_ctx = MagicMock()
        acquire_ctx.__aenter__.return_value = mock_conn
        pool.acquire.return_value = acquire_ctx
        return pool, mock_conn

    @pytest.mark.asyncio
    async def test_success(self, mock_pool):
        from backend.services.staging import reject_staging

        pool, mock_conn = mock_pool
        mock_conn.execute.return_value = "UPDATE 1"

        ok = await reject_staging(pool, 1, reviewed_by="灵知", review_notes="质量不够")
        assert ok is True


class TestGetStagingStats:
    """暂存区统计"""

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
        from backend.services.staging import get_staging_stats

        pool, mock_conn = mock_pool
        mock_conn.fetchval.side_effect = [15, 3]
        mock_conn.fetch.side_effect = [
            [{"status": "draft", "count": 10}, {"status": "submitted", "count": 5}],
            [{"source": "lingke", "count": 8}, {"source": "manual", "count": 7}],
        ]

        stats = await get_staging_stats(pool)
        assert stats["total"] == 15
        assert stats["by_status"]["draft"] == 10
        assert stats["gap_linked"] == 3


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestStagingAPI:
    """知识临时区 API 端点测试"""

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

    def test_create_endpoint_exists(self, client):
        """POST /api/v1/staging 应返回 200 或 500"""
        response = client.post(
            "/api/v1/staging",
            json={"title": "测试", "content": "内容", "source": "lingke"},
        )
        assert response.status_code in [200, 500]

    def test_create_rejects_invalid_source(self, client):
        """无效 source 应返回 400"""
        response = client.post(
            "/api/v1/staging",
            json={"title": "测试", "content": "内容", "source": "bad_source"},
        )
        assert response.status_code == 400

    def test_list_endpoint_exists(self, client):
        """GET /api/v1/staging 应返回 200 或 500"""
        response = client.get("/api/v1/staging")
        assert response.status_code in [200, 500]

    def test_stats_endpoint_exists(self, client):
        """GET /api/v1/staging/stats 应返回 200 或 500"""
        response = client.get("/api/v1/staging/stats")
        assert response.status_code in [200, 500]

    def test_get_detail_endpoint(self, client):
        """GET /api/v1/staging/{id} 应返回 200/404/500"""
        response = client.get("/api/v1/staging/99999")
        assert response.status_code in [200, 404, 500]

    def test_submit_endpoint(self, client):
        """PATCH /api/v1/staging/{id}/submit 应返回 200/400/500"""
        response = client.patch("/api/v1/staging/99999/submit")
        assert response.status_code in [200, 400, 500]

    def test_approve_endpoint(self, client):
        """PATCH /api/v1/staging/{id}/approve 应返回 200/400/500"""
        response = client.patch(
            "/api/v1/staging/99999/approve",
            json={"reviewed_by": "灵知"},
        )
        assert response.status_code in [200, 400, 500]

    def test_reject_endpoint(self, client):
        """PATCH /api/v1/staging/{id}/reject 应返回 200/400/500"""
        response = client.patch(
            "/api/v1/staging/99999/reject",
            json={"review_notes": "不合格"},
        )
        assert response.status_code in [200, 400, 500]

    def test_list_with_filters(self, client):
        """带过滤参数的查询应被接受"""
        response = client.get(
            "/api/v1/staging",
            params={"status": "draft", "source": "lingke", "limit": 10},
        )
        assert response.status_code in [200, 500]
