"""
处理器抽象层

提供统一的数据处理接口，支持通过处理器链对数据进行逐步处理。
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from backend.textbook_processing.autonomous_processor import (
    AutonomousTextbookProcessor,
    ProcessingResult,
)

logger = logging.getLogger(__name__)


class Processor(ABC):
    """处理器抽象基类"""

    @abstractmethod
    async def process(self, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """处理数据

        Args:
            data: 输入数据
            **kwargs: 额外参数

        Returns:
            处理后的数据
        """


class TOCProcessor(Processor):
    """TOC处理器

    从文本中提取目录结构，可选地进行扩展。
    """

    def __init__(
        self, auto_expand: bool = True, target_depth: int = 3, api_key: Optional[str] = None
    ):
        """
        Args:
            auto_expand: 是否自动扩展TOC
            target_depth: 目标TOC深度
            api_key: DeepSeek API密钥
        """
        self.auto_expand = auto_expand
        self.target_depth = target_depth
        self.api_key = api_key
        self._processor: Optional[AutonomousTextbookProcessor] = None

    def _get_processor(self) -> AutonomousTextbookProcessor:
        """获取自主处理器实例"""
        if self._processor is None:
            self._processor = AutonomousTextbookProcessor(
                api_key=self.api_key, target_toc_depth=self.target_depth
            )
        return self._processor

    async def process(self, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """处理TOC

        Args:
            data: 文本数据列表
            **kwargs: 额外参数

        Returns:
            包含TOC的数据
        """
        processor = self._get_processor()

        results = []
        for item in data:
            try:
                # 调用自主处理器处理文本
                result: ProcessingResult = await processor.process(
                    textbook_path=item.get("path", ""), textbook_title=item.get("name", "")
                )

                # 转换TOC为字典格式
                toc_list = [toc.to_dict() for toc in result.toc_items]
                block_list = [block.to_dict() for block in result.text_blocks]

                # 合并到原始数据
                processed_item = item.copy()
                processed_item["toc"] = toc_list
                processed_item["blocks"] = block_list
                processed_item["statistics"] = result.statistics

                results.append(processed_item)

                logger.info(
                    f"Processed TOC for {item.get('name', 'unknown')}: {len(toc_list)} items"
                )

            except Exception as e:
                logger.error(f"Failed to process TOC for {item.get('name', 'unknown')}: {e}")
                # 保留原始数据
                results.append(item)

        return results


class SegmentProcessor(Processor):
    """文本分割处理器

    将文本分割为语义边界清晰的文本块。
    """

    def __init__(self, max_block_size: int = 300, min_block_size: int = 100):
        """
        Args:
            max_block_size: 最大文本块大小
            min_block_size: 最小文本块大小
        """
        self.max_block_size = max_block_size
        self.min_block_size = min_block_size
        self._processor: Optional[AutonomousTextbookProcessor] = None

    def _get_processor(self) -> AutonomousTextbookProcessor:
        """获取自主处理器实例"""
        if self._processor is None:
            self._processor = AutonomousTextbookProcessor(max_block_chars=self.max_block_size)
        return self._processor

    async def process(self, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """处理文本分割

        Args:
            data: 文本数据列表
            **kwargs: 额外参数

        Returns:
            包含文本块的数据
        """
        # 注意：文本分割已经在TOCProcessor中完成
        # 这个处理器主要用于验证或重新分割

        results = []
        for item in data:
            try:
                # 如果已经有blocks，则验证块大小
                if "blocks" in item:
                    blocks = item["blocks"]
                    valid_blocks = []
                    for block in blocks:
                        content = block.get("content", "")
                        if self.min_block_size <= len(content) <= self.max_block_size * 2:
                            valid_blocks.append(block)
                        else:
                            # 重新分割大块
                            logger.warning(
                                f"Block size {len(content)} exceeds limit, need re-segmentation"
                            )

                    processed_item = item.copy()
                    processed_item["blocks"] = valid_blocks
                    results.append(processed_item)
                else:
                    # 如果没有blocks，则分割文本
                    processor = self._get_processor()
                    result = await processor.process(
                        textbook_path=item.get("path", ""), textbook_title=item.get("name", "")
                    )
                    block_list = [block.to_dict() for block in result.text_blocks]

                    processed_item = item.copy()
                    processed_item["blocks"] = block_list
                    results.append(processed_item)

            except Exception as e:
                logger.error(f"Failed to segment text for {item.get('name', 'unknown')}: {e}")
                results.append(item)

        return results


class QualityValidator(Processor):
    """质量验证处理器

    验证数据质量，检查缺失字段、长度限制等。
    """

    def __init__(self, max_content_length: int = 10000, min_content_length: int = 10):
        """
        Args:
            max_content_length: 最大内容长度
            min_content_length: 最小内容长度
        """
        self.max_content_length = max_content_length
        self.min_content_length = min_content_length

    async def process(self, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """验证数据质量

        Args:
            data: 数据列表
            **kwargs: 额外参数

        Returns:
            验证后的数据
        """
        results = []
        validation_errors = []

        for idx, item in enumerate(data):
            valid = True
            errors = []

            # 检查必需字段
            if "content" not in item:
                errors.append("Missing 'content' field")
                valid = False
            elif not isinstance(item["content"], str):
                errors.append("'content' must be a string")
                valid = False
            else:
                content_length = len(item["content"])
                if content_length < self.min_content_length:
                    errors.append(
                        f"Content too short: {content_length} < {self.min_content_length}"
                    )
                if content_length > self.max_content_length:
                    errors.append(f"Content too long: {content_length} > {self.max_content_length}")

            # 检查TOC（如果存在）
            if "toc" in item:
                if not isinstance(item["toc"], list):
                    errors.append("'toc' must be a list")
                    valid = False

            # 检查blocks（如果存在）
            if "blocks" in item:
                if not isinstance(item["blocks"], list):
                    errors.append("'blocks' must be a list")
                    valid = False

            if valid:
                results.append(item)
            else:
                validation_errors.append(
                    {
                        "index": idx,
                        "item": item.get("name", item.get("path", "unknown")),
                        "errors": errors,
                    }
                )
                logger.warning(f"Validation failed for item {idx}: {', '.join(errors)}")

        if validation_errors:
            logger.warning(f"Validation completed: {len(results)}/{len(data)} items passed")
        else:
            logger.info(f"Validation completed: all {len(data)} items passed")

        return results


class VectorEmbedder(Processor):
    """向量嵌入处理器

    为文本内容生成向量嵌入。
    """

    def __init__(self, embedding_service_url: Optional[str] = None):
        """
        Args:
            embedding_service_url: 嵌入服务URL（备用方案）
        """
        self.embedding_service_url = embedding_service_url or os.getenv(
            "EMBEDDING_SERVICE_URL", "http://localhost:8001"
        )

    async def process(self, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """生成向量嵌入

        Args:
            data: 数据列表
            **kwargs: 额外参数

        Returns:
            包含向量嵌入的数据
        """
        items_to_embed = []
        indices_to_embed = []
        for i, item in enumerate(data):
            if "embedding" in item:
                continue
            content = item.get("content", "")
            if content and content.strip():
                items_to_embed.append(content)
                indices_to_embed.append(i)

        if items_to_embed:
            embeddings = await self._generate_embeddings(items_to_embed)
            for idx, embedding in zip(indices_to_embed, embeddings):
                data[idx]["embedding"] = embedding

        return data

    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """生成嵌入向量，优先使用本地BGE模型，备用远程服务"""
        try:
            from backend.core.database import get_db_pool

            pool = get_db_pool()
            if pool:
                from backend.services.retrieval.vector import VectorRetriever

                retriever = VectorRetriever(pool)
                return await retriever.embed_batch(texts)
        except Exception as e:
            logger.warning(f"本地BGE模型不可用，尝试嵌入服务: {e}")

        return await self._embed_via_service(texts)

    async def _embed_via_service(self, texts: List[str]) -> List[List[float]]:
        """通过嵌入服务生成嵌入向量"""
        import httpx

        embeddings = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for text in texts:
                try:
                    resp = await client.post(
                        f"{self.embedding_service_url}/embed", json={"text": text}
                    )
                    if resp.status_code == 200:
                        embeddings.append(resp.json()["embedding"])
                    else:
                        logger.error(f"嵌入服务返回 {resp.status_code}")
                        embeddings.append(None)
                except Exception as e:
                    logger.error(f"嵌入服务连接失败: {e}")
                    embeddings.append(None)
        return embeddings
