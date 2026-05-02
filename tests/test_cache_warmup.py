"""
测试 CacheWarmer 模块
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.cache.warmup import CacheWarmer


@pytest.fixture
def mock_pool():
    """创建模拟的数据库连接池"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def mock_retriever():
    """创建模拟的混合检索器"""
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[
        {"id": 1, "title": "测试文档", "content": "测试内容"}
    ])
    return retriever


@pytest.fixture
def cache_warmer(mock_pool, mock_retriever):
    """创建 CacheWarmer 实例"""
    return CacheWarmer(mock_pool, mock_retriever)


class TestCacheWarmer:
    """测试 CacheWarmer 类"""

    def test_init(self, mock_pool, mock_retriever):
        """测试初始化"""
        warmer = CacheWarmer(mock_pool, mock_retriever)

        assert warmer.db_pool == mock_pool
        assert warmer.retriever == mock_retriever

    async def test_warmup_popular_queries(self, cache_warmer, mock_pool, mock_retriever):
        """测试预热热门查询"""
        # 模拟返回热门查询
        mock_pool.fetch.return_value = [
            {"query": "气功", "frequency": 100},
            {"query": "中医", "frequency": 50}
        ]

        stats = await cache_warmer.warmup_popular_queries(limit=2)

        assert stats["total_queries"] == 2
        assert stats["successful"] == 2
        assert stats["failed"] == 0
        assert len(stats["queries"]) == 2

        # 验证调用了搜索
        assert mock_retriever.search.call_count == 2

    async def test_warmup_categories(self, cache_warmer, mock_pool):
        """测试预热分类数据"""
        # 模拟返回分类
        mock_pool.fetch.return_value = [
            {"category": "气功"},
            {"category": "中医"}
        ]

        stats = await cache_warmer.warmup_categories()

        assert stats["total"] == 2
        assert len(stats["categories"]) == 2
        assert "气功" in stats["categories"]

    async def test_warmup_stats(self, cache_warmer, mock_pool):
        """测试预热统计数据"""
        # 模拟统计查询
        mock_pool.fetchval.side_effect = [
            1000,  # total_documents
            800,   # vector_enabled
            9      # categories
        ]

        stats = await cache_warmer.warmup_stats()

        assert stats["total_documents"] == 1000
        assert stats["vector_enabled"] == 800
        assert stats["categories"] == 9

    async def test_warmup_recent_documents(self, cache_warmer, mock_pool):
        """测试预热最近文档"""
        # 模拟返回最近文档
        mock_pool.fetch.return_value = [
            {"doc_id": 1},
            {"doc_id": 2}
        ]
        mock_pool.fetchrow.return_value = {
            "id": 1,
            "title": "测试",
            "content": "内容",
            "category": "气功"
        }

        stats = await cache_warmer.warmup_recent_documents(limit=2)

        assert stats["total"] == 2
        assert stats["successful"] == 2

    async def test_warmup_all(self, cache_warmer, mock_pool, mock_retriever):
        """测试执行所有预热任务"""
        # 模拟各种查询
        mock_pool.fetch.side_effect = [
            [],  # popular queries
            [{"category": "气功"}],  # categories
            [{"doc_id": 1}],  # recent documents
        ]
        mock_pool.fetchval.side_effect = [
            1000,  # total_documents
            800,   # vector_enabled
            9      # categories
        ]
        mock_pool.fetchrow.return_value = {
            "id": 1,
            "title": "测试",
            "content": "内容",
            "category": "气功"
        }

        results = await cache_warmer.warmup_all()

        assert "stats" in results
        assert "categories" in results
        assert "popular_queries" in results
        assert "recent_documents" in results

    async def test_warmup_popular_queries_with_errors(self, cache_warmer, mock_pool, mock_retriever):
        """测试预热热门查询时处理错误"""
        # 模拟返回热门查询
        mock_pool.fetch.return_value = [
            {"query": "气功", "frequency": 100}
        ]

        # 模拟搜索失败
        mock_retriever.search.side_effect = Exception("Search error")

        stats = await cache_warmer.warmup_popular_queries(limit=1)

        assert stats["total_queries"] == 1
        assert stats["successful"] == 0
        assert stats["failed"] == 1

    def test_get_default_popular_queries(self, cache_warmer):
        """测试获取默认热门查询"""
        queries = cache_warmer._get_default_popular_queries(5)

        assert len(queries) == 5
        assert all("query" in q and "frequency" in q for q in queries)

    async def test_warmup_popular_queries_no_logs(self, cache_warmer, mock_pool):
        """测试当没有搜索日志时使用默认查询"""
        # 模拟抛出异常（表不存在）
        mock_pool.fetch.side_effect = Exception("Table not found")

        stats = await cache_warmer.warmup_popular_queries(limit=5)

        # 应该使用默认查询
        assert stats["total_queries"] > 0
