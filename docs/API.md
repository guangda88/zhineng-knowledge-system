# 智能知识系统 API 文档

版本: 1.0.0
基础路径: `http://localhost:8001`

---

## 目录

- [概述](#概述)
- [认证](#认证)
- [基础接口](#基础接口)
- [文档管理](#文档管理)
- [检索服务](#检索服务)
- [问答服务](#问答服务)
- [推理服务](#推理服务)
- [知识图谱](#知识图谱)
- [领域系统](#领域系统)
- [监控与健康](#监控与健康)
- [错误码](#错误码)

---

## 概述

智能知识系统提供基于 RAG（检索增强生成）的智能问答服务，支持气功、中医、儒家三个领域的知识检索和推理。

### 技术栈

- **框架**: FastAPI 0.115.0
- **数据库**: PostgreSQL 16 + pgvector
- **缓存**: Redis 7
- **向量检索**: pgvector + BGE嵌入
- **关键词检索**: BM25

### 响应格式

所有API响应使用JSON格式：

```json
{
  "status": "success",
  "data": {},
  "message": "操作成功"
}
```

---

## 认证

当前版本API无需认证（开发模式）。

> 生产环境建议启用 JWT 或 OAuth2 认证。

---

## 基础接口

### 系统信息

```http
GET /
```

**响应示例**:

```json
{
  "status": "ok",
  "message": "智能知识系统运行中",
  "categories": ["气功", "中医", "儒家"],
  "version": "1.0.0",
  "stats": {
    "total": 1234,
    "errors": 5
  }
}
```

### 健康检查

```http
GET /health
```

**响应示例**:

```json
{
  "status": "ok",
  "database": "ok",
  "timestamp": "2026-03-25T10:30:00"
}
```

---

## 文档管理

### 获取文档列表

```http
GET /api/v1/documents
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| category | string | 否 | 分类筛选: `气功`, `中医`, `儒家` |
| limit | integer | 否 | 返回数量 (1-100), 默认10 |
| offset | integer | 否 | 偏移量, 默认0 |

**请求示例**:

```bash
curl "http://localhost:8001/api/v1/documents?category=气功&limit=20"
```

**响应示例**:

```json
{
  "total": 45,
  "documents": [
    {
      "id": 1,
      "title": "气功基础入门",
      "category": "气功",
      "tags": ["入门", "基础"],
      "created_at": "2026-03-20T10:00:00"
    }
  ]
}
```

### 获取单个文档

```http
GET /api/v1/documents/{doc_id}
```

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| doc_id | integer | 是 | 文档ID |

**响应示例**:

```json
{
  "id": 1,
  "title": "气功基础入门",
  "content": "气功是中国传统养生方法...",
  "category": "气功",
  "tags": ["入门", "基础"],
  "created_at": "2026-03-20T10:00:00"
}
```

### 创建文档

```http
POST /api/v1/documents
Content-Type: application/json
```

**请求体**:

```json
{
  "title": "八段锦第二式",
  "content": "左右开弓似射雕：左脚向左迈出...",
  "category": "气功",
  "tags": ["八段锦", "功法"]
}
```

**字段验证**:

| 字段 | 验证规则 |
|------|----------|
| title | 1-500字符 |
| content | 最少1字符 |
| category | 必须为: `气功`, `中医`, `儒家` |
| tags | 最多10个标签 |

**响应示例** (201):

```json
{
  "id": 123,
  "message": "文档创建成功"
}
```

---

## 检索服务

### 关键词搜索

```http
GET /api/v1/search
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | 是 | 搜索关键词 (1-200字符) |
| category | string | 否 | 分类筛选 |
| limit | integer | 否 | 返回数量 (1-100), 默认10 |

**请求示例**:

```bash
curl "http://localhost:8001/api/v1/search?q=八段锦&category=气功&limit=5"
```

**响应示例**:

```json
{
  "query": "八段锦",
  "total": 8,
  "results": [
    {
      "id": 2,
      "title": "八段锦第一式",
      "content": "双手托天理三焦...",
      "category": "气功"
    }
  ]
}
```

### 混合检索

```http
POST /api/v1/search/hybrid
Content-Type: application/json
```

**请求体**:

```json
{
  "query": "八段锦的功效是什么",
  "category": "气功",
  "top_k": 10,
  "use_vector": true,
  "use_bm25": true
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| query | string | 搜索查询 (1-200字符) |
| category | string | 可选分类筛选 |
| top_k | integer | 返回数量 (1-50), 默认10 |
| use_vector | boolean | 是否使用向量检索, 默认true |
| use_bm25 | boolean | 是否使用BM25检索, 默认true |

**响应示例**:

```json
{
  "query": "八段锦的功效是什么",
  "total": 10,
  "results": [
    {
      "id": 5,
      "title": "八段锦的功效",
      "content": "八段锦具有调理脾胃、...",
      "category": "气功",
      "score": 0.89,
      "retrieval_method": "hybrid"
    }
  ]
}
```

### 更新文档嵌入

```http
POST /api/v1/embeddings/update
Content-Type: application/json
```

**请求体 (指定文档)**:

```json
{
  "doc_ids": [1, 2, 3],
  "all_docs": false
}
```

**请求体 (全部文档)**:

```json
{
  "all_docs": true
}
```

**响应示例**:

```json
{
  "status": "success",
  "message": "已更新 3 个文档的嵌入向量",
  "updated": 3
}
```

### 检索服务状态

```http
GET /api/v1/retrieval/status
```

**响应示例**:

```json
{
  "vector_enabled": true,
  "bm25_enabled": true,
  "hybrid_enabled": true,
  "documents_with_vector": 120,
  "total_documents": 150,
  "embedding_coverage": 80.0
}
```

---

## 问答服务

### 智能问答

```http
POST /api/v1/ask
Content-Type: application/json
```

**请求体**:

```json
{
  "question": "八段锦的第一式是什么？",
  "category": "气功",
  "session_id": "20260325103000"
}
```

**字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 用户问题 (1-1000字符) |
| category | string | 否 | 指定分类 |
| session_id | string | 否 | 会话ID, 用于多轮对话 |

**响应示例**:

```json
{
  "answer": "根据知识库找到 3 条相关内容：\n\n1. **八段锦第一式**\n双手托天理三焦：十字交叉手向上托起...",
  "sources": [
    {
      "id": 2,
      "title": "八段锦第一式",
      "content": "双手托天理三焦：..."
    }
  ],
  "session_id": "20260325103000"
}
```

### 获取分类统计

```http
GET /api/v1/categories
```

**响应示例**:

```json
{
  "categories": [
    {"category": "气功", "count": 45},
    {"category": "中医", "count": 38},
    {"category": "儒家", "count": 27}
  ]
}
```

### 系统统计

```http
GET /api/v1/stats
```

**响应示例**:

```json
{
  "document_count": 110,
  "category_stats": [
    {"category": "气功", "count": 45},
    {"category": "中医", "count": 38},
    {"category": "儒家", "count": 27}
  ],
  "request_stats": {
    "total": 1234,
    "errors": 5
  }
}
```

---

## 推理服务

### 推理问答

```http
POST /api/v1/reason
Content-Type: application/json
```

**请求体**:

```json
{
  "question": "八段锦和太极拳有什么区别？",
  "mode": "auto",
  "category": "气功",
  "session_id": "session_123",
  "use_rag": true
}
```

**字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 用户问题 (1-500字符) |
| mode | string | 否 | 推理模式: `cot`, `react`, `graph_rag`, `auto` |
| category | string | 否 | 指定分类 |
| session_id | string | 否 | 会话ID |
| use_rag | boolean | 否 | 是否使用RAG检索, 默认true |

**推理模式说明**:

- **cot**: 链式推理 (Chain of Thought), 适合需要逻辑推理的问题
- **react**: ReAct模式, 适合需要多步骤执行的问题
- **graph_rag**: 图谱推理, 适合涉及实体关系的问题
- **auto**: 自动选择最适合的推理模式

**响应示例**:

```json
{
  "question": "八段锦和太极拳有什么区别？",
  "mode": "graph_rag",
  "session_id": "session_123",
  "answer": "八段锦和太极拳在起源、动作特点、练习目的等方面有以下区别...",
  "reasoning_steps": [
    "步骤1: 识别问题中的两个关键实体 - 八段锦、太极拳",
    "步骤2: 查询知识图谱获取两者关系",
    "步骤3: 结合检索到的文档内容生成对比分析"
  ],
  "sources": [
    {
      "id": 10,
      "title": "八段锦概述",
      "relevance": 0.92
    },
    {
      "id": 25,
      "title": "太极拳入门",
      "relevance": 0.88
    }
  ]
}
```

---

## 知识图谱

### 查询实体关系

```http
POST /api/v1/graph/query
Content-Type: application/json
```

**请求体**:

```json
{
  "entity1": "八段锦",
  "entity2": "气功",
  "max_depth": 3
}
```

**字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| entity1 | string | 是 | 起始实体 |
| entity2 | string | 是 | 目标实体 |
| max_depth | integer | 否 | 最大搜索深度 (1-5), 默认3 |

**响应示例**:

```json
{
  "entity1": "八段锦",
  "entity2": "气功",
  "found": true,
  "path": ["八段锦", "气功功法", "气功"],
  "path_details": [
    {
      "from": "八段锦",
      "relation": "属于",
      "to": "气功功法"
    },
    {
      "from": "气功功法",
      "relation": "属于",
      "to": "气功"
    }
  ]
}
```

### 获取图谱数据

```http
GET /api/v1/graph/data
```

**响应示例** (用于前端可视化):

```json
{
  "nodes": [
    {
      "id": "八段锦",
      "label": "八段锦",
      "type": "功法",
      "category": "气功"
    },
    {
      "id": "气功",
      "label": "气功",
      "type": "category",
      "category": "气功"
    }
  ],
  "links": [
    {
      "source": "八段锦",
      "target": "气功",
      "label": "属于",
      "type": "hierarchy"
    }
  ]
}
```

### 构建知识图谱

```http
POST /api/v1/graph/build?category=气功
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| category | string | 否 | 指定分类, 不指定则使用所有文档 |

**响应示例**:

```json
{
  "status": "success",
  "message": "知识图谱构建完成",
  "entity_count": 156,
  "relation_count": 203,
  "document_count": 50
}
```

### 推理服务状态

```http
GET /api/v1/reasoning/status
```

**响应示例**:

```json
{
  "cot_enabled": true,
  "react_enabled": true,
  "graph_rag_enabled": true,
  "graph_entity_count": 156,
  "graph_relation_count": 203,
  "api_configured": true
}
```

---

## 领域系统

### 获取领域列表

```http
GET /api/v1/domains
```

**响应示例**:

```json
{
  "domains": [
    {
      "name": "qigong",
      "type": "specialized",
      "enabled": true,
      "priority": 1
    },
    {
      "name": "tcm",
      "type": "specialized",
      "enabled": true,
      "priority": 2
    },
    {
      "name": "confucian",
      "type": "specialized",
      "enabled": true,
      "priority": 3
    },
    {
      "name": "general",
      "type": "fallback",
      "enabled": true,
      "priority": 99
    }
  ],
  "total": 4,
  "enabled": 4
}
```

### 获取领域统计

```http
GET /api/v1/domains/{domain_name}/stats
```

**响应示例**:

```json
{
  "name": "qigong",
  "type": "specialized",
  "enabled": true,
  "priority": 1,
  "stats": {
    "document_count": 45,
    "query_count": 234,
    "avg_response_time": 0.156,
    "cache_hit_rate": 0.78
  },
  "health": "healthy"
}
```

### 领域直接查询

```http
POST /api/v1/domains/{domain_name}/query
Content-Type: application/json
```

**请求体** (使用表单数据):

```
question=八段锦怎么练习
```

**响应示例**:

```json
{
  "answer": "八段锦的练习方法如下...",
  "sources": [],
  "confidence": 0.89,
  "domain": "qigong",
  "metadata": {}
}
```

### 网关统一查询

```http
POST /api/v1/gateway/query
Content-Type: application/json
```

**请求体 (单领域)**:

```json
{
  "question": "八段锦的第一式是什么",
  "session_id": "session_456",
  "multi_domain": false
}
```

**请求体 (多领域)**:

```json
{
  "question": "中医和儒家在养生观念上的异同",
  "session_id": "session_789",
  "multi_domain": true
}
```

**响应示例 (单领域)**:

```json
{
  "question": "八段锦的第一式是什么",
  "domain": "qigong",
  "strategy": "keyword_match",
  "result": {
    "answer": "八段锦第一式是双手托天理三焦...",
    "sources": [],
    "confidence": 0.92,
    "domain": "qigong",
    "metadata": {}
  },
  "session_id": "session_456"
}
```

**响应示例 (多领域)**:

```json
{
  "question": "中医和儒家在养生观念上的异同",
  "domain": "multi",
  "results": [
    {
      "answer": "从中医角度来看...",
      "sources": [],
      "confidence": 0.85,
      "domain": "tcm",
      "metadata": {}
    },
    {
      "answer": "儒家养生强调...",
      "sources": [],
      "confidence": 0.82,
      "domain": "confucian",
      "metadata": {}
    }
  ],
  "session_id": "session_789"
}
```

### 网关统计

```http
GET /api/v1/gateway/stats
```

**响应示例**:

```json
{
  "total_queries": 1234,
  "queries_by_domain": {
    "qigong": 567,
    "tcm": 345,
    "confucian": 234,
    "general": 88
  },
  "avg_response_time": 0.234,
  "rate_limit_exceeded": 12
}
```

---

## 监控与健康

### 获取系统指标

```http
GET /api/v1/metrics
```

**响应示例**:

```json
{
  "metrics": {
    "app_startup": 1,
    "gateway_query_total": 1234,
    "gateway_query_success": 1220,
    "gateway_query_error": 14,
    "gateway_rate_limited": 12
  },
  "gateway": {
    "total_queries": 1234,
    "queries_by_domain": {
      "qigong": 567,
      "tcm": 345,
      "confucian": 234,
      "general": 88
    }
  },
  "timestamp": "2026-03-25T10:30:00"
}
```

### Prometheus指标

```http
GET /api/v1/metrics/prometheus
```

**响应类型**: `text/plain`

**响应示例**:

```
# HELP app_startup Application startup count
# TYPE app_startup counter
app_startup_total{version="1.0.0"} 1

# HELP gateway_query_total Total gateway queries
# TYPE gateway_query_total counter
gateway_query_total{domain="qigong"} 567
gateway_query_total{domain="tcm"} 345

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1"} 1234
http_request_duration_seconds_bucket{le="0.5"} 1500
```

### 系统健康检查

```http
GET /api/v1/health
GET /api/v1/health?detailed=true
```

**响应示例 (简略)**:

```json
{
  "status": "healthy",
  "timestamp": "2026-03-25T10:30:00"
}
```

**响应示例 (详细)**:

```json
{
  "status": "healthy",
  "timestamp": "2026-03-25T10:30:00",
  "domains": {
    "total_domains": 4,
    "enabled_domains": 4,
    "domains": [
      {
        "name": "qigong",
        "status": "healthy"
      },
      {
        "name": "tcm",
        "status": "healthy"
      }
    ]
  },
  "checks": [
    {
      "name": "database",
      "status": "healthy",
      "message": "Connection OK"
    }
  ]
}
```

### 特定健康检查详情

```http
GET /api/v1/health/{check_name}
```

**可用的检查名称**: `database`, `redis`, `api`

**响应示例**:

```json
{
  "name": "database",
  "status": "healthy",
  "message": "Connection OK",
  "timestamp": "2026-03-25T10:30:00",
  "details": {
    "pool_size": 10,
    "active_connections": 3
  }
}
```

---

## 错误码

| HTTP状态码 | 错误类型 | 说明 |
|-----------|---------|------|
| 200 | - | 请求成功 |
| 201 | - | 资源创建成功 |
| 400 | ValidationError | 请求参数验证失败 |
| 404 | NotFound | 资源不存在 |
| 429 | RateLimitExceeded | 超过速率限制 |
| 500 | InternalError | 服务器内部错误 |

**错误响应格式**:

```json
{
  "detail": "错误描述信息"
}
```

**错误示例** (速率限制):

```json
{
  "error": "rate_limit_exceeded",
  "retry_after": 60
}
```

---

## 交互式文档

访问以下地址获取交互式API文档:

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

---

## 示例代码

### Python

```python
import httpx

BASE_URL = "http://localhost:8001"

# 智能问答
async def ask_question(question: str, category: str = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/ask",
            json={
                "question": question,
                "category": category
            }
        )
        return response.json()

# 混合检索
async def hybrid_search(query: str, category: str = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/search/hybrid",
            json={
                "query": query,
                "category": category,
                "top_k": 10
            }
        )
        return response.json()

# 推理问答
async def reason(question: str, mode: str = "auto"):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/reason",
            json={
                "question": question,
                "mode": mode
            }
        )
        return response.json()
```

### JavaScript

```javascript
const BASE_URL = 'http://localhost:8001';

// 智能问答
async function askQuestion(question, category = null) {
  const response = await fetch(`${BASE_URL}/api/v1/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      category
    })
  });
  return await response.json();
}

// 混合检索
async function hybridSearch(query, category = null) {
  const response = await fetch(`${BASE_URL}/api/v1/search/hybrid`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      category,
      top_k: 10
    })
  });
  return await response.json();
}

// 推理问答
async function reason(question, mode = 'auto') {
  const response = await fetch(`${BASE_URL}/api/v1/reason`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      mode
    })
  });
  return await response.json();
}
```

### cURL

```bash
# 智能问答
curl -X POST "http://localhost:8001/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "八段锦的第一式是什么？",
    "category": "气功"
  }'

# 混合检索
curl -X POST "http://localhost:8001/api/v1/search/hybrid" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "八段锦的功效",
    "category": "气功"
  }'

# 推理问答
curl -X POST "http://localhost:8001/api/v1/reason" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "八段锦和太极拳有什么区别？",
    "mode": "graph_rag"
  }'
```

---

## 更新日志

### v1.0.0 (2026-03-25)
- 初始版本发布
- 支持文档管理、检索、问答、推理服务
- 知识图谱功能
- 领域系统和网关路由
- 监控和健康检查
