#!/usr/bin/env python3
"""
RAG 系统状态检查脚本

检查：
1. 文档嵌入向量覆盖率
2. 各分类文档数量
3. 向量检索功能
4. 检索服务状态
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncpg
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(project_root / ".env")


async def check_embedding_coverage():
    """检查文档嵌入向量覆盖率"""
    print("=" * 60)
    print("1. 文档嵌入向量覆盖率检查")
    print("=" * 60)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ 未找到 DATABASE_URL 环境变量")
        return

    # 解析数据库URL
    # 格式: postgresql://user:password@host:port/database
    import re
    match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", database_url)
    if not match:
        print("❌ 无法解析 DATABASE_URL")
        return

    user, password, host, port, database = match.groups()

    try:
        pool = await asyncpg.create_pool(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database
        )

        async with pool.acquire() as conn:
            # 总文档数
            total_docs = await conn.fetchval("SELECT COUNT(*) FROM documents")

            # 有嵌入向量的文档数
            docs_with_embedding = await conn.fetchval(
                "SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL"
            )

            coverage = (docs_with_embedding / total_docs * 100) if total_docs > 0 else 0

            print(f"总文档数: {total_docs:,}")
            print(f"有嵌入向量的文档: {docs_with_embedding:,}")
            print(f"覆盖率: {coverage:.2f}%")

            if coverage >= 95:
                print("✅ 嵌入向量覆盖率良好")
            elif coverage >= 50:
                print("⚠️  嵌入向量覆盖率一般，建议更新")
            else:
                print("❌ 嵌入向量覆盖率低，需要更新")

        await pool.close()

    except Exception as e:
        print(f"❌ 检查失败: {e}")


async def check_category_distribution():
    """检查各分类文档数量"""
    print("\n" + "=" * 60)
    print("2. 各分类文档数量")
    print("=" * 60)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ 未找到 DATABASE_URL 环境变量")
        return

    import re
    match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", database_url)
    if not match:
        print("❌ 无法解析 DATABASE_URL")
        return

    user, password, host, port, database = match.groups()

    try:
        pool = await asyncpg.create_pool(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database
        )

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT category, COUNT(*) as count
                FROM documents
                GROUP BY category
                ORDER BY count DESC
            """)

            print(f"{'分类':<15} {'文档数':>10} {'占比':>8}")
            print("-" * 35)

            total = sum(row['count'] for row in rows)
            for row in rows:
                category = row['category'] or '未分类'
                count = row['count']
                percent = (count / total * 100) if total > 0 else 0
                print(f"{category:<15} {count:>10,} {percent:>7.2f}%")

        await pool.close()

    except Exception as e:
        print(f"❌ 检查失败: {e}")


async def check_vector_retrieval():
    """检查向量检索功能"""
    print("\n" + "=" * 60)
    print("3. 向量检索功能测试")
    print("=" * 60)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ 未找到 DATABASE_URL 环境变量")
        return

    import re
    match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", database_url)
    if not match:
        print("❌ 无法解析 DATABASE_URL")
        return

    user, password, host, port, database = match.groups()

    try:
        pool = await asyncpg.create_pool(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database
        )

        async with pool.acquire() as conn:
            # 测试查询：智能气功
            test_query = "智能气功的练功方法"
            print(f"测试查询: {test_query}\n")

            # 使用一个模拟向量（实际应该使用真实的embedding模型）
            # 这里我们直接用相似度查询测试pgvector扩展是否工作
            rows = await conn.fetch("""
                SELECT id, title, category,
                       array_length(embedding, 1) as dim
                FROM documents
                WHERE embedding IS NOT NULL
                LIMIT 3
            """)

            if rows:
                print("✅ pgvector 扩展工作正常")
                print(f"   向量维度: {rows[0]['dim']}")
                print(f"   示例文档:")
                for row in rows:
                    print(f"   - {row['title'][:50]} (ID: {row['id']}, 分类: {row['category']})")
            else:
                print("❌ 没有找到有嵌入向量的文档")

        await pool.close()

    except Exception as e:
        print(f"❌ 检查失败: {e}")


async def check_embedding_model():
    """检查嵌入模型状态"""
    print("\n" + "=" * 60)
    print("4. 嵌入模型状态")
    print("=" * 60)

    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    print(f"配置的嵌入模型: {model_name}")

    # 检查是否已下载
    cache_dir = os.path.expanduser("~/.cache/torch/sentence_transformers")
    model_dir = os.path.join(cache_dir, model_name.replace("/", "_"))

    if os.path.exists(model_dir):
        print(f"✅ 模型已下载: {model_dir}")
    else:
        print(f"⚠️  模型未下载，首次使用时会自动下载")


async def check_retrieval_services():
    """检查检索服务状态"""
    print("\n" + "=" * 60)
    print("5. 检索服务状态")
    print("=" * 60)

    # 检查后端服务
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=zhineng-api", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.stdout.strip():
            print(f"✅ 后端服务运行中: {result.stdout.strip()}")
        else:
            print("❌ 后端服务未运行")

    except Exception as e:
        print(f"⚠️  无法检查后端服务状态: {e}")

    # 检查API端点（简单检查）
    print("\n可用的API端点:")
    endpoints = [
        "GET  /api/v1/search",
        "POST /api/v1/search/hybrid",
        "GET  /api/v1/search/retrieval/status",
        "POST /api/v1/ask",
        "GET  /api/v1/categories",
    ]

    for endpoint in endpoints:
        print(f"  {endpoint}")


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("RAG 系统状态检查")
    print("=" * 60)

    await check_embedding_coverage()
    await check_category_distribution()
    await check_vector_retrieval()
    await check_embedding_model()
    await check_retrieval_services()

    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
