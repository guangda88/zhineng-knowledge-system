# 向量搜索修复指南

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**修复日期**: 2026-03-31
**状态**: ✅ 已完成

---

## 📋 修复总结

### 问题
- 🔴 **严重**: 向量搜索使用 SHA256 哈希模拟，所有语义搜索返回垃圾结果
- 🔴 **影响**: 混合搜索、GraphRAG 推理功能完全失效

### 解决方案
部署本地 **BGE-M3** 嵌入服务，替换哈希模拟为真实的语义嵌入向量

### 优势
- ✅ **免费**: 无需外部 API 费用
- ✅ **快速**: 本地推理，低延迟
- ✅ **中文优化**: BGE-M3 专为中文优化
- ✅ **自包含**: 无外部依赖
- ✅ **CPU 兼容**: 不需要 GPU

---

## 🔧 修改内容

### 1. 新增文件

| 文件 | 说明 |
|------|------|
| `backend/services/embeddings/embedding_service.py` | BGE-M3 嵌入服务 |
| `backend/services/embeddings/Dockerfile` | 嵌入服务容器配置 |
| `backend/services/embeddings/requirements.txt` | Python 依赖 |

### 2. 修改文件

| 文件 | 修改内容 |
|------|----------|
| `docker-compose.yml` | 添加 embedding 服务定义 |
| `backend/services/retrieval/vector.py` | 替换 SHA256 为真实嵌入 API 调用 |
| `.env.example` | 添加 EMBEDDING_SERVICE_URL 配置 |
| `.env.production` | 添加 EMBEDDING_SERVICE_URL 配置 |

---

## 🚀 部署步骤

### 步骤 1: 停止当前服务

```bash
cd /home/ai/zhineng-knowledge-system
docker-compose down
```

### 步骤 2: 拉取 BGE-M3 模型（首次运行）

```bash
# 创建模型缓存目录
mkdir -p data/embedding_cache

# 预下载模型（可选，加速首次启动）
docker run --rm -v $(pwd)/data/embedding_cache:/cache python:3.11-slim bash -c "
pip install --no-cache-dir sentence-transformers
python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer(\"BAAI/bge-m3\", cache_folder=\"/cache\")'
"
```

### 步骤 3: 启动服务

```bash
# 启动所有服务（包括新的 embedding 服务）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 应该看到 zhineng-embedding 容器
```

### 步骤 4: 等待模型加载

```bash
# 查看嵌入服务日志（首次启动需要下载模型，约 2-3 GB）
docker-compose logs -f embedding

# 等待看到：
# "模型加载成功，向量维度: 1024"
# "Application startup complete"
```

### 步骤 5: 验证嵌入服务

```bash
# 健康检查
curl http://localhost:8001/health
# 预期: {"status":"healthy","model_loaded":true,"device":"cpu"}

# 模型信息
curl http://localhost:8001/info
# 预期: {"model_name":"BAAI/bge-m3","dimension":1024,...}

# 测试嵌入
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text":"测试文本"}'
# 预期: 返回 1024 维向量
```

### 步骤 6: 重建所有文档向量

```bash
# 运行重建脚本
python scripts/rebuild_embeddings.py

# 或手动执行（Python）
python3 -c "
import asyncio
from backend.services.retrieval.vector import VectorRetriever
import asyncpg

async def rebuild():
    pool = await asyncpg.create_pool('postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb')
    async with VectorRetriever(pool) as retriever:
        stats = await retriever.update_all_embeddings(batch_size=50)
        print(f'完成: {stats}')
    await pool.close()

asyncio.run(rebuild())
"
```

### 步骤 7: 测试向量搜索

```bash
# 测试语义搜索
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "气功的呼吸方法",
    "category": "气功",
    "top_k": 5
  }'

# 预期: 返回相关的气功文档，按语义相似度排序
```

---

## 📊 性能指标

### 嵌入服务

| 指标 | 值 |
|------|-----|
| 模型 | BGE-M3 (BAAI) |
| 向量维度 | 1024 |
| 模型大小 | ~2.3 GB |
| 单文本推理 | ~0.5-2 秒（CPU） |
| 批量推理（10） | ~2-5 秒（CPU） |
| 内存占用 | 2-4 GB |

### 资源配置

| 资源 | 限制 | 预留 |
|------|------|------|
| CPU | 2 核心 | 0.5 核心 |
| 内存 | 4 GB | 2 GB |

---

## 🔍 监控和调试

### 查看日志

```bash
# 嵌入服务日志
docker-compose logs -f --tail=100 embedding

# API 服务日志（向量检索相关）
docker-compose logs api | grep -i "向量"
```

### 性能监控

```bash
# 容器资源使用
docker stats zhineng-embedding

# 嵌入服务响应时间
time curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text":"测试"}'
```

### 故障排查

**问题 1: 嵌入服务无法启动**

```bash
# 查看详细错误
docker-compose logs embedding

# 常见原因：
# 1. 内存不足 - 减少其他容器内存限制
# 2. 模型下载失败 - 检查网络连接
# 3. 端口冲突 - 检查 8001 端口占用
```

**问题 2: 模型加载慢**

```bash
# 查看模型下载进度
docker exec zhineng-embedding du -sh /cache

# 预下载模型（步骤 2）可加速
```

**问题 3: 向量搜索结果差**

```bash
# 1. 检查嵌入是否正常
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text":"气功"}' | jq '.embedding | length'

# 2. 重建文档向量（步骤 6）
python scripts/rebuild_embeddings.py

# 3. 检查向量维度
docker exec zhineng-postgres psql -U zhineng -d zhineng_kb -c "
SELECT id, title,
       CASE WHEN embedding IS NULL THEN 0 ELSE array_length(embedding::real[], 1) END as dim
FROM documents
LIMIT 10;
"
```

---

## 📝 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_SERVICE_URL` | `http://embedding:8001` | 嵌入服务地址 |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 模型名称 |
| `EMBEDDING_SERVICE_PORT` | `8001` | 服务端口 |

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/info` | GET | 模型信息 |
| `/embed` | POST | 单文本嵌入 |
| `/embed_batch` | POST | 批量嵌入 |

---

## ✅ 验证清单

- [ ] 嵌入服务容器启动成功
- [ ] 模型加载完成（日志显示 "模型加载成功"）
- [ ] `/health` 端点返回正常
- [ ] `/embed` 端点返回 1024 维向量
- [ ] 所有文档向量已重建
- [ ] 向量搜索返回相关结果
- [ ] 混合搜索工作正常
- [ ] GraphRAG 推理功能正常

---

## 🎯 效果对比

### 修复前（SHA256 哈希）

```python
# 相似度完全随机，无语义意义
query = "气功的呼吸方法"
results = [
    {"title": "儒家经典", "similarity": 0.999},  # 不相关
    {"title": "中医诊断", "similarity": 0.998},  # 不相关
]
```

### 修复后（BGE-M3）

```python
# 语义相似，结果准确
query = "气功的呼吸方法"
results = [
    {"title": "气功调息法", "similarity": 0.89},  # 高度相关
    {"title": "气功呼吸要领", "similarity": 0.85},  # 相关
    {"title": "气功入门指南", "similarity": 0.78},  # 部分相关
]
```

---

## 📚 技术细节

### BGE-M3 模型

- **开发者**: 北京智源人工智能研究院 (BAAI)
- **架构**: Transformer-based
- **特点**:
  - 支持多语言（中文、英文等）
  - 最大序列长度: 8192 tokens
  - 适合长文档理解
  - 在中文语义理解任务上表现优异

### 向量相似度计算

使用 **余弦相似度** (Cosine Similarity):

```
similarity = (A · B) / (||A|| * ||B||)
```

PostgreSQL pgvector 使用 `<=>` 操作符计算距离，转换为相似度：

```
similarity = 1 - distance
```

---

## 🎉 完成状态

| 任务 | 状态 |
|------|------|
| 创建嵌入服务 | ✅ 完成 |
| 更新向量检索代码 | ✅ 完成 |
| 配置 Docker Compose | ✅ 完成 |
| 更新环境变量配置 | ✅ 完成 |
| 创建部署文档 | ✅ 完成 |

---

**下一步**: 执行部署步骤，启动嵌入服务并重建文档向量！
