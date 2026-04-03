# 文字处理工程流API文档

**文字处理工程流（团队A）API完整文档**

---

## 📋 目录

1. [概述](#概述)
2. [文本处理API](#文本处理api)
3. [向量嵌入API](#向量嵌入api)
4. [检索API](#检索api)
5. [RAG问答API](#rag问答api)
6. [文本标注API](#文本标注api)
7. [错误处理](#错误处理)
8. [使用示例](#使用示例)

---

## 概述

文字处理工程流提供了一套完整的文本处理、向量检索和问答生成API。

### 核心功能

- ✅ 文本解析和分块
- ✅ 向量嵌入生成
- ✅ 语义检索
- ✅ RAG问答
- ✅ 文本标注

### 技术栈

- FastAPI (Web框架)
- PostgreSQL (数据库)
- pgvector (向量数据库)
- sentence-transformers (本地嵌入模型)
- CLIProxyAI (远程AI服务)

---

## 文本处理API

### 1. 文本分块

**端点**: `POST /api/v1/text/chunk`

**描述**: 将文本智能分块，保持语义完整性

**请求体**:
```json
{
  "text": "混元灵通是智能气功的核心理论...",
  "max_chunk_size": 300,
  "min_chunk_size": 100,
  "overlap": 50
}
```

**响应**:
```json
{
  "chunks": [
    {
      "id": "chunk_000001",
      "content": "混元灵通是智能气功的核心理论",
      "metadata": {
        "title": "智能气功基础",
        "tags": ["气功", "理论"]
      },
      "char_count": 20,
      "word_count": 12
    }
  ],
  "statistics": {
    "total_chunks": 5,
    "total_chars": 1500,
    "avg_chunk_size": 300
  }
}
```

### 2. 文件处理

**端点**: `POST /api/v1/text/process-file`

**描述**: 处理上传的文本文件

**请求**: `multipart/form-data`
- `file`: 文本文件
- `format`: 文件格式（txt/md/html）

**响应**:
```json
{
  "chunks": [...],
  "metadata": {
    "title": "智能气功基础教程",
    "author": "庞明",
    "chapters": ["第一章", "第二章"],
    "encoding": "utf-8"
  }
}
```

---

## 向量嵌入API

### 1. 生成嵌入

**端点**: `POST /api/v1/embeddings`

**描述**: 生成文本的向量嵌入

**请求体**:
```json
{
  "text": "混元灵通是智能气功的核心理论",
  "provider": "local"
}
```

**响应**:
```json
{
  "vector": [0.1, 0.2, 0.3, ...],
  "dimension": 512,
  "provider": "local",
  "quality_score": 0.95,
  "processing_time": 0.15
}
```

### 2. 批量嵌入

**端点**: `POST /api/v1/embeddings/batch`

**描述**: 批量生成向量嵌入

**请求体**:
```json
{
  "texts": [
    "混元灵通是智能气功的核心理论",
    "组场是智能气功的练习方法"
  ],
  "batch_size": 32,
  "provider": "local"
}
```

**响应**:
```json
{
  "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]],
  "count": 2,
  "total_time": 0.25,
  "avg_quality": 0.93
}
```

---

## 检索API

### 1. 混合检索

**端点**: `POST /api/v1/search`

**描述**: 使用混合检索（向量+全文）搜索文档

**请求体**:
```json
{
  "query": "什么是混元灵通？",
  "method": "hybrid",
  "top_k": 10,
  "threshold": 0.5,
  "category": "theory"
}
```

**响应**:
```json
{
  "results": [
    {
      "id": 1,
      "title": "混元灵通理论",
      "content": "混元灵通是智能气功的核心理论...",
      "score": 0.92,
      "method": "hybrid",
      "rank": 1
    }
  ],
  "total_time": 0.5,
  "vector_count": 5,
  "fulltext_count": 5,
  "fusion_method": "rrf"
}
```

### 2. 向量检索

**端点**: `POST /api/v1/search/vector`

**描述**: 纯向量检索

**请求体**:
```json
{
  "query": "混元灵通",
  "top_k": 10
}
```

### 3. 全文检索

**端点**: `POST /api/v1/search/fulltext`

**描述**: 纯全文检索

**请求体**:
```json
{
  "query": "混元灵通",
  "top_k": 10
}
```

---

## RAG问答API

### 1. 单轮问答

**端点**: `POST /api/v1/rag/query`

**描述**: RAG增强的单轮问答

**请求体**:
```json
{
  "question": "什么是混元灵通？",
  "retrieval_method": "hybrid",
  "top_k": 5,
  "max_context_length": 2000
}
```

**响应**:
```json
{
  "answer": "混元灵通是智能气功的核心理论，强调通过意念来统一身心...",
  "quality": "high",
  "confidence": 0.9,
  "citations": [
    {
      "source_id": 1,
      "title": "混元灵通理论",
      "content_snippet": "混元灵通是智能气功的核心理论",
      "relevance_score": 0.92
    }
  ],
  "processing_time": 1.5
}
```

### 2. 多轮对话

**端点**: `POST /api/v1/rag/chat`

**描述**: 支持上下文的多轮对话

**请求体**:
```json
{
  "conversation_id": "conv_123",
  "message": "它有什么特点？"
}
```

**响应**:
```json
{
  "answer": "...",
  "conversation_id": "conv_123",
  "turn": 2,
  "context_summary": [...]
}
```

### 3. 清空对话历史

**端点**: `DELETE /api/v1/rag/history/{conversation_id}`

**描述**: 清空指定对话的历史记录

**响应**:
```json
{
  "success": true,
  "message": "对话历史已清空"
}
```

---

## 文本标注API

### 1. 创建标注

**端点**: `POST /api/v1/annotations`

**描述**: 创建文本标注

**请求体**:
```json
{
  "text_block_id": 1,
  "annotation_type": "keyword",
  "content": "混元灵通",
  "start_pos": 0,
  "end_pos": 4,
  "importance": "high",
  "confidence": 0.95,
  "metadata": {
    "source": "manual"
  }
}
```

**响应**:
```json
{
  "id": 1,
  "text_block_id": 1,
  "annotation_type": "keyword",
  "content": "混元灵通",
  "importance": "high",
  "confidence": 0.95,
  "created_at": "2026-04-01T10:00:00Z",
  "version": 1
}
```

### 2. 列出标注

**端点**: `GET /api/v1/annotations`

**查询参数**:
- `text_block_id`: 文本块ID
- `annotation_type`: 标注类型
- `importance`: 重要性
- `limit`: 返回数量（默认100）
- `offset`: 偏移量

**响应**:
```json
{
  "annotations": [...],
  "total": 50,
  "limit": 100,
  "offset": 0
}
```

### 3. 更新标注

**端点**: `PUT /api/v1/annotations/{annotation_id}`

**请求体**:
```json
{
  "content": "混元灵通（核心理论）",
  "importance": "critical"
}
```

**响应**:
```json
{
  "id": 1,
  "content": "混元灵通（核心理论）",
  "importance": "critical",
  "version": 2,
  "updated_at": "2026-04-01T10:05:00Z"
}
```

### 4. 删除标注

**端点**: `DELETE /api/v1/annotations/{annotation_id}`

**响应**:
```json
{
  "success": true,
  "message": "标注已删除"
}
```

### 5. 导出标注

**端点**: `POST /api/v1/annotations/export`

**请求体**:
```json
{
  "format": "json",
  "filters": {
    "text_block_id": 1,
    "annotation_type": "keyword"
  }
}
```

**响应**:
```json
{
  "export_id": 1,
  "status": "completed",
  "download_url": "/api/v1/exports/1"
}
```

### 6. 标注统计

**端点**: `GET /api/v1/annotations/statistics`

**响应**:
```json
{
  "total_annotations": 150,
  "type_distribution": {
    "keyword": 50,
    "topic": 30,
    "entity": 40,
    "sentiment": 30
  },
  "importance_distribution": {
    "high": 20,
    "medium": 80,
    "low": 50
  },
  "average_confidence": 0.85
}
```

### 7. 添加评论

**端点**: `POST /api/v1/annotations/{annotation_id}/comments`

**请求体**:
```json
{
  "content": "这个标注很准确",
  "author": "user1"
}
```

**响应**:
```json
{
  "id": 1,
  "annotation_id": 1,
  "content": "这个标注很准确",
  "author": "user1",
  "created_at": "2026-04-01T10:10:00Z"
}
```

---

## 错误处理

### 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "输入文本不能为空",
    "details": {
      "field": "text",
      "reason": "required"
    }
  },
  "request_id": "req_123456"
}
```

### 常见错误码

| 错误码 | HTTP状态 | 描述 |
|--------|---------|------|
| `VALIDATION_ERROR` | 400 | 请求参数验证失败 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `UNAUTHORIZED` | 401 | 未授权 |
| `RATE_LIMIT_EXCEEDED` | 429 | 超过速率限制 |
| `INTERNAL_ERROR` | 500 | 内部服务器错误 |

---

## 使用示例

### Python示例

```python
import requests

# API基础URL
BASE_URL = "http://localhost:8001/api/v1"

# 1. 文本分块
response = requests.post(
    f"{BASE_URL}/text/chunk",
    json={
        "text": "混元灵通是智能气功的核心理论...",
        "max_chunk_size": 300
    }
)
chunks = response.json()["chunks"]

# 2. 生成嵌入
response = requests.post(
    f"{BASE_URL}/embeddings",
    json={
        "text": "混元灵通是智能气功的核心理论"
    }
)
vector = response.json()["vector"]

# 3. 检索
response = requests.post(
    f"{BASE_URL}/search",
    json={
        "query": "什么是混元灵通？",
        "method": "hybrid",
        "top_k": 5
    }
)
results = response.json()["results"]

# 4. RAG问答
response = requests.post(
    f"{BASE_URL}/rag/query",
    json={
        "question": "什么是混元灵通？"
    }
)
answer = response.json()["answer"]

# 5. 创建标注
response = requests.post(
    f"{BASE_URL}/annotations",
    json={
        "text_block_id": 1,
        "annotation_type": "keyword",
        "content": "混元灵通",
        "importance": "high"
    }
)
annotation = response.json()
```

### JavaScript示例

```javascript
const BASE_URL = 'http://localhost:8001/api/v1';

// 文本分块
async function chunkText(text) {
  const response = await fetch(`${BASE_URL}/text/chunk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, max_chunk_size: 300 })
  });
  return response.json();
}

// RAG问答
async function askQuestion(question) {
  const response = await fetch(`${BASE_URL}/rag/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question })
  });
  return response.json();
}

// 使用示例
const chunks = await chunkText('混元灵通是智能气功的核心理论...');
const answer = await askQuestion('什么是混元灵通？');
console.log(answer.answer);
```

---

## 性能指标

### 推荐配置

| 操作 | 推荐参数 | 预期性能 |
|------|---------|---------|
| 文本分块 | max_chunk_size=300 | <1秒/1000字 |
| 向量嵌入 | batch_size=32 | <5秒/100个 |
| 混合检索 | top_k=10 | <1秒 |
| RAG问答 | top_k=5 | <3秒 |

### 优化建议

1. **批量处理**: 使用批量API提高吞吐量
2. **缓存启用**: 启用检索缓存减少重复计算
3. **提供商选择**: 短文本使用远程API，长文本使用本地模型

---

## 附录

### A. 标注类型列表

| 类型 | 值 | 描述 |
|------|-----|------|
| 关键词 | `keyword` | 重要关键词 |
| 主题 | `topic` | 内容主题 |
| 重要性 | `importance` | 重要性标注 |
| 情感 | `sentiment` | 情感倾向 |
| 实体 | `entity` | 命名实体 |
| 自定义 | `custom` | 自定义类型 |

### B. 重要性级别

| 级别 | 值 | 描述 |
|------|-----|------|
| 低 | `low` | 低重要性 |
| 中 | `medium` | 中等重要性 |
| 高 | `high` | 高重要性 |
| 关键 | `critical` | 关键内容 |

---

**文档版本**: v1.0.0

**最后更新**: 2026-04-01

**众智混元，万法灵通** ⚡🚀
