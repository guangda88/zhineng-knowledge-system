"""Phase 2/3 API: 内容提取管道 + 知识图谱 + 维度标注

提供以下端点：
- GET  /api/v1/pipeline/stats — 总览统计
- POST /api/v1/pipeline/extract — 触发内容提取
- POST /api/v1/pipeline/tag — 触发维度标注
- POST /api/v1/pipeline/kg-build — 触发知识图谱构建
- POST /api/v1/pipeline/cross-ref — 触发 data.db 对账
- GET  /api/v1/pipeline/tasks — 任务列表
- GET  /api/v1/pipeline/kg/stats — 知识图谱统计
- GET  /api/v1/pipeline/kg/entities — 实体搜索
- GET  /api/v1/pipeline/kg/graph — 子图查询
"""

import asyncio
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from backend.common.db_helpers import row_to_dict
from backend.core.dependency_injection import get_db_pool as _get_di_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pipeline", tags=["Phase 2/3 管道"])

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost:5432/zhineng_kb",
)


def _pool():
    pool = _get_di_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接池未初始化")
    return pool


# ============================================================
# Request Models
# ============================================================


class ExtractRequest(BaseModel):
    extensions: Optional[List[str]] = None
    domain: Optional[str] = None
    limit: int = 1000


class TagRequest(BaseModel):
    domain: Optional[str] = None
    limit: int = 50000
    dry_run: bool = False


class KGBuildRequest(BaseModel):
    domain: Optional[str] = None
    limit: int = 100000


# ============================================================
# Stats & Overview
# ============================================================


@router.get("/stats")
async def get_pipeline_stats():
    """Phase 2/3 管道总览统计（使用 pg_class 快速估算大表）"""
    pool = _pool()

    async with pool.acquire() as conn:
        # sys_books total — use pg_class estimate for 3M+ row table
        total = (
            await conn.fetchval(
                "SELECT reltuples::bigint FROM pg_class WHERE relname = 'sys_books'"
            )
            or 3024428
        )

        # sys_books extraction stats — use pg_class estimate
        extraction = await conn.fetch("""
            SELECT extraction_status, COUNT(*) as cnt
            FROM sys_books
            GROUP BY extraction_status
            ORDER BY cnt DESC
        """)

        # sys_books tagging — partial GIN index makes this fast
        tagged = await conn.fetchval(
            "SELECT COUNT(*) FROM sys_books WHERE qigong_dims != '{}'::jsonb"
        )

        # Cross-reference stats
        cross_ref = await conn.fetch("""
            SELECT cross_ref_status, COUNT(*) as cnt
            FROM sys_books
            GROUP BY cross_ref_status
            ORDER BY cnt DESC
        """)

        # Content stats
        contents = await conn.fetchval("SELECT COUNT(*) FROM sys_book_contents")
        total_chars = await conn.fetchval(
            "SELECT COALESCE(SUM(char_count), 0) FROM sys_book_contents"
        )

        # KG stats
        entities = await conn.fetchval("SELECT COUNT(*) FROM kg_entities")
        relations = await conn.fetchval("SELECT COUNT(*) FROM kg_relations")

        # Recent tasks
        tasks = await conn.fetch("""
            SELECT id, task_type, status, total_items, processed_items,
                   failed_items, created_at, completed_at
            FROM extraction_tasks
            ORDER BY created_at DESC
            LIMIT 5
        """)

        return {
            "status": "ok",
            "data": {
                "sys_books": {
                    "total": total,
                    "extraction": {r["extraction_status"]: r["cnt"] for r in extraction},
                    "tagging": {
                        "tagged": tagged,
                        "untagged": total - tagged,
                        "coverage_percent": round(tagged / total * 100, 1) if total else 0,
                    },
                    "cross_reference": {r["cross_ref_status"]: r["cnt"] for r in cross_ref},
                },
                "contents": {
                    "extracted_books": contents,
                    "total_chars": total_chars,
                },
                "knowledge_graph": {
                    "entities": entities,
                    "relations": relations,
                },
                "recent_tasks": [row_to_dict(t) for t in tasks],
            },
        }


# ============================================================
# Content Extraction
# ============================================================


@router.post("/extract")
async def trigger_extraction(
    req: ExtractRequest,
    background_tasks: BackgroundTasks,
):
    """触发内容提取（后台任务）"""
    from backend.services.content_extraction.extractor import BatchExtractionService

    service = BatchExtractionService(DB_URL)

    async def run():
        try:
            await service.extract_batch(
                extensions=req.extensions,
                domain=req.domain,
                limit=req.limit,
            )
        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
        finally:
            await service.close()

    background_tasks.add_task(run)

    return {
        "status": "ok",
        "message": f"Extraction started: limit={req.limit}, domain={req.domain}",
        "data": {"extensions": req.extensions, "domain": req.domain, "limit": req.limit},
    }


# ============================================================
# Dimension Tagging
# ============================================================


@router.post("/tag")
async def trigger_tagging(
    req: TagRequest,
    background_tasks: BackgroundTasks,
):
    """触发维度标注（后台任务）"""
    from backend.services.content_extraction.sysbooks_tagger import SysBooksDimensionTagger

    tagger = SysBooksDimensionTagger(DB_URL)

    async def run():
        try:
            await tagger.tag_batch(
                domain=req.domain,
                limit=req.limit,
                dry_run=req.dry_run,
            )
        except Exception as e:
            logger.error(f"Tagging failed: {e}", exc_info=True)
        finally:
            await tagger.close()

    background_tasks.add_task(run)

    return {
        "status": "ok",
        "message": f"Tagging started: limit={req.limit}, domain={req.domain}, dry_run={req.dry_run}",
    }


@router.get("/tag/stats")
async def get_tagging_stats():
    """获取标注统计详情"""
    from backend.services.content_extraction.sysbooks_tagger import SysBooksDimensionTagger

    tagger = SysBooksDimensionTagger(DB_URL)
    try:
        stats = await tagger.get_tagging_stats()
        return {"status": "ok", "data": stats}
    finally:
        await tagger.close()


# ============================================================
# Knowledge Graph
# ============================================================


@router.post("/kg-build")
async def trigger_kg_build(
    req: KGBuildRequest,
    background_tasks: BackgroundTasks,
):
    """触发知识图谱构建（后台任务）"""
    from backend.services.knowledge_graph.builder import KnowledgeGraphBuilder

    builder = KnowledgeGraphBuilder(DB_URL)

    async def run():
        try:
            await builder.build_from_metadata(domain=req.domain, limit=req.limit)
            await builder.build_path_hierarchy()
            await builder.build_domain_associations()
        except Exception as e:
            logger.error(f"KG build failed: {e}", exc_info=True)
        finally:
            await builder.close()

    background_tasks.add_task(run)

    return {
        "status": "ok",
        "message": f"Knowledge graph build started: limit={req.limit}, domain={req.domain}",
    }


@router.get("/kg/stats")
async def get_kg_stats():
    """知识图谱统计"""
    from backend.services.knowledge_graph.builder import KnowledgeGraphBuilder

    builder = KnowledgeGraphBuilder(DB_URL)
    try:
        stats = await builder.get_graph_stats()
        return {"status": "ok", "data": stats}
    finally:
        await builder.close()


@router.get("/kg/entities")
async def search_entities(
    q: str = Query("", max_length=200, description="搜索实体名称"),
    entity_type: Optional[str] = Query(None, description="实体类型筛选"),
    limit: int = Query(20, ge=1, le=100),
):
    """搜索知识图谱实体"""
    pool = _pool()

    conditions = []
    params: list = []
    idx = 1

    if q and q.strip():
        conditions.append(f"name LIKE ${idx}")
        params.append(f"%{q.strip()}%")
        idx += 1

    if entity_type:
        conditions.append(f"entity_type = ${idx}")
        params.append(entity_type)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, name, entity_type, description, mention_count, properties
            FROM kg_entities
            {where}
            ORDER BY mention_count DESC
            LIMIT ${idx}
            """,
            *params,
            limit,
        )

    return {
        "status": "ok",
        "data": [row_to_dict(r) for r in rows],
    }


@router.get("/kg/graph")
async def get_subgraph(
    entity_id: int = Query(..., description="中心实体ID"),
    depth: int = Query(2, ge=1, le=3, description="扩展深度"),
):
    """获取实体周围的子图"""
    pool = _pool()

    async with pool.acquire() as conn:
        # Get center entity
        center = await conn.fetchrow(
            "SELECT id, name, entity_type FROM kg_entities WHERE id = $1",
            entity_id,
        )
        if not center:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

        # BFS to find neighbors
        visited = {entity_id}
        current_level = [entity_id]
        all_entity_ids = {entity_id}
        all_relations: list = []

        for d in range(depth):
            next_level = set()
            for eid in current_level:
                rels = await conn.fetch(
                    """
                    SELECT r.id, r.source_entity_id, r.target_entity_id,
                           r.relation_type, r.weight,
                           se.name as source_name, se.entity_type as source_type,
                           te.name as target_name, te.entity_type as target_type
                    FROM kg_relations r
                    JOIN kg_entities se ON r.source_entity_id = se.id
                    JOIN kg_entities te ON r.target_entity_id = te.id
                    WHERE r.source_entity_id = $1 OR r.target_entity_id = $1
                    """,
                    eid,
                )

                for rel in rels:
                    all_relations.append(row_to_dict(rel))
                    neighbor = (
                        rel["target_entity_id"]
                        if rel["source_entity_id"] == eid
                        else rel["source_entity_id"]
                    )
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
                        all_entity_ids.add(neighbor)

            current_level = list(next_level)

        # Get all entities in subgraph
        entities = await conn.fetch(
            """
            SELECT id, name, entity_type, mention_count
            FROM kg_entities
            WHERE id = ANY($1::bigint[])
            """,
            list(all_entity_ids),
        )

        return {
            "status": "ok",
            "data": {
                "center": row_to_dict(center),
                "entities": [row_to_dict(e) for e in entities],
                "relations": all_relations,
                "depth": depth,
                "total_entities": len(entities),
                "total_relations": len(all_relations),
            },
        }


# ============================================================
# Cross-reference
# ============================================================


@router.post("/cross-ref")
async def trigger_cross_ref(background_tasks: BackgroundTasks):
    """触发 data.db ↔ sys_books 对账（后台任务）"""
    script_path = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ),
        "scripts",
        "cross_reference_data.py",
    )

    async def run():
        proc = await asyncio.create_subprocess_exec(
            "python3",
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"Cross-reference failed: {stderr.decode()}")

    background_tasks.add_task(run)

    return {"status": "ok", "message": "Cross-reference started in background"}


# ============================================================
# Task Management
# ============================================================


@router.get("/tasks")
async def list_tasks(
    task_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """获取任务列表"""
    pool = _pool()

    conditions = []
    params: list = []
    idx = 1

    if task_type:
        conditions.append(f"task_type = ${idx}")
        params.append(task_type)
        idx += 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, task_type, status, total_items, processed_items,
                   failed_items, config, result_summary, error_message,
                   started_at, completed_at, created_at
            FROM extraction_tasks
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx}
            """,
            *params,
            limit,
        )

    return {
        "status": "ok",
        "data": [row_to_dict(r) for r in rows],
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """获取任务详情"""
    pool = _pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, task_type, status, total_items, processed_items,
                   failed_items, config, result_summary, error_message,
                   started_at, completed_at, created_at
            FROM extraction_tasks
            WHERE id = $1
            """,
            task_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {"status": "ok", "data": row_to_dict(row)}
