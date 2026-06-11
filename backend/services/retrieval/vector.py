"""
向量检索服务模块
使用 BGE 嵌入模型 (本地 sentence-transformers) 和 pgvector 进行语义搜索
当本地模型不可用时，降级到远程 EMBEDDING_SERVICE_URL
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logger = logging.getLogger(__name__)

DOMAIN_KEYWORDS = {
    "儒家": ["论语", "孟子", "大学", "中庸", "礼记", "诗经", "尚书", "孝经", "荀子", "朱子", "阳明", "传习录", "儒", "春秋繁露", "商君书", "周礼", "潜夫论", "读通鉴论", "文献通考", "书目答问", "廿二史"],
    "佛家": ["佛", "法华", "华严", "楞严", "金刚", "般若", "禅", "坛经", "维摩", "净土", "心经", "菩萨", "僧", "弘明集", "佛国记", "续藏经", "陀罗尼", "曼拏罗", "藏经", "高贤传", "大藏经", "嘉兴大藏经", "七千佛", "六甲祈", "神咒经", "六祖", "赞佛"],
    "道家": ["老子", "庄子", "道德经", "列子", "文子", "抱朴子", "道藏", "黄庭", "悟真", "参同", "内丹", "三十六水法", "一贯天机", "太上老君", "上清", "召魔伏", "奇门", "风水", "青囊", "三极至命"],
    "中医": ["黄帝内经", "本草", "伤寒", "金匮", "难经", "脉经", "针灸", "千金", "温病", "方剂", "张景岳", "景岳", "丹溪", "颅囟经", "神农本草", "濒湖脉学", "千金翼方"],
    "气功": ["气功", "混元", "捧气", "形神庄", "五元庄", "站桩", "导引", "吐纳", "丹田", "组场", "经络", "气血"],
    "武术": ["太极", "八卦", "形意", "少林", "武当", "咏春", "拳", "剑", "刀", "枪", "棍", "三命通会", "七杀星"],
    "哲学": ["哲学", "逻辑", "存在", "认识论", "伦理", "美学", "辩证", "易", "周易", "易经", "春秋"],
    "科学": ["科学", "物理", "化学", "数学", "生物", "天文", "地理", "系统论"],
    "心理学": ["心理", "意识", "认知", "情绪", "人格", "行为", "精神"],
}


def infer_domain(text: str) -> str:
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return domain
    return "古籍"

_MODEL_INSTANCE = None
_MODEL_DIM = 512
_MODEL_LOCK = asyncio.Lock()
_USE_REMOTE = False
_EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "")
_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


async def _get_http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=15)
    return _HTTP_CLIENT


async def _remote_embed(text: str) -> List[float]:
    """调用远程嵌入服务"""
    client = await _get_http_client()
    url = f"{_EMBEDDING_SERVICE_URL}/embed"
    resp = await client.post(url, json={"text": text})
    if resp.status_code == 200:
        return resp.json()["embedding"]
    raise RuntimeError(f"Remote embedding service error {resp.status_code}: {resp.text}")


async def _remote_embed_batch(texts: List[str]) -> List[List[float]]:
    """调用远程嵌入服务（批量）"""
    client = await _get_http_client()
    url = f"{_EMBEDDING_SERVICE_URL}/embed_batch"
    resp = await client.post(url, json={"texts": texts}, timeout=30)
    if resp.status_code == 200:
        return resp.json()["embeddings"]
    raise RuntimeError(f"Remote embedding service error {resp.status_code}: {resp.text}")


async def _get_model():
    global _MODEL_INSTANCE, _MODEL_DIM, _USE_REMOTE
    if _MODEL_INSTANCE is not None:
        return _MODEL_INSTANCE

    if _USE_REMOTE:
        return None

    async with _MODEL_LOCK:
        if _MODEL_INSTANCE is not None:
            return _MODEL_INSTANCE

        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

        try:
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_HUB_OFFLINE", "1")

            loop = asyncio.get_running_loop()

            def _load():
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(model_name, device="cpu")
                return model

            _MODEL_INSTANCE = await loop.run_in_executor(None, _load)
            _MODEL_DIM = _MODEL_INSTANCE.get_sentence_embedding_dimension()
            logger.info(f"Local embedding model loaded: dim={_MODEL_DIM}")
        except ImportError:
            if _EMBEDDING_SERVICE_URL:
                _USE_REMOTE = True
                logger.info(
                    f"sentence_transformers not available, "
                    f"using remote embedding service: {_EMBEDDING_SERVICE_URL}"
                )
            else:
                raise
        except Exception as e:
            if _EMBEDDING_SERVICE_URL:
                _USE_REMOTE = True
                logger.warning(
                    f"Local model load failed ({e}), "
                    f"falling back to remote embedding service: {_EMBEDDING_SERVICE_URL}"
                )
            else:
                raise

    return _MODEL_INSTANCE


def get_embedding_dim() -> int:
    return _MODEL_DIM


class VectorRetriever:
    """
    向量检索服务

    使用 BGE 嵌入模型和 pgvector 进行语义搜索

    Example:
        async with VectorRetriever(pool) as retriever:
            results = await retriever.search("query")
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embedding_dim: int = 512,
    ):
        self.db_pool = db_pool
        self.embedding_dim = embedding_dim
        self._model = None

    async def _ensure_model(self):
        await _get_model()
        self._model = _MODEL_INSTANCE
        self.embedding_dim = _MODEL_DIM
        return _MODEL_INSTANCE

    async def close(self) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def embed_text(self, text: str) -> List[float]:
        """
        生成文本嵌入向量

        优先使用本地 BGE 模型，不可用时降级到远程嵌入服务
        """
        if not text or not text.strip():
            raise ValueError("输入文本不能为空")

        await _get_model()

        if _USE_REMOTE:
            return await _remote_embed(text)

        model = _MODEL_INSTANCE
        loop = asyncio.get_event_loop()

        def _encode():
            return model.encode(text, normalize_embeddings=True).tolist()

        return await loop.run_in_executor(None, _encode)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入向量"""
        if not texts:
            raise ValueError("文本列表不能为空")

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        await _get_model()

        if _USE_REMOTE:
            return await _remote_embed_batch(valid_texts)

        model = _MODEL_INSTANCE
        loop = asyncio.get_event_loop()

        def _encode_batch():
            return model.encode(valid_texts, normalize_embeddings=True, batch_size=64).tolist()

        return await loop.run_in_executor(None, _encode_batch)

    async def _search_textbook_blocks(
        self,
        query_vector: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """搜索 textbook_blocks_v2 分块（已有 64K+ 条带 embedding 的分块）"""
        sql = """
            SELECT tbv.id, tbv.content, tbv.node_id,
                   1 - (tbv.embedding <=> $1::vector) as similarity,
                   tn.name as node_title, tn.path as node_path
            FROM textbook_blocks_v2 tbv
            LEFT JOIN textbook_nodes tn ON tbv.node_id = tn.id
            WHERE tbv.embedding IS NOT NULL
                  AND length(tbv.content) > 20
            ORDER BY tbv.embedding <=> $1::vector
            LIMIT $2
        """
        rows = await self.db_pool.fetch(sql, query_vector, top_k)
        results = []
        for r in rows:
            title = r["node_title"] or "教材"
            if r["node_path"]:
                title = f"{r['node_path']} → {title}"
            combined_text = (title + " " + (r["content"] or ""))[:200]
            cat = infer_domain(combined_text)
            results.append(
                {
                    "id": f"tbv_{r['id']}",
                    "title": title,
                    "content": r["content"],
                    "category": cat,
                    "similarity": float(r["similarity"]),
                    "method": "vector",
                    "source_table": "textbook_blocks_v2",
                }
            )
        return results

    async def _search_doc_chunks(
        self,
        query_vector: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """搜索 doc_chunks 分块"""
        sql = """
            SELECT dc.id, dc.content, dc.doc_id,
                   1 - (dc.embedding <=> $1::vector) as similarity,
                   d.title as doc_title, d.category
            FROM doc_chunks dc
            JOIN documents d ON d.id = dc.doc_id
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> $1::vector
            LIMIT $2
        """
        rows = await self.db_pool.fetch(sql, query_vector, top_k)
        results = []
        for r in rows:
            results.append(
                {
                    "id": f"chunk_{r['id']}",
                    "title": r["doc_title"],
                    "content": r["content"],
                    "category": r["category"],
                    "similarity": float(r["similarity"]),
                    "method": "vector",
                    "source_table": "doc_chunks",
                    "doc_id": r["doc_id"],
                }
            )
        return results

    async def search_by_vector(
        self,
        vector_str: str,
        category: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """向量搜索（接受预计算的 vector string，跳过 embed 步骤）

        同时搜索 documents、guoxue_content、textbook_blocks_v2、doc_chunks 四张表，合并结果。
        """
        if category:
            doc_sql = """
                SELECT id, title, content, category,
                       1 - (embedding <=> $1::vector) as similarity,
                       'documents' as source_table
                FROM documents
                WHERE category = $2 AND embedding IS NOT NULL
                      AND length(content) > 100
                      AND content NOT LIKE '来源: %'
                      AND content NOT LIKE '文件名: %'
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """
            doc_params = [vector_str, category, top_k]
        else:
            doc_sql = """
                SELECT id, title, content, category,
                       1 - (embedding <=> $1::vector) as similarity,
                       'documents' as source_table
                FROM documents
                WHERE embedding IS NOT NULL
                      AND length(content) > 100
                      AND content NOT LIKE '来源: %'
                      AND content NOT LIKE '文件名: %'
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """
            doc_params = [vector_str, top_k]

        gx_sql = """
            SELECT gc.id, gc.body as content, gc.book_id,
                   1 - (gc.embedding <=> $1::vector) as similarity,
                   'guoxue_content' as source_table,
                   gb.title as book_title
            FROM guoxue_content gc
            LEFT JOIN guoxue_books gb ON gc.book_id = gb.book_id
            WHERE gc.embedding IS NOT NULL
                  AND body_length > 100
            ORDER BY gc.embedding <=> $1::vector
            LIMIT $2
        """
        gx_params = [vector_str, top_k]

        async def _fetch_doc():
            async with self.db_pool.acquire() as conn:
                return await conn.fetch(doc_sql, *doc_params)

        async def _fetch_gx():
            async with self.db_pool.acquire() as conn:
                return await conn.fetch(gx_sql, *gx_params)

        doc_rows_raw, gx_rows_raw, tbv_rows_raw, chunk_rows_raw = await asyncio.gather(
            _fetch_doc(),
            _fetch_gx(),
            self._search_textbook_blocks(vector_str, top_k),
            self._search_doc_chunks(vector_str, top_k),
            return_exceptions=True,
        )

        doc_rows = doc_rows_raw if isinstance(doc_rows_raw, list) else []
        gx_rows = gx_rows_raw if isinstance(gx_rows_raw, list) else []
        if isinstance(tbv_rows_raw, Exception):
            logger.warning(f"textbook_blocks_v2 搜索失败: {tbv_rows_raw}")
        if isinstance(chunk_rows_raw, Exception):
            logger.warning(f"doc_chunks 搜索失败: {chunk_rows_raw}")
        tbv_rows = tbv_rows_raw if isinstance(tbv_rows_raw, list) else []
        chunk_rows = chunk_rows_raw if isinstance(chunk_rows_raw, list) else []

        # Build normalized results
        normalized = []
        for r in doc_rows:
            normalized.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "content": r["content"],
                    "category": r["category"],
                    "similarity": float(r["similarity"]),
                    "source_table": r["source_table"],
                }
            )
        for r in gx_rows:
            book_title = r.get("book_title") or "古籍"
            normalized.append(
                {
                    "id": r["id"],
                    "title": book_title,
                    "content": r["content"],
                    "category": infer_domain(book_title),
                    "similarity": float(r["similarity"]),
                    "source_table": r["source_table"],
                }
            )
        normalized.extend(tbv_rows)
        normalized.extend(chunk_rows)

        # Table-aware merge: each source table gets a minimum allocation
        # to prevent high-similarity tables (e.g. guoxue_content) from
        # crowding out lower-similarity but more relevant tables (e.g. doc_chunks).
        per_table_limit = max(top_k // 4, 2)

        by_table: dict[str, list] = {}
        for row in normalized:
            tbl = row.get("source_table", "unknown")
            by_table.setdefault(tbl, []).append(row)
        for tbl in by_table:
            by_table[tbl].sort(key=lambda r: r["similarity"], reverse=True)

        selected: list[dict] = []
        selected_ids: set = set()
        for table_rows in by_table.values():
            for row in table_rows[:per_table_limit]:
                rid = row["id"]
                if rid not in selected_ids:
                    selected.append(row)
                    selected_ids.add(rid)

        normalized.sort(key=lambda r: r["similarity"], reverse=True)
        remaining = top_k - len(selected)
        if remaining > 0:
            for row in normalized:
                if remaining <= 0:
                    break
                if row["id"] not in selected_ids:
                    selected.append(row)
                    selected_ids.add(row["id"])
                    remaining -= 1

        selected.sort(key=lambda r: r["similarity"], reverse=True)

        results = []
        for row in selected:
            if row["similarity"] >= threshold:
                results.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "content": row["content"],
                        "category": row["category"],
                        "similarity": row["similarity"],
                        "method": "vector",
                        "source_table": row.get("source_table", ""),
                    }
                )
        return results

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

        同时搜索 documents、guoxue_content、textbook_blocks_v2、doc_chunks 四张表，合并结果。

        Args:
            query: 查询文本
            category: 分类筛选
            top_k: 返回数量
            threshold: 相似度阈值

        Returns:
            检索结果列表
        """
        query_vector = await self.embed_text(query)
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"
        return await self.search_by_vector(vector_str, category, top_k, threshold)

    async def update_embedding(self, doc_id: int) -> bool:
        """
        更新文档的嵌入向量

        Args:
            doc_id: 文档ID

        Returns:
            是否成功
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT title, content FROM documents WHERE id = $1",
                doc_id,
            )

            if not row:
                logger.warning(f"文档 {doc_id} 不存在")
                return False

            text = f"{row['title']}\n{row['content']}"
            embedding = await self.embed_text(text)
            vector_str = "[" + ",".join(map(str, embedding)) + "]"

            await conn.execute(
                "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                vector_str,
                doc_id,
            )

            logger.info(f"已更新文档 {doc_id} 的嵌入向量")
            return True

    async def update_all_embeddings(self, batch_size: int = 32) -> Dict[str, int]:
        """
        批量更新所有文档的嵌入向量

        Args:
            batch_size: 批处理大小

        Returns:
            统计信息
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, title, content
                   FROM documents
                   WHERE embedding IS NULL
                   ORDER BY id"""
            )

        total = len(rows)
        updated = 0
        failed = 0

        logger.info(f"开始更新 {total} 个文档的嵌入向量")

        for i in range(0, total, batch_size):
            batch = rows[i : i + batch_size]
            texts = [f"{row['title']}\n{row['content']}" for row in batch]

            try:
                embeddings = await self.embed_batch(texts)

                # Batch update using UNNEST to reduce N+1 queries
                async with self.db_pool.acquire() as conn:
                    values_list = []
                    params = []
                    param_idx = 1
                    for row, embedding in zip(batch, embeddings):
                        vector_str = "[" + ",".join(map(str, embedding)) + "]"
                        values_list.append(f"(${param_idx}::int, ${param_idx+1}::vector)")
                        params.extend([row["id"], vector_str])
                        param_idx += 2

                    values_sql = ", ".join([f"({v})" for v in values_list])
                    await conn.execute(
                        f"""
                        UPDATE documents AS d
                        SET embedding = v.embedding
                        FROM (VALUES {values_sql}) AS v(id, embedding)
                        WHERE d.id = v.id
                        """,
                        *params,
                    )
                    updated += len(batch)
            except Exception as e:
                logger.error(f"批处理嵌入失败 (batch {i}): {e}")
                failed += len(batch)

            logger.info(f"进度: {updated}/{total}")

        logger.info(f"嵌入向量更新完成: 成功={updated}, 失败={failed}")

        return {
            "total": total,
            "updated": updated,
            "failed": failed,
        }
