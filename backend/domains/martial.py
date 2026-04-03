"""武术领域实现

提供武术/武功知识的专业查询和搜索
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult
from .mixins import DatabaseSearchMixin, QueryFormatterMixin

logger = logging.getLogger(__name__)


class MartialDomain(DatabaseSearchMixin, QueryFormatterMixin, BaseDomain):
    """武术领域

    专注于武术、武功、功夫等知识
    """

    KEYWORDS = [
        "武术",
        "武功",
        "功夫",
        "拳",
        "拳法",
        "太极",
        "太极拳",
        "少林",
        "少林拳",
        "武当",
        "咏春",
        "形意拳",
        "八卦掌",
        "螳螂拳",
        "洪拳",
        "长拳",
        "南拳",
        "刀法",
        "剑法",
        "棍法",
        "枪法",
        "散打",
        "搏击",
        "格斗",
        "武术套路",
        "内功",
        "外功",
        "气功",
        "站桩",
        "套路",
        "对练",
        "实战",
        "防身",
        "功夫片",
        "李小龙",
        "截拳道",
        "武术家",
        "武林",
        "江湖",
        "门派",
        "师承",
    ]

    CATEGORIES = ["拳法流派", "器械武术", "内功养生", "历史人物", "训练方法", "武术理论"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="martial",
            domain_type=DomainType.MARTIAL,
            enabled=True,
            priority=5,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        logger.info("初始化武术领域")

    async def shutdown(self) -> None:
        logger.info("关闭武术领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)
        return self.format_query_result(
            question=question,
            sources=sources,
            domain_name=self.name,
            domain_label="武术",
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return await self.search_by_category(self._db_pool, query, "武术", top_k)
