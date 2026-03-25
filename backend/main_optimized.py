"""智能知识系统 - FastAPI 主入口 (优化版)"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncpg
import os
import json
import logging
from datetime import datetime
from functools import lru_cache
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://zhineng:zhineng123@localhost:5432/zhineng_kb")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = FastAPI(
    title="智能知识系统 API",
    description="基于 RAG 的气功、中医、儒家知识问答系统",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库连接池
pool: Optional[asyncpg.Pool] = None

# 请求统计
request_stats = {"total": 0, "errors": 0}


async def get_db() -> asyncpg.Pool:
    """获取数据库连接"""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            DATABASE_URL, 
            min_size=2, 
            max_size=10,
            command_timeout=60
        )
    return pool


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    start_time = time.time()
    request_stats["total"] += 1
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 只记录 API 请求
        if request.url.path.startswith("/api/"):
            logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
        
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        request_stats["errors"] += 1
        logger.error(f"Request error: {str(e)}")
        raise


# ========== 数据模型 ==========

class Document(BaseModel):
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    category: str = Field(..., pattern="^(气功|中医|儒家)$")
    tags: List[str] = []
    source: str = "manual"

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    category: Optional[str] = Field(None, pattern="^(气功|中医|儒家)$")
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str


# ========== API 路由 ==========

@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "ok",
        "message": "智能知识系统运行中",
        "categories": ["气功", "中医", "儒家"],
        "version": "1.0.0",
        "stats": request_stats
    }


@app.get("/health")
async def health_check():
    """健康检查（用于监控）"""
    db_status = "ok"
    try:
        db = await get_db()
        async with db.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/documents")
async def list_documents(
    category: Optional[str] = None,
    limit: int = Query(100, le=1000, ge=1),
    offset: int = Query(0, ge=0)
):
    """获取文档列表"""
    db = await get_db()
    
    # 只查询需要的字段
    if category:
        rows = await db.fetch(
            "SELECT id, title, category, tags, source, created_at FROM documents WHERE category = $1 ORDER BY id LIMIT $2 OFFSET $3",
            category, limit, offset
        )
    else:
        rows = await db.fetch(
            "SELECT id, title, category, tags, source, created_at FROM documents ORDER BY id LIMIT $1 OFFSET $2",
            limit, offset
        )
    
    documents = []
    for row in rows:
        doc = dict(row)
        if isinstance(doc.get('tags'), str):
            try:
                doc['tags'] = json.loads(doc['tags'])
            except:
                doc['tags'] = []
        documents.append(doc)
    
    return {
        "total": len(documents),
        "documents": documents
    }


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: int):
    """获取单个文档"""
    db = await get_db()
    row = await db.fetchrow(
        "SELECT id, title, content, category, tags, source, created_at FROM documents WHERE id = $1", doc_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    doc = dict(row)
    if isinstance(doc.get('tags'), str):
        try:
            doc['tags'] = json.loads(doc['tags'])
        except:
            doc['tags'] = []
    return doc


@app.post("/api/documents", status_code=201)
async def create_document(doc: Document):
    """创建文档"""
    db = await get_db()
    
    # 验证标签
    if len(doc.tags) > 10:
        raise HTTPException(status_code=400, detail="标签数量不能超过10个")
    
    doc_id = await db.fetchval(
        """INSERT INTO documents (title, content, category, tags, source) 
           VALUES ($1, $2, $3, $4::jsonb, $5) RETURNING id""",
        doc.title, doc.content, doc.category, json.dumps(doc.tags), doc.source
    )
    
    logger.info(f"Created document: {doc_id} - {doc.title}")
    return {"id": doc_id, "message": "文档创建成功"}


@app.get("/api/search")
async def search_documents(
    q: str = Query(..., min_length=1, max_length=200),
    category: Optional[str] = None,
    limit: int = Query(10, le=100, ge=1)
):
    """关键词搜索"""
    db = await get_db()
    
    search_pattern = f"%{q}%"
    
    # 只查询需要的字段
    if category:
        rows = await db.fetch(
            """SELECT id, title, content, category 
               FROM documents 
               WHERE category = $1 AND (title ILIKE $2 OR content ILIKE $2)
               ORDER BY id LIMIT $3""",
            category, search_pattern, limit
        )
    else:
        rows = await db.fetch(
            """SELECT id, title, content, category 
               FROM documents 
               WHERE title ILIKE $1 OR content ILIKE $1
               ORDER BY id LIMIT $2""",
            search_pattern, limit
        )
    
    return {
        "query": q,
        "total": len(rows),
        "results": [dict(row) for row in rows]
    }


@app.post("/api/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """智能问答 (RAG) - 当前为简单版本"""
    db = await get_db()
    
    # 验证问题长度
    if len(request.question.strip()) == 0:
        raise HTTPException(status_code=400, detail="问题不能为空")
    
    search_pattern = f"%{request.question}%"
    
    if request.category:
        rows = await db.fetch(
            """SELECT id, title, content 
               FROM documents 
               WHERE category = $1 AND content ILIKE $2
               LIMIT 3""",
            request.category, search_pattern
        )
    else:
        rows = await db.fetch(
            """SELECT id, title, content 
               FROM documents 
               WHERE content ILIKE $1 LIMIT 3""",
            search_pattern
        )
    
    sources = [dict(row) for row in rows]
    
    if sources:
        answer = f"根据知识库找到 {len(sources)} 条相关内容：\n\n"
        for i, s in enumerate(sources[:3], 1):
            content_preview = s['content'][:150] + "..." if len(s['content']) > 150 else s['content']
            answer += f"{i}. **{s['title']}**\n{content_preview}\n\n"
    else:
        answer = "抱歉，知识库中没有找到相关内容。请尝试其他关键词，如：气功、八段锦、中医、论语等。"
    
    session_id = request.session_id or datetime.now().strftime("%Y%m%d%H%M%S")
    
    # 保存历史
    try:
        await db.execute(
            """INSERT INTO chat_history (session_id, question, answer, sources) 
               VALUES ($1, $2, $3, $4::jsonb)""",
            session_id, request.question, answer, json.dumps(sources, ensure_ascii=False)
        )
    except Exception as e:
        logger.error(f"Failed to save chat history: {e}")
    
    return ChatResponse(
        answer=answer,
        sources=sources,
        session_id=session_id
    )


@app.get("/api/categories")
async def get_categories():
    """获取所有分类"""
    db = await get_db()
    rows = await db.fetch(
        "SELECT category, COUNT(*) as count FROM documents GROUP BY category ORDER BY count DESC"
    )
    return {"categories": [dict(row) for row in rows]}


@app.get("/api/stats")
async def get_stats():
    """系统统计"""
    db = await get_db()
    
    # 并行执行多个查询
    doc_count, category_stats, chat_count = await asyncio.gather(
        db.fetchval("SELECT COUNT(*) FROM documents"),
        db.fetch("SELECT category, COUNT(*) as count FROM documents GROUP BY category"),
        db.fetchval("SELECT COUNT(*) FROM chat_history")
    )
    
    return {
        "document_count": doc_count,
        "category_stats": [dict(row) for row in category_stats],
        "chat_count": chat_count,
        "request_stats": request_stats
    }


if __name__ == "__main__":
    import uvicorn
    import asyncio
    asyncio.run(uvicorn.run(app, host="0.0.0.0", port=8000))
