"""上下文压缩技能

基于智能上下文压缩的对话优化，防止会话因上下文限制而中断。

功能：
- 对话历史压缩
- 检索结果压缩
- 文档内容压缩
- 自定义上下文压缩
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 导入上下文压缩模块
try:
    from backend.services.compression import AdvancedContextCompressor, CompressionStrategy

    COMPRESSION_AVAILABLE = True
except ImportError:
    COMPRESSION_AVAILABLE = False
    logging.warning("上下文压缩模块不可用，压缩功能将被禁用")

logger = logging.getLogger(__name__)


# 默认保留关键词
DEFAULT_KEYWORDS = [
    # 通用重要词
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
    # 智能气功领域关键词
    "智能气功",
    "形神庄",
    "捧气贯顶",
    "三心并站庄",
    "混元",
    "整体观",
    "意元体",
    "组场",
    "庞明",
    "脏真",
    "中脉",
    "周天",
    # 20维分类关键词
    "20维",
    "20维度",
    "分类",
    "类别",
    "维度",
    # 文档结构
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


@dataclass
class CompressionConfig:
    """压缩配置"""

    target_ratio: float = 0.5
    preserve_keywords: bool = True
    custom_keywords: List[str] = field(default_factory=list)
    strategies: List[str] = field(default_factory=lambda: ["density", "semantic", "list"])
    max_field_length: int = 2000
    max_list_items: int = 10


@dataclass
class CompressionStats:
    """压缩统计"""

    total_compressions: int = 0
    total_original_tokens: int = 0
    total_compressed_tokens: int = 0
    tokens_saved: int = 0
    reduction_ratio: float = 0.0


class ContextCompressionSkill:
    """上下文压缩技能

    使用方法：
    ```python
    skill = ContextCompressionSkill()
    compressed = skill.compress_context(context)
    ```
    """

    name = "context-compression"
    version = "1.0.0"
    description = "基于智能上下文压缩的对话优化"

    def __init__(self, config: Optional[CompressionConfig] = None):
        """初始化技能"""
        self.config = config or CompressionConfig()
        self.stats = CompressionStats()

        if COMPRESSION_AVAILABLE:
            all_keywords = DEFAULT_KEYWORDS + self.config.custom_keywords

            strategy_map = {
                "density": CompressionStrategy.DENSITY,
                "semantic": CompressionStrategy.SEMANTIC,
                "list": CompressionStrategy.LIST,
            }
            strategies = []
            for s in self.config.strategies:
                if s in strategy_map:
                    strategies.append(strategy_map[s])

            self._compressor = AdvancedContextCompressor(
                target_ratio=self.config.target_ratio,
                preserve_keywords=self.config.preserve_keywords,
                custom_keywords=all_keywords,
                strategies=strategies if strategies else None,
            )
            logger.info(f"[{self.name}] 上下文压缩已启用")
        else:
            self._compressor = None
            logger.warning(f"[{self.name}] 上下文压缩不可用")

    def compress_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """压缩上下文字典"""
        if not context:
            return context

        original_tokens = self._estimate_tokens(context)

        if self._compressor:
            compressed = self._compressor.compress(context)
        else:
            compressed = self._simple_compress(context)

        compressed_tokens = self._estimate_tokens(compressed)

        self._update_stats(original_tokens, compressed_tokens)

        logger.debug(f"[{self.name}] 上下文压缩: {original_tokens} -> {compressed_tokens} tokens")

        return compressed

    def compress_messages(
        self, messages: List[Dict[str, str]], max_messages: int = 20
    ) -> List[Dict[str, str]]:
        """压缩对话历史"""
        if not messages:
            return messages

        result = []

        # 保留系统消息
        for msg in messages:
            if msg.get("role") == "system":
                result.append(msg)

        # 分类消息
        important, regular = self._classify_messages(messages)

        # 合并重要消息和最近的常规消息
        result.extend(important)
        result.extend(regular[-max_messages:])

        logger.debug(f"[{self.name}] 消息压缩: {len(messages)} -> {len(result)} 条")

        return result

    def compress_search_results(
        self, results: List[Dict[str, Any]], max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """压缩检索结果"""
        if not results:
            return results

        compressed = results[:max_results]

        for result in compressed:
            if "content" in result:
                content = result["content"]
                if len(content) > self.config.max_field_length:
                    result["content"] = content[: self.config.max_field_length] + "... [compressed]"
                    result["content_compressed"] = True

        return compressed

    def compress_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """压缩文档内容"""
        compressed = document.copy()

        for key, value in document.items():
            if isinstance(value, str) and len(value) > self.config.max_field_length:
                compressed[key] = value[: self.config.max_field_length] + "... [compressed]"
            elif isinstance(value, list) and len(value) > self.config.max_list_items:
                compressed[key] = value[: self.config.max_list_items]

        return compressed

    def compress_text(self, text: str, max_length: Optional[int] = None) -> str:
        """压缩文本"""
        if not text:
            return text

        max_len = max_length or self.config.max_field_length

        if len(text) <= max_len:
            return text

        if self._compressor and CompressionStrategy.SEMANTIC in [
            s.value for s in (self._compressor.strategies or [])
        ]:
            compressed = self._compressor.semantic_compress(text)
            if len(compressed) <= max_len:
                return compressed

        return text[:max_len] + "... [compressed]"

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_compressions": self.stats.total_compressions,
            "total_original_tokens": self.stats.total_original_tokens,
            "total_compressed_tokens": self.stats.total_compressed_tokens,
            "tokens_saved": self.stats.tokens_saved,
            "reduction_ratio": round(self.stats.reduction_ratio * 100, 2),
            "lingflow_available": COMPRESSION_AVAILABLE,
        }

    def reset_stats(self) -> None:
        """重置统计"""
        self.stats = CompressionStats()

    def _classify_messages(self, messages: List[Dict[str, str]]) -> tuple:
        """分类消息：重要消息和常规消息"""
        important = []
        regular = []
        keywords_lower = [kw.lower() for kw in DEFAULT_KEYWORDS]

        for msg in messages:
            if msg.get("role") == "system":
                continue

            content = msg.get("content", "").lower()
            if any(kw in content for kw in keywords_lower):
                important.append(msg)
            else:
                regular.append(msg)

        return important, regular

    def _simple_compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """简化压缩实现"""
        compressed = {}

        for key, value in context.items():
            if isinstance(value, str):
                if len(value) > self.config.max_field_length:
                    compressed[key] = value[: self.config.max_field_length] + "... [compressed]"
                else:
                    compressed[key] = value
            elif isinstance(value, list):
                if len(value) > self.config.max_list_items:
                    compressed[key] = value[: self.config.max_list_items]
                else:
                    compressed[key] = value
            else:
                compressed[key] = value

        return compressed

    def _estimate_tokens(self, data: Any) -> int:
        """估算 token 数量"""
        return len(str(data)) // 4

    def _update_stats(self, original: int, compressed: int) -> None:
        """更新统计"""
        self.stats.total_compressions += 1
        self.stats.total_original_tokens += original
        self.stats.total_compressed_tokens += compressed
        self.stats.tokens_saved += original - compressed
        self.stats.reduction_ratio = 1.0 - (
            self.stats.total_compressed_tokens / max(self.stats.total_original_tokens, 1)
        )


# 技能工厂函数
def create_skill(config: Optional[CompressionConfig] = None) -> ContextCompressionSkill:
    """创建上下文压缩技能实例"""
    return ContextCompressionSkill(config)


# 技能元数据
SKILL_METADATA = {
    "name": "context-compression",
    "version": "1.0.0",
    "description": "基于智能上下文压缩的对话优化",
    "author": "zhineng-knowledge-system（灵知系统）",
    "category": "utilities",
    "tags": ["compression", "context", "lingflow"],
    "dependencies": ["lingflow"],
    "config_schema": {
        "target_ratio": {
            "type": "float",
            "default": 0.5,
            "min": 0.1,
            "max": 0.9,
            "description": "目标压缩比例",
        },
        "max_field_length": {"type": "int", "default": 2000, "description": "单个字段最大长度"},
        "max_list_items": {"type": "int", "default": 10, "description": "列表最大保留数量"},
        "custom_keywords": {"type": "list", "default": [], "description": "自定义关键词"},
    },
}


if __name__ == "__main__":
    # 测试技能
    skill = create_skill()

    test_context = {"requirements": "测试内容" * 100, "description": "智能气功形神庄练习要求" * 50}

    compressed = skill.compress_context(test_context)
    print(f"原始: {skill._estimate_tokens(test_context)} tokens")
    print(f"压缩: {skill._estimate_tokens(compressed)} tokens")
    print(f"统计: {skill.get_stats()}")
