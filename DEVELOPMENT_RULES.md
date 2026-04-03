# 灵知系统 - 项目总体开发规则

**文档版本**: doc-v2.0.0
**项目版本**: v1.3.0-dev
**日期**: 2026-03-25 → 2026-03-31
**适用**: 全体开发阶段
**强制执行**: 是

---

## 0. 核心原则（最高准则）

> **"注重实践，避免空谈，一切围绕用户生命状态的提升提供服务"**

这是系统的最高准则，所有代码、功能、设计都必须服务于这个目标。

**📘 完整的核心原则请参考**: [ENGINEERING_ALIGNMENT.md - 第三章：核心原则](../ENGINEERING_ALIGNMENT.md#三核心原则)

本文档保留以下快速参考：

### 0.1 快速参考

**项目定位**: 集科学研究、理论探索、实践指导于一体的智能生命状态提升系统

**核心价值观**:
1. 知行合一 - 理论 + 实践
2. 用户中心 - 尊重意愿，个性化
3. 技术服务生命 - 技术是手段，生命是目的
4. 完整知识体系 - 科学 + 理论 + 实践

**核心原则三问**:
1. 这个功能如何帮助用户实践？
2. 如何验证它真的改善了用户生命状态？
3. 成功指标是什么？（技术+生命）

### 0.2 生命指标测量框架

为了回答"如何验证它真的改善了用户生命状态"，需要建立可操作的测量指标。

#### 直接指标（Direct Metrics）

| 指标 | 测量方式 | 数据来源 | 频率 |
|------|---------|---------|------|
| **连续练习天数** | 用户累计练习天数 | practice_records表 | 实时 |
| **用户等级迁移** | 入门→进阶→高级的次数 | user_level表 | 实时 |
| **生命状态自评** | 用户自评（1-10分） | life_state_tracking表 | 每周 |
| **练习完成率** | 计划vs实际完成比例 | practice_plan表 | 每周 |

#### 代理指标（Proxy Metrics）

| 指标 | 测量方式 | 代理目标 | 频率 |
|------|---------|---------|------|
| **实践转化率** | 知道理论后开始实践的比例 | 用户实际开始练习 | 每月 |
| **21天坚持率** | 持续练习21天的用户比例 | 形成习惯的能力 | 每月 |
| **生命状态改善率** | 自评有改善的用户比例 | 实际效果验证 | 每月 |
| **推荐意愿** | 愿意推荐给朋友的用户比例 | 满意度 | 每月 |

#### 测量流程

```
功能上线
    ↓
设定目标（如：21天坚持率>40%）
    ↓
数据收集（自动追踪+用户自评）
    ↓
数据分析（对比基线）
    ↓
效果验证（是否达到目标）
    ↓
决策（继续/调整/停止）
```

#### 数据表结构

```sql
-- 用户等级表
CREATE TABLE user_levels (
    user_id VARCHAR(100) PRIMARY KEY,
    current_level VARCHAR(50),  -- 入门、初级、中级、高级、资深
    level_history JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 生命状态追踪表
CREATE TABLE life_state_tracking (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    tracked_date DATE,
    physical_health INT CHECK (physical_health BETWEEN 1 AND 10),
    mental_peace INT CHECK (mental_peace BETWEEN 1 AND 10),
    energy_level INT CHECK (energy_level BETWEEN 1 AND 10),
    sleep_quality INT CHECK (sleep_quality BETWEEN 1 AND 10),
    emotional_stability INT CHECK (emotional_stability BETWEEN 1 AND 10),
    subjective_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 练习记录表
CREATE TABLE practice_records (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    concept VARCHAR(200),
    practice_date TIMESTAMP,
    duration_minutes INT,
    before_state JSONB,
    after_state JSONB,
    subjective_feeling TEXT,
    insights TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 0.3 代码审查标准

**所有代码审查必须检查**：

- ✅ 是否为生命状态提升服务？
- ✅ 是否尊重用户意愿？
- ✅ 是否有科学依据？
- ✅ 是否可验证效果？

### 0.4 完整知识体系

每个回答都应包含：理论理解、科学依据、实践方法、个性化建议

### 0.5 个性化服务

从2天体验到5年规划，完全个性化。每一步都尊重用户意愿。

### 0.6 技术与生命服务

技术指标服务于生命指标（参考 ENGINEERING_ALIGNMENT.md）

### 0.7 标注系统

提升识别精度 → 用户获得准确内容 → 练习正确 → 生命状态提升

详细说明参考: [docs/ANNOTATION_SYSTEM_CLARIFICATION.md](docs/ANNOTATION_SYSTEM_CLARIFICATION.md)

---

## 1. 项目结构规范

### 目录结构

```
zhineng-knowledge-system/
├── backend/                    # 后端代码（Python 3.12）
│   ├── main.py                # FastAPI 入口（create_app 工厂函数）
│   ├── config/                # 配置包（Pydantic Settings 多继承）
│   │   ├── __init__.py        # Config 单例、get_config()、reload_config()
│   │   ├── base.py            # BaseConfig（环境、API、BGE、DeepSeek）
│   │   ├── database.py        # DatabaseConfig
│   │   ├── redis.py           # RedisConfig
│   │   ├── security.py        # SecurityConfig（JWT、CORS、API Key）
│   │   └── lingzhi.py         # LingZhiConfig（遗留 DB 路径）
│   ├── api/                   # API 路由
│   │   ├── v1/                # v1 端点（documents, search, reasoning, books...）
│   │   └── v2/                # v2 端点（复用 v1 router，authenticated）
│   ├── services/              # 业务服务
│   │   ├── retrieval/         # 向量检索、BM25、混合检索
│   │   ├── reasoning/         # CoT、ReAct、GraphRAG 推理
│   │   ├── rag/               # RAG 编排
│   │   └── knowledge_base/    # 知识库处理
│   ├── domains/               # 领域驱动（气功、中医、儒家、通用）
│   ├── auth/                  # JWT 认证（RS256）+ RBAC
│   ├── gateway/               # API 网关（限流、熔断、路由）
│   ├── cache/                 # 多级缓存（L1 内存 + L2 Redis）
│   ├── core/                  # 应用基础设施
│   │   ├── lifespan.py        # FastAPI 生命周期（启动/关闭）
│   │   ├── database.py        # DB 连接池（asyncpg + SQLAlchemy）
│   │   ├── dependency_injection.py  # DI 容器 + FastAPI Depends
│   │   ├── service_manager.py # 服务生命周期管理
│   │   └── services.py        # DatabaseService、CacheService...
│   ├── common/                # 共享工具（db_helpers、singleton、typing）
│   ├── middleware/             # HTTP 中间件（限流、安全头）
│   ├── monitoring/            # 可观测性（指标、健康检查、Prometheus）
│   ├── models.py              # Pydantic 请求/响应模型
│   └── textbook_processing/   # 教材处理（TOC 解析、自动处理器）
├── frontend/                  # 前端（HTML/CSS/JS，Nginx 托管）
├── tests/                     # 测试（pytest + pytest-asyncio）
├── scripts/                   # 运维脚本（部署、健康检查、格式化）
├── nginx/                     # Nginx 反向代理配置
├── monitoring/                # Prometheus + Grafana 配置
├── docs/                      # 文档
├── data/                      # 运行时数据
├── docker-compose.yml         # 容器编排（9 个服务）
├── init.sql                   # 数据库 Schema（documents, chat_history, qigong_knowledge）
├── DEVELOPMENT_RULES.md       # 本文件（权威开发规范）
├── AGENTS.md                  # AI Agent 快速上手指南
└── ENGINEERING_ALIGNMENT.md   # 工程流程/原则/规划对齐文档
```

### 文件命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 模块 | 小写+下划线 | `services/retrieval.py` |
| 类名 | 大驼峰 | `VectorRetriever` |
| 函数名 | 小写+下划线 | `search_documents` |
| 常量 | 大写+下划线 | `MAX_RESULTS` |
| 私有方法 | 前缀下划线 | `_internal_func` |
| SQL 表名 | 小写+下划线复数 | `documents`, `chat_history` |
| SQL 字段 | 小写+下划线 | `created_at`, `user_id` |
| SQL 索引 | `idx_表名_字段` | `idx_documents_category` |

---

## 2. 代码编写规范

### Python 代码规范

遵循 PEP 8 标准，使用 Black 格式化：

```bash
# 格式化检查
isort backend/ --profile black
flake8 backend/ --max-line-length=100 --ignore=E203,W503,E501
```

#### 必须遵守的规则

1. **类型注解**: 所有公共函数必须有类型注解
```python
from typing import List, Dict

async def search_documents(query: str, limit: int = 10) -> List[Dict]:
    """搜索文档"""
    ...
```

2. **文档字符串**: 所有公共函数必须有 docstring
```python
def search_documents(query: str, limit: int = 10) -> List[Dict]:
    """
    搜索文档

    Args:
        query: 搜索关键词
        limit: 返回结果数量

    Returns:
        文档列表
    """
    ...
```

3. **异步优先**: I/O 操作必须使用 async/await
```python
# ✅ 正确
async def get_document(doc_id: int):
    row = await db.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)

# ❌ 错误
def get_document(doc_id: int):
    row = db.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
```

4. **错误处理**: 捕获具体异常
```python
# ✅ 正确
try:
    result = await api.call()
except ConnectionError as e:
    logger.error(f"连接失败: {e}")

# ❌ 错误
try:
    result = await api.call()
except Exception:
    pass
```

### 代码复杂度限制

| 指标 | 限制 | 说明 |
|------|------|------|
| 函数行数 | < 50 | 超过必须拆分 |
| 圈复杂度 | < 10 | 嵌套层数 |
| 参数数量 | < 5 | 超过使用对象 |
| 返回值类型 | 明确 | 使用类型注解 |

---

## 3. API 设计规范

### RESTful API 约定

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/resources | 获取列表 |
| GET | /api/resources/{id} | 获取单个 |
| POST | /api/resources | 创建资源 |
| PUT | /api/resources/{id} | 更新资源 |
| DELETE | /api/resources/{id} | 删除资源 |

### 响应格式统一

```python
# 成功响应
{
    "status": "ok",
    "data": {...}
}

# 错误响应
{
    "status": "error",
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "参数验证失败",
        "details": {...}
    }
}
```

### API 版本控制

- 主版本号不变时保持向后兼容
- 废弃 API 保留至少 1 个版本
- 使用 `/api/v{version}/` 前缀时需谨慎

---

## 4. Git 工作流规范

### 分支策略

```
main (生产分支)
├── develop (开发分支)
│   ├── feature/xxx (功能分支)
│   └── fix/xxx (修复分支)
```

### 提交规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

| Type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档更新 |
| style | 代码格式调整 |
| refactor | 重构 |
| test | 测试相关 |
| chore | 构建/工具链 |

### Commit 示例

```
feat(retrieval): 添加向量检索API

- 实现 /api/search/vector 端点
- 集成 BGE 嵌入服务
- 添加单元测试

Closes #123
```

### 提交前检查

```bash
# 1. 代码格式化
isort backend/ --profile black
flake8 backend/ --max-line-length=100

# 2. 运行测试
pytest tests/ -v

# 3. 类型检查 (可选)
mypy backend/
```

### 4.4 规则修改流程

**原则**：
- [ ] 修改规则和规划之前，必须进行充分的讨论
- [ ] 修改规则和规划必须基于真实数据
- [ ] 修改规则和规划必须得到共识

**流程（人工层）**：
1. 数据收集阶段
   - [ ] 收集完整的数据
   - [ ] 验证数据的准确性
   - [ ] 确保数据是基于真实的测量

2. 讨论阶段
   - [ ] 组织充分的讨论
   - [ ] 收集各方的意见
   - [ ] 识别讨论的共识和分歧
   - [ ] 解决讨论的分歧

3. 决策和执行阶段
   - [ ] 基于充分讨论做出决策
   - [ ] 确保决策是基于真实数据的
   - [ ] 获得各方对决策的认可
   - [ ] 按照决策执行修改
   - [ ] 验证修改的效果

**强制执行（技术层 - 详见 `HOOKS_IMPLEMENTATION_GUIDE.md`）**：

**触发条件**：
当 AI 或开发者尝试修改 `DEVELOPMENT_RULES.md` 或 `PHASED_IMPLEMENTATION_PLAN.md` 时触发。

**执行机制**：
`RulesChecker` Hook 将自动检查规则修改操作。

**检查项**：
- [ ] 是否已讨论（规则 4.4.1）
- [ ] 基于真实数据（规则 4.4.2）
- [ ] 是否达成共识（规则 4.4.3）

**注意**：
- 这是通过 `RulesChecker` Hook 自动强制执行的
- AI 无法绕过这个检查
- 详见 `docs/COMPREHENSIVE_HOOKS_IMPLEMENTATION_PLAN.md`

---

## 5. 测试规范

### 测试覆盖率要求

| 代码类型 | 覆盖率要求 |
|----------|------------|
| 核心业务逻辑 | > 80% |
| API 接口 | > 70% |
| 工具函数 | > 60% |

### 测试类型

```bash
# 单元测试
pytest tests/test_api.py -v

# 集成测试
pytest tests/integration/ -v

# 性能测试
pytest tests/performance/ -v

# 全部测试
pytest tests/ -v --cov=backend
```

### 测试命名规范

```python
# 功能测试
def test_search_documents_with_valid_query():
    ...

# 边界测试
def test_search_documents_with_empty_query():
    ...

# 异常测试
def test_search_documents_with_database_error():
    ...
```

---

## 6. 数据库规范

### SQL 规范

1. **表名**: 小写+下划线复数 `documents`, `chat_history`
2. **字段名**: 小写+下划线 `created_at`, `user_id`
3. **索引命名**: `idx_表名_字段名` `idx_documents_category`

### 数据库迁移

```sql
-- 迁移文件命名: YYYYMMDD_description.sql
-- 20260325_add_vector_table.sql
```

### 查询优化

```python
# ✅ 使用参数化查询
await db.fetch("SELECT * FROM documents WHERE id = $1", doc_id)

# ❌ 禁止 SQL 注入风险
await db.fetch(f"SELECT * FROM documents WHERE id = {doc_id}")
```

---

## 7. 安全规范

### 输入验证

```python
from pydantic import Field

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    category: str = Field(..., pattern="^(气功|中医|儒家)$")
```

### 密码管理

```bash
# .env 文件加入 .gitignore
echo ".env" >> .gitignore

# 使用环境变量
DATABASE_URL = os.getenv("DATABASE_URL")
```

### API 安全

- 输入验证必须严格
- 敏感数据不得记录到日志
- 实现 CORS 限制
- 考虑速率限制

### 数据库锁死防范 ⚠️ 强制规则

**背景**: 6进程并发导入导致锁死的历史教训 (2026-04-02)

```
PID  操作                    锁类型    等待
────────────────────────────────────────────
158759 INSERT ... ON CONFLICT   IO      5-35秒
159654 TRUNCATE guji_documents  Lock    34-49秒
160248 SELECT COUNT(*)          Lock    22-48秒
160317 SELECT pg_size_pretty()  Lock    21-50秒
160569 CREATE INDEX             Lock    16-39秒
161352 DROP+CREATE TABLE        Lock    47秒
```

**强制规则**:

1. **批量导入必须使用 ImportManager**
   ```python
   from backend.services.import_manager import ImportManager

   async with ImportManager("task_name") as mgr:
       # 执行导入
       pass
   ```

2. **使用统一入口运行导入**
   ```bash
   # 正确 ✅
   python scripts/import_guard.py guji

   # 错误 ❌ - 直接运行脚本可能导致并发
   python scripts/import_guji_data.py
   ```

3. **事务控制**
   - 批量操作分批提交 (1000-2000条/批)
   - 避免长事务持有锁
   - 设置超时: `lock_timeout = '5s'`, `statement_timeout = '300s'`

4. **监控和清理**
   ```bash
   # 定期检查锁状态
   python scripts/db_lock_monitor.py

   # 清理过期锁
   python scripts/db_lock_monitor.py --clean
   ```

5. **禁止操作**
   - ❌ 禁止同时运行多个导入脚本
   - ❌ 禁止在导入时执行 DDL (TRUNCATE/DROP)
   - ❌ 禁止绕过 ImportManager 的批量写入

---

## 8. 部署规范

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DATABASE_URL | 数据库连接 | - |
| REDIS_URL | Redis连接 | - |
| LOG_LEVEL | 日志级别 | INFO |
| API_PORT | API端口 | 8001 |

### 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| PostgreSQL | 5436 | 避免冲突 |
| Redis | 6381 | 避免冲突 |
| API | 8001 | 主服务 |
| Web | 8008 | 前端 |

### 健康检查

```bash
# 必须提供的健康检查端点
GET /health          # 服务健康状态
GET /health/db       # 数据库连接状态
```

---

## 9. 文档规范

### 必需文档

| 文档 | 位置 | 说明 |
|------|------|------|
| API 文档 | `/docs/api.md` | API 接口说明 |
| 部署文档 | `/docs/deploy.md` | 部署步骤 |
| 开发文档 | `/docs/dev.md` | 开发指南 |
| 变更日志 | `CHANGELOG.md` | 版本变更 |

### 文档格式

```markdown
# 标题

## 背景/目的

## 实现步骤

1. 步骤1
2. 步骤2

## 注意事项
```

---

## 10. 日志规范

### 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 调试信息 |
| INFO | 一般信息 |
| WARNING | 警告信息 |
| ERROR | 错误信息 |
| CRITICAL | 严重错误 |

### 日志格式

```python
logger.info(f"用户 {user_id} 执行搜索: {query}")
logger.error(f"数据库连接失败: {e}", exc_info=True)
```

### 日志内容规范

- ✅ 用户操作关键节点
- ✅ 错误信息含上下文
- ✅ 性能关键指标
- ❌ 不记录敏感信息

---

## 11. 性能规范

### 性能目标

| 指标 | 目标 |
|------|------|
| API 响应时间 | P95 < 1s |
| 数据库查询 | < 100ms |
| 页面加载 | < 2s |

### 优化措施

```python
# 使用连接池
pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

# 使用缓存
@cached_with_monitor(ttl=3600)
async def get_document(id: int):
    ...

# 只查询需要的字段
SELECT id, title, content FROM documents  # 而非 SELECT *
```

---

## 12. 代码审查规范

### 12.1 数据验证（带强制执行）

**数据验证要求**：
- [ ] 确保数据是真实的（基于静态分析或运行测试）
- [ ] 确保数据是准确的（经过二次验证）
- [ ] 确保数据是完整的（覆盖所有范围）

**强制执行机制（`DataVerificationGate` Hook）**：
在生成报告或进行决策前，必须通过 `DataVerificationGate`。

**执行机制**：
- 检查报告是否包含数据来源声明
- 禁止基于假设的数据（data_source: "assumption"）
- 验证静态分析/测试是否真实运行过

**注意**：
- 这是通过 `DataVerificationGate` Hook 自动强制执行的
- 详见 `docs/COMPREHENSIVE_HOOKS_IMPLEMENTATION_PLAN.md`

### 审查检查点

- [ ] 代码符合 PEP 8
- [ ] 函数有类型注解和文档字符串
- [ ] 有相应的单元测试
- [ ] 通过所有测试
- [ ] 无安全漏洞
- [ ] 性能无明显退化

### Pull Request 要求

1. 描述清晰的目的和变更
2. 关联相关 Issue
3. 通过 CI 检查
4. 至少 1 人审查

---

## 13. 禁止事项

### 严格禁止

1. ❌ 硬编码密码/密钥
2. ❌ SQL 注入风险代码
3. ❌ 提交敏感数据
4. ❌ 跳过测试直接合并
5. ❌ 在 main 分支直接开发
6. ❌ **忽视紧急问题**（技术强制执行）

### 13.3 紧急问题说明（带强制执行逻辑）

**紧急问题判定（技术标准）**：
```yaml
urgency_checks:
  - name: "system_health"
    check: "GET /health"
    condition: "status != 200"
  - name: "api_container"
    check: "docker ps --filter name=zhineng-api"
    condition: "status contains 'unhealthy'"
  - name: "import_errors"
    check: "python -m flake8 backend --select=F821"
    condition: "result.count > 0"
```

**强制执行机制（`UrgencyGuard` Hook）**：
当系统处于"紧急状态"时，`UrgencyGuard` Hook 将拦截所有非紧急操作。

**执行逻辑**：
1. **检查系统状态**：每次行动前，运行 `urgency_checks`
2. **判定状态**：如果任一检查失败，系统进入"紧急模式"
3. **拦截操作**：
   - ✅ **允许**：`fix_urgent_issue`、`debug_system`、`restart_service`
   - ❌ **拒绝**：`add_tests`、`refactor_code`、`modify_documentation`、`improve_coverage`

**注意**：
- 这是通过 `UrgencyGuard` Hook 自动强制执行的
- AI 无法绕过这个检查
- 详见 `docs/COMPREHENSIVE_HOOKS_IMPLEMENTATION_PLAN.md`

### 不推荐

1. ⚠️ 过度优化
2. ⚠️ 提前设计过度抽象
3. ⚠️ 添加非必要依赖

---

## 14. 系统资源管理规范

### 14.1 资源监控要求

**强制执行的监控标准**：
- [ ] 内存使用率必须 < 80%（警告阈值）
- [ ] 内存使用率必须 < 90%（紧急阈值）
- [ ] 磁盘使用率必须 < 85%（根分区）
- [ ] 容器必须有资源限制（mem_limit, cpus）
- [ ] 僵尸进程数量必须 < 10个

**自动监控机制**：
```bash
# 已配置的自动监控任务（crontab）
*/10 * * * * ./scripts/emergency_memory_recovery.sh  # 每10分钟检查
0 * * * * ./scripts/monitor_disk.sh                   # 每小时检查
*/30 * * * * ./scripts/monitor_docker.sh               # 每30分钟检查
0 * * * * ./scripts/cleanup_zombies.sh                 # 每小时清理
```

---

### 14.2 高等级响应事件定义

**响应事件等级**：

| 等级 | 触发条件 | 响应时间 | 处理优先级 |
|------|---------|---------|-----------|
| 🔴 P0 - 紧急 | 内存使用率 > 90% | 立即（<5分钟） | 最高 |
| 🟠 P1 - 严重 | 内存使用率 > 80% | 30分钟内 | 高 |
| 🟡 P2 - 警告 | 磁盘使用率 > 85% | 2小时内 | 中 |
| 🟢 P3 - 一般 | 单个容器异常 | 1天内 | 正常 |

**P0 紧急事件（技术强制执行）**：

当系统满足以下任一条件时，进入 **P0 紧急状态**：

```yaml
p0_triggers:
  memory_critical:
    condition: "内存使用率 > 90%"
    action: "立即执行应急恢复"
    auto_response: true

  container_oom:
    condition: "容器因OOM被杀死"
    action: "增加内存限制或优化应用"
    auto_response: true

  disk_full:
    condition: "根分区可用 < 10%"
    action: "紧急清理磁盘空间"
    auto_response: true

  service_down:
    condition: "核心服务停止运行"
    action: "立即重启服务"
    auto_response: true
```

**P0 状态的强制执行**：

1. **拦截非紧急操作**（技术层强制）
   - ❌ 禁止：新增功能、重构代码、优化测试、更新文档
   - ✅ 允许：修复资源问题、重启服务、清理缓存、扩容

2. **自动触发应急响应**
   ```bash
   # 自动执行（每10分钟检查）
   ./scripts/emergency_memory_recovery.sh
   ```

3. **立即通知机制**
   - 每日健康检查报告中高亮显示
   - Prometheus 告警规则触发
   - 系统日志记录 CRITICAL 级别

---

### 14.3 容器资源配置强制要求

**Docker Compose 配置要求**：

所有容器 **必须** 配置资源限制：

```yaml
services:
  your-service:
    deploy:
      resources:
        limits:
          cpus: '1.0'        # CPU上限
          memory: 1G         # 内存上限（必需）
        reservations:
          cpus: '0.5'        # CPU预留（可选）
          memory: 512M       # 内存预留（建议）
```

**资源限制标准**：

| 服务类型 | 内存限制 | CPU限制 | 说明 |
|---------|---------|---------|------|
| 核心API | 1GB | 1.0 | 主要业务服务 |
| 数据库 | 512MB | 0.5 | PostgreSQL/Redis |
| Web服务器 | 128MB | 0.3 | Nginx |
| 监控服务 | 256MB | 0.5 | Prometheus/Grafana |
| 辅助工具 | 64MB | 0.2 | Exporter等 |

**强制检查（`ResourceGuard` Hook）**：

在部署容器时，自动检查：
- [ ] 是否设置了 `mem_limit`
- [ ] 是否设置了 `cpus` 限制
- [ ] 限制值是否合理（参考标准）

**未配置资源限制的后果**：
- ⚠️ 容器可能无限制占用系统资源
- ⚠️ 单个容器异常可能导致系统崩溃
- ⚠️ 无法进行容量规划
- 🔴 **违反开发规范，禁止部署**

---

### 14.4 资源问题响应流程

**标准响应流程**：

1. **检测阶段**（自动）
   ```bash
   # 每10分钟自动检查
   ./scripts/emergency_memory_recovery.sh
   ```

2. **评估阶段**（自动 + 人工）
   - 确认资源占用情况
   - 识别占用高的进程/容器
   - 评估影响范围

3. **响应阶段**（自动优先）
   - P0级别：自动执行应急恢复
   - P1级别：自动告警，人工介入
   - P2/P3级别：记录日志，定期处理

4. **恢复阶段**（验证）
   - 确认资源使用率下降
   - 验证服务正常运行
   - 记录问题和解决方案

**P0 事件响应示例**：

```bash
# 检测到内存使用率 96%
# → 自动触发应急恢复脚本
# → 停止非核心容器
# → 清理系统缓存
# → 清理僵尸进程
# → 生成应急报告
# → 通知管理员

# 结果：内存使用率降至 80% 以下
```

---

### 14.5 容量规划与扩展

**容量基线管理**：

```bash
# 定期创建容量基线（每周）
./scripts/create_capacity_baseline.sh

# 生成容量评估报告（每周）
./scripts/weekly_capacity_review.sh
```

**扩容决策标准**：

| 指标 | 正常 | 警告 | 需要扩容 |
|------|------|------|---------|
| 内存使用率 | < 60% | 60-80% | > 80% |
| CPU使用率 | < 50% | 50-70% | > 70% |
| 磁盘使用率 | < 70% | 70-85% | > 85% |

**扩容流程**：
1. 评估当前资源使用趋势
2. 分析未来3-6个月容量需求
3. 制定扩容方案（硬件/架构优化）
4. 测试扩容方案
5. 执行扩容（低峰时段）
6. 验证扩容效果
7. 更新容量基线

---

### 14.6 资源问题预防措施

**日常预防**：

1. **每日健康检查**（每天早上9点）
   ```bash
   ./scripts/daily_health_check.sh
   ```

2. **每周容量评估**（每周日下午）
   ```bash
   ./scripts/weekly_capacity_review.sh
   ```

3. **容器资源限制审查**（每次部署前）
   - 检查新添加的服务是否配置了资源限制
   - 评估现有限制是否合理
   - 更新资源分配基线

**开发阶段预防**：

1. **代码审查检查点**：
   - [ ] 新服务是否配置了资源限制
   - [ ] 是否有内存泄漏风险
   - [ ] 是否有资源密集型操作

2. **测试阶段检查**：
   - [ ] 性能测试是否通过
   - [ ] 内存使用是否在预期范围
   - [ ] 是否有资源未释放的bug

3. **部署前检查**：
   - [ ] 容器资源限制已配置
   - [ ] 容量规划已更新
   - [ ] 监控告警已配置

---

### 14.7 违规处理

**资源管理违规**：

| 违规行为 | 后果 |
|---------|------|
| 部署无资源限制的容器 | 禁止部署，要求整改 |
| 忽视P0资源问题 | 强制切换到紧急模式 |
| 未经批准的高资源占用服务 | 强制停止容器 |
| 删除或禁用监控脚本 | 恢复脚本并警告 |

**资源管理规范修订**：

本规范的修订需要：
1. 基于真实的生产环境数据
2. 团队讨论并达成共识
3. 更新文档并通知所有成员
4. 更新相关的自动化检查脚本

---

## 15. 检查清单

### 开发前

- [ ] 确认开发分支
- [ ] 拉取最新代码
- [ ] 启动开发环境

### 提交前

- [ ] 代码格式化通过
- [ ] 所有测试通过
- [ ] 自查代码质量
- [ ] 更新相关文档

### 部署前

- [ ] 环境变量配置
- [ ] 数据库迁移准备
- [ ] 备份当前数据
- [ ] 通知相关人员

---

## 16. 违规处理

### 规范执行

所有规则必须遵守，如有违反：

1. 第一次：口头警告
2. 第二次：书面警告
3. 第三次：代码审查要求

### 规范修订

规范可以修订，但需要：

1. 提出修订理由
2. 团队讨论
3. 达成共识
4. 更新文档

---

## 17. 附录

### 工具配置

```bash
# .editorconfig
root = true

[*.py]
indent_size = 4
charset = utf-8

[*.md]
trim_trailing_whitespace = true
insert_final_newline = true
```

### VSCode 配置

```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Args": ["--max-line-length=100"],
    "python.formatting.provider": "black",
    "editor.formatOnSave": true
}
```

---

## 15. 外部资源访问规范

> **⚠️ 重要更新 (2026-04-03)**: 115网盘访问限制现已扩大到 **OpenList** 系统整体。
> 所有针对 OpenList 的访问（包括但不限于 115网盘路径、国学大师内容、古籍下载）
> **必须遵守以下速率限制**。

### 15.1 OpenList/115网盘访问限制

**严禁高速高频多线程访问OpenList！**

**强制执行的速率限制**（防止账号被锁定）：

| 参数 | 限制值 | 说明 |
|------|--------|------|
| **单文件线程数** | 2 | 下载单个文件时的最大线程 |
| **同时下载数** | 3～4 | 并发下载任务数量 |
| **API请求频率** | ≤ 1次/秒 | 接口调用间隔 |

**访问地址**：
- OpenList API: `http://100.66.1.8:2455`
- guji目录: `/115/国学大师/guji`

**代码实现要求**：

```python
# ✅ 正确 - 添加延迟
import time

async def fetch_guji_files():
    for file in files:
        result = await api.fetch(file)
        time.sleep(1)  # 每次请求间隔1秒
        yield result

# ❌ 错误 - 无延迟，可能触发保护
async def fetch_guji_files_wrong():
    for file in files:
        yield await api.fetch(file)  # 太快！
```

```python
# ✅ 正确 - 限制并发
import asyncio

MAX_CONCURRENT = 4  # 最大4个并发任务

async def fetch_with_limit():
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def fetch_one(file):
        async with semaphore:
            result = await api.fetch(file)
            await asyncio.sleep(1)  # 请求间隔
            return result

    return await asyncio.gather(*[fetch_one(f) for f in files])
```

### 15.2 rclone 访问配置

```bash
# ✅ 正确配置
rclone copy openlist:115/国学大师/guji /dest/ \
  --transfers 3 \          # 同时传输3个文件
  --checkers 4 \           # 4个检查线程
  --bwlimit 1M \           # 限速1MB/s
  --retries 3 \            # 失败重试3次
  --low-level-retries 10   # 低级重试

# ❌ 错误配置 - 会导致115保护
rclone copy openlist:115/国学大师/guji /dest/ \
  --transfers 10 \         # 太多并发！
  --bwlimit 10M            # 速率太高！
```

### 15.3 Hook 自动检查

**Pre-commit hook 自动检查**：
- 检测代码中是否有违反速率限制的模式
- 警告未添加延迟的API调用
- 检查并发数是否超限

**Hook脚本位置**：`scripts/hooks/check_115_rate_limit.py`

**执行方式**：
```bash
# 自动执行（每次git commit）
pre-commit run check-115-rate-limit --all-files

# 手动执行
python scripts/hooks/check_115_rate_limit.py
```

### 15.4 违规后果

| 违规类型 | 后果 |
|---------|------|
| 超过API频率 | 115账号被锁定（24小时） |
| 并发数超限 | 下载任务失败 |
| 无限制批量访问 | IP被临时封禁 |
| 违反OpenList限制 | 服务访问权限暂停 |

**恢复时间**：通常24小时，严重违规可能更长。

### 15.5 Claude Code 集成

**自动Hooks保护**（项目配置 `.claude/settings.json`）：

1. **PreToolUse Hook** - Bash命令执行前检查：
   - 检测openlist/115相关命令
   - 验证速率限制参数
   - 阻止高风险操作

2. **Write/Edit Hook** - 代码写入后检查：
   - 运行 `check_115_rate_limit.py` 验证
   - 警告未添加延迟的API调用
   - 检测并发数超限

3. **SessionStart Hook** - 会话开始时提醒：
   - 显示OpenList访问规则
   - 强调严禁高频访问

**环境变量**：
```bash
OPENLIST_RATE_LIMIT=1         # 请求间隔(秒)
OPENLIST_MAX_CONCURRENT=1     # 最大并发数
OPENLIST_MIN_DELAY=1          # 最小延迟(秒)
```

---

## 变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-03-25 | 初始版本 | LingFlow |
| 1.1.0 | 2026-03-30 | 新增第14章：系统资源管理规范 | Claude Code |
| 2.0.0 | 2026-03-31 | 更新项目结构至当前架构；补充 SQL 命名规范 | Claude Code |
| 2.0.0 | 2026-03-31 | 更新项目结构至当前架构；补充 SQL 命名规范；对齐 ENGINEERING_ALIGNMENT.md | Claude Code |
| 2.1.0 | 2026-04-02 | 新增第15章：外部资源访问规范（115网盘速率限制） | Claude Code |
| 2.2.0 | 2026-04-03 | 115网盘访问限制扩展至OpenList；新增Claude Code hooks集成；启用上下文管理 | Claude Code |

---

**本规则自 2026-03-25 起生效，所有开发活动必须遵守。**
