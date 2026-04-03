"""数据分析器

对知识库进行多维度分析
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from backend.core.database import get_db_pool

logger = logging.getLogger(__name__)


class DataAnalyzer:
    """数据分析器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def analyze_knowledge_graph(self) -> Dict[str, Any]:
        """分析知识图谱

        基于文档统计的知识图谱近似分析。
        """
        pool = await get_db_pool()

        total_docs = await pool.fetchval("SELECT COUNT(*) FROM documents")

        cat_rows = await pool.fetch(
            "SELECT category, COUNT(*) AS cnt FROM documents GROUP BY category ORDER BY cnt DESC"
        )
        node_types = {r["category"]: r["cnt"] for r in cat_rows if r["category"]}

        tag_rows = await pool.fetch(
            "SELECT unnest(string_to_array(COALESCE(tags, ''), ',')) AS tag, COUNT(*) AS cnt "
            "FROM documents WHERE tags IS NOT NULL AND tags != '' "
            "GROUP BY tag ORDER BY cnt DESC LIMIT 20"
        )
        top_tags = [
            {"tag": r["tag"].strip(), "count": r["cnt"]}
            for r in tag_rows
            if r["tag"] and r["tag"].strip()
        ]

        return {
            "total_nodes": total_docs or 0,
            "total_edges": sum(r["cnt"] for r in tag_rows),
            "node_types": node_types,
            "graph_density": round(sum(r["cnt"] for r in cat_rows) / max(total_docs, 1), 4),
            "avg_connections": round(sum(r["cnt"] for r in tag_rows) / max(len(tag_rows), 1), 2),
            "top_tags": top_tags,
            "generated_at": datetime.now().isoformat(),
        }

    async def analyze_learning_progress(self, parameters: Dict) -> Dict[str, Any]:
        """分析学习进度"""
        pool = await get_db_pool()
        user_id = parameters.get("user_id")
        days = parameters.get("days", 30)

        practice_stats = {
            "total_sessions": 0,
            "total_duration_minutes": 0.0,
            "topics_practiced": 0,
            "avg_score": 0.0,
        }

        try:
            row = await pool.fetchrow(
                "SELECT COUNT(*) AS sessions, COALESCE(SUM(duration_minutes), 0) AS total_min "
                "FROM practice_records WHERE created_at >= NOW() - $1::interval",
                f"{days} days",
            )
            if row:
                practice_stats["total_sessions"] = row["sessions"]
                practice_stats["total_duration_minutes"] = float(row["total_min"] or 0)
        except Exception as e:
            logger.warning(f"practice_records query failed: {e}")

        try:
            cat_rows = await pool.fetch(
                "SELECT category, COUNT(*) AS cnt FROM documents GROUP BY category ORDER BY cnt DESC"
            )
            topics = [r["category"] for r in cat_rows if r["category"]]
        except Exception:
            topics = []

        return {
            "user_id": user_id,
            "period_days": days,
            "total_study_hours": round(practice_stats["total_duration_minutes"] / 60, 1),
            "total_practice_sessions": practice_stats["total_sessions"],
            "topics_available": len(topics),
            "topics": topics[:10],
            "generated_at": datetime.now().isoformat(),
        }

    async def analyze_content_distribution(self) -> Dict[str, Any]:
        """分析内容分布"""
        pool = await get_db_pool()

        total = await pool.fetchval("SELECT COUNT(*) FROM documents")

        cat_rows = await pool.fetch(
            "SELECT category, COUNT(*) AS cnt FROM documents GROUP BY category ORDER BY cnt DESC"
        )
        by_category = {r["category"]: r["cnt"] for r in cat_rows if r["category"]}

        growth = {}
        for period, days in [("last_7_days", 7), ("last_30_days", 30), ("last_90_days", 90)]:
            cnt = await pool.fetchval(
                "SELECT COUNT(*) FROM documents WHERE created_at >= NOW() - $1::interval",
                f"{days} days",
            )
            growth[period] = cnt or 0

        return {
            "total_documents": total or 0,
            "by_category": by_category,
            "growth_trend": growth,
            "generated_at": datetime.now().isoformat(),
        }

    async def analyze_user_behavior(self, parameters: Dict) -> Dict[str, Any]:
        """分析用户行为"""
        pool = await get_db_pool()

        result: Dict[str, Any] = {
            "focus_logs_total": 0,
            "focus_logs_7d": 0,
            "top_elements": [],
            "avg_dwell_time_ms": 0,
            "generated_at": datetime.now().isoformat(),
        }

        try:
            total = await pool.fetchval("SELECT COUNT(*) FROM user_focus_log")
            result["focus_logs_total"] = total or 0

            recent = await pool.fetchval(
                "SELECT COUNT(*) FROM user_focus_log WHERE timestamp >= NOW() - INTERVAL '7 days'"
            )
            result["focus_logs_7d"] = recent or 0

            avg = await pool.fetchval(
                "SELECT AVG(dwell_time_ms) FROM user_focus_log WHERE dwell_time_ms IS NOT NULL"
            )
            result["avg_dwell_time_ms"] = round(float(avg), 1) if avg else 0.0

            top_rows = await pool.fetch(
                "SELECT element_id, COUNT(*) AS cnt, AVG(dwell_time_ms) AS avg_dwell "
                "FROM user_focus_log WHERE element_id IS NOT NULL "
                "GROUP BY element_id ORDER BY cnt DESC LIMIT 10"
            )
            result["top_elements"] = [
                {
                    "element_id": r["element_id"],
                    "views": r["cnt"],
                    "avg_dwell_ms": round(float(r["avg_dwell"]), 1),
                }
                for r in top_rows
            ]
        except Exception as e:
            logger.warning(f"user_focus_log queries failed (table may not exist): {e}")

        return result

    async def generate_statistics_report(
        self, report_type: str = "weekly", start_date: datetime = None, end_date: datetime = None
    ) -> Dict[str, Any]:
        """生成统计报告"""
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            if report_type == "daily":
                start_date = end_date - timedelta(days=1)
            elif report_type == "weekly":
                start_date = end_date - timedelta(weeks=1)
            elif report_type == "monthly":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=7)

        # 并行获取各类分析数据
        knowledge_graph, content_dist, user_behavior = await asyncio.gather(
            self.analyze_knowledge_graph(),
            self.analyze_content_distribution(),
            self.analyze_user_behavior({}),
        )

        return {
            "report_type": report_type,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": (end_date - start_date).days,
            },
            "knowledge_graph": knowledge_graph,
            "content_distribution": content_dist,
            "user_behavior": user_behavior,
            "generated_at": datetime.now().isoformat(),
        }
