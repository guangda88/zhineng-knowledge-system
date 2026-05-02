"""
BM25 关键词检索服务模块

内存安全设计：
- initialize(): 仅加载 doc_count + avg_doc_length，不加载词频字典
- IDF 按需查询: 从物化视图 mv_bm25_word_stats 获取，避免 2GB+ 内存占用
- search() 两阶段: 先用 GIN 索引 + sv_text 打分，再加载 top_k 内容
"""

import asyncio
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any
from typing import Counter as CounterType
from typing import Dict, List, Optional, Tuple

import asyncpg

logger = logging.getLogger(__name__)

_CUSTOM_DICT_PATH = Path(__file__).parent / "custom_dict.txt"
_SINGLE_CHAR_DOMAIN_WORDS = frozenset("仁义礼智信道德气心神精")
_TSVECTOR_WORD_RE = re.compile(r"'([^']+)':([0-9A-Za-z,]+)")
_CANDIDATE_CAP = 1000


class BM25Retriever:
    """BM25 关键词检索服务

    使用物化视图 mv_bm25_word_stats 按需查询 IDF，
    避免将 1170 万词加载到内存。

    initialize(): 秒级完成，仅查询 doc_count + avg_doc_length
    search(): GIN 预过滤 → sv_text 解析词频 → BM25 打分 → 加载 top_k 内容
    """

    def __init__(self, db_pool: asyncpg.Pool, k1: float = 1.2, b: float = 0.75):
        """
        初始化BM25检索器

        Args:
            db_pool: 数据库连接池
            k1: 词频饱和参数
            b: 长度归一化参数
        """
        self.db_pool = db_pool
        self.k1 = k1
        self.b = b
        self.doc_count: int = 0
        self.avg_doc_length: float = 0.0
        self._jieba_ready = False
        self._tbv_has_search_vector: Optional[bool] = None

    def _ensure_jieba(self) -> None:
        if self._jieba_ready:
            return
        try:
            import jieba

            jieba.setLogLevel(logging.WARNING)
            if _CUSTOM_DICT_PATH.exists():
                jieba.load_userdict(str(_CUSTOM_DICT_PATH))
            self._jieba_ready = True
        except ImportError:
            pass

    def _segment_query(self, query: str) -> str:
        self._ensure_jieba()
        try:
            import jieba

            words = jieba.lcut(query)
            return " ".join(
                w.strip()
                for w in words
                if w.strip() and (len(w.strip()) > 1 or w.strip() in _SINGLE_CHAR_DOMAIN_WORDS)
            )
        except ImportError:
            return query

    async def initialize(self) -> None:
        """初始化 BM25 统计信息

        仅查询文档数和平均长度（毫秒级）。
        IDF 通过物化视图 mv_bm25_word_stats 按需查询，不加载到内存。
        如果物化视图不存在则自动创建（首次约 30 秒）。
        """
        async with self.db_pool.acquire() as conn:
            await self._ensure_materialized_view(conn)

            self.doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")

            avg_len = await conn.fetchval("SELECT AVG(LENGTH(content)) FROM documents")
            self.avg_doc_length = float(avg_len) if avg_len else 100.0

        logger.info(
            f"BM25索引初始化完成: {self.doc_count}个文档, " f"平均长度={self.avg_doc_length:.1f}"
        )

    async def _ensure_materialized_view(self, conn: asyncpg.Connection) -> None:
        """确保物化视图存在，不存在则创建"""
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_bm25_word_stats')"
        )
        if not exists:
            logger.info("创建 mv_bm25_word_stats 物化视图（首次约 30 秒）...")
            await conn.execute(
                """
                CREATE MATERIALIZED VIEW mv_bm25_word_stats AS
                SELECT word, ndoc
                FROM ts_stat('SELECT search_vector FROM documents')
                WHERE ndoc >= 2
                """
            )
            await conn.execute(
                "CREATE UNIQUE INDEX idx_mv_bm25_word_stats ON mv_bm25_word_stats(word)"
            )
            logger.info("mv_bm25_word_stats 物化视图创建完成")

    async def refresh_stats(self) -> None:
        """刷新物化视图（文档变更后调用）"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_bm25_word_stats")
        logger.info("mv_bm25_word_stats 物化视图已刷新")

    async def _get_idf_map(self, conn: asyncpg.Connection, words: List[str]) -> Dict[str, float]:
        """从物化视图按需查询 IDF

        Args:
            conn: 数据库连接
            words: 查询词列表

        Returns:
            {word: idf_value} 字典，仅包含物化视图中存在的词
        """
        rows = await conn.fetch(
            "SELECT word, ndoc FROM mv_bm25_word_stats WHERE word = ANY($1)", words
        )
        result = {}
        for r in rows:
            df = r["ndoc"]
            result[r["word"]] = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
        return result

    @staticmethod
    def _parse_tsvector(sv_text: str) -> Tuple[CounterType[str], int]:
        """从 tsvector 文本表示解析词频

        Args:
            sv_text: tsvector::text 输出，格式如 "'word1':1,3 'word2':2"

        Returns:
            (词频 Counter, 文档总位置数)
        """
        freqs: CounterType[str] = Counter()
        total = 0
        for match in _TSVECTOR_WORD_RE.finditer(sv_text):
            word = match.group(1)
            n = len(match.group(2).split(","))
            freqs[word] = n
            total += n
        return freqs, total

    def _score_with_idf(
        self,
        query_words: List[str],
        freqs: CounterType[str],
        idf_map: Dict[str, float],
        doc_length: int,
    ) -> float:
        """使用按需 IDF 和预计算词频计算 BM25 分数

        Args:
            query_words: 查询词列表
            freqs: 文档词频统计（从 tsvector 解析）
            idf_map: 查询词的 IDF 值（从物化视图查询）
            doc_length: 文档长度（字符数）

        Returns:
            BM25 分数
        """
        score = 0.0
        for word in query_words:
            idf = idf_map.get(word)
            if idf is None:
                continue

            tf = freqs.get(word, 0)
            if tf == 0:
                continue

            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
            score += idf * (numerator / denominator)

        return score

    async def search(
        self, query: str, category: Optional[str] = None, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """BM25 关键词搜索（SQL-side scoring + parallel content load）

        Phase 1: Build tsquery, get IDF map
        Phase 2: SQL-side ts_rank scoring across 4 tables in parallel
        Phase 3: Load content for top_k candidates only

        Args:
            query: 查询文本
            category: 分类筛选
            top_k: 返回数量

        Returns:
            检索结果列表
        """
        if self.doc_count == 0:
            await self.initialize()

        segmented = self._segment_query(query)
        if not segmented.strip():
            return []

        query_words = segmented.split()
        tsq = " & ".join(query_words)

        # Phase 1: Get IDF map (fast, single connection)
        async with self.db_pool.acquire() as conn:
            idf_map = await self._get_idf_map(conn, query_words)
        if not idf_map:
            return []

        # Compute IDF weight multiplier for ts_rank normalization
        avg_idf = sum(idf_map.values()) / len(idf_map) if idf_map else 1.0
        idf_weight = min(avg_idf, 4.0)

        # Check textbook_blocks_v2 search_vector availability (once)
        if self._tbv_has_search_vector is None:
            try:
                async with self.db_pool.acquire() as conn:
                    has_sv = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM textbook_blocks_v2 WHERE search_vector IS NOT NULL LIMIT 1)"
                    )
                    self._tbv_has_search_vector = bool(has_sv)
            except Exception:
                self._tbv_has_search_vector = False

        # Phase 2: SQL-side scoring with ts_rank across all 4 tables in parallel
        async def _score_docs():
            async with self.db_pool.acquire() as c:
                if category:
                    return await c.fetch(
                        """
                        SELECT id, ts_rank_cd(search_vector, query) * $3 AS score
                        FROM documents, plainto_tsquery('simple', $1) query
                        WHERE category = $2
                          AND search_vector @@ query
                          AND length(content) > 100
                          AND content NOT LIKE '来源: %%'
                          AND content NOT LIKE '文件名: %%'
                        ORDER BY score DESC
                        LIMIT $4
                        """,
                        segmented,
                        category,
                        idf_weight,
                        top_k,
                    )
                return await c.fetch(
                    """
                    SELECT id, ts_rank_cd(search_vector, query) * $2 AS score
                    FROM documents, plainto_tsquery('simple', $1) query
                    WHERE search_vector @@ query
                      AND length(content) > 100
                      AND content NOT LIKE '来源: %%'
                      AND content NOT LIKE '文件名: %%'
                    ORDER BY score DESC
                    LIMIT $3
                    """,
                    segmented,
                    idf_weight,
                    top_k,
                )

        async def _score_gx():
            async with self.db_pool.acquire() as c:
                return await c.fetch(
                    """
                    SELECT gc.id, ts_rank_cd(gc.search_vector, query) * $2 AS score
                    FROM guoxue_content gc, plainto_tsquery('simple', $1) query
                    WHERE gc.search_vector @@ query
                      AND gc.body_length > 100
                    ORDER BY score DESC
                    LIMIT $3
                    """,
                    segmented,
                    idf_weight,
                    top_k,
                )

        async def _score_tbv():
            if not self._tbv_has_search_vector:
                return []
            async with self.db_pool.acquire() as c:
                return await c.fetch(
                    """
                    SELECT tbv.id, ts_rank_cd(tbv.search_vector, query) * $2 AS score
                    FROM textbook_blocks_v2 tbv, plainto_tsquery('simple', $1) query
                    WHERE tbv.search_vector @@ query
                      AND length(tbv.content) > 20
                    ORDER BY score DESC
                    LIMIT $3
                    """,
                    segmented,
                    idf_weight,
                    top_k,
                )

        async def _score_chunks():
            async with self.db_pool.acquire() as c:
                return await c.fetch(
                    """
                    SELECT dc.id, ts_rank_cd(dc.search_vector, query) * $2 AS score
                    FROM doc_chunks dc, plainto_tsquery('simple', $1) query
                    WHERE dc.search_vector @@ query
                    ORDER BY score DESC
                    LIMIT $3
                    """,
                    segmented,
                    idf_weight,
                    top_k,
                )

        doc_scored, gx_scored, tbv_scored, chunk_scored = await asyncio.gather(
            _score_docs(),
            _score_gx(),
            _score_tbv(),
            _score_chunks(),
            return_exceptions=True,
        )

        doc_scored = doc_scored if isinstance(doc_scored, list) else []
        gx_scored = gx_scored if isinstance(gx_scored, list) else []
        tbv_scored = tbv_scored if isinstance(tbv_scored, list) else []
        chunk_scored = chunk_scored if isinstance(chunk_scored, list) else []

        # Merge all scored results and sort globally
        all_scored: List[Tuple[int, float, str]] = []
        for r in doc_scored:
            all_scored.append((r["id"], float(r["score"]), "documents"))
        for r in gx_scored:
            all_scored.append((r["id"], float(r["score"]), "guoxue_content"))
        for r in tbv_scored:
            all_scored.append((r["id"], float(r["score"]), "textbook_blocks_v2"))
        for r in chunk_scored:
            all_scored.append((r["id"], float(r["score"]), "doc_chunks"))

        if not all_scored:
            return []

        all_scored.sort(key=lambda x: x[1], reverse=True)
        all_scored = all_scored[:top_k]
        top_scores = {(s[0], s[2]): s[1] for s in all_scored}

        doc_ids = [s[0] for s in all_scored if s[2] == "documents"]
        gx_ids = [s[0] for s in all_scored if s[2] == "guoxue_content"]
        tbv_ids = [s[0] for s in all_scored if s[2] == "textbook_blocks_v2"]
        chunk_ids = [s[0] for s in all_scored if s[2] == "doc_chunks"]

        # Phase 3: Load content for top_k in parallel

        async def _load_doc_content():
            if not doc_ids:
                return []
            async with self.db_pool.acquire() as c:
                return [
                    (r, "documents")
                    for r in await c.fetch(
                        "SELECT id, title, content, category FROM documents WHERE id = ANY($1)",
                        doc_ids,
                    )
                ]

        async def _load_gx_content():
            if not gx_ids:
                return []
            async with self.db_pool.acquire() as c:
                rows = await c.fetch(
                    """
                    SELECT gc.id, COALESCE(gb.title, '古籍') as title,
                           gc.body as content, '古籍' as category
                    FROM guoxue_content gc
                    LEFT JOIN guoxue_books gb ON gc.book_id = gb.book_id
                    WHERE gc.id = ANY($1)
                    """,
                    gx_ids,
                )
                return [(r, "guoxue_content") for r in rows]

        async def _load_tbv_content():
            if not tbv_ids:
                return []
            async with self.db_pool.acquire() as c:
                rows = await c.fetch(
                    """
                    SELECT tbv.id, tbv.content,
                           COALESCE(tn.name, '教材') as title,
                           '教材' as category,
                           tn.path
                    FROM textbook_blocks_v2 tbv
                    LEFT JOIN textbook_nodes tn ON tbv.node_id = tn.id
                    WHERE tbv.id = ANY($1)
                    """,
                    tbv_ids,
                )
                results = []
                for r in rows:
                    title = r["title"]
                    if r.get("path"):
                        title = f"{r['path']} → {title}"
                    results.append(
                        (
                            {
                                "id": r["id"],
                                "title": title,
                                "content": r["content"],
                                "category": r["category"],
                            },
                            "textbook_blocks_v2",
                        )
                    )
                return results

        async def _load_chunk_content():
            if not chunk_ids:
                return []
            async with self.db_pool.acquire() as c:
                rows = await c.fetch(
                    """
                    SELECT dc.id, dc.content, d.title, d.category, dc.doc_id
                    FROM doc_chunks dc
                    JOIN documents d ON d.id = dc.doc_id
                    WHERE dc.id = ANY($1)
                    """,
                    chunk_ids,
                )
                return [(r, "doc_chunks") for r in rows]

        content_row_sets = await asyncio.gather(
            _load_doc_content(),
            _load_gx_content(),
            _load_tbv_content(),
            _load_chunk_content(),
            return_exceptions=True,
        )

        content_rows = []
        for crs in content_row_sets:
            if isinstance(crs, list):
                content_rows.extend(crs)

        results = []
        for row, source in content_rows:
            score_key = (row["id"], source)
            results.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "category": row["category"],
                    "score": top_scores.get(score_key, 0),
                    "method": "bm25",
                    "source_table": source,
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(
            f"BM25搜索: query='{query}', docs={len(doc_scored)}, guoxue={len(gx_scored)}, "
            f"blocks={len(tbv_scored)}, chunks={len(chunk_scored)}, found={len(results)}"
        )
        return results
