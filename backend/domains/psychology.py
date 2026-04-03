"""心理学领域实现

提供心理学知识的专业查询和搜索
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult
from .mixins import DatabaseSearchMixin, QueryFormatterMixin

logger = logging.getLogger(__name__)


class PsychologyDomain(DatabaseSearchMixin, QueryFormatterMixin, BaseDomain):
    """心理学领域

    专注于心理学、心理健康、心理调控等知识
    """

    KEYWORDS = [
        "心理",
        "心理学",
        "意识",
        "潜意识",
        "认知",
        "情绪",
        "情感",
        "动机",
        "需求",
        "行为",
        "性格",
        "人格",
        "气质",
        "能力",
        "智力",
        "记忆",
        "注意",
        "感知",
        "思维",
        "想象",
        "创造",
        "学习",
        "发展",
        "成长",
        "自我",
        "自尊",
        "自信",
        "压力",
        "焦虑",
        "抑郁",
        "恐惧",
        "愤怒",
        "幸福",
        "快乐",
        "满足",
        "冥想",
        "正念",
        "放松",
        "催眠",
        "暗示",
        "条件反射",
        "心理调控",
        "心理素质",
        "心理健康",
        "心理咨询",
        "心理治疗",
        "精神分析",
        "行为主义",
        "人本主义",
        "认知疗法",
        "弗洛伊德",
        "荣格",
        "马斯洛",
    ]

    CATEGORIES = ["基础理论", "认知心理", "情绪管理", "心理健康", "心理调控", "应用心理"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="psychology",
            domain_type=DomainType.PSYCHOLOGY,
            enabled=True,
            priority=2,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        logger.info("初始化心理学领域")

    async def shutdown(self) -> None:
        logger.info("关闭心理学领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)
        return self.format_query_result(
            question=question,
            sources=sources,
            domain_name=self.name,
            domain_label="心理学",
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return await self.search_by_category(self._db_pool, query, "心理学", top_k)
