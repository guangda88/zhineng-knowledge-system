"""GitHub趋势采集器

采集GitHub上与灵知系统相关的开源项目趋势。
参考LingFlow的github_trend_collector.py，适配为异步版本。
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.services.intelligence.base import BaseCollector, CollectionResult, IntelligenceItem
from backend.services.intelligence.relevance_analyzer import RelevanceAnalyzer

logger = logging.getLogger(__name__)

# 灵知系统领域关键词：领域前沿 + 技术引擎 + 基础设施
DEFAULT_KEYWORDS = [
    # 领域前沿：古籍/中医/气功/数字人文
    "classical-chinese",
    "ancient-chinese-text",
    "chinese-ocr",
    "hanzi-recognition",
    "digital-humanities",
    "traditional-chinese-medicine",
    "chinese-medicine-nlp",
    "chinese-ner",
    "chinese-knowledge-graph",
    # 技术引擎：RAG/嵌入/中文大模型
    "rag",
    "graphrag",
    "knowledge-graph",
    "vector-search",
    "semantic-search",
    "chinese-embedding",
    "bge",
    "deepseek",
    "qwen",
    "chatglm",
    "chinese-llm",
    # 通用技术
    "text-to-speech",
    "chinese-speech",
    "hybrid-search",
]


class GitHubCollector(BaseCollector):
    """GitHub趋势采集器

    通过GitHub Search API搜索相关仓库，按star数排序，
    过滤后进行相关性评分。

    Args:
        token: 可选的GitHub Personal Access Token，提高API限制
        min_stars: 最低star数阈值
        recent_days: 最近活跃天数阈值
    """

    source = "github"

    def __init__(
        self,
        token: Optional[str] = None,
        min_stars: int = 100,
        recent_days: int = 90,
    ):
        self.token = token
        self.min_stars = min_stars
        self.recent_days = recent_days
        self.analyzer = RelevanceAnalyzer()
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    async def collect(self, keywords: Optional[List[str]] = None) -> CollectionResult:
        """执行GitHub趋势采集

        Args:
            keywords: 搜索关键词列表，为空时使用默认关键词

        Returns:
            CollectionResult: 采集结果
        """
        start_time = time.time()
        result = CollectionResult()
        search_keywords = keywords or DEFAULT_KEYWORDS
        seen_ids: set = set()

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            for keyword in search_keywords:
                try:
                    repos = await self._search_repositories(client, keyword)
                    for repo in repos:
                        repo_id = str(repo.get("id", ""))
                        full_name = repo.get("full_name", "")

                        if repo_id in seen_ids or full_name in seen_ids:
                            continue

                        if repo.get("stargazers_count", 0) < self.min_stars:
                            continue

                        seen_ids.add(repo_id)
                        seen_ids.add(full_name)

                        item = self._to_intelligence_item(repo)
                        result.items.append(item)
                        result.total_found += 1

                except Exception as e:
                    error_msg = f"GitHub搜索 '{keyword}' 失败: {e}"
                    logger.warning(error_msg)
                    result.errors.append(error_msg)

        # 按相关性排序
        result.items.sort(key=lambda x: x.relevance_score, reverse=True)
        result.duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"GitHub采集完成: {result.total_found} 条, 耗时 {result.duration_ms}ms")
        return result

    async def _search_repositories(
        self, client: httpx.AsyncClient, keyword: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索GitHub仓库

        Args:
            client: httpx异步客户端
            keyword: 搜索关键词
            max_results: 最大返回数量

        Returns:
            List[Dict]: 仓库信息列表
        """
        url = "https://api.github.com/search/repositories"
        params = {
            "q": keyword,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results,
        }

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])

    def _to_intelligence_item(self, repo: Dict[str, Any]) -> IntelligenceItem:
        """将GitHub仓库数据转换为IntelligenceItem

        Args:
            repo: GitHub API返回的仓库信息

        Returns:
            IntelligenceItem: 标准化的情报条目
        """
        full_name = repo.get("full_name", "")
        topics = repo.get("topics", [])

        item_dict = {
            "name": repo.get("name", ""),
            "description": repo.get("description", "") or "",
            "tags": topics,
            "metrics": {
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
                "updated_at": repo.get("updated_at", ""),
            },
            "language": repo.get("language", ""),
            "updated_at": repo.get("updated_at", ""),
        }

        score = self.analyzer.calculate_relevance(item_dict)
        category = self.analyzer.categorize(score)
        reason = self.analyzer.explain_relevance(item_dict, score)

        return IntelligenceItem(
            source="github",
            source_id=full_name,
            name=full_name,
            description=repo.get("description", "") or "",
            url=repo.get("html_url", ""),
            language=repo.get("language", "") or "",
            tags=topics,
            metrics=item_dict["metrics"],
            relevance_score=score,
            relevance_category=category,
            relevance_reason=reason,
        )
