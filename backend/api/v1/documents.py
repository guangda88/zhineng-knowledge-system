"""文档管理API路由"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.common import fetch_one_or_404, rows_to_list
from backend.common.typing import JSONResponse
from backend.core.database import init_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


# ========== 数据模型 ==========


class DocumentCreate(BaseModel):
    """创建文档请求模型"""

    title: str = Field(..., min_length=1, max_length=500, description="文档标题")
    content: str = Field(..., min_length=1, description="文档内容")
    category: str = Field(
        ...,
        pattern="^(气功|中医|儒家|佛家|道家|武术|哲学|科学|心理学)$",
        description="文档分类",
    )
    tags: List[str] = Field(default_factory=list, description="文档标签")


# ========== 路由 ==========


@router.get("")
async def list_documents(
    category: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> JSONResponse:
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

    return {"total": len(rows), "documents": rows_to_list(rows)}


@router.get("/{doc_id}")
async def get_document(doc_id: int) -> JSONResponse:
    """获取单个文档"""
    pool = await init_db_pool()
    return await fetch_one_or_404(
        pool,
        """SELECT id, title, content, category, tags, created_at
           FROM documents WHERE id = $1""",
        doc_id,
        error_message="文档不存在",
    )


@router.post("", status_code=201)
async def create_document(doc: DocumentCreate) -> JSONResponse:
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
