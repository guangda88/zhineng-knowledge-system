"""
搜索结果片段提取与高亮

基于关键词位置智能提取上下文片段，并使用 HTML <mark> 标签高亮显示。
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)


class ResultHighlighter:
    """搜索结果片段提取与高亮"""

    def __init__(self, max_length: int = 200, window_size: int = 50, max_snippets: int = 3):
        """
        初始化高亮器

        Args:
            max_length: 片段最大长度（字符数）
            window_size: 关键词前后窗口大小
            max_snippets: 最多提取的片段数量
        """
        self.max_length = max_length
        self.window_size = window_size
        self.max_snippets = max_snippets

    def extract_snippet(
        self, content: str, query: str, max_length: int = None, window_size: int = None
    ) -> str:
        """
        提取包含查询关键词的上下文片段

        Args:
            content: 完整内容
            query: 查询文本
            max_length: 片段最大长度（覆盖默认值）
            window_size: 关键词前后窗口大小（覆盖默认值）

        Returns:
            带高亮的文本片段
        """
        if not content or not query:
            return ""

        max_length = max_length or self.max_length
        window_size = window_size or self.window_size

        # 1. 查找关键词位置
        positions = self._find_keyword_positions(content, query)

        if not positions:
            # 关键词未找到，返回前N个字符
            return content[:max_length] + "..." if len(content) > max_length else content

        # 2. 提取上下文窗口
        snippet = self._extract_context_window(content, positions, max_length, window_size)

        # 3. 高亮关键词
        return self._highlight_keywords(snippet, query)

    def _find_keyword_positions(self, content: str, query: str) -> List[int]:
        """
        查找关键词在文本中的位置

        Args:
            content: 完整内容
            query: 查询文本

        Returns:
            关键词位置列表
        """
        # 移除特殊字符，保留中文、英文、数字
        query_clean = re.sub(r"[^\w\u4e00-\u9fff]", " ", query).strip()

        if not query_clean:
            return []

        # 对查询词进行分词（按空格分割）
        keywords = [kw for kw in query_clean.split() if len(kw) > 1]

        positions = []

        for keyword in keywords:
            # 忽略大小写匹配
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            for match in pattern.finditer(content):
                positions.append(match.start())

        return positions

    def _extract_context_window(
        self, content: str, positions: List[int], max_length: int, window_size: int
    ) -> str:
        """
        提取上下文窗口

        Args:
            content: 完整内容
            positions: 关键词位置列表
            max_length: 片段最大长度
            window_size: 关键词前后窗口大小

        Returns:
            上下文片段
        """
        if not positions:
            return ""

        # 计算窗口范围
        windows = []
        for pos in positions:
            start = max(0, pos - window_size)
            # 预估关键词长度（实际可能不同，但足够用于窗口计算）
            keyword_length = min(len(content) - pos, 10)
            end = min(len(content), pos + keyword_length + window_size)
            windows.append((start, end))

        # 合并重叠窗口
        merged = self._merge_overlapping_windows(windows, window_size)

        # 限制总长度
        result = []
        total_length = 0

        for i, (start, end) in enumerate(merged[: self.max_snippets]):
            segment_length = end - start

            if total_length + segment_length > max_length:
                # 超出长度限制，截断最后一个片段
                remaining = max_length - total_length
                if remaining > 0:
                    result.append(content[start : start + remaining])
                break

            # 添加片段分隔符
            if i > 0:
                result.append(" ... ")

            result.append(content[start:end])
            total_length += segment_length

        snippet = "".join(result)

        # 如果片段来自文档中间，添加省略号
        if snippet and merged[0][0] > 0:
            snippet = "..." + snippet
        if snippet and merged[-1][1] < len(content):
            snippet = snippet + "..."

        return snippet

    def _merge_overlapping_windows(
        self, windows: List[Tuple[int, int]], window_size: int
    ) -> List[Tuple[int, int]]:
        """
        合并重叠的窗口

        Args:
            windows: 窗口列表 [(start, end), ...]
            window_size: 窗口大小

        Returns:
            合并后的窗口列表
        """
        if not windows:
            return []

        # 按起始位置排序
        windows.sort()

        merged = [windows[0]]

        for current in windows[1:]:
            last_start, last_end = merged[-1]
            current_start, current_end = current

            # 如果窗口重叠或距离小于 window_size，则合并
            if current_start <= last_end + window_size:
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                merged.append(current)

        return merged

    def _highlight_keywords(self, text: str, query: str) -> str:
        """
        高亮关键词

        Args:
            text: 待高亮的文本
            query: 查询文本

        Returns:
            带高亮标记的文本
        """
        if not text or not query:
            return text

        # 清理查询词
        query_clean = re.sub(r"[^\w\u4e00-\u9fff]", " ", query).strip()
        keywords = [kw for kw in query_clean.split() if len(kw) > 1]

        if not keywords:
            return text

        # 按关键词长度降序排序（先匹配长的关键词）
        keywords.sort(key=len, reverse=True)

        highlighted_text = text

        for keyword in keywords:
            # 忽略大小写匹配，保留原始大小写
            pattern = re.compile(f"({re.escape(keyword)})", re.IGNORECASE)

            # 替换为 <mark> 标签（只替换未高亮的部分）
            def replace_func(match):
                # 避免重复高亮
                if "<mark>" in highlighted_text:
                    # 如果已经有标记，检查是否已经高亮
                    pos = match.start()
                    # 简单检查：前面有 <mark> 且后面没有 </mark>
                    if (
                        highlighted_text[max(0, pos - 6) : pos] == "<mark>"
                        and "</mark>" not in highlighted_text[pos : pos + len(keyword) + 7]
                    ):
                        return match.group(0)
                return f"<mark>{match.group(0)}</mark>"

            highlighted_text = pattern.sub(replace_func, highlighted_text)

        return highlighted_text

    def extract_multiple_snippets(
        self, content: str, query: str, max_snippets: int = 3, max_length_per_snippet: int = 150
    ) -> List[str]:
        """
        提取多个片段

        Args:
            content: 完整内容
            query: 查询文本
            max_snippets: 最多提取的片段数量
            max_length_per_snippet: 每个片段的最大长度

        Returns:
            片段列表
        """
        if not content or not query:
            return []

        positions = self._find_keyword_positions(content, query)

        if not positions:
            return [content[:max_length_per_snippet]]

        # 提取多个不重叠的片段
        windows = []
        for pos in positions[: max_snippets * 10]:  # 限制检查的位置数量
            start = max(0, pos - self.window_size)
            end = min(len(content), pos + self.window_size)
            windows.append((start, end))

        # 按起始位置排序
        windows.sort()

        # 提取不重叠的片段
        snippets = []
        last_end = -1

        for start, end in windows:
            # 跳过重叠的窗口
            if start <= last_end:
                continue

            snippet = content[start:end]
            if len(snippet) > max_length_per_snippet:
                snippet = snippet[:max_length_per_snippet] + "..."

            snippets.append(self._highlight_keywords(snippet, query))
            last_end = end

            if len(snippets) >= max_snippets:
                break

        return snippets

    def get_highlight_summary(self, content: str, query: str, max_length: int = 300) -> str:
        """
        获取高亮摘要（多个片段的汇总）

        Args:
            content: 完整内容
            query: 查询文本
            max_length: 总摘要最大长度

        Returns:
            高亮摘要
        """
        if not content or not query:
            return ""

        # 提取片段
        snippet = self.extract_snippet(content, query, max_length=max_length)

        if len(snippet) <= max_length:
            return snippet

        # 如果单个片段过长，使用多个片段
        snippets = self.extract_multiple_snippets(
            content, query, max_snippets=2, max_length_per_snippet=max_length // 2
        )

        return " ... ".join(snippets)
