"""
混合并发工具

提供线程池 + 异步 IO 的混合并发执行器，优化 CPU 密集型任务和 IO 密集型任务的性能。
"""

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, List, Optional, TypeVar

from tqdm import tqdm

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MixedConcurrencyExecutor:
    """
    混合并发执行器

    结合 ThreadPoolExecutor（用于 CPU 密集型任务）和 asyncio（用于 IO 密集型任务），
    实现最优的性能。
    """

    def __init__(
        self,
        max_thread_workers: int = 4,
        max_async_tasks: int = 100,
        enable_progress_bar: bool = False,
    ):
        """
        初始化混合并发执行器

        Args:
            max_thread_workers: 线程池最大工作线程数
            max_async_tasks: 最大并发异步任务数
            enable_progress_bar: 是否启用进度条
        """
        self.max_thread_workers = max_thread_workers
        self.max_async_tasks = max_async_tasks
        self.enable_progress_bar = enable_progress_bar

        # 线程池
        self.thread_pool = ThreadPoolExecutor(max_workers=max_thread_workers)

        # 信号量（控制异步任务并发数）
        self.semaphore = asyncio.Semaphore(max_async_tasks)

    async def execute_in_thread(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        在线程池中执行同步函数

        Args:
            func: 同步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, functools.partial(func, *args, **kwargs)
        )

    async def execute_async(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        在异步上下文中执行异步函数（受信号量限制）

        Args:
            func: 异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值
        """
        async with self.semaphore:
            return await func(*args, **kwargs)

    async def execute_batch(
        self, tasks: List[Callable[[], Awaitable[T]]], use_thread: bool = False
    ) -> List[T]:
        """
        批量执行任务

        Args:
            tasks: 任务列表
            use_thread: 是否使用线程池

        Returns:
            执行结果列表
        """
        if use_thread:
            # 在线程池中执行
            coroutines = [self.execute_in_thread(lambda f=t: f()) for t in tasks]
        else:
            # 在异步上下文中执行
            coroutines = [self.execute_async(lambda f=t: f()) for t in tasks]

        # 添加进度条
        if self.enable_progress_bar:
            coroutines = tqdm(coroutines, total=len(tasks), desc="执行任务")

        return await asyncio.gather(*coroutines)

    async def map_thread(
        self, func: Callable[..., T], items: List[Any], desc: Optional[str] = None
    ) -> List[T]:
        """
        在线程池中映射函数到列表

        Args:
            func: 函数
            items: 列表项
            desc: 进度条描述

        Returns:
            结果列表
        """
        tasks = [functools.partial(func, item) for item in items]

        if self.enable_progress_bar:
            progress = tqdm(total=len(items), desc=desc or "处理中")

            async def _with_progress(task):
                result = await self.execute_in_thread(task)
                progress.update(1)
                return result

            coroutines = [_with_progress(task) for task in tasks]
            results = await asyncio.gather(*coroutines)
            progress.close()
        else:
            coroutines = [self.execute_in_thread(task) for task in tasks]
            results = await asyncio.gather(*coroutines)

        return results

    async def map_async(
        self, func: Callable[..., Awaitable[T]], items: List[Any], desc: Optional[str] = None
    ) -> List[T]:
        """
        在异步上下文中映射函数到列表

        Args:
            func: 异步函数
            items: 列表项
            desc: 进度条描述

        Returns:
            结果列表
        """
        tasks = [functools.partial(func, item) for item in items]

        if self.enable_progress_bar:
            progress = tqdm(total=len(items), desc=desc or "处理中")

            async def _with_progress(task):
                result = await self.execute_async(task)
                progress.update(1)
                return result

            coroutines = [_with_progress(task) for task in tasks]
            results = await asyncio.gather(*coroutines)
            progress.close()
        else:
            coroutines = [self.execute_async(task) for task in tasks]
            results = await asyncio.gather(*coroutines)

        return results

    def shutdown(self, wait: bool = True):
        """
        关闭执行器，释放资源

        Args:
            wait: 是否等待所有任务完成
        """
        self.thread_pool.shutdown(wait=wait)
        logger.info("混合并发执行器已关闭")


class DocumentParsingOrchestrator:
    """
    文档解析编排器

    使用混合并发执行器优化文档解析性能。
    目标：>50 docs/s 解析速度，>200 texts/s 嵌入速度
    """

    def __init__(
        self,
        parser,
        embedding_service,
        max_thread_workers: int = 4,
        max_async_tasks: int = 100,
        enable_progress_bar: bool = False,
    ):
        """
        初始化文档解析编排器

        Args:
            parser: 文档解析器
            embedding_service: 向量嵌入服务
            max_thread_workers: 线程池最大工作线程数
            max_async_tasks: 最大并发异步任务数
            enable_progress_bar: 是否启用进度条
        """
        self.parser = parser
        self.embedding_service = embedding_service
        self.executor = MixedConcurrencyExecutor(
            max_thread_workers=max_thread_workers,
            max_async_tasks=max_async_tasks,
            enable_progress_bar=enable_progress_bar,
        )

    async def parse_documents(self, file_paths: List[str], batch_size: int = 50) -> List[dict]:
        """
        批量解析文档

        Args:
            file_paths: 文件路径列表
            batch_size: 批量大小

        Returns:
            解析结果列表
        """
        results = []

        for i in range(0, len(file_paths), batch_size):
            batch = file_paths[i : i + batch_size]
            logger.info(f"解析文档批次 {i//batch_size + 1}/{(len(file_paths)-1)//batch_size + 1}")

            # 在线程池中解析文档（CPU 密集型）
            batch_results = await self.executor.map_thread(
                func=lambda fp: asyncio.run(self.parser.parse_file(fp)),
                items=batch,
                desc="解析文档",
            )

            results.extend(batch_results)

        return results

    async def generate_embeddings(
        self, texts: List[str], batch_size: int = 200
    ) -> List[List[float]]:
        """
        批量生成向量嵌入

        Args:
            texts: 文本列表
            batch_size: 批量大小

        Returns:
            向量列表
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            logger.info(f"生成向量嵌入批次 {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")

            # 在异步上下文中生成嵌入（IO 密集型）
            batch_embeddings = await self.executor.map_async(
                func=self.embedding_service.embed_text, items=batch, desc="生成嵌入"
            )

            embeddings.extend(batch_embeddings)

        return embeddings

    async def parse_and_embed(
        self, file_paths: List[str], parse_batch_size: int = 50, embed_batch_size: int = 200
    ) -> List[dict]:
        """
        解析文档并生成向量嵌入（流水线模式）

        Args:
            file_paths: 文件路径列表
            parse_batch_size: 解析批量大小
            embed_batch_size: 嵌入批量大小

        Returns:
            解析和嵌入结果列表
        """
        logger.info(f"开始处理 {len(file_paths)} 个文档")

        # 第一阶段：批量解析文档（CPU 密集型，使用线程池）
        parse_results = await self.parse_documents(file_paths, parse_batch_size)

        # 提取文本内容
        texts = []
        valid_results = []
        for result in parse_results:
            if result.get("status") == "success" and result.get("content"):
                texts.append(result["content"])
                valid_results.append(result)

        logger.info(f"文档解析完成 - 成功: {len(valid_results)}/{len(file_paths)}")

        # 第二阶段：批量生成向量嵌入（IO 密集型，使用异步）
        if texts:
            embeddings = await self.generate_embeddings(texts, embed_batch_size)

            # 合并结果
            for i, (result, embedding) in enumerate(zip(valid_results, embeddings)):
                result["embedding"] = embedding
        else:
            logger.warning("没有有效文本可生成嵌入")
            embeddings = []

        return valid_results

    def shutdown(self):
        """关闭编排器"""
        self.executor.shutdown()


async def benchmark_concurrency(
    func: Callable, items: List[Any], max_workers_list: List[int] = [2, 4, 8, 16]
) -> dict:
    """
    并发性能基准测试

    Args:
        func: 测试函数
        items: 测试项列表
        max_workers_list: 线程数/并发数列表

    Returns:
        性能测试结果
    """
    results = {}

    for max_workers in max_workers_list:
        logger.info(f"测试并发数: {max_workers}")

        executor = MixedConcurrencyExecutor(
            max_thread_workers=max_workers, max_async_tasks=max_workers, enable_progress_bar=False
        )

        import time

        start_time = time.time()

        try:
            if asyncio.iscoroutinefunction(func):
                await executor.map_async(func, items)
            else:
                await executor.map_thread(func, items)

            elapsed = time.time() - start_time
            throughput = len(items) / elapsed

            results[max_workers] = {
                "elapsed_time": elapsed,
                "throughput": throughput,
                "items_per_second": throughput,
            }

            logger.info(f"完成 - 耗时: {elapsed:.2f}s, 吞吐量: {throughput:.2f} items/s")

        finally:
            executor.shutdown()

    return results
