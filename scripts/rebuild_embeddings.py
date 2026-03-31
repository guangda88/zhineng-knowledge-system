#!/usr/bin/env python3
"""重建所有文档的嵌入向量

使用 BGE-M3 嵌入服务为所有文档生成真实的语义向量
"""
import asyncio
import sys
import os
import logging

# 添加后端路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from services.retrieval.vector import VectorRetriever
import asyncpg

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    # 数据库连接配置
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb"
    )
    embedding_service_url = os.getenv(
        "EMBEDDING_SERVICE_URL",
        "http://localhost:8001"
    )

    logger.info("=== 文档向量重建脚本 ===")
    logger.info(f"数据库: {db_url}")
    logger.info(f"嵌入服务: {embedding_service_url}")

    # 检查嵌入服务
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{embedding_service_url}/health", timeout=5.0)
            response.raise_for_status()
            health = response.json()
            if not health.get("model_loaded"):
                logger.error("❌ 嵌入服务未就绪，请等待模型加载完成")
                return 1
            logger.info(f"✅ 嵌入服务正常: {health}")
    except Exception as e:
        logger.error(f"❌ 嵌入服务检查失败: {e}")
        logger.error("请确保嵌入服务已启动: docker-compose up -d embedding")
        return 1

    # 创建数据库连接池
    logger.info("连接数据库...")
    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)

    try:
        # 统计需要更新的文档
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM documents WHERE embedding IS NULL"
            )
            all_docs = await conn.fetchval("SELECT COUNT(*) FROM documents")

        logger.info(f"文档总数: {all_docs}")
        logger.info(f"需要更新: {total}")

        if total == 0:
            logger.info("✅ 所有文档已有向量，无需更新")
            return 0

        # 确认
        confirm = input(f"\n是否开始更新 {total} 个文档的向量? (yes/no): ")
        if confirm.lower() not in ['yes', 'y']:
            logger.info("已取消")
            return 0

        # 创建向量检索器
        async with VectorRetriever(pool) as retriever:
            # 批量更新
            stats = await retriever.update_all_embeddings(batch_size=50)

        logger.info(f"\n=== 更新完成 ===")
        logger.info(f"总数: {stats['total']}")
        logger.info(f"成功: {stats['updated']}")
        logger.info(f"失败: {stats['failed']}")

        if stats['failed'] > 0:
            logger.warning(f"⚠️  {stats['failed']} 个文档更新失败，请查看日志")
            return 1
        else:
            logger.info("✅ 所有文档向量更新成功")
            return 0

    except Exception as e:
        logger.error(f"❌ 发生错误: {e}", exc_info=True)
        return 1
    finally:
        await pool.close()
        logger.info("数据库连接已关闭")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
