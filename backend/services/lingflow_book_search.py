"""LingFlow 书目统一搜索服务

提供跨 books / sys_books / guoxue_books 的统一搜索能力：
- 多源联合搜索
- 智能结果合并与排序
- 分类/朝代/来源筛选
- 向量语义推荐增强
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class LingFlowBookSearchService:
    """LingFlow 书目统一搜索服务"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def unified_search(
        self,
        query: str,
        category: Optional[str] = None,
        dynasty: Optional[str] = None,
        author: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """统一搜索 — 同时检索 books、sys_books、guoxue_books

        Args:
            query: 搜索关键词
            category: 分类（气功/中医/儒家）
            dynasty: 朝代
            author: 作者
            source: 数据源标识
            page: 页码
            size: 每页数量

        Returns:
            统一搜索结果
        """
        keyword = query.strip() if query else ""
        if not keyword and not category and not dynasty and not author:
            return {"total": 0, "page": page, "size": size, "results": [], "sources": {}}

        results: List[Dict[str, Any]] = []
        source_counts: Dict[str, int] = {}

        books_results = await self._search_books(keyword, category, dynasty, author, size)
        results.extend(books_results)
        source_counts["books"] = len(books_results)

        sysbooks_results = await self._search_sys_books(keyword, category, source, size)
        results.extend(sysbooks_results)
        source_counts["sys_books"] = len(sysbooks_results)

        guoxue_results = await self._search_guoxue_books(keyword, size)
        results.extend(guoxue_results)
        source_counts["guoxue_books"] = len(guoxue_results)

        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        offset = (page - 1) * size
        total = len(results)
        results = results[offset : offset + size]

        return {
            "total": total,
            "page": page,
            "size": size,
            "results": results,
            "sources": source_counts,
        }

    async def _search_books(
        self,
        keyword: str,
        category: Optional[str],
        dynasty: Optional[str],
        author: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """搜索 books 表（结构化书籍）"""
        conditions = []
        params: list = []
        idx = 1

        if keyword:
            conditions.append(
                f"(b.title ILIKE ${idx} OR b.author ILIKE ${idx} " f"OR b.description ILIKE ${idx})"
            )
            params.append(f"%{keyword}%")
            idx += 1

        if category:
            conditions.append(f"b.category = ${idx}")
            params.append(category)
            idx += 1

        if dynasty:
            conditions.append(f"b.dynasty ILIKE ${idx}")
            params.append(f"%{dynasty}%")
            idx += 1

        if author:
            conditions.append(f"b.author ILIKE ${idx}")
            params.append(f"%{author}%")
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        try:
            title_param_idx = None
            if keyword:
                title_param_idx = 1

            order_expr = "b.view_count DESC, b.created_at DESC"
            if title_param_idx:
                order_expr = (
                    f"CASE WHEN b.title ILIKE ${title_param_idx} THEN 0 ELSE 1 END, {order_expr}"
                )

            rows = await self.pool.fetch(
                f"""
                SELECT b.id, b.title, b.author, b.category, b.dynasty,
                       b.year, b.language, b.description,
                       b.has_content, b.total_chars, b.view_count,
                       b.source_id
                FROM books b
                {where}
                ORDER BY {order_expr}
                LIMIT ${idx}
                """,
                *params,
                timeout=15,
            )

            return [
                {
                    "source": "books",
                    "id": r["id"],
                    "title": r["title"],
                    "author": r["author"],
                    "category": r["category"],
                    "dynasty": r["dynasty"],
                    "year": r["year"],
                    "description": r["description"],
                    "has_content": r["has_content"],
                    "total_chars": r["total_chars"],
                    "view_count": r["view_count"],
                    "relevance": 1.0,
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"books 搜索失败: {e}")
            return []

    async def _search_sys_books(
        self,
        keyword: str,
        category: Optional[str],
        source: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """搜索 sys_books 表（300万+ 书目记录）"""
        if not keyword:
            return []

        conditions = ["(s.filename ILIKE $1 OR s.path ILIKE $1)"]
        params: list = [f"%{keyword}%"]
        idx = 2

        if source:
            conditions.append(f"s.source = ${idx}")
            params.append(source)
            idx += 1

        if category:
            conditions.append(f"s.domain = ${idx}")
            params.append(category)
            idx += 1

        where = " AND ".join(conditions)
        params.append(limit)

        try:
            rows = await self.pool.fetch(
                f"""
                SELECT s.id, s.filename, s.path, s.source, s.domain,
                       s.subcategory, s.extension, s.size,
                       s.author, s.category AS file_category
                FROM sys_books s
                WHERE {where}
                ORDER BY s.filename
                LIMIT ${idx}
                """,
                *params,
                timeout=15,
            )

            return [
                {
                    "source": "sys_books",
                    "id": r["id"],
                    "title": r["filename"],
                    "path": r["path"],
                    "source_name": r["source"],
                    "domain": r["domain"],
                    "subcategory": r["subcategory"],
                    "extension": r["extension"],
                    "size": r["size"],
                    "author": r["author"],
                    "relevance": 0.8,
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"sys_books 搜索失败: {e}")
            return []

    async def _search_guoxue_books(
        self,
        keyword: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """搜索 guoxue_books 表（国学经典 109 部）"""
        if not keyword:
            return []

        try:
            rows = await self.pool.fetch(
                """
                SELECT book_id, title, description, content_count, total_chars,
                       GREATEST(
                           similarity(title, $1),
                           similarity(COALESCE(description, ''), $1)
                       ) AS sim_score
                FROM guoxue_books
                WHERE title % $1 OR description % $1
                ORDER BY sim_score DESC
                LIMIT $2
                """,
                keyword,
                limit,
                timeout=15,
            )

            return [
                {
                    "source": "guoxue_books",
                    "id": r["book_id"],
                    "title": r["title"],
                    "description": r["description"],
                    "content_count": r["content_count"],
                    "total_chars": r["total_chars"],
                    "relevance": round(float(r["sim_score"]), 4),
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"guoxue_books 搜索失败: {e}")
            return []

    async def search_books_fulltext(
        self,
        query: str,
        book_id: Optional[int] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """在 book_chapters 中进行全文搜索

        Args:
            query: 搜索关键词
            book_id: 限定书籍ID
            page: 页码
            size: 每页数量

        Returns:
            全文搜索结果
        """
        keyword = query.strip()
        if not keyword:
            return {"total": 0, "page": page, "size": size, "results": []}

        conditions = ["bc.content ILIKE $1"]
        params: list = [f"%{keyword}%"]
        idx = 2

        if book_id is not None:
            conditions.append(f"bc.book_id = ${idx}")
            params.append(book_id)
            idx += 1

        where = " AND ".join(conditions)
        offset = (page - 1) * size
        params.extend([size, offset])

        try:
            rows = await self.pool.fetch(
                f"""
                SELECT bc.id, bc.book_id, bc.chapter_num, bc.title,
                       bc.content, bc.char_count,
                       b.title AS book_title, b.author AS book_author,
                       position($1 in bc.content) AS match_pos
                FROM book_chapters bc
                JOIN books b ON b.id = bc.book_id
                WHERE {where}
                ORDER BY match_pos, bc.chapter_num
                LIMIT ${idx} OFFSET ${idx + 1}
                """,
                *params,
                timeout=30,
            )

            results = []
            for r in rows:
                snippet = self._extract_snippet(r["content"], keyword, 300)
                results.append(
                    {
                        "id": r["id"],
                        "book_id": r["book_id"],
                        "book_title": r["book_title"],
                        "book_author": r["book_author"],
                        "chapter_num": r["chapter_num"],
                        "chapter_title": r["title"],
                        "snippet": snippet,
                        "char_count": r["char_count"],
                        "relevance": round(1.0 / max(r["match_pos"], 1), 4),
                    }
                )

            return {
                "total": len(results) if len(results) < size and page == 1 else len(results),
                "page": page,
                "size": size,
                "results": results,
            }
        except Exception as e:
            logger.error(f"book_chapters 全文搜索失败: {e}")
            return {"total": 0, "page": page, "size": size, "results": []}

    def _extract_snippet(self, content: str, keyword: str, max_len: int = 300) -> str:
        """从内容中提取包含关键词的片段"""
        if not content:
            return ""

        pos = content.find(keyword)
        if pos == -1:
            return content[:max_len] + "..." if len(content) > max_len else content

        start = max(0, pos - max_len // 3)
        end = min(len(content), start + max_len)

        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet.replace(keyword, f"**{keyword}**", 1)
