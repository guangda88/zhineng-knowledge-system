"""
增强文本处理器（Enhanced Text Processor）

文字处理工程流A-1的核心组件

功能：
1. 多格式文本解析（TXT, MD, HTML）
2. 智能文本分块（保持语义完整性）
3. 元数据提取（章节、标题、标签）
4. 编码自动检测
5. 内容清洗和标准化
"""

import html
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chardet

logger = logging.getLogger(__name__)


class TextFormat(Enum):
    """支持的文本格式"""

    TXT = "txt"
    MARKDOWN = "md"
    HTML = "html"
    AUTO = "auto"


@dataclass
class TextChunk:
    """文本块"""

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    char_count: int = 0
    word_count: int = 0
    paragraph_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.content)
        self.word_count = len(self.content.split())
        self.paragraph_count = len([p for p in self.content.split("\n\n") if p.strip()])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "paragraph_count": self.paragraph_count,
        }


@dataclass
class TextMetadata:
    """文本元数据"""

    title: Optional[str] = None
    author: Optional[str] = None
    chapters: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    language: str = "zh"
    encoding: str = "utf-8"
    format: TextFormat = TextFormat.TXT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "chapters": self.chapters,
            "sections": self.sections,
            "tags": self.tags,
            "language": self.language,
            "encoding": self.encoding,
            "format": self.format.value,
        }


class TextCleaner:
    """文本清洗器"""

    # 常见噪音模式
    NOISE_PATTERNS = [
        r"Page\s*\d+\s*of\s*\d+",  # 页码
        r"©\s*\d{4}.*?",  # 版权信息
        r"www\.\w+\.\w+",  # 网址
        r"\s{2,}",  # 多个空格
    ]

    # 需要保留的特殊符号
    PRESERVE_PATTERNS = [
        r"混元灵通",
        r"组场",
        r"发气",
        r"智能气功",
    ]

    @classmethod
    def clean(cls, text: str) -> str:
        """清洗文本

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        if not text:
            return ""

        # 清理HTML实体
        text = html.unescape(text)

        # 移除噪音（但保留特殊术语）
        for pattern in cls.NOISE_PATTERNS:
            # 检查是否包含需要保留的特殊术语
            matches = re.finditer(pattern, text)
            for match in matches:
                segment = match.group()
                # 如果不包含特殊术语，才移除
                if not any(term in segment for term in cls.PRESERVE_PATTERNS):
                    text = text.replace(segment, " ")

        # 标准化空白字符
        text = re.sub(r"\s{2,}", " ", text)  # 多个空格压缩为一个
        text = re.sub(r"\n{3,}", "\n\n", text)  # 多个换行压缩为两个

        # 移除首尾空白
        text = text.strip()

        return text

    @classmethod
    def normalize_punctuation(cls, text: str) -> str:
        """标准化标点符号"""
        # 中文标点标准化
        punct_map = {
            "。": "。",
            "，": "，",
            "；": "；",
            "：": "：",
            "？": "？",
            "！": "！",
            '"': '"',
            '"': '"',
            "'": "'",
            "'": "'",
            "（": "(",
            "）": ")",
        }

        for old, new in punct_map.items():
            text = text.replace(old, new)

        return text


class EncodingDetector:
    """编码检测器"""

    @staticmethod
    def detect(file_path: Path) -> str:
        """检测文件编码

        Args:
            file_path: 文件路径

        Returns:
            检测到的编码
        """
        try:
            with open(file_path, "rb") as f:
                raw_data = f.read(10000)  # 读取前10KB
                result = chardet.detect(raw_data)
                encoding = result["encoding"]

                # 如果检测不到或置信度太低，使用常见编码
                if not encoding or result["confidence"] < 0.7:
                    # 尝试常见中文编码
                    for enc in ["utf-8", "gbk", "gb2312", "gb18030"]:
                        try:
                            raw_data.decode(enc)
                            encoding = enc
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        encoding = "utf-8"  # 默认

                logger.info(f"检测到编码: {encoding} (置信度: {result['confidence']:.2f})")
                return encoding

        except Exception as e:
            logger.warning(f"编码检测失败: {e}，使用默认编码utf-8")
            return "utf-8"

    @staticmethod
    def read_with_encoding(file_path: Path, encoding: Optional[str] = None) -> str:
        """使用指定或检测到的编码读取文件

        Args:
            file_path: 文件路径
            encoding: 指定编码（None则自动检测）

        Returns:
            文件内容
        """
        if encoding is None:
            encoding = EncodingDetector.detect(file_path)

        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            # 如果失败，尝试其他编码
            for enc in ["utf-8", "gbk", "gb2312", "gb18030", "latin-1"]:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        content = f.read()
                    logger.warning(f"使用编码 {enc} 成功读取文件")
                    return content
                except UnicodeDecodeError:
                    continue

            # 如果都失败，使用忽略错误模式
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()


class MetadataExtractor:
    """元数据提取器"""

    # 章节模式
    CHAPTER_PATTERNS = [
        re.compile(r"^第\s*[一二三四五六七八九十百零\d]+\s*章[、\s]*(.*)$", re.IGNORECASE),
        re.compile(r"^第?\s*[一二三四五六七八九十\d]+\s*部?[、\s]*(.*)$", re.IGNORECASE),
        re.compile(r"^([一二三四五六七八九十\d]+)[、.．]\s*(.+)$"),
    ]

    # 标题模式
    TITLE_PATTERNS = [
        re.compile(r"^#\s+(.+)$"),  # Markdown
        re.compile(r"^title\s*:\s*(.+)$", re.IGNORECASE),  # YAML frontmatter
        re.compile(r"<title>(.+)</title>", re.IGNORECASE),  # HTML
    ]

    # 作者模式
    AUTHOR_PATTERNS = [
        re.compile(r"^author\s*:\s*(.+)$", re.IGNORECASE),
        re.compile(r"作者[：:]\s*(.+)$"),
    ]

    @classmethod
    def extract(cls, content: str, file_format: TextFormat = TextFormat.TXT) -> TextMetadata:
        """提取元数据

        Args:
            content: 文本内容
            file_format: 文件格式

        Returns:
            文本元数据
        """
        metadata = TextMetadata(format=file_format)

        lines = content.split("\n")

        # 提取标题（从前几行）
        for i, line in enumerate(lines[:50]):  # 只检查前50行
            for pattern in cls.TITLE_PATTERNS:
                match = pattern.match(line.strip())
                if match and not metadata.title:
                    metadata.title = match.group(1).strip()
                    break
            if metadata.title:
                break

        # 提取作者
        for i, line in enumerate(lines[:50]):
            for pattern in cls.AUTHOR_PATTERNS:
                match = pattern.match(line.strip())
                if match:
                    metadata.author = match.group(1).strip()
                    break
            if metadata.author:
                break

        # 提取章节
        for i, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue

            for pattern in cls.CHAPTER_PATTERNS:
                match = pattern.match(line)
                if match:
                    title = match.group(1) if match.groups() else line
                    metadata.chapters.append(title)
                    metadata.sections.append(
                        {"title": title, "level": 1, "line": i}  # 使用enumerate的索引而不是index()
                    )
                    break

        # 提取标签（基于关键词）
        content_lower = content.lower()
        keywords = {
            "智能气功": "气功",
            "混元灵通": "修炼",
            "组场": "练习方法",
            "发气": "技术应用",
            "康复": "应用",
            "治病": "应用",
        }

        for keyword, tag in keywords.items():
            if keyword in content_lower and tag not in metadata.tags:
                metadata.tags.append(tag)

        logger.info(
            f"提取元数据: 标题='{metadata.title}', 章节={len(metadata.chapters)}, 标签={metadata.tags}"
        )
        return metadata


class SemanticChunker:
    """语义分块器"""

    def __init__(self, max_chunk_size: int = 300, min_chunk_size: int = 100, overlap: int = 50):
        """初始化分块器

        Args:
            max_chunk_size: 最大块大小（字符数）
            min_chunk_size: 最小块大小
            overlap: 块之间重叠字符数
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap = overlap

    def chunk(self, text: str, metadata: Optional[TextMetadata] = None) -> List[TextChunk]:
        """语义分块

        Args:
            text: 输入文本
            metadata: 文本元数据

        Returns:
            文本块列表
        """
        if not text:
            return []

        # 清洗和标准化
        text = TextCleaner.clean(text)
        text = TextCleaner.normalize_punctuation(text)

        # 按段落分割
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        current_chunk = ""
        chunk_id = 0

        for para in paragraphs:
            # 如果当前块加上新段落不超过最大大小，直接添加
            if len(current_chunk) + len(para) + 2 <= self.max_chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunk = self._create_chunk(current_chunk, chunk_id, metadata)
                    chunks.append(chunk)
                    chunk_id += 1

                # 处理长段落
                if len(para) > self.max_chunk_size:
                    # 需要分割长段落
                    sub_chunks = self._split_long_paragraph(para, chunk_id, metadata)
                    chunks.extend(sub_chunks)
                    chunk_id += len(sub_chunks)
                    current_chunk = ""
                else:
                    # 开始新块
                    current_chunk = para

        # 保存最后一个块
        if current_chunk:
            chunk = self._create_chunk(current_chunk, chunk_id, metadata)
            chunks.append(chunk)

        # 添加重叠（上下文）
        if self.overlap > 0:
            chunks = self._add_overlap(chunks)

        logger.info(
            f"文本分块: {len(chunks)} 个块, 平均大小 {sum(c.char_count for c in chunks) / len(chunks):.0f} 字符"
        )
        return chunks

    def _create_chunk(
        self, content: str, chunk_id: int, metadata: Optional[TextMetadata]
    ) -> TextChunk:
        """创建文本块"""
        chunk_metadata = {}

        if metadata:
            chunk_metadata = {
                "title": metadata.title,
                "author": metadata.author,
                "language": metadata.language,
                "tags": metadata.tags.copy(),
            }

        return TextChunk(id=f"chunk_{chunk_id:06d}", content=content, metadata=chunk_metadata)

    def _split_long_paragraph(
        self, para: str, start_id: int, metadata: Optional[TextMetadata]
    ) -> List[TextChunk]:
        """分割长段落"""
        chunks = []

        # 按句子分割
        sentences = re.split(r"([。！？；])", para)

        current_chunk = ""
        chunk_id = start_id

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]

            if len(current_chunk) + len(sentence) <= self.max_chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunk = self._create_chunk(current_chunk, chunk_id, metadata)
                    chunks.append(chunk)
                    chunk_id += 1
                current_chunk = sentence

        if current_chunk:
            chunk = self._create_chunk(current_chunk, chunk_id, metadata)
            chunks.append(chunk)

        return chunks

    def _add_overlap(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """添加重叠上下文"""
        if len(chunks) <= 1:
            return chunks

        for i in range(len(chunks)):
            if i > 0:
                # 从前一块获取尾部
                prev_chunk = chunks[i - 1]
                if len(prev_chunk.content) > self.overlap:
                    overlap_text = prev_chunk.content[-self.overlap :]
                    chunks[i].content = overlap_text + "\n\n" + chunks[i].content
                    chunks[i].char_count = len(chunks[i].content)

        return chunks


class EnhancedTextProcessor:
    """增强文本处理器（主类）"""

    def __init__(self, max_chunk_size: int = 300, min_chunk_size: int = 100, overlap: int = 50):
        """初始化处理器

        Args:
            max_chunk_size: 最大块大小
            min_chunk_size: 最小块大小
            overlap: 块重叠大小
        """
        self.chunker = SemanticChunker(
            max_chunk_size=max_chunk_size, min_chunk_size=min_chunk_size, overlap=overlap
        )

    async def process_file(
        self,
        file_path: str,
        encoding: Optional[str] = None,
        file_format: TextFormat = TextFormat.AUTO,
    ) -> Tuple[List[TextChunk], TextMetadata]:
        """处理文本文件

        Args:
            file_path: 文件路径
            encoding: 文件编码（None则自动检测）
            file_format: 文件格式

        Returns:
            (文本块列表, 元数据)
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 检测编码
        if encoding is None:
            encoding = EncodingDetector.detect(path)

        # 读取文件
        content = EncodingDetector.read_with_encoding(path, encoding)

        # 处理内容
        return await self.process_content(
            content, file_format=file_format, detected_encoding=encoding
        )

    async def process_content(
        self,
        content: str,
        file_format: TextFormat = TextFormat.AUTO,
        detected_encoding: str = "utf-8",
    ) -> Tuple[List[TextChunk], TextMetadata]:
        """处理文本内容

        Args:
            content: 文本内容
            file_format: 文件格式
            detected_encoding: 检测到的编码

        Returns:
            (文本块列表, 元数据)
        """
        # 提取元数据
        metadata = MetadataExtractor.extract(content, file_format)
        metadata.encoding = detected_encoding

        # 分块
        chunks = self.chunker.chunk(content, metadata)

        logger.info(f"处理完成: {len(chunks)} 个块, 元数据={metadata.to_dict()}")
        return chunks, metadata

    def get_statistics(self, chunks: List[TextChunk]) -> Dict[str, Any]:
        """获取统计信息

        Args:
            chunks: 文本块列表

        Returns:
            统计信息
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "total_chars": 0,
                "total_words": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0,
            }

        total_chars = sum(c.char_count for c in chunks)
        total_words = sum(c.word_count for c in chunks)
        sizes = [c.char_count for c in chunks]

        return {
            "total_chunks": len(chunks),
            "total_chars": total_chars,
            "total_words": total_words,
            "avg_chunk_size": total_chars / len(chunks),
            "min_chunk_size": min(sizes),
            "max_chunk_size": max(sizes),
            "total_paragraphs": sum(c.paragraph_count for c in chunks),
        }


__all__ = [
    "TextFormat",
    "TextChunk",
    "TextMetadata",
    "TextCleaner",
    "EncodingDetector",
    "MetadataExtractor",
    "SemanticChunker",
    "EnhancedTextProcessor",
]
