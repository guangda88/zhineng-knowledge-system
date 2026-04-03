"""sys_books 书目检索API

提供对 302 万条书目记录的搜索、统计、分类浏览等功能。
使用 asyncpg 直接查询 sys_books 表。
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.common.db_helpers import row_to_dict
from backend.core.dependency_injection import get_db_pool as _get_di_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sysbooks", tags=["书目检索"])


def _pool():
    pool = _get_di_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="数据库连接池未初始化")
    return pool


@router.get("/search")
async def search_books(
    q: str = Query("", max_length=200, description="搜索关键词（文件名/路径）"),
    domain: Optional[str] = Query(None, description="领域筛选"),
    extension: Optional[str] = Query(None, description="扩展名筛选（pdf/txt/djvu等）"),
    source: Optional[str] = Query(None, description="来源筛选"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """书目搜索

    支持按文件名、路径模糊搜索，支持领域、扩展名、来源筛选。
    """
    try:
        pool = _pool()
        conditions = []
        params = []
        idx = 1

        if q and q.strip():
            conditions.append(f"(filename ILIKE ${idx} OR path ILIKE ${idx})")
            params.append(f"%{q.strip()}%")
            idx += 1

        if domain:
            conditions.append(f"domain = ${idx}")
            params.append(domain)
            idx += 1

        if extension:
            conditions.append(f"extension = ${idx}")
            params.append(extension.lower().lstrip("."))
            idx += 1

        if source:
            conditions.append(f"source = ${idx}")
            params.append(source)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        if where:
            total = await pool.fetchval(
                f"SELECT COUNT(*) FROM sys_books {where}",
                *params,
                timeout=30,
            )
        else:
            estimate = await pool.fetchrow(
                "SELECT reltuples::bigint AS estimate FROM pg_class WHERE oid = 'sys_books'::regclass"
            )
            total = estimate["estimate"] if estimate else 3024428

        offset = (page - 1) * size
        rows = await pool.fetch(
            f"""
            SELECT id, source, path, filename, category, author, year,
                   book_number, file_type, size, extension, domain, subcategory
            FROM sys_books
            {where}
            ORDER BY id
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            size,
            offset,
        )

        return {
            "status": "ok",
            "data": {
                "total": total or 0,
                "page": page,
                "size": size,
                "results": [row_to_dict(r) for r in rows],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"search_books failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="搜索书目失败")


@router.get("/stats")
async def get_stats():
    """书目统计

    返回总量、领域分布、扩展名分布等统计数据。
    """
    try:
        pool = _pool()

        estimate = await pool.fetchrow(
            "SELECT reltuples::bigint AS estimate FROM pg_class WHERE oid = 'sys_books'::regclass"
        )
        total = estimate["estimate"] if estimate else 3024428

        domain_rows = await pool.fetch(
            "SELECT domain, COUNT(*) as cnt FROM sys_books GROUP BY domain ORDER BY cnt DESC"
        )

        ext_rows = await pool.fetch("""
            SELECT extension, COUNT(*) as cnt
            FROM sys_books
            WHERE extension IS NOT NULL
            GROUP BY extension
            ORDER BY cnt DESC
            LIMIT 20
            """)

        source_rows = await pool.fetch(
            "SELECT source, COUNT(*) as cnt FROM sys_books GROUP BY source ORDER BY cnt DESC"
        )

        file_type_rows = await pool.fetch("""
            SELECT file_type, COUNT(*) as cnt
            FROM sys_books
            WHERE file_type IS NOT NULL
            GROUP BY file_type
            ORDER BY cnt DESC
            """)

        return {
            "status": "ok",
            "data": {
                "total": total,
                "by_domain": [{"domain": r["domain"], "count": r["cnt"]} for r in domain_rows],
                "by_extension": [
                    {"extension": r["extension"], "count": r["cnt"]} for r in ext_rows
                ],
                "by_source": [{"source": r["source"], "count": r["cnt"]} for r in source_rows],
                "by_file_type": [
                    {"file_type": r["file_type"], "count": r["cnt"]} for r in file_type_rows
                ],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询书目统计失败")


@router.get("/domains")
async def get_domains():
    """领域分类树

    返回所有领域及其子分类的文档数量。
    """
    try:
        pool = _pool()

        rows = await pool.fetch("""
            SELECT domain, subcategory, COUNT(*) as cnt
            FROM sys_books
            WHERE domain IS NOT NULL
            GROUP BY domain, subcategory
            ORDER BY domain, cnt DESC
            """)

        tree: Dict[str, Any] = {}
        for r in rows:
            d = r["domain"]
            sc = r["subcategory"]
            cnt = r["cnt"]
            if d not in tree:
                tree[d] = {"domain": d, "total": 0, "subcategories": []}
            tree[d]["total"] += cnt
            if sc:
                tree[d]["subcategories"].append({"name": sc, "count": cnt})

        return {
            "status": "ok",
            "data": sorted(tree.values(), key=lambda x: x["total"], reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_domains failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询领域分类失败")


@router.get("/{book_id}")
async def get_book(book_id: int):
    """获取单条书目详情"""
    try:
        pool = _pool()

        row = await pool.fetchrow(
            """
            SELECT id, source, path, filename, category, author, year,
                   book_number, file_type, size, extension, created_date,
                   publisher, domain, subcategory
            FROM sys_books
            WHERE id = $1
            """,
            book_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail=f"书目 {book_id} 不存在")

        return {"status": "ok", "data": row_to_dict(row)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_book failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询书目详情失败")
