"""推理基类模块

定义推理器的基类和结果数据结构
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """问题类型分类"""

    FACTUAL = "factual"  # 简单事实查询
    REASONING = "reasoning"  # 需要推理
    MULTI_HOP = "multi_hop"  # 多跳推理
    COMPARISON = "comparison"  # 对比分析
    EXPLANATION = "explanation"  # 解释说明


@dataclass
class ReasoningStep:
    """推理步骤"""

    step_number: int
    content: str  # 步骤内容
    thought: Optional[str] = None  # 思考过程
    action: Optional[str] = None  # 行动（ReAct模式）
    observation: Optional[str] = None  # 观察结果（ReAct模式）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_number": self.step_number,
            "content": self.content,
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
        }


@dataclass
class ReasoningResult:
    """推理结果"""

    answer: str  # 最终答案
    query_type: QueryType  # 问题类型
    steps: List[ReasoningStep] = field(default_factory=list)  # 推理步骤
    sources: List[Dict[str, Any]] = field(default_factory=list)  # 来源文档
    confidence: float = 0.0  # 置信度 (0-1)
    reasoning_time: float = 0.0  # 推理耗时（秒）
    model_used: str = ""  # 使用的模型

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "answer": self.answer,
            "query_type": self.query_type.value,
            "steps": [step.to_dict() for step in self.steps],
            "sources": self.sources,
            "confidence": self.confidence,
            "reasoning_time": self.reasoning_time,
            "model_used": self.model_used,
            "timestamp": datetime.now().isoformat(),
        }


class BaseReasoner(ABC):
    """推理器基类"""

    def __init__(self, api_key: str = "", api_url: str = ""):
        """初始化推理器

        Args:
            api_key: API密钥
            api_url: API地址
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = "base"

        # 初始化LLM客户端（带速率限制）
        self.llm_client = None
        try:
            from backend.common.llm_api_wrapper import get_llm_client

            self.llm_client = get_llm_client(
                api_key=api_key or self._get_default_api_key(), api_url=api_url
            )
            logger.info("LLM client initialized with rate limiting")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM client: {e}")

    def _get_default_api_key(self) -> str:
        """获取默认API密钥"""
        import os

        return os.getenv("DEEPSEEK_API_KEY", "")

    @abstractmethod
    async def reason(
        self, question: str, context: Optional[List[Dict[str, Any]]] = None, **kwargs
    ) -> ReasoningResult:
        """执行推理

        Args:
            question: 用户问题
            context: 上下文文档
            **kwargs: 其他参数

        Returns:
            推理结果
        """

    def analyze_query(self, question: str) -> QueryType:
        """分析问题类型

        Args:
            question: 用户问题

        Returns:
            问题类型
        """
        _question_lower = question.lower()  # noqa: F841

        # 多跳推理关键词
        multi_hop_keywords = [
            "为什么",
            "怎么",
            "如何",
            "原因",
            "关系",
            "联系",
            "影响",
            "导致",
            "因为",
            "所以",
        ]

        # 对比分析关键词
        comparison_keywords = [
            "区别",
            "差异",
            "比较",
            "对比",
            "相同",
            "不同",
            "优劣",
            "优缺点",
            "和...的区别",
        ]

        # 解释说明关键词
        explanation_keywords = [
            "解释",
            "说明",
            "阐述",
            "描述",
            "介绍",
            "是什么",
            "什么是",
            "原理",
            "机制",
        ]

        # 检查关键词
        if any(kw in question for kw in comparison_keywords):
            return QueryType.COMPARISON

        if any(kw in question for kw in explanation_keywords):
            return QueryType.EXPLANATION

        if any(kw in question for kw in multi_hop_keywords):
            return QueryType.MULTI_HOP

        # 默认根据问题长度判断
        if len(question) > 20:
            return QueryType.REASONING

        return QueryType.FACTUAL

    def format_context(self, context: List[Dict[str, Any]]) -> str:
        """格式化上下文

        Args:
            context: 上下文文档列表

        Returns:
            格式化的上下文字符串
        """
        if not context:
            return "无相关上下文"

        formatted = []
        for i, doc in enumerate(context[:5], 1):
            title = doc.get("title", "")
            content = doc.get("content", "")
            formatted.append(f"[{i}] {title}\n{content[:300]}")

        return "\n\n".join(formatted)
