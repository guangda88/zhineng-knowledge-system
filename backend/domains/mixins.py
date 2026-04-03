"""领域类混入模块

提供可复用的领域功能方法，减少代码重复。
"""

import logging
from typing import Any, Dict, List, Optional

from backend.common import rows_to_list

logger = logging.getLogger(__name__)


class DatabaseSearchMixin:
    """数据库搜索混入类

    为领域类提供通用的数据库搜索功能。
    """

    async def search_by_category(
        self,
        db_pool,
        query: str,
        category: str,
        top_k: int = 10,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """按分类搜索文档

        Args:
            db_pool: 数据库连接池
            query: 搜索关键词
            category: 文档分类
            top_k: 返回数量
            fields: 搜索字段列表

        Returns:
            搜索结果列表
        """
        if not db_pool:
            return []

        if fields is None:
            fields = ["title", "content"]

        try:
            search_pattern = f"%{query}%"
            field_conditions = " OR ".join([f"{field} ILIKE $2" for field in fields])

            rows = await db_pool.fetch(
                f"""SELECT id, title, content, category
                   FROM documents
                   WHERE category = $1 AND ({field_conditions})
                   LIMIT $3""",
                category,
                search_pattern,
                top_k,
            )
            return rows_to_list(rows)
        except Exception as e:
            logger.error(f"{category}领域搜索失败: {e}")
            return []

    async def get_document_by_title_pattern(
        self,
        db_pool,
        category: str,
        title_pattern: str,
    ) -> Optional[Dict[str, Any]]:
        """根据标题模糊匹配获取文档

        Args:
            db_pool: 数据库连接池
            category: 文档分类
            title_pattern: 标题匹配模式

        Returns:
            文档字典或None
        """
        if not db_pool:
            return None

        try:
            row = await db_pool.fetchrow(
                """SELECT id, title, content
                   FROM documents
                   WHERE category = $1
                   AND title ILIKE $2
                   LIMIT 1""",
                category,
                f"%{title_pattern}%",
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取文档详情失败: {e}")
            return None


class QueryFormatterMixin:
    """查询结果格式化混入类

    提供统一的查询结果格式化方法。
    """

    def format_query_result(
        self,
        question: str,
        sources: List[Dict[str, Any]],
        domain_name: str,
        domain_label: str,
        no_result_prefix: str = "抱歉",
    ) -> Any:
        """格式化查询结果

        Args:
            question: 用户问题
            sources: 搜索结果源
            domain_name: 领域名称
            domain_label: 领域显示标签
            no_result_prefix: 无结果时的消息前缀

        Returns:
            QueryResult对象（需要从外部导入）
        """
        from .base import QueryResult

        if sources:
            content = f'【{domain_label}知识】关于"{question}"：\n\n'
            for i, source in enumerate(sources[:3], 1):
                content += f"{i}. {source.get('title', '')}\n"
                content += f"   {source.get('content', '')[:150]}...\n\n"
            confidence = 0.8
        else:
            content = (
                f'{no_result_prefix}，在{domain_label}知识库中没有找到关于"{question}"的相关内容。'
            )
            confidence = 0.2

        return QueryResult(
            content=content,
            sources=sources,
            confidence=confidence,
            domain=domain_name,
            metadata={"domain_type": domain_label},
        )


class RelationMapMixin:
    """关联关系映射混入类

    用于管理领域内的实体关联关系。
    """

    # 关联关系字典
    _relation_map: Dict[str, List[str]] = {}

    def get_related_items(self, item_name: str) -> List[str]:
        """获取相关项目

        Args:
            item_name: 项目名称

        Returns:
            相关项目列表
        """
        return self._relation_map.get(item_name, [])

    def add_relation(self, item: str, related: List[str]) -> None:
        """添加关联关系

        Args:
            item: 项目名称
            related: 相关项目列表
        """
        self._relation_map[item] = related
