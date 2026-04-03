"""
测试混合检索服务（Hybrid Retrieval Service）

文字处理工程流A-3的测试套件
"""

import pytest
import asyncio
from backend.services.hybrid_retrieval import (
    RetrievalMethod,
    RetrievalResult,
    ResultFusion,
    HybridRetrievalService
)


class TestResultFusion:
    """测试结果融合器"""

    def test_rrf_fusion(self):
        """测试RRF融合算法"""
        # 创建模拟的向量检索结果
        vector_results = [
            RetrievalResult(id=1, title="A", content="...", category=None, score=0.9, method=RetrievalMethod.VECTOR),
            RetrievalResult(id=2, title="B", content="...", category=None, score=0.8, method=RetrievalMethod.VECTOR),
            RetrievalResult(id=3, title="C", content="...", category=None, score=0.7, method=RetrievalMethod.VECTOR),
        ]

        # 创建模拟的全文检索结果（有些重叠，有些不重叠）
        fulltext_results = [
            RetrievalResult(id=2, title="B", content="...", category=None, score=0.9, method=RetrievalMethod.FULLTEXT),
            RetrievalResult(id=4, title="D", content="...", category=None, score=0.8, method=RetrievalMethod.FULLTEXT),
            RetrievalResult(id=5, title="E", content="...", category=None, score=0.7, method=RetrievalMethod.FULLTEXT),
        ]

        # 执行RRF融合
        fused = ResultFusion.rrf(vector_results, fulltext_results, k=60)

        # 验证结果
        assert len(fused) == 5  # 应该包含所有唯一文档

        # 文档2应该有更高的排名（同时出现在两个结果中）
        doc_2 = next(r for r in fused if r.id == 2)
        assert doc_2.score > 0.0

        # 验证排名已设置
        for i, result in enumerate(fused):
            assert result.rank == i + 1
            assert result.method == RetrievalMethod.HYBRID

    def test_weighted_fusion(self):
        """测试加权融合"""
        vector_results = [
            RetrievalResult(id=1, title="A", content="...", category=None, score=0.9, method=RetrievalMethod.VECTOR),
            RetrievalResult(id=2, title="B", content="...", category=None, score=0.8, method=RetrievalMethod.VECTOR),
        ]

        fulltext_results = [
            RetrievalResult(id=2, title="B", content="...", category=None, score=0.9, method=RetrievalMethod.FULLTEXT),
            RetrievalResult(id=3, title="C", content="...", category=None, score=0.7, method=RetrievalMethod.FULLTEXT),
        ]

        # 执行加权融合
        fused = ResultFusion.weighted(
            vector_results,
            fulltext_results,
            vector_weight=0.6,
            fulltext_weight=0.4
        )

        # 验证结果
        assert len(fused) == 3
        assert all(r.method == RetrievalMethod.HYBRID for r in fused)


class TestRetrievalResult:
    """测试检索结果"""

    def test_to_dict(self):
        """测试转换为字典"""
        result = RetrievalResult(
            id=1,
            title="测试标题",
            content="这是一段很长的内容，应该被截断显示。" * 10,
            category="test",
            score=0.9,
            method=RetrievalMethod.VECTOR,
            rank=1
        )

        result_dict = result.to_dict()

        # 验证内容被截断
        assert len(result_dict["content"]) <= 203  # 200 + "..."

        # 验证其他字段
        assert result_dict["id"] == 1
        assert result_dict["title"] == "测试标题"
        assert result_dict["score"] == 0.9
        assert result_dict["method"] == "vector"
        assert result_dict["rank"] == 1


# 集成测试（需要真实数据库）
@pytest.mark.integration
class TestHybridRetrievalIntegration:
    """集成测试"""

    @pytest.fixture
    async def db_pool(self):
        """创建测试数据库连接池"""
        # 这里应该创建测试数据库连接
        # 为了简化，暂时返回None
        return None

    @pytest.fixture
    def service(self, db_pool):
        """创建服务实例"""
        return HybridRetrievalService(
            db_pool=db_pool,
            enable_cache=True,
            cache_ttl=3600
        )

    def test_cache_operations(self, service):
        """测试缓存操作"""
        # 创建模拟结果
        results = [
            RetrievalResult(
                id=i,
                title=f"结果{i}",
                content=f"内容{i}",
                category=None,
                score=0.9 - i * 0.1,
                method=RetrievalMethod.VECTOR
            )
            for i in range(5)
        ]

        # 测试缓存保存
        service.cache.set(
            query="测试查询",
            method="vector",
            results=results,
            top_k=5
        )

        # 测试缓存获取
        cached = service.cache.get(
            query="测试查询",
            method="vector",
            top_k=5
        )

        assert cached is not None
        assert len(cached) == 5
        assert cached[0].title == "结果0"

    def test_clear_cache(self, service):
        """测试清空缓存"""
        results = [
            RetrievalResult(
                id=1,
                title="测试",
                content="内容",
                category=None,
                score=0.9,
                method=RetrievalMethod.VECTOR
            )
        ]

        # 保存到缓存
        service.cache.set(
            query="测试",
            method="vector",
            results=results
        )

        # 清空缓存
        service.clear_cache()

        # 验证缓存已清空
        cached = service.cache.get(
            query="测试",
            method="vector"
        )

        assert cached is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
