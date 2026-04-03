"""HuggingFace趋势采集器

采集HuggingFace上与灵知系统相关的模型和数据集趋势。
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.services.intelligence.base import BaseCollector, CollectionResult, IntelligenceItem
from backend.services.intelligence.relevance_analyzer import RelevanceAnalyzer

logger = logging.getLogger(__name__)

# 模型搜索关键词：中文嵌入/中文大模型/中文语音/中文NLP
MODEL_KEYWORDS = [
    "bge",
    "chinese-embedding",
    "text-embedding",
    "chinese",
    "sentence-transformers",
    "cross-encoder",
    "reranker",
    "tts",
    "speech-recognition",
    "whisper",
    "chinese-qa",
    "chinese-lm",
    "classical-chinese",
    "ancient-chinese",
    "chinese-ner",
]

# 数据集搜索关键词：中文语料/古籍/中医/知识问答
DATASET_KEYWORDS = [
    "chinese-corpus",
    "chinese-qa",
    "traditional-chinese-medicine",
    "chinese-knowledge",
    "classical-chinese",
    "ancient-chinese",
    "chinese-ner",
    "embedding-training",
    "rag-dataset",
    "chinese-text",
    "qa-dataset",
    "hanzi",
    "wenyanwen",
]


class HuggingFaceCollector(BaseCollector):
    """HuggingFace趋势采集器

    采集HuggingFace Hub上与灵知系统相关的模型和数据集，
    按下载量/点赞数排序，进行相关性评分。

    Args:
        min_downloads: 最低下载量阈值
        max_items_per_keyword: 每个关键词最大采集数量
    """

    source = "huggingface"

    def __init__(
        self,
        min_downloads: int = 100,
        max_items_per_keyword: int = 10,
    ):
        self.min_downloads = min_downloads
        self.max_items_per_keyword = max_items_per_keyword
        self.analyzer = RelevanceAnalyzer()

    async def collect(self, keywords: Optional[List[str]] = None) -> CollectionResult:
        """执行HuggingFace趋势采集

        Args:
            keywords: 未使用（HuggingFace使用内置关键词）

        Returns:
            CollectionResult: 采集结果
        """
        start_time = time.time()
        result = CollectionResult()
        seen_ids: set = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 采集模型
            for keyword in MODEL_KEYWORDS:
                try:
                    models = await self._search_models(client, keyword)
                    for model in models:
                        model_id = model.get("id", "")
                        if model_id in seen_ids:
                            continue
                        seen_ids.add(model_id)

                        downloads = model.get("downloads", 0)
                        if downloads < self.min_downloads:
                            continue

                        item = self._model_to_item(model)
                        result.items.append(item)
                        result.total_found += 1

                except Exception as e:
                    error_msg = f"HuggingFace模型搜索 '{keyword}' 失败: {e}"
                    logger.warning(error_msg)
                    result.errors.append(error_msg)

            # 采集数据集
            for keyword in DATASET_KEYWORDS:
                try:
                    datasets = await self._search_datasets(client, keyword)
                    for dataset in datasets:
                        dataset_id = dataset.get("id", "")
                        if dataset_id in seen_ids:
                            continue
                        seen_ids.add(dataset_id)

                        downloads = dataset.get("downloads", 0)
                        if downloads < self.min_downloads:
                            continue

                        item = self._dataset_to_item(dataset)
                        result.items.append(item)
                        result.total_found += 1

                except Exception as e:
                    error_msg = f"HuggingFace数据集搜索 '{keyword}' 失败: {e}"
                    logger.warning(error_msg)
                    result.errors.append(error_msg)

        result.items.sort(key=lambda x: x.relevance_score, reverse=True)
        result.duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"HuggingFace采集完成: {result.total_found} 条, 耗时 {result.duration_ms}ms")
        return result

    async def _search_models(self, client: httpx.AsyncClient, keyword: str) -> List[Dict[str, Any]]:
        """搜索HuggingFace模型

        Args:
            client: httpx异步客户端
            keyword: 搜索关键词

        Returns:
            List[Dict]: 模型信息列表
        """
        url = "https://huggingface.co/api/models"
        params = {
            "search": keyword,
            "sort": "downloads",
            "direction": "-1",
            "limit": self.max_items_per_keyword,
        }

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _search_datasets(
        self, client: httpx.AsyncClient, keyword: str
    ) -> List[Dict[str, Any]]:
        """搜索HuggingFace数据集

        Args:
            client: httpx异步客户端
            keyword: 搜索关键词

        Returns:
            List[Dict]: 数据集信息列表
        """
        url = "https://huggingface.co/api/datasets"
        params = {
            "search": keyword,
            "sort": "downloads",
            "direction": "-1",
            "limit": self.max_items_per_keyword,
        }

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _model_to_item(self, model: Dict[str, Any]) -> IntelligenceItem:
        """将HuggingFace模型转换为IntelligenceItem"""
        model_id = model.get("id", "")
        tags = model.get("tags", []) or []

        item_dict = {
            "name": model_id,
            "description": (
                model.get("pipeline_tag", "") or model.get("tags", [""])[0] if tags else ""
            ),
            "tags": tags,
            "metrics": {
                "downloads": model.get("downloads", 0),
                "likes": model.get("likes", 0),
                "model_type": model.get("pipeline_tag", ""),
                "private": model.get("private", False),
            },
            "language": ", ".join(model.get("language", []) or []),
            "updated_at": model.get("lastModified", ""),
        }

        score = self.analyzer.calculate_relevance(item_dict)
        category = self.analyzer.categorize(score)
        reason = self.analyzer.explain_relevance(item_dict, score)

        _hf_type = "models" if "models" in model.get("_id", "") else "models"  # noqa: F841

        return IntelligenceItem(
            source="huggingface",
            source_id=f"model:{model_id}",
            name=model_id,
            description=f"[Model] {item_dict['description']}",
            url=f"https://huggingface.co/{model_id}",
            language=item_dict["language"],
            tags=tags,
            metrics=item_dict["metrics"],
            relevance_score=score,
            relevance_category=category,
            relevance_reason=reason,
        )

    def _dataset_to_item(self, dataset: Dict[str, Any]) -> IntelligenceItem:
        """将HuggingFace数据集转换为IntelligenceItem"""
        dataset_id = dataset.get("id", "")
        tags = dataset.get("tags", []) or []

        item_dict = {
            "name": dataset_id,
            "description": dataset.get("tags", [""])[0] if tags else "dataset",
            "tags": tags,
            "metrics": {
                "downloads": dataset.get("downloads", 0),
                "likes": dataset.get("likes", 0),
                "dataset_size": dataset.get("size_categories", ""),
            },
            "language": ", ".join(dataset.get("language", []) or []),
            "updated_at": dataset.get("lastModified", ""),
        }

        score = self.analyzer.calculate_relevance(item_dict)
        category = self.analyzer.categorize(score)
        reason = self.analyzer.explain_relevance(item_dict, score)

        return IntelligenceItem(
            source="huggingface",
            source_id=f"dataset:{dataset_id}",
            name=dataset_id,
            description=f"[Dataset] {item_dict['description']}",
            url=f"https://huggingface.co/datasets/{dataset_id}",
            language=item_dict["language"],
            tags=tags,
            metrics=item_dict["metrics"],
            relevance_score=score,
            relevance_category=category,
            relevance_reason=reason,
        )
