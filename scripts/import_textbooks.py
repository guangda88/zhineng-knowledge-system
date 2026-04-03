"""
智能气功教材数据导入脚本

从 /home/ai/zhineng-knowledge-system/data/textbooks/txt格式/
导入智能气功相关教材到灵知系统
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.services.enhanced_vector_service import EmbeddingProvider, TextVectorizer
from backend.services.text_processor import EnhancedTextProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 配置
TEXTBOOKS_DIR = Path("data/textbooks/txt格式")
PROCESSED_DIR = Path("data/textbooks/processed")
CHUNK_SIZE = 300
OVERLAP = 50

# 确保输出目录存在
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


async def process_single_file(file_path: Path, processor, vectorizer):
    """
    处理单个教材文件

    Args:
        file_path: 文本文件路径
        processor: 文本处理器
        vectorizer: 向量化器

    Returns:
        处理结果字典
    """
    try:
        logger.info(f"开始处理: {file_path.name}")

        # 1. 文本处理
        chunks, metadata = await processor.process_file(str(file_path))

        logger.info(f"  - 分块完成: {len(chunks)} 个块")

        # 2. 向量化
        if chunks:
            contents = [chunk.content for chunk in chunks]
            vectors, stats = await vectorizer.vectorize_text_blocks(contents)

            logger.info(f"  - 向量化完成: {len(vectors)} 个向量")
            logger.info(f"  - 平均质量: {stats['avg_quality']:.2f}")

        # 3. 保存处理结果
        result = {
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "chunks_count": len(chunks),
            "metadata": metadata.to_dict(),
            "processed_at": datetime.now().isoformat(),
        }

        # 保存到processed目录
        import json

        output_file = PROCESSED_DIR / f"{file_path.stem}_processed.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 处理完成: {file_path.name}")

        return result

    except Exception as e:
        logger.error(f"❌ 处理失败 {file_path.name}: {e}")
        return {
            "file_name": file_path.name,
            "error": str(e),
            "processed_at": datetime.now().isoformat(),
        }


async def import_textbooks(limit: int = None, skip_processed: bool = True):
    """
    导入所有教材文件

    Args:
        limit: 限制处理文件数量（None表示全部）
        skip_processed: 是否跳过已处理的文件
    """
    # 检查textbooks目录
    if not TEXTBOOKS_DIR.exists():
        logger.error(f"教材目录不存在: {TEXTBOOKS_DIR}")
        return

    # 获取所有txt文件
    txt_files = list(TEXTBOOKS_DIR.glob("*.txt"))
    logger.info(f"找到 {len(txt_files)} 个文本文件")

    if skip_processed:
        # 过滤掉已处理的文件
        processed_files = set()
        for processed_file in PROCESSED_DIR.glob("*_processed.json"):
            original_name = processed_file.stem.replace("_processed", "")
            processed_files.add(original_name + ".txt")

        txt_files = [f for f in txt_files if f.name not in processed_files]
        logger.info(f"跳过已处理文件后，剩余 {len(txt_files)} 个文件")

    if limit:
        txt_files = txt_files[:limit]
        logger.info(f"限制处理数量为: {limit}")

    # 初始化处理器
    processor = EnhancedTextProcessor(max_chunk_size=CHUNK_SIZE, overlap=OVERLAP)

    vectorizer = TextVectorizer(preferred_provider=EmbeddingProvider.LOCAL)

    # 处理每个文件
    results = []
    total_start = datetime.now()

    for i, file_path in enumerate(txt_files, 1):
        logger.info(f"[{i}/{len(txt_files)}] 处理文件...")

        result = await process_single_file(file_path, processor, vectorizer)
        results.append(result)

    # 统计
    total_time = (datetime.now() - total_start).total_seconds()
    successful = sum(1 for r in results if "error" not in r)
    failed = len(results) - successful

    logger.info("=" * 60)
    logger.info("导入完成统计")
    logger.info("=" * 60)
    logger.info(f"总文件数: {len(txt_files)}")
    logger.info(f"成功处理: {successful}")
    logger.info(f"处理失败: {failed}")
    logger.info(f"总耗时: {total_time:.2f} 秒")
    logger.info(f"平均耗时: {total_time/len(txt_files):.2f} 秒/文件")
    logger.info("=" * 60)

    # 保存导入报告
    report = {
        "total_files": len(txt_files),
        "successful": successful,
        "failed": failed,
        "total_time": total_time,
        "avg_time_per_file": total_time / len(txt_files),
        "results": results,
        "completed_at": datetime.now().isoformat(),
    }

    report_file = PROCESSED_DIR / "import_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"导入报告已保存: {report_file}")

    return report


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="智能气功教材数据导入")
    parser.add_argument("--limit", type=int, help="限制处理文件数量")
    parser.add_argument("--all", action="store_true", help="处理所有文件（包括已处理的）")

    args = parser.parse_args()

    # 开始导入
    await import_textbooks(limit=args.limit, skip_processed=not args.all)


if __name__ == "__main__":
    asyncio.run(main())
