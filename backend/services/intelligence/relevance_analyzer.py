"""情报相关性分析器

基于灵知系统领域关键词对采集到的技术项目/包/模型进行相关性评分。
三级关键词体系：领域前沿 > 技术引擎 > 基础设施

灵知系统的本质：用现代AI技术让中华传统文化知识"活起来"。
关注焦点不是通用AI工具链，而是：
  - 古籍数字化、文言文NLP、中医/气功知识图谱
  - 中文RAG方案、中文嵌入模型、中文大模型
  - 支撑上述目标的基础技术
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RelevanceAnalyzer:
    """灵知系统领域相关性分析器

    通过加权关键词匹配、热度加成、时效加成计算综合相关性评分。
    """

    # 领域前沿关键词（权重 90-100）：灵知独有的关注领域，最能体现系统价值
    DOMAIN_KEYWORDS: Dict[str, int] = {
        "classical-chinese": 100,
        "wenyanwen": 100,
        "文言文": 100,
        "ancient-chinese": 98,
        "ancient-text": 95,
        "古籍": 95,
        "guji": 95,
        "chinese-ancient": 95,
        "digital-humanities": 93,
        "数字人文": 93,
        "cultural-heritage": 92,
        "tcm-nlp": 92,
        "中医nlp": 92,
        "traditional-chinese-medicine": 90,
        "chinese-medicine": 90,
        "qigong": 90,
        "气功": 90,
        "hanzi-ocr": 90,
        "chinese-ocr": 88,
        "vertical-text": 87,
        "chinese-ner": 86,
        "ancient-text-ocr": 85,
        "chinese-knowledge-graph": 85,
        "chinese-corpus": 84,
        "chinese-question-answering": 83,
        "classical-chinese-nlp": 82,
        "formula-knowledge-graph": 80,
        "方剂": 80,
    }

    # 技术引擎关键词（权重 50-75）：支撑灵知系统的核心技术
    TECH_KEYWORDS: Dict[str, int] = {
        "rag": 75,
        "retrieval-augmented": 73,
        "graphrag": 72,
        "graph-rag": 72,
        "bge": 72,
        "chinese-embedding": 72,
        "text-embedding": 70,
        "vector-search": 70,
        "semantic-search": 70,
        "knowledge-graph": 70,
        "chinese-llm": 70,
        "deepseek": 68,
        "qwen": 68,
        "chatglm": 68,
        "glm": 65,
        "multi-agent": 65,
        "chinese-nlp": 65,
        "sentence-transformers": 63,
        "cross-encoder": 62,
        "reranker": 62,
        "hybrid-search": 60,
        "bm25": 58,
        "chinese-segmentation": 58,
        "jieba": 55,
        "text-to-speech": 55,
        "tts": 55,
        "edge-tts": 53,
        "ocr": 53,
        "asr": 53,
        "whisper": 53,
        "speech-recognition": 53,
        "pgvector": 50,
        "chain-of-thought": 50,
    }

    # 基础设施关键词（权重 10-35）：底层框架和通用工具
    INFRA_KEYWORDS: Dict[str, int] = {
        "langchain": 35,
        "llamaindex": 35,
        "huggingface": 30,
        "transformers": 28,
        "dataset": 25,
        "embedding-model": 25,
        "embedding": 22,
        "pytorch": 20,
        "onnx": 20,
        "fastapi": 15,
        "asyncpg": 15,
        "pydantic": 12,
        "postgresql": 10,
        "redis": 10,
        "docker-compose": 10,
    }

    ALL_KEYWORDS: Dict[str, int] = {
        **DOMAIN_KEYWORDS,
        **TECH_KEYWORDS,
        **INFRA_KEYWORDS,
    }

    # 中文相关加成关键词（用于额外加分判断）
    _CHINESE_INDICATORS = [
        "chinese",
        "中文",
        "zh",
        "mandarin",
        "hanzi",
        "文言",
        "古文",
        "古籍",
        "中医",
        "气功",
    ]

    @staticmethod
    def _tiered_score(value, thresholds):
        """根据阈值表计算分层评分。thresholds 为 [(min_value, score), ...] 降序排列。"""
        for threshold, points in thresholds:
            if value >= threshold:
                return points
        return 0

    def _calc_freshness_bonus(self, updated_at) -> int:
        """计算时效加成"""
        if not updated_at:
            return 0
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return 0
        if not isinstance(updated_at, datetime):
            return 0
        now = datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.now()
        days_diff = (now - updated_at).days
        if days_diff <= 7:
            return 15
        if days_diff <= 30:
            return 10
        if days_diff <= 90:
            return 5
        return 0

    def _calc_chinese_bonus(self, item) -> int:
        """计算中文/传统文化加成"""
        language = item.get("language", "").lower()
        name = item.get("name", "").lower()
        desc = item.get("description", "").lower()
        for indicator in self._CHINESE_INDICATORS:
            if indicator in name or indicator in desc or indicator in language:
                return 10
        return 0

    STAR_TIERS = [(50000, 30), (10000, 25), (5000, 20), (1000, 15), (500, 10), (100, 5)]
    DOWNLOAD_TIERS = [(1000000, 30), (100000, 25), (50000, 20), (10000, 15), (5000, 10), (1000, 5)]

    def calculate_relevance(self, item: Dict[str, Any]) -> int:
        """计算相关性评分（0-100）"""
        score = 0

        text_parts = [
            item.get("name", "").lower(),
            item.get("description", "").lower(),
            " ".join(item.get("tags", [])).lower(),
        ]
        text = " ".join(text_parts)

        for keyword, weight in self.ALL_KEYWORDS.items():
            keyword_lower = keyword.lower()
            if keyword_lower in text or re.search(rf"\b{re.escape(keyword_lower)}\b", text):
                score += weight

        metrics = item.get("metrics", {})
        stars = metrics.get("stars", 0) or 0
        downloads = metrics.get("weekly_downloads", 0) or metrics.get("downloads", 0) or 0

        score += self._tiered_score(stars, self.STAR_TIERS)
        score += self._tiered_score(downloads, self.DOWNLOAD_TIERS)
        score += self._calc_freshness_bonus(item.get("updated_at") or item.get("last_updated"))
        score += self._calc_chinese_bonus(item)

        return min(score, 100)

    def categorize(self, score: int) -> str:
        """根据评分分类

        Args:
            score: 相关性评分

        Returns:
            str: 'high_value' / 'medium_value' / 'monitoring'
        """
        if score >= 80:
            return "high_value"
        elif score >= 50:
            return "medium_value"
        return "monitoring"

    def explain_relevance(self, item: Dict[str, Any], score: int) -> str:
        """生成相关性说明

        Args:
            item: 项目信息字典
            score: 相关性评分

        Returns:
            str: 人类可读的相关性说明
        """
        text = " ".join(
            [
                item.get("name", "").lower(),
                item.get("description", "").lower(),
                " ".join(item.get("tags", [])).lower(),
            ]
        )

        matched_domain = [k for k in self.DOMAIN_KEYWORDS if k in text]
        matched_tech = [k for k in self.TECH_KEYWORDS if k in text]
        matched_infra = [k for k in self.INFRA_KEYWORDS if k in text]

        parts = []
        if matched_domain:
            parts.append(f"领域前沿匹配: {', '.join(matched_domain[:5])}")
        if matched_tech:
            parts.append(f"技术引擎相关: {', '.join(matched_tech[:5])}")
        if matched_infra:
            parts.append(f"基础设施相关: {', '.join(matched_infra[:3])}")

        category = self.categorize(score)
        parts.append(f"相关性等级: {category} (评分: {score})")

        return "; ".join(parts) if parts else "无直接关键词匹配，建议持续关注"
