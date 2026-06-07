"""
Reranker 模块测试
"""
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestCreateReranker:
    @pytest.fixture(autouse=True)
    def _mock_cross_encoder(self):
        with patch.dict(sys.modules, {"sentence_transformers": MagicMock()}):
            yield

    def test_create_reranker_default(self):
        from backend.services.retrieval.reranker import Reranker, create_reranker

        reranker = create_reranker()
        assert isinstance(reranker, Reranker)

    def test_create_reranker_custom_top_n(self):
        from backend.services.retrieval.reranker import create_reranker

        reranker = create_reranker(top_n=5)
        assert reranker.top_n == 5

    @patch("backend.services.retrieval.reranker.asyncio.Lock")
    def test_cpu_fallback_top_n(self, mock_lock):
        from backend.services.retrieval.reranker import create_reranker

        with patch("backend.services.retrieval.reranker._DEFAULT_TOP_N", 20), \
             patch("backend.services.retrieval.reranker._FALLBACK_TOP_N", 10):
            reranker = create_reranker(top_n=None)
            assert reranker.top_n in (10, 20)


class TestReranker:
    @pytest.fixture(autouse=True)
    def _mock_cross_encoder(self):
        with patch.dict(sys.modules, {"sentence_transformers": MagicMock()}):
            yield

    def test_init_defaults(self):
        from backend.services.retrieval.reranker import Reranker

        r = Reranker()
        assert r.top_n == 20
        assert r.max_length == 512

    def test_init_custom(self):
        from backend.services.retrieval.reranker import Reranker

        r = Reranker(top_n=5, max_length=256)
        assert r.top_n == 5
        assert r.max_length == 256

    @pytest.mark.asyncio
    async def test_rerank_empty_results(self):
        from backend.services.retrieval.reranker import Reranker

        r = Reranker()
        result = await r.rerank("test query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_single_result(self):
        from backend.services.retrieval.reranker import Reranker

        r = Reranker()
        results = [{"id": 1, "title": "test", "content": "content", "score": 0.9}]
        result = await r.rerank("test query", results)
        assert len(result) == 1
        assert result[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_rerank_with_model(self):
        from backend.services.retrieval.reranker import Reranker

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.8, 0.3, 0.95]

        r = Reranker(top_n=20)
        r._model = mock_model

        results = [
            {"id": 1, "title": "气功呼吸法", "content": "腹式呼吸是气功的基础", "score": 0.9},
            {"id": 2, "title": "中医理论", "content": "阴阳五行学说是中医的核心", "score": 0.85},
            {"id": 3, "title": "气功站桩", "content": "站桩是气功基本功", "score": 0.7},
        ]

        result = await r.rerank("气功呼吸要领", results, top_k=3)

        assert len(result) >= 3
        assert result[0]["id"] == 3
        assert result[0]["rerank_score"] == 0.95
        assert result[1]["rerank_score"] == 0.8
        assert result[2]["rerank_score"] == 0.3

        mock_model.predict.assert_called_once()
        call_args = mock_model.predict.call_args[0][0]
        assert len(call_args) == 3
        assert call_args[0][0] == "气功呼吸要领"

    @pytest.mark.asyncio
    async def test_rerank_truncates_long_content(self):
        from backend.services.retrieval.reranker import Reranker

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.5, 0.4]

        r = Reranker()
        r._model = mock_model

        long_content = "x" * 1000
        results = [
            {"id": 1, "title": "test", "content": long_content, "score": 0.9},
            {"id": 2, "title": "short", "content": "short", "score": 0.8},
        ]

        await r.rerank("query", results, top_k=2)

        call_args = mock_model.predict.call_args[0][0]
        doc_text = call_args[0][1]
        assert len(doc_text) <= 510

    @pytest.mark.asyncio
    async def test_rerank_top_n_limit(self):
        from backend.services.retrieval.reranker import Reranker

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1 * i for i in range(5)]

        r = Reranker(top_n=5)
        r._model = mock_model

        results = [{"id": i, "title": f"doc{i}", "content": f"content{i}", "score": 0.5} for i in range(20)]

        result = await r.rerank("query", results, top_k=3)

        assert mock_model.predict.call_args[0][0].__len__() == 5
        assert len(result) == 18

    @pytest.mark.asyncio
    async def test_rerank_model_failure_returns_original(self):
        from backend.services.retrieval.reranker import Reranker

        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("model error")

        r = Reranker()
        r._model = mock_model

        results = [
            {"id": 1, "title": "test", "content": "content", "score": 0.9},
            {"id": 2, "title": "test2", "content": "content2", "score": 0.8},
        ]

        result = await r.rerank("query", results, top_k=2)

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert "rerank_score" not in result[0]
