"""内容提取管道服务

从 sys_books 表中的文件提取文本内容，支持多种格式：
- TXT: 直接读取
- PDF: PyMuPDF / pdfplumber
- DOC/DOCX: python-docx
- DJVU: djvulibre
"""

import asyncio
import hashlib
import logging
import os
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class ExtractionMethod(str, Enum):
    TXT_DIRECT = "txt_direct"
    PYMUPDF = "pymupdf"
    PDFPLUMBER = "pdfplumber"
    PYTHON_DOCX = "python-docx"
    DJVU = "djvu"
    OCR = "ocr"
    ASR = "asr"
    SKIPPED = "skipped"


class ContentExtractor:
    """内容提取器

    从文件系统中的文件提取文本内容。
    """

    # 支持的文件格式映射
    FORMAT_HANDLERS = {
        ".txt": "_extract_txt",
        ".md": "_extract_txt",
        ".text": "_extract_txt",
        ".pdf": "_extract_pdf",
        ".doc": "_extract_doc",
        ".docx": "_extract_doc",
        ".djvu": "_extract_djvu",
    }

    def __init__(self, base_paths: Optional[Dict[str, str]] = None):
        """初始化提取器

        Args:
            base_paths: 源名称到本地路径的映射
                {"Ammiao": "/mnt/data/ammiao", "Z-disk": "/mnt/data/z-disk"}
        """
        self.base_paths = base_paths or {}

    def resolve_file_path(self, source: str, path: str, filename: str) -> Optional[str]:
        """将 sys_books 的 Windows 路径转换为本地路径

        Args:
            source: 数据源名称
            path: Windows 路径 (e.g., "K:\\中医")
            filename: 文件名

        Returns:
            本地文件路径，如果不存在返回 None
        """
        if source in self.base_paths:
            base = self.base_paths[source]
            # Convert Windows path separators
            rel_path = path.replace("\\", "/").replace(":", "")
            # Remove leading slash
            rel_path = rel_path.lstrip("/")
            local_path = os.path.join(base, rel_path, filename)
            if os.path.exists(local_path):
                return local_path

        return None

    async def extract(self, file_path: str, extension: str) -> Dict[str, Any]:
        """提取文件内容

        Args:
            file_path: 本地文件路径
            extension: 文件扩展名

        Returns:
            {"content": str, "method": str, "char_count": int, ...}
        """
        ext = extension.lower() if extension else ""
        if not ext.startswith("."):
            ext = "." + ext

        handler_name = self.FORMAT_HANDLERS.get(ext)

        if handler_name:
            handler = getattr(self, handler_name)
            return await handler(file_path)

        return {
            "content": "",
            "method": ExtractionMethod.SKIPPED,
            "char_count": 0,
            "chinese_char_count": 0,
            "error": f"Unsupported format: {ext}",
        }

    async def _extract_txt(self, file_path: str) -> Dict[str, Any]:
        """提取 TXT 文件"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_txt_sync, file_path)

    def _extract_txt_sync(self, file_path: str) -> Dict[str, Any]:
        content = ""
        for encoding in ["utf-8", "gbk", "gb2312", "gb18030"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if not content:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

        return self._build_result(content, ExtractionMethod.TXT_DIRECT)

    async def _extract_pdf(self, file_path: str) -> Dict[str, Any]:
        """提取 PDF 文件，优先 PyMuPDF，降级 pdfplumber"""
        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(None, self._extract_pdf_pymupdf, file_path)
            if result["char_count"] > 100:
                return result
        except Exception as e:
            logger.debug(f"PyMuPDF failed for {file_path}: {e}")

        try:
            result = await loop.run_in_executor(None, self._extract_pdf_pdfplumber, file_path)
            return result
        except Exception as e:
            logger.debug(f"pdfplumber failed for {file_path}: {e}")

        return {
            "content": "",
            "method": ExtractionMethod.PYMUPDF,
            "char_count": 0,
            "chinese_char_count": 0,
            "error": "All PDF extraction methods failed",
        }

    def _extract_pdf_pymupdf(self, file_path: str) -> Dict[str, Any]:
        import fitz

        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        content = "\n".join(pages)
        return self._build_result(content, ExtractionMethod.PYMUPDF)

    def _extract_pdf_pdfplumber(self, file_path: str) -> Dict[str, Any]:
        import pdfplumber

        pages = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        content = "\n".join(pages)
        return self._build_result(content, ExtractionMethod.PDFPLUMBER)

    async def _extract_doc(self, file_path: str) -> Dict[str, Any]:
        """提取 DOC/DOCX 文件"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_doc_sync, file_path)

    def _extract_doc_sync(self, file_path: str) -> Dict[str, Any]:
        from docx import Document

        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        content = "\n".join(paragraphs)
        return self._build_result(content, ExtractionMethod.PYTHON_DOCX)

    async def _extract_djvu(self, file_path: str) -> Dict[str, Any]:
        """提取 DJVU 文件 (通过 djvulibre 命令行)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_djvu_sync, file_path)

    def _extract_djvu_sync(self, file_path: str) -> Dict[str, Any]:
        import subprocess

        result = subprocess.run(
            ["djvutxt", file_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        content = result.stdout
        if not content.strip():
            return {
                "content": "",
                "method": ExtractionMethod.DJVU,
                "char_count": 0,
                "chinese_char_count": 0,
                "error": "djvutxt returned empty output",
            }
        return self._build_result(content, ExtractionMethod.DJVU)

    def _build_result(self, content: str, method: ExtractionMethod) -> Dict[str, Any]:
        """构建提取结果"""
        char_count = len(content)
        chinese_char_count = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
        content_hash = hashlib.sha256(content.encode("utf-8"), usedforsecurity=False).hexdigest()

        quality = 0.0
        if char_count > 0:
            chinese_ratio = chinese_char_count / char_count
            if chinese_ratio > 0.3:
                quality = min(chinese_ratio * 100, 100)
            elif char_count > 500:
                quality = 30.0

        return {
            "content": content,
            "method": method,
            "char_count": char_count,
            "chinese_char_count": chinese_char_count,
            "content_hash": content_hash,
            "quality_score": round(quality, 1),
        }


class BatchExtractionService:
    """批量内容提取服务

    从 sys_books 表读取待提取的文件，调用 ContentExtractor 提取内容，
    将结果写入 sys_book_contents 表。
    """

    def __init__(self, db_url: str, base_paths: Optional[Dict[str, str]] = None):
        self.db_url = db_url
        self.extractor = ContentExtractor(base_paths)
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url, min_size=2, max_size=6, command_timeout=600, timeout=10
            )
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def get_extraction_stats(self) -> Dict[str, Any]:
        """获取提取统计"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            status_counts = await conn.fetch(
                """
                SELECT extraction_status, COUNT(*) as cnt
                FROM sys_books
                GROUP BY extraction_status
                ORDER BY cnt DESC
            """
            )

            by_extension = await conn.fetch(
                """
                SELECT extension, extraction_status, COUNT(*) as cnt
                FROM sys_books
                WHERE extraction_status != 'pending'
                GROUP BY extension, extraction_status
                ORDER BY cnt DESC
                LIMIT 20
            """
            )

            contents_count = await conn.fetchval("SELECT COUNT(*) FROM sys_book_contents")

            return {
                "by_status": {r["extraction_status"]: r["cnt"] for r in status_counts},
                "by_extension": [
                    {
                        "extension": r["extension"],
                        "status": r["extraction_status"],
                        "count": r["cnt"],
                    }
                    for r in by_extension
                ],
                "contents_total": contents_count,
            }

    async def extract_batch(
        self,
        extensions: Optional[List[str]] = None,
        domain: Optional[str] = None,
        limit: int = 1000,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """批量提取内容

        Args:
            extensions: 限制文件扩展名列表
            domain: 限制领域
            limit: 最大处理数量
            batch_size: 每批处理数量

        Returns:
            提取统计信息
        """
        pool = await self._get_pool()
        start_time = time.time()

        # Create task record
        async with pool.acquire() as conn:
            task_id = await conn.fetchval(
                """
                INSERT INTO extraction_tasks (task_type, status, total_items, config)
                VALUES ('batch_extract', 'running', $1, $2)
                RETURNING id
                """,
                limit,
                {"extensions": extensions, "domain": domain, "batch_size": batch_size},
            )

        stats = {
            "task_id": task_id,
            "total": 0,
            "extracted": 0,
            "skipped": 0,
            "failed": 0,
        }

        try:
            # Build query conditions
            conditions = ["extraction_status = 'pending'", "file_type = 'file'"]
            params: list = []
            idx = 1

            if extensions:
                ext_placeholders = ", ".join(f"${idx + i}" for i in range(len(extensions)))
                conditions.append(f"extension IN ({ext_placeholders})")
                params.extend(e.lower().lstrip(".") for e in extensions)
                idx += len(extensions)

            if domain:
                conditions.append(f"domain = ${idx}")
                params.append(domain)
                idx += 1

            where = " AND ".join(conditions)

            async with pool.acquire() as conn:
                # Get total count
                total = await conn.fetchval(
                    f"SELECT COUNT(*) FROM sys_books WHERE {where}",
                    *params,
                )
                stats["total"] = min(total, limit)

                # Process in batches
                offset = 0
                while offset < limit:
                    rows = await conn.fetch(
                        f"""
                        SELECT id, source, path, filename, extension, size
                        FROM sys_books
                        WHERE {where}
                        ORDER BY id
                        LIMIT ${idx} OFFSET ${idx + 1}
                        """,
                        *params,
                        batch_size,
                        offset,
                    )

                    if not rows:
                        break

                    for row in rows:
                        try:
                            file_path = self.extractor.resolve_file_path(
                                row["source"], row["path"], row["filename"]
                            )

                            if not file_path:
                                await conn.execute(
                                    """
                                    UPDATE sys_books
                                    SET extraction_status = 'skipped',
                                        extraction_error = 'File not found on local disk'
                                    WHERE id = $1
                                    """,
                                    row["id"],
                                )
                                stats["skipped"] += 1
                                continue

                            result = await self.extractor.extract(file_path, row["extension"])

                            if result["char_count"] > 50:
                                await self._save_extraction(conn, row["id"], result)
                                stats["extracted"] += 1
                            else:
                                await conn.execute(
                                    """
                                    UPDATE sys_books
                                    SET extraction_status = 'failed',
                                        extraction_error = $1,
                                        content_length = $2
                                    WHERE id = $3
                                    """,
                                    result.get("error", "Content too short"),
                                    result["char_count"],
                                    row["id"],
                                )
                                stats["failed"] += 1

                        except Exception as e:
                            logger.error(f"Error extracting book {row['id']}: {e}")
                            await conn.execute(
                                """
                                UPDATE sys_books
                                SET extraction_status = 'failed', extraction_error = $1
                                WHERE id = $2
                                """,
                                str(e)[:500],
                                row["id"],
                            )
                            stats["failed"] += 1

                    offset += len(rows)

                    if offset % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = offset / elapsed if elapsed > 0 else 0
                        logger.info(
                            f"  Progress: {offset:,}/{stats['total']:,} | "
                            f"extracted={stats['extracted']:,} | "
                            f"rate={rate:.0f}/s"
                        )

        finally:
            elapsed = time.time() - start_time
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE extraction_tasks
                    SET status = 'completed',
                        processed_items = $1,
                        failed_items = $2,
                        result_summary = $3,
                        completed_at = NOW()
                    WHERE id = $4
                    """,
                    stats["extracted"],
                    stats["failed"],
                    stats,
                    task_id,
                )

        stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"Batch extraction complete: {stats['extracted']:,} extracted, "
            f"{stats['skipped']:,} skipped, {stats['failed']:,} failed "
            f"in {elapsed:.1f}s"
        )
        return stats

    async def _save_extraction(
        self,
        conn: asyncpg.Connection,
        book_id: int,
        result: Dict[str, Any],
    ):
        """保存提取结果到数据库"""
        # Update sys_books
        await conn.execute(
            """
            UPDATE sys_books
            SET extraction_status = 'extracted',
                extracted_at = NOW(),
                content_hash = $1,
                content_length = $2
            WHERE id = $3
            """,
            result.get("content_hash"),
            result["char_count"],
            book_id,
        )

        # Insert into sys_book_contents
        await conn.execute(
            """
            INSERT INTO sys_book_contents (
                sys_book_id, content, char_count, chinese_char_count,
                content_hash, extraction_method, quality_score
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (sys_book_id) DO UPDATE SET
                content = $2, char_count = $3, chinese_char_count = $4,
                content_hash = $5, extraction_method = $6, quality_score = $7,
                updated_at = NOW()
            """,
            book_id,
            result["content"],
            result["char_count"],
            result["chinese_char_count"],
            result.get("content_hash"),
            result["method"],
            result.get("quality_score", 0),
        )


async def run_extraction(
    db_url: str,
    extensions: Optional[List[str]] = None,
    domain: Optional[str] = None,
    limit: int = 1000,
    base_paths: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """运行批量提取的便捷函数"""
    service = BatchExtractionService(db_url, base_paths)
    try:
        return await service.extract_batch(
            extensions=extensions,
            domain=domain,
            limit=limit,
        )
    finally:
        await service.close()
