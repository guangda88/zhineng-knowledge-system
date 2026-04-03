# ADR-0002: 嵌入模型选型 — BGE-M3 统一方案

**状态**: 已接受
**日期**: 2026-04-03
**替代**: LINGZHI_SYSTEM_PRINCIPLES 中 bge-small-zh-v1.5 的引用

## 背景

项目中存在两种嵌入模型的使用：

| 组件 | 模型 | 维度 | 说明 |
|------|------|------|------|
| `backend/services/retrieval/vector.py` | BAAI/bge-small-zh-v1.5 | 512 | 后端直接加载 SentenceTransformer |
| `backend/services/embeddings/embedding_service.py` | BAAI/bge-m3 | 1024→512 | Docker 微服务，批量生成 |

此外：
- LINGZHI_SYSTEM_PRINCIPLES 文档引用 `bge-small-zh-v1.5`
- COMPREHENSIVE_DEVELOPMENT_PLAN_V2 里程碑3 引用 `BGE-M3`
- 数据库中所有 embedding 列统一为 `vector(512)`
- guji_documents 嵌入生成使用 BGE-M3 微服务

### 模型对比

| 维度 | bge-small-zh-v1.5 | BGE-M3 |
|------|-------------------|--------|
| 参数量 | 33M | 568M |
| 语言 | 中文 | 多语言（含中文） |
| 维度 | 512 | 1024（可降至512） |
| 检索质量（中文） | 良好 | 优秀 |
| 推理速度 | 快（33M参数） | 慢（568M参数） |
| 内存占用 | ~130MB | ~2.1GB |
| 跨领域表现 | 通用中文 | 中文古籍/专业领域更强 |

## 决策

**采用 BGE-M3 作为统一嵌入模型**，分两阶段迁移：

### 阶段一（当前 — 2026年4月）
- Docker 微服务保持 BGE-M3，用于批量嵌入生成（guji_documents、documents 等）
- 后端 `vector.py` 仍使用 bge-small-zh-v1.5 进行在线查询嵌入
- **混合模式**：查询时用 bge-small 生成向量，存储用 BGE-M3 生成

### 阶段二（2026年5月 — 里程碑3完成后）
- `vector.py` 改为调用 BGE-M3 微服务 HTTP API
- 移除后端直接加载的 SentenceTransformer 实例
- 统一查询和存储为同一模型

## 理由

1. **检索准确性优先**：BGE-M3 在中文古籍和专业领域表现显著优于 bge-small
2. **内存效率**：微服务模式（独立容器）比后端内嵌模型节省 API 进程内存
3. **渐进迁移**：阶段一允许两个模型并行运行，避免大爆炸式迁移风险
4. **成本控制**：BGE-M3 仅用于离线批量生成和 API 调用，不阻塞后端启动

## 后果

### 正面
- 嵌入质量统一提升
- 文档冲突解决（PRINCIPLES 引用需更新）
- 为9域知识库提供更好的跨域检索

### 风险与缓解
- **维度不匹配风险**：阶段一查询(bge-small)与存储(BGE-M3)使用不同模型
  - 缓解：两个模型都输出512维向量，余弦相似度仍可计算，但语义空间不同
  - 影响：查询精度可能低于统一模型
  - 期限：阶段二必须在5月完成
- **微服务可用性**：BGE-M3 微服务单点故障
  - 缓解：阶段二加入重试和降级机制

### 需更新文档
- [ ] LINGZHI_SYSTEM_PRINCIPLES — 更新模型引用为 BGE-M3
- [ ] ENGINEERING_ALIGNMENT.md — TD-1 标记为已解决
- [ ] AGENTS.md — 更新嵌入说明
