"""佛家领域实现

提供佛家（释家）知识的专业查询和搜索
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult
from .mixins import DatabaseSearchMixin, QueryFormatterMixin

logger = logging.getLogger(__name__)


class BuddhistDomain(DatabaseSearchMixin, QueryFormatterMixin, BaseDomain):
    """佛家领域

    专注于佛教、禅宗、佛学等知识
    """

    KEYWORDS = [
        "佛",
        "佛教",
        "佛家",
        "禅",
        "禅宗",
        "禅修",
        "菩提",
        "般若",
        "佛法",
        "释迦",
        "释迦牟尼",
        "达摩",
        "六祖",
        "慧能",
        "金刚经",
        "心经",
        "般若波罗蜜多心经",
        "楞严经",
        "法华经",
        "华严经",
        "阿含经",
        "净土",
        "阿弥陀佛",
        "观音",
        "菩萨",
        "罗汉",
        "涅槃",
        "因果",
        "轮回",
        "业力",
        "觉悟",
        "正念",
        "冥想",
        "打坐",
        "参禅",
        "悟道",
        "四谛",
        "八正道",
        "十二因缘",
        "五蕴",
        "色空",
        "戒定慧",
        "丛林",
        "寺院",
        "出家",
        "和尚",
        "僧",
    ]

    CATEGORIES = ["经典著作", "禅修实践", "佛学思想", "历史传承", "宗派流派", "修行方法"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="buddhist",
            domain_type=DomainType.BUDDHIST,
            enabled=True,
            priority=7,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        logger.info("初始化佛家领域")

    async def shutdown(self) -> None:
        logger.info("关闭佛家领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)
        return self.format_query_result(
            question=question,
            sources=sources,
            domain_name=self.name,
            domain_label="佛家",
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return await self.search_by_category(self._db_pool, query, "佛家", top_k)
