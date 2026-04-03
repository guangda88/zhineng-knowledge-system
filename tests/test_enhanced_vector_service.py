"""
测试增强向量嵌入服务（Enhanced Vector Embedding Service）

文字处理工程流A-2的测试套件
"""

import asyncio

import numpy as np
import pytest

from backend.services.enhanced_vector_service import (
    BatchEmbeddingResult,
    EmbeddingProvider,
    EmbeddingResult,
    EnhancedEmbeddingService,
    TextVectorizer,
    VectorQualityAssessor,
)


class TestVectorQualityAssessor:
    """测试向量质量评估器"""

    def test_assess_normalized_vector(self):
        """测试评估归一化向量"""
        vector = [0.5, 0.5, 0.5, 0.5]
        score = VectorQualityAssessor.assess(vector)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # 应该有不错的分数

    def test_assess_zero_vector(self):
        """测试评估零向量"""
        vector = [0.0, 0.0, 0.0, 0.0]
        score = VectorQualityAssessor.assess(vector)
        # 零向量方差低，分数应该较低
        assert 0.0 <= score <= 1.0

    def test_assess_vector_with_nan(self):
        """测试评估包含NaN的向量"""
        vector = [0.5, float("nan"), 0.5, 0.5]
        score = VectorQualityAssessor.assess(vector)
        assert score == 0.0  # NaN应该得0分

    def test_assess_batch(self):
        """测试批量评估"""
        vectors = [
            [0.5, 0.5, 0.5, 0.5],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0],
        ]

        avg_score, scores = VectorQualityAssessor.assess_batch(vectors)

        assert len(scores) == 3
        assert 0.0 <= avg_score <= 1.0
        assert all(0.0 <= s <= 1.0 for s in scores)


class TestEnhancedEmbeddingService:
    """测试增强嵌入服务"""

    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return EnhancedEmbeddingService(
            preferred_provider=EmbeddingProvider.LOCAL, auto_fallback=True
        )

    def test_embed_single_text(self, service):
        """测试嵌入单个文本"""
        text = "混元灵通是智能气功的核心理论"

        result = asyncio.run(service.embed(text))

        assert isinstance(result, EmbeddingResult)
        assert len(result.vector) > 0
        assert result.provider == EmbeddingProvider.LOCAL
        assert 0.0 <= result.quality_score <= 1.0
        assert result.processing_time >= 0.0

    def test_embed_empty_text_raises_error(self, service):
        """测试嵌入空文本抛出错误"""
        with pytest.raises(ValueError, match="输入文本不能为空"):
            asyncio.run(service.embed(""))

    def test_embed_batch_texts(self, service):
        """测试批量嵌入"""
        texts = [
            "混元灵通是智能气功的核心理论",
            "组场是智能气功的练习方法",
            "通过意念引导达到强身健体",
        ]

        result = asyncio.run(service.embed_batch(texts, batch_size=2))

        assert isinstance(result, BatchEmbeddingResult)
        assert len(result.embeddings) == 3
        assert result.provider == EmbeddingProvider.LOCAL
        assert len(result.quality_scores) == 3
        assert result.total_time >= 0.0
        assert result.avg_time_per_item >= 0.0

    def test_embed_empty_batch_raises_error(self, service):
        """测试嵌入空列表抛出错误"""
        with pytest.raises(ValueError, match="文本列表不能为空"):
            asyncio.run(service.embed_batch([]))

    def test_embed_batch_filters_empty_texts(self, service):
        """测试批量嵌入过滤空文本"""
        texts = [
            "混元灵通是智能气功的核心理论",
            "",  # 空文本
            "   ",  # 只有空白
            "组场是智能气功的练习方法",
        ]

        result = asyncio.run(service.embed_batch(texts))

        # 应该只处理非空文本
        assert len(result.embeddings) == 2

    def test_auto_fallback_to_local(self, service):
        """测试自动回退到本地模型"""
        # 这个测试需要mock远程API失败的情况
        # 由于我们还没有mock框架，暂时跳过
        pass


class TestTextVectorizer:
    """测试文本向量化器"""

    @pytest.fixture
    def vectorizer(self):
        """创建向量化器实例"""
        return TextVectorizer(preferred_provider=EmbeddingProvider.LOCAL)

    def test_vectorize_text_blocks(self, vectorizer):
        """测试向量化文本块"""
        text_blocks = [
            "混元灵通是智能气功的核心理论。",
            "组场是智能气功的重要练习方法。",
            "通过意念引导可以增强人体功能。",
        ]

        vectors, stats = asyncio.run(vectorizer.vectorize_text_blocks(text_blocks, batch_size=2))

        assert len(vectors) == 3
        assert all(isinstance(v, list) for v in vectors)
        assert all(len(v) > 0 for v in vectors)
        assert stats["input_count"] == 3
        assert stats["output_count"] == 3

    def test_vectorize_single(self, vectorizer):
        """测试向量化单个文本"""
        text = "混元灵通是智能气功的核心理论"

        vector = asyncio.run(vectorizer.vectorize_single(text))

        assert isinstance(vector, list)
        assert len(vector) > 0
        assert all(isinstance(x, (int, float)) for x in vector)

    def test_vectorize_empty_list(self, vectorizer):
        """测试向量化空列表"""
        vectors, stats = asyncio.run(vectorizer.vectorize_text_blocks([]))

        assert vectors == []
        assert stats == {}


# 性能测试
@pytest.mark.slow
class TestEmbeddingPerformance:
    """性能测试"""

    @pytest.fixture
    def service(self):
        return EnhancedEmbeddingService(preferred_provider=EmbeddingProvider.LOCAL)

    def test_single_embedding_performance(self, service):
        """测试单个嵌入性能"""
        text = "混元灵通是智能气功的核心理论" * 10  # 较长文本

        import time

        start = time.time()
        result = asyncio.run(service.embed(text))
        elapsed = time.time() - start

        assert result.processing_time < 5.0  # 应该在5秒内完成
        assert elapsed < 5.0

    def test_batch_embedding_performance(self, service):
        """测试批量嵌入性能"""
        texts = [f"这是第{i}段文本内容。" * 10 for i in range(100)]

        import time

        start = time.time()
        result = asyncio.run(service.embed_batch(texts, batch_size=32))
        elapsed = time.time() - start

        # 100个文本应该在合理时间内完成
        assert elapsed < 60.0  # 1分钟内
        assert len(result.embeddings) == 100


# 集成测试
@pytest.mark.integration
class TestEmbeddingIntegration:
    """集成测试"""

    def test_end_to_end_vectorization(self):
        """端到端向量化测试"""
        # 模拟真实的文本处理流程
        text_blocks = [
            "第一章 混元灵通理论\n\n混元灵通是智能气功的核心理论，强调通过意念来统一身心。",
            "第二章 组场方法\n\n组场是智能气功的重要练习方法，通过集体意念形成气场。",
            "第三章 实践应用\n\n智能气功可以应用于康复、保健等多个领域。",
        ]

        vectorizer = TextVectorizer()
        vectors, stats = asyncio.run(vectorizer.vectorize_text_blocks(text_blocks))

        # 验证结果
        assert len(vectors) == 3
        assert all(len(v) > 0 for v in vectors)
        assert all(len(v) == len(vectors[0]) for v in vectors)  # 维度一致

        # 验证统计信息
        assert "avg_quality" in stats
        assert stats["avg_quality"] > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
