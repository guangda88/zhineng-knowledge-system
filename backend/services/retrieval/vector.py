"""
向量检索服务模块
使用 BGE 嵌入模型 (本地 sentence-transformers) 和 pgvector 进行语义搜索
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

_MODEL_INSTANCE = None
_MODEL_DIM = 512
_MODEL_LOCK = asyncio.Lock()


async def _get_model():
    global _MODEL_INSTANCE, _MODEL_DIM
    if _MODEL_INSTANCE is not None:
        return _MODEL_INSTANCE

    async with _MODEL_LOCK:
        if _MODEL_INSTANCE is not None:
            return _MODEL_INSTANCE

        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
        logger.info(f"Loading local embedding model: {model_name}")

        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

        loop = asyncio.get_running_loop()

        def _load():
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name, device="cpu")
            return model

        _MODEL_INSTANCE = await loop.run_in_executor(None, _load)
        _MODEL_DIM = _MODEL_INSTANCE.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded: dim={_MODEL_DIM}")

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
        if self._model is None:
            self._model = await _get_model()
            self.embedding_dim = _MODEL_DIM
        return self._model

    async def close(self) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def embed_text(self, text: str) -> List[float]:
        """
        生成文本嵌入向量（使用本地 BGE 模型）

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        if not text or not text.strip():
            raise ValueError("输入文本不能为空")

        model = await self._ensure_model()
        loop = asyncio.get_event_loop()

        def _encode():
            return model.encode(text, normalize_embeddings=True).tolist()

        return await loop.run_in_executor(None, _encode)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        if not texts:
            raise ValueError("文本列表不能为空")

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        model = await self._ensure_model()
        loop = asyncio.get_event_loop()

        def _encode_batch():
            return model.encode(valid_texts, normalize_embeddings=True, batch_size=32).tolist()

        return await loop.run_in_executor(None, _encode_batch)

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        向量相似度搜索

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

        if category:
            sql = """
                SELECT id, title, content, category,
                       1 - (embedding <=> $1::vector) as similarity
                FROM documents
                WHERE category = $2 AND embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """
            params = [vector_str, category, top_k]
        else:
            sql = """
                SELECT id, title, content, category,
                       1 - (embedding <=> $1::vector) as similarity
                FROM documents
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """
            params = [vector_str, top_k]

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results = []
        for row in rows:
            if row["similarity"] >= threshold:
                results.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "content": row["content"],
                        "category": row["category"],
                        "similarity": float(row["similarity"]),
                        "method": "vector",
                    }
                )

        logger.info(f"向量搜索: query='{query}', found={len(results)}")
        return results

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
            rows = await conn.fetch("""SELECT id, title, content
                   FROM documents
                   WHERE embedding IS NULL
                   ORDER BY id""")

        total = len(rows)
        updated = 0
        failed = 0

        logger.info(f"开始更新 {total} 个文档的嵌入向量")

        for i in range(0, total, batch_size):
            batch = rows[i : i + batch_size]
            texts = [f"{row['title']}\n{row['content']}" for row in batch]

            try:
                embeddings = await self.embed_batch(texts)

                async with self.db_pool.acquire() as conn:
                    for row, embedding in zip(batch, embeddings):
                        try:
                            vector_str = "[" + ",".join(map(str, embedding)) + "]"
                            await conn.execute(
                                "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                                vector_str,
                                row["id"],
                            )
                            updated += 1
                        except Exception as e:
                            logger.error(f"更新文档 {row['id']} 失败: {e}")
                            failed += 1
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
