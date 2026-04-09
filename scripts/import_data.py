#!/usr/bin/env python3
"""
数据导入脚本
将ima_export中的JSON数据导入到PostgreSQL数据库
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DataImporter:
    """数据导入器"""

    def __init__(self, db_url: str, data_dir: str):
        """初始化导入器

        Args:
            db_url: 数据库连接URL
            data_dir: 数据目录路径
        """
        self.db_url = db_url
        self.data_dir = Path(data_dir)
        self.pool: asyncpg.Pool = None
        self.stats = {"total": 0, "success": 0, "failed": 0, "by_category": {}}

    async def init_pool(self) -> None:
        """初始化数据库连接池"""
        self.pool = await asyncpg.create_pool(
            self.db_url, min_size=1, max_size=10, command_timeout=120
        )
        logger.info("数据库连接池已初始化")

    async def close(self) -> None:
        """关闭连接池"""
        if self.pool:
            await self.pool.close()
            logger.info("数据库连接池已关闭")

    def load_json_file(self, filepath: Path) -> List[Dict[str, Any]]:
        """加载JSON文件

        Args:
            filepath: 文件路径

        Returns:
            数据列表
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # 如果是字典，检查是否有data字段
                    if "data" in data:
                        return data["data"]
                    # 或者将字典包装成列表
                    return [data]
                return data
        except Exception as e:
            logger.error(f"加载文件 {filepath} 失败: {e}")
            return []

    def categorize_file(self, filename: str) -> str:
        """根据文件名确定分类

        Args:
            filename: 文件名

        Returns:
            分类名称
        """
        filename_lower = filename.lower()
        if "气功" in filename_lower or "qigong" in filename_lower:
            return "气功"
        elif "中医" in filename_lower or "tcm" in filename_lower:
            return "中医"
        elif "儒家" in filename_lower or "confucian" in filename_lower:
            return "儒家"
        elif "太极" in filename_lower or "taiji" in filename_lower:
            # 太极归类到气功
            return "气功"
        else:
            return "气功"  # 默认分类

    async def import_file(self, filepath: Path, category: str) -> int:
        """导入单个文件

        Args:
            filepath: 文件路径
            category: 分类

        Returns:
            成功导入的数量
        """
        data = self.load_json_file(filepath)
        if not data:
            return 0

        imported = 0
        async with self.pool.acquire() as conn:
            for item in data:
                try:
                    # 提取字段
                    title = item.get("title", item.get("name", "无标题"))
                    content = item.get("content", item.get("description", item.get("正文", "")))

                    # 如果内容为空，跳过
                    if not content or content.strip() == "":
                        continue

                    # 构建标签
                    tags = item.get("tags", [])
                    if isinstance(tags, str):
                        tags = [tags]
                    elif not isinstance(tags, list):
                        tags = []

                    # 添加分类作为标签
                    if category not in tags:
                        tags.append(category)

                    # 插入数据库
                    await conn.execute(
                        """INSERT INTO documents (title, content, category, tags)
                           VALUES ($1, $2, $3, $4)
                           ON CONFLICT DO NOTHING""",
                        title[:500],  # 标题长度限制
                        content,
                        category,
                        tags,
                    )

                    imported += 1
                    self.stats["success"] += 1

                except Exception as e:
                    self.stats["failed"] += 1
                    logger.debug(f"导入记录失败: {e}")

        logger.info(f"文件 {filepath.name} 导入 {imported}/{len(data)} 条记录")
        return imported

    async def import_all(self) -> None:
        """导入所有数据"""
        if not self.pool:
            await self.init_pool()

        export_dir = self.data_dir / "ima_export"
        if not export_dir.exists():
            logger.error(f"数据目录不存在: {export_dir}")
            return

        # 查找所有JSON文件
        json_files = list(export_dir.glob("*.json"))
        logger.info(f"找到 {len(json_files)} 个JSON文件")

        for json_file in json_files:
            category = self.categorize_file(json_file.name)
            self.stats["by_category"][category] = self.stats["by_category"].get(category, 0)

            try:
                count = await self.import_file(json_file, category)
                self.stats["by_category"][category] += count
                self.stats["total"] += count
            except Exception as e:
                logger.error(f"导入文件 {json_file.name} 失败: {e}")

        # 打印统计
        logger.info("=" * 50)
        logger.info("导入完成")
        logger.info(f"总计: {self.stats['total']} 条")
        logger.info(f"成功: {self.stats['success']} 条")
        logger.info(f"失败: {self.stats['failed']} 条")
        logger.info("分类统计:")
        for category, count in self.stats["by_category"].items():
            logger.info(f"  {category}: {count} 条")

    async def verify_import(self) -> None:
        """验证导入结果"""
        if not self.pool:
            await self.init_pool()

        async with self.pool.acquire() as conn:
            # 总数
            total = await conn.fetchval("SELECT COUNT(*) FROM documents")

            # 分类统计
            rows = await conn.fetch(
                """SELECT category, COUNT(*) as count
                   FROM documents
                   GROUP BY category
                   ORDER BY count DESC"""
            )

            logger.info("=" * 50)
            logger.info("数据库验证结果")
            logger.info(f"总文档数: {total}")
            logger.info("分类分布:")
            for row in rows:
                logger.info(f"  {row['category']}: {row['count']} 条")


async def main():
    """主函数"""
    # 数据库配置
    db_url = os.getenv("DATABASE_URL", "postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb")

    # 数据目录
    data_dir = os.getenv("DATA_DIR", "/home/ai/zhineng-knowledge-system/data")

    logger.info(f"数据库URL: {db_url}")
    logger.info(f"数据目录: {data_dir}")

    # 创建导入器
    importer = DataImporter(db_url, data_dir)

    try:
        # 执行导入
        await importer.import_all()

        # 验证结果
        await importer.verify_import()

    finally:
        await importer.close()


if __name__ == "__main__":
    asyncio.run(main())
