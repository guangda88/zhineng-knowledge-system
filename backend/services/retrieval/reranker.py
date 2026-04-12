"""
Cross-Encoder Reranker 模块
在 hybrid RRF 粗排后，用 cross-encoder 对 top-N 结果精排

依赖：sentence-transformers（已安装，与 BGE embedding 共用生态）
模型：BAAI/bge-reranker-v2-m3（推荐，与 bge-small-zh 同生态）
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_RERANKER_INSTANCE = None
_RERANKER_LOCK = asyncio.Lock()

_DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"
_DEFAULT_TOP_N = 20
_FALLBACK_TOP_N = 10


async def _get_reranker():
    """延迟加载 reranker 模型（单例）"""
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is not None:
        return _RERANKER_INSTANCE

    async with _RERANKER_LOCK:
        if _RERANKER_INSTANCE is not None:
            return _RERANKER_INSTANCE

        model_name = os.getenv("RERANKER_MODEL", _DEFAULT_MODEL)
        logger.info(f"Loading reranker model: {model_name}")

        loop = asyncio.get_running_loop()

        def _load():
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(model_name, device="cpu")
            return model

        _RERANKER_INSTANCE = await loop.run_in_executor(None, _load)
        logger.info(f"Reranker model loaded: {model_name}")

    return _RERANKER_INSTANCE


class Reranker:
    """
    Cross-Encoder 精排器

    对检索结果做二次排序，提升 top-k 的精确度。
    在 hybrid RRF 之后、返回给用户之前插入。

    Args:
        top_n: 对前 N 条结果做 rerank（GPU: 20, CPU: 10）
        max_length: 每对 (query, doc) 的最大 token 长度
    """

    def __init__(
        self,
        top_n: int = _DEFAULT_TOP_N,
        max_length: int = 512,
    ):
        self.top_n = top_n
        self.max_length = max_length
        self._model = None
        self._cpu_fallback = False

    async def _ensure_model(self):
        if self._model is None:
            self._model = await _get_reranker()
        return self._model

    async def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        对检索结果做 cross-encoder 精排

        Args:
            query: 用户查询
            results: RRF 融合后的检索结果
            top_k: 最终返回数量

        Returns:
            精排后的结果（按 rerank_score 降序）
        """
        if not results:
            return results

        candidates = results[: self.top_n]

        if len(candidates) <= 1:
            return candidates

        model = await self._ensure_model()

        pairs = []
        for r in candidates:
            content = r.get("content", "")
            title = r.get("title", "")
            doc_text = f"{title}\n{content}" if title else content
            if len(doc_text) > 500:
                doc_text = doc_text[:500]
            pairs.append([query, doc_text])

        loop = asyncio.get_running_loop()

        def _predict():
            return model.predict(pairs, show_progress_bar=False)

        try:
            scores = await loop.run_in_executor(None, _predict)
        except Exception as e:
            logger.warning(f"Reranker 推理失败，返回原始排序: {e}")
            return results[:top_k]

        for i, r in enumerate(candidates):
            r["rerank_score"] = float(scores[i])

        candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

        reranked = candidates[:top_k]

        remaining = results[self.top_n:]
        reranked.extend(remaining)

        logger.info(
            f"Reranker: query='{query[:30]}...', "
            f"candidates={len(candidates)}, "
            f"top_score={candidates[0].get('rerank_score', 0):.4f}"
        )

        return reranked


def create_reranker(top_n: Optional[int] = None) -> Reranker:
    """
    创建 Reranker 实例

    自动检测 CPU/GPU 环境调整 top_n：
    - 有 GPU：top_n=20（默认）
    - 纯 CPU：top_n=10（降级，减少延迟）
    """
    if top_n is None:
        try:
            import torch

            if torch.cuda.is_available():
                top_n = _DEFAULT_TOP_N
            else:
                top_n = _FALLBACK_TOP_N
        except ImportError:
            top_n = _FALLBACK_TOP_N

    return Reranker(top_n=top_n)
