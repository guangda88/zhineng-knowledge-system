"""智能知识系统 MCP Server — 47个工具封装

封装智能知识系统的核心 API 为 MCP 工具，供灵族成员通过 MCP 协议调用。
使用 FastMCP 框架，代理至 FastAPI 后端。

P0 工具(11):
  1. knowledge_search  — 知识检索（混合 BM25+向量）
  2. ask_question      — 智能问答
  3. domain_query      — 领域路由查询
  4. optimization_status — 自优化状态
  4b. analyze_optimization — 分析优化机会
  4c. execute_optimization — 触发优化执行
  4d. optimization_dashboard — 优化仪表盘
  4e. trigger_audit / audit_history — 系统审计
  4f. error_analysis / log_error — 错误分析与记录
  5. submit_feedback   — 反馈提交
  6. generate_training_data — 训练数据生成
  7. safe_db_query     — 安全数据库查询

P1 扩展(19 + 10 新增):
  藏书检索: book_search, book_fulltext, book_detail, book_related
  国学经典: guoxue_search, guoxue_cross_book, guoxue_classics
  书目系统: sysbook_search, sysbook_domains
  推理图谱: reason, graph_query, kg_entities, kg_subgraph
  知识缺口: knowledge_gaps, gap_stats
  灵信线程: thread_list, thread_summary
  管道情报: pipeline_stats, intelligence_dashboard
  文档管理: document_create, document_get, document_list, embedding_update
  多模型对比: evolution_compare, evolution_dashboard
  音频转录: audio_transcribe
  标注系统: annotation_stats, ocr_pending_tasks
  内容提取: content_extract
"""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zhineng-mcp")

BASE_URL = os.getenv("ZHINENG_API_URL", "http://localhost:8000")
DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)
TRAINING_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prepare_training_data.py"

READONLY_TABLES = {
    "documents",
    "guji_documents",
    "textbook_knowledge",
    "lingmessage_threads",
    "lingmessage_messages",
    "lingmessage_agents",
}

mcp = FastMCP("zhineng-knowledge")


# ---------------------------------------------------------------------------
# Tool 1: 知识检索
# ---------------------------------------------------------------------------


@mcp.tool()
async def knowledge_search(
    query: str,
    category: Optional[str] = None,
    top_k: int = 10,
    use_hybrid: bool = True,
) -> dict:
    """检索知识库。默认使用混合检索（BM25 + 向量），可通过 use_hybrid=False 切换纯关键词。

    Args:
        query: 搜索关键词或自然语言查询
        category: 限定分类（中医/儒家/气功/古籍/教材等），为空则全库搜索
        top_k: 返回结果数量
        use_hybrid: True 使用混合检索，False 使用纯关键词检索

    Returns:
        搜索结果列表，包含文档标题、内容摘要、相关性分数
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        if use_hybrid:
            payload: Dict[str, Any] = {"query": query, "top_k": top_k}
            if category:
                payload["category"] = category
            resp = await client.post("/api/v1/search/hybrid", json=payload)
        else:
            params: Dict[str, Any] = {"q": query, "limit": top_k}
            if category:
                params["category"] = category
            resp = await client.get("/api/v1/search", params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 2: 智能问答
# ---------------------------------------------------------------------------


@mcp.tool()
async def ask_question(
    question: str,
    category: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """向知识系统提问，返回 AI 生成的答案及引用来源。

    Args:
        question: 自然语言问题
        category: 限定知识分类
        session_id: 会话 ID，用于多轮对话上下文

    Returns:
        包含 answer、sources、confidence 的回答
    """
    payload: Dict[str, Any] = {"question": question}
    if category:
        payload["category"] = category
    if session_id:
        payload["session_id"] = session_id

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        resp = await client.post("/api/v1/ask", json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 3: 领域路由查询
# ---------------------------------------------------------------------------


@mcp.tool()
async def domain_query(
    domain: str,
    question: str,
) -> dict:
    """查询特定知识领域。系统自动路由至对应领域处理器。

    可用领域: 气功, 中医, 儒家, 佛家, 道家, 武术, 哲学, 科学, 心理学

    Args:
        domain: 领域名称
        question: 查询内容

    Returns:
        领域专属检索结果
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/domains/{domain}/query",
            json={"question": question},
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 4: 自优化状态
# ---------------------------------------------------------------------------


@mcp.tool()
async def optimization_status() -> dict:
    """获取自优化系统当前状态：优化机会列表、系统指标、反馈分析。

    Returns:
        opportunities: 当前优化机会列表
        stats: 系统统计
        feedback_analysis: 反馈分析摘要
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        results = {}
        try:
            opp_resp = await client.get("/optimization/opportunities")
            opp_resp.raise_for_status()
            results["opportunities"] = opp_resp.json()
        except Exception as e:
            results["opportunities_error"] = str(e)

        try:
            stats_resp = await client.get("/optimization/stats")
            stats_resp.raise_for_status()
            results["stats"] = stats_resp.json()
        except Exception as e:
            results["stats_error"] = str(e)

        try:
            fb_resp = await client.get("/optimization/feedback/analysis")
            fb_resp.raise_for_status()
            results["feedback_analysis"] = fb_resp.json()
        except Exception as e:
            results["feedback_analysis_error"] = str(e)

        return results


# ---------------------------------------------------------------------------
# Tool 4b: 分析优化机会
# ---------------------------------------------------------------------------


@mcp.tool()
async def analyze_optimization(opportunity_id: str) -> dict:
    """深入分析优化机会，制定详细执行计划。

    Args:
        opportunity_id: 优化机会ID（从 optimization_status 获取）

    Returns:
        机会详情 + 优化计划
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post(f"/optimization/opportunities/{opportunity_id}/analyze")
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 4c: 执行优化
# ---------------------------------------------------------------------------


@mcp.tool()
async def execute_optimization(
    opportunity_id: str,
    auto_approve: bool = False,
) -> dict:
    """触发优化执行。优化在后台运行，非关键优化可自动批准。

    Args:
        opportunity_id: 优化机会ID
        auto_approve: 是否跳过人工确认（关键优化需人工确认）

    Returns:
        执行状态和 opportunity_id
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.post(
            f"/optimization/opportunities/{opportunity_id}/execute",
            json={"opportunity_id": opportunity_id, "auto_approve": auto_approve},
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 4d: 优化仪表盘
# ---------------------------------------------------------------------------


@mcp.tool()
async def optimization_dashboard() -> dict:
    """获取自优化仪表盘：机会分布、活跃优化、近期完成。

    Returns:
        by_priority, by_category, by_status, recent_optimizations, active_count
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.get("/optimization/dashboard")
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 4e: 系统审计
# ---------------------------------------------------------------------------


@mcp.tool()
async def trigger_audit(
    audit_type: str = "comprehensive",
) -> dict:
    """触发系统审计。审计在后台运行。

    Args:
        audit_type: 审计类型 (comprehensive/security/performance/code_quality)

    Returns:
        审计启动确认
    """
    valid_types = {"comprehensive", "security", "performance", "code_quality"}
    if audit_type not in valid_types:
        return {"error": f"Invalid audit_type. Must be one of {valid_types}"}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.post("/optimization/audit/perform", params={"audit_type": audit_type})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def audit_history(limit: int = 10) -> dict:
    """查询审计历史记录。

    Args:
        limit: 返回最近N条记录

    Returns:
        审计记录列表
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/optimization/audit/history", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 4f: 错误分析
# ---------------------------------------------------------------------------


@mcp.tool()
async def error_analysis() -> dict:
    """获取系统错误分析：错误频率、模式、趋势。

    Returns:
        错误统计分析
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/optimization/errors/analysis")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def log_error(
    error_type: str,
    error_message: str,
    stack_trace: str,
    severity: str = "error",
    context: Optional[Dict[str, Any]] = None,
) -> dict:
    """记录系统错误至自优化引擎，用于模式分析和自动优化。

    Args:
        error_type: 错误类型
        error_message: 错误消息
        stack_trace: 堆栈跟踪
        severity: 严重程度 (error/warning/critical)
        context: 上下文信息（可选）

    Returns:
        确认信息含 error_id
    """
    if severity not in ("error", "warning", "critical"):
        return {"error": "severity must be one of: error, warning, critical"}

    payload: Dict[str, Any] = {
        "error_type": error_type,
        "error_message": error_message,
        "stack_trace": stack_trace,
        "severity": severity,
    }
    if context is not None:
        payload["context"] = context

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.post("/optimization/errors/log", json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 5: 反馈提交
# ---------------------------------------------------------------------------


@mcp.tool()
async def submit_feedback(
    user_id: str,
    feedback_type: str,
    content: str,
    rating: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> dict:
    """提交用户反馈至自优化引擎。支持 bug/feature/improvement/complaint 四种类型。

    Args:
        user_id: 提交者标识（如 lingminopt, lingzhi, lingyi）
        feedback_type: 反馈类型 (bug/feature/improvement/complaint)
        content: 反馈内容
        rating: 评分 1-5（可选）
        metadata: 附加元数据（可选）

    Returns:
        提交确认信息
    """
    if feedback_type not in ("bug", "feature", "improvement", "complaint"):
        return {"error": f"Invalid feedback_type: {feedback_type}"}
    if rating is not None and not (1 <= rating <= 5):
        return {"error": "Rating must be 1-5"}

    payload: Dict[str, Any] = {
        "user_id": user_id,
        "feedback_type": feedback_type,
        "content": content,
    }
    if rating is not None:
        payload["rating"] = rating
    if metadata is not None:
        payload["metadata"] = metadata

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.post("/optimization/feedback", json=payload)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool 6: 训练数据生成
# ---------------------------------------------------------------------------


@mcp.tool()
async def generate_training_data(
    data_type: str = "all",
    output_dir: str = "data/training",
) -> dict:
    """运行微调数据准备流水线，生成训练数据集。

    可选数据类型:
      - intent_classifier: 意图分类数据集
      - embedding_pairs: 嵌入微调样本对
      - qa_benchmark: RAG 问答评估基准
      - all: 全部（默认）

    Args:
        data_type: 要生成的数据类型
        output_dir: 输出目录

    Returns:
        生成结果统计
    """
    import sys

    valid_types = {"intent_classifier", "embedding_pairs", "qa_benchmark", "all"}
    if data_type not in valid_types:
        return {"error": f"Invalid data_type: {data_type}. Must be one of {valid_types}"}

    script_path = str(TRAINING_SCRIPT)
    if not Path(script_path).exists():
        return {"error": f"Training script not found: {script_path}"}

    env = os.environ.copy()
    env["TRAINING_DATA_DIR"] = output_dir

    cmd = [sys.executable, script_path]
    if data_type != "all":
        cmd.append(data_type)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()

    result: Dict[str, Any] = {
        "returncode": proc.returncode,
        "data_type": data_type,
        "output_dir": output_dir,
    }
    if proc.returncode == 0:
        try:
            report_path = Path(output_dir) / "data_quality_report.json"
            if report_path.exists():
                import json

                with open(report_path) as f:
                    result["report"] = json.load(f)
        except Exception:
            pass
    else:
        result["error"] = stderr.decode()[-2000:] if stderr else "Unknown error"
        result["stdout"] = stdout.decode()[-1000:] if stdout else ""

    return result


# ---------------------------------------------------------------------------
# Tool 7: 安全数据库查询
# ---------------------------------------------------------------------------

_SELECT_ONLY_RE = re.compile(r"^\s*SELECT\s", re.IGNORECASE)


@mcp.tool()
async def safe_db_query(
    query: str,
    params: Optional[List[Any]] = None,
    table_hint: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """执行只读参数化数据库查询。仅允许 SELECT 语句，且仅限白名单表。

    白名单表: documents, guji_documents, textbook_knowledge,
              lingmessage_threads, lingmessage_messages, lingmessage_agents

    Args:
        query: SQL SELECT 语句（可使用 $1, $2... 占位符）
        params: 查询参数列表
        table_hint: 显式声明查询的表名（用于安全校验）
        limit: 最大返回行数（默认 100，最大 1000）

    Returns:
        rows: 查询结果行列表
        count: 返回行数
    """
    if not _SELECT_ONLY_RE.match(query):
        return {"error": "Only SELECT queries are allowed"}

    limit = min(max(limit, 1), 1000)

    q_lower = query.lower()
    allowed_found = False
    for table in READONLY_TABLES:
        if table in q_lower:
            allowed_found = True
            break
    if not allowed_found:
        return {"error": f"Query must reference one of: {sorted(READONLY_TABLES)}"}

    if not query.rstrip().rstrip(";").lower().endswith(f"limit {limit}"):
        if ";" in query.rstrip()[:-1]:
            return {"error": "Multi-statement queries not allowed"}
        query = query.rstrip().rstrip(";")
        query += f" LIMIT {limit}"

    try:
        conn = await asyncpg.connect(DB_URL)
        try:
            if params:
                rows = await conn.fetch(query, *params)
            else:
                rows = await conn.fetch(query)
            return {
                "rows": [dict(r) for r in rows],
                "count": len(rows),
            }
        finally:
            await conn.close()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tool 5b: 检索反馈（持久化）
# ---------------------------------------------------------------------------


@mcp.tool()
async def submit_search_feedback(
    query: str,
    feedback_type: str,
    doc_id: Optional[int] = None,
    rating: Optional[int] = None,
    comment: Optional[str] = None,
    search_method: Optional[str] = None,
) -> dict:
    """提交检索质量反馈。反馈持久化到数据库，用于优化检索质量。

    Args:
        query: 原始搜索查询
        feedback_type: 反馈类型 (helpful/not_helpful/wrong/irrelevant/partial)
        doc_id: 相关文档 ID
        rating: 评分 1-5
        comment: 文字评论
        search_method: 检索方式 (keyword/hybrid/vector)

    Returns:
        提交确认，包含反馈 ID
    """
    valid_types = {"helpful", "not_helpful", "wrong", "irrelevant", "partial"}
    if feedback_type not in valid_types:
        return {"error": f"Invalid feedback_type. Must be one of {valid_types}"}

    payload: Dict[str, Any] = {
        "query": query,
        "feedback_type": feedback_type,
    }
    if doc_id is not None:
        payload["doc_id"] = doc_id
    if rating is not None:
        payload["rating"] = rating
    if comment is not None:
        payload["comment"] = comment
    if search_method is not None:
        payload["search_method"] = search_method

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.post("/api/v1/feedback", json=payload)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def get_search_feedback(
    feedback_type: Optional[str] = None,
    doc_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """查询检索反馈列表。可按类型、文档ID、查询关键词过滤。

    Args:
        feedback_type: 过滤类型 (helpful/not_helpful/wrong/irrelevant/partial)
        doc_id: 过滤特定文档的反馈
        query: 过滤特定查询的反馈
        limit: 返回数量（最大200）

    Returns:
        反馈列表和统计信息
    """
    params: Dict[str, Any] = {"limit": min(limit, 200)}
    if feedback_type:
        params["feedback_type"] = feedback_type
    if doc_id is not None:
        params["doc_id"] = doc_id
    if query:
        params["query"] = query

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.get("/api/v1/feedback", params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# 辅助工具：获取分类列表 / 系统统计
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_categories() -> dict:
    """获取知识库所有分类列表。

    Returns:
        categories: 分类名称列表
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/categories")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def system_stats() -> dict:
    """获取知识系统统计信息：文档数量、分类分布等。

    Returns:
        系统级统计数据
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/stats")
        resp.raise_for_status()
        return resp.json()


# ── P1 扩展工具（19个） ──


@mcp.tool()
async def book_search(q: str, category: str = "", page: int = 1, size: int = 10) -> dict:
    """统一跨源搜书（灵典）— books+sys_books+guoxue_books。"""
    params = {"q": q, "page": page, "size": size}
    if category:
        params["category"] = category
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.get("/library/lingflow/unified", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def book_fulltext(q: str, book_id: str = "", page: int = 1, size: int = 10) -> dict:
    """书籍全文内容搜索（灵典全文）。"""
    params = {"q": q, "page": page, "size": size}
    if book_id:
        params["book_id"] = book_id
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.get("/library/lingflow/fulltext", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def book_detail(book_id: str) -> dict:
    """书籍详情+章节目录（灵典详情）。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get(f"/library/{book_id}")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def book_related(book_id: str, top_k: int = 5) -> dict:
    """向量相似书籍推荐（灵典荐）。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get(f"/library/{book_id}/related", params={"top_k": top_k})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def guoxue_search(q: str, mode: str = "fulltext", page: int = 1, size: int = 20) -> dict:
    """国学经典全文搜索（灵经）— 26万条，3种模式(fulltext/fuzzy/broad)。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.get(
            "/api/v1/guoxue/search", params={"q": q, "mode": mode, "page": page, "size": size}
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def guoxue_cross_book(q: str, top_k: int = 10, per_book: int = 3) -> dict:
    """跨典籍搜索（灵经跨）— 概念在不同经典中的论述。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.get(
            "/api/v1/guoxue/search/cross-book",
            params={"q": q, "top_k": top_k, "per_book": per_book},
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def guoxue_classics(page: int = 1, size: int = 50) -> dict:
    """国学典籍列表（灵经目）— 109部。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/guoxue/books", params={"page": page, "size": size})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def sysbook_search(q: str = "", domain: str = "", page: int = 1, size: int = 20) -> dict:
    """系统书目检索（灵目）— 302万条。"""
    params = {"page": page, "size": size}
    if q:
        params["q"] = q
    if domain:
        params["domain"] = domain
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.get("/api/v1/sysbooks/search", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def sysbook_domains() -> dict:
    """书目领域分类树（灵目域）。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/sysbooks/domains")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def reason(
    question: str, mode: str = "auto", category: str = "", use_rag: bool = True
) -> dict:
    """多模式推理问答（灵思）— CoT/ReAct/GraphRAG/auto。"""
    payload = {"question": question, "mode": mode, "use_rag": use_rag}
    if category:
        payload["category"] = category
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post("/api/v1/reason", json=payload)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def graph_query(entity1: str, entity2: str, max_depth: int = 3) -> dict:
    """知识图谱路径查询（灵图）— 两实体间关系。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.post(
            "/api/v1/graph/query",
            json={"entity1": entity1, "entity2": entity2, "max_depth": max_depth},
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def kg_entities(q: str = "", entity_type: str = "", limit: int = 20) -> dict:
    """知识图谱实体搜索（灵图实）。"""
    params = {"limit": limit}
    if q:
        params["q"] = q
    if entity_type:
        params["entity_type"] = entity_type
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/pipeline/kg/entities", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def kg_subgraph(entity_id: str, depth: int = 1) -> dict:
    """获取实体周围子图（灵图邻）— BFS扩展。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get(
            "/api/v1/pipeline/kg/graph", params={"entity_id": entity_id, "depth": depth}
        )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def knowledge_gaps(status: str = "", category: str = "", limit: int = 20) -> dict:
    """查询知识缺口列表（灵缺）— 灵知反射弧。"""
    params = {"limit": limit}
    if status:
        params["status"] = status
    if category:
        params["category"] = category
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/knowledge-gaps", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def gap_stats() -> dict:
    """知识缺口统计（灵缺统）。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/knowledge-gaps/stats")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def thread_list(status: str = "", limit: int = 20) -> dict:
    """灵信线程列表（灵信列）。"""
    params = {"limit": limit}
    if status:
        params["status"] = status
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/lingmessage/threads", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def thread_summary(thread_id: str) -> dict:
    """灵信线程摘要（灵信摘）— 消息+共识。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get(f"/api/v1/lingmessage/threads/{thread_id}/summary")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def pipeline_stats() -> dict:
    """管道总览（灵报）— 提取/标注/图谱/对账进度。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/pipeline/stats")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def intelligence_dashboard() -> dict:
    """情报仪表盘摘要（灵智）。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/intelligence/dashboard")
        resp.raise_for_status()
        return resp.json()


# ── P1 扩展工具（10个） ──


@mcp.tool()
async def document_create(
    title: str,
    content: str,
    category: str = "",
    tags: Optional[List[str]] = None,
) -> dict:
    """创建知识库文档（灵文创）。

    Args:
        title: 文档标题
        content: 文档内容
        category: 分类
        tags: 标签列表
    """
    payload: Dict[str, Any] = {"title": title, "content": content}
    if category:
        payload["category"] = category
    if tags:
        payload["tags"] = tags
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        resp = await client.post("/api/v1/documents", json=payload)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def document_get(doc_id: int) -> dict:
    """获取文档详情（灵文阅）。

    Args:
        doc_id: 文档ID
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get(f"/api/v1/documents/{doc_id}")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def document_list(category: str = "", page: int = 1, size: int = 20) -> dict:
    """列出知识库文档（灵文列）。

    Args:
        category: 按分类过滤
        page: 页码
        size: 每页数量
    """
    params: Dict[str, Any] = {"page": page, "size": size}
    if category:
        params["category"] = category
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/documents", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def embedding_update(doc_ids: Optional[List[int]] = None) -> dict:
    """更新文档嵌入向量（灵嵌）。不传doc_ids则更新全部。

    Args:
        doc_ids: 要更新的文档ID列表，空则全量更新
    """
    payload: Dict[str, Any] = {}
    if doc_ids:
        payload["doc_ids"] = doc_ids
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post("/api/v1/search/embeddings/update", json=payload)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def evolution_compare(
    question: str,
    models: Optional[List[str]] = None,
) -> dict:
    """多模型对比问答（灵比对）。触发后台对比任务。

    Args:
        question: 对比问题
        models: 模型列表（可选）
    """
    payload: Dict[str, Any] = {"question": question}
    if models:
        payload["models"] = models
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post("/api/v1/evolution/compare", json=payload)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def evolution_dashboard(period: str = "7d") -> dict:
    """进化仪表盘（灵进仪）— 用户行为、对比统计。

    Args:
        period: 统计周期 (7d/30d/90d)
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/api/v1/evolution/dashboard", params={"period": period})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def audio_transcribe(
    file_path: str,
    method: str = "local",
) -> dict:
    """音频转录（灵音）— 上传音频并启动转录。

    Args:
        file_path: 音频文件路径
        method: 转录方式 (local=本地Whisper, cloud=听悟)
    """
    try:
        import aiofiles as _aiofiles
    except ImportError:
        _aiofiles = None

    from pathlib import Path as _Path

    if _aiofiles:
        async with _aiofiles.open(file_path, "rb") as f:
            audio_data = await f.read()
    else:
        audio_data = _Path(file_path).read_bytes()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        upload_resp = await client.post(
            "/audio/upload",
            files={"file": (_Path(file_path).name, audio_data)},
        )
        upload_resp.raise_for_status()
        file_id = upload_resp.json().get("file_id") or upload_resp.json().get("id")

        if not file_id:
            return {
                "error": "Upload succeeded but no file_id returned",
                "upload": upload_resp.json(),
            }

        endpoint = (
            f"/audio/transcribe-local/{file_id}"
            if method == "local"
            else f"/audio/transcribe/{file_id}"
        )
        resp = await client.post(endpoint)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def annotation_stats() -> dict:
    """标注统计（灵注统）— OCR + 转录标注进度。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/annotation/stats")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def ocr_pending_tasks(limit: int = 10) -> dict:
    """待处理OCR任务（灵OCR待）。

    Args:
        limit: 返回数量
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.get("/annotation/ocr/tasks/pending", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def content_extract(
    source_type: str = "document",
    source_id: Optional[int] = None,
) -> dict:
    """触发内容提取管道（灵管提）。

    Args:
        source_type: 来源类型 (document/guji/textbook)
        source_id: 特定来源ID（可选，空则处理全部待处理）
    """
    payload: Dict[str, Any] = {"source_type": source_type}
    if source_id is not None:
        payload["source_id"] = source_id
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.post("/api/v1/pipeline/extract", json=payload)
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    mcp.run()
