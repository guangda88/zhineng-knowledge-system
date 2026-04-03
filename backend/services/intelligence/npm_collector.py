"""npm趋势采集器

采集npm上与灵知系统相关的JavaScript/TypeScript包趋势。
参考LingFlow的npm_trend_collector.py，适配为异步版本。
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.services.intelligence.base import BaseCollector, CollectionResult, IntelligenceItem
from backend.services.intelligence.relevance_analyzer import RelevanceAnalyzer

logger = logging.getLogger(__name__)

# 灵知系统领域关键词
DEFAULT_KEYWORDS = [
    # 领域前沿
    "chinese-nlp",
    "chinese-tokenizer",
    "chinese-segmentation",
    "chinese-ocr",
    "hanzi",
    "pinyin",
    # 技术引擎
    "vector-search",
    "semantic-search",
    "text-embedding",
    "knowledge-graph",
    "rag",
    "llm",
    "ai-agent",
    "text-to-speech",
    "tts",
    "speech-recognition",
    "search-engine",
]


class NPMCollector(BaseCollector):
    """npm趋势采集器

    通过npm Registry API搜索相关包，按下载量过滤，
    进行相关性评分。

    Args:
        min_weekly_downloads: 最低周下载量阈值
        min_dependents: 最低依赖数阈值
        recent_days: 最近更新天数阈值
    """

    source = "npm"

    def __init__(
        self,
        min_weekly_downloads: int = 500,
        min_dependents: int = 3,
        recent_days: int = 180,
    ):
        self.min_weekly_downloads = min_weekly_downloads
        self.min_dependents = min_dependents
        self.recent_days = recent_days
        self.analyzer = RelevanceAnalyzer()

    async def collect(self, keywords: Optional[List[str]] = None) -> CollectionResult:
        """执行npm趋势采集

        Args:
            keywords: 搜索关键词列表

        Returns:
            CollectionResult: 采集结果
        """
        start_time = time.time()
        result = CollectionResult()
        search_keywords = keywords or DEFAULT_KEYWORDS
        seen_names: set = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for keyword in search_keywords:
                try:
                    packages = await self._search_packages(client, keyword)
                    for pkg in packages:
                        name = pkg.get("package", {}).get("name", "")
                        if name in seen_names:
                            continue
                        seen_names.add(name)

                        package_data = pkg.get("package", {})
                        score_detail = pkg.get("score", {})
                        search_score = score_detail.get("detail", {})

                        # 获取下载量
                        downloads = await self._get_downloads(client, name)

                        # 质量过滤
                        if downloads < self.min_weekly_downloads:
                            continue

                        item = self._to_intelligence_item(package_data, downloads, search_score)
                        result.items.append(item)
                        result.total_found += 1

                except Exception as e:
                    error_msg = f"npm搜索 '{keyword}' 失败: {e}"
                    logger.warning(error_msg)
                    result.errors.append(error_msg)

        result.items.sort(key=lambda x: x.relevance_score, reverse=True)
        result.duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"npm采集完成: {result.total_found} 条, 耗时 {result.duration_ms}ms")
        return result

    async def _search_packages(
        self, client: httpx.AsyncClient, keyword: str, size: int = 15
    ) -> List[Dict[str, Any]]:
        """搜索npm包

        Args:
            client: httpx异步客户端
            keyword: 搜索关键词
            size: 返回数量

        Returns:
            List[Dict]: 包信息列表
        """
        url = "https://registry.npmjs.org/-/v1/search"
        params = {"text": keyword, "size": size}

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("objects", [])

    async def _get_downloads(self, client: httpx.AsyncClient, package_name: str) -> int:
        """获取包的周下载量

        Args:
            client: httpx异步客户端
            package_name: 包名

        Returns:
            int: 周下载量
        """
        try:
            url = f"https://api.npmjs.org/downloads/point/last-week/{package_name}"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data.get("downloads", 0)
        except Exception:
            return 0

    def _to_intelligence_item(
        self,
        package_data: Dict[str, Any],
        downloads: int,
        search_score: Dict[str, Any],
    ) -> IntelligenceItem:
        """将npm包数据转换为IntelligenceItem

        Args:
            package_data: npm搜索结果中的package字段
            downloads: 周下载量
            search_score: npm搜索评分

        Returns:
            IntelligenceItem: 标准化情报条目
        """
        name = package_data.get("name", "")
        keywords_list = package_data.get("keywords", []) or []

        item_dict = {
            "name": name,
            "description": package_data.get("description", "") or "",
            "tags": keywords_list if isinstance(keywords_list, list) else [],
            "metrics": {
                "weekly_downloads": downloads,
                "version": package_data.get("version", ""),
                "search_quality": search_score.get("quality", 0),
                "search_popularity": search_score.get("popularity", 0),
            },
            "language": "JavaScript",
            "updated_at": package_data.get("date", ""),
        }

        score = self.analyzer.calculate_relevance(item_dict)
        category = self.analyzer.categorize(score)
        reason = self.analyzer.explain_relevance(item_dict, score)

        return IntelligenceItem(
            source="npm",
            source_id=name,
            name=name,
            description=package_data.get("description", "") or "",
            url=f"https://www.npmjs.com/package/{name}",
            language="JavaScript",
            tags=keywords_list if isinstance(keywords_list, list) else [],
            metrics=item_dict["metrics"],
            relevance_score=score,
            relevance_category=category,
            relevance_reason=reason,
        )
