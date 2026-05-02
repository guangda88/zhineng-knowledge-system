"""
文档摄取服务

负责将解析后的文档内容摄取到数据库中，包括生成嵌入向量、存储元数据等。
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg

from backend.services.document_parser import DocumentParser

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    """
    文档摄取服务

    将解析后的文档摄取到数据库中，自动生成嵌入向量。
    """

    def __init__(self, db_pool: asyncpg.Pool, parser: DocumentParser):
        """
        初始化文档摄取服务

        Args:
            db_pool: 数据库连接池
            parser: 文档解析器
        """
        self.db_pool = db_pool
        self.parser = parser

        # 向量检索器（延迟初始化）
        self._vector_retriever = None

    async def ingest_file(
        self, file_path: str, category: str, title: Optional[str] = None, overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        摄取文件到数据库

        Args:
            file_path: 文件路径
            category: 文档分类
            title: 文档标题（可选，默认从文件或元数据提取）
            overwrite: 是否覆盖已存在的文档

        Returns:
            摄取结果: {
                "status": "success" | "error",
                "doc_id": Optional[int],
                "message": str,
                "error": Optional[str]
            }
        """
        try:
            # 1. 解析文档
            parsed = await self.parser.parse_file(file_path, extract_metadata=True)

            if parsed["status"] == "error":
                return {
                    "status": "error",
                    "message": f"文档解析失败: {parsed['error']}",
                    "error": parsed["error"],
                }

            content = parsed["content"]
            metadata = parsed.get("metadata", {})

            # 2. 验证内容
            if not content or len(content.strip()) < 10:
                return {
                    "status": "error",
                    "message": "文档内容为空或过短",
                    "error": "Empty content",
                }

            # 3. 提取标题
            doc_title = title or metadata.get("title") or os.path.basename(file_path)

            # 4. 生成嵌入向量
            logger.info(f"生成嵌入向量: {file_path}")
            vector_retriever = await self._get_vector_retriever()
            embedding = await vector_retriever.embed_text(content)

            # 5. 插入或更新数据库
            if overwrite:
                doc_id = await self._update_document(
                    file_path, doc_title, content, category, embedding, metadata
                )
            else:
                doc_id = await self._insert_document(
                    file_path, doc_title, content, category, embedding, metadata
                )

            logger.info(f"文档摄取成功: {file_path} -> ID {doc_id}")

            return {
                "status": "success",
                "doc_id": doc_id,
                "message": f"文档摄取成功，ID: {doc_id}",
                "metadata": {
                    "title": doc_title,
                    "category": category,
                    "content_length": len(content),
                    "metadata": metadata,
                },
            }

        except Exception as e:
            logger.error(f"文档摄取失败 {file_path}: {e}", exc_info=True)
            return {"status": "error", "message": f"文档摄取失败: {e}", "error": str(e)}

    async def ingest_batch(
        self, file_paths: List[str], category: str, overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        批量摄取文件

        Args:
            file_paths: 文件路径列表
            category: 文档分类
            overwrite: 是否覆盖已存在的文档

        Returns:
            批量摄取结果
        """
        results = {"total": len(file_paths), "successful": 0, "failed": 0, "errors": []}

        logger.info(f"开始批量摄取 {len(file_paths)} 个文件")

        for file_path in file_paths:
            result = await self.ingest_file(file_path, category, overwrite=overwrite)

            if result["status"] == "success":
                results["successful"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(
                    {"file": file_path, "error": result.get("error", "Unknown error")}
                )

        logger.info(f"批量摄取完成: 成功 {results['successful']}, 失败 {results['failed']}")

        return results

    async def _get_vector_retriever(self):
        """
        获取向量检索器实例（延迟初始化）

        Returns:
            VectorRetriever 实例
        """
        if self._vector_retriever is None:
            from backend.services.retrieval.vector import VectorRetriever

            self._vector_retriever = VectorRetriever(self.db_pool)

        return self._vector_retriever

    async def _insert_document(
        self,
        file_path: str,
        title: str,
        content: str,
        category: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> int:
        """
        插入新文档到数据库

        Args:
            file_path: 文件路径
            title: 文档标题
            content: 文档内容
            category: 文档分类
            embedding: 嵌入向量
            metadata: 元数据

        Returns:
            文档ID
        """
        # 检查是否已存在
        existing = await self.db_pool.fetchval(
            "SELECT id FROM documents WHERE source_file = $1", file_path
        )

        if existing:
            raise ValueError(f"文档已存在: {file_path} (ID: {existing})")

        # 插入文档
        sql = """
            INSERT INTO documents (title, content, category, embedding, source_file, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """

        doc_id = await self.db_pool.fetchval(
            sql,
            title,
            content,
            category,
            str(embedding),
            file_path,
            json.dumps(metadata, ensure_ascii=False),
        )

        return doc_id

    async def _update_document(
        self,
        file_path: str,
        title: str,
        content: str,
        category: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> int:
        """
        更新已存在的文档

        Args:
            file_path: 文件路径
            title: 文档标题
            content: 文档内容
            category: 文档分类
            embedding: 嵌入向量
            metadata: 元数据

        Returns:
            文档ID
        """
        sql = """
            INSERT INTO documents (title, content, category, embedding, source_file, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (source_file) DO UPDATE
            SET title = EXCLUDED.title,
                content = EXCLUDED.content,
                category = EXCLUDED.category,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id
        """

        doc_id = await self.db_pool.fetchval(
            sql,
            title,
            content,
            category,
            str(embedding),
            file_path,
            json.dumps(metadata, ensure_ascii=False),
        )

        return doc_id

    async def remove_document(self, file_path: str) -> bool:
        """
        从数据库删除文档

        Args:
            file_path: 文件路径

        Returns:
            是否成功删除
        """
        try:
            sql = "DELETE FROM documents WHERE source_file = $1"
            result = await self.db_pool.execute(sql, file_path)

            # 检查是否有删除的行
            deleted = result.split(" ")[-1] if result else "0"
            success = deleted != "0"

            if success:
                logger.info(f"文档已删除: {file_path}")

            return success

        except Exception as e:
            logger.error(f"删除文档失败 {file_path}: {e}", exc_info=True)
            return False

    async def get_document_by_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        根据文件路径获取文档信息

        Args:
            file_path: 文件路径

        Returns:
            文档信息或 None
        """
        sql = """
            SELECT id, title, content, category, source_file, metadata, updated_at
            FROM documents
            WHERE source_file = $1
        """

        row = await self.db_pool.fetchrow(sql, file_path)

        if row:
            return {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "category": row["category"],
                "source_file": row["source_file"],
                "metadata": row.get("metadata"),
                "updated_at": row["updated_at"],
            }

        return None

    async def sync_directory(
        self,
        directory: str,
        category: str,
        overwrite: bool = False,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        同步目录中的所有文档

        Args:
            directory: 目录路径
            category: 文档分类
            overwrite: 是否覆盖已存在的文档
            extensions: 文件扩展名列表（默认支持 PDF, DOCX, TXT, MD）

        Returns:
            同步结果
        """
        if not os.path.exists(directory):
            return {
                "status": "error",
                "message": f"目录不存在: {directory}",
                "total": 0,
                "successful": 0,
                "failed": 0,
            }

        # 默认支持的扩展名
        if extensions is None:
            extensions = [".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"]

        # 扫描目录
        file_paths = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    file_path = os.path.join(root, file)
                    file_paths.append(file_path)

        logger.info(f"发现 {len(file_paths)} 个待同步文件")

        # 批量摄取
        return await self.ingest_batch(file_paths, category, overwrite=overwrite)
