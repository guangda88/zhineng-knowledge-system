"""
RAG问答管道（RAG Question-Answering Pipeline）

文字处理工程流A-4的核心组件

功能：
1. 检索增强生成（RAG）
2. 上下文管理
3. 答案质量评估
4. 引用溯源
5. 多轮对话支持
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.services.ai_service_adapter import TaskType, UnifiedAIService
from backend.services.hybrid_retrieval import (
    HybridRetrievalService,
    RetrievalMethod,
    RetrievalResult,
)

logger = logging.getLogger(__name__)


class AnswerQuality(Enum):
    """答案质量等级"""

    HIGH = "high"  # 高质量：答案完整，有引用
    MEDIUM = "medium"  # 中等质量：答案较完整，引用不足
    LOW = "low"  # 低质量：答案不完整或无引用
    FAILED = "failed"  # 失败：无法生成答案


@dataclass
class Citation:
    """引用"""

    source_id: int
    title: str
    content_snippet: str
    relevance_score: float
    page_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "content_snippet": (
                self.content_snippet[:100] + "..."
                if len(self.content_snippet) > 100
                else self.content_snippet
            ),
            "relevance_score": self.relevance_score,
            "page_number": self.page_number,
        }


@dataclass
class RAGAnswer:
    """RAG答案"""

    answer: str
    quality: AnswerQuality
    confidence: float
    citations: List[Citation]
    retrieval_method: str
    context_used: List[str]
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "quality": self.quality.value,
            "confidence": self.confidence,
            "citations": [c.to_dict() for c in self.citations],
            "retrieval_method": self.retrieval_method,
            "context_count": len(self.context_used),
            "processing_time": self.processing_time,
            "metadata": self.metadata,
        }


@dataclass
class ConversationTurn:
    """对话轮次"""

    query: str
    answer: RAGAnswer
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {"query": self.query, "answer": self.answer.to_dict(), "timestamp": self.timestamp}


class ContextBuilder:
    """上下文构建器"""

    @staticmethod
    def build_context(
        retrieval_results: List[RetrievalResult],
        max_context_length: int = 2000,
        include_metadata: bool = True,
    ) -> Tuple[str, List[Citation]]:
        """构建RAG上下文

        Args:
            retrieval_results: 检索结果
            max_context_length: 最大上下文长度
            include_metadata: 是否包含元数据

        Returns:
            (上下文字符串, 引用列表)
        """
        citations = []
        context_parts = []

        for i, result in enumerate(retrieval_results):
            # 创建引用
            citation = Citation(
                source_id=result.id,
                title=result.title,
                content_snippet=result.content,
                relevance_score=result.score,
            )
            citations.append(citation)

            # 构建上下文片段
            if include_metadata:
                context_part = f"【文献{i + 1}】{result.title}\n{result.content}"
            else:
                context_part = result.content

            context_parts.append(context_part)

        # 合并上下文
        context = "\n\n".join(context_parts)

        # 如果超过最大长度，截断
        if len(context) > max_context_length:
            # 按比例截断每个部分
            ratio = max_context_length / len(context)
            truncated_parts = []

            for part in context_parts:
                target_length = int(len(part) * ratio)
                if len(part) > target_length:
                    # 在句子边界截断
                    truncated = ContextBuilder._truncate_at_sentence(part, target_length)
                    truncated_parts.append(truncated)
                else:
                    truncated_parts.append(part)

            context = "\n\n".join(truncated_parts)

        return context, citations

    @staticmethod
    def _truncate_at_sentence(text: str, max_length: int) -> str:
        """在句子边界截断文本"""
        if len(text) <= max_length:
            return text

        # 查找最近的句子结束符
        truncated = text[:max_length]

        # 尝试在句号、问号、感叹号处截断
        for delimiter in ["。", "？", "！", ".", "?", "!"]:
            last_pos = truncated.rfind(delimiter)
            if last_pos > max_length * 0.8:  # 至少保留80%
                return truncated[: last_pos + 1]

        # 如果没有找到合适的截断点，直接截断
        return truncated + "..."


class AnswerQualityAssessor:
    """答案质量评估器"""

    @staticmethod
    def assess(
        answer: str, citations: List[Citation], context_length: int
    ) -> Tuple[AnswerQuality, float]:
        """评估答案质量

        Args:
            answer: 生成的答案
            citations: 引用列表
            context_length: 使用的上下文长度

        Returns:
            (质量等级, 置信度)
        """
        scores = []

        # 1. 答案长度评分
        if len(answer) < 20:
            length_score = 0.3  # 太短
        elif len(answer) < 100:
            length_score = 0.7  # 适中
        elif len(answer) < 500:
            length_score = 1.0  # 理想
        else:
            length_score = 0.8  # 较长但可接受

        scores.append(length_score)

        # 2. 引用评分
        if len(citations) == 0:
            citation_score = 0.0  # 无引用
        elif len(citations) < 2:
            citation_score = 0.5  # 引用不足
        elif len(citations) < 5:
            citation_score = 1.0  # 理想
        else:
            citation_score = 0.8  # 引用较多

        scores.append(citation_score)

        # 3. 上下文使用评分
        if context_length == 0:
            context_score = 0.0  # 无上下文
        elif context_length < 200:
            context_score = 0.5  # 上下文不足
        else:
            context_score = 1.0  # 充足的上下文

        scores.append(context_score)

        # 4. 答案完整性评分（基于关键词）
        completeness_keywords = [
            "混元灵通",
            "智能气功",
            "组场",
            "发气",
            "因为",
            "所以",
            "因此",
            "方法",
            "原理",
        ]

        keyword_count = sum(1 for kw in completeness_keywords if kw in answer)
        if keyword_count >= 3:
            completeness_score = 1.0
        elif keyword_count >= 1:
            completeness_score = 0.6
        else:
            completeness_score = 0.3

        scores.append(completeness_score)

        # 计算平均分数
        avg_score = sum(scores) / len(scores)
        confidence = avg_score

        # 确定质量等级
        if avg_score >= 0.8:
            quality = AnswerQuality.HIGH
        elif avg_score >= 0.5:
            quality = AnswerQuality.MEDIUM
        elif avg_score >= 0.3:
            quality = AnswerQuality.LOW
        else:
            quality = AnswerQuality.FAILED

        return quality, confidence


class RAGPipeline:
    """RAG问答管道（主类）"""

    def __init__(
        self,
        db_pool,
        retrieval_service: Optional[HybridRetrievalService] = None,
        ai_service: Optional[UnifiedAIService] = None,
        enable_multi_turn: bool = True,
    ):
        """初始化RAG管道

        Args:
            db_pool: 数据库连接池
            retrieval_service: 检索服务（None则创建新实例）
            ai_service: AI服务（None则创建新实例）
            enable_multi_turn: 是否启用多轮对话
        """
        # 初始化服务
        if retrieval_service is None:
            retrieval_service = HybridRetrievalService(db_pool)
        self.retrieval_service = retrieval_service

        if ai_service is None:
            ai_service = UnifiedAIService()
        self.ai_service = ai_service

        self.enable_multi_turn = enable_multi_turn
        self.conversation_history: List[ConversationTurn] = []

    async def query(
        self,
        question: str,
        retrieval_method: RetrievalMethod = RetrievalMethod.HYBRID,
        top_k: int = 5,
        max_context_length: int = 2000,
        use_history: bool = True,
    ) -> RAGAnswer:
        """执行RAG查询

        Args:
            question: 用户问题
            retrieval_method: 检索方法
            top_k: 检索结果数量
            max_context_length: 最大上下文长度
            use_history: 是否使用对话历史

        Returns:
            RAG答案
        """
        import time

        start_time = time.time()

        try:
            # 1. 检索相关文档
            search_result = await self.retrieval_service.search(
                query=question, method=retrieval_method, top_k=top_k
            )

            # 2. 构建上下文
            context, citations = ContextBuilder.build_context(
                retrieval_results=search_result.results, max_context_length=max_context_length
            )

            # 3. 生成答案
            if use_history and self.enable_multi_turn and self.conversation_history:
                # 包含历史对话
                answer_text = await self._generate_with_history(
                    question=question,
                    context=context,
                    history=self.conversation_history[-3:],  # 只使用最近3轮
                )
            else:
                # 单轮问答
                answer_text = await self.ai_service.rag_query(
                    query=question,
                    context=[{"title": "相关文献", "content": context}],
                    max_tokens=1000,
                )

            # 4. 评估答案质量
            quality, confidence = AnswerQualityAssessor.assess(
                answer=answer_text, citations=citations, context_length=len(context)
            )

            # 5. 创建答案对象
            processing_time = time.time() - start_time

            answer = RAGAnswer(
                answer=answer_text,
                quality=quality,
                confidence=confidence,
                citations=citations,
                retrieval_method=retrieval_method.value,
                context_used=[c.title for c in citations],
                processing_time=processing_time,
                metadata={
                    "retrieval_count": search_result.vector_count + search_result.fulltext_count,
                    "retrieval_time": search_result.total_time,
                },
            )

            # 6. 保存到对话历史
            if self.enable_multi_turn:
                self.conversation_history.append(
                    ConversationTurn(query=question, answer=answer, timestamp=time.time())
                )

            logger.info(
                f"RAG查询完成: question='{question[:30]}...', "
                f"quality={quality.value}, confidence={confidence:.2f}, "
                f"time={processing_time:.2f}s"
            )

            return answer

        except Exception as e:
            logger.error(f"RAG查询失败: {e}", exc_info=True)

            # 返回失败答案
            return RAGAnswer(
                answer="抱歉，我无法回答这个问题。请尝试重新表述或联系管理员。",
                quality=AnswerQuality.FAILED,
                confidence=0.0,
                citations=[],
                retrieval_method=retrieval_method.value,
                context_used=[],
                processing_time=time.time() - start_time,
            )

    async def _generate_with_history(
        self, question: str, context: str, history: List[ConversationTurn]
    ) -> str:
        """使用历史对话生成答案"""
        # 构建包含历史的消息
        messages = [
            {
                "role": "system",
                "content": (
                    "你是灵知系统的智能助手。基于提供的上下文回答用户问题，"
                    "并考虑对话历史。如果上下文不足，请诚实说明。"
                ),
            }
        ]

        # 添加历史对话
        for turn in history:
            messages.append({"role": "user", "content": turn.query})
            messages.append({"role": "assistant", "content": turn.answer.answer})

        # 添加当前问题和上下文
        messages.append({"role": "user", "content": f"上下文：\n{context}\n\n问题：{question}"})

        # 调用AI服务
        response = await self.ai_service.adapter.chat(
            messages=messages, task_type=TaskType.CHINESE, max_tokens=1000
        )

        return response["content"]

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        logger.info("对话历史已清空")

    def get_conversation_summary(self) -> List[Dict[str, Any]]:
        """获取对话摘要"""
        return [
            {
                "query": turn.query,
                "answer_quality": turn.answer.quality.value,
                "confidence": turn.answer.confidence,
                "timestamp": turn.timestamp,
            }
            for turn in self.conversation_history
        ]


__all__ = [
    "AnswerQuality",
    "RAGAnswer",
    "Citation",
    "ConversationTurn",
    "RAGPipeline",
]
