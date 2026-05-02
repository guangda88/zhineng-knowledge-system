"""纠错向量库 API — 检索历史纠错记录，辅助输出自检"""

import json

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.common.db_helpers import require_pool

router = APIRouter(prefix="/api/v1/corrections", tags=["corrections"])


class CorrectionQuery(BaseModel):
    text: str
    top_k: int = 5
    error_type: str | None = None


class CorrectionRecord(BaseModel):
    id: int
    error_type: str
    original_output: str
    correction: str
    context: str
    rule: str
    similarity: float | None = None


@router.post("/search", summary="检索相似纠错记录")
async def search_corrections(query: CorrectionQuery):
    """给定一段文本，检索最相似的历史纠错记录。"""
    pool = require_pool()
    import httpx

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://localhost:8001/embed",
            json={"text": query.text},
            timeout=10,
        )
        if r.status_code != 200:
            return {"status": "error", "error": "embedding service unavailable"}
        data = r.json()
        embedding = data.get("embedding") or data.get("data", [{}])[0].get("embedding")

    if not embedding:
        return {"status": "error", "error": "embedding failed"}

    async with pool.acquire() as conn:
        type_filter = "AND c.error_type = $3" if query.error_type else ""
        params = [str(embedding), query.top_k]
        if query.error_type:
            params.append(query.error_type)

        rows = await conn.fetch(
            f"""
            SELECT c.id, c.error_type, c.original_output, c.correction,
                   c.context, c.metadata->>'rule' as rule,
                   1 - (c.embedding <=> $1::vector) as similarity
            FROM corrections c
            WHERE c.embedding IS NOT NULL {type_filter}
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2
            """,
            *params,
        )

    results = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "error_type": row["error_type"],
                "original_output": row["original_output"],
                "correction": row["correction"],
                "context": row["context"],
                "rule": row["rule"],
                "similarity": round(row["similarity"], 4),
            }
        )

    return {"status": "ok", "data": results, "count": len(results)}


@router.post("/check", summary="输出自检 — 规则检查 + 向量检索")
async def check_output(query: CorrectionQuery):
    """检查一段待输出的文本。先用确定性规则扫描，再检索相似历史纠错。"""
    pool = require_pool()
    from backend.services.output_rules import quick_check

    rule_result = quick_check(query.text)

    import httpx

    embedding = None
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://localhost:8001/embed",
            json={"text": query.text},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            embedding = data.get("embedding") or data.get("data", [{}])[0].get("embedding")

    vector_warnings = []
    if embedding:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.error_type, c.original_output, c.correction,
                       c.metadata->>'rule' as rule,
                       1 - (c.embedding <=> $1::vector) as similarity
                FROM corrections c
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
                """,
                str(embedding),
                query.top_k,
            )

        for row in rows:
            sim = row["similarity"]
            if sim > 0.7:
                vector_warnings.append(
                    {
                        "type": row["error_type"],
                        "similar_error": row["original_output"][:100],
                        "correction": row["correction"][:100],
                        "rule": row["rule"],
                        "similarity": round(sim, 4),
                    }
                )

    total_risk = rule_result["risk_score"]
    if vector_warnings:
        total_risk = min(total_risk + 0.15, 1.0)

    if total_risk > 0.3:
        level = "high"
    elif total_risk > 0.15:
        level = "medium"
    else:
        level = "low"

    return {
        "status": "ok",
        "warning_level": level,
        "risk_score": round(total_risk, 2),
        "rule_check": rule_result,
        "vector_warnings": vector_warnings,
    }


@router.get("/stats", summary="纠错库统计")
async def correction_stats():
    """返回纠错库的统计信息。"""
    pool = require_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT count(*) FROM corrections")
        type_dist = await conn.fetch(
            "SELECT error_type, count(*) as cnt FROM corrections GROUP BY error_type ORDER BY cnt DESC"
        )
        with_embed = await conn.fetchval(
            "SELECT count(*) FROM corrections WHERE embedding IS NOT NULL"
        )

    return {
        "status": "ok",
        "data": {
            "total": total,
            "with_embedding": with_embed,
            "type_distribution": [
                {"error_type": r["error_type"], "count": r["cnt"]} for r in type_dist
            ],
        },
    }


@router.post("/add", summary="添加新的纠错记录")
async def add_correction(
    error_type: str = Query(...),
    original_output: str = Query(...),
    correction: str = Query(...),
    context: str = Query(""),
    rule: str = Query(""),
):
    """手动添加一条纠错记录。"""
    pool = require_pool()
    import httpx

    embed_text = f"{original_output} {correction} {context}"
    embedding = None

    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://localhost:8001/embed",
            json={"text": embed_text},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            embedding = data.get("embedding") or data.get("data", [{}])[0].get("embedding")

    async with pool.acquire() as conn:
        row_id = await conn.fetchval(
            """
            INSERT INTO corrections (error_type, original_output, correction, context, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            error_type,
            original_output,
            correction,
            context,
            str(embedding) if embedding else None,
            json.dumps({"rule": rule}),
        )

    return {"status": "ok", "id": row_id, "embedding": embedding is not None}
