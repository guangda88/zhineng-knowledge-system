#!/usr/bin/env python
"""
增量索引器启动脚本

监控文档目录变化，自动更新索引。
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.config import get_config
from backend.services.document_ingestion import DocumentIngestionService
from backend.services.indexing.incremental_indexer import IncrementalIndexer


def setup_logging(level: str = "INFO"):
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main():
    """主函数"""
    setup_logging()

    logger = logging.getLogger(__name__)
    config = get_config()

    # 配置参数
    watch_dir = os.getenv("WATCH_DIR", "data/documents")
    batch_size = int(os.getenv("BATCH_SIZE", "50"))
    batch_interval = float(os.getenv("BATCH_INTERVAL", "10.0"))

    logger.info(f"增量索引器启动 - 监控目录: {watch_dir}")
    logger.info(f"批处理配置 - 批大小: {batch_size}, 间隔: {batch_interval}s")

    # 确保监控目录存在
    watch_path = Path(watch_dir)
    if not watch_path.exists():
        logger.warning(f"监控目录不存在，创建目录: {watch_path}")
        watch_path.mkdir(parents=True, exist_ok=True)

    try:
        # 初始化文档导入服务
        ingestion_service = DocumentIngestionService()
        logger.info("文档导入服务初始化成功")

        # 初始化增量索引器
        indexer = IncrementalIndexer(
            watch_dir=watch_dir,
            ingestion_service=ingestion_service,
            batch_size=batch_size,
            batch_interval=batch_interval,
            recursive=True,
        )

        # 启动索引器
        await indexer.start()
        logger.info("增量索引器已启动，按 Ctrl+C 停止")

        # 保持运行
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("接收到停止信号")
            await indexer.stop()
            logger.info("增量索引器已停止")

    except Exception as e:
        logger.error(f"增量索引器运行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
        sys.exit(0)
