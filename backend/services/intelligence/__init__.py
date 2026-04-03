"""情报系统服务模块

采集与灵知系统相关的技术和数据集前沿内容，来源包括：
- GitHub: 开源项目趋势（RAG、嵌入、中文NLP等）
- npm: JavaScript/TypeScript包趋势
- HuggingFace: 模型和数据集趋势
"""

from backend.services.intelligence.base import BaseCollector, CollectionResult, IntelligenceItem
from backend.services.intelligence.relevance_analyzer import RelevanceAnalyzer

__all__ = ["IntelligenceItem", "BaseCollector", "CollectionResult", "RelevanceAnalyzer"]
