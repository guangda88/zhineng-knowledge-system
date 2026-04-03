"""道家领域实现

提供道家/道教知识的专业查询和搜索
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult
from .mixins import DatabaseSearchMixin, QueryFormatterMixin

logger = logging.getLogger(__name__)


class DaoistDomain(DatabaseSearchMixin, QueryFormatterMixin, BaseDomain):
    """道家领域

    专注于道家、道教、老子、庄子等知识
    """

    KEYWORDS = [
        "道",
        "道家",
        "道教",
        "老子",
        "庄子",
        "道德经",
        "南华经",
        "道藏",
        "无为",
        "自然",
        "道法自然",
        "上善若水",
        "阴阳",
        "太极",
        "八卦",
        "风水",
        "炼丹",
        "内丹",
        "外丹",
        "修道",
        "真人",
        "仙人",
        "神仙",
        "张三丰",
        "全真",
        "正一",
        "天师",
        "符箓",
        "斋醮",
        "科仪",
        "洞天福地",
        "逍遥",
        "齐物",
        "心斋",
        "坐忘",
        "抱一",
        "守一",
        "胎息",
        "辟谷",
        "黄老",
        "玄学",
        "清静",
        "虚无",
    ]

    CATEGORIES = ["经典著作", "哲学思想", "修炼方法", "历史传承", "宗派流派", "养生术"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="daoist",
            domain_type=DomainType.DAOIST,
            enabled=True,
            priority=6,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        logger.info("初始化道家领域")

    async def shutdown(self) -> None:
        logger.info("关闭道家领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)
        return self.format_query_result(
            question=question,
            sources=sources,
            domain_name=self.name,
            domain_label="道家",
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return await self.search_by_category(self._db_pool, query, "道家", top_k)
