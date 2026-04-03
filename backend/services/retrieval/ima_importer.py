"""
Ima知识库数据导入服务
从导出的JSON文件导入到PostgreSQL
"""

import json
import logging
from pathlib import Path
from typing import Dict

import asyncpg

logger = logging.getLogger(__name__)


class ImaKnowledgeImporter:
    """Ima知识库导入器"""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        初始化导入器

        Args:
            db_pool: 数据库连接池
        """
        self.db_pool = db_pool
        self.export_dir = Path("/home/ai/zhineng-knowledge-system/data/ima_export")

        # 分类映射
        self.category_mapping = {
            "气功.json": "气功",
            "中医.json": "中医",
            "儒家.json": "儒家",
            "太极.json": "气功",  # 太极归类到气功
        }

    async def import_all(self, limit: int = 1000) -> Dict[str, int]:
        """
        导入所有分类的知识

        Args:
            limit: 每个分类最多导入数量

        Returns:
            导入统计
        """
        stats = {}

        for json_file, category in self.category_mapping.items():
            file_path = self.export_dir / json_file
            if not file_path.exists():
                logger.warning(f"文件不存在: {file_path}")
                continue

            count = await self.import_category(file_path, category, limit)
            stats[category] = count

        logger.info(f"导入完成: {stats}")
        return stats

    async def import_category(self, file_path: Path, category: str, limit: int = 1000) -> int:
        """
        导入单个分类的知识

        Args:
            file_path: JSON文件路径
            category: 分类名称
            limit: 最大导入数量

        Returns:
            导入数量
        """
        with open(file_path, "r", encoding="utf-8") as f:
            items = json.load(f)

        # 限制导入数量
        items = items[:limit]

        imported = 0
        skipped = 0

        async with self.db_pool.acquire() as conn:
            for item in items:
                try:
                    # 检查是否已存在
                    existing = await conn.fetchval(
                        "SELECT id FROM documents WHERE title = $1", item["name"]
                    )

                    if existing:
                        skipped += 1
                        continue

                    # 插入新文档
                    # 从路径生成简短描述
                    _path_parts = item["path"].split("/")  # noqa: F841
                    description = f"来源: {item['path']}"

                    await conn.execute(
                        """INSERT INTO documents (title, content, category, tags)
                           VALUES ($1, $2, $3, $4)""",
                        item["name"],
                        description,
                        category,
                        [],  # 空标签数组
                    )

                    imported += 1

                except Exception as e:
                    logger.error(f"导入失败 [{item['name']}]: {e}")

        logger.info(f"{category}: 导入={imported}, 跳过={skipped}")
        return imported

    async def import_qigong_knowledge(self) -> int:
        """
        导入气功知识核心内容

        Returns:
            导入数量
        """
        # 气功核心知识（手动定义）
        _qigong_knowledge = [  # noqa: F841
            {
                "title": "八段锦完整教程",
                "content": "八段锦是中国传统养生功法，由八节动作组成。第一式：双手托天理三焦，...",
            },
            # 更多内容...
        ]

        return 0
