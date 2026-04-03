"""LingFlow 压缩模块

实现高级上下文压缩功能，支持多种压缩策略。
"""

import logging
import re
import string
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """压缩策略枚举"""

    DENSITY = "density"  # 基于信息密度压缩
    SEMANTIC = "semantic"  # 语义压缩
    LIST = "list"  # 列表压缩


@dataclass
class CompressionResult:
    """压缩结果"""

    original_size: int
    compressed_size: int
    compression_ratio: float
    data: Any
    strategies_used: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def reduction_percentage(self) -> float:
        """压缩百分比"""
        if self.original_size == 0:
            return 0.0
        return (1 - self.compressed_size / self.original_size) * 100


class AdvancedContextCompressor:
    """高级上下文压缩器

    支持多种压缩策略的智能上下文压缩。

    特性：
    - 信息密度分析
    - 语义保留压缩
    - 关键词保护
    - 列表智能采样
    """

    def __init__(
        self,
        target_ratio: float = 0.5,
        preserve_keywords: bool = True,
        custom_keywords: Optional[List[str]] = None,
        strategies: Optional[List[CompressionStrategy]] = None,
        max_field_length: int = 2000,
        max_list_items: int = 10,
    ):
        """初始化压缩器

        Args:
            target_ratio: 目标压缩比例 (0.5 = 压缩到50%)
            preserve_keywords: 是否保留关键词
            custom_keywords: 自定义关键词列表
            strategies: 使用的压缩策略列表
            max_field_length: 字段最大长度
            max_list_items: 列表最大项数
        """
        self.target_ratio = target_ratio
        self.preserve_keywords = preserve_keywords
        self.custom_keywords = set(custom_keywords or [])
        self.strategies = strategies or [
            CompressionStrategy.DENSITY,
            CompressionStrategy.SEMANTIC,
            CompressionStrategy.LIST,
        ]
        self.max_field_length = max_field_length
        self.max_list_items = max_list_items

        # 构建关键词模式
        self._keyword_patterns = self._build_keyword_patterns()

        # 常见无意义词（停用词）
        self._stopwords = self._build_stopwords()

        logger.debug(
            f"初始化压缩器: target_ratio={target_ratio}, "
            f"strategies={[s.value for s in self.strategies]}"
        )

    def compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """压缩上下文字典

        Args:
            context: 上下文字典

        Returns:
            压缩后的上下文字典
        """
        if not context:
            return context

        original_size = self._estimate_size(context)
        compressed = context.copy()
        strategies_used = []

        # 应用各种压缩策略
        for strategy in self.strategies:
            if strategy == CompressionStrategy.DENSITY:
                compressed = self._density_compress(compressed)
                strategies_used.append("density")
            elif strategy == CompressionStrategy.SEMANTIC:
                compressed = self._semantic_compress_dict(compressed)
                strategies_used.append("semantic")
            elif strategy == CompressionStrategy.LIST:
                compressed = self._list_compress(compressed)
                strategies_used.append("list")

        compressed_size = self._estimate_size(compressed)

        logger.debug(
            f"压缩完成: {original_size} -> {compressed_size} "
            f"({CompressionResult(original_size, compressed_size, 0, compressed).reduction_percentage:.1f}% 减少)"
        )

        return compressed

    def semantic_compress(self, text: str) -> str:
        """语义文本压缩

        保留关键信息，去除冗余内容。

        Args:
            text: 输入文本

        Returns:
            压缩后的文本
        """
        if not text:
            return text

        # 分割成段落和句子
        paragraphs = text.split("\n\n")
        compressed_paragraphs = []

        for paragraph in paragraphs:
            sentences = self._split_sentences(paragraph)
            if not sentences:
                continue

            # 计算每个句子的重要性
            scored_sentences = self._score_sentences(sentences)

            # 根据目标比例选择句子
            target_count = max(1, int(len(scored_sentences) * self.target_ratio))
            selected = sorted(scored_sentences, key=lambda x: x[1], reverse=True)[:target_count]

            # 按原始顺序排列
            selected_indices = [idx for idx, _ in selected]
            compressed_sentences = [sentences[i] for i in sorted(selected_indices)]

            compressed_paragraphs.append(" ".join(compressed_sentences))

        return "\n\n".join(compressed_paragraphs)

    def _density_compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """基于信息密度的压缩

        保留高信息密度内容，压缩低密度内容。
        """
        compressed = {}

        for key, value in context.items():
            if isinstance(value, str):
                density = self._calculate_density(value)
                # 根据密度决定压缩程度
                if density < 0.3:  # 低密度
                    compressed[key] = self._truncate_text(value, self.max_field_length // 2)
                elif density < 0.6:  # 中密度
                    compressed[key] = self._truncate_text(value, int(self.max_field_length * 0.75))
                else:  # 高密度
                    compressed[key] = self._truncate_text(value, self.max_field_length)
            else:
                compressed[key] = value

        return compressed

    def _semantic_compress_dict(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """对字典中的文本进行语义压缩"""
        compressed = {}

        for key, value in context.items():
            if isinstance(value, str) and len(value) > 500:
                # 检查是否包含关键词
                has_keywords = self._has_keywords(value)

                if has_keywords:
                    # 包含关键词，保留更多内容
                    compressed[key] = self._semantic_compress_with_keywords(value)
                else:
                    # 普通语义压缩
                    compressed[key] = self.semantic_compress(value)
            else:
                compressed[key] = value

        return compressed

    def _list_compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """压缩列表类型字段"""
        compressed = {}

        for key, value in context.items():
            if isinstance(value, list):
                if len(value) > self.max_list_items:
                    # 智能采样：保留首尾和重要项
                    compressed[key] = self._smart_sample_list(value, self.max_list_items)
                else:
                    compressed[key] = value
            else:
                compressed[key] = value

        return compressed

    def _smart_sample_list(self, items: List[Any], max_items: int) -> List[Any]:
        """智能采样列表

        保留：
        - 前几项（开头信息）
        - 后几项（结尾信息）
        - 包含关键词的重要项
        """
        if len(items) <= max_items:
            return items

        result = []
        reserved_head = max(1, max_items // 4)
        reserved_tail = max(1, max_items // 4)
        reserved_important = max_items - reserved_head - reserved_tail

        # 保留头部
        result.extend(items[:reserved_head])

        # 查找包含关键词的重要项
        important_items = []
        for item in items[reserved_head : -reserved_tail if reserved_tail > 0 else len(items)]:
            item_str = str(item)
            if self._has_keywords(item_str):
                important_items.append(item)

        # 保留重要项
        if important_items:
            result.extend(important_items[:reserved_important])

        # 保留尾部
        if reserved_tail > 0:
            result.extend(items[-reserved_tail:])

        return result[:max_items]

    def _has_keywords(self, text: str) -> bool:
        """检查文本是否包含关键词"""
        text_lower = text.lower()

        # 检查自定义关键词
        for keyword in self.custom_keywords:
            if keyword.lower() in text_lower:
                return True

        # 检查关键词模式
        for pattern in self._keyword_patterns:
            if pattern.search(text_lower):
                return True

        return False

    def _semantic_compress_with_keywords(self, text: str) -> str:
        """保留关键词的语义压缩"""
        sentences = self._split_sentences(text)
        if not sentences:
            return text

        # 优先保留包含关键词的句子
        keyword_sentences = []
        other_sentences = []

        for sentence in sentences:
            if self._has_keywords(sentence):
                keyword_sentences.append(sentence)
            else:
                other_sentences.append(sentence)

        # 所有包含关键词的句子都保留
        result = keyword_sentences.copy()

        # 从其他句子中选择一些
        other_count = max(0, int(len(sentences) * self.target_ratio) - len(keyword_sentences))
        if other_count > 0 and other_sentences:
            # 按重要性评分选择
            scored = self._score_sentences(other_sentences)
            selected = sorted(scored, key=lambda x: x[1], reverse=True)[:other_count]
            selected_indices = [idx for idx, _ in selected]
            result.extend(other_sentences[i] for i in sorted(selected_indices))

        return " ".join(result)

    def _score_sentences(self, sentences: List[str]) -> List[Tuple[int, float]]:
        """为句子评分

        返回: [(index, score), ...]
        """
        scores = []

        for i, sentence in enumerate(sentences):
            score = 0.0

            # 长度因子（中等长度得分高）
            length = len(sentence)
            if 20 <= length <= 100:
                score += 1.0
            elif length > 100:
                score += 0.5

            # 关键词因子
            if self._has_keywords(sentence):
                score += 2.0

            # 信息密度因子
            density = self._calculate_density(sentence)
            score += density * 2.0

            # 数字和特殊字符因子（通常包含重要信息）
            if re.search(r"\d+", sentence):
                score += 0.5

            # 非停用词比例
            words = sentence.split()
            if words:
                non_stopwords = sum(1 for w in words if w.lower() not in self._stopwords)
                score += (non_stopwords / len(words)) * 1.0

            scores.append((i, score))

        return scores

    def _calculate_density(self, text: str) -> float:
        """计算文本的信息密度

        密度 = (非停用词数 + 数字数 + 特殊字符数) / 总字符数
        """
        if not text:
            return 0.0

        words = text.split()
        if not words:
            return 0.0

        # 非停用词比例
        non_stopwords = sum(1 for w in words if w.lower() not in self._stopwords)

        # 数字计数
        digit_count = sum(c.isdigit() for c in text)

        # 关键字符
        special_chars = sum(c in ":-=+[]{}()" for c in text)

        total = len(words) + max(digit_count // 3, 0) + special_chars
        density = (non_stopwords + digit_count / 3 + special_chars) / max(total, 1)

        return min(density, 1.0)

    def _truncate_text(self, text: str, max_length: int) -> str:
        """截断文本，尝试在句子边界处截断"""
        if len(text) <= max_length:
            return text

        # 尝试在句子边界截断
        truncated = text[:max_length]

        # 查找最后的句子结束符
        for sep in (". ", "。", "! ", "！", "? ", "？", "\n"):
            last_sep = truncated.rfind(sep)
            if last_sep > max_length // 2:  # 确保不会截断太多
                return truncated[: last_sep + len(sep)] + "..."

        # 没有找到合适的边界，直接截断
        return truncated + "..."

    def _split_sentences(self, text: str) -> List[str]:
        """分割文本为句子"""
        # 简单的句子分割（支持中英文）
        pattern = r"[.。!！?？]\s+|[\n]+"
        sentences = re.split(pattern, text)

        # 清理空句子
        return [s.strip() for s in sentences if s.strip()]

    def _estimate_size(self, data: Any) -> int:
        """估算数据大小（字符数）"""
        if isinstance(data, str):
            return len(data)
        elif isinstance(data, (list, tuple, dict)):
            return len(str(data))
        else:
            return len(str(data))

    def _build_keyword_patterns(self) -> List[re.Pattern]:
        """构建关键词正则表达式模式"""
        patterns = []

        # 默认重要词
        default_keywords = [
            "must",
            "should",
            "require",
            "ensure",
            "critical",
            "important",
            "essential",
            "verify",
            "validate",
            "confirm",
            "定义",
            "原理",
            "方法",
            "步骤",
            "注意事项",
            "禁忌",
            "功效",
            "作用",
            "要点",
        ]

        all_keywords = list(self.custom_keywords) + default_keywords

        for keyword in all_keywords:
            try:
                pattern = re.compile(r"\b" + re.escape(keyword.lower()) + r"\b")
                patterns.append(pattern)
            except re.error:
                # 忽略无效的正则表达式
                pass

        return patterns

    def _build_stopwords(self) -> Set[str]:
        """构建停用词集合"""
        # 中英文常见停用词
        stopwords = {
            # 英文
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            # 中文
            "的",
            "了",
            "在",
            "是",
            "我",
            "有",
            "和",
            "就",
            "不",
            "人",
            "都",
            "一",
            "一个",
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
            "去",
            "你",
            "会",
            "着",
            "没有",
            "看",
            "好",
            "自己",
            "这",
        }

        return stopwords


# 便捷函数
def compress_context(
    context: Dict[str, Any], target_ratio: float = 0.5, keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """压缩上下文字典

    Args:
        context: 上下文字典
        target_ratio: 目标压缩比例
        keywords: 要保留的关键词

    Returns:
        压缩后的上下文
    """
    compressor = AdvancedContextCompressor(target_ratio=target_ratio, custom_keywords=keywords)
    return compressor.compress(context)


def compress_text(text: str, target_ratio: float = 0.5, preserve_keywords: bool = True) -> str:
    """压缩文本

    Args:
        text: 输入文本
        target_ratio: 目标压缩比例
        preserve_keywords: 是否保留关键词

    Returns:
        压缩后的文本
    """
    if not text:
        return text

    compressor = AdvancedContextCompressor(
        target_ratio=target_ratio, preserve_keywords=preserve_keywords
    )
    return compressor.semantic_compress(text)


def compress_messages(
    messages: List[Dict[str, str]], max_messages: int = 20
) -> List[Dict[str, str]]:
    """压缩消息列表

    Args:
        messages: 消息列表
        max_messages: 保留的最大消息数

    Returns:
        压缩后的消息列表
    """
    if not messages:
        return messages

    # 保留系统消息
    result = [m for m in messages if m.get("role") == "system"]

    # 其他消息
    other_messages = [m for m in messages if m.get("role") != "system"]

    # 保留最近的消息
    result.extend(other_messages[-max_messages:])

    return result
