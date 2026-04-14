"""
BM25 关键词检索服务模块

内存安全设计：
- initialize(): 仅加载 doc_count + avg_doc_length，不加载词频字典
- IDF 按需查询: 从物化视图 mv_bm25_word_stats 获取，避免 2GB+ 内存占用
- search() 两阶段: 先用 GIN 索引 + sv_text 打分，再加载 top_k 内容
"""

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
_CANDIDATE_CAP = 5000


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
            await conn.execute("""
                CREATE MATERIALIZED VIEW mv_bm25_word_stats AS
                SELECT word, ndoc
                FROM ts_stat('SELECT search_vector FROM documents')
                WHERE ndoc >= 2
                """)
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
        """BM25 关键词搜索（两阶段，内存安全）

        Phase 1: GIN 索引预过滤候选 → 获取 id + sv_text + content_len（不含 content）
        Phase 2: Python 端 BM25 打分
        Phase 3: 仅加载 top_k 候选的 content

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

        async with self.db_pool.acquire() as conn:
            idf_map = await self._get_idf_map(conn, query_words)
            if not idf_map:
                return []

            if category:
                rows = await conn.fetch(
                    """
                    SELECT id, search_vector::text AS sv_text, length(content) AS content_len
                    FROM documents
                    WHERE category = $2
                      AND search_vector @@ plainto_tsquery('simple', $1)
                    LIMIT $3
                    """,
                    segmented,
                    category,
                    _CANDIDATE_CAP,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, search_vector::text AS sv_text, length(content) AS content_len
                    FROM documents
                    WHERE search_vector @@ plainto_tsquery('simple', $1)
                    LIMIT $2
                    """,
                    segmented,
                    _CANDIDATE_CAP,
                )

            scored: List[Tuple[int, float]] = []
            for row in rows:
                freqs, _ = self._parse_tsvector(row["sv_text"])
                doc_length = row["content_len"] or 1
                score = self._score_with_idf(query_words, freqs, idf_map, doc_length)
                if score > 0:
                    scored.append((row["id"], score))

            if not scored:
                return []

            scored.sort(key=lambda x: x[1], reverse=True)
            top_ids = [s[0] for s in scored[:top_k]]
            top_scores = {s[0]: s[1] for s in scored[:top_k]}

            content_rows = await conn.fetch(
                "SELECT id, title, content, category FROM documents WHERE id = ANY($1)",
                top_ids,
            )

        results = []
        for row in content_rows:
            results.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "category": row["category"],
                    "score": top_scores[row["id"]],
                    "method": "bm25",
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"BM25搜索: query='{query}', candidates={len(rows)}, found={len(results)}")
        return results
