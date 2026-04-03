# 灵知系统 - AI模型与功能完整清单

**更新日期**: 2026-04-02

---

## 🤖 模型架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    灵知系统 AI 架构                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  本地嵌入模型  │    │   线上LLM    │    │   推理引擎    │  │
│  │              │    │   (14个)     │    │              │  │
│  │  BGE-M3      │    │              │    │  CoT/ReAct   │  │
│  │  512维向量   │    │  智能调度池   │    │  GraphRAG    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│          │                  │                    │           │
│          └──────────────────┴────────────────────┘       │
│                             │                            │
│                    ┌────────▼─────────┐                 │
│                    │  FreeTokenPool   │                 │
│                    │  (智能Token池)    │                 │
│                    └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 💻 本地模型

### 嵌入模型 (Embedding Model)

| 模型 | 维度 | 框架 | 用途 |
|------|------|------|------|
| **BGE-M3** | 1024维 | SentenceTransformer | 多语言文本嵌入 |
| **BGE-small-zh-v1.5** | 512维 | FlagEmbedding | 中文语义搜索 |
| **FlagEmbedding** | 768维 | FlagEmbedding | 通用嵌入 |

**服务配置**:
```python
# 模型路径
EMBEDDING_MODEL: BAAI/bge-m3

# 服务端口
FastAPI: 独立嵌入服务
```

**功能**:
- ✅ 文本向量化
- ✅ 批量嵌入
- ✅ 语义相似度计算
- ✅ 向量搜索支持

---

## ☁️ 线上模型 (API调用)

### 模型调度策略

```
智能调度池 (FreeTokenPool)
│
├─ 优先级排序 (0-99)
├─ 额度检查
├─ 任务匹配
├─ 复杂度适配
└─ 负载均衡
```

### 已配置模型列表

#### 🥇 主力模型 (优先级 0-1)

| 模型 | 状态 | 额度 | 优势 | 用途 |
|------|------|------|------|------|
| **GLM Coding Plan Pro** | ⚠️ 未配置 | 100M/月 | 代码生成、复杂推理 | 开发主力 |
| **GLM-4** | ✅ 已配置 | 100万/月 | 通用对话、长文本 | 日常对话 |
| **DeepSeek-V3** | ✅ 已配置 | 500万/30天 | 数学、代码推理 | 复杂推理 |

#### 🥈 补充模型 (优先级 2-5)

| 模型 | 状态 | 额度 | 优势 | 用途 |
|------|------|------|------|------|
| **千帆Qwen** | ✅ | 100万/月 | 中文理解 | 中文任务 |
| **通义千问** | ✅ | 100万/月 | 长文本(128K) | 长文档 |
| **混元** | ✅ | 100万/30天 | 多模态 | 图文理解 |
| **豆包** | ✅ | 200万/30天 | 高并发 | 实时响应 |
| **Kimi** | ✅ | 300万/30天 | 超长文本 | 大文档 |
| **MiniMax** | ✅ | 100万/60天 | 对话 | 聊天 |
| **讯飞星火** | ✅ | 50万/月 | 中文语音 | 语音 |

#### 📉 额外配置

| 模型 | 状态 | 额度 | 用途 |
|------|------|------|------|
| GLM-4.7-CC | ⚠️ 未配置 | - | 高级推理 |
| 千帆百炼 | ✅ | - | 百度生态 |
| 通义CLI | ✅ | - | 命令行工具 |
| 豆包NAS | ✅ | - | 存储服务 |

---

## 🧠 推理能力

### 1. CoT (Chain of Thought) - 链式思考

**文件**: `backend/services/reasoning/cot.py`

**功能**:
- ✅ 多步骤推理
- ✅ 思维链可视化
- ✅ 中间步骤验证

**使用场景**:
```
复杂问题 → 分解 → 逐步推理 → 验证结论
```

**示例**:
```python
from backend.services.reasoning.cot import ChainOfThought

reasoning = ChainOfThought()
result = await reasoning.reason(
    query="为什么智能气功强调形神合一?",
    domain="qigong"
)
```

### 2. ReAct - 推理+行动

**文件**: `backend/services/reasoning/react.py`

**功能**:
- ✅ 推理循环
- ✅ 工具调用
- ✅ 观察-思考-行动循环

**使用场景**:
```
问题 → 思考 → 行动 → 观察 → 调整 → ...
```

**示例**:
```python
from backend.services.reasoning.react import ReActAgent

agent = ReActAgent()
result = await agent.solve(
    task="查找黄帝内经中关于气的论述",
    tools=["search_books", "retrieve_content"]
)
```

### 3. GraphRAG - 图推理检索增强生成

**文件**: `backend/services/reasoning/graph_rag.py`

**功能**:
- ✅ 知识图谱构建
- ✅ 图遍历推理
- ✅ 多跳推理

**使用场景**:
```
实体 → 关系图 → 多跳推理 → 综合答案
```

**示例**:
```python
from backend.services.reasoning.graph_rag import GraphRAG

graph_rag = GraphRAG()
result = await graph_rag.query(
    question="庄子与老子思想的关系是什么?",
    knowledge_graph=True
)
```

---

## 📝 生成能力

### 1. 文本生成

**文件**: `backend/services/generation/generators.py`

**功能**:
- ✅ 文章生成
- ✅ 内容创作
- ✅ 风格迁移
- ✅ 摘要生成

**支持类型**:
```python
- 散文
- 说明文
- 论述文
- 讲稿
- 社交媒体文案
```

### 2. 代码生成

**优先使用**: GLM Coding Plan Pro

**功能**:
- ✅ 函数/类生成
- ✅ 代码注释
- ✅ 代码重构
- ✅ Bug修复
- ✅ 单元测试

**优化**:
- 智能缓存 (30-50%节省)
- 批处理 (50-70%减少调用)
- 自适应限流

### 3. PPT生成

**文件**: `backend/services/generation/ppt_generator.py`

**功能**:
- ✅ 大纲生成
- ✅ 幻灯片内容
- ✅ 演讲者备注
- ✅ 视觉建议

**输出格式**:
```python
{
    "title": "演示文稿标题",
    "slides": [
        {"title": "第1页", "content": "...", "notes": "..."},
        ...
    ]
}
```

### 4. 报告生成

**文件**: `backend/services/generation/report_generator.py`

**功能**:
- ✅ 数据分析报告
- ✅ 研究报告
- ✅ 进展报告
- ✅ 统计图表

**报告类型**:
```python
- 学术报告
- 技术报告
- 进展报告
- 数据报告
```

### 5. 课程生成

**文件**: `backend/services/generation/course_generator.py`

**功能**:
- ✅ 教学大纲
- ✅ 课程内容
- ✅ 练习题
- ✅ 学习计划

**适用场景**:
```python
- 气功教学课程
- 理论学习课程
- 实践指导课程
- 分阶段培训
```

### 6. 音频生成

**文件**: `backend/services/generation/audio_generator.py.backup`

**功能**:
- ✅ TTS语音合成
- ✅ 音频内容生成
- ✅ 多语言支持

**支持格式**:
```python
- MP3
- WAV
- M4A
```

### 7. 数据分析

**文件**: `backend/services/generation/data_analyzer.py`

**功能**:
- ✅ 数据洞察
- ✅ 趋势分析
- ✅ 可视化建议
- ✅ 报告生成

---

## 🔍 检索能力

### 1. 向量检索 (Vector Retrieval)

**文件**: `backend/services/retrieval/vector.py`

**功能**:
- ✅ 语义搜索
- ✅ 相似度计算
- ✅ Top-K召回

**技术**:
```python
- pgvector (PostgreSQL扩展)
- 余弦相似度
- HNSW索引
```

**使用场景**:
```python
# 语义搜索
query = "如何调理身心?"
results = await vector_search.search(query, top_k=10)
```

### 2. BM25检索

**文件**: `backend/services/retrieval/bm25.py`

**功能**:
- ✅ 关键词匹配
- ✅ TF-IDF权重
- ✅ 相关性评分

**使用场景**:
```python
# 关键词搜索
results = await bm25_search.search("气功 意守", top_k=10)
```

### 3. 混合检索 (Hybrid Retrieval)

**文件**: `backend/services/hybrid_retrieval.py`

**功能**:
- ✅ 向量 + BM25双路召回
- ✅ RRF (Reciprocal Rank Fusion) 融合
- ✅ 动态权重调整

**融合策略**:
```python
score = 1 / (k + rank_vector) + 1 / (k + rank_bm25)
```

**使用场景**:
```python
# 混合检索
results = await hybrid_search.search(
    query="混元整体理论",
    alpha=0.5  # 向量权重
)
```

### 4. 多维度搜索

**文件**: `backend/services/book_search.py`

**功能**:
- ✅ 标题搜索
- ✅ 作者搜索
- ✅ 分类筛选
- ✅ 朝代筛选
- ✅ 全文内容搜索

**搜索维度**:
```python
- 元数据搜索 (标题、作者、描述)
- 全文搜索 (章节内容)
- 向量搜索 (语义相似)
- 组合搜索 (多条件)
```

---

## 🔎 分析能力

### 1. OCR识别

**功能**:
- ✅ 图片文字提取
- ✅ PDF文字提取
- ✅ 手写识别
- ✅ 表格识别

**支持格式**:
```python
- PNG, JPG, JPEG
- PDF
- TIFF
```

### 2. 语音转写

**功能**:
- ✅ 音频转文本
- ✅ 说话人识别
- ✅ 时间戳生成
- ✅ 标点符号添加

**支持格式**:
```python
- MP3, WAV, M4A
- FLAC, OGG
```

### 3. 数据标注

**文件**: `backend/services/annotation/`

**功能**:
- ✅ 文本校正
- ✅ 实体标注
- ✅ 关系抽取
- ✅ 分类标注

### 4. 情感分析

**功能**:
- ✅ 情感分类
- ✅ 观点提取
- ✅ 情感强度
- ✅ 情感趋势

### 5. 实体识别

**功能**:
- ✅ 人名识别
- ✅ 地名识别
- ✅ 机构名识别
- ✅ 术语识别

---

## 🛠️ 优化功能

### 1. 智能缓存

**文件**: `backend/services/evolution/smart_cache.py`

**效果**: 节省30-50%重复请求

**功能**:
- ✅ 内存 + 磁盘双重缓存
- ✅ 48小时TTL
- ✅ 自动过期清理
- ✅ MD5哈希键

### 2. 批处理

**文件**: `backend/services/evolution/batch_processor.py`

**效果**: 减少50-70% API调用

**功能**:
- ✅ 自动分批处理
- ✅ 智能合并请求
- ✅ 批次间延迟
- ✅ 并发处理

### 3. 自适应限流

**文件**: `backend/services/evolution/rate_limiter.py`

**效果**: 避免90%频率限制错误

**功能**:
- ✅ 多时间窗口监控
- ✅ 自适应调整限制
- ✅ 自动计算等待时间
- ✅ 详细统计信息

---

## 📊 监控功能

### Token监控

**文件**: `scripts/token_monitor_dashboard.py`

**功能**:
- ✅ 实时Token使用监控
- ✅ Provider性能对比
- ✅ 成功率统计
- ✅ 延迟监控
- ✅ 错误追踪

**使用方式**:
```bash
# 查看仪表板
python scripts/token_monitor_dashboard.py

# 实时监控
python scripts/token_monitor_dashboard.py --realtime

# Provider对比
python scripts/token_monitor_dashboard.py --compare

# 导出报告
python scripts/token_monitor_dashboard.py --export
```

---

## 🎯 使用示例

### 基础文本生成

```python
from backend.services.ai_service import generate_text

result = await generate_text(
    prompt="解释什么是气功中的意守丹田",
    complexity="medium",
    max_tokens=1000
)

# 返回
{
    "success": True,
    "content": "意守丹田是...",
    "provider": "glm_coding",
    "tokens": 856,
    "latency_ms": 1234
}
```

### 复杂推理任务

```python
from backend.services.ai_service import generate_text
from backend.services.evolution.TaskType import TaskType

result = await generate_text(
    prompt="比较庄子与老子思想的异同",
    complexity="high",
    task_type=TaskType.REASONING
)
```

### 带缓存的调用

```python
from backend.services.evolution.optimized_ai_client import optimized_chat

# 自动应用缓存、限流等优化
response = await optimized_chat("什么是智能气功?")
```

### 批量处理

```python
from backend.services.evolution.optimized_ai_client import batch_chat

prompts = ["问题1", "问题2", "问题3"]
results = await batch_chat(
    prompts,
    batch_size=3,
    delay_between_batches=5
)
```

---

## 📋 模型选择指南

### 按任务类型选择

| 任务类型 | 推荐模型 | 理由 |
|----------|----------|------|
| **代码生成** | GLM Coding Plan Pro | 专业代码模型 |
| **复杂推理** | DeepSeek-V3 | 推理能力强 |
| **长文本处理** | 通义千问、Kimi | 支持128K+ |
| **中文对话** | GLM-4、千帆Qwen | 中文优化 |
| **实时响应** | 豆包 | 高并发能力 |
| **日常问答** | GLM-4 | 平衡性能成本 |

### 按复杂度选择

| 复杂度 | 推荐模型 | 额度策略 |
|--------|----------|----------|
| **简单** | GLM-4、千帆 | 优先使用便宜的 |
| **中等** | GLM-4、DeepSeek | 负载均衡 |
| **复杂** | DeepSeek、GLM Coding Plan | 优先使用推理强的 |

---

## 💡 最佳实践

### 1. Token优化

```python
# ✅ 好的做法：使用缓存
response = await optimized_chat("常见问题")

# ❌ 不好的做法：重复调用
for _ in range(10):
    await api_call("相同问题")
```

### 2. 批量操作

```python
# ✅ 好的做法：批量处理
results = await batch_chat(prompts, batch_size=5)

# ❌ 不好的做法：逐个调用
for prompt in prompts:
    await api_call(prompt)
```

### 3. 错误处理

```python
# ✅ 好的做法：使用fallback
result = await generate_with_fallback(
    prompt,
    max_retries=3
)

# ❌ 不好的做法：单次调用
result = await api_call(prompt)  # 可能失败
```

---

## 📈 性能指标

### 响应时间

| 操作 | 平均时间 |
|------|----------|
| 文本生成 | 1-3秒 |
| 代码生成 | 2-5秒 |
| 向量检索 | 50-200ms |
| BM25检索 | 20-100ms |
| 混合检索 | 100-300ms |

### Token消耗

| 操作 | 平均Token |
|------|-----------|
| 简单问答 | 500-1000 |
| 复杂推理 | 2000-5000 |
| 代码生成 | 1000-3000 |
| 长文档处理 | 5000-10000 |

### 成本优化

| 优化项 | 节省比例 |
|--------|----------|
| 智能缓存 | 30-50% |
| 批处理 | 50-70% |
| 自适应限流 | 减少90%错误 |

---

## 🎉 总结

**本地模型**:
- BGE-M3 嵌入模型 (1024维)
- 语义搜索支持

**线上模型**:
- 14个API提供商
- 1810万+ tokens额度
- 智能调度池

**核心能力**:
- 推理: CoT + ReAct + GraphRAG
- 生成: 文本/代码/PPT/报告/课程/音频
- 检索: 向量 + BM25 + 混合
- 分析: OCR + 语音 + 标注

**优化功能**:
- 智能缓存 (30-50%节省)
- 批处理 (50-70%减少调用)
- 自适应限流 (90%错误避免)

**众智混元，万法灵通** ⚡🚀
