"""科学领域实现

提供科学知识的专业查询和搜索
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult
from .mixins import DatabaseSearchMixin, QueryFormatterMixin

logger = logging.getLogger(__name__)


class ScienceDomain(DatabaseSearchMixin, QueryFormatterMixin, BaseDomain):
    """科学领域

    专注于现代科学、科学方法、科学思想等知识
    """

    KEYWORDS = [
        "科学",
        "物理学",
        "化学",
        "生物学",
        "天文学",
        "地理学",
        "数学",
        "统计学",
        "量子",
        "相对论",
        "进化论",
        "基因",
        "DNA",
        "分子",
        "原子",
        "粒子",
        "能量",
        "力",
        "场",
        "波",
        "光谱",
        "实验",
        "假设",
        "理论",
        "定律",
        "公式",
        "模型",
        "观测",
        "数据",
        "分析",
        "科学方法",
        "科学精神",
        "科学史",
        "科学家",
        "技术",
        "工程",
        "信息论",
        "系统论",
        "控制论",
        "复杂性",
        "混沌",
        "分形",
        "人工智能",
        "计算机",
        "网络",
        "互联网",
    ]

    CATEGORIES = ["物理科学", "生命科学", "地球科学", "数学统计", "技术工程", "科学思想"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="science",
            domain_type=DomainType.SCIENCE,
            enabled=True,
            priority=3,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        logger.info("初始化科学领域")

    async def shutdown(self) -> None:
        logger.info("关闭科学领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)
        return self.format_query_result(
            question=question,
            sources=sources,
            domain_name=self.name,
            domain_label="科学",
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        return await self.search_by_category(self._db_pool, query, "科学", top_k)
