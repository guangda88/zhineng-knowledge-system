"""LingFlow 国学古籍搜索服务

提供国学古籍（guoxue_content / guoxue_books）的高级搜索功能：
- jieba 预分词全文搜索（search_vector + GIN 索引）
- 模糊匹配（pg_trgm similarity）
- 语义向量搜索（pgvector + BGE embedding）
- Cross-encoder 精排（Reranker）
- 关键词高亮与上下文片段
- 多字段加权排序（标题 > 正文 > 章节ID）
- 跨典籍联合搜索
"""

import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logger = logging.getLogger(__name__)

_EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://embedding:8001")


class LingFlowGuoxueSearchService:
    """LingFlow 国学古籍搜索服务"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
        self._reranker = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def _get_reranker(self):
        if self._reranker is None:
            try:
                from backend.services.retrieval.reranker import create_reranker

                self._reranker = create_reranker()
            except ImportError:
                logger.info("sentence_transformers 不可用，跳过 reranker")
                self._reranker = None
        return self._reranker

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
        elif search_mode == "semantic":
            return await self._semantic_search(keyword, book_id, page, size)
        else:
            return await self._fulltext_search(keyword, book_id, page, size)

    _SINGLE_CHAR_DOMAIN_WORDS = frozenset("仁义礼智信道德气心神精")
    _jieba_ready = False

    def _segment_query(self, query: str) -> str:
        if not self._jieba_ready:
            try:
                from pathlib import Path

                import jieba

                jieba.setLogLevel(logging.WARNING)
                custom_dict = Path(__file__).parent / "retrieval" / "custom_dict.txt"
                if custom_dict.exists():
                    jieba.load_userdict(str(custom_dict))
                self._jieba_ready = True
            except ImportError:
                pass
        try:
            import jieba

            words = jieba.lcut(query)
            return " ".join(
                w.strip()
                for w in words
                if w.strip() and (len(w.strip()) > 1 or w.strip() in self._SINGLE_CHAR_DOMAIN_WORDS)
            )
        except ImportError:
            return query

    async def _fulltext_search(
        self,
        keyword: str,
        book_id: Optional[int],
        page: int,
        size: int,
    ) -> Dict[str, Any]:
        """jieba 预分词全文搜索（利用 search_vector GIN 索引）

        使用 jieba 分词后的 search_vector 列 + GIN 索引，
        比 pg_trgm 更快且中文召回率更高。
        """
        segmented = self._segment_query(keyword)
        if not segmented.strip():
            return {"total": 0, "page": page, "size": size, "results": []}

        conditions = ["gc.search_vector @@ plainto_tsquery('simple', $1)"]
        params: list = [segmented]
        idx = 2

        if book_id is not None:
            conditions.append(f"gc.book_id = ${idx}")
            params.append(book_id)
            idx += 1

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * size

        rows = await self.pool.fetch(
            f"""
            WITH ranked_ids AS MATERIALIZED (
                SELECT gc.id,
                       ts_rank(gc.search_vector, plainto_tsquery('simple', $1)) AS rank_score
                FROM guoxue_content gc
                WHERE {where_clause}
                LIMIT 5000
            )
            SELECT gc.id, gc.book_id, gc.chapter_id,
                   gc.body, gc.body_length, gc.source_table,
                   ri.rank_score,
                   gb.title AS book_title
            FROM (SELECT id, rank_score FROM ranked_ids
                  ORDER BY rank_score DESC
                  LIMIT ${idx} OFFSET ${idx + 1}) ri
            JOIN guoxue_content gc ON gc.id = ri.id
            LEFT JOIN guoxue_books gb ON gb.book_id = gc.book_id
            ORDER BY ri.rank_score DESC
            """,
            *params,
            size,
            offset,
            timeout=60,
        )

        total = await self._estimate_total(where_clause, params)

        results = []
        for r in rows:
            snippet = self._make_snippet(r["body"], keyword, max_len=300, segmented=segmented)
            results.append(
                {
                    "id": r["id"],
                    "book_id": r["book_id"],
                    "book_title": r["book_title"],
                    "chapter_id": r["chapter_id"],
                    "snippet": snippet,
                    "body_length": r["body_length"],
                    "sim_score": round(float(r["rank_score"]), 4),
                    "match_pos": 0,
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

    async def _semantic_search(
        self,
        keyword: str,
        book_id: Optional[int],
        page: int,
        size: int,
    ) -> Dict[str, Any]:
        """语义向量搜索 + Cross-encoder 精排

        使用 pgvector 向量相似度检索语义相关内容，
        再用 cross-encoder reranker 对 top-N 结果精排。
        当 embedding 列无数据时自动降级到 fulltext 模式。
        """
        try:
            client = await self._get_http_client()
            resp = await client.post(
                f"{_EMBEDDING_SERVICE_URL}/embed",
                json={"text": keyword, "normalize": True},
            )
            resp.raise_for_status()
            query_vec = resp.json()["embedding"]
        except Exception as e:
            logger.warning(f"Embedding 服务调用失败，降级到 fulltext: {e}")
            return await self._fulltext_search(keyword, book_id, page, size)

        vec_str = "[" + ",".join(map(str, query_vec)) + "]"

        has_embedding = await self.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM guoxue_content WHERE embedding IS NOT NULL LIMIT 1)"
        )
        if not has_embedding:
            logger.info("guoxue_content embedding 列无数据，降级到 fulltext 模式")
            return await self._fulltext_search(keyword, book_id, page, size)

        conditions = ["gc.embedding IS NOT NULL"]
        params: list = [vec_str]
        idx = 2

        if book_id is not None:
            conditions.append(f"gc.book_id = ${idx}")
            params.append(book_id)
            idx += 1

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * size
        fetch_size = min(size * 3, 60)

        rows = await self.pool.fetch(
            f"""
            SELECT gc.id, gc.book_id, gc.chapter_id,
                   gc.body, gc.body_length, gc.source_table,
                   1 - (gc.embedding <=> $1::vector) AS vec_score
            FROM guoxue_content gc
            WHERE {where_clause}
            ORDER BY gc.embedding <=> $1::vector
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            fetch_size,
            offset,
            timeout=30,
        )

        results = []
        for r in rows:
            snippet = self._make_snippet(r["body"], keyword, max_len=300)
            results.append(
                {
                    "id": r["id"],
                    "book_id": r["book_id"],
                    "book_title": None,
                    "chapter_id": r["chapter_id"],
                    "snippet": snippet,
                    "body_length": r["body_length"],
                    "sim_score": round(float(r["vec_score"]), 4),
                    "source_table": r["source_table"],
                    "content": r["body"][:500] if r["body"] else "",
                }
            )

        if results:
            book_ids = list(set(r["book_id"] for r in results))
            book_rows = await self.pool.fetch(
                "SELECT book_id, title FROM guoxue_books WHERE book_id = ANY($1)",
                book_ids,
            )
            book_map = {r["book_id"]: r["title"] for r in book_rows}
            for r in results:
                r["book_title"] = book_map.get(r["book_id"])

        if len(results) > 1:
            try:
                reranker = await self._get_reranker()
                results = await reranker.rerank(keyword, results, top_k=size)
            except Exception as e:
                logger.warning(f"Reranker 精排失败，使用向量排序: {e}")

        results = results[:size]

        for r in results:
            r.pop("content", None)

        return {
            "total": len(results) if page == 1 else fetch_size,
            "page": page,
            "size": size,
            "results": results,
        }

    async def _estimate_total(
        self,
        where_clause: str,
        params: list,
    ) -> int:
        """估算匹配总数"""
        try:
            count = await self.pool.fetchval(
                f"SELECT count(*) FROM guoxue_content gc WHERE {where_clause}",
                *params,
                timeout=30,
            )
            return count or 0
        except Exception:
            estimate = await self.pool.fetchval(
                "SELECT reltuples::bigint FROM pg_class WHERE oid = 'guoxue_content'::regclass"
            )
            return estimate or 263767

    def _make_snippet(
        self, body: str, keyword: str, max_len: int = 300, segmented: str = ""
    ) -> str:
        """生成高亮上下文片段

        Args:
            body: 原文
            keyword: 用户原始查询
            max_len: 片段最大长度
            segmented: jieba 分词后的空格分隔词列表

        Returns:
            包含 **keyword** 高亮的片段
        """
        if not body:
            return ""

        highlight_words = [keyword]
        if segmented:
            highlight_words = [w for w in segmented.split() if w] or [keyword]

        best_pos = -1
        for hw in sorted(highlight_words, key=len, reverse=True):
            pos = body.find(hw)
            if pos != -1:
                best_pos = pos
                break
            pos_lower = body.lower().find(hw.lower())
            if pos_lower != -1:
                best_pos = pos_lower
                break

        if best_pos == -1:
            return body[:max_len] + "..." if len(body) > max_len else body

        start = max(0, best_pos - max_len // 3)
        end = min(len(body), start + max_len)

        snippet = body[start:end]

        if snippet != body[: len(snippet)]:
            snippet = "..." + snippet
        if snippet != body[-len(snippet) :]:
            snippet = snippet + "..."

        for hw in sorted(highlight_words, key=len, reverse=True):
            snippet = snippet.replace(hw, f"**{hw}**")
        return snippet
