"""文档管理API路由"""

import json
import logging
from typing import Any, Dict, List, Optional

from core.database import init_db_pool
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


# ========== 数据模型 ==========


class DocumentCreate(BaseModel):
    """创建文档请求模型"""

    title: str = Field(..., min_length=1, max_length=500, description="文档标题")
    content: str = Field(..., min_length=1, description="文档内容")
    category: str = Field(..., pattern="^(气功|中医|儒家)$", description="文档分类")
    tags: List[str] = Field(default_factory=list, description="文档标签")


# ========== 路由 ==========


@router.get("")
async def list_documents(
    category: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """获取文档列表"""
    pool = await init_db_pool()

    if category:
        rows = await pool.fetch(
            """SELECT id, title, category, tags, created_at
               FROM documents WHERE category = $1
               ORDER BY id LIMIT $2 OFFSET $3""",
            category,
            limit,
            offset,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, title, category, tags, created_at
               FROM documents ORDER BY id LIMIT $1 OFFSET $2""",
            limit,
            offset,
        )

    return {"total": len(rows), "documents": [dict(row) for row in rows]}


@router.get("/{doc_id}")
async def get_document(doc_id: int) -> Dict[str, Any]:
    """获取单个文档"""
    pool = await init_db_pool()
    row = await pool.fetchrow(
        """SELECT id, title, content, category, tags, created_at
           FROM documents WHERE id = $1""",
        doc_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")

    return dict(row)


@router.post("", status_code=201)
async def create_document(doc: DocumentCreate) -> Dict[str, Any]:
    """创建文档"""
    pool = await init_db_pool()

    if len(doc.tags) > 10:
        raise HTTPException(status_code=400, detail="标签数量不能超过10个")

    doc_id = await pool.fetchval(
        """INSERT INTO documents (title, content, category, tags)
           VALUES ($1, $2, $3, $4::jsonb) RETURNING id""",
        doc.title,
        doc.content,
        doc.category,
        json.dumps(doc.tags),
    )

    logger.info(f"Created document: {doc_id} - {doc.title}")
    return {"id": doc_id, "message": "文档创建成功"}
