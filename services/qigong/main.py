"""
气功知识服务 - Qigong Knowledge Service

提供气功领域的专业知识检索和问答
"""
from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any, Optional
import asyncio
from pydantic import BaseModel
import httpx

app = FastAPI(
    title="气功知识服务",
    description="Zhinqong (Qigong) Knowledge Domain Service",
    version="1.0.0"
)


# ==================== 数据模型 ====================

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    domain: str = "qigong"


class Document(BaseModel):
    id: str
    title: str
    content: str
    source: str
    category: str
    tags: List[str] = []


class QueryResponse(BaseModel):
    query: str
    documents: List[Document]
    total: int
    domain: str


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: List[str]
    confidence: float
    reasoning: Optional[str] = None


# ==================== 气功知识数据 ====================

# 气功知识库（示例数据，实际应从数据库/向量库加载）
QIGONG_KNOWLEDGE_BASE = [
    {
        "id": "qg001",
        "title": "气功的基本原理",
        "content": "气功是中国传统养生方法，通过调身、调息、调心相结合，达到强身健体、防病治病的目的。气功强调'气'的生命能量，通过呼吸调节和意念引导，使气血运行通畅，从而增强人体自愈能力。",
        "source": "中医基础理论",
        "category": "基础理论",
        "tags": ["原理", "基础", "养生"]
    },
    {
        "id": "qg002",
        "title": "八段锦功法",
        "content": "八段锦是传统气功功法，由八个动作组成：双手托天理三焦、左右开弓似射雕、调理脾胃须单举、五劳七伤往后瞧、摇头摆尾去心火、两手攀足固肾腰、攒拳怒目增气力、背后七颠百病消。每个动作都有特定的养生功效。",
        "source": "传统功法",
        "category": "功法练习",
        "tags": ["八段锦", "练习", "功法"]
    },
    {
        "id": "qg003",
        "title": "气功与高血压",
        "content": "研究表明，气功练习对高血压有辅助治疗作用。机制包括：1) 降低交感神经兴奋性；2) 改善血管弹性；3) 减轻精神压力。建议每日练习2-3次，每次20-30分钟，在专业指导下进行。",
        "source": "现代研究",
        "category": "养生保健",
        "tags": ["高血压", "健康", "研究"]
    },
    {
        "id": "qg004",
        "title": "太极拳与气功",
        "content": "太极拳结合了气功的导引术和武术的攻防技巧，通过缓慢、连贯的动作，配合深长呼吸，达到动静结合、刚柔并济的效果。太极拳被视为'流动的气功'，是气功与武术的完美结合。",
        "source": "太极理论",
        "category": "综合功法",
        "tags": ["太极拳", "综合", "武术"]
    },
    {
        "id": "qg005",
        "title": "气功呼吸法",
        "content": "气功呼吸主要有腹式呼吸和逆腹式呼吸两种。腹式呼吸：吸气时腹部隆起，呼气时腹部内收；逆腹式呼吸相反，吸气时腹部内收，呼气时腹部隆起。初学者应从自然呼吸开始，逐步过渡到腹式呼吸。",
        "source": "练习方法",
        "category": "练习技巧",
        "tags": ["呼吸", "方法", "入门"]
    }
]


# ==================== API 端点 ====================

@app.get("/", response_model=Dict[str, Any])
async def root():
    """服务根目录"""
    return {
        "service": "气功知识服务",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "search": "/api/v1/search - 搜索知识文档",
            "qa": "/api/v1/qa - 智能问答",
            "categories": "/api/v1/categories - 获取知识分类",
            "health": "/health - 健康检查"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "qigong-knowledge"}


@app.get("/api/v1/categories")
async def get_categories():
    """获取知识分类"""
    categories = {}
    for doc in QIGONG_KNOWLEDGE_BASE:
        cat = doc["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            "id": doc["id"],
            "title": doc["title"],
            "tags": doc["tags"]
        })
    return categories


@app.post("/api/v1/search", response_model=QueryResponse)
async def search_knowledge(request: QueryRequest):
    """搜索气功知识"""
    query = request.query.lower()

    # 简单的关键词匹配搜索
    results = []
    for doc in QIGONG_KNOWLEDGE_BASE:
        # 搜索标题、内容、标签
        if (query in doc["title"].lower() or
            query in doc["content"].lower() or
            any(query in tag.lower() for tag in doc["tags"])):
            results.append(Document(**doc))

    # 按相关性排序（简单实现）
    results.sort(key=lambda x: (
        query in x.title.lower(),
        sum(query in tag.lower() for tag in x.tags)
    ), reverse=True)

    return QueryResponse(
        query=request.query,
        documents=results[:request.top_k],
        total=len(results),
        domain="qigong"
    )


@app.post("/api/v1/qa", response_model=QAResponse)
async def question_answering(question: str, reasoning: bool = False):
    """气功知识智能问答"""
    # 1. 搜索相关知识
    query_lower = question.lower()
    relevant_docs = []

    for doc in QIGONG_KNOWLEDGE_BASE:
        if (query_lower in doc["title"].lower() or
            any(keyword in doc["content"].lower() for keyword in
               ["气功", "高血压", "练习", "呼吸", "八段锦", "太极拳"] if
               keyword in question.lower())):
            relevant_docs.append(doc)

    if not relevant_docs:
        # 知识库中找不到相关内容
        return QAResponse(
            question=question,
            answer="抱歉，知识库中没有找到相关内容。建议您提供更具体的问题，或咨询专业的气功老师。",
            sources=[],
            confidence=0.0,
            reasoning="未找到相关文档"
        )

    # 2. 基于检索结果生成答案（简化实现）
    best_doc = relevant_docs[0]
    answer = f"根据知识库，{best_doc['content']}"

    # 提取推理过程
    reasoning_steps = [
        f"识别到 {len(relevant_docs)} 篇相关文档",
        f"最相关文档: {best_doc['title']}",
        f"来源: {best_doc['source']}"
    ]

    return QAResponse(
        question=question,
        answer=answer,
        sources=[doc["id"] for doc in relevant_docs[:3]],
        confidence=min(0.9, 0.5 + len(relevant_docs) * 0.1),
        reasoning=" | ".join(reasoning_steps)
    )


@app.post("/api/v1/reasoning")
async def reasoning_query(question: str):
    """带推理的气功知识查询"""
    # 使用 ReAct 模式进行推理
    thought_process = []

    # Thought 1: 分析问题
    thought_process.append("分析问题: " + question)

    # Thought 2: 识别关键词
    keywords = [w for w in ["气功", "高血压", "练习", "方法", "原理"] if w in question]
    thought_process.append(f"识别关键词: {', '.join(keywords) if keywords else '通用知识查询'}")

    # Thought 3: 搜索知识
    relevant_docs = []
    for doc in QIGONG_KNOWLEDGE_BASE:
        if any(kw in doc["content"].lower() for kw in keywords + ["气功"]):
            relevant_docs.append(doc)
    thought_process.append(f"搜索结果: 找到 {len(relevant_docs)} 篇相关文档")

    # Thought 4: 综合回答
    if relevant_docs:
        best_doc = relevant_docs[0]
        answer = f"根据知识库分析：{best_doc['content']}"
        thought_process.append(f"生成答案: 基于 {best_doc['title']}")
    else:
        answer = "知识库中没有找到完全匹配的内容，建议提供更具体的问题。"
        thought_process.append("生成答案: 使用通用回复")

    return {
        "question": question,
        "thought_process": thought_process,
        "answer": answer,
        "sources": [doc["id"] for doc in relevant_docs[:3]]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
