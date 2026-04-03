#!/usr/bin/env python3
"""
增强型目录解析器 - 支持6-9层深度解析

专门针对智能气功九本教材的复杂目录结构
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ParseMethod(Enum):
    """解析方法"""

    REGEX = "regex"
    HEURISTIC = "heuristic"
    AI_ASSISTED = "ai"


@dataclass
class TocItem:
    """目录条目"""

    title: str
    level: int  # 层级 1-9
    page_number: Optional[int] = None
    line_number: int = 0
    confidence: float = 1.0
    parent_index: Optional[int] = None
    parse_method: ParseMethod = ParseMethod.HEURISTIC
    chapter_number: Optional[str] = None  # 章节编号

    def to_dict(self) -> dict:
        return {
            "title": self.title.strip(),
            "level": self.level,
            "page_number": self.page_number,
            "line_number": self.line_number,
            "confidence": self.confidence,
            "parent_index": self.parent_index,
            "parse_method": self.parse_method.value,
            "chapter_number": self.chapter_number,
        }


@dataclass
class TocParseResult:
    """目录解析结果"""

    items: List[TocItem] = field(default_factory=list)
    raw_lines: List[str] = field(default_factory=list)
    parse_method: ParseMethod = ParseMethod.HEURISTIC
    confidence: float = 0.0
    issues: List[str] = field(default_factory=list)
    max_depth: int = 0

    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "item_count": len(self.items),
            "parse_method": self.parse_method.value,
            "confidence": self.confidence,
            "issues": self.issues,
            "max_depth": self.max_depth,
        }


class DeepTocParser:
    """深层目录解析器 - 支持6-9层深度"""

    # 智能气功教材目录模式 - 更全面的匹配规则
    PATTERNS = {
        # 层级1: 第X章
        "level1_chinese_full": re.compile(r"^第([一二三四五六七八九十百零\d]+)章\s+(.+)$"),
        "level1_chinese": re.compile(r"^第([一二三四五六七八九十百零\d]+)章[、\s]*(.+)$"),
        "level1_arabic": re.compile(r"^第?(\d+)章[、\s]*(.+)$"),
        "level1_simple": re.compile(r"^(\d+)\s*[、.．]\s*(.+)$"),
        # 层级1-2: 编号+篇/编/部分
        "level1_part": re.compile(r"^([第]?[一二三四五六七八九十\d]+)[篇编部部分]\s+(.+)$"),
        # 层级2: 第X节
        "level2_chinese": re.compile(r"^第([一二三四五六七八九十百零\d]+)节[、\s]*(.+)$"),
        "level2_arabic": re.compile(r"^(\d+)[、.．]\s+(.+)$"),
        "level2_dot": re.compile(r"^(\d+)\.(\d+)\s+(.+)$"),
        # 层级2-3: 中文数字 +顿号
        "level2_1_chinese": re.compile(r"^([一二三四五六七八九十]+)、\s*(.+)$"),
        "level3_chinese": re.compile(r"^([\(（]?[一二三四五六七八九十]+)[）\)]?[、.．]\s*(.+)$"),
        # 层级3-4: 罗马数字 (I, II, III, IV, V, VI, VII, VIII, IX, X)
        "level3_roman": re.compile(r"^([IVX]+)[、.．\s]+([^\(]+)$"),
        "level3_roman_paren": re.compile(r"^([IVX]+)[、.．\s]+\(([^)]+)\)$"),
        "level4_roman_nested": re.compile(r"^([IVX]+)[、.．]+(.+)$"),
        # 层级4-5: 阿拉伯数字子项 (一、二、三 或 1、2、3)
        "level4_chinese_sub": re.compile(r"^([一二三四五六七八九十]+)[、.．]\s*(.+)$"),
        "level4_arabic_sub": re.compile(r"^(\d+)[、.．]\s*(.+)$"),
        # 层级5-6: 带括号的子项 ((一) (二) 或 (1) (2))
        "level5_paren_chinese": re.compile(
            r"^[（\(]([一二三四五六七八九十]+)[）\)][、.．]?\s*(.+)$"
        ),
        "level5_paren_arabic": re.compile(r"^[（\(](\d+)[）\)][、.．]?\s*(.+)$"),
        # 层级6-7: 中文数字 + 序 (第一次、第二次等)
        "level6_ordinal": re.compile(r"^(第[一二三四五六七八九十]+[次次遍式])\s*(.+)$"),
        "level6_paren_ordinal": re.compile(
            r"^[（\(](第?[一二三四五六七八九十]+[次次遍式])[）\)]\s*(.+)$"
        ),
        # 层级7-8: 嵌套子项
        "level7_nested": re.compile(r"^([\(\)【\]\da-zA-Z]+)[、.．]\s*(.+)$"),
    }

    # 换行符模式（用于识别段落分隔）
    PARAGRAPH_BREAK = re.compile(r"^(={3,}|−{3,}|—{3,}|\*{3,})$")

    def __init__(self, enable_ai: bool = False):
        """初始化解析器"""
        self.enable_ai = enable_ai

    def detect_encoding(self, file_path: Path) -> str:
        """检测文件编码"""
        encodings = ["utf-8", "gbk", "gb2312", "gb18030", "big5"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read(1000)
                if len(content) > 100 and any("\u4e00" <= c <= "\u9fff" for c in content):
                    return encoding
            except (UnicodeDecodeError, IOError, OSError):
                # 尝试下一个编码
                continue
        return "utf-8"  # 默认

    def parse(self, content: str, method: ParseMethod = ParseMethod.HEURISTIC) -> TocParseResult:
        """解析目录"""
        lines = content.split("\n")
        result = TocParseResult(raw_lines=lines, parse_method=method)

        # 定位目录区域
        toc_start, toc_end = self._locate_toc_area(lines)
        if toc_start < 0:
            result.issues.append("未找到明显的目录区域，尝试全文解析")
            toc_start, toc_end = 0, min(len(lines), 3000)

        toc_lines = lines[toc_start:toc_end]
        result.raw_lines = toc_lines

        # 使用深度解析方法
        result = self._parse_deep_structure(toc_lines, result)

        # 建立层级关系
        result.items = self._build_hierarchy(result.items)

        # 计算最大深度
        if result.items:
            result.max_depth = max(item.level for item in result.items)

        # 计算置信度
        result.confidence = self._calculate_confidence(result)

        return result

    def _locate_toc_area(self, lines: List[str]) -> Tuple[int, int]:
        """定位目录区域"""
        toc_start = -1
        toc_end = len(lines)

        # 查找目录开始
        for i, line in enumerate(lines[:100]):
            line_clean = line.strip()
            if line_clean in ["目录", "目  录", "CONTENTS", "内 容", "内容"]:
                toc_start = i + 1
                break
            elif "目录" in line_clean:
                toc_start = i
                break

        # 如果没找到，尝试通过模式匹配
        if toc_start < 0:
            for i, line in enumerate(lines[:300]):
                for pattern_name in ["level1_chinese", "level1_arabic", "level1_part"]:
                    if self.PATTERNS[pattern_name].match(line.strip()):
                        toc_start = max(0, i - 5)  # 往前包含一些上下文
                        break
                if toc_start >= 0:
                    break

        # 查找目录结束
        if toc_start >= 0:
            # 统计连续的非目录行数和总行数
            consecutive_non_toc = 0
            total_lines_checked = 0
            max_lines_to_check = min(len(lines), toc_start + 8000)  # 增加检查范围

            for i in range(toc_start + 5, max_lines_to_check):
                line = lines[i].strip()
                if not line:
                    continue

                is_toc_line = self._is_toc_like_line(line)

                # 改进的检测逻辑：
                # 1. 检查是否是较长的段落（可能是正文）
                # 2. 检查是否包含页码格式（目录通常有页码）
                if not is_toc_line:
                    consecutive_non_toc += 1
                else:
                    consecutive_non_toc = 0

                total_lines_checked += 1

                # 动态调整结束条件
                # 如果已经检查了足够多的行，且有较多连续非目录行
                if total_lines_checked > 200 and consecutive_non_toc >= 30:
                    toc_end = i - consecutive_non_toc
                    break

                # 如果连续非目录行过多，也认为目录结束
                if consecutive_non_toc >= 50:
                    toc_end = i - consecutive_non_toc
                    break

                # 如果找到了明显的正文开始标记（如"第一章"后面跟着长段落）
                if consecutive_non_toc >= 10:
                    # 检查当前行是否是章节标题
                    if self._is_chapter_start(line):
                        toc_end = i - consecutive_non_toc
                        break

        return toc_start, toc_end

    def _is_toc_like_line(self, line: str) -> bool:
        """判断是否像目录行"""
        if not line:
            return False

        # 检查是否匹配任何目录模式
        for pattern_name in [
            "level1_chinese",
            "level1_arabic",
            "level1_part",
            "level2_chinese",
            "level2_arabic",
            "level2_1_chinese",
            "level3_roman",
            "level4_chinese_sub",
        ]:
            if self.PATTERNS[pattern_name].match(line):
                return True

        return False

    def _is_chapter_start(self, line: str) -> bool:
        """判断是否是章节开始（正文）"""
        if not line:
            return False

        # 检查是否匹配章节标题模式
        chapter_patterns = [
            r"^第[一二三四五六七八九十百零\d]+章[：\s]",
            r"^第[一二三四五六七八九十百零\d]+节[：\s]",
            r"^[一二三四五六七八九十]+、",
            r"^\d+、",
            r"^第[一二三四五六七八九十百零\d]+部分[：\s]",
        ]

        for pattern in chapter_patterns:
            if re.match(pattern, line):
                return True

        return False

    def _parse_deep_structure(self, lines: List[str], result: TocParseResult) -> TocParseResult:
        """深度解析目录结构"""
        items = []
        indent_levels = {}  # 缩进 -> 层级映射

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 跳过分隔线
            if self.PARAGRAPH_BREAK.match(line_stripped):
                continue

            # 尝试解析
            parsed = self._try_parse_line(line_stripped, i, line)
            if parsed:
                items.append(parsed)

        result.items = items
        return result

    def _try_parse_line(self, line: str, line_num: int, original_line: str) -> Optional[TocItem]:
        """尝试解析单行"""
        indent = len(original_line) - len(line)

        # 去除页码（目录中常见的\t数字格式）
        page_num_pattern = re.compile(r"\t\d+$")
        page_number = None
        if page_num_pattern.search(line):
            match = page_num_pattern.search(line)
            page_number = match.group(0).strip("\t")
            line = page_num_pattern.sub("", line).strip()

        # 去除末尾的纯数字（也是页码的另一种格式）
        trailing_num_pattern = re.compile(r"\s+\d{1,4}$")
        if trailing_num_pattern.search(line) and not re.search(r"[一二三四五六七八九十]", line):
            match = trailing_num_pattern.search(line)
            try:
                page_number = match.group(0).strip()
                line = trailing_num_pattern.sub("", line).strip()
            except (AttributeError, IndexError):
                # 匹配失败，保持原样
                pass

        # 按优先级尝试各种模式
        patterns_to_try = [
            ("level1_chinese_full", 1),
            ("level1_part", 1),
            ("level1_chinese", 1),
            ("level1_arabic", 1),
            ("level1_simple", 1),
            ("level2_chinese", 2),
            ("level2_1_chinese", 2),
            ("level2_arabic", 2),
            ("level2_dot", 2),
            ("level3_roman", 3),
            ("level3_roman_paren", 3),
            ("level4_chinese_sub", 4),
            ("level4_arabic_sub", 4),
            ("level5_paren_chinese", 5),
            ("level5_paren_arabic", 5),
            ("level6_ordinal", 6),
            ("level6_paren_ordinal", 6),
            ("level3_chinese", 3),
        ]

        for pattern_name, base_level in patterns_to_try:
            pattern = self.PATTERNS[pattern_name]
            match = pattern.match(line)
            if match:
                title = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                level = base_level

                # 提取章节编号
                chapter_num = match.group(1) if match.groups() else None

                # 根据缩进微调层级
                if indent > 0:
                    level += min(indent // 2, 3)  # 最多增加3层

                return TocItem(
                    title=title.strip(),
                    level=level,
                    line_number=line_num,
                    confidence=0.8,
                    parse_method=ParseMethod.HEURISTIC,
                    chapter_number=chapter_num,
                    page_number=int(page_number) if page_number and page_number.isdigit() else None,
                )

        # 如果没有匹配，检查是否是简单的标题行（全中文，较短）
        # 改进的策略：
        # 1. 长度限制：保持60字符以减少误判
        # 2. 必须包含章节标识符（第、节、章等）
        # 3. 避免纯标点符号的行
        # 4. 避免过长的连续文本（正文特征）

        # 排除纯标点和空白
        punctuation_pattern = r'^[\s，。！？、；：""' "（）【]+$"
        if re.match(punctuation_pattern, line):
            return None  # 直接跳过，不作为标题

        is_candidate = (
            len(line) < 60  # 严格长度限制
            and any("\u4e00" <= c <= "\u9fff" for c in line)  # 包含中文
            and not re.match(r'^[\s，。！？、；：""' "（）【]+$", line)  # 避免纯标点
        )

        # 检查是否像章节标题的特征（放宽条件）
        chapter_like = False
        chapter_patterns = [
            r"^第[一二三四五六七八九十百零\d]+[章节部分]",  # 第X章/节/部分
            r"^[一二三四五六七八九十]+、",  # 中文数字编号
            r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[、.]",  # 罗马数字编号
            r"^[A-Z]+[、.]",  # 字母编号
            r"^\d+[、.]",  # 阿拉伯数字编号
            r"综述|概论|引言|绪论|概述|说明",  # 常见章节关键词
        ]

        for pattern in chapter_patterns:
            if re.search(pattern, line):
                chapter_like = True
                break

        # 放宽条件：有章节特征，或者是有序号的中短文本
        if is_candidate and chapter_like:
            # 根据缩进推断层级
            inferred_level = 1
            if indent >= 2:
                inferred_level = min(indent // 2 + 1, 6)

            return TocItem(
                title=line.strip(),
                level=inferred_level,
                line_number=line_num,
                confidence=0.5,
                parse_method=ParseMethod.HEURISTIC,
                page_number=int(page_number) if page_number and page_number.isdigit() else None,
            )

        return None

    def _build_hierarchy(self, items: List[TocItem]) -> List[TocItem]:
        """建立层级关系"""
        if not items:
            return items

        # 使用栈结构建立父子关系
        level_stack = {}  # level -> item_index

        for i, item in enumerate(items):
            level = item.level

            # 找到父级
            if level > 1:
                for parent_level in range(level - 1, 0, -1):
                    if parent_level in level_stack:
                        item.parent_index = level_stack[parent_level]
                        break

            # 更新栈
            level_stack[level] = i

        return items

    def _calculate_confidence(self, result: TocParseResult) -> float:
        """计算置信度"""
        if not result.items:
            return 0.0

        # 基础分数
        score = 0.5

        # 层级深度加分 (目标6-9层)
        max_depth = max(item.level for item in result.items) if result.items else 0
        if max_depth >= 6:
            score += 0.3
        elif max_depth >= 4:
            score += 0.2
        elif max_depth >= 2:
            score += 0.1

        # 条目数量
        if len(result.items) >= 50:
            score += 0.1
        elif len(result.items) >= 20:
            score += 0.05

        # 层级连续性
        levels = set(item.level for item in result.items)
        if len(levels) >= 6:
            score += 0.1
        elif len(levels) >= 4:
            score += 0.05

        return round(min(score, 1.0), 2)


def parse_textbook_toc(text_file: Path) -> TocParseResult:
    """解析单本教材目录"""
    parser = DeepTocParser()

    # 检测编码
    encoding = parser.detect_encoding(text_file)
    logger.info(f"  使用编码: {encoding}")

    # 读取内容
    with open(text_file, "r", encoding=encoding, errors="ignore") as f:
        content = f.read()

    # 解析
    result = parser.parse(content, ParseMethod.HEURISTIC)

    return result


if __name__ == "__main__":
    import sys
    from pathlib import Path

    text_file = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path("data/processed/textbooks_v2/04-功法学/full_text.txt")
    )

    result = parse_textbook_toc(text_file)

    print(f"解析结果: {len(result.items)} 个条目")
    print(f"最大深度: {result.max_depth}")
    print(f"置信度: {result.confidence}")
    print(f"层级分布: {sorted(set(item.level for item in result.items))}")

    print("\n目录结构预览:")
    for item in result.items[:50]:
        indent = "  " * (item.level - 1)
        print(f"{indent}{item.level}. {item.title}")
