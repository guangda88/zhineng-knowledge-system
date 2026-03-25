# 智能知识系统 - 项目总体开发规则

**版本**: 1.0.0
**日期**: 2026-03-25
**适用**: 全体开发阶段
**强制执行**: 是

---

## 1. 项目结构规范

### 目录结构

```
zhineng-knowledge-system/
├── backend/                 # 后端代码
│   ├── main.py             # 主入口 (必须单文件优先)
│   ├── config.py           # 配置管理
│   ├── models.py           # 数据模型
│   ├── api/                # API 子模块 (需要时创建)
│   │   ├── __init__.py
│   │   ├── documents.py
│   │   └── chat.py
│   ├── services/           # 业务服务
│   │   ├── __init__.py
│   │   ├── retrieval.py    # 检索服务
│   │   └── rag.py          # RAG 服务
│   ├── utils/              # 工具函数
│   │   ├── __init__.py
│   │   ├── cache.py
│   │   └── logging.py
│   └── requirements.txt    # Python 依赖
├── frontend/              # 前端代码
│   └── dist/               # 构建输出
│       ├── index.html
│       ├── app.js
│       └── style.css
├── nginx/                 # Nginx 配置
│   └── nginx.conf
├── tests/                 # 测试代码
│   ├── test_api.py        # API 测试
│   ├── test_retrieval.py  # 检索测试
│   ├── conftest.py        # pytest 配置
│   └── pytest.ini         # pytest 设置
├── scripts/               # 脚本工具
│   ├── ima_migrator.py   # 数据迁移
│   └── init_db.py         # 数据库初始化
├── data/                  # 数据文件
│   └── import.json
├── docker-compose.yml     # 容器编排
├── init.sql               # 数据库初始化
├── requirements.txt       # 根依赖 (可选)
├── DEVELOPMENT_RULES.md   # 本文件
└── PHASED_IMPLEMENTATION_PLAN.md  # 开发规划
```

### 文件命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 模块 | 小写+下划线 | `services/retrieval.py` |
| 类名 | 大驼峰 | `VectorRetriever` |
| 函数名 | 小写+下划线 | `search_documents` |
| 常量 | 大写+下划线 | `MAX_RESULTS` |
| 私有方法 | 前缀下划线 | `_internal_func` |

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

### 不推荐

1. ⚠️ 过度优化
2. ⚠️ 提前设计过度抽象
3. ⚠️ 添加非必要依赖

---

## 14. 检查清单

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

## 15. 违规处理

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

## 16. 附录

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

## 变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-03-25 | 初始版本 | LingFlow |

---

**本规则自 2026-03-25 起生效，所有开发活动必须遵守。**
