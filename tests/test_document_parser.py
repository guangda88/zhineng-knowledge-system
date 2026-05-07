"""
测试 DocumentParser 模块
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.document_parser import DocumentParser


@pytest.fixture
def temp_text_file(tmp_path):
    """创建临时文本文件"""
    file_path = tmp_path / "test.txt"
    file_path.write_text("这是一段测试文本。\n这是第二行。", encoding="utf-8")
    return str(file_path)


@pytest.fixture
def temp_markdown_file(tmp_path):
    """创建临时 Markdown 文件"""
    file_path = tmp_path / "test.md"
    file_path.write_text("# 标题\n\n这是一段测试文本。", encoding="utf-8")
    return str(file_path)


class TestDocumentParser:
    """测试 DocumentParser 类"""

    def test_init_default(self):
        """测试默认初始化"""
        parser = DocumentParser()
        assert parser.tika_url == "http://localhost:9998"
        assert parser.use_tika_fallback is True
        assert parser.executor is not None

    def test_init_custom(self):
        """测试自定义参数初始化"""
        parser = DocumentParser(
            tika_url="http://localhost:9999",
            max_workers=8,
            use_tika_fallback=False
        )
        assert parser.tika_url == "http://localhost:9999"
        assert parser.use_tika_fallback is False

    def test_detect_format(self):
        """测试文件格式检测"""
        parser = DocumentParser()

        assert parser.detect_format("test.pdf") == "pdf"
        assert parser.detect_format("test.docx") == "docx"
        assert parser.detect_format("test.doc") == "docx"
        assert parser.detect_format("test.txt") == "txt"
        assert parser.detect_format("test.md") == "md"
        assert parser.detect_format("test.markdown") == "md"
        assert parser.detect_format("test.text") == "text"
        assert parser.detect_format("test.unknown") == "unknown"

    @pytest.mark.asyncio
    async def test_parse_text_file(self, temp_text_file):
        """测试解析文本文件"""
        parser = DocumentParser()
        result = await parser.parse_file(temp_text_file)

        assert result["status"] == "success"
        assert "这是一段测试文本" in result["content"]
        assert "metadata" in result
        assert result["metadata"]["encoding"] in ["utf-8", "gbk", "latin-1"]

    @pytest.mark.asyncio
    async def test_parse_markdown_file(self, temp_markdown_file):
        """测试解析 Markdown 文件"""
        parser = DocumentParser()
        result = await parser.parse_file(temp_markdown_file)

        assert result["status"] == "success"
        assert "标题" in result["content"]
        assert "这是一段测试文本" in result["content"]

    @pytest.mark.asyncio
    async def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        parser = DocumentParser()
        result = await parser.parse_file("/nonexistent/file.txt")

        assert result["status"] == "error"
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_parse_with_metadata(self, temp_text_file):
        """测试解析时提取元数据"""
        parser = DocumentParser()
        result = await parser.parse_file(temp_text_file, extract_metadata=True)

        assert result["status"] == "success"
        assert "metadata" in result
        assert "title" in result["metadata"]

    @pytest.mark.asyncio
    async def test_parse_without_metadata(self, temp_text_file):
        """测试解析时不提取元数据"""
        parser = DocumentParser()
        result = await parser.parse_file(temp_text_file, extract_metadata=False)

        assert result["status"] == "success"
        assert result["metadata"] == {"title": "test.txt", "encoding": "utf-8"}

    @pytest.mark.asyncio
    async def test_parse_batch(self, tmp_path):
        """测试批量解析"""
        # 创建多个文件
        file1 = tmp_path / "test1.txt"
        file2 = tmp_path / "test2.txt"
        file1.write_text("测试1", encoding="utf-8")
        file2.write_text("测试2", encoding="utf-8")

        parser = DocumentParser()
        results = await parser.parse_batch([str(file1), str(file2)])

        assert len(results) == 2
        assert all(r["status"] == "success" for r in results)
        assert "测试1" in results[0]["content"]
        assert "测试2" in results[1]["content"]

    def test_extract_text_only(self, temp_text_file):
        """测试仅提取文本（同步方法）"""
        parser = DocumentParser()
        content = parser.extract_text_only(temp_text_file)

        assert "这是一段测试文本" in content
        assert "这是第二行" in content

    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭解析器"""
        parser = DocumentParser()
        await parser.close()

        # 关闭后不应抛出异常
        await parser.close()


@pytest.mark.skipif(
    not os.environ.get("TEST_WITH_PDF"),
    reason="需要 TEST_WITH_PDF 环境变量"
)
class TestDocumentParserPDF:
    """测试 PDF 解析（需要真实 PDF 文件）"""

    @pytest.mark.asyncio
    async def test_parse_pdf(self):
        """测试解析 PDF 文件"""
        pdf_path = os.environ.get("TEST_PDF_PATH")
        if not pdf_path or not os.path.exists(pdf_path):
            pytest.skip("测试 PDF 文件不存在")

        parser = DocumentParser()
        result = await parser.parse_file(pdf_path)

        assert result["status"] == "success"
        assert len(result["content"]) > 0
        assert "metadata" in result


@pytest.mark.skipif(
    not os.environ.get("TEST_WITH_DOCX"),
    reason="需要 TEST_WITH_DOCX 环境变量"
)
class TestDocumentParserDOCX:
    """测试 DOCX 解析（需要真实 DOCX 文件）"""

    @pytest.mark.asyncio
    async def test_parse_docx(self):
        """测试解析 DOCX 文件"""
        docx_path = os.environ.get("TEST_DOCX_PATH")
        if not docx_path or not os.path.exists(docx_path):
            pytest.skip("测试 DOCX 文件不存在")

        parser = DocumentParser()
        result = await parser.parse_file(docx_path)

        assert result["status"] == "success"
        assert len(result["content"]) > 0
        assert "metadata" in result
