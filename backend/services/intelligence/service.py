"""情报聚合服务

协调各采集器，执行采集并将结果持久化到数据库。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from backend.core.database import get_db_pool
from backend.services.intelligence.base import CollectionResult, IntelligenceItem
from backend.services.intelligence.github_collector import GitHubCollector
from backend.services.intelligence.huggingface_collector import HuggingFaceCollector
from backend.services.intelligence.npm_collector import NPMCollector

logger = logging.getLogger(__name__)

COLLECTOR_MAP = {
    "github": GitHubCollector,
    "npm": NPMCollector,
    "huggingface": HuggingFaceCollector,
}


class IntelligenceService:
    """情报聚合服务

    协调多个采集器执行情报采集，将结果写入PostgreSQL，
    并提供查询和统计功能。
    """

    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token

    def _get_collector(self, source: str):
        """获取指定来源的采集器实例

        Args:
            source: 来源标识 ('github', 'npm', 'huggingface')

        Returns:
            BaseCollector: 采集器实例

        Raises:
            ValueError: 不支持的来源
        """
        if source == "github":
            return GitHubCollector(token=self.github_token)
        elif source == "npm":
            return NPMCollector()
        elif source == "huggingface":
            return HuggingFaceCollector()
        raise ValueError(f"不支持的情报来源: {source}")

    async def collect_all(self, sources: Optional[List[str]] = None) -> Dict[str, CollectionResult]:
        """执行全部或指定来源的情报采集

        Args:
            sources: 来源列表，为空时采集全部来源

        Returns:
            Dict[str, CollectionResult]: 各来源的采集结果
        """
        target_sources = sources or list(COLLECTOR_MAP.keys())
        results: Dict[str, CollectionResult] = {}

        for source in target_sources:
            if source not in COLLECTOR_MAP:
                logger.warning(f"跳过不支持的来源: {source}")
                continue

            collection_id = await self._create_collection_record(source)
            try:
                collector = self._get_collector(source)
                result = await collector.collect()
                await self._persist_items(result.items)
                await self._update_collection_record(
                    collection_id,
                    "completed",
                    items_found=result.total_found,
                    items_new=result.new_count,
                    items_updated=result.updated_count,
                    duration_ms=result.duration_ms,
                    errors=result.errors,
                )
                results[source] = result
                logger.info(
                    f"情报采集 [{source}]: {result.total_found} 条, "
                    f"新 {result.new_count}, 更新 {result.updated_count}"
                )
            except Exception as e:
                logger.error(f"情报采集 [{source}] 失败: {e}", exc_info=True)
                await self._update_collection_record(collection_id, "failed", error_message=str(e))
                results[source] = CollectionResult(errors=[str(e)])

        return results

    async def get_items(
        self,
        source: Optional[str] = None,
        relevance_category: Optional[str] = None,
        is_read: Optional[bool] = None,
        starred: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """查询情报条目

        Args:
            source: 按来源过滤
            relevance_category: 按相关性分类过滤
            is_read: 按已读状态过滤
            starred: 按收藏状态过滤
            search: 搜索关键词（匹配名称和描述）
            limit: 每页数量
            offset: 偏移量

        Returns:
            Dict: 包含 items 和 total 的字典
        """
        pool = await get_db_pool()

        conditions = []
        params = []
        param_idx = 1

        if source:
            conditions.append(f"source = ${param_idx}")
            params.append(source)
            param_idx += 1

        if relevance_category:
            conditions.append(f"relevance_category = ${param_idx}")
            params.append(relevance_category)
            param_idx += 1

        if is_read is not None:
            conditions.append(f"is_read = ${param_idx}")
            params.append(is_read)
            param_idx += 1

        if starred is not None:
            conditions.append(f"starred = ${param_idx}")
            params.append(starred)
            param_idx += 1

        if search:
            conditions.append(f"(name ILIKE ${param_idx} OR description ILIKE ${param_idx})")
            params.append(f"%{search}%")
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 获取总数
        count_sql = f"SELECT COUNT(*) FROM intelligence_items {where_clause}"
        total = await pool.fetchval(count_sql, *params)

        # 获取分页数据
        data_sql = f"""
            SELECT id, source, source_id, name, description, url, language,
                   tags, metrics, relevance_score, relevance_category,
                   relevance_reason, is_read, notes, starred,
                   collected_at, updated_at
            FROM intelligence_items {where_clause}
            ORDER BY relevance_score DESC, collected_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])
        rows = await pool.fetch(data_sql, *params)

        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "source": row["source"],
                    "source_id": row["source_id"],
                    "name": row["name"],
                    "description": row["description"],
                    "url": row["url"],
                    "language": row["language"],
                    "tags": row["tags"] or [],
                    "metrics": (
                        json.loads(row["metrics"])
                        if isinstance(row["metrics"], str)
                        else row["metrics"]
                    ),
                    "relevance_score": row["relevance_score"],
                    "relevance_category": row["relevance_category"],
                    "relevance_reason": row["relevance_reason"],
                    "is_read": row["is_read"],
                    "notes": row["notes"],
                    "starred": row["starred"],
                    "collected_at": (
                        row["collected_at"].isoformat() if row["collected_at"] else None
                    ),
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
            )

        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """获取单个情报条目详情

        Args:
            item_id: 条目ID

        Returns:
            Optional[Dict]: 条目详情，不存在时返回None
        """
        pool = await get_db_pool()
        row = await pool.fetchrow(
            """
            SELECT id, source, source_id, name, description, url, language,
                   tags, metrics, relevance_score, relevance_category,
                   relevance_reason, is_read, notes, starred,
                   collected_at, updated_at
            FROM intelligence_items WHERE id = $1
            """,
            item_id,
        )
        if not row:
            return None

        return {
            "id": row["id"],
            "source": row["source"],
            "source_id": row["source_id"],
            "name": row["name"],
            "description": row["description"],
            "url": row["url"],
            "language": row["language"],
            "tags": row["tags"] or [],
            "metrics": (
                json.loads(row["metrics"]) if isinstance(row["metrics"], str) else row["metrics"]
            ),
            "relevance_score": row["relevance_score"],
            "relevance_category": row["relevance_category"],
            "relevance_reason": row["relevance_reason"],
            "is_read": row["is_read"],
            "notes": row["notes"],
            "starred": row["starred"],
            "collected_at": row["collected_at"].isoformat() if row["collected_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    async def mark_read(self, item_id: int, is_read: bool = True) -> bool:
        """标记条目为已读/未读

        Args:
            item_id: 条目ID
            is_read: 是否已读

        Returns:
            bool: 是否成功
        """
        pool = await get_db_pool()
        result = await pool.execute(
            "UPDATE intelligence_items SET is_read = $1 WHERE id = $2",
            is_read,
            item_id,
        )
        return "UPDATE 1" in result

    async def toggle_star(self, item_id: int) -> Optional[bool]:
        """切换条目收藏状态

        Args:
            item_id: 条目ID

        Returns:
            Optional[bool]: 切换后的收藏状态，不存在返回None
        """
        pool = await get_db_pool()
        row = await pool.fetchrow(
            "UPDATE intelligence_items SET starred = NOT starred WHERE id = $1 RETURNING starred",
            item_id,
        )
        return row["starred"] if row else None

    async def update_notes(self, item_id: int, notes: str) -> bool:
        """更新条目备注

        Args:
            item_id: 条目ID
            notes: 备注内容

        Returns:
            bool: 是否成功
        """
        pool = await get_db_pool()
        result = await pool.execute(
            "UPDATE intelligence_items SET notes = $1 WHERE id = $2",
            notes,
            item_id,
        )
        return "UPDATE 1" in result

    async def get_dashboard(self) -> Dict[str, Any]:
        """获取情报仪表盘摘要

        Returns:
            Dict: 包含各来源统计、分类统计、最近采集等
        """
        pool = await get_db_pool()

        # 总体统计
        stats_row = await pool.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE NOT is_read) AS unread,
                COUNT(*) FILTER (WHERE starred) AS starred_count,
                COUNT(*) FILTER (WHERE relevance_category = 'high_value') AS high_value,
                COUNT(*) FILTER (WHERE relevance_category = 'medium_value') AS medium_value,
                COUNT(*) FILTER (WHERE relevance_category = 'monitoring') AS monitoring,
                ROUND(AVG(relevance_score), 1) AS avg_score
            FROM intelligence_items
        """
        )

        # 各来源统计
        source_rows = await pool.fetch(
            """
            SELECT
                source,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE NOT is_read) AS unread,
                COUNT(*) FILTER (WHERE starred) AS starred_count,
                ROUND(AVG(relevance_score), 1) AS avg_score,
                MAX(collected_at) AS last_collected
            FROM intelligence_items
            GROUP BY source
            ORDER BY source
        """
        )

        # 最近采集任务
        recent_collections = await pool.fetch(
            """
            SELECT id, source, status, items_found, items_new, items_updated,
                   duration_ms, started_at, completed_at, error_message
            FROM intelligence_collections
            ORDER BY started_at DESC
            LIMIT 10
        """
        )

        # 最近高价值条目
        recent_high_value = await pool.fetch(
            """
            SELECT id, source, source_id, name, description, url,
                   relevance_score, relevance_category, collected_at
            FROM intelligence_items
            WHERE relevance_category = 'high_value'
            ORDER BY collected_at DESC
            LIMIT 5
        """
        )

        return {
            "summary": {
                "total": stats_row["total"] if stats_row else 0,
                "unread": stats_row["unread"] if stats_row else 0,
                "starred": stats_row["starred_count"] if stats_row else 0,
                "high_value": stats_row["high_value"] if stats_row else 0,
                "medium_value": stats_row["medium_value"] if stats_row else 0,
                "monitoring": stats_row["monitoring"] if stats_row else 0,
                "avg_score": (
                    float(stats_row["avg_score"]) if stats_row and stats_row["avg_score"] else 0.0
                ),
            },
            "by_source": [
                {
                    "source": row["source"],
                    "total": row["total"],
                    "unread": row["unread"],
                    "starred": row["starred_count"],
                    "avg_score": float(row["avg_score"]) if row["avg_score"] else 0.0,
                    "last_collected": (
                        row["last_collected"].isoformat() if row["last_collected"] else None
                    ),
                }
                for row in source_rows
            ],
            "recent_collections": [
                {
                    "id": row["id"],
                    "source": row["source"],
                    "status": row["status"],
                    "items_found": row["items_found"],
                    "items_new": row["items_new"],
                    "items_updated": row["items_updated"],
                    "duration_ms": row["duration_ms"],
                    "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                    "completed_at": (
                        row["completed_at"].isoformat() if row["completed_at"] else None
                    ),
                    "error_message": row["error_message"],
                }
                for row in recent_collections
            ],
            "recent_high_value": [
                {
                    "id": row["id"],
                    "source": row["source"],
                    "name": row["name"],
                    "description": row["description"],
                    "url": row["url"],
                    "relevance_score": row["relevance_score"],
                    "collected_at": (
                        row["collected_at"].isoformat() if row["collected_at"] else None
                    ),
                }
                for row in recent_high_value
            ],
        }

    async def _create_collection_record(self, source: str) -> int:
        """创建采集任务记录

        Args:
            source: 来源标识

        Returns:
            int: 采集任务ID
        """
        pool = await get_db_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO intelligence_collections (source, status)
            VALUES ($1, 'running')
            RETURNING id
            """,
            source,
        )
        return row["id"]

    async def _update_collection_record(
        self,
        collection_id: int,
        status: str,
        items_found: int = 0,
        items_new: int = 0,
        items_updated: int = 0,
        duration_ms: int = 0,
        error_message: Optional[str] = None,
        errors: Optional[List[str]] = None,
    ) -> None:
        """更新采集任务记录

        Args:
            collection_id: 采集任务ID
            status: 任务状态
            items_found: 发现条目数
            items_new: 新增条目数
            items_updated: 更新条目数
            duration_ms: 耗时（毫秒）
            error_message: 错误信息
            errors: 错误列表
        """
        pool = await get_db_pool()
        combined_error = error_message or ("; ".join(errors) if errors else None)

        await pool.execute(
            """
            UPDATE intelligence_collections
            SET status = $1, items_found = $2, items_new = $3,
                items_updated = $4, duration_ms = $5, error_message = $6,
                completed_at = NOW()
            WHERE id = $7
            """,
            status,
            items_found,
            items_new,
            items_updated,
            duration_ms,
            combined_error,
            collection_id,
        )

    async def _persist_items(self, items: List[IntelligenceItem]) -> None:
        """将采集到的情报条目写入数据库（UPSERT）

        Args:
            items: 情报条目列表
        """
        pool = await get_db_pool()
        for item in items:
            try:
                metrics_json = json.dumps(item.metrics, ensure_ascii=False)

                _row = await pool.fetchrow(  # noqa: F841
                    """
                    INSERT INTO intelligence_items (
                        source, source_id, name, description, url, language,
                        tags, metrics, relevance_score, relevance_category,
                        relevance_reason
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (source, source_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        url = EXCLUDED.url,
                        language = EXCLUDED.language,
                        tags = EXCLUDED.tags,
                        metrics = EXCLUDED.metrics,
                        relevance_score = EXCLUDED.relevance_score,
                        relevance_category = EXCLUDED.relevance_category,
                        relevance_reason = EXCLUDED.relevance_reason,
                        updated_at = NOW()
                    RETURNING (xmax = 0) AS is_new
                    """,
                    item.source,
                    item.source_id,
                    item.name,
                    item.description,
                    item.url,
                    item.language,
                    item.tags,
                    metrics_json,
                    item.relevance_score,
                    item.relevance_category,
                    item.relevance_reason,
                )
            except Exception as e:
                logger.error(f"持久化情报条目失败 [{item.source}:{item.source_id}]: {e}")
