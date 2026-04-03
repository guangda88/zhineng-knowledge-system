"""哲学领域实现

提供哲学知识的专业查询和搜索
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult
from .mixins import DatabaseSearchMixin, QueryFormatterMixin

logger = logging.getLogger(__name__)


class PhilosophyDomain(DatabaseSearchMixin, QueryFormatterMixin, BaseDomain):
    """哲学领域

    专注于中西哲学、思想体系等知识
    """

    KEYWORDS = [
        "哲学",
        "哲思",
        "思想家",
        "哲学家",
        "形而上学",
        "认识论",
        "伦理学",
        "美学",
        "逻辑学",
        "辩证法",
        "唯物",
        "唯心",
        "存在",
        "存在主义",
        "现象学",
        "结构主义",
        "后现代",
        "理性",
        "经验",
        "本体",
        "认识",
        "真理",
        "价值",
        "意义",
        "自由",
        "意志",
        "意识",
        "精神",
        "灵魂",
        "身心",
        "因果",
        "必然",
        "偶然",
        "矛盾",
        "质变",
        "量变",
        "否定之否定",
        "对立统一",
        "天人合一",
        "知行合一",
        "格物致知",
        "心学",
        "理学",
        "王阳明",
        "朱熹",
        "程颢",
        "程颐",
    ]

    CATEGORIES = ["中国哲学", "西方哲学", "逻辑学", "伦理学", "美学", "哲学史"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="philosophy",
            domain_type=DomainType.PHILOSOPHY,
            enabled=True,
            priority=4,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        logger.info("初始化哲学领域")

    async def shutdown(self) -> None:
        logger.info("关闭哲学领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)
        return self.format_query_result(
            question=question,
            sources=sources,
            domain_name=self.name,
            domain_label="哲学",
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return await self.search_by_category(self._db_pool, query, "哲学", top_k)
