"""书籍搜索服务

提供书籍的多维度搜索功能：
- 元数据搜索（标题、作者）
- 全文搜索（章节内容）
- 向量搜索（语义相似度）
"""

import logging
from typing import Any, Dict, List, Optional

from backend.services.retrieval.vector import VectorRetriever

logger = logging.getLogger(__name__)


class BookSearchService:
    """书籍搜索服务"""

    def __init__(self, db_pool):
        self.pool = db_pool

    async def search_metadata(
        self,
        query: str,
        category: Optional[str] = None,
        dynasty: Optional[str] = None,
        author: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """元数据搜索（标题、作者、描述）"""
        conditions = []
        params = []
        param_idx = 1

        if query and query.strip():
            query_str = query.strip()
            conditions.append(
                f"(title ILIKE ${param_idx} OR author ILIKE ${param_idx} OR description ILIKE ${param_idx})"
            )
            params.append(f"%{query_str}%")
            param_idx += 1

        if category:
            conditions.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1

        if dynasty:
            conditions.append(f"dynasty = ${param_idx}")
            params.append(dynasty)
            param_idx += 1

        if author:
            conditions.append(f"author ILIKE ${param_idx}")
            params.append(f"%{author}%")
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        order_clause = "ORDER BY view_count DESC, created_at DESC"
        if query and query.strip():
            order_clause = f"ORDER BY CASE WHEN title ILIKE ${param_idx} THEN 1 ELSE 2 END, view_count DESC, created_at DESC"
            params.append(f"{query.strip()}%")
            param_idx += 1

        async with self.pool.acquire() as conn:
            count_sql = f"SELECT count(*) as total FROM books {where_clause}"
            row = await conn.fetchrow(count_sql, *params[:param_idx - 1])
            total = row["total"] if row else 0

            offset = (page - 1) * size
            data_sql = (
                f"SELECT id, title, author, category, dynasty, year, language, "
                f"description, has_content, total_pages, total_chars, "
                f"view_count, source_id, created_at "
                f"FROM books {where_clause} {order_clause} "
                f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
            )
            params.extend([size, offset])
            rows = await conn.fetch(data_sql, *params)

        return {
            "total": total or 0,
            "page": page,
            "size": size,
            "results": [self._book_row_to_dict(r) for r in rows],
        }

    async def search_content(
        self, query: str, category: Optional[str] = None, page: int = 1, size: int = 20
    ) -> Dict[str, Any]:
        """全文内容搜索"""
        if not query or not query.strip():
            return {"total": 0, "page": page, "size": size, "results": []}

        conditions = ["bc.content ILIKE $1"]
        params: list = [f"%{query.strip()}%"]
        param_idx = 2

        if category:
            conditions.append(f"b.category = ${param_idx}")
            params.append(category)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}"

        async with self.pool.acquire() as conn:
            offset = (page - 1) * size
            sql = (
                f"SELECT bc.id, bc.book_id, bc.chapter_num, bc.title, "
                f"bc.content, bc.char_count, b.title as book_title "
                f"FROM book_chapters bc JOIN books b ON bc.book_id = b.id "
                f"{where_clause} "
                f"ORDER BY bc.char_count DESC "
                f"LIMIT ${param_idx} OFFSET ${param_idx + 1}"
            )
            params.extend([size, offset])
            rows = await conn.fetch(sql, *params)

        return {
            "total": len(rows),
            "page": page,
            "size": size,
            "results": [self._chapter_row_to_dict(r, query) for r in rows],
        }

    async def search_similar(
        self, book_id: int, top_k: int = 10, threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """基于向量的相似书籍推荐"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT embedding FROM books WHERE id = $1", book_id
            )
            if not row or not row["embedding"]:
                logger.warning(f"Book {book_id} not found or has no embedding")
                return []

            query_vector = row["embedding"]

        try:
            async with VectorRetriever(self.pool) as _retriever:
                vector_str = "[" + ",".join(map(str, query_vector)) + "]"

                sql = """
                    SELECT id, title, author, category, dynasty,
                           1 - (embedding <=> $1::vector) as similarity
                    FROM books
                    WHERE id != $2 AND embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """

                rows = await self.pool.fetch(sql, vector_str, book_id, top_k)

                results = []
                for r in rows:
                    if r["similarity"] >= threshold:
                        results.append(
                            {
                                "id": r["id"],
                                "title": r["title"],
                                "author": r["author"],
                                "category": r["category"],
                                "dynasty": r["dynasty"],
                                "similarity": float(r["similarity"]),
                            }
                        )

                logger.info(f"Found {len(results)} similar books for book {book_id}")
                return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def get_book_detail(self, book_id: int) -> Optional[Dict[str, Any]]:
        """获取书籍详情"""
        async with self.pool.acquire() as conn:
            book = await conn.fetchrow(
                "SELECT id, title, author, category, dynasty, year, language, "
                "description, has_content, total_pages, total_chars, "
                "view_count, source_id, created_at "
                "FROM books WHERE id = $1",
                book_id,
            )
            if not book:
                return None

            chapters = await conn.fetch(
                "SELECT id, chapter_num, title, level, char_count, order_position "
                "FROM book_chapters WHERE book_id = $1 "
                "ORDER BY order_position, chapter_num",
                book_id,
            )

            await conn.execute(
                "UPDATE books SET view_count = view_count + 1 WHERE id = $1",
                book_id,
            )

        result = self._book_row_to_dict(book)
        result["chapters"] = [
            {
                "id": ch["id"],
                "chapter_num": ch["chapter_num"],
                "title": ch["title"],
                "level": ch["level"],
                "char_count": ch["char_count"],
            }
            for ch in chapters
        ]
        result["view_count"] = book["view_count"] + 1
        return result

    async def get_chapter_content(self, book_id: int, chapter_id: int) -> Optional[Dict[str, Any]]:
        """获取章节内容"""
        async with self.pool.acquire() as conn:
            chapter = await conn.fetchrow(
                "SELECT id, book_id, chapter_num, title, content, char_count "
                "FROM book_chapters WHERE id = $1 AND book_id = $2",
                chapter_id,
                book_id,
            )

        if not chapter:
            return None

        return {
            "id": chapter["id"],
            "book_id": chapter["book_id"],
            "chapter_num": chapter["chapter_num"],
            "title": chapter["title"],
            "content": chapter["content"],
            "char_count": chapter["char_count"],
        }

    async def get_filters(self) -> Dict[str, Any]:
        """获取筛选选项"""
        async with self.pool.acquire() as conn:
            categories = [
                r["category"]
                for r in await conn.fetch(
                    "SELECT DISTINCT category FROM books "
                    "WHERE category IS NOT NULL ORDER BY category"
                )
            ]
            dynasties = [
                r["dynasty"]
                for r in await conn.fetch(
                    "SELECT DISTINCT dynasty FROM books "
                    "WHERE dynasty IS NOT NULL ORDER BY dynasty"
                )
            ]
            languages = [
                r["language"]
                for r in await conn.fetch(
                    "SELECT DISTINCT language FROM books "
                    "WHERE language IS NOT NULL ORDER BY language"
                )
            ]
            sources = await conn.fetch(
                "SELECT id, code, name_zh, name_en, description, category, "
                "supports_search, supports_fulltext, is_active "
                "FROM data_sources WHERE is_active = true ORDER BY sort_order"
            )

        return {
            "categories": categories,
            "dynasties": dynasties,
            "languages": languages,
            "sources": [
                {
                    "id": s["id"],
                    "code": s["code"],
                    "name_zh": s["name_zh"],
                    "name_en": s["name_en"],
                    "description": s["description"],
                    "category": s["category"],
                    "supports_search": s["supports_search"],
                    "supports_fulltext": s["supports_fulltext"],
                    "is_active": s["is_active"],
                }
                for s in sources
            ],
        }

    def _book_row_to_dict(self, row) -> Dict[str, Any]:
        """转换行为字典"""
        return {
            "id": row["id"],
            "title": row["title"],
            "author": row["author"],
            "category": row["category"],
            "dynasty": row["dynasty"],
            "year": row["year"],
            "language": row["language"],
            "description": row["description"],
            "has_content": row["has_content"],
            "total_pages": row["total_pages"],
            "total_chars": row["total_chars"],
            "view_count": row["view_count"],
            "source_id": row["source_id"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    def _chapter_row_to_dict(self, row, query: str = None) -> Dict[str, Any]:
        """转换章节行为字典（带高亮）"""
        preview = row["content"] or ""
        if query and query.strip():
            query_lower = query.strip().lower()
            content_lower = preview.lower()
            pos = content_lower.find(query_lower)

            if pos != -1:
                start = max(0, pos - 200)
                end = min(len(preview), pos + 200)
                preview = preview[start:end]
                if len(preview) > 0:
                    preview = preview.replace(
                        query.strip(), f"**{query.strip()}**", 1
                    )
            else:
                preview = preview[:400] + "..."

        return {
            "id": row["id"],
            "book_id": row["book_id"],
            "book_title": row["book_title"] if "book_title" in row.keys() else "",
            "chapter_num": row["chapter_num"],
            "title": row["title"],
            "preview": preview,
            "char_count": row["char_count"],
        }
