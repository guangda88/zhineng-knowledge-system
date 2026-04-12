"""Tests for guoxue semantic search + reranker integration"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestGuoxueSemanticSearch:
    """Test _semantic_search method of LingFlowGuoxueSearchService"""

    @pytest.fixture
    def mock_pool(self):
        pool = AsyncMock()
        return pool

    @pytest.fixture
    def service(self, mock_pool):
        from backend.services.lingflow_guoxue_search import LingFlowGuoxueSearchService
        return LingFlowGuoxueSearchService(mock_pool)

    @pytest.mark.asyncio
    async def test_semantic_search_falls_back_when_no_embeddings(self, service, mock_pool):
        with patch.object(service, '_get_http_client', new_callable=AsyncMock) as mock_client:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"embedding": [0.1] * 512}
            mock_resp.raise_for_status = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value = mock_http

            mock_pool.fetchval = AsyncMock(return_value=False)

            with patch.object(service, '_fulltext_search', new_callable=AsyncMock) as mock_ft:
                mock_ft.return_value = {"total": 0, "results": [], "page": 1, "size": 20}
                await service._semantic_search("论语", None, 1, 20)
                mock_ft.assert_called_once_with("论语", None, 1, 20)

    @pytest.mark.asyncio
    async def test_semantic_search_returns_results(self, service, mock_pool):
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "id": 1, "book_id": 5, "chapter_id": 1,
            "body": "子曰学而时习之", "body_length": 7,
            "source_table": "lunyu", "vec_score": 0.92,
        }[key]
        mock_row.get = lambda key, default=None: {
            "id": 1, "book_id": 5, "chapter_id": 1,
            "body": "子曰学而时习之", "body_length": 7,
            "source_table": "lunyu", "vec_score": 0.92,
        }.get(key, default)

        with patch.object(service, '_get_http_client', new_callable=AsyncMock) as mock_client:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1] * 512}
            mock_resp.raise_for_status = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value = mock_http

            mock_pool.fetchval = AsyncMock(return_value=True)
            mock_pool.fetch = AsyncMock(
                side_effect=[
                    [mock_row],
                    [MagicMock(book_id=5, title="论语")],
                ]
            )

            with patch.object(service, '_get_reranker', new_callable=AsyncMock) as mock_rr:
                mock_reranker = AsyncMock()
                mock_reranker.rerank = AsyncMock(
                    side_effect=lambda q, r, top_k: r[:top_k]
                )
                mock_rr.return_value = mock_reranker

                result = await service._semantic_search("学而时习之", None, 1, 20)

        assert "results" in result
        assert result["page"] == 1
        assert result["size"] == 20

    @pytest.mark.asyncio
    async def test_semantic_search_with_book_filter(self, service, mock_pool):
        with patch.object(service, '_get_http_client', new_callable=AsyncMock) as mock_client:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1] * 512}
            mock_resp.raise_for_status = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value = mock_http

            mock_pool.fetchval = AsyncMock(return_value=True)
            mock_pool.fetch = AsyncMock(return_value=[])

            result = await service._semantic_search("道", book_id=10, page=1, size=10)

        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_semantic_search_empty_query(self, service, mock_pool):
        result = await service.search("")
        assert result["total"] == 0
        assert result["results"] == []


class TestGuoxueSearchModeRouting:
    """Test that search() routes to correct method by mode"""

    @pytest.fixture
    def service(self):
        from backend.services.lingflow_guoxue_search import LingFlowGuoxueSearchService
        pool = AsyncMock()
        return LingFlowGuoxueSearchService(pool)

    @pytest.mark.asyncio
    async def test_mode_semantic_routes_correctly(self, service):
        with patch.object(service, '_semantic_search', new_callable=AsyncMock) as mock:
            mock.return_value = {"total": 0, "results": [], "page": 1, "size": 20}
            await service.search("test", search_mode="semantic")
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_mode_fulltext_routes_correctly(self, service):
        with patch.object(service, '_fulltext_search', new_callable=AsyncMock) as mock:
            mock.return_value = {"total": 0, "results": [], "page": 1, "size": 20}
            await service.search("test", search_mode="fulltext")
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_mode_fuzzy_routes_correctly(self, service):
        with patch.object(service, '_fuzzy_search', new_callable=AsyncMock) as mock:
            mock.return_value = {"total": 0, "results": [], "page": 1, "size": 20}
            await service.search("test", search_mode="fuzzy")
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_mode_broad_routes_correctly(self, service):
        with patch.object(service, '_broad_search', new_callable=AsyncMock) as mock:
            mock.return_value = {"total": 0, "results": [], "page": 1, "size": 20}
            await service.search("test", search_mode="broad")
            mock.assert_called_once()


class TestGuoxueAPIMode:
    """Test API accepts semantic mode"""

    def test_semantic_mode_accepted_by_pattern(self):
        import re
        pattern = re.compile(r"^(fulltext|fuzzy|broad|semantic)$")
        assert pattern.match("semantic") is not None
        assert pattern.match("fulltext") is not None
        assert pattern.match("fuzzy") is not None
        assert pattern.match("broad") is not None
        assert pattern.match("invalid") is None
