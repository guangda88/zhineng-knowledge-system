"""
智能气功批量打标服务

提供批量自动打标、覆盖率统计、维度验证等功能
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg

from .path_parser import parse_qigong_dimensions


class QigongBatchTagger:
    """
    智能气功批量打标服务

    功能：
    - 按路径模式批量打标
    - 覆盖率统计
    - 打标结果验证
    - 维度分布统计
    - 安全级别检测
    """

    # 安全级别关键词配置
    SECURITY_KEYWORDS = {
        "restricted": [
            "内部",
            "保密",
            "机密",
            "秘密",
            "仅限内部",
            "internal",
            "confidential",
            "restricted",
            "secret",
        ],
        "confidential": ["内部资料", "内部教学", "未公开", "内部培训", "内部交流"],
        "internal": ["讲义", "教案", "备课", "辅导", "学员须知", "培训资料"],
    }

    DEFAULT_SECURITY_LEVEL = "public"

    def __init__(self, db_url: str):
        """
        初始化打标服务

        Args:
            db_url: PostgreSQL数据库连接URL
        """
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """获取连接池"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url, min_size=2, max_size=10, timeout=10
            )
        return self._pool

    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def tag_by_title_content(
        self, batch_size: int = 1000, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        基于标题和内容批量打标（适用于无 file_path 字段的数据库）

        Args:
            batch_size: 每批处理的数量
            dry_run: 是否只测试不实际写入

        Returns:
            统计信息字典
        """
        from .content_parser import QigongContentParser

        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 查询需要打标的文档（空维度）
            rows = await conn.fetch(
                """
                SELECT id, title, content, qigong_dims
                FROM documents
                WHERE category = '气功'
                  AND qigong_dims = '{}'::jsonb
                ORDER BY id
                LIMIT $1
            """,
                batch_size,
            )

            stats = {
                "total": len(rows),
                "tagged": 0,
                "skipped": 0,
                "errors": 0,
                "start_time": datetime.now().isoformat(),
            }

            parser = QigongContentParser()

            for row in rows:
                try:
                    # 基于标题和内容解析维度
                    dims = parser.parse_from_title_content(row["title"], row.get("content") or "")

                    if not dims:
                        stats["skipped"] += 1
                        continue

                    if not dry_run:
                        # 更新数据库
                        await conn.execute(
                            """
                            UPDATE documents
                            SET qigong_dims = $1::jsonb,
                                updated_at = NOW()
                            WHERE id = $2
                        """,
                            json.dumps(dims, ensure_ascii=False),
                            row["id"],
                        )

                    stats["tagged"] += 1

                    # 每100条打印一次进度
                    if stats["tagged"] % 100 == 0:
                        print(f"已处理: {stats['tagged']}/{stats['total']}")

                except Exception as e:
                    print(f"Error tagging {row['id']} ({row['title'][:50]}): {e}")
                    stats["errors"] += 1

            stats["end_time"] = datetime.now().isoformat()
            stats["duration_seconds"] = (
                datetime.fromisoformat(stats["end_time"])
                - datetime.fromisoformat(stats["start_time"])
            ).total_seconds()

            return stats

    async def tag_by_path_pattern(
        self, pattern: str = "%", dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        按路径模式批量打标

        Args:
            pattern: LIKE 模式，默认全部
            dry_run: 是否只测试不实际写入

        Returns:
            统计信息字典
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 查询需要打标的文档（使用 title 替代 file_path）
            rows = await conn.fetch("""
                SELECT id, title, content, category, qigong_dims
                FROM documents
                WHERE category = '气功'
                  AND qigong_dims = '{}'::jsonb
                ORDER BY id
                LIMIT 10000
            """)

            stats = {
                "total": len(rows),
                "tagged": 0,
                "skipped": 0,
                "errors": 0,
                "start_time": datetime.now().isoformat(),
            }

            for row in rows:
                try:
                    # 检查是否已有维度数据
                    existing_dims = row.get("qigong_dims") or {}
                    if existing_dims:
                        stats["skipped"] += 1
                        continue

                    # 使用标题解析（模拟路径）
                    dims = parse_qigong_dimensions("/" + row["title"])

                    if not dims:
                        stats["skipped"] += 1
                        continue

                    if not dry_run:
                        # 更新数据库
                        await conn.execute(
                            """
                            UPDATE documents
                            SET qigong_dims = $1::jsonb,
                                updated_at = NOW()
                            WHERE id = $2
                        """,
                            dims,
                            row["id"],
                        )

                    stats["tagged"] += 1

                    # 每100条打印一次进度
                    if stats["tagged"] % 100 == 0:
                        print(f"已处理: {stats['tagged']}/{stats['total']}")

                except Exception as e:
                    print(f"Error tagging {row['id']} ({row['title']}): {e}")
                    stats["errors"] += 1

            stats["end_time"] = datetime.now().isoformat()
            stats["duration_seconds"] = (
                datetime.fromisoformat(stats["end_time"])
                - datetime.fromisoformat(stats["start_time"])
            ).total_seconds()

            return stats

    async def tag_by_id_list(self, doc_ids: List[int], dry_run: bool = False) -> Dict[str, Any]:
        """
        按文档ID列表批量打标

        Args:
            doc_ids: 文档ID列表
            dry_run: 是否只测试不实际写入

        Returns:
            统计信息字典
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 查询文档
            rows = await conn.fetch(
                """
                SELECT id, file_path, title, category
                FROM documents
                WHERE id = ANY($1::int[])
                  AND category = '气功'
                ORDER BY id
            """,
                doc_ids,
            )

            stats = {
                "total": len(rows),
                "tagged": 0,
                "skipped": 0,
                "errors": 0,
            }

            for row in rows:
                try:
                    # 解析路径
                    dims = parse_qigong_dimensions(row["file_path"])

                    if not dims:
                        stats["skipped"] += 1
                        continue

                    if not dry_run:
                        # 更新数据库
                        await conn.execute(
                            """
                            UPDATE documents
                            SET qigong_dims = $1::jsonb,
                                updated_at = NOW()
                            WHERE id = $2
                        """,
                            dims,
                            row["id"],
                        )

                    stats["tagged"] += 1

                except Exception as e:
                    print(f"Error tagging {row['id']}: {e}")
                    stats["errors"] += 1

            return stats

    async def get_coverage_stats(self) -> Dict[str, Any]:
        """
        获取打标覆盖率统计

        Returns:
            统计信息字典，包含总体覆盖率和各维度覆盖率
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 总数
            total = await conn.fetchval("""
                SELECT COUNT(*)::int FROM documents WHERE category = '气功'
            """)

            # 已打标
            tagged = await conn.fetchval("""
                SELECT COUNT(*)::int FROM documents
                WHERE category = '气功'
                  AND qigong_dims IS NOT NULL
                  AND qigong_dims != '{}'::jsonb
            """)

            # 各维度覆盖率
            dimensions = [
                "theory_system",
                "content_topic",
                "gongfa_stage",
                "gongfa_method",
                "discipline",
                "teaching_level",
                "speaker",
                "media_format",
            ]

            dim_coverage = {}
            for dim in dimensions:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*)::int FROM documents
                    WHERE category = '气功'
                      AND qigong_dims ? $1
                """,
                    dim,
                )
                dim_coverage[dim] = {
                    "count": count,
                    "coverage_percent": round(count / total * 100, 1) if total else 0,
                }

            return {
                "total": total,
                "tagged": tagged,
                "untagged": total - tagged,
                "coverage_percent": round(tagged / total * 100, 1) if total else 0,
                "dimensions": dim_coverage,
            }

    async def get_dimension_distribution(self, dimension: str) -> List[Dict[str, Any]]:
        """
        获取指定维度的分布统计

        Args:
            dimension: 维度名称（如 gongfa_method, discipline）

        Returns:
            分布列表，按数量降序
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    qigong_dims->>$1 AS value,
                    COUNT(*) AS count
                FROM documents
                WHERE category = '气功'
                  AND qigong_dims ? $1
                GROUP BY qigong_dims->>$1
                ORDER BY count DESC
            """,
                dimension,
            )

            return [{"value": r["value"], "count": r["count"]} for r in rows]

    async def validate_dimensions(
        self, vocab_table: str = "qigong_dimension_vocab"
    ) -> Dict[str, Any]:
        """
        验证维度数据是否符合受控词表

        Args:
            vocab_table: 受控词表名称

        Returns:
            验证结果
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 获取所有已使用的维度值
            rows = await conn.fetch("""
                SELECT DISTINCT
                    jsonb_object_keys(qigong_dims) AS dimensions
                FROM documents
                WHERE category = '气功'
                  AND qigong_dims IS NOT NULL
            """)

            all_dimensions = set()
            for r in rows:
                all_dimensions.update(r["dimensions"])

            # 获取受控词表中的维度
            vocab_dims = await conn.fetch(f"""
                SELECT dimension_code FROM {vocab_table}
            """)

            vocab_dimension_set = {r["dimension_code"] for r in vocab_dims}

            # 检查差异
            invalid = all_dimensions - vocab_dimension_set

            return {
                "total_dimensions_used": len(all_dimensions),
                "valid_dimensions": len(all_dimensions & vocab_dimension_set),
                "invalid_dimensions": list(invalid),
                "is_valid": len(invalid) == 0,
            }

    async def fix_invalid_tags(
        self, old_value: str, new_value: str, dimension: str, dry_run: bool = True
    ) -> int:
        """
        修复无效的标签值

        Args:
            old_value: 旧的值
            new_value: 新的值
            dimension: 维度名称
            dry_run: 是否只测试不实际写入

        Returns:
            修复的文档数量
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 查询需要修复的文档
            if dry_run:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM documents
                    WHERE category = '气功'
                      AND qigong_dims->>$1 = $2
                """,
                    dimension,
                    old_value,
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE documents
                    SET qigong_dims = qigong_dims || jsonb_build_object($1, $2)
                    WHERE category = '气功'
                      AND qigong_dims->>$1 = $3
                """,
                    dimension,
                    new_value,
                    old_value,
                )
                count = result.split()[-1] if result else "0"
                count = int(count)

            return int(count)

    async def detect_security_level(
        self, doc_id: int, file_path: str, title: str = None
    ) -> Dict[str, Any]:
        """
        检测文档的安全级别

        Args:
            doc_id: 文档ID
            file_path: 文件路径
            title: 文档标题（可选）

        Returns:
            安全级别检测结果
        """
        import os

        # 收集检测信号
        signals = {
            "path": file_path.lower(),
            "filename": os.path.basename(file_path).lower(),
            "title": (title or "").lower(),
            "parent_dirs": [],
        }

        # 收集父目录名
        parts = Path(file_path).parts
        for i, part in enumerate(parts):
            if i > 0:  # 跳过根目录
                signals["parent_dirs"].append(part.lower())

        # 检测逻辑
        detected_level = self.DEFAULT_SECURITY_LEVEL
        confidence = 0.0
        matched_keywords = []

        # 按优先级检查 restricted
        for keyword in self.SECURITY_KEYWORDS["restricted"]:
            if any(
                keyword in signal
                for signal in [signals["path"], signals["filename"], signals["title"]]
                + signals["parent_dirs"]
            ):
                detected_level = "restricted"
                confidence = 0.9
                matched_keywords.append(keyword)
                break

        # 检查 confidential
        if detected_level == "public":
            for keyword in self.SECURITY_KEYWORDS["confidential"]:
                if any(
                    keyword in signal
                    for signal in [signals["path"], signals["filename"], signals["title"]]
                    + signals["parent_dirs"]
                ):
                    detected_level = "confidential"
                    confidence = 0.7
                    matched_keywords.append(keyword)
                    break

        # 检查 internal
        if detected_level == "public":
            for keyword in self.SECURITY_KEYWORDS["internal"]:
                if any(
                    keyword in signal
                    for signal in [signals["path"], signals["filename"], signals["title"]]
                    + signals["parent_dirs"]
                ):
                    detected_level = "internal"
                    confidence = 0.5
                    matched_keywords.append(keyword)
                    break

        return {
            "detected_level": detected_level,
            "confidence": confidence,
            "matched_keywords": matched_keywords,
            "is_sensitive": detected_level != "public",
        }

    async def scan_and_tag_security(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        扫描所有文档并标记安全级别

        Args:
            dry_run: 是否只测试不实际写入

        Returns:
            扫描统计信息
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 获取所有气功文档
            rows = await conn.fetch("""
                SELECT id, file_path, title, qigong_dims
                FROM documents
                WHERE category = '气功'
                ORDER BY id
            """)

            stats = {
                "total_scanned": len(rows),
                "public": 0,
                "internal": 0,
                "confidential": 0,
                "restricted": 0,
                "tagged": 0,
                "errors": 0,
            }

            for row in rows:
                try:
                    # 检测安全级别
                    detection = await self.detect_security_level(
                        row["id"], row["file_path"], row.get("title")
                    )

                    level = detection["detected_level"]
                    stats[level] += 1

                    # 更新维度数据
                    if not dry_run and detection["is_sensitive"]:
                        current_dims = row.get("qigong_dims") or {}

                        # 只在安全级别不存在时添加
                        if "security_level" not in current_dims:
                            current_dims["security_level"] = level

                            await conn.execute(
                                """
                                UPDATE documents
                                SET qigong_dims = $1::jsonb,
                                    updated_at = NOW()
                                WHERE id = $2
                            """,
                                current_dims,
                                row["id"],
                            )

                            # 如果是敏感文档，同时添加到保密文档表
                            if level in ("confidential", "restricted"):
                                await conn.execute(
                                    """
                                    INSERT INTO documents_confidential (
                                        document_id, security_level,
                                        access_reason, source_system
                                    ) VALUES ($1, $2, $3, $4)
                                    ON CONFLICT (document_id) DO UPDATE SET
                                        security_level = $2,
                                        updated_at = NOW()
                                """,
                                    row["id"],
                                    level,
                                    f"Auto-detected: {', '.join(detection['matched_keywords'])}",
                                    "batch_tagger",
                                )

                            stats["tagged"] += 1

                except Exception as e:
                    print(f"Error scanning doc {row['id']}: {e}")
                    stats["errors"] += 1

            return stats

    async def get_security_stats(self) -> Dict[str, Any]:
        """
        获取安全级别统计信息

        Returns:
            统计信息字典
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # 从 qigong_dims 统计
            rows = await conn.fetch("""
                SELECT
                    COALESCE(qigong_dims->>'security_level', 'public') AS level,
                    COUNT(*) AS count
                FROM documents
                WHERE category = '气功'
                GROUP BY qigong_dims->>'security_level'
                ORDER BY
                    CASE qigong_dims->>'security_level'
                        WHEN 'restricted' THEN 1
                        WHEN 'confidential' THEN 2
                        WHEN 'internal' THEN 3
                        WHEN 'public' THEN 4
                        ELSE 5
                    END
            """)

            dimension_stats = {r["level"]: r["count"] for r in rows}

            # 从 documents_confidential 表统计
            confidential_count = await conn.fetchval("""
                SELECT COUNT(*) FROM documents_confidential
            """)

            # 按级别统计保密文档
            confidential_by_level = await conn.fetch("""
                SELECT security_level, COUNT(*) AS count
                FROM documents_confidential
                GROUP BY security_level
                ORDER BY
                    CASE security_level
                        WHEN 'restricted' THEN 1
                        WHEN 'confidential' THEN 2
                        WHEN 'internal' THEN 3
                    END
            """)

            confidential_stats = {r["security_level"]: r["count"] for r in confidential_by_level}

            return {
                "by_dimension": dimension_stats,
                "confidential_table_total": confidential_count,
                "confidential_by_level": confidential_stats,
                "total_documents": sum(dimension_stats.values()),
            }


# 便捷函数
async def batch_tag_qigong_docs(
    db_url: str, pattern: str = "%", dry_run: bool = False
) -> Dict[str, Any]:
    """
    批量打标智能气功文档

    Args:
        db_url: 数据库连接URL
        pattern: 路径匹配模式
        dry_run: 是否只测试

    Returns:
        统计信息
    """
    tagger = QigongBatchTagger(db_url)
    try:
        return await tagger.tag_by_path_pattern(pattern, dry_run)
    finally:
        await tagger.close()


async def get_tagging_coverage(db_url: str) -> Dict[str, Any]:
    """
    获取打标覆盖率

    Args:
        db_url: 数据库连接URL

    Returns:
        覆盖率统计
    """
    tagger = QigongBatchTagger(db_url)
    try:
        return await tagger.get_coverage_stats()
    finally:
        await tagger.close()
