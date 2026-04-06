"""
增强向量嵌入服务（Enhanced Vector Embedding Service）

文字处理工程流A-2的核心组件

功能：
1. 本地BGE模型优先（快速、免费）
2. CLIProxyAI远程API备选（高质量）
3. 批量处理优化
4. 向量质量评估
5. 自动回退机制
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.services.ai_service_adapter import AIServiceAdapter
from backend.services.retrieval.vector import _get_local_model

logger = logging.getLogger(__name__)


class EmbeddingProvider(Enum):
    """嵌入提供商"""

    LOCAL = "local"  # 本地BGE模型
    REMOTE = "remote"  # CLIProxyAI远程API
    HYBRID = "hybrid"  # 混合模式


@dataclass
class EmbeddingResult:
    """嵌入结果"""

    vector: List[float]
    provider: EmbeddingProvider
    dimension: int
    quality_score: float = 1.0
    processing_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "provider": self.provider.value,
            "quality_score": self.quality_score,
            "processing_time": self.processing_time,
        }


@dataclass
class BatchEmbeddingResult:
    """批量嵌入结果"""

    embeddings: List[List[float]]
    provider: EmbeddingProvider
    total_time: float
    avg_time_per_item: float
    quality_scores: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": len(self.embeddings),
            "provider": self.provider.value,
            "total_time": self.total_time,
            "avg_time_per_item": self.avg_time_per_item,
            "avg_quality": np.mean(self.quality_scores) if self.quality_scores else 0.0,
        }


class VectorQualityAssessor:
    """向量质量评估器"""

    @staticmethod
    def assess(vector: List[float]) -> float:
        """评估向量质量

        Args:
            vector: 嵌入向量

        Returns:
            质量分数 (0-1)
        """
        if not vector:
            return 0.0

        arr = np.array(vector)

        # 3. 检查是否有NaN或Inf（优先检查，存在则直接返回0分）
        if np.isnan(arr).any() or np.isinf(arr).any():
            return 0.0

        # 1. 检查向量是否归一化
        norm = np.linalg.norm(arr)
        is_normalized = 0.9 <= norm <= 1.1

        # 2. 检查向量是否有足够的方差
        variance = np.var(arr)
        has_variance = variance > 0.001

        # 综合评分
        scores = []
        if is_normalized:
            scores.append(1.0)
        else:
            scores.append(0.5)  # 部分分数

        if has_variance:
            scores.append(1.0)
        else:
            scores.append(0.0)

        scores.append(1.0)  # 有效向量（无NaN/Inf）

        return sum(scores) / len(scores)

    @staticmethod
    def assess_batch(vectors: List[List[float]]) -> Tuple[float, List[float]]:
        """评估批量向量质量

        Args:
            vectors: 向量列表

        Returns:
            (平均质量分数, 每个向量的质量分数)
        """
        if not vectors:
            return 0.0, []

        scores = [VectorQualityAssessor.assess(v) for v in vectors]
        avg_score = np.mean(scores)

        return avg_score, scores


class EnhancedEmbeddingService:
    """增强嵌入服务"""

    def __init__(
        self,
        preferred_provider: EmbeddingProvider = EmbeddingProvider.LOCAL,
        remote_api_key: Optional[str] = None,
        auto_fallback: bool = True,
    ):
        """初始化服务

        Args:
            preferred_provider: 首选提供商
            remote_api_key: 远程API密钥
            auto_fallback: 是否自动回退
        """
        self.preferred_provider = preferred_provider
        self.auto_fallback = auto_fallback
        self.remote_api_key = remote_api_key

        self._local_model = None
        self._remote_adapter = None

    async def _get_local_model(self):
        """获取本地模型"""
        if self._local_model is None:
            self._local_model = await _get_local_model()
        return self._local_model

    async def _get_remote_adapter(self) -> AIServiceAdapter:
        """获取远程适配器"""
        if self._remote_adapter is None:
            self._remote_adapter = AIServiceAdapter(api_key=self.remote_api_key)
        return self._remote_adapter

    async def embed(
        self, text: str, provider: Optional[EmbeddingProvider] = None
    ) -> EmbeddingResult:
        """生成文本嵌入

        Args:
            text: 输入文本
            provider: 指定提供商（None则使用默认）

        Returns:
            嵌入结果
        """
        import time

        start_time = time.time()

        if not text or not text.strip():
            raise ValueError("输入文本不能为空")

        # 确定使用的提供商
        provider = provider or self.preferred_provider

        try:
            if provider == EmbeddingProvider.LOCAL:
                result = await self._embed_local(text)
            elif provider == EmbeddingProvider.REMOTE:
                result = await self._embed_remote(text)
            else:  # HYBRID
                result = await self._embed_hybrid(text)

            processing_time = time.time() - start_time
            result.processing_time = processing_time

            logger.info(
                f"嵌入生成: provider={provider.value}, time={processing_time:.3f}s, quality={result.quality_score:.2f}"
            )
            return result

        except Exception as e:
            logger.error(f"嵌入生成失败 (provider={provider.value}): {e}")

            # 自动回退到本地模型
            if self.auto_fallback and provider != EmbeddingProvider.LOCAL:
                logger.info("回退到本地模型")
                return await self.embed(text, EmbeddingProvider.LOCAL)
            else:
                raise

    async def _embed_local(self, text: str) -> EmbeddingResult:
        """使用本地模型生成嵌入"""
        model = await self._get_local_model()

        loop = asyncio.get_running_loop()

        def _encode():
            return model.encode(text, normalize_embeddings=True).tolist()

        vector = await loop.run_in_executor(None, _encode)

        # 评估质量
        quality_score = VectorQualityAssessor.assess(vector)

        return EmbeddingResult(
            vector=vector,
            provider=EmbeddingProvider.LOCAL,
            dimension=len(vector),
            quality_score=quality_score,
        )

    async def _embed_remote(self, text: str) -> EmbeddingResult:
        """使用远程API生成嵌入"""
        adapter = await self._get_remote_adapter()

        # 尝试使用远程embedding API
        # 注意：这需要CLIProxyAI支持embedding API
        # 如果不支持，回退到本地
        try:
            # 假设CLIProxyAI支持OpenAI兼容的embedding API
            vector = await adapter.embed(text)

            # 评估质量
            quality_score = VectorQualityAssessor.assess(vector)

            return EmbeddingResult(
                vector=vector,
                provider=EmbeddingProvider.REMOTE,
                dimension=len(vector),
                quality_score=quality_score,
            )
        except Exception as e:
            logger.warning(f"远程嵌入API不可用: {e}，使用本地模型")
            return await self._embed_local(text)

    async def _embed_hybrid(self, text: str) -> EmbeddingResult:
        """混合模式：短文本用远程，长文本用本地"""
        # 对于短文本（<100字符），使用远程API获取更高质量
        # 对于长文本，使用本地模型节省成本
        if len(text) < 100:
            return await self._embed_remote(text)
        else:
            return await self._embed_local(text)

    async def embed_batch(
        self, texts: List[str], provider: Optional[EmbeddingProvider] = None, batch_size: int = 32
    ) -> BatchEmbeddingResult:
        """批量生成嵌入

        Args:
            texts: 输入文本列表
            provider: 指定提供商
            batch_size: 批处理大小

        Returns:
            批量嵌入结果
        """
        import time

        start_time = time.time()

        if not texts:
            raise ValueError("文本列表不能为空")

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return BatchEmbeddingResult(
                embeddings=[],
                provider=provider or self.preferred_provider,
                total_time=0.0,
                avg_time_per_item=0.0,
                quality_scores=[],
            )

        provider = provider or self.preferred_provider

        try:
            if provider == EmbeddingProvider.LOCAL:
                result = await self._embed_batch_local(valid_texts, batch_size)
            elif provider == EmbeddingProvider.REMOTE:
                result = await self._embed_batch_remote(valid_texts, batch_size)
            else:
                # 混合模式：根据文本长度选择
                result = await self._embed_batch_hybrid(valid_texts, batch_size)

            total_time = time.time() - start_time
            result.total_time = total_time
            result.avg_time_per_item = total_time / len(valid_texts)

            # 计算平均质量
            avg_quality = np.mean(result.quality_scores) if result.quality_scores else 0.0

            logger.info(
                f"批量嵌入: count={len(valid_texts)}, provider={provider.value}, "
                f"total_time={total_time:.2f}s, avg_quality={avg_quality:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"批量嵌入失败: {e}")
            if self.auto_fallback and provider != EmbeddingProvider.LOCAL:
                logger.info("回退到本地模型")
                return await self.embed_batch(valid_texts, EmbeddingProvider.LOCAL, batch_size)
            else:
                raise

    async def _embed_batch_local(self, texts: List[str], batch_size: int) -> BatchEmbeddingResult:
        """本地批量嵌入"""
        model = await self._get_local_model()
        loop = asyncio.get_event_loop()

        all_embeddings = []
        all_quality_scores = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            def _encode_batch(b=batch):
                return model.encode(
                    b, normalize_embeddings=True, batch_size=batch_size
                ).tolist()

            embeddings = await loop.run_in_executor(None, _encode_batch)
            all_embeddings.extend(embeddings)

            # 评估质量
            quality_scores = [VectorQualityAssessor.assess(emb) for emb in embeddings]
            all_quality_scores.extend(quality_scores)

            logger.debug(f"批次 {i // batch_size + 1}: {len(batch)} 个文本")

        return BatchEmbeddingResult(
            embeddings=all_embeddings,
            provider=EmbeddingProvider.LOCAL,
            total_time=0.0,  # 会在上层设置
            avg_time_per_item=0.0,
            quality_scores=all_quality_scores,
        )

    async def _embed_batch_remote(self, texts: List[str], batch_size: int) -> BatchEmbeddingResult:
        """远程批量嵌入"""
        # 注意：大多数远程API有速率限制，需要控制并发
        adapter = await self._get_remote_adapter()

        all_embeddings = []
        all_quality_scores = []

        # 串行调用以避免速率限制
        for text in texts:
            try:
                vector = await adapter.embed(text)
                all_embeddings.append(vector)
                all_quality_scores.append(VectorQualityAssessor.assess(vector))
            except Exception as e:
                logger.warning(f"远程嵌入失败，使用本地: {e}")
                local_result = await self._embed_local(text)
                all_embeddings.append(local_result.vector)
                all_quality_scores.append(local_result.quality_score)

        return BatchEmbeddingResult(
            embeddings=all_embeddings,
            provider=EmbeddingProvider.REMOTE,
            total_time=0.0,
            avg_time_per_item=0.0,
            quality_scores=all_quality_scores,
        )

    async def _embed_batch_hybrid(self, texts: List[str], batch_size: int) -> BatchEmbeddingResult:
        """混合批量嵌入"""
        short_texts = []
        long_texts = []
        short_indices = []
        long_indices = []

        for i, text in enumerate(texts):
            if len(text) < 100:
                short_texts.append(text)
                short_indices.append(i)
            else:
                long_texts.append(text)
                long_indices.append(i)

        # 短文本用远程，长文本用本地
        all_embeddings = [None] * len(texts)
        all_quality_scores = [0.0] * len(texts)

        if short_texts:
            short_result = await self._embed_batch_remote(short_texts, batch_size)
            for idx, emb, quality in zip(
                short_indices, short_result.embeddings, short_result.quality_scores
            ):
                all_embeddings[idx] = emb
                all_quality_scores[idx] = quality

        if long_texts:
            long_result = await self._embed_batch_local(long_texts, batch_size)
            for idx, emb, quality in zip(
                long_indices, long_result.embeddings, long_result.quality_scores
            ):
                all_embeddings[idx] = emb
                all_quality_scores[idx] = quality

        return BatchEmbeddingResult(
            embeddings=all_embeddings,
            provider=EmbeddingProvider.HYBRID,
            total_time=0.0,
            avg_time_per_item=0.0,
            quality_scores=all_quality_scores,
        )


class TextVectorizer:
    """文本向量化器（高层API）"""

    def __init__(
        self,
        preferred_provider: EmbeddingProvider = EmbeddingProvider.LOCAL,
        remote_api_key: Optional[str] = None,
    ):
        """初始化向量化器

        Args:
            preferred_provider: 首选提供商
            remote_api_key: 远程API密钥
        """
        self.embedding_service = EnhancedEmbeddingService(
            preferred_provider=preferred_provider, remote_api_key=remote_api_key
        )

    async def vectorize_text_blocks(
        self, text_blocks: List[str], batch_size: int = 32
    ) -> Tuple[List[List[float]], Dict[str, Any]]:
        """向量化文本块

        Args:
            text_blocks: 文本块列表
            batch_size: 批处理大小

        Returns:
            (向量列表, 统计信息)
        """
        if not text_blocks:
            return [], {}

        result = await self.embedding_service.embed_batch(texts=text_blocks, batch_size=batch_size)

        stats = result.to_dict()
        stats["input_count"] = len(text_blocks)
        stats["output_count"] = len(result.embeddings)

        return result.embeddings, stats

    async def vectorize_single(self, text: str) -> List[float]:
        """向量化单个文本

        Args:
            text: 输入文本

        Returns:
            向量
        """
        result = await self.embedding_service.embed(text)
        return result.vector


__all__ = [
    "EmbeddingProvider",
    "EmbeddingResult",
    "BatchEmbeddingResult",
    "VectorQualityAssessor",
    "EnhancedEmbeddingService",
    "TextVectorizer",
]
