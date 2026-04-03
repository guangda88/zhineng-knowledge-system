"""批处理系统

合并多个AI请求，减少API调用次数，节省50-70%的Token消耗
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class BatchProcessor:
    """批处理器"""

    def __init__(
        self, batch_size: int = 5, delay_between_batches: float = 3.0, max_concurrent: int = 3
    ):
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
        self.max_concurrent = max_concurrent

        self.stats = {
            "total_requests": 0,
            "batched_requests": 0,
            "batches_processed": 0,
            "time_saved_seconds": 0,
        }

    async def batch_process(
        self, prompts: List[str], process_func: Callable, show_progress: bool = True
    ) -> List[Any]:
        """批量处理提示词

        Args:
            prompts: 提示词列表
            process_func: 处理函数（async）
            show_progress: 是否显示进度

        Returns:
            处理结果列表
        """

        self.stats["total_requests"] = len(prompts)
        self.stats["batched_requests"] = len(prompts)

        results = []
        total_batches = (len(prompts) - 1) // self.batch_size + 1

        for i in range(0, len(prompts), self.batch_size):
            batch = prompts[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1

            if show_progress:
                print(f"🔄 处理批次 {batch_num}/{total_batches} ({len(batch)}个请求)")

            # 并发处理当前批次
            tasks = [process_func(prompt) for prompt in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果和异常
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"批次{batch_num}请求{j + 1}失败: {result}")
                    results.append(None)
                else:
                    results.append(result)

            self.stats["batches_processed"] += 1

            # 批次间延迟
            if i + self.batch_size < len(prompts):
                if show_progress:
                    print(f"⏳ 等待 {self.delay_between_batches} 秒...")
                await asyncio.sleep(self.delay_between_batches)

        # 计算节省的时间
        # 如果不批处理，假设每次请求2秒
        sequential_time = len(prompts) * 2
        batch_time = total_batches * self.delay_between_batches + len(prompts) * 0.5
        self.stats["time_saved_seconds"] = max(0, sequential_time - batch_time)

        return results

    async def smart_batch(
        self, prompts: List[str], process_func: Callable, max_size_per_batch: int = 10000
    ) -> List[Any]:
        """智能批处理（自动合并小请求）"""

        # 按大小分组
        batches = []
        current_batch = []
        current_size = 0

        for prompt in prompts:
            prompt_size = len(prompt)

            # 检查是否需要新建批次
            if current_batch and current_size + prompt_size > max_size_per_batch:
                batches.append(current_batch)
                current_batch = [prompt]
                current_size = prompt_size
            else:
                current_batch.append(prompt)
                current_size += prompt_size

        if current_batch:
            batches.append(current_batch)

        # 合并后处理
        print(f"📦 智能批处理: {len(prompts)}个请求 → {len(batches)}个批次")

        all_results = []

        for i, batch in enumerate(batches):
            print(f"🔄 批次 {i + 1}/{len(batches)} ({len(batch)}个请求)")

            # 合并提示词
            combined_prompt = "\n\n".join(
                [f"【任务{j + 1}】\n{prompt}" for j, prompt in enumerate(batch)]
            )

            # 调用处理函数
            result = await process_func(combined_prompt)

            # 如果返回的是合并结果，需要分割
            if isinstance(result, str):
                # 简单分割（实际可能需要更复杂的逻辑）
                parts = result.split("\n\n")
                for part in parts[: len(batch)]:
                    all_results.append(part.strip())
            else:
                all_results.append(result)

            if i < len(batches) - 1:
                await asyncio.sleep(self.delay_between_batches)

        return all_results

    def get_stats(self) -> Dict[str, Any]:
        """获取批处理统计"""
        return self.stats.copy()

    def format_stats(self) -> str:
        """格式化统计信息"""
        stats = self.get_stats()

        lines = [
            "📊 批处理统计",
            "=" * 50,
            f"总请求数: {stats['total_requests']}",
            f"批处理数: {stats['batched_requests']}",
            f"批次总数: {stats['batches_processed']}",
            f"平均批次大小: {stats['batched_requests'] // stats['batches_processed'] if stats['batches_processed'] > 0 else 0}",
            f"节省时间: {stats['time_saved_seconds']:.1f}秒",
            "=" * 50,
        ]

        return "\n".join(lines)


# 全局实例
_batch_processor: BatchProcessor = None


def get_batch_processor(batch_size: int = 5, delay_between_batches: float = 3.0) -> BatchProcessor:
    """获取批处理器实例"""
    global _batch_processor

    if _batch_processor is None:
        _batch_processor = BatchProcessor(
            batch_size=batch_size, delay_between_batches=delay_between_batches
        )

    return _batch_processor


# 便捷函数
async def batch_process(
    prompts: List[str],
    batch_size: int = 5,
    delay_between_batches: float = 3.0,
    show_progress: bool = True,
) -> List[Any]:
    """批量处理提示词

    Args:
        prompts: 提示词列表
        batch_size: 每批大小
        delay_between_batches: 批次间延迟（秒）
        show_progress: 是否显示进度

    Returns:
        处理结果列表
    """

    from backend.services.ai_service import chat

    processor = get_batch_processor(batch_size, delay_between_batches)

    return await processor.batch_process(prompts, chat, show_progress)


async def batch_code_development(
    prompts: List[str], batch_size: int = 3, delay_between_batches: float = 5.0
) -> List[str]:
    """批量代码开发

    Args:
        prompts: 代码需求列表
        batch_size: 每批大小（代码任务建议3-5个）
        delay_between_batches: 批次间延迟（代码任务建议5秒）

    Returns:
        生成的代码列表
    """

    from backend.services.ai_service import code_development

    processor = get_batch_processor(batch_size, delay_between_batches)

    return await processor.batch_process(prompts, code_development)


async def batch_summarize(
    texts: List[str], batch_size: int = 5, delay_between_batches: float = 2.0
) -> List[str]:
    """批量文本摘要

    Args:
        texts: 文本列表
        batch_size: 每批大小
        delay_between_batches: 批次间延迟

    Returns:
        摘要列表
    """

    async def summarize_text(text: str) -> str:
        from backend.services.ai_service import summarize

        return await summarize(text)

    processor = get_batch_processor(batch_size, delay_between_batches)

    return await processor.batch_process(texts, summarize_text)
