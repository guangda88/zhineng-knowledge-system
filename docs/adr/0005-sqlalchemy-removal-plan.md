# ADR-0005: SQLAlchemy 逐步移除计划（里程碑 M6）

**状态**: 已接受
**日期**: 2026-04-03
**目标**: 2026-05-31（M6）

## 背景

项目使用双重数据库访问模式：
- **asyncpg 原始 SQL**：性能关键路径（搜索、嵌入、生命周期API）
- **SQLAlchemy 异步 ORM**：Book、Annotation、Evolution 等模块

### 当前 SQLAlchemy 使用范围（19个文件）

| 类别 | 文件数 | 模块 |
|------|--------|------|
| ORM 模型定义 | 4 | book.py, source.py, text_annotation.py, evolution.py |
| API 路由（ORM查询） | 3 | books.py, analytics.py, evolution.py |
| 服务层（ORM查询） | 4 | book_search.py, text_annotation_service.py, verification_agent.py, cache_service.py |
| 独立分析脚本 | 4 | analytics/scripts/ 下4个脚本 |
| 核心基础设施 | 1 | core/database.py（Base、engine、session factory） |
| Web App 服务 | 2 | services/web_app/ 下2个文件 |
| 其他 | 1 | scripts/migrate_user_analytics.py |

### 关键架构问题

1. **两个 Base 类**：`database.py` 用 `declarative_base()`，`evolution.py` 用独立的 `DeclarativeBase`
2. **同步 vs 异步**：`text_annotation_service.py` 使用同步 `Session`，其余用 `AsyncSession`
3. **多数仅用 `text()`**：5个文件仅使用 SQLAlchemy 的 `text()` 执行原始 SQL，可零改动迁至 asyncpg

## 决策

分三个阶段移除 SQLAlchemy，保留 ORM 模型定义文件至最后：

### 阶段一：低风险迁移（2026年4月）
**仅移除 `text()` 包装层，改用 asyncpg 直接执行**

| 文件 | 迁移方式 | 风险 |
|------|----------|------|
| `analytics.py` | `text()` → asyncpg `pool.execute()` | 低 |
| `evolution.py` | `text()` → asyncpg | 低 |
| `migrate_user_analytics.py` | 已用 asyncpg，仅移除 sqlalchemy import | 低 |
| `backup_manager.py` | `text()` → asyncpg | 低 |

### 阶段二：ORM 查询迁移（2026年5月）
**将 ORM select/add/commit 改为 asyncpg 原始 SQL**

| 文件 | 迁移方式 | 风险 |
|------|----------|------|
| `books.py` | ORM → asyncpg 参数化查询 | 中 |
| `book_search.py` | ORM query builder → asyncpg SQL | 中 |
| `text_annotation_service.py` | 同步 Session → asyncpg | 中（需重写为异步） |

### 阶段三：模型定义清理（2026年5月底）
**移除 ORM 模型和 database.py 中的 SQLAlchemy 基础设施**

| 文件 | 操作 |
|------|------|
| `models/book.py` | 转为 Pydantic schema（保留类型定义） |
| `models/source.py` | 同上 |
| `models/text_annotation.py` | 同上 |
| `models/evolution.py` | 同上 |
| `core/database.py` | 移除 `declarative_base()`、`create_async_engine()`、`sessionmaker` |

### 不迁移的范围

`analytics/scripts/` 下4个独立脚本保持 SQLAlchemy——它们是离线分析工具，不影响运行时性能，且迁移收益低。

## 理由

1. **性能统一**：asyncpg 比 SQLAlchemy ORM 快3-5倍（避免查询构建开销）
2. **代码一致**：消除项目中两种 DB 访问模式的认知负担
3. **依赖简化**：移除 SQLAlchemy 减少约 2MB 依赖和 ORM 抽象层
4. **ADR-003 对齐**：ENGINEERING_ALIGNMENT 已限制 SQLAlchemy 仅用于 ORM 查询

## 后果

- 需为每个迁移模块编写测试，确保行为不变
- ORM 模型转为 Pydantic schema 后，类型验证由 Pydantic 承担
- `analytics/scripts/` 保留 SQLAlchemy 作为例外，在代码注释中说明
