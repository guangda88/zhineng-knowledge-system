"""
测试RAG问答管道（RAG Question-Answering Pipeline）

文字处理工程流A-4的测试套件
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from backend.services.hybrid_retrieval import RetrievalMethod, RetrievalResult
from backend.services.rag_pipeline import (
    AnswerQuality,
    AnswerQualityAssessor,
    Citation,
    ContextBuilder,
    RAGAnswer,
    RAGPipeline,
)


class TestContextBuilder:
    """测试上下文构建器"""

    def test_build_context_basic(self):
        """测试基础上下文构建"""
        results = [
            RetrievalResult(
                id=1,
                title="混元灵通理论",
                content="混元灵通是智能气功的核心理论。",
                category=None,
                score=0.9,
                method=RetrievalMethod.VECTOR,
            ),
            RetrievalResult(
                id=2,
                title="组场方法",
                content="组场是智能气功的练习方法。",
                category=None,
                score=0.8,
                method=RetrievalMethod.VECTOR,
            ),
        ]

        context, citations = ContextBuilder.build_context(results)

        # 验证上下文包含标题和内容
        assert "混元灵通理论" in context
        assert "核心理论" in context
        assert "组场方法" in context

        # 验证引用数量
        assert len(citations) == 2
        assert citations[0].title == "混元灵通理论"
        assert citations[1].title == "组场方法"

    def test_build_context_truncation(self):
        """测试上下文截断"""
        # 创建很长的内容
        long_content = "这是一段很长的内容。" * 100

        results = [
            RetrievalResult(
                id=1,
                title="长文档",
                content=long_content,
                category=None,
                score=0.9,
                method=RetrievalMethod.VECTOR,
            )
        ]

        # 限制最大长度为500字符
        context, citations = ContextBuilder.build_context(results, max_context_length=500)

        # 验证上下文被截断
        assert len(context) <= 550  # 允许一些误差


class TestAnswerQualityAssessor:
    """测试答案质量评估器"""

    def test_assess_high_quality(self):
        """测试评估高质量答案"""
        answer = "混元灵通是智能气功的核心理论，强调通过意念来统一身心。组场是重要的练习方法，通过集体意念形成气场。"
        citations = [
            Citation(
                source_id=1,
                title="混元灵通理论",
                content_snippet="混元灵通是智能气功的核心理论",
                relevance_score=0.9,
            ),
            Citation(
                source_id=2,
                title="组场方法",
                content_snippet="组场是智能气功的练习方法",
                relevance_score=0.8,
            ),
        ]

        quality, confidence = AnswerQualityAssessor.assess(answer, citations, context_length=500)

        assert quality == AnswerQuality.HIGH
        assert confidence > 0.8

    def test_assess_low_quality(self):
        """测试评估低质量答案"""
        answer = "我不知道"
        citations = []

        quality, confidence = AnswerQualityAssessor.assess(answer, citations, context_length=0)

        assert quality in [AnswerQuality.LOW, AnswerQuality.FAILED]
        assert confidence < 0.5

    def test_assess_medium_quality(self):
        """测试评估中等质量答案"""
        answer = "混元灵通是智能气功的理论。"
        citations = [
            Citation(
                source_id=1, title="混元灵通理论", content_snippet="混元灵通", relevance_score=0.9
            )
        ]

        quality, confidence = AnswerQualityAssessor.assess(answer, citations, context_length=200)

        assert quality in [AnswerQuality.MEDIUM, AnswerQuality.HIGH]
        assert confidence >= 0.5


class TestCitation:
    """测试引用"""

    def test_to_dict_truncation(self):
        """测试引用转换时的内容截断"""
        long_content = "这是一段很长的内容。" * 50

        citation = Citation(
            source_id=1, title="测试标题", content_snippet=long_content, relevance_score=0.9
        )

        citation_dict = citation.to_dict()

        # 验证内容被截断
        assert len(citation_dict["content_snippet"]) <= 103  # 100 + "..."

    def test_to_dict_fields(self):
        """测试引用字段转换"""
        citation = Citation(
            source_id=123,
            title="测试标题",
            content_snippet="测试内容",
            relevance_score=0.85,
            page_number=10,
        )

        citation_dict = citation.to_dict()

        assert citation_dict["source_id"] == 123
        assert citation_dict["title"] == "测试标题"
        assert citation_dict["relevance_score"] == 0.85
        assert citation_dict["page_number"] == 10


class TestRAGAnswer:
    """测试RAG答案"""

    def test_to_dict(self):
        """测试答案转换"""
        answer = RAGAnswer(
            answer="这是测试答案",
            quality=AnswerQuality.HIGH,
            confidence=0.9,
            citations=[
                Citation(source_id=1, title="测试", content_snippet="内容", relevance_score=0.9)
            ],
            retrieval_method="hybrid",
            context_used=["测试"],
            processing_time=1.5,
        )

        answer_dict = answer.to_dict()

        assert answer_dict["answer"] == "这是测试答案"
        assert answer_dict["quality"] == "high"
        assert answer_dict["confidence"] == 0.9
        assert len(answer_dict["citations"]) == 1
        assert answer_dict["retrieval_method"] == "hybrid"
        assert answer_dict["context_count"] == 1
        assert answer_dict["processing_time"] == 1.5


# 集成测试（需要mock外部依赖）
@pytest.mark.integration
class TestRAGPipelineIntegration:
    """RAG管道集成测试"""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock数据库连接池"""
        return Mock()

    @pytest.fixture
    def mock_retrieval_service(self):
        """Mock检索服务"""
        service = Mock()
        service.search = AsyncMock()

        # 模拟返回结果
        mock_result = Mock()
        mock_result.results = [
            RetrievalResult(
                id=1,
                title="混元灵通理论",
                content="混元灵通是智能气功的核心理论",
                category=None,
                score=0.9,
                method=RetrievalMethod.VECTOR,
            )
        ]
        mock_result.vector_count = 1
        mock_result.fulltext_count = 0
        mock_result.total_time = 0.5

        service.search.return_value = mock_result
        return service

    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI服务"""
        service = Mock()
        service.rag_query = AsyncMock(return_value="混元灵通是智能气功的核心理论")
        service.adapter = Mock()
        service.adapter.chat = AsyncMock(
            return_value={"content": "混元灵通是智能气功的核心理论特点"}
        )
        return service

    @pytest.fixture
    def pipeline(self, mock_db_pool, mock_retrieval_service, mock_ai_service):
        """创建RAG管道实例"""
        return RAGPipeline(
            db_pool=mock_db_pool,
            retrieval_service=mock_retrieval_service,
            ai_service=mock_ai_service,
        )

    def test_query_basic(self, pipeline):
        """测试基础查询"""
        answer = asyncio.run(pipeline.query("什么是混元灵通？"))

        # 验证答案
        assert isinstance(answer, RAGAnswer)
        assert answer.answer != ""
        assert len(answer.citations) > 0
        assert answer.processing_time > 0

    def test_multi_turn_conversation(self, pipeline):
        """测试多轮对话"""
        # 第一轮
        asyncio.run(pipeline.query("什么是混元灵通？"))

        # 第二轮
        asyncio.run(pipeline.query("它有什么特点？"))

        # 验证对话历史
        assert len(pipeline.conversation_history) == 2
        assert pipeline.conversation_history[0].query == "什么是混元灵通？"
        assert pipeline.conversation_history[1].query == "它有什么特点？"

    def test_clear_history(self, pipeline):
        """测试清空历史"""
        # 添加一轮对话
        asyncio.run(pipeline.query("测试问题"))

        # 清空历史
        pipeline.clear_history()

        # 验证历史已清空
        assert len(pipeline.conversation_history) == 0

    def test_get_conversation_summary(self, pipeline):
        """测试获取对话摘要"""
        # 添加对话
        asyncio.run(pipeline.query("第一个问题"))
        asyncio.run(pipeline.query("第二个问题"))

        # 获取摘要
        summary = pipeline.get_conversation_summary()

        assert len(summary) == 2
        assert "query" in summary[0]
        assert "answer_quality" in summary[0]
        assert "confidence" in summary[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
