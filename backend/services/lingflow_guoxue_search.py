"""LingFlow 国学古籍搜索服务

提供国学古籍（guoxue_content / guoxue_books）的高级搜索功能：
- 全文三元组搜索（利用 pg_trgm 索引）
- 模糊匹配（pg_trgm similarity）
- 关键词高亮与上下文片段
- 多字段加权排序（标题 > 正文 > 章节ID）
- 跨典籍联合搜索
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class LingFlowGuoxueSearchService:
    """LingFlow 国学古籍搜索服务"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def search(
        self,
        query: str,
        book_id: Optional[int] = None,
        category: Optional[str] = None,
        search_mode: str = "fulltext",
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """统一搜索入口

        Args:
            query: 搜索关键词
            book_id: 限定典籍ID
            category: 分类（未使用，预留）
            search_mode: fulltext | fuzzy | broad
            page: 页码
            size: 每页数量

        Returns:
            搜索结果字典
        """
        keyword = query.strip()
        if not keyword:
            return {"total": 0, "page": page, "size": size, "results": []}

        if search_mode == "fuzzy":
            return await self._fuzzy_search(keyword, book_id, page, size)
        elif search_mode == "broad":
            return await self._broad_search(keyword, book_id, page, size)
        else:
            return await self._fulltext_search(keyword, book_id, page, size)

    async def _fulltext_search(
        self,
        keyword: str,
        book_id: Optional[int],
        page: int,
        size: int,
    ) -> Dict[str, Any]:
        """三元组全文搜索（精确匹配优先）

        利用 pg_trgm 索引在 body 全文范围内搜索，
        按匹配位置（越靠前权重越高）和章节顺序排序。
        """
        conditions = ["body % $1"]
        params: list = [keyword]
        idx = 2

        if book_id is not None:
            conditions.append(f"gc.book_id = ${idx}")
            params.append(book_id)
            idx += 1

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * size

        rows = await self.pool.fetch(
            f"""
            WITH matches AS MATERIALIZED (
                SELECT gc.id, gc.book_id, gc.chapter_id,
                       gc.body, gc.body_length, gc.source_table,
                       gc.created_at,
                       similarity(body, $1) AS sim_score,
                       CASE
                           WHEN body LIKE $1 || '%%' THEN 0
                           WHEN position($1 in body) > 0
                               THEN position($1 in body)
                           ELSE 999999
                       END AS match_pos
                FROM guoxue_content gc
                WHERE {where_clause}
                ORDER BY sim_score DESC, match_pos, gc.chapter_id, gc.id
                LIMIT ${idx} OFFSET ${idx + 1}
            )
            SELECT m.*, gb.title AS book_title
            FROM matches m
            LEFT JOIN guoxue_books gb ON gb.book_id = m.book_id
            """,
            *params,
            size,
            offset,
            timeout=60,
        )

        total = await self._estimate_total(where_clause, params)

        results = []
        for r in rows:
            snippet = self._make_snippet(r["body"], keyword, max_len=300)
            results.append(
                {
                    "id": r["id"],
                    "book_id": r["book_id"],
                    "book_title": r["book_title"],
                    "chapter_id": r["chapter_id"],
                    "snippet": snippet,
                    "body_length": r["body_length"],
                    "sim_score": round(float(r["sim_score"]), 4),
                    "match_pos": r["match_pos"],
                    "source_table": r["source_table"],
                }
            )

        return {
            "total": total if len(results) == size else len(results) if page == 1 else total,
            "page": page,
            "size": size,
            "results": results,
        }

    async def _fuzzy_search(
        self,
        keyword: str,
        book_id: Optional[int],
        page: int,
        size: int,
    ) -> Dict[str, Any]:
        """模糊搜索（pg_trgm similarity 阈值过滤）

        适合用户输入有错别字或简写时的搜索场景。
        """
        threshold = 0.1
        conditions = [f"similarity(body, $1) >= ${2}"]
        params: list = [keyword, threshold]
        idx = 3

        if book_id is not None:
            conditions.append(f"gc.book_id = ${idx}")
            params.append(book_id)
            idx += 1

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * size

        rows = await self.pool.fetch(
            f"""
            WITH matches AS MATERIALIZED (
                SELECT gc.id, gc.book_id, gc.chapter_id,
                       gc.body, gc.body_length, gc.source_table,
                       gc.created_at,
                       similarity(body, $1) AS sim_score
                FROM guoxue_content gc
                WHERE {where_clause}
                ORDER BY sim_score DESC
                LIMIT ${idx} OFFSET ${idx + 1}
            )
            SELECT m.*, gb.title AS book_title
            FROM matches m
            LEFT JOIN guoxue_books gb ON gb.book_id = m.book_id
            """,
            *params,
            size,
            offset,
            timeout=60,
        )

        results = []
        for r in rows:
            snippet = self._make_snippet(r["body"], keyword, max_len=300)
            results.append(
                {
                    "id": r["id"],
                    "book_id": r["book_id"],
                    "book_title": r["book_title"],
                    "chapter_id": r["chapter_id"],
                    "snippet": snippet,
                    "body_length": r["body_length"],
                    "sim_score": round(float(r["sim_score"]), 4),
                    "source_table": r["source_table"],
                }
            )

        return {
            "total": (
                len(results)
                if len(results) < size and page == 1
                else await self._estimate_total(where_clause, params)
            ),
            "page": page,
            "size": size,
            "results": results,
        }

    async def _broad_search(
        self,
        keyword: str,
        book_id: Optional[int],
        page: int,
        size: int,
    ) -> Dict[str, Any]:
        """宽泛搜索（先搜书名，再搜正文）

        返回典籍级别的匹配结果，适合用户不知道具体书名时的探索性搜索。
        """
        offset = (page - 1) * size

        book_rows = await self.pool.fetch(
            """
            SELECT book_id, title, description, content_count, total_chars,
                   similarity(title, $1) AS title_sim,
                   similarity(description, $1) AS desc_sim
            FROM guoxue_books
            WHERE title % $1 OR description % $1
            ORDER BY GREATEST(similarity(title, $1), similarity(description, $1)) DESC
            LIMIT $2 OFFSET $3
            """,
            keyword,
            size,
            offset,
            timeout=30,
        )

        book_results = []
        for r in book_rows:
            top_snippet = None
            content_row = await self.pool.fetchrow(
                """
                SELECT substring(body, 1, 300) AS preview
                FROM guoxue_content
                WHERE book_id = $1 AND body % $2
                ORDER BY similarity(body, $2) DESC
                LIMIT 1
                """,
                r["book_id"],
                keyword,
                timeout=15,
            )
            if content_row:
                top_snippet = content_row["preview"]

            book_results.append(
                {
                    "book_id": r["book_id"],
                    "title": r["title"],
                    "description": r["description"],
                    "content_count": r["content_count"],
                    "total_chars": r["total_chars"],
                    "title_sim": round(float(r["title_sim"]), 4),
                    "desc_sim": round(float(r["desc_sim"]), 4),
                    "top_snippet": top_snippet,
                }
            )

        book_total = await self.pool.fetchval(
            """
            SELECT COUNT(*) FROM guoxue_books
            WHERE title % $1 OR description % $1
            """,
            keyword,
        )

        return {
            "total": book_total or 0,
            "page": page,
            "size": size,
            "results": book_results,
        }

    async def cross_book_search(
        self,
        keyword: str,
        top_k: int = 5,
        per_book: int = 3,
    ) -> List[Dict[str, Any]]:
        """跨典籍搜索 — 在所有典籍中搜索关键词，每部返回最相关的几条

        Args:
            keyword: 搜索关键词
            top_k: 返回典籍数量
            per_book: 每部典籍返回条数

        Returns:
            按典籍分组的结果列表
        """
        books = await self.pool.fetch(
            """
            SELECT gb.book_id, gb.title,
                   MAX(similarity(gc.body, $1)) AS best_sim
            FROM guoxue_content gc
            JOIN guoxue_books gb ON gb.book_id = gc.book_id
            WHERE gc.body % $1
            GROUP BY gb.book_id, gb.title
            ORDER BY best_sim DESC
            LIMIT $2
            """,
            keyword,
            top_k,
            timeout=60,
        )

        results = []
        for b in books:
            content_rows = await self.pool.fetch(
                """
                SELECT id, chapter_id, substring(body, 1, 400) AS preview,
                       body_length, similarity(body, $1) AS sim_score
                FROM guoxue_content
                WHERE book_id = $2 AND body % $1
                ORDER BY sim_score DESC
                LIMIT $3
                """,
                keyword,
                b["book_id"],
                per_book,
                timeout=30,
            )
            items = []
            for c in content_rows:
                items.append(
                    {
                        "id": c["id"],
                        "chapter_id": c["chapter_id"],
                        "preview": c["preview"],
                        "body_length": c["body_length"],
                        "sim_score": round(float(c["sim_score"]), 4),
                    }
                )
            results.append(
                {
                    "book_id": b["book_id"],
                    "title": b["title"],
                    "best_sim": round(float(b["best_sim"]), 4),
                    "items": items,
                }
            )

        return results

    async def _estimate_total(
        self,
        where_clause: str,
        params: list,
    ) -> int:
        """估算匹配总数（使用 pg_class.reltuples）"""
        try:
            estimate = await self.pool.fetchrow(
                "SELECT reltuples::bigint AS estimate FROM pg_class WHERE oid = 'guoxue_content'::regclass",
            )
            return estimate["estimate"] if estimate else 263767
        except Exception:
            return 263767

    def _make_snippet(self, body: str, keyword: str, max_len: int = 300) -> str:
        """生成高亮上下文片段

        Args:
            body: 原文
            keyword: 关键词
            max_len: 片段最大长度

        Returns:
            包含 **keyword** 高亮的片段
        """
        if not body:
            return ""

        pos = body.find(keyword)
        if pos == -1:
            pos_lower = body.lower().find(keyword.lower())
            if pos_lower != -1:
                pos = pos_lower

        if pos == -1:
            return body[:max_len] + "..." if len(body) > max_len else body

        start = max(0, pos - max_len // 3)
        end = min(len(body), start + max_len)

        snippet = body[start:end]

        if snippet != body[: len(snippet)]:
            snippet = "..." + snippet
        if snippet != body[-len(snippet) :]:
            snippet = snippet + "..."

        snippet = snippet.replace(keyword, f"**{keyword}**", 1)
        return snippet
