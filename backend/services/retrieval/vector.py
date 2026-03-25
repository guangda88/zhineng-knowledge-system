"""
向量检索服务模块
遵循开发规则：异步优先、类型注解、错误处理
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
import asyncpg
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


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
        embedding_api_url: str = "http://localhost:8000/embed",
        embedding_dim: int = 1024
    ):
        """
        初始化向量检索器

        Args:
            db_pool: 数据库连接池
            embedding_api_url: 嵌入服务API地址
            embedding_dim: 向量维度
        """
        self.db_pool = db_pool
        self.embedding_api_url = embedding_api_url
        self.embedding_dim = embedding_dim
        self._http_client: Optional[httpx.AsyncClient] = None
        self._owner = False  # 标记是否由当前实例创建客户端

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端（延迟初始化）"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
            self._owner = True
        return self._http_client

    async def close(self) -> None:
        """关闭HTTP客户端连接"""
        if self._http_client and self._owner:
            await self._http_client.aclose()
            self._http_client = None
            self._owner = False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口，确保资源释放"""
        await self.close()
        return False
    
    async def embed_text(self, text: str) -> List[float]:
        """
        生成文本嵌入向量
        
        Args:
            text: 输入文本
        
        Returns:
            嵌入向量
        """
        # TODO: 集成实际的BGE嵌入服务
        # 目前使用简单哈希模拟（生产环境需替换）
        import hashlib
        
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        hash_bytes = hash_obj.digest()
        
        # 扩展到1024维
        vector = []
        for i in range(self.embedding_dim):
            byte_idx = i % len(hash_bytes)
            val = (hash_bytes[byte_idx] / 255.0 - 0.5) * 2
            vector.append(val)
        
        # 归一化
        norm = sum(v * v for v in vector) ** 0.5
        vector = [v / norm for v in vector]
        
        return vector
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成嵌入向量
        
        Args:
            texts: 输入文本列表
        
        Returns:
            嵌入向量列表
        """
        tasks = [self.embed_text(text) for text in texts]
        return await asyncio.gather(*tasks)
    
    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 10,
        threshold: float = 0.0
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
        # 生成查询向量
        query_vector = await self.embed_text(query)
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"
        
        # 构建查询条件
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
        
        # 过滤低相似度结果
        results = []
        for row in rows:
            if row['similarity'] >= threshold:
                results.append({
                    'id': row['id'],
                    'title': row['title'],
                    'content': row['content'],
                    'category': row['category'],
                    'similarity': float(row['similarity']),
                    'method': 'vector'
                })
        
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
            # 获取文档内容
            row = await conn.fetchrow(
                "SELECT title, content FROM documents WHERE id = $1",
                doc_id
            )
            
            if not row:
                logger.warning(f"文档 {doc_id} 不存在")
                return False
            
            # 生成嵌入
            text = f"{row['title']}\n{row['content']}"
            embedding = await self.embed_text(text)
            vector_str = "[" + ",".join(map(str, embedding)) + "]"
            
            # 更新数据库
            await conn.execute(
                "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                vector_str, doc_id
            )
            
            logger.info(f"已更新文档 {doc_id} 的嵌入向量")
            return True
    
    async def update_all_embeddings(self, batch_size: int = 100) -> Dict[str, int]:
        """
        批量更新所有文档的嵌入向量
        
        Args:
            batch_size: 批处理大小
        
        Returns:
            统计信息
        """
        async with self.db_pool.acquire() as conn:
            # 获取没有向量的文档
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
            batch = rows[i:i + batch_size]
            
            for row in batch:
                try:
                    text = f"{row['title']}\n{row['content']}"
                    embedding = await self.embed_text(text)
                    vector_str = "[" + ",".join(map(str, embedding)) + "]"
                    
                    await self.db_pool.execute(
                        "UPDATE documents SET embedding = $1::vector WHERE id = $2",
                        vector_str, row['id']
                    )
                    updated += 1
                    
                except Exception as e:
                    logger.error(f"更新文档 {row['id']} 失败: {e}")
                    failed += 1
            
            logger.info(f"进度: {updated}/{total}")
        
        logger.info(f"嵌入向量更新完成: 成功={updated}, 失败={failed}")
        
        return {
            'total': total,
            'updated': updated,
            'failed': failed
        }
