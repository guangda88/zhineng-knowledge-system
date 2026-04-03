"""sys_books 维度标注服务

对 sys_books 表中的 302 万条记录进行自动维度标注：
1. 基于路径解析 (QigongPathParser)
2. 基于文件名/标题解析 (QigongContentParser)
3. 写入 qigong_dims JSONB 字段
4. 支持批量处理和进度追踪
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg

from backend.services.qigong.content_parser import QigongContentParser
from backend.services.qigong.path_parser import QigongPathParser

logger = logging.getLogger(__name__)


class SysBooksDimensionTagger:
    """sys_books 维度标注器

    对 sys_books 表中的记录进行自动维度标注，
    将结果写入 qigong_dims JSONB 字段。
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None
        self.path_parser = QigongPathParser()
        self.content_parser = QigongContentParser()

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url, min_size=2, max_size=8, command_timeout=600, timeout=10
            )
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def tag_batch(
        self,
        domain: Optional[str] = None,
        batch_size: int = 5000,
        limit: int = 50000,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """批量维度标注

        Args:
            domain: 限制领域
            batch_size: 每批处理数量
            limit: 最大处理数量
            dry_run: 是否只测试不写入

        Returns:
            标注统计信息
        """
        pool = await self._get_pool()
        start_time = time.time()

        # Create task record
        async with pool.acquire() as conn:
            task_id = await conn.fetchval(
                """
                INSERT INTO extraction_tasks (task_type, status, total_items, config)
                VALUES ('batch_tag', 'running', $1, $2)
                RETURNING id
                """,
                limit,
                json.dumps({"domain": domain, "dry_run": dry_run}),
            )

        stats = {
            "task_id": task_id,
            "total": 0,
            "tagged": 0,
            "skipped": 0,
            "errors": 0,
        }

        try:
            # Build conditions
            conditions = ["qigong_dims = '{}'::jsonb"]
            params: list = []
            idx = 1

            if domain:
                conditions.append(f"domain = ${idx}")
                params.append(domain)
                idx += 1

            where = " AND ".join(conditions)

            async with pool.acquire() as conn:
                total = (
                    await conn.fetchval(
                        "SELECT reltuples::bigint FROM pg_class WHERE relname = 'sys_books'"
                    )
                    or limit
                )
                stats["total"] = min(total, limit)

            last_id = 0
            processed = 0
            while processed < limit:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        f"""
                        SELECT id, path, filename, category, domain, extension
                        FROM sys_books
                        WHERE {where} AND id > ${idx}
                        ORDER BY id
                        LIMIT ${idx + 1}
                        """,
                        *params,
                        last_id,
                        batch_size,
                    )

                if not rows:
                    break

                last_id = rows[-1]["id"]

                # Parse dimensions in batch
                batch_updates: List[tuple] = []
                for row in rows:
                    try:
                        dims = self._parse_dimensions(row)
                        if dims:
                            batch_updates.append(
                                (
                                    json.dumps(dims, ensure_ascii=False),
                                    row["id"],
                                )
                            )
                            stats["tagged"] += 1
                        else:
                            stats["skipped"] += 1
                    except Exception as e:
                        logger.debug(f"Error parsing {row['id']}: {e}")
                        stats["errors"] += 1

                # Apply updates
                if batch_updates and not dry_run:
                    async with pool.acquire() as conn:
                        await conn.executemany(
                            """
                            UPDATE sys_books
                            SET qigong_dims = $1::jsonb
                            WHERE id = $2
                            """,
                            batch_updates,
                        )

                processed += len(rows)
                stats["total"] = processed

                if processed % 20000 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"  Progress: {processed:,} | tagged={stats['tagged']:,} | "
                        f"rate={rate:.0f}/s"
                    )

        finally:
            elapsed = time.time() - start_time
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE extraction_tasks
                    SET status = 'completed',
                        processed_items = $1,
                        failed_items = $2,
                        result_summary = $3,
                        completed_at = NOW()
                    WHERE id = $4
                    """,
                    stats["tagged"],
                    stats["errors"],
                    json.dumps(stats),
                    task_id,
                )

        stats["elapsed_seconds"] = round(elapsed, 1)
        logger.info(
            f"Tagging complete: {stats['tagged']:,} tagged, "
            f"{stats['skipped']:,} skipped, {stats['errors']:,} errors "
            f"in {elapsed:.1f}s"
        )
        return stats

    def _parse_dimensions(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """解析单条记录的维度信息

        综合使用路径解析和内容解析：
        - 气功领域：使用专门的路径/内容解析器
        - 其他领域：生成基础维度
        """
        domain = row.get("domain")
        path = row.get("path", "")
        filename = row.get("filename", "")
        extension = row.get("extension", "")
        category = row.get("category", "")

        if domain in ("智能气功", "气功"):
            return self._parse_qigong_dimensions(path, filename, extension, category)
        elif domain in ("中医",):
            return self._parse_tcm_dimensions(path, filename, extension, category)
        elif domain in ("儒家",):
            return self._parse_confucian_dimensions(path, filename, extension, category)
        else:
            return self._parse_generic_dimensions(path, filename, extension, domain)

    def _parse_qigong_dimensions(
        self, path: str, filename: str, extension: str, category: str
    ) -> Dict[str, Any]:
        """气功领域维度解析"""
        full_path = f"{path}/{filename}"

        # Use path parser first
        path_result = self.path_parser.parse(full_path)
        dims = path_result.to_dict()

        # Enhance with content parser
        content_result = self.content_parser.parse_from_title_content(filename, "")

        # Merge: path parser results take priority for path-derived fields,
        # content parser fills in what path parser missed
        for key, value in content_result.items():
            if key not in dims or not dims[key]:
                dims[key] = value

        return dims

    def _parse_tcm_dimensions(
        self, path: str, filename: str, extension: str, category: str
    ) -> Dict[str, Any]:
        """中医领域维度解析"""
        dims: Dict[str, Any] = {
            "theory_system": "中医理论",
            "media_format": self._extension_to_media(extension),
        }

        path_lower = (path + filename).lower()

        tcm_subcategories = {
            "黄帝内经": "黄帝内经",
            "伤寒": "伤寒论",
            "本草": "本草",
            "针灸": "针灸",
            "经络": "经络",
            "方剂": "方剂",
            "诊断": "诊断",
            "温病": "温病",
            "金匮": "金匮要略",
            "脉经": "脉学",
        }

        for keyword, subcategory in tcm_subcategories.items():
            if keyword in path_lower:
                dims["content_topic"] = subcategory
                break

        return dims

    def _parse_confucian_dimensions(
        self, path: str, filename: str, extension: str, category: str
    ) -> Dict[str, Any]:
        """儒家领域维度解析"""
        dims: Dict[str, Any] = {
            "theory_system": "儒家思想",
            "media_format": self._extension_to_media(extension),
        }

        path_lower = (path + filename).lower()

        confucian_classics = {
            "论语": "论语",
            "孟子": "孟子",
            "大学": "大学",
            "中庸": "中庸",
            "诗经": "诗经",
            "尚书": "尚书",
            "礼记": "礼记",
            "周易": "周易",
            "春秋": "春秋",
            "孝经": "孝经",
            "尔雅": "尔雅",
        }

        for keyword, classic in confucian_classics.items():
            if keyword in path_lower:
                dims["content_topic"] = classic
                break

        return dims

    def _parse_generic_dimensions(
        self, path: str, filename: str, extension: str, domain: str
    ) -> Dict[str, Any]:
        """通用领域维度解析"""
        dims: Dict[str, Any] = {
            "theory_system": domain or "综合",
            "media_format": self._extension_to_media(extension),
        }

        return dims

    def _extension_to_media(self, extension: str) -> str:
        """扩展名转媒体格式"""
        ext = (extension or "").lower().lstrip(".")
        media_map = {
            "txt": "文字",
            "md": "文字",
            "text": "文字",
            "pdf": "文档",
            "doc": "文档",
            "docx": "文档",
            "djvu": "文档",
            "mobi": "文档",
            "epub": "文档",
            "mp3": "音频",
            "wav": "音频",
            "m4a": "音频",
            "flac": "音频",
            "mp4": "视频",
            "avi": "视频",
            "rmvb": "视频",
            "rm": "视频",
            "mkv": "视频",
            "mov": "视频",
            "jpg": "图片",
            "jpeg": "图片",
            "png": "图片",
        }
        return media_map.get(ext, "文档")

    async def get_tagging_stats(self) -> Dict[str, Any]:
        """获取标注统计（使用 pg_class 估算大表总数）"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            total = (
                await conn.fetchval(
                    "SELECT reltuples::bigint FROM pg_class WHERE relname = 'sys_books'"
                )
                or 3024428
            )
            tagged = await conn.fetchval(
                "SELECT COUNT(*) FROM sys_books WHERE qigong_dims != '{}'::jsonb"
            )

            by_domain = await conn.fetch("""
                SELECT domain,
                       COUNT(*) as total,
                       COUNT(*) FILTER (WHERE qigong_dims != '{}'::jsonb) as tagged
                FROM sys_books
                WHERE domain IS NOT NULL
                GROUP BY domain
                ORDER BY total DESC
                LIMIT 15
            """)

            return {
                "total": total,
                "tagged": tagged,
                "untagged": total - tagged,
                "coverage_percent": round(tagged / total * 100, 1) if total else 0,
                "by_domain": [
                    {
                        "domain": r["domain"],
                        "total": r["total"],
                        "tagged": r["tagged"],
                        "coverage": round(r["tagged"] / r["total"] * 100, 1) if r["total"] else 0,
                    }
                    for r in by_domain
                ],
            }


async def tag_sys_books(
    db_url: str,
    domain: Optional[str] = None,
    limit: int = 50000,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """标注 sys_books 的便捷函数"""
    tagger = SysBooksDimensionTagger(db_url)
    try:
        return await tagger.tag_batch(domain=domain, limit=limit, dry_run=dry_run)
    finally:
        await tagger.close()
