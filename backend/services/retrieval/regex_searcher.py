"""
正则表达式搜索器

支持 PCRE 正则表达式语法，提供多表搜索和匹配位置信息。
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class RegexSearcher:
    """正则表达式搜索器"""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        初始化正则搜索器

        Args:
            db_pool: 数据库连接池
        """
        self.db_pool = db_pool

        # 默认搜索的表
        self.default_tables = ["documents", "guoxue_content", "textbook_blocks_v2"]

    async def search(
        self,
        pattern: str,
        tables: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 100,
        case_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        正则表达式全文搜索

        Args:
            pattern: 正则表达式模式
            tables: 搜索的表列表
            category: 分类筛选
            limit: 返回数量限制
            case_sensitive: 是否区分大小写

        Returns:
            匹配的文档列表
        """
        if not pattern:
            logger.warning("正则表达式模式为空")
            return []

        tables = tables or self.default_tables

        results = []

        for table in tables:
            try:
                table_results = await self._search_table(
                    table, pattern, category, limit, case_sensitive
                )
                results.extend(table_results)

                # 如果已经达到限制，提前终止
                if len(results) >= limit:
                    break

            except Exception as e:
                logger.warning(f"表 {table} 搜索失败: {e}")
                continue

        return results[:limit]

    async def _search_table(
        self, table: str, pattern: str, category: Optional[str], limit: int, case_sensitive: bool
    ) -> List[Dict[str, Any]]:
        """
        在单个表中搜索

        Args:
            table: 表名
            pattern: 正则表达式模式
            category: 分类筛选
            limit: 返回数量限制
            case_sensitive: 是否区分大小写

        Returns:
            匹配的文档列表
        """
        # 构建查询
        regex_flags = "" if case_sensitive else "i"  # 'i' 表示不区分大小写

        # 基础查询
        base_query = f"""
            SELECT
                id,
                title,
                content,
                category,
                {table} as source_table
            FROM {table}
            WHERE content ~ $1
        """

        # 添加分类筛选
        params = [pattern]
        if category:
            base_query += " AND category = $2"
            params.append(category)

        # 添加排序（按匹配数量）
        base_query += f"""
            ORDER BY array_length(regexp_matches(content, $1, '{regex_flags}'), 1) DESC NULLS LAST
            LIMIT {limit}
        """

        # 执行查询
        rows = await self.db_pool.fetch(base_query, *params)

        # 处理结果
        results = []
        for r in rows:
            # 获取匹配位置和数量
            matches = await self._get_match_details(table, r["id"], pattern, case_sensitive)

            result = {
                "id": r["id"],
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "category": r.get("category", "未知"),
                "source_table": r["source_table"],
                "match_count": matches["count"],
                "matches": matches["positions"],
            }

            results.append(result)

        return results

    async def _get_match_details(
        self, table: str, doc_id: int, pattern: str, case_sensitive: bool
    ) -> Dict[str, Any]:
        """
        获取匹配的详细信息

        Args:
            table: 表名
            doc_id: 文档ID
            pattern: 正则表达式模式
            case_sensitive: 是否区分大小写

        Returns:
            匹配信息字典 {"count": int, "positions": List[Dict]}
        """
        try:
            # 查询匹配位置
            regex_flags = "" if case_sensitive else "i"
            sql = f"""
                SELECT
                    regexp_matches(content, $1, '{regex_flags}') as matches,
                    array_length(regexp_matches(content, $1, '{regex_flags}'), 1) as count
                FROM {table}
                WHERE id = $2
            """

            row = await self.db_pool.fetchrow(sql, pattern, doc_id)

            if not row:
                return {"count": 0, "positions": []}

            # 转换匹配位置
            positions = []
            matches = row.get("matches") or []
            count = row.get("count", 0)

            # PostgreSQL 的 regexp_matches 返回匹配的文本，不是位置
            # 我们需要使用 regexp_match 逐个查找位置
            content = await self._get_document_content(table, doc_id)
            if content:
                import re

                flags = 0 if case_sensitive else re.IGNORECASE
                re_pattern = re.compile(pattern, flags)

                for match in re_pattern.finditer(content):
                    positions.append(
                        {"start": match.start(), "end": match.end(), "text": match.group(0)}
                    )

            return {"count": len(positions), "positions": positions}

        except Exception as e:
            logger.warning(f"获取匹配详情失败: {e}")
            return {"count": 0, "positions": []}

    async def _get_document_content(self, table: str, doc_id: int) -> Optional[str]:
        """
        获取文档内容

        Args:
            table: 表名
            doc_id: 文档ID

        Returns:
            文档内容
        """
        try:
            sql = f"""
                SELECT content
                FROM {table}
                WHERE id = $1
            """

            row = await self.db_pool.fetchrow(sql, doc_id)
            return row["content"] if row else None

        except Exception as e:
            logger.warning(f"获取文档内容失败: {e}")
            return None

    async def search_with_context(
        self,
        pattern: str,
        context_size: int = 50,
        tables: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 100,
        case_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        带上下文的正则搜索

        Args:
            pattern: 正则表达式模式
            context_size: 上下文窗口大小
            tables: 搜索的表列表
            category: 分类筛选
            limit: 返回数量限制
            case_sensitive: 是否区分大小写

        Returns:
            带上下文片段的匹配结果
        """
        results = await self.search(pattern, tables, category, limit, case_sensitive)

        # 为每个结果提取上下文片段
        for result in results:
            content = result.get("content", "")
            matches = result.get("matches", [])

            if matches:
                # 提取第一个匹配的上下文
                match = matches[0]
                start = match["start"]
                end = match["end"]

                context_start = max(0, start - context_size)
                context_end = min(len(content), end + context_size)

                result["snippet"] = content[context_start:context_end]
                result["match_highlighted"] = (
                    content[context_start:start]
                    + f"<mark>{content[start:end]}</mark>"
                    + content[end:context_end]
                )
            else:
                result["snippet"] = content[:200] + "..." if len(content) > 200 else content

        return results

    async def validate_pattern(self, pattern: str) -> bool:
        """
        验证正则表达式是否有效

        Args:
            pattern: 正则表达式模式

        Returns:
            是否有效
        """
        try:
            import re

            re.compile(pattern)
            return True
        except re.error:
            return False

    async def count_matches(
        self, pattern: str, tables: Optional[List[str]] = None, case_sensitive: bool = False
    ) -> Dict[str, int]:
        """
        统计每个表的匹配数量

        Args:
            pattern: 正则表达式模式
            tables: 搜索的表列表
            case_sensitive: 是否区分大小写

        Returns:
            {表名: 匹配数量} 字典
        """
        tables = tables or self.default_tables
        results = {}

        for table in tables:
            try:
                regex_flags = "" if case_sensitive else "i"
                sql = f"""
                    SELECT COUNT(*) as count
                    FROM {table}
                    WHERE content ~ $1
                """

                row = await self.db_pool.fetchrow(sql, pattern)
                results[table] = row["count"] if row else 0

            except Exception as e:
                logger.warning(f"表 {table} 统计失败: {e}")
                results[table] = 0

        return results
