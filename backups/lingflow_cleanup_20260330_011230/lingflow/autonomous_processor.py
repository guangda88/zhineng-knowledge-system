#!/usr/bin/env python3
"""
自主教科书处理系统 (Autonomous Textbook Processor)

目标：
- 不依赖XMind，自主生成高质量TOC
- 支持多层次结构扩展（达到5-6级深度）
- 智能文本分割（语义边界识别）
- 高质量小节标题生成
- 自动质量评估和优化

设计原则：
1. 渐进式提升：从基础TOC开始，逐步扩展深度
2. 多方法融合：正则匹配 + AI辅助 + 启发式规则
3. 质量导向：每步都有质量检查和反馈
4. 可复用：适用于不同教科书
"""

import asyncio
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from backend.config import config

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """处理阶段"""

    INIT = "initialization"
    TOC_EXTRACTION = "toc_extraction"
    TOC_EXPANSION = "toc_expansion"
    TEXT_SEGMENTATION = "text_segmentation"
    SUBSECTION_GENERATION = "subsection_generation"
    QUALITY_ASSESSMENT = "quality_assessment"
    OPTIMIZATION = "optimization"
    COMPLETED = "completed"


@dataclass
class TocItem:
    """目录条目"""

    id: str  # 唯一标识
    title: str
    level: int  # 层级 1-6
    line_number: int = 0
    page_number: Optional[int] = None
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    text_range: Tuple[int, int] = (0, 0)  # (start_line, end_line)
    generated: bool = False  # 是否由AI生成
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title.strip(),
            "level": self.level,
            "line_number": self.line_number,
            "page_number": self.page_number,
            "parent_id": self.parent_id,
            "children": self.children,
            "text_range": self.text_range,
            "generated": self.generated,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class TextBlock:
    """文本块"""

    id: str
    toc_id: str  # 关联的TOC条目ID
    content: str
    start_line: int
    end_line: int
    char_count: int = 0
    subsections: List[str] = field(default_factory=list)  # 小节标题列表
    quality_score: float = 0.0

    def __post_init__(self):
        self.char_count = len(self.content)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "toc_id": self.toc_id,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "char_count": self.char_count,
            "subsections": self.subsections,
            "quality_score": self.quality_score,
        }


@dataclass
class ProcessingResult:
    """处理结果"""

    textbook_id: str
    textbook_title: str
    stage: ProcessingStage
    toc_items: List[TocItem] = field(default_factory=list)
    text_blocks: List[TextBlock] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    quality_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "textbook_id": self.textbook_id,
            "textbook_title": self.textbook_title,
            "stage": self.stage.value,
            "toc_items": [item.to_dict() for item in self.toc_items],
            "text_blocks": [block.to_dict() for block in self.text_blocks],
            "statistics": self.statistics,
            "issues": self.issues,
            "quality_metrics": self.quality_metrics,
        }


class AutonomousTocExtractor:
    """自主TOC提取器"""

    # 目录模式 - 从粗到细
    PATTERNS = {
        # Level 1: 第X章 - 更宽松的匹配
        "l1_chapter_cn": re.compile(
            r"^第\s*([一二三四五六七八九十百零\d]+)\s*章[、\s]*(.*)$", re.IGNORECASE
        ),
        "l1_chapter_cn_simple": re.compile(
            r"^第\s*([一二三四五六七八九十百零\d]+)\s*章\s*$", re.IGNORECASE
        ),
        "l1_chapter_ar": re.compile(
            r"^(\d+)\s*[、.．]\s*第?\s*[一二三四五六七八九十]*\s*章[、\s]*(.*)$", re.IGNORECASE
        ),
        # Level 1-2: 篇/编/部分
        "l1_part": re.compile(
            r"^([第]?[一二三四五六七八九十\d]+)\s*[篇编部部分]\s+(.+)$", re.IGNORECASE
        ),
        # Level 2: 第X节
        "l2_section_cn": re.compile(
            r"^第\s*([一二三四五六七八九十百零\d]+)\s*节[、\s]*(.+)$", re.IGNORECASE
        ),
        "l2_section_ar": re.compile(r"^(\d+)[、.．]\s+(.+)$"),
        # Level 2-3: 罗马数字
        "l3_roman": re.compile(r"^([IVX]+)[、.．\s]+(.+)$"),
        # Level 3-4: 中文数字
        "l3_chinese_num": re.compile(r"^([一二三四五六七八九十]+)[、.．]\s*(.+)$"),
        "l4_chinese_num_paren": re.compile(
            r"^[（\(]([一二三四五六七八九十]+)[）\)][、.．]?\s*(.+)$"
        ),
        # Level 4-5: 阿拉伯数字子项
        "l4_arabic_sub": re.compile(r"^(\d+)[、.．]\s*(.+)$"),
        "l5_arabic_paren": re.compile(r"^[（\(](\d+)[）\)][、.．]?\s*(.+)$"),
        # Level 5-6: 带序号
        "l6_ordinal": re.compile(r"^(第[一二三四五六七八九十]+[次次遍式])\s*(.+)$"),
    }

    def __init__(self):
        self.reset()

    def reset(self):
        """重置状态"""
        self.toc_items: List[TocItem] = []
        self.parent_stack: List[str] = []  # 用于追踪父子关系

    def extract(self, content: str) -> List[TocItem]:
        """提取TOC

        Args:
            content: 教材全文

        Returns:
            TOC条目列表
        """
        self.reset()

        # 步骤1: 尝试从目录区域提取
        toc_lines = self._locate_toc_area(content)

        # 步骤2: 提取基础TOC
        self._extract_basic_toc(toc_lines)

        # 如果TOC条目太少，尝试从全文提取章节
        if len(self.toc_items) < 5:
            logger.info(f"目录区域提取到 {len(self.toc_items)} 个条目，尝试从全文提取...")
            self._extract_from_full_text(content)

        # 步骤3: 建立层级关系
        self._build_hierarchy()

        return self.toc_items

    def _extract_from_full_text(self, content: str):
        """从全文中提取章节标题"""
        lines = content.split("\n")
        full_text_toc_items = []

        for idx, line in enumerate(lines):
            line_stripped = line.strip()

            # 只匹配第X章级别的标题
            for pattern in [
                self.PATTERNS["l1_chapter_cn"],
                self.PATTERNS["l1_chapter_cn_simple"],
                self.PATTERNS["l1_chapter_ar"],
            ]:
                match = pattern.match(line_stripped)
                if match:
                    # 提取标题
                    if pattern == self.PATTERNS["l1_chapter_cn_simple"]:
                        title = match.group(0)
                    else:
                        groups = match.groups()
                        title = groups[1] if len(groups) >= 2 and groups[1] else match.group(0)

                    title = title.strip()
                    if len(title) >= 2 and len(title) <= 100:
                        full_text_toc_items.append(
                            TocItem(
                                id=f"toc_full_{len(full_text_toc_items):04d}",
                                title=title,
                                level=1,
                                line_number=idx,
                                generated=False,
                            )
                        )
                    break

        # 如果从全文提取的更多，替换当前TOC
        if len(full_text_toc_items) > len(self.toc_items):
            logger.info(f"从全文提取到 {len(full_text_toc_items)} 个章节，替换目录TOC")
            self.toc_items = full_text_toc_items

    def _locate_toc_area(self, content: str) -> List[str]:
        """定位目录区域"""
        lines = content.split("\n")

        # 查找目录开始 - 扩展搜索范围
        toc_start = -1
        for i, line in enumerate(lines[:200]):
            line_clean = line.strip()
            if line_clean in ["目录", "目  录", "CONTENTS", "内 容"]:
                toc_start = i + 1
                break
            elif "目录" in line_clean or "内容" in line_clean:
                toc_start = i
                break

        # 如果没找到，通过模式匹配搜索全文
        if toc_start < 0:
            logger.info("未找到目录标题，通过模式匹配搜索...")
            chapter_matches = []
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if (
                    self.PATTERNS["l1_chapter_cn"].match(line_stripped)
                    or self.PATTERNS["l1_chapter_ar"].match(line_stripped)
                    or (line_stripped.startswith("第") and "章" in line_stripped)
                ):
                    chapter_matches.append(i)

            # 如果找到章节，使用前50行到第一个章节之间的区域
            if chapter_matches:
                toc_start = max(0, chapter_matches[0] - 50)
            else:
                # 最后手段：使用开头部分
                toc_start = 0

        # 查找目录结束
        toc_end = len(lines)
        if toc_start >= 0:
            consecutive_non_toc = 0
            for i in range(toc_start, min(len(lines), toc_start + 500)):
                line = lines[i].strip()
                if not line:
                    continue

                is_toc = self._is_toc_line(line)
                if is_toc:
                    consecutive_non_toc = 0
                else:
                    consecutive_non_toc += 1

                if consecutive_non_toc >= 30:
                    toc_end = i - consecutive_non_toc
                    break

        return lines[toc_start:toc_end]

    def _is_toc_line(self, line: str) -> bool:
        """判断是否为目录行"""
        for pattern in self.PATTERNS.values():
            if pattern.match(line.strip()):
                return True
        return False

    def _extract_basic_toc(self, toc_lines: List[str]):
        """提取基础TOC"""
        for idx, line in enumerate(toc_lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 尝试各种模式
            toc_item = self._try_patterns(line_stripped, idx)
            if toc_item:
                self.toc_items.append(toc_item)

    def _try_patterns(self, line: str, line_num: int) -> Optional[TocItem]:
        """尝试各种模式匹配"""
        # 按优先级尝试
        patterns_priority = [
            ("l1_chapter_cn", 1),
            ("l1_chapter_cn_simple", 1),
            ("l1_chapter_ar", 1),
            ("l1_part", 1),
            ("l2_section_cn", 2),
            ("l2_section_ar", 2),
            ("l3_roman", 3),
            ("l3_chinese_num", 3),
            ("l4_chinese_num_paren", 4),
            ("l4_arabic_sub", 4),
            ("l5_arabic_paren", 5),
            ("l6_ordinal", 6),
        ]

        for pattern_name, level in patterns_priority:
            match = self.PATTERNS[pattern_name].match(line)
            if match:
                # 根据模式提取标题
                if pattern_name == "l1_chapter_cn_simple":
                    # 格式: 第X章 (没有额外标题)
                    title = match.group(0)
                elif pattern_name in ["l1_chapter_cn", "l2_section_cn", "l6_ordinal"]:
                    # 格式: 第X章 标题 或 第X节 标题
                    groups = match.groups()
                    title = groups[1] if len(groups) >= 2 and groups[1] else match.group(0)
                elif pattern_name == "l1_part":
                    title = match.group(2)
                else:
                    # 格式: 编号. 标题
                    groups = match.groups()
                    title = groups[1] if len(groups) >= 2 and groups[1] else match.group(0)

                # 清理标题
                title = title.strip()

                # 跳过过短或过长的行
                if len(title) < 2 or len(title) > 100:
                    continue

                return TocItem(
                    id=f"toc_{len(self.toc_items):04d}",
                    title=title,
                    level=level,
                    line_number=line_num,
                    generated=False,
                )

        return None

    def _build_hierarchy(self):
        """建立层级关系"""
        # 重置父栈
        self.parent_stack = []

        for item in self.toc_items:
            # 清理父栈中级别>=当前级别的项目
            while (
                self.parent_stack
                and self.toc_items[self._find_item_by_id(self.parent_stack[-1])].level >= item.level
            ):
                self.parent_stack.pop()

            # 设置父ID
            if self.parent_stack:
                item.parent_id = self.parent_stack[-1]
                # 添加到父级的children列表
                parent = self.toc_items[self._find_item_by_id(self.parent_stack[-1])]
                if item.id not in parent.children:
                    parent.children.append(item.id)

            # 将当前ID入栈
            self.parent_stack.append(item.id)

    def _find_item_by_id(self, item_id: str) -> int:
        """根据ID查找项目索引"""
        for i, item in enumerate(self.toc_items):
            if item.id == item_id:
                return i
        return -1


class TocExpander:
    """TOC扩展器 - 使用AI扩展TOC深度"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.DEEPSEEK_API_KEY
        self.api_url = config.DEEPSEEK_API_URL
        self.model = config.DEEPSEEK_MODEL
        self.client = httpx.AsyncClient(timeout=30.0)

    async def expand_toc(
        self,
        toc_items: List[TocItem],
        content: str,
        target_depth: int = 5,
        max_subsections_per_level: int = 10,
    ) -> List[TocItem]:
        """扩展TOC到目标深度

        Args:
            toc_items: 原始TOC条目
            content: 教材全文
            target_depth: 目标深度
            max_subsections_per_level: 每级最大子节数

        Returns:
            扩展后的TOC条目
        """
        logger.info(f"开始扩展TOC，目标深度: {target_depth}")

        # 迭代扩展直到达到目标深度
        expanded_items = toc_items.copy()
        max_iterations = target_depth  # 最多迭代次数

        for iteration in range(max_iterations):
            # 找到需要扩展的项目
            items_to_expand = [
                item for item in expanded_items if item.level < target_depth and not item.children
            ]

            if not items_to_expand:
                logger.info(f"第{iteration+1}轮扩展：没有需要扩展的项目")
                break

            logger.info(f"第{iteration+1}轮扩展：找到 {len(items_to_expand)} 个需要扩展的项目")

            # 扩展这些项目
            for item in items_to_expand:
                try:
                    # 获取该项目的文本内容
                    text_range = self._find_text_range(item, content, expanded_items)

                    # 提取相关文本
                    relevant_text = content[text_range[0] : text_range[1]]

                    # 调用AI生成子标题
                    subsections = await self._generate_subsections(
                        item, relevant_text, target_depth, max_subsections_per_level
                    )

                    if not subsections:
                        logger.warning(f"项目 '{item.title}' 没有生成子项")
                        continue

                    # 添加新的子条目
                    new_items = self._create_subsection_items(
                        item, subsections, len(expanded_items)
                    )
                    expanded_items.extend(new_items)

                    # 更新父子关系
                    item.children = [sub_item.id for sub_item in new_items]
                    for sub_item in new_items:
                        sub_item.parent_id = item.id

                    logger.info(f"扩展项目 '{item.title}': 生成 {len(subsections)} 个子项")

                except Exception as e:
                    logger.error(f"扩展项目 '{item.title}' 失败: {e}")
                    continue

        return expanded_items

    def _find_text_range(
        self, item: TocItem, content: str, all_items: List[TocItem]
    ) -> Tuple[int, int]:
        """查找项目的文本范围"""
        lines = content.split("\n")

        # 简单实现：查找标题所在行，到下一个同级或更高级标题
        start_line = item.line_number

        # 查找结束行
        end_line = len(lines)
        for other_item in all_items:
            if other_item.id == item.id:
                continue
            if other_item.level <= item.level and other_item.line_number > start_line:
                end_line = min(end_line, other_item.line_number)
                break

        # 转换为字符位置
        start_char = sum(len(line) + 1 for line in lines[:start_line])
        end_char = sum(len(line) + 1 for line in lines[:end_line])

        return (start_char, end_char)

    async def _generate_subsections(
        self, parent_item: TocItem, text: str, target_depth: int, max_count: int
    ) -> List[str]:
        """使用AI生成子标题，带重试机制"""
        if not self.api_key or self.api_key == "sk-dummy":
            # 模拟生成（用于测试）
            return [f"子项 {i+1}" for i in range(min(3, max_count))]

        prompt = f"""你是一位专业的教科书内容分析师。请为以下章节内容生成{max_count}个小节标题。

章节标题: {parent_item.title}
当前层级: {parent_item.level}
目标层级: {parent_item.level + 1}

章节内容（前2000字符）:
{text[:2000]}

要求:
1. 生成{max_count}个简短、准确的小节标题
2. 每个标题应反映该小节的核心内容
3. 使用学术性语言，与教科书风格一致
4. 标题长度控制在2-20字之间
5. 每行一个标题，不要编号

请直接输出标题列表，不要解释。"""

        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                )

                response.raise_for_status()
                data = response.json()

                # 解析结果
                content_text = data["choices"][0]["message"]["content"].strip()
                subsections = [line.strip() for line in content_text.split("\n") if line.strip()]

                return subsections[:max_count]

            except httpx.HTTPStatusError as e:
                if e.response.status_code in [429, 500, 502, 503, 504]:
                    # 可重试错误
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"API请求失败 (状态码: {e.response.status_code}), {delay}秒后重试..."
                        )
                        await asyncio.sleep(delay)
                        continue
                logger.error(f"API请求失败: {e}")
                return []

            except Exception as e:
                logger.error(f"AI生成失败: {e}")
                return []

        return []

    def _create_subsection_items(
        self, parent: TocItem, subsections: List[str], start_index: int
    ) -> List[TocItem]:
        """创建子节条目"""
        items = []
        for idx, title in enumerate(subsections):
            item = TocItem(
                id=f"toc_{start_index + idx:04d}",
                title=title,
                level=parent.level + 1,
                line_number=parent.line_number,  # 临时设置，后续会更新
                parent_id=parent.id,
                generated=True,
                confidence=0.8,
            )
            items.append(item)

        return items


class SmartTextSegmenter:
    """智能文本分割器 - 基于语义边界"""

    def __init__(self, max_chars: int = 300, min_chars: int = 100):
        """
        Args:
            max_chars: 最大字符数
            min_chars: 最小字符数
        """
        self.max_chars = max_chars
        self.min_chars = min_chars

        # 中英文句子分割模式
        self.sentence_patterns = [
            re.compile(r"[.。!！?？;；:：]\s+"),  # 句号、问号、感叹号
            re.compile(r"[，,]\s+"),  # 逗号（优先级低）
        ]

    def segment(self, content: str, toc_items: List[TocItem]) -> List[TextBlock]:
        """分割文本

        Args:
            content: 教材全文
            toc_items: TOC条目列表

        Returns:
            文本块列表
        """
        logger.info("开始智能文本分割")

        blocks = []
        lines = content.split("\n")

        # 只处理原始TOC（非AI生成的）
        original_items = [item for item in toc_items if not item.generated]
        logger.info(f"找到 {len(original_items)} 个原始TOC项进行分割")

        for toc_item in original_items:
            # 获取该TOC项目的文本范围
            text_range = self._get_text_range(toc_item, toc_items, lines)

            if text_range[1] - text_range[0] == 0:
                continue

            # 提取文本
            text = "\n".join(lines[text_range[0] : text_range[1]])

            if not text.strip():
                continue

            # 如果文本小于最大限制，直接作为一个块
            if len(text) <= self.max_chars:
                block = TextBlock(
                    id=f"block_{len(blocks):04d}",
                    toc_id=toc_item.id,
                    content=text,
                    start_line=text_range[0],
                    end_line=text_range[1],
                )
                blocks.append(block)
            else:
                # 分割成多个块
                sub_blocks = self._split_large_text(text, toc_item, len(blocks))
                blocks.extend(sub_blocks)

        logger.info(f"分割完成，生成 {len(blocks)} 个文本块")
        return blocks

    def _get_text_range(
        self, item: TocItem, all_items: List[TocItem], lines: List[str]
    ) -> Tuple[int, int]:
        """获取项目的文本行范围"""
        # 从标题行的下一行开始，跳过标题
        start_line = item.line_number + 1

        # 查找下一个同级或更高级的项目
        end_line = len(lines)
        for other_item in all_items:
            if other_item.id == item.id:
                continue
            if other_item.level <= item.level and other_item.line_number > start_line:
                end_line = min(end_line, other_item.line_number)
                break

        return (start_line, end_line)

    def _split_large_text(self, text: str, toc_item: TocItem, start_index: int) -> List[TextBlock]:
        """分割大文本"""
        blocks = []
        paragraphs = text.split("\n\n")

        current_block = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果段落本身超过最大限制，进一步分割
            if len(para) > self.max_chars:
                # 先保存当前块（如果有）
                if current_block:
                    blocks.append(
                        self._create_block(current_block, toc_item, len(blocks) + start_index)
                    )
                    current_block = []
                    current_length = 0

                # 分割长段落
                sentences = self._split_paragraph(para)
                for sentence in sentences:
                    if len(sentence) > self.max_chars:
                        # 如果句子仍然太长，强制分割
                        chunks = [
                            sentence[i : i + self.max_chars]
                            for i in range(0, len(sentence), self.max_chars)
                        ]
                        for chunk in chunks:
                            block = TextBlock(
                                id=f"block_{len(blocks) + start_index:04d}",
                                toc_id=toc_item.id,
                                content=chunk,
                                start_line=toc_item.line_number,
                                end_line=toc_item.line_number,
                            )
                            blocks.append(block)
                    else:
                        # 检查添加这个句子是否会超出限制（考虑分隔符）
                        separator_len = 2 if current_block else 0  # \n\n between items
                        new_length = current_length + separator_len + len(sentence)
                        if new_length > self.max_chars:
                            # 超出限制，保存当前块并开始新块
                            if current_block:
                                blocks.append(
                                    self._create_block(
                                        current_block, toc_item, len(blocks) + start_index
                                    )
                                )
                            current_block = [sentence]
                            current_length = len(sentence)
                        else:
                            # 未超出限制，添加到当前块
                            current_block.append(sentence)
                            current_length = new_length
            else:
                # 检查添加这个段落是否会超出限制（考虑分隔符）
                separator_len = 2 if current_block else 0  # \n\n between items
                new_length = current_length + separator_len + len(para)
                if new_length > self.max_chars:
                    # 超出限制，保存当前块并开始新块
                    if current_block:
                        blocks.append(
                            self._create_block(current_block, toc_item, len(blocks) + start_index)
                        )
                    current_block = [para]
                    current_length = len(para)
                else:
                    # 未超出限制，添加到当前块
                    current_block.append(para)
                    current_length = new_length

        # 添加最后的块
        if current_block:
            blocks.append(self._create_block(current_block, toc_item, len(blocks) + start_index))

        return blocks

    def _split_paragraph(self, paragraph: str) -> List[str]:
        """分割段落为句子"""
        sentences = []
        current = ""

        for char in paragraph:
            current += char
            if char in ".。!！?？;；":
                if current.strip():
                    sentences.append(current.strip())
                current = ""

        if current.strip():
            sentences.append(current.strip())

        return sentences

    def _create_block(self, lines: List[str], toc_item: TocItem, index: int) -> TextBlock:
        """创建文本块"""
        content = "\n\n".join(lines)
        return TextBlock(
            id=f"block_{index:04d}",
            toc_id=toc_item.id,
            content=content,
            start_line=toc_item.line_number,
            end_line=toc_item.line_number,
        )


class AutonomousTextbookProcessor:
    """自主教科书处理器 - 主类"""

    def __init__(self, api_key: str = None, max_block_chars: int = 300, target_toc_depth: int = 3):
        """
        Args:
            api_key: DeepSeek API密钥
            max_block_chars: 最大文本块字符数
            target_toc_depth: 目标TOC深度
        """
        self.api_key = api_key
        self.max_block_chars = max_block_chars
        self.target_toc_depth = target_toc_depth

        # 初始化各模块
        self.toc_extractor = AutonomousTocExtractor()
        self.toc_expander = TocExpander(api_key)
        self.text_segmenter = SmartTextSegmenter(max_block_chars)

    async def process(self, textbook_path: str, textbook_title: str = None) -> ProcessingResult:
        """处理教科书

        Args:
            textbook_path: 教科书文件路径
            textbook_title: 教科书标题（可选）

        Returns:
            处理结果
        """
        # 读取文件
        path = Path(textbook_path)
        if not path.exists():
            raise FileNotFoundError(f"教科书文件不存在: {textbook_path}")

        # 尝试多种编码
        encodings = ["utf-8", "gbk", "gb2312", "gb18030"]
        content = None
        used_encoding = None

        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                used_encoding = encoding
                logger.info(f"使用编码 {encoding} 读取文件: {textbook_path}")
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise ValueError(f"无法解码文件: {textbook_path}，尝试的编码: {', '.join(encodings)}")

        if not textbook_title:
            textbook_title = path.stem

        # 创建结果对象
        result = ProcessingResult(
            textbook_id=path.stem, textbook_title=textbook_title, stage=ProcessingStage.INIT
        )

        # 阶段1: TOC提取
        result.stage = ProcessingStage.TOC_EXTRACTION
        result.toc_items = self.toc_extractor.extract(content)
        result.statistics["toc_items_extracted"] = len(result.toc_items)
        result.statistics["toc_max_level"] = max(
            (item.level for item in result.toc_items), default=0
        )

        logger.info(f"提取到 {len(result.toc_items)} 个TOC条目")

        # 阶段2: TOC扩展
        if result.statistics["toc_max_level"] < self.target_toc_depth:
            result.stage = ProcessingStage.TOC_EXPANSION
            result.toc_items = await self.toc_expander.expand_toc(
                result.toc_items, content, self.target_toc_depth
            )
            result.statistics["toc_items_expanded"] = len(result.toc_items)
            result.statistics["toc_max_level"] = max(
                (item.level for item in result.toc_items), default=0
            )

            logger.info(
                f"扩展后: {len(result.toc_items)} 个TOC条目，深度 {result.statistics['toc_max_level']}"
            )

        # 阶段3: 文本分割
        result.stage = ProcessingStage.TEXT_SEGMENTATION
        result.text_blocks = self.text_segmenter.segment(content, result.toc_items)
        result.statistics["text_blocks_created"] = len(result.text_blocks)

        # 统计文本块大小
        block_sizes = [block.char_count for block in result.text_blocks]
        result.statistics["avg_block_size"] = (
            sum(block_sizes) / len(block_sizes) if block_sizes else 0
        )
        result.statistics["max_block_size"] = max(block_sizes) if block_sizes else 0
        result.statistics["min_block_size"] = min(block_sizes) if block_sizes else 0
        result.statistics["blocks_over_limit"] = sum(
            1 for size in block_sizes if size > self.max_block_chars
        )

        logger.info(
            f"分割完成: {len(result.text_blocks)} 个块，平均大小 {result.statistics['avg_block_size']:.1f}"
        )

        # 阶段4: 完成
        result.stage = ProcessingStage.COMPLETED

        return result


# 便捷函数
async def process_textbook(
    textbook_path: str, api_key: str = None, max_block_chars: int = 300, target_toc_depth: int = 5
) -> ProcessingResult:
    """处理教科书的便捷函数"""
    processor = AutonomousTextbookProcessor(
        api_key=api_key, max_block_chars=max_block_chars, target_toc_depth=target_toc_depth
    )
    return await processor.process(textbook_path)


if __name__ == "__main__":
    # 测试代码
    import sys

    logging.basicConfig(level=logging.INFO)

    async def test():
        if len(sys.argv) < 2:
            print("用法: python autonomous_processor.py <textbook_path>")
            return

        textbook_path = sys.argv[1]
        result = await process_textbook(textbook_path)

        # 输出结果
        print("\n" + "=" * 60)
        print("处理结果")
        print("=" * 60)
        print(f"教科书: {result.textbook_title}")
        print(f"阶段: {result.stage.value}")
        print(f"TOC条目: {result.statistics.get('toc_items_extracted', 0)}")
        print(f"TOC深度: {result.statistics.get('toc_max_level', 0)}")
        print(f"文本块: {result.statistics.get('text_blocks_created', 0)}")
        print(f"平均块大小: {result.statistics.get('avg_block_size', 0):.1f}")
        print(f"超出限制的块: {result.statistics.get('blocks_over_limit', 0)}")
        print("=" * 60)

        # 保存结果
        output_path = (
            Path("backend/lingflow/data/processed/textbooks_v2")
            / f"{Path(textbook_path).stem}_processed.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {output_path}")

    asyncio.run(test())
