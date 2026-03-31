# 智能知识系统 — 架构与安全深度分析报告

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

> **分析日期**: 2026-03-30  
> **分析范围**: `backend/` 全量源码、`docker-compose.yml`、基础设施配置  
> **严重等级**: 🔴 严重 | 🟠 高 | 🟡 中 | 🔵 低

---

## 一、架构总览

### 1.1 技术栈

| 层次 | 技术选型 |
|------|---------|
| Web框架 | FastAPI (ASGI) |
| 数据库 | PostgreSQL 16 + pgvector (asyncpg) |
| 缓存 | Redis 7 (redis-py async) |
| 反向代理 | Nginx (Alpine) |
| 监控 | Prometheus + Grafana |
| 容器 | Docker Compose v3.8 |

### 1.2 模块结构

```
backend/
├── api/v1/          # API路由层 (6个路由模块)
├── auth/            # JWT认证 + RBAC授权 (完整实现但未接入)
├── cache/           # L1/L2缓存管理
├── common/          # 公共工具 (DB helpers)
├── config/          # 多继承配置系统
├── core/            # 中间件、DI、生命周期、服务管理
├── domains/         # 领域路由 (气功/中医/儒家)
├── gateway/         # API网关、熔断器、限流器
├── middleware/       # 限流中间件
├── monitoring/      # 指标、健康检查、Prometheus导出
├── services/        # 检索(BM25/向量/混合)、推理(CoT/ReAct/GraphRAG)
└── models.py        # Pydantic数据模型
```

### 1.3 架构评估

**优点**:
- 清晰的模块化分层（路由 → 服务 → 基础设施）
- 完善的缓存架构（L1内存 + L2 Redis，带装饰器模式）
- 网关层设计合理（熔断器、滑动窗口限流、令牌桶）
- 安全头中间件完善（CSP, HSTS, X-Frame-Options, X-Content-Type-Options）
- 监控体系完整（Prometheus + Grafana + 自定义指标）

**核心问题**:
- 认证系统完全未接入运行时
- 大量模块级全局可变单例，缺乏统一生命周期管理
- 存在双数据库连接池管理
- 关键数据（黑名单、用户、BM25索引）仅存内存

---

## 二、安全漏洞分析

### 🔴 严重-1: 认证中间件未接入应用

**文件**: `backend/main.py:38-72`  
**影响**: 所有 `/api/v1/*` 路由完全无认证保护

`AuthMiddleware`（`backend/auth/middleware.py:174`）已完整实现 JWT 验证、用户上下文注入、令牌自动刷新等功能，但 `create_app()` 中从未调用 `app.add_middleware(AuthMiddleware)`。

当前 `main.py` 注册的中间件：
```python
# main.py:47-67
CORSMiddleware       ✅ 已注册
add_security_headers ✅ 已注册  
log_requests         ✅ 已注册
GZipMiddleware       ✅ 已注册
RateLimitMiddleware  ✅ 已注册
AuthMiddleware       ❌ 未注册
```

**后果**: 任何人可无认证访问全部 API 端点，包括文档管理、缓存操作、推理引擎等。

**修复建议**: 在 `main.py` 的 `create_app()` 中添加：
```python
from auth.middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)
```

---

### 🔴 严重-2: RBAC 权限系统形同虚设

**文件**: `backend/auth/rbac.py`  
**影响**: 所有 `@require_permission`、`@require_role` 装饰器无效果

由于 `AuthMiddleware` 未接入，`request.state.user` 永远不会被设置，RBAC 装饰器依赖的用户上下文始终为空。系统定义了 30+ 种权限和 4 个角色（ADMIN/OPERATOR/USER/GUEST），全部无法生效。

---

### 🔴 严重-3: 缓存操作端点无认证无授权

**文件**: `backend/api/v1/health.py:163-209`

```python
@router.post("/api/v1/cache/reset")  # 任何匿名用户可重置缓存统计
@router.post("/api/v1/cache/clear")  # 任何匿名用户可清空全部缓存
```

攻击者可通过反复调用 `POST /api/v1/cache/clear` 清空所有缓存，导致：
- 缓存雪崩：所有请求直达数据库
- 性能降级：热点查询失去缓存加速
- 服务拒绝：数据库连接池被耗尽

---

### 🟠 高-1: 教材处理路径遍历风险

**文件**: `backend/api/v1/textbook_processing.py:122-127`

```python
textbook_path = Path(request.path)  # 用户输入直接用于文件路径
if not textbook_path.exists():      # 验证存在但不验证范围
    raise HTTPException(status_code=404, ...)
```

用户可提交 `request.path = "/etc/passwd"` 或 `"../../../etc/hosts"` 等路径。虽然 `Path.exists()` 检查了存在性，但没有验证路径是否在允许的目录范围内。如果后续的 `process_textbook` 读取文件内容，则构成路径遍历漏洞。

**修复建议**: 添加路径范围验证：
```python
ALLOWED_BASE = Path("/app/textbooks")
textbook_path = (ALLOWED_BASE / request.path).resolve()
if not str(textbook_path).startswith(str(ALLOWED_BASE.resolve())):
    raise HTTPException(status_code=403, detail="Path not allowed")
```

---

### 🟠 高-2: 限流器 IP 伪造

**文件**: `backend/middleware/rate_limit.py:82-100`

```python
def _get_client_ip(self, request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()  # 直接信任
```

直接信任 `X-Forwarded-For` 头，攻击者可通过设置该头伪造 IP 绕过限流。在无反向代理或配置不当的环境下，这是一个可利用的漏洞。

**修复建议**: 
- 仅在确认 Nginx 覆写了该头后才读取
- 使用可信代理列表验证
- 考虑使用 `request.client.host` 作为最终回退

---

### 🟠 高-3: 令牌黑名单仅存内存

**文件**: `backend/auth/jwt.py:257-352`

`TokenBlacklist` 使用 Python `dict` 存储已吊销令牌：
```python
self._blacklisted: Dict[str, int] = {}  # 内存字典
```

**问题**:
- 应用重启后黑名单丢失，已登出的令牌可继续使用
- 多实例部署时各实例黑名单不共享
- 大量登出操作可能消耗大量内存

**修复建议**: 迁移到 Redis 存储，利用 TTL 自动清理。

---

### 🟠 高-4: RBAC 用户存储仅存内存

**文件**: `backend/auth/rbac.py`（`InMemoryUserRepository`）

默认 `RBACManager` 使用内存存储用户数据，包含硬编码的 admin/guest 用户。重启后所有用户数据丢失，无法持久化，也无法多实例共享。

---

### 🟠 高-5: Docker Compose 默认弱密码

**文件**: `docker-compose.yml:9,37,66,152,179,200`

| 服务 | 默认密码 |
|------|---------|
| PostgreSQL | `zhineng123` |
| Redis | `redis123` |
| Grafana | `admin123` |
| Postgres Exporter | 连接字符串明文 |

虽然使用了 `${VAR:-default}` 模式，但默认值是弱密码，生产环境可能直接使用默认值。

**修复建议**: 
- 移除默认值，强制通过 `.env` 文件或密钥管理服务提供
- 添加 `.env` 文件权限检查（不应提交到 Git）

---

### 🟡 中-1: JWT 开发环境自动生成临时密钥

**文件**: `backend/auth/jwt.py:179-203`

```python
if environment in ("production", "prod"):
    raise ValueError("生产环境必须提供 RSA 密钥对")
# 开发环境自动生成临时密钥
logger.warning("未提供RSA密钥对，生成临时密钥对...")
private_key, public_key = self._generate_rsa_key_pair()
```

如果 `ENVIRONMENT` 环境变量未设置或不是 `production`/`prod`，系统会在每次启动时生成新的密钥对。这意味着：
- 重启后所有已签发的令牌失效
- 如果错误地以开发配置部署到预发布环境，安全性无法保证

---

### 🟡 中-2: DeepSeek API Key 绕过配置系统

**文件**: `backend/api/v1/reasoning.py`（推理模块）

推理模块直接通过 `os.getenv("DEEPSEEK_API_KEY")` 读取 API Key，未经过统一的配置管理系统。这导致：
- 配置验证被绕过
- Key 可能被记录到日志中
- 无法利用配置热更新机制

---

### 🟡 中-3: 气功领域 ILIKE 通配符注入

**文件**: `backend/domains/qigong.py`

查询使用参数化 SQL（安全），但用户输入中的 `%` 和 `_` 不会被转义：
```sql
WHERE title ILIKE '%{user_input}%'
```
用户可以输入 `%` 匹配所有记录，或使用 `_` 进行单字符通配，可能泄露非预期数据。

---

### 🔵 低-1: 安全头中间件 CSP 未严格配置

**文件**: `backend/core/middleware.py`

CSP 策略如果配置过于宽松（如 `default-src *`），会降低 XSS 防护效果。

---

### 🔵 低-2: 错误信息泄露内部细节

多处异常处理直接返回 `str(e)` 给客户端：
```python
# health.py:116
return {"error": str(e), "enabled": False}
```
可能泄露数据库连接字符串、Redis 地址等内部信息。

---

## 三、架构问题分析

### 🔴 架构-1: 双数据库连接池管理

**文件对比**:
- `backend/core/database.py:18-36` — `init_db_pool()` 硬编码 min=10, max=50
- `backend/core/dependency_injection.py:147-171` — `get_db_pool()` 使用配置值 min=2, max=config.DB_POOL_SIZE

**问题**: 两套独立的连接池管理并存于同一应用中：
- `search.py:30` 调用 `init_db_pool()`（`core/database.py` 的）
- `lifespan.py:132` 调用 `get_db_pool()`（`dependency_injection.py` 的）
- `health.py:42` 调用 `init_db_pool()`

这意味着可能创建两个独立的 PostgreSQL 连接池，最多同时持有 `50 + DB_POOL_SIZE` 个连接，可能超过 PostgreSQL 的连接限制。

**修复建议**: 统一为一个连接池入口点，移除 `core/database.py` 的 `init_db_pool()` 或将其代理到 DI 容器。

---

### 🟠 架构-2: 模块级全局单例泛滥

项目中存在约 15+ 个模块级可变全局变量：

| 文件 | 变量 | 用途 |
|------|------|------|
| `core/database.py` | `db_pool` | 数据库连接池 |
| `core/dependency_injection.py` | `_db_pool`, `_redis_client`, `_container` | DI 容器及依赖 |
| `api/v1/search.py` | `_hybrid_retriever` | 混合检索器 |
| `api/v1/reasoning.py` | `_cot_reasoner`, `_react_reasoner`, `_graph_rag_reasoner` | 推理引擎 |
| `auth/jwt.py` | `_global_auth` | JWT 认证器 |
| `auth/rbac.py` | `_global_rbac` | RBAC 管理器 |
| `auth/middleware.py` | (依赖上述) | 认证中间件 |
| `domains/registry.py` | `_global_registry` | 领域注册表 |
| `core/service_manager.py` | `_global_service_manager` | 服务管理器 |
| `middleware/rate_limit.py` | `rate_limiter` | 限流器 |
| `cache/manager.py` | `_cache_manager` | 缓存管理器 |
| `monitoring/` | 多个指标收集器 | 监控 |

**问题**:
1. 没有统一的初始化顺序保证 — 各模块独立延迟初始化，可能产生循环依赖
2. 没有统一的清理路径 — `lifespan.py` 的关闭逻辑与单例清理可能冲突
3. 测试困难 — 全局状态难以隔离，测试间可能互相影响
4. 多实例部署不安全 — 内存状态不共享

**修复建议**: 
- 利用现有的 `ServiceManager` 统一管理所有服务生命周期
- 使用 FastAPI 的 `app.state` 存储运行时实例
- 将延迟初始化改为显式初始化（在 lifespan 中）

---

### 🟠 架构-3: BM25 全量加载不可扩展

**文件**: `backend/services/retrieval/bm25.py`

`BM25Retriever.initialize()` 将所有文档加载到内存构建倒排索引：
```python
async def initialize(self):
    documents = await self.pool.fetch("SELECT id, title, content, category FROM documents")
    # 全量加载到内存
```

当文档量增长到数万或更多时：
- 内存占用线性增长
- 初始化时间变长
- 索引更新需要全量重建

**修复建议**: 
- 使用 PostgreSQL 的全文搜索（`tsvector`/`tsquery`）替代内存 BM25
- 或引入 Elasticsearch/MeiliSearch 等专用搜索引擎
- 至少实现增量索引更新

---

### 🟠 架构-4: 生命周期管理碎片化

**文件**: `backend/core/lifespan.py`

生命周期管理存在两个问题：

1. **双重初始化路径**: `ServiceManager` 管理了一组服务（DatabaseService, CacheService 等），但后续还有独立的初始化块（cache setup、domains、health checks、metrics），这些不在 ServiceManager 的管理范围内。

2. **静默降级过多**: 大量 `try/except` 块捕获异常后仅 `logger.warning` 继续，应用可能以降级状态运行而运维人员不知情：
```python
try:
    from backend.cache import setup_cache
    await setup_cache(...)
except Exception as e:
    logger.warning(f"Cache initialization failed (continuing without cache): {e}")
```

**修复建议**: 
- 将所有初始化逻辑纳入 ServiceManager 统一管理
- 关键服务（数据库、缓存）初始化失败应阻止启动
- 添加启动就绪检查端点，暴露各子系统状态

---

### 🟡 架构-5: Optional Import 过度使用

**文件**: `backend/core/lifespan.py:72-174`

lifespan 中有 5 个 `try/except ImportError` 块：
```python
try:
    from backend.core.config_watcher import ...
except Exception:
    ...
try:
    from domains import setup_domains
except ImportError:
    ...
try:
    from monitoring import get_health_checker
except ImportError:
    ...
```

这导致应用可能以不可预测的状态运行 — 某些功能缺失但无明确通知。对于内部模块（非第三方库），ImportError 通常表示代码结构问题而非可选依赖。

---

### 🟡 架构-6: 配置系统多继承复杂度

**文件**: `backend/config/__init__.py`

`Config` 类通过多继承组合：
```python
class Config(BaseConfig, DatabaseConfig, RedisConfig, SecurityConfig, LingZhiConfig):
    ...
```

各父类有自己的验证器，但配置值来源混杂（环境变量、默认值、字段验证器），增加了配置冲突的排查难度。特别是 `DATABASE_URL` 在 `base.py` 中是 `Optional` 但在 `database.py` 的验证器中强制非空。

---

### 🔵 架构-7: Docker Compose 命令重复定义

**文件**: `docker-compose.yml:123-134`

Prometheus 服务定义了两次 `command`：
```yaml
command:
  - '--config.file=/etc/prometheus/prometheus.yml'
  - ...
command: ['--config.file=/etc/prometheus/prometheus.yml']  # 覆盖上面的
```

第二个 `command` 会覆盖第一个，导致部分配置丢失。

---

## 四、问题汇总表

| 编号 | 严重度 | 类别 | 问题 | 位置 |
|------|--------|------|------|------|
| SEC-1 | 🔴 严重 | 安全 | 认证中间件未接入 | `main.py` |
| SEC-2 | 🔴 严重 | 安全 | RBAC 系统无效 | `auth/rbac.py` |
| SEC-3 | 🔴 严重 | 安全 | 缓存端点无保护 | `health.py:163-209` |
| SEC-4 | 🟠 高 | 安全 | 路径遍历风险 | `textbook_processing.py:122` |
| SEC-5 | 🟠 高 | 安全 | IP 伪造绕过限流 | `rate_limit.py:82-100` |
| SEC-6 | 🟠 高 | 安全 | 黑名单仅存内存 | `jwt.py:257-352` |
| SEC-7 | 🟠 高 | 安全 | 用户存储仅存内存 | `rbac.py` |
| SEC-8 | 🟠 高 | 安全 | 默认弱密码 | `docker-compose.yml` |
| SEC-9 | 🟡 中 | 安全 | 开发环境临时密钥 | `jwt.py:179-203` |
| SEC-10 | 🟡 中 | 安全 | API Key 绕过配置 | `reasoning.py` |
| SEC-11 | 🟡 中 | 安全 | ILIKE 通配符注入 | `domains/qigong.py` |
| SEC-12 | 🔵 低 | 安全 | 错误信息泄露 | 多处 |
| ARC-1 | 🔴 高 | 架构 | 双数据库连接池 | `database.py` vs `di.py` |
| ARC-2 | 🟠 高 | 架构 | 全局单例泛滥 | 15+ 模块 |
| ARC-3 | 🟠 高 | 架构 | BM25 全量加载 | `bm25.py` |
| ARC-4 | 🟠 高 | 架构 | 生命周期碎片化 | `lifespan.py` |
| ARC-5 | 🟡 中 | 架构 | Optional Import 过度 | `lifespan.py` |
| ARC-6 | 🟡 中 | 架构 | 配置多继承复杂 | `config/__init__.py` |
| ARC-7 | 🔵 低 | 架构 | Compose 命令重复 | `docker-compose.yml` |

---

## 五、优先修复建议

### 立即修复（P0 — 安全阻断项）

1. **接入 AuthMiddleware** — `backend/main.py` 添加 `app.add_middleware(AuthMiddleware)`
2. **保护缓存端点** — 对 `/api/v1/cache/clear` 和 `/api/v1/cache/reset` 添加管理员权限校验
3. **修复路径遍历** — `textbook_processing.py` 添加路径白名单验证

### 短期修复（P1 — 1-2周内）

4. **统一数据库连接池** — 合并 `core/database.py` 和 `dependency_injection.py` 的连接池管理
5. **令牌黑名单迁移 Redis** — 利用现有 Redis 基础设施持久化黑名单
6. **修复 IP 获取逻辑** — 添加可信代理配置，防止 IP 伪造
7. **强化默认密码** — 移除 docker-compose.yml 中的弱默认值

### 中期优化（P2 — 1个月内）

8. **统一单例管理** — 将所有模块级单例迁移到 ServiceManager
9. **BM25 外置** — 引入 PostgreSQL 全文搜索或 Elasticsearch
10. **生命周期整合** — 将所有初始化逻辑纳入 ServiceManager

---

## 六、架构改进方向

### 6.1 认证架构

```
当前状态:
  AuthMiddleware → 未注册 → 所有请求无认证
  
目标状态:
  Request → RateLimitMiddleware → AuthMiddleware → Route Handler
                                                        ↓
                                                   @require_permission()
                                                        ↓
                                                   RBAC Check
```

### 6.2 连接池统一

```
当前状态:
  core/database.py::init_db_pool()     ← search.py, health.py 使用
  dependency_injection.py::get_db_pool() ← lifespan.py 使用
  
目标状态:
  ServiceManager → DatabaseService → 单一连接池
                                       ↓
                              所有模块通过 DI 获取
```

### 6.3 可扩展性改进

- BM25 索引 → PostgreSQL tsvector 或 Elasticsearch
- 内存缓存 → 统一使用 Redis（已支持 L2）
- 全局单例 → ServiceManager + app.state

---

*报告完*
