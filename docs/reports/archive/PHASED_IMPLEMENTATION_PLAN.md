# 智能知识系统 - 分步实施总体规划

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**版本**: 1.0.0
**日期**: 2026-03-25
**目标**: 从模块化到统一完成

---

## 总体策略

```
核心理念：增量式开发，每阶段都可独立验证

阶段0: 规划与准备
  ↓
阶段1: 最小可用 (MVP) - 单模块验证
  ├── 基础数据层
  └── 简单查询
  ↓
阶段2: 核心功能 - 气功知识模块
  ├── 向量检索
  └── 气功问答
  ↓
阶段3: RAG 增强 - 智能检索
  ├── 混合检索
  └── 重排序
  ↓
阶段4: 推理能力 - 复杂问答
  ├── CoT推理
  └── GraphRAG
  ↓
阶段5: 系统集成 - 统一平台
  ├── 多领域支持
  └── API网关
  ↓
阶段6: 高级特性 - 生产就绪
  ├── 监控告警
  └── 性能优化
```

---

## 📋 阶段 0: 规划与准备 (1-2天)

### 目标
- 明确技术栈
- 搭建开发环境
- 准备基础设施

### 任务清单

```bash
# 0.1 项目规划
├── [ ] 定义功能优先级
├── [ ] 确定技术选型
└── [ ] 制定里程碑

# 0.2 环境准备
├── [ ] Docker 环境
├── [ ] Python 3.12
├── [ ] Node.js 18+
└── [ ] 数据库准备

# 0.3 基础设施
├── [ ] 共享存储目录
├── [ ] 网络配置
└── [ ] 安全配置
```

### 验收标准
- [ ] 环境可以运行 `docker --version`
- [ ] 可以连接到共享存储
- [ ] Python 和 Node.js 可用

### 输出物
- 环境检查脚本
- 技术选型文档

---

## 📋 阶段 1: 最小可用 MVP (3-5天)

### 目标
- 建立最基础的数据存储和查询能力
- 验证基础设施可用性
- **单模块，可独立运行**

### 架构

```
┌─────────────────────────────────┐
│         阶段1架构                │
├─────────────────────────────────┤
│                                 │
│  ┌─────────┐                   │
│  │ FastAPI │                   │
│  │ :8001   │                   │
│  └────┬────┘                   │
│       │                         │
│       ▼                         │
│  ┌─────────┐                   │
│  │PostgreSQL│                  │
│  │ :5436   │                   │
│  └─────────┘                   │
│                                 │
│  简单的CRUD API                  │
└─────────────────────────────────┘
```

### 任务清单

```bash
# 1.1 数据库层
├── [ ] 启动 PostgreSQL 容器
├── [ ] 创建数据库和表结构
├── [ ] 插入气功知识样本数据 (5-10条)
└── [ ] 验证数据可查询

# 1.2 基础API
├── [ ] 创建 FastAPI 项目
├── [ ] 实现 CRUD 接口
│   ├── GET /api/v1/documents       - 获取文档列表
│   ├── GET /api/v1/documents/{id}   - 获取单个文档
│   ├── POST /api/v1/documents      - 创建文档
│   └── GET /api/v1/search?q={query} - 简单搜索
└── [ ] 测试 API 可用性

# 1.3 前端界面
├── [ ] 创建简单的 HTML 页面
├── [ ] 实现文档列表展示
├── [ ] 实现搜索功能
└── [ ] 前后端联调

# 1.4 Docker 化
├── [ ] 编写 Dockerfile
├── [ ] 编写 docker-compose.yml
├── [ ] 一键启动脚本
└── [ ] 验证部署
```

### 文件结构 (阶段1)

```
zhineng-knowledge-system/
├── docker-compose.yml
├── backend/
│   ├── main.py              # FastAPI 主入口
│   ├── database.py          # 数据库连接
│   ├── models.py            # 数据模型
│   ├── crud.py              # CRUD 操作
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/
│   └── sample_data.sql
├── tests/
│   ├── test_api.py
│   └── conftest.py
├── DEVELOPMENT_RULES.md
└── PHASED_IMPLEMENTATION_PLAN.md
```

### 验收标准
- [ ] `docker-compose up -d` 成功启动
- [ ] 访问 http://localhost:8001/docs 看到 API 文档
- [ ] 可以通过 API 添加和查询文档
- [ ] 前端页面能正常显示文档列表 (http://localhost:8008)
- [ ] 搜索功能返回正确结果

### 成果展示
```bash
# 启动
cd /home/ai/zhineng-knowledge-system && docker-compose up -d

# 测试
curl http://localhost:8001/api/v1/documents
curl http://localhost:8001/api/v1/search?q=气功

# 访问
浏览器打开 http://localhost:8001/docs
```

---

## 📋 阶段 2: 核心功能 - 气功知识模块 (5-7天)

### 目标
- 实现向量检索能力
- 建立气功领域知识库
- **独立模块，可独立运行**

### 架构

```
┌─────────────────────────────────────┐
│         阶段2架构                    │
├─────────────────────────────────────┤
│                                      │
│  ┌──────────┐  ┌───────────┐         │
│  │Web 前端  │  │FastAPI后端│         │
│  │  :8008   │  │   :8001    │         │
│  └────┬─────┘  └─────┬─────┘         │
│       │             │                │
│       ▼             ▼                │
│  ┌──────────────────────┐           │
│  │   气功知识服务      │           │
│  │   (内嵌模块)        │           │
│  └──────────────────────┘           │
│       │                             │
│       ▼                             │
│  ┌───────────┐  ┌───────────┐       │
│  │PostgreSQL │  │   Redis   │       │
│  │+pgvector  │  │  缓存     │       │
│  │  :5436    │  │  :6381    │       │
│  └───────────┘  └───────────┘       │
│                                      │
│  核心功能:                           │
│  • 向量嵌入 + 检索                    │
│  • 气功知识库                         │
│  • 智能问答                           │
└──────────────────────────────────────┘
```

### 任务清单

```bash
# 2.1 向量数据库
├── [ ] 配置 pgvector 扩展
├── [ ] 创建向量表结构
├── [ ] 实现向量嵌入 API
├── [ ] 集成 BGE 嵌入模型
└── [ ] 测试向量检索效果

# 2.2 气功知识库
├── [ ] 创建知识库表结构
├── [ ] 整理气功知识数据
│   ├── 基础理论 (10篇)
│   ├── 功法练习 (15篇)
│   ├── 养生保健 (10篇)
│   └── 练习技巧 (8篇)
├── [ ] 实现数据导入脚本
└── [ ] 批量导入知识

# 2.3 气功知识服务
├── [ ] 创建独立 FastAPI 服务
├── [ ] 实现知识检索 API
├── [ ] 实现问答 API
├── [ ] 集成向量检索
└── [ ] 添加领域特色功能

# 2.4 检索功能
├── [ ] 实现混合检索
│   ├── BM25 关键词检索
│   └── 向量语义检索
├── [ ] 实现结果合并
├── [ ] 实现重排序
└── [ ] 优化检索精度

# 2.5 Docker Compose 更新
├── [ ] 添加 qigong-service
├── [ ] 添加 redis
├── [ ] 更新环境变量
└── [ ] 编写启动脚本
```

### 文件结构 (阶段2)

```
zhineng-knowledge-system/
├── docker-compose.yml
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── services/
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── vector.py       # 向量检索
│   │   │   ├── bm25.py         # 关键词检索
│   │   │   └── hybrid.py       # 混合检索
│   │   └── qigong/
│   │       ├── __init__.py
│   │       ├── base_theory.py  # 基础理论
│   │       ├── exercises.py    # 功法练习
│   │       ├── health.py       # 养生保健
│   │       └── techniques.py   # 练习技巧
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/
│   ├── qigong_knowledge.json   # 气功知识数据
│   └── sample_embeddings.json  # 预计算嵌入
└── tests/
    ├── test_api.py
    └── test_retrieval.py
```

### 核心代码示例

```python
# 向量检索服务 (异步)
import asyncpg
from typing import List, Dict, Optional

class VectorRetriever:
    """向量检索服务 - 遵循异步优先规则"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.embedding_model = "BAAI/bge-large-zh-v1.5"

    async def init_pool(self, dsn: str) -> None:
        """初始化数据库连接池"""
        self.pool = await asyncpg.create_pool(
            dsn,
            min_size=2,
            max_size=10
        )

    async def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        向量相似度搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        # 1. 生成查询向量
        query_vector = await self.embed(query)

        # 2. 向量相似度搜索
        sql = """
            SELECT id, title, content,
                   1 - (embedding <=> $1::vector) as similarity
            FROM documents
            ORDER BY embedding <-> $1::vector
            LIMIT $2
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, query_vector, top_k)
            return [dict(row) for row in rows]
```

### 验收标准
- [ ] 向量检索准确率 > 80%
- [ ] 气功知识库包含 40+ 篇文档
- [ ] 问答功能正常工作
- [ ] 混合检索优于单一检索
- [ ] 响应时间 < 500ms

---

## 📋 阶段 3: RAG 增强 (5-7天)

### 目标
- 集成 RAG 能力
- 支持文档上传和解析
- 实现智能问答

### 架构

```
┌──────────────────────────────────────┐
│         阶段3架构                     │
├──────────────────────────────────────┤
│                                        │
│  ┌────────┐  ┌──────┐  ┌─────────┐  │
│  │Web UI  │  │API   │  │向量检索  │  │
│  └───┬────┘  └───┬──┘  └─────┬───┘  │
│      │          │               │     │
│      ▼          ▼               ▼     │
│  ┌─────────────────────────────────┐ │
│  │        RAG Pipeline           │ │
│  │  ┌────────┐  ┌──────┐        │ │
│  │  │文档解析│  │嵌入  │        │ │
│  │  └────┬───┘  └───┬──┘        │ │
│  │       │         │              │ │
│  │       ▼         ▼              │ │
│  │  ┌────────┐  ┌──────────┐   │ │
│  │  │ 向量库  │  │ LLM API   │   │ │
│  │  └────────┘  └──────────┘   │ │
│  └─────────────────────────────────┘ │
│                                        │
│  新功能:                               │
│  • 文档上传 (PDF/Word/TXT)            │
│  • 自动分块和嵌入                      │
│  • RAG 问答                            │
└──────────────────────────────────────┘
```

### 任务清单

```bash
# 3.1 文档处理
├── [ ] 实现文件上传 API
├── [ ] 集成文档解析库
│   ├── PyPDF2 (PDF)
│   ├── python-docx (Word)
│   └── chardet (编码检测)
├── [ ] 实现文档分块
│   ├── 按段落分块
│   ├── 按语义分块
│   └── 固定大小分块
└── [ ] 实现批处理队列

# 3.2 RAG 问答
├── [ ] 设计 Prompt 模板
├── [ ] 实现上下文检索
├── [ ] 集成 LLM API (DeepSeek)
├── [ ] 实现答案生成
└── [ ] 添加引用来源

# 3.3 前端增强
├── [ ] 文档上传界面
├── [ ] 对话界面
├── [ ] 答案展示（高亮来源）
└── [ ] 历史记录

# 3.4 测试与优化
├── [ ] 单元测试
├── [ ] 集成测试
├── [ ] 性能测试
└── [ ] 用户体验优化
```

### RAG Pipeline 代码

```python
class RAGPipeline:
    def __init__(self):
        self.embedder = "BAAI/bge-large-zh-v1.5"
        self.llm = "deepseek-chat"
        self.vector_db = PostgreSQL()

    async def answer(self, question: str):
        # 1. 检索相关文档
        docs = await self.retrieve(question, top_k=3)

        # 2. 构建提示词
        context = "\n".join([f"{d['title']}: {d['content']}" for d in docs])
        prompt = f"""
基于以下上下文回答问题：

上下文：
{context}

问题：{question}

请给出准确的答案，并引用来源。
"""

        # 3. 调用 LLM
        answer = await self.llm.generate(prompt)

        return {
            "answer": answer,
            "sources": [d["id"] for d in docs]
        }
```

### 验收标准
- [ ] 支持上传 PDF/Word 文档
- [ ] 自动分块准确率 > 90%
- [ ] RAG 问答准确率 > 85%
- [ ] 答案包含引用来源
- [ ] 端到端响应时间 < 3s

---

## 📋 阶段 4: 推理能力 (7-10天)

### 目标
- 添加推理模式
- 支持复杂问题链式推理
- 优化回答质量

### 架构

```
┌──────────────────────────────────────┐
│         阶段4架构                     │
├──────────────────────────────────────┤
│                                        │
│  ┌─────────────────────────────────┐  │
│  │       推理引擎                  │  │
│  │  ┌────────┐  ┌──────────┐      │  │
│  │  │CoT Engine│  │ReAct Agent│     │  │
│  │  └────────┘  └────┬─────┘      │  │
│  │                   │               │  │
│  │  ┌────────▼──────────────┐     │  │
│  │  │   DeepSeek-R1 API       │     │  │
│  │  │   (复杂推理)           │     │  │
│  │  └────────────────────────┘     │  │
│  └─────────────────────────────────┘  │
│                     ▼                   │
│  ┌─────────────────────────────────┐  │
│  │       知识库 + GraphRAG         │  │
│  │  • 实体抽取                   │  │
│  │  • 关系构建                   │  │  │
│  │  • 图谱遍历                   │  │
│  └─────────────────────────────────┘  │
│                                        │
│  新功能:                               │
│  • Chain-of-Thought 推理             │
│  • 多步推理链                        │
│  • 图谱推理 (实体关系)               │
│  • 推理过程可视化                   │
└──────────────────────────────────────┘
```

### 任务清单

```bash
# 4.1 推理引擎
├── [ ] 实现 CoT (Chain of Thought)
├── [ ] 实现 ReAct 模式
├── [ ] 集成 DeepSeek-R1 API
└── [ ] 实现推理缓存

# 4.2 GraphRAG
├── [ ] 实体抽取
├── [ ] 关系抽取
├── [ ] 图谱构建 (Neo4j 或 内存图谱)
├── [ ] 图谱遍历查询
└── [ ] 与 RAG 集成

# 4.3 推理 API
├── [ ] POST /api/v1/reason - 推理问答
├── [ ] POST /api/v1/graph_query - 图谱查询
└── [ ] GET /api/v1/reasoning/{id} - 推理历史

# 4.4 前端展示
├── [ ] 推理过程展示
├── [ ] 思维链可视化
└── [ ] 图谱可视化 (简单版)
```

### 推理 API 示例

```python
@app.post("/api/v1/reasoning")
async def reasoning_answer(request: ReasoningRequest):
    """推理问答"""

    # 1. 分析问题类型
    query_type = analyze_query(request.question)

    # 2. 选择推理模式
    if query_type == "factual":
        # 简单事实查询 - 直接检索
        return await simple_search(request.question)

    elif query_type == "reasoning":
        # 需要推理的问题
        return await cot_reasoning(request.question)

    elif query_type == "multi_hop":
        # 多跳推理 - 使用 GraphRAG
        return await graph_rag_reasoning(request.question)


async def cot_reasoning(question: str):
    """Chain of Thought 推理"""

    prompt = f"""
请使用逐步推理的方式回答以下问题：

问题：{question}

请按照以下格式回答：
思考过程：
1. 首先分析问题的关键点
2. 然后逐步推理
3. 最后得出结论

答案：
[你的最终答案]
"""

    # 调用 DeepSeek-R1 (推理模型)
    response = await deepseek_r1.generate(
        prompt,
        max_tokens=2000,
        temperature=0.7
    )

    return response
```

### 验收标准
- [ ] 推理模式准确提升 15%+
- [ ] 复杂问题有推理过程展示
- [ ] GraphRAG 支持多跳查询
- [ ] 推理缓存命中率 > 30%

---

## 📋 阶段 5: 系统集成 (5-7天)

### 目标
- 统一多领域支持
- 实现 API 网关
- 完善监控

### 架构

```
┌──────────────────────────────────────┐
│         阶段5架构                     │
├──────────────────────────────────────┤
│                                        │
│  ┌────────────────────────────────┐   │
│  │         API Gateway            │   │
│  │  ┌────────┐  ┌──────┐        │   │
│  │  │路由   │  │认证  │        │   │
│  │  └───┬────┘  └───┬──┘        │   │
│  │      │          │             │   │
│  │      ▼          ▼             │   │
│  │  ┌──────────────────────────┐ │   │
│  │  │    服务层                │ │   │
│  │  │  ┌─────────┬─────────┐│   │   │
│  │  │  │气功知识 │ 通用知识││   │   │
│  │  │  │  :8002  │  :8001  ││   │   │
│  │  │  └─────────┴─────────┘│   │   │
│  │  └──────────────────────────┘ │   │
│  └────────────────────────────────┘   │
│                                        │
│  ┌───────────────────────────────────┐ │
│  │         支持服务                │ │ │
│  │  • 任务队列 (Celery)              │ │ │
│  │  • 向量库 (PostgreSQL+pgvector)   │ │ │
│  │  • 缓存 (Redis)                   │ │ │
│  │  • 存储 (MinIO)                   │ │ │
│  └───────────────────────────────────┘ │
│                                        │
│  ┌───────────────────────────────────┐ │
│  │         监控                    │   │ │
│  │  • Grafana                      │ │ │
│  │  • Prometheus                   │ │ │
│  │  │ 日志聚合                      │ │ │
│  └───────────────────────────────────┘ │
│                                        │
└──────────────────────────────────────┘
```

### 任务清单

```bash
# 5.1 API 网关
├── [ ] 实现统一路由
├── [ ] 实现服务注册与发现
├── [ ] 实现负载均衡
├── [ ] 实现熔断降级
└── [ ] 实现 API 限流

# 5.2 多领域支持
├── [ ] 抽象领域接口
├── [ ] 气功领域实现
├── [ ] 通用知识领域实现
├── [ ] 可扩展的领域插件系统
└── [ ] 跨领域查询

# 5.3 监控完善
├── [ ] 配置 Prometheus 指标
├── [ ] 配置 Grafana 仪表盘
├── [ ] 实现日志聚合
├── [ ] 实现告警规则
└── [ ] 实现健康检查

# 5.4 部署优化
├── [ ] 统一 docker-compose.yml
├── [ ] 编写部署脚本
├── [ ] 实现滚动更新
└── [ ] 实现备份恢复
```

### API 网关示例

```python
class APIGateway:
    """API 网关"""

    def __init__(self):
        # 服务注册表
        self.services = {
            "qigong": "http://qigong-service:8002",
            "general": "http://general-service:8001",
            "tcm": "http://tcm-service:8003"
        }

    async def route_request(self, request):
        # 1. 识别领域
        domain = await self.detect_domain(request)

        # 2. 路由到对应服务
        service_url = self.services.get(domain)
        if not service_url:
            # 降级到通用服务
            service_url = self.services["general"]

        # 3. 转发请求
        return await self.forward(service_url, request)

    async def detect_domain(self, request):
        """识别问题所属领域"""
        keywords = request.query.lower()

        # 气功关键词
        qigong_keywords = ["气功", "八段锦", "呼吸", "养生", "功法"]
        if any(kw in keywords for kw in qigong_keywords):
            return "qigong"

        # 中医关键词
        tcm_keywords = ["中医", "针灸", "中药", "经络", "穴位"]
        if any(kw in keywords for kw in tcm_keywords):
            return "tcm"

        return "general"
```

### 验收标准
- [ ] API 网关正常运行
- [ ] 多领域查询正确路由
- [ ] 监控数据正常采集
- [ ] 告警规则生效
- [ ] 系统可用性 > 99%

---

## 📋 阶段 6: 高级特性 (5-7天)

### 目标
- 生产环境就绪
- 性能优化
- 安全加固

### 任务清单

```bash
# 6.1 性能优化
├── [ ] 实现查询缓存
├── [ ] 实现结果缓存
├── [ ] 优化数据库查询
├── [ ] 添加 CDN 支持
└── [ ] 性能压测

# 6.2 安全加固
├── [ ] 实现 JWT 认证
├── [ ] 实现 RBAC 权限
├── [ ] 添加 API 限流
├── [ ] 实现数据加密
└── [ ] 安全扫描

# 6.3 运维工具
├── [ ] 实现一键部署脚本
├── [ ] 实现一键备份
├── [ ] 实现一键恢复
├── [ ] 编写运维文档
└── [ ] 实现 CI/CD

# 6.4 文档完善
├── [ ] API 文档
├── [ ] 部署文档
├── [ ] 用户手册
├── [ ] 运维手册
└── [ ] 开发文档
```

### 优化配置

```python
# 性能优化配置
PERFORMANCE_CONFIG = {
    "cache": {
        "enabled": True,
        "ttl": {
            "query_result": 3600,     # 查询结果缓存1小时
            "vector_search": 1800,    # 向量搜索缓存30分钟
            "llm_response": 7200     # LLM响应缓存2小时
        }
    },
    "batching": {
        "enabled": True,
        "batch_size": 10,
        "timeout": 5000
    },
    "optimization": {
        "query_parallel": True,
        "result_rerank": True,
        "early_termination": True
    }
}
```

### 验收标准
- [ ] P95 响应时间 < 100ms (简单查询)
- [ ] P95 响应时间 < 2s (复杂查询)
- [ ] 并发支持 > 100 QPS
- [ ] 安全扫描通过
- [ ] 文档完整度 > 90%

---

## 📊 进度跟踪

### 里程碑

| 阶段 | 预计时间 | 状态 | 完成度 |
|------|----------|------|--------|
| 阶段0: 规划准备 | 1-2天 | ✅ 完成 | 100% |
| 阶段1: MVP | 3-5天 | ✅ 完成 | 100% |
| 阶段2: 气功模块 | 5-7天 | 🔄 收尾 | 95% |
| 阶段3: RAG增强 | 5-7天 | ✅ 完成 | 100% |
| 阶段4: 推理能力 | 7-10天 | ✅ 完成 | 100% |
| 阶段5: 系统集成 | 5-7天 | ⏳ 待开始 | 0% |
| 阶段6: 高级特性 | 5-7天 | ⏳ 待开始 | 0% |

### 总计

- **预计总时间**: 30-45 天
- **可并行**: 部分阶段可并行开发
- **灵活调整**: 可根据实际情况调整

---

## 🎯 立即开始：阶段0

```bash
# 创建阶段0目录
mkdir -p phase0-setup

# 环境检查脚本
cat > phase0-setup/check_env.sh << 'EOF'
#!/bin/bash
echo "=== 环境检查 ==="

echo "检查 Docker..."
if command -v docker &> /dev/null; then
    echo "✅ Docker: $(docker --version)"
else
    echo "❌ Docker 未安装"
    exit 1
fi

echo "检查 Python..."
if command -v python3 &> /dev/null; then
    echo "✅ Python: $(python3 --version)"
else
    echo "❌ Python 未安装"
    exit 1
fi

echo "检查 Node.js..."
if command -v node &> /dev/null; then
    echo "✅ Node.js: $(node --version)"
else
    echo "❌ Node.js 未安装"
    exit 1
fi

echo "检查共享存储..."
if [ -d /data ]; then
    echo "✅ 共享存储: /data ($(df -h /data | tail -1 | awk '{print $4} 可用'))"
else
    echo "❌ 共享存储 /data 不存在"
    exit 1
fi

echo "=== 环境检查完成 ==="
EOF
chmod +x phase0-setup/check_env.sh
```

需要我开始执行阶段0的环境检查吗？
