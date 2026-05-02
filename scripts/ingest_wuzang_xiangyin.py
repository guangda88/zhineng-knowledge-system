#!/usr/bin/env python3
"""
摄取《五脏相音》文档到知识系统
"""

import asyncio
import sys
import os

# 确保工作目录正确
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

from backend.services.document_ingestion import DocumentIngestionService
from backend.services.document_parser import DocumentParser
from backend.core.database import init_db_pool, close_db_pool


async def ingest_wuzang_xiangyin():
    """摄取五脏相音文档"""

    # 获取数据库连接池
    print("正在连接数据库...")
    db_pool = await init_db_pool()

    # 创建解析器
    parser = DocumentParser()

    # 创建摄取服务
    ingestion = DocumentIngestionService(db_pool, parser)

    # 文档路径
    file_path = "/home/ai/zhineng-knowledge-system/data/documents/五脏相音-五脏相音六腑应律.pdf"

    # 摄取文档（中医分类）
    print(f"正在摄取文档: {file_path}")
    result = await ingestion.ingest_file(
        file_path=file_path,
        category="中医",
        title="五脏相音 六腑应律"
    )

    print("\n摄取结果:")
    print(f"  状态: {result['status']}")
    if result['status'] == 'success':
        print(f"  文档ID: {result['doc_id']}")
        print(f"  标题: {result['metadata']['title']}")
        print(f"  分类: {result['metadata']['category']}")
        print(f"  内容长度: {result['metadata']['content_length']} 字符")
    else:
        print(f"  错误: {result.get('error', 'Unknown error')}")

    # 关闭数据库连接池
    await close_db_pool()


if __name__ == "__main__":
    asyncio.run(ingest_wuzang_xiangyin())
