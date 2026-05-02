"""
文档解析器

支持多种文档格式的文本提取和元数据解析。
当前支持：PDF, DOCX, TXT, Markdown
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

# 文档解析库
try:
    from docx import Document

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx 未安装，DOCX 解析将不可用")

try:
    import PyPDF2

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("PyPDF2 未安装，PDF 解析将不可用")

# Apache Tika（可选）
try:
    import tika
    from tika import parser

    TIKA_AVAILABLE = True
except ImportError:
    TIKA_AVAILABLE = False
    logging.warning("tika 未安装，Apache Tika 解析将不可用")

logger = logging.getLogger(__name__)


class DocumentParser:
    """
    文档解析器

    支持多种文档格式的文本提取和元数据解析。
    优先使用专用库（PyPDF2, python-docx），备选 Apache Tika。
    """

    def __init__(
        self,
        tika_url: str = "http://localhost:9998",
        max_workers: int = 4,
        use_tika_fallback: bool = True,
    ):
        """
        初始化文档解析器

        Args:
            tika_url: Apache Tika Server URL
            max_workers: 线程池最大工作线程数
            use_tika_fallback: 是否在专用库失败时使用 Tika
        """
        self.tika_url = tika_url
        self.use_tika_fallback = use_tika_fallback
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        logger.info(
            f"文档解析器初始化 - DOCX: {DOCX_AVAILABLE}, PDF: {PDF_AVAILABLE}, Tika: {TIKA_AVAILABLE}"
        )

    async def parse_file(
        self, file_path: str, extract_metadata: bool = True, enable_ocr: bool = False
    ) -> Dict[str, Any]:
        """
        解析文档文件

        Args:
            file_path: 文件路径
            extract_metadata: 是否提取元数据
            enable_ocr: 是否启用 OCR（需要 Tika）

        Returns:
            解析结果: {
                "content": str,
                "metadata": Dict,
                "status": "success" | "error",
                "error": Optional[str]
            }
        """
        if not os.path.exists(file_path):
            return {
                "content": "",
                "metadata": {},
                "status": "error",
                "error": f"文件不存在: {file_path}",
            }

        # 检测文件格式
        file_format = self.detect_format(file_path)

        try:
            # 根据格式选择解析方法
            if file_format == "docx" and DOCX_AVAILABLE:
                result = await self._parse_docx(file_path, extract_metadata)
            elif file_format == "pdf" and PDF_AVAILABLE:
                result = await self._parse_pdf(file_path, extract_metadata)
            elif file_format in ["txt", "md", "text"]:
                result = await self._parse_text(file_path)
            elif TIKA_AVAILABLE and self.use_tika_fallback:
                # 使用 Apache Tika 作为备选
                result = await self._parse_with_tika(file_path, extract_metadata, enable_ocr)
            else:
                result = {
                    "content": "",
                    "metadata": {},
                    "status": "error",
                    "error": f"不支持的文档格式: {file_format}",
                }

            logger.info(
                f"文档解析成功: {file_path} ({file_format}) - {len(result['content'])} 字符"
            )
            return result

        except Exception as e:
            logger.error(f"文档解析失败 {file_path}: {e}", exc_info=True)
            return {"content": "", "metadata": {}, "status": "error", "error": str(e)}

    async def parse_batch(
        self, file_paths: List[str], extract_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量解析文档

        Args:
            file_paths: 文件路径列表
            extract_metadata: 是否提取元数据

        Returns:
            解析结果列表
        """
        tasks = [self.parse_file(fp, extract_metadata) for fp in file_paths]
        return await asyncio.gather(*tasks)

    def detect_format(self, file_path: str) -> str:
        """
        检测文档格式

        Args:
            file_path: 文件路径

        Returns:
            格式标识符（docx, pdf, txt, md, text, unknown）
        """
        ext = os.path.splitext(file_path)[1].lower()

        format_map = {
            ".pdf": "pdf",
            ".docx": "docx",
            ".doc": "docx",  # 尝试用 docx 解析
            ".txt": "txt",
            ".text": "text",
            ".md": "md",
            ".markdown": "md",
        }

        return format_map.get(ext, "unknown")

    async def _parse_docx(self, file_path: str, extract_metadata: bool = True) -> Dict[str, Any]:
        """
        解析 DOCX 文件

        Args:
            file_path: 文件路径
            extract_metadata: 是否提取元数据

        Returns:
            解析结果
        """
        loop = asyncio.get_event_loop()

        def _parse():
            doc = Document(file_path)

            # 提取文本
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            content = "\n".join(paragraphs)

            # 提取表格
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        tables_text.append(" | ".join(row_text))

            if tables_text:
                content += "\n\n" + "\n".join(tables_text)

            # 提取元数据
            metadata = {}
            if extract_metadata:
                core_props = doc.core_properties
                metadata = {
                    "title": core_props.title or os.path.basename(file_path),
                    "author": core_props.author or "",
                    "created": str(core_props.created) if core_props.created else "",
                    "modified": str(core_props.modified) if core_props.modified else "",
                    "pages": len(doc.paragraphs),
                    "tables": len(doc.tables),
                }

            return {"content": content, "metadata": metadata, "status": "success"}

        return await loop.run_in_executor(self.executor, _parse)

    async def _parse_pdf(self, file_path: str, extract_metadata: bool = True) -> Dict[str, Any]:
        """
        解析 PDF 文件

        Args:
            file_path: 文件路径
            extract_metadata: 是否提取元数据

        Returns:
            解析结果
        """
        loop = asyncio.get_event_loop()

        def _parse():
            content = []
            metadata = {}

            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # 提取文本
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            content.append(text)
                    except Exception as e:
                        logger.warning(f"PDF 第 {page_num} 页提取失败: {e}")
                        continue

                # 提取元数据
                if extract_metadata:
                    pdf_info = pdf_reader.metadata
                    metadata = {
                        "title": pdf_info.get("/Title", os.path.basename(file_path)),
                        "author": pdf_info.get("/Author", ""),
                        "creator": pdf_info.get("/Creator", ""),
                        "pages": len(pdf_reader.pages),
                    }

            return {"content": "\n\n".join(content), "metadata": metadata, "status": "success"}

        return await loop.run_in_executor(self.executor, _parse)

    async def _parse_text(self, file_path: str) -> Dict[str, Any]:
        """
        解析纯文本文件

        Args:
            file_path: 文件路径

        Returns:
            解析结果
        """
        loop = asyncio.get_event_loop()

        def _parse():
            # 检测文件编码
            with open(file_path, "rb") as file:
                raw_data = file.read()

                # 尝试 UTF-8
                try:
                    content = raw_data.decode("utf-8")
                except UnicodeDecodeError:
                    # 尝试 GBK（中文常用）
                    try:
                        content = raw_data.decode("gbk")
                    except UnicodeDecodeError:
                        # 尝试 latin-1
                        content = raw_data.decode("latin-1", errors="ignore")

            metadata = {
                "title": os.path.basename(file_path),
                "encoding": "utf-8" if isinstance(content, str) else "unknown",
            }

            return {"content": content, "metadata": metadata, "status": "success"}

        return await loop.run_in_executor(self.executor, _parse)

    async def _parse_with_tika(
        self, file_path: str, extract_metadata: bool = True, enable_ocr: bool = False
    ) -> Dict[str, Any]:
        """
        使用 Apache Tika 解析文档

        Args:
            file_path: 文件路径
            extract_metadata: 是否提取元数据
            enable_ocr: 是否启用 OCR

        Returns:
            解析结果
        """
        if not TIKA_AVAILABLE:
            return {"content": "", "metadata": {}, "status": "error", "error": "Apache Tika 不可用"}

        loop = asyncio.get_event_loop()

        def _parse():
            try:
                # 配置 Tika 参数
                tika_config = {
                    "serverEndpoint": self.tika_url,
                    "meta": extract_metadata,
                }

                # 如果启用 OCR，添加 OCR 配置
                if enable_ocr:
                    # 注意：OCR 需要额外配置 Tika Server
                    pass

                result = parser.from_file(file_path, **tika_config)

                content = result.get("content", "")
                metadata = result.get("metadata", {})

                # 处理元数据
                if extract_metadata:
                    metadata = {
                        "title": metadata.get("title")
                        or metadata.get("resourceName")
                        or os.path.basename(file_path),
                        "author": metadata.get("Author") or metadata.get("creator") or "",
                        "created": metadata.get("created") or "",
                        "modified": metadata.get("modified") or "",
                        "content-type": metadata.get("Content-Type") or "",
                        "tika_parser": metadata.get("X-Parsed-By") or "",
                    }

                return {"content": content, "metadata": metadata, "status": "success"}

            except Exception as e:
                logger.error(f"Tika 解析失败 {file_path}: {e}", exc_info=True)
                return {
                    "content": "",
                    "metadata": {},
                    "status": "error",
                    "error": f"Tika 解析失败: {e}",
                }

        return await loop.run_in_executor(self.executor, _parse)

    def extract_text_only(self, file_path: str) -> str:
        """
        仅提取文本（轻量级，不提取元数据）

        Args:
            file_path: 文件路径

        Returns:
            文本内容
        """
        result = asyncio.run(self.parse_file(file_path, extract_metadata=False))
        return result.get("content", "")

    async def close(self):
        """关闭解析器，释放资源"""
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("文档解析器已关闭")
