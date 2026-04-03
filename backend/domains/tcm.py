"""中医领域实现

提供中医知识的专业查询和搜索
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseDomain, DomainConfig, DomainType, QueryResult

logger = logging.getLogger(__name__)


class TcmDomain(BaseDomain):
    """中医领域

    专注于中医、中药、针灸、经络等知识
    """

    KEYWORDS = [
        "中医",
        "中药",
        "针灸",
        "经络",
        "穴位",
        "阴阳",
        "五行",
        "气血",
        "脏腑",
        "辨证",
        "论治",
        "方剂",
        "草药",
        "推拿",
        "拔罐",
        "艾灸",
        "刮痧",
        "脉诊",
        "舌诊",
        "望闻问切",
        "伤寒",
        "金匮",
        "黄帝内经",
        "难经",
        "神农",
        "本草",
        "治病",
        "调理",
        "养生",
        "保健",
    ]

    CATEGORIES = ["基础理论", "诊断方法", "治疗技术", "中药方剂", "经络穴位", "预防保健"]

    def __init__(self, db_pool=None):
        config = DomainConfig(
            name="tcm",
            domain_type=DomainType.TCM,
            enabled=True,
            priority=9,
            categories=self.CATEGORIES,
            keywords=self.KEYWORDS,
        )
        super().__init__(config)
        self._db_pool = db_pool

    async def initialize(self) -> None:
        """初始化中医领域"""
        logger.info("初始化中医领域")

    async def shutdown(self) -> None:
        """关闭中医领域"""
        logger.info("关闭中医领域")

    async def query(self, question: str, context: Optional[str] = None, **kwargs) -> QueryResult:
        """执行中医领域查询"""
        self._stats.query_count += 1
        sources = await self.search(question, top_k=3)

        if sources:
            content = f'【中医知识】关于"{question}"：\n\n'
            for i, source in enumerate(sources[:3], 1):
                content += f"{i}. {source.get('title', '')}\n"
                content += f"   {source.get('content', '')[:150]}...\n\n"
            confidence = 0.8
        else:
            content = f'抱歉，在中医知识库中没有找到关于"{question}"的相关内容。'
            confidence = 0.2

        return QueryResult(
            content=content,
            sources=sources,
            confidence=confidence,
            domain=self.name,
            metadata={"domain_type": "中医"},
        )

    async def search(self, query: str, top_k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """搜索中医文档"""
        if not self._db_pool:
            return []

        try:
            search_pattern = f"%{query}%"
            rows = await self._db_pool.fetch(
                """SELECT id, title, content, category
                   FROM documents
                   WHERE category = '中医'
                   AND (title ILIKE $1 OR content ILIKE $1)
                   LIMIT $2""",
                search_pattern,
                top_k,
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"中医领域搜索失败: {e}")
            return []

    async def get_herbs_by_disease(self, disease: str) -> List[Dict[str, Any]]:
        """根据疾病获取相关中药"""
        # 这里可以集成中医知识图谱
        return []

    async def get_acupoints_by_meridian(self, meridian: str) -> List[str]:
        """获取经络上的穴位"""
        # 简化实现
        meridian_points = {
            "肺经": ["中府", "云门", "天府", "尺泽", "孔最", "列缺", "太渊"],
            "胃经": ["承泣", "四白", "地仓", "颊车", "下关", "头维"],
            "脾经": ["隐白", "大都", "太白", "公孙", "商丘", "三阴交"],
            "心经": ["极泉", "青灵", "少海", "灵道", "通里", "神门"],
            "肾经": ["涌泉", "然谷", "太溪", "大钟", "水泉", "照海"],
        }
        return meridian_points.get(meridian, [])
