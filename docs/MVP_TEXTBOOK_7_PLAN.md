# 教材7 MVP实施计划

**目标**: 基于教材7构建端到端MVP，验证核心价值

---

## 一、当前状态

✅ **已完成**:
- 教材7的5级TOC生成（953条目，超越XMind的234条目）
- 领域知识库建设（415个术语，12种模式）
- 基础设施就绪（Docker、PostgreSQL、FastAPI）

❌ **未完成**:
- TOC导入数据库
- 向量检索实现
- 智能问答实现
- Web UI构建

---

## 二、MVP功能范围

### 必须包含（P0）

1. **教材7知识库**
   - TOC结构化存储
   - 文本块与TOC关联
   - 向量嵌入生成

2. **智能检索**
   - 向量检索（pgvector + BGE）
   - 全文检索（GIN索引）
   - 混合检索（向量+BM25）

3. **智能问答**
   - RAG管道（检索+生成）
   - DeepSeek API集成
   - 基础推理模式

4. **Web UI**
   - 教材浏览（层级树状）
   - 搜索界面
   - 问答界面

### 暂不包含

- 用户认证/授权
- 其他8本教材
- 高级推理模式
- 性能优化

---

## 三、数据库设计

### 3.1 表结构

```sql
-- 教材节点表（参考Ima结构）
CREATE TABLE textbook_nodes (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    path VARCHAR(1024) NOT NULL,
    level INTEGER NOT NULL,
    parent_id VARCHAR(64),
    textbook_id VARCHAR(50) NOT NULL,
    line_range INT4RANGE,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_nodes_textbook ON textbook_nodes(textbook_id);
CREATE INDEX idx_nodes_parent ON textbook_nodes(parent_id);
CREATE INDEX idx_nodes_path ON textbook_nodes(path);
CREATE INDEX idx_nodes_level ON textbook_nodes(level);

-- 文本块表
CREATE TABLE textbook_blocks (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(64) REFERENCES textbook_nodes(id),
    content TEXT NOT NULL,
    block_order INTEGER NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_blocks_node ON textbook_blocks(node_id);
CREATE INDEX idx_blocks_vector ON textbook_blocks USING ivfflat (embedding vector_cosine_ops);

-- 全文搜索索引
CREATE INDEX idx_blocks_content_gin ON textbook_blocks USING gin(to_tsvector('chinese', content));

-- 向量搜索表（优化检索性能）
CREATE TABLE textbook_vectors (
    id SERIAL PRIMARY KEY,
    block_id INTEGER REFERENCES textbook_blocks(id),
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_vectors_embedding ON textbook_vectors USING ivfflat (embedding vector_cosine_ops);
```

### 3.2 初始数据

```sql
-- 插入教材7元数据
INSERT INTO textbooks (id, title, category, version) VALUES
('7', '智能气功科学·气功与人类文化', '智能气功', '2010版');
```

---

## 四、后端实现

### 4.1 数据导入服务

**文件**: `backend/services/textbook_importer.py`

```python
class TextbookImporter:
    """教材导入服务"""

    async def import_toc(self, textbook_id: str, toc_path: str) -> int:
        """导入TOC到数据库"""
        # 1. 读取TOC JSON
        # 2. 递归创建节点
        # 3. 提取文本块
        # 4. 生成向量嵌入
        pass

    async def extract_blocks(self, node_id: str, line_range: tuple) -> List[Dict]:
        """提取文本块"""
        pass

    async def generate_embeddings(self, blocks: List[Dict]) -> List[List[float]]:
        """生成向量嵌入（BGE）"""
        pass
```

### 4.2 检索服务

**文件**: `backend/services/retrieval/hybrid_search.py`

```python
class HybridRetriever:
    """混合检索服务"""

    async def search(
        self,
        query: str,
        limit: int = 10,
        use_vector: bool = True,
        use_fulltext: bool = True
    ) -> List[Dict]:
        """混合检索（向量+全文）"""
        # 1. 向量检索
        # 2. 全文检索
        # 3. 结果融合
        # 4. 重新排序
        pass

    async def vector_search(self, query: str, limit: int) -> List[Dict]:
        """向量检索"""
        pass

    async def fulltext_search(self, query: str, limit: int) -> List[Dict]:
        """全文检索"""
        pass
```

### 4.3 RAG服务

**文件**: `backend/services/rag/rag_pipeline.py`

```python
class RAGPipeline:
    """RAG管道服务"""

    async def answer(
        self,
        question: str,
        textbook_id: str = "7",
        mode: str = "basic"
    ) -> Dict:
        """问答"""
        # 1. 检索相关文档
        # 2. 构建prompt
        # 3. 调用DeepSeek生成答案
        # 4. 返回结果
        pass

    async def retrieve_context(self, question: str, textbook_id: str) -> List[Dict]:
        """检索上下文"""
        pass

    async def generate_answer(self, question: str, context: List[Dict]) -> str:
        """生成答案（DeepSeek）"""
        pass
```

### 4.4 API接口

**文件**: `backend/api/v1/textbooks.py`

```python
@router.get("/{textbook_id}/toc")
async def get_toc(textbook_id: str):
    """获取教材TOC"""
    pass

@router.get("/{textbook_id}/nodes/{node_id}")
async def get_node(textbook_id: str, node_id: str):
    """获取节点详情"""
    pass

@router.get("/{textbook_id}/blocks")
async def get_blocks(textbook_id: str, node_id: str):
    """获取文本块"""
    pass
```

**文件**: `backend/api/v1/search.py`

```python
@router.post("/search")
async def search(request: SearchRequest):
    """智能检索"""
    pass
```

**文件**: `backend/api/v1/chat.py`

```python
@router.post("/chat")
async def chat(request: ChatRequest):
    """智能问答"""
    pass
```

---

## 五、前端实现

### 5.1 技术栈选择

**方案A: 简化版（推荐MVP）**
- 原生HTML + CSS + JavaScript
- 无框架依赖
- 快速开发

**方案B: Vue.js 3**
- 更好的用户体验
- 组件化开发
- 需要构建工具

**建议**: MVP使用方案A，后续升级到方案B

### 5.2 页面结构

```
frontend/
├── index.html          # 首页（教材选择）
├── textbook.html       # 教材浏览页
├── search.html         # 搜索页
├── chat.html           # 问答页
├── css/
│   └── style.css       # 样式
└── js/
    ├── api.js          # API客户端
    ├── textbook.js     # 教材浏览
    ├── search.js       # 搜索
    └── chat.js         # 问答
```

### 5.3 核心功能

#### 教材浏览
- 左侧：TOC树状展示
- 右侧：内容详情
- 可展开/折叠

#### 搜索
- 搜索框
- 结果列表
- 高亮显示

#### 问答
- 对话界面
- 历史记录
- 引用来源

---

## 六、实施步骤

### Week 1: 数据导入

**Day 1-2: 数据库设计**
- 创建表结构
- 编写迁移脚本
- 测试数据库连接

**Day 3-4: 数据导入服务**
- 实现TOC导入
- 实现文本块提取
- 实现向量嵌入生成

**Day 5-7: 向量检索**
- 集成BGE模型
- 实现向量检索
- 实现全文检索
- 实现混合检索

### Week 2: RAG实现

**Day 8-10: RAG管道**
- 实现检索上下文
- 实现DeepSeek集成
- 实现答案生成

**Day 11-14: API开发**
- 实现教材API
- 实现搜索API
- 实现问答API
- API测试

### Week 3: 前端开发

**Day 15-17: 基础框架**
- 搭建页面结构
- 实现API客户端
- 样式设计

**Day 18-21: 功能实现**
- 实现教材浏览
- 实现搜索功能
- 实现问答功能

### Week 4: 测试和优化

**Day 22-24: 端到端测试**
- 测试教材浏览
- 测试检索质量
- 测试问答质量

**Day 25-28: 优化**
- 性能优化
- 用户体验优化
- Bug修复

---

## 七、质量目标

### 7.1 功能指标

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| TOC完整性 | 100% | 检查953条目是否全部导入 |
| 检索准确率 | >75% | 人工评估前50个检索结果 |
| 答案准确率 | >70% | 人工评估前50个问答结果 |
| 响应时间 | <5秒 | 测试100个请求 |

### 7.2 性能指标

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| 检索延迟 | <1秒 | 向量检索测试 |
| 答案生成 | <5秒 | RAG端到端测试 |
| 并发支持 | >10 QPS | 压力测试 |

---

## 八、风险和应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| BGE模型部署失败 | 中 | 高 | 使用OpenAI embedding |
| DeepSeek API不稳定 | 中 | 高 | 准备备用API |
| 性能不达标 | 中 | 中 | 优化索引、缓存 |
| 用户体验差 | 低 | 中 | 收集反馈、迭代 |

---

## 九、成功标准

MVP成功的标志：

1. ✅ 教材7的TOC完整导入数据库
2. ✅ 检索功能可用（向量+全文）
3. ✅ 问答功能可用（RAG）
4. ✅ Web UI可访问和使用
5. ✅ 答案准确率>70%
6. ✅ 响应时间<5秒
7. ✅ 至少5个用户测试并获得正面反馈

---

## 十、下一步

**立即执行**:
1. 创建数据库表结构
2. 实现数据导入服务
3. 导入教材7的TOC
4. 生成向量嵌入

**本周目标**:
- 完成数据导入
- 完成向量检索
- 完成基础API

**本月目标**:
- 完成完整MVP
- 通过质量测试
- 收集用户反馈

---

**文档版本**: 1.0.0
**创建日期**: 2026-03-28
**负责人**: AI Team
**预计完成**: 2026-04-28
