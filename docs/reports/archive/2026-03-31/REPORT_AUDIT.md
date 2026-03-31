# ARCHITECTURE_SECURITY_ANALYSIS.md 审计报告

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

> **审计日期**: 2026-03-30  
> **审计方法**: 逐条回溯源码验证，核实每一项声明的真实性、准确性和修复可行性

---

## 一、逐条审计结果

### SEC-1: 认证中间件未接入 — ✅ 真实，但修复建议严重不完整

**真实性**: 完全属实。`main.py:38-72` 确实未注册 `AuthMiddleware`，5 个中间件中无认证中间件。

**问题 — "一行代码修复"是错误的**:

报告建议添加 `app.add_middleware(AuthMiddleware)` 即可修复，这是**危险的误导**。

原因分析：

1. **没有登录端点**: `AuthConfig.public_paths` 定义了 `/auth/login`、`/auth/register`、`/auth/refresh` 为公开路径，但项目中**根本没有实现这些端点**。没有任何 API 路由处理登录/注册请求。

2. **添加后整个 API 立即锁死**: `AuthConfig.protected_path_prefixes = {"/api"}` 意味着所有 `/api/v1/*` 路由都需要认证。没有登录端点 = 没有人能获取令牌 = 所有接口永久返回 401。

3. **即使加了登录端点，也不够**: `InMemoryUserRepository` 只有硬编码的 admin/guest 用户，没有密码字段，没有登录验证逻辑。需要额外实现：
   - 用户名/密码验证
   - 登录路由
   - 注册路由
   - 令牌刷新路由

**实际需要的修复**（远不止一行）：

```
1. 实现 /auth/login 端点（用户名+密码 → TokenPair）
2. 实现 /auth/register 端点
3. 实现 /auth/refresh 端点（或使用已有的 RefreshTokenMiddleware）
4. 为 User 添加 password_hash 字段和验证方法
5. 将用户存储从内存迁移到数据库
6. 在 main.py 中添加 app.add_middleware(AuthMiddleware)
```

**结论**: 漏洞真实存在且严重，但报告将修复复杂度严重低估了。真实修复需要 4-8 个文件的改动，不是"一行代码"。

---

### SEC-2: RBAC 系统无效 — ✅ 真实

**验证结果**: 属实。由于 AuthMiddleware 未接入，`request.state.user` 永远不会被设置。RBAC 装饰器 (`@require_permission`, `@require_role`) 依赖 `request.state.user`，全部失效。

**补充**: 报告中"4 个角色 30+ 种权限"的描述准确 — `rbac.py:41-100` 定义了 `Permission` 枚举，`rbac.py:103-113` 定义了 `Role` 枚举（ADMIN/OPERATOR/USER/GUEST）。

---

### SEC-3: 缓存端点无保护 — ✅ 真实

**验证结果**: `health.py:163-209` 的 `POST /api/v1/cache/reset` 和 `POST /api/v1/cache/clear` 确实无任何认证或授权检查。

**评估**: 报告描述的攻击场景（缓存雪崩 → 数据库连接池耗尽）合理。报告建议"添加管理员权限校验"方向正确，但同样受 SEC-1 影响 — 需要先接入认证系统。

---

### SEC-4: 路径遍历 — ✅ 真实，但报告措辞过于谨慎

**报告原文**: "如果后续的 `process_textbook` 读取文件内容，则构成路径遍历漏洞"

**实际情况**: 不是"如果"，而是**确认读取**。

验证结果：
- `textbook_processing.py:122` — `Path(request.path)` 接受用户输入
- `textbook_processing.py:123` — 仅检查 `exists()`，无路径范围限制
- `textbook_service.py:163-167` — 确认调用 `_read_text_file(textbook_file_path)`
- `textbook_service.py:246-259` — `open(file_path, 'r', ...)` 直接打开任意文件

这是一个**已确认的任意文件读取漏洞**，攻击者可以读取服务器上进程用户有权限读取的任何文件（`/etc/passwd`、`.env`、密钥文件等）。

**报告应提升严重性描述**，从"风险"改为"已确认漏洞"。

**修复建议评估**: 报告建议的路径白名单方案方向正确，但还需要：
- 验证文件扩展名（仅允许 `.txt`, `.pdf` 等）
- 防止符号链接逃逸
- 对批量处理端点 `batch_process_textbooks` 同样需要验证

---

### SEC-5: 限流器 IP 伪造 — ✅ 真实，但需结合上下文

**验证结果**: `rate_limit.py:88-90` 直接信任 `X-Forwarded-For` 头，属实。

**上下文补充**: Nginx 配置（`nginx.conf:46`）确实使用 `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`，会追加真实 IP。**但是**：
- Nginx 没有 `real_ip` 模块配置，无法剥离客户端伪造的头部
- 如果攻击者直接访问 API 容器的 8001 端口（绕过 Nginx），可以完全伪造 IP

**修复建议评估**: 报告建议"仅在确认 Nginx 覆写了该头后才读取"方向正确但不够具体。实际修复：
1. API 容器端口 8001 不应暴露到宿主机（当前 `docker-compose.yml:72` 暴露了）
2. 在 Nginx 中添加 `set_real_ip_from` 配置
3. 在代码中添加可信代理 IP 列表

---

### SEC-6: 令牌黑名单仅存内存 — ✅ 真实

**验证结果**: `jwt.py:270` — `self._blacklisted: Dict[str, int] = {}`，纯内存字典。

报告准确。Redis 迁移建议合理且可行。

---

### SEC-7: RBAC 用户存储仅存内存 — ✅ 真实

**验证结果**: 
- `rbac.py:442` — `InMemoryUserRepository` 使用 `Dict[str, User]`
- `rbac.py:524-541` — 硬编码 admin（无密码）和 guest 用户
- `rbac.py:516` — `self._user_repo = user_repository or InMemoryUserRepository()` 为默认值

报告准确。但未提及一个更严重的问题：硬编码的 admin 用户**没有密码**，即使认证系统接入后，任何人都可以用 admin 身份获取令牌。

---

### SEC-8: Docker 默认弱密码 — ✅ 真实

**验证结果**: `docker-compose.yml` 确认使用 `${VAR:-default}` 模式且默认值为弱密码。

报告准确。但忽略了一个额外问题：`postgres-exporter` 的连接字符串（第 200 行）直接明文包含了密码，即使使用了环境变量替换。

---

### SEC-9: JWT 开发环境临时密钥 — ✅ 真实

**验证结果**: `jwt.py:179-203` 确认在非 production 环境自动生成临时 RSA 密钥对。

报告准确，风险评估合理。

---

### SEC-10: DeepSeek API Key 绕过配置 — ✅ 真实

**验证结果**: `reasoning.py:54,67,80` 三处直接使用 `os.getenv("DEEPSEEK_API_KEY")`，未通过 `Config` 系统。

报告准确。

---

### SEC-11: ILIKE 通配符注入 — ✅ 真实

**验证结果**: `qigong.py:123` — `search_pattern = f"%{query}%"` 中用户输入的 `%` 和 `_` 不会被转义。

报告准确。但应补充：同样的问题存在于 `qigong.py:155` 的 `get_exercise_by_name` 方法中。

---

### SEC-12: 错误信息泄露 — ✅ 真实

报告准确，多处 `str(e)` 直接返回客户端。

---

### ARC-1: 双数据库连接池 — ✅ 真实，报告细节需修正

**验证结果**: 两个独立连接池确认并存于同一运行时：

| 连接池 | 文件 | 参数 | 使用者 |
|--------|------|------|--------|
| Pool #1 | `core/database.py:18-36` | 硬编码 min=10, max=50 | search.py, documents.py, health.py, reasoning.py, services.py |
| Pool #2 | `dependency_injection.py:147-171` | 配置 min=2, max=config | lifespan.py |

**启动时序确认**:
1. `lifespan.py:93` → `service_manager.start_all()` → `DatabaseService.start()` → `init_db_pool()` → **Pool #1 创建**
2. `lifespan.py:132` → `get_db_pool()` (DI) → **Pool #2 创建**

**报告需修正**: 报告说"最多同时持有 50 + DB_POOL_SIZE 个连接"，但实际风险可能更小 — 如果 `DB_POOL_SIZE` 配置值 <= 50（常见默认值），两个池总共最多 100 个连接，对 PostgreSQL 来说不是灾难。但仍浪费资源且增加维护复杂度。

**修复建议评估**: 报告建议"移除 `core/database.py` 的 `init_db_pool()` 或将其代理到 DI 容器"。但更实际的修复方向是：
- 保留 `database.py` 的 `init_db_pool()`（被 6 个文件使用）
- 修改 `lifespan.py` 改为调用 `init_db_pool()` 而非 DI 的 `get_db_pool()`
- 废弃 DI 中的 `_db_pool`

报告的修复方向不够具体，未考虑改动影响范围的最小化。

---

### ARC-2: 全局单例泛滥 — ✅ 真实，数量准确

**验证结果**: 报告中列出的 15+ 个模块级全局变量全部属实，每个都有对应的源文件和变量名。

报告准确，问题分析合理。

---

### ARC-3: BM25 全量加载 — ✅ 真实，但问题比报告描述的更严重

**验证结果**: 
- `bm25.py:53-54` — `initialize()` 执行 `SELECT id, title, content FROM documents`，加载全部文档到内存
- `bm25.py:176-188` — `search()` 方法**每次搜索**也执行一次全量 `SELECT`，然后在 Python 中逐个计算 BM25 分数

报告只提到了 `initialize()` 的全量加载问题，但未提及更严重的问题：**每次搜索都会再次全量加载所有文档**。`initialize()` 只构建统计信息（文档频率、平均长度），实际搜索时还是要全部取出重新评分。

这意味着不仅是初始化慢，而是**每次查询都慢**。

---

### ARC-4: 生命周期碎片化 — ✅ 真实

**验证结果**: `lifespan.py` 中确实有 ServiceManager 管理的服务和多个独立的 `try/except` 初始化块。

报告准确。

---

### ARC-5: Optional Import 过度使用 — ✅ 真实

报告准确，5 个 `try/except ImportError` 块确认存在。

---

### ARC-6: 配置多继承复杂度 — ✅ 真实

报告准确。补充：`DATABASE_URL` 在 `base.py` 中为 `Optional` 但验证器强制非空的问题是真实的设计冲突。

---

### ARC-7: Docker Compose 命令重复 — ✅ 真实

**验证结果**: `docker-compose.yml:123-134`，Prometheus 服务确实定义了两次 `command`：
```yaml
command:                          # 第 123 行，完整配置（5 个参数）
  - '--config.file=...'
  - '--storage.tsdb.path=...'
  - ...
command: ['--config.file=...']    # 第 134 行，覆盖上面，只有 1 个参数
```

Docker Compose 中后定义的 `command` 覆盖先定义的，因此 Prometheus 实际只使用了 `--config.file` 一个参数，丢失了 `--storage.tsdb.path`、`--web.enable-lifecycle` 等配置。

---

## 二、报告整体评估

### 准确率

| 评估项 | 结果 |
|--------|------|
| 安全漏洞识别 | 12/12 全部属实 |
| 架构问题识别 | 7/7 全部属实 |
| 代码行号引用 | 准确（少量偏移因文件编辑） |
| 严重度评级 | 基本合理，2 处需调整 |
| 修复可行性 | **多处不切实际** |

### 需要修正的 5 个关键问题

**1. SEC-1 修复建议严重不完整（最关键）**

报告称"一行代码即可修复 3 个严重漏洞"，实际需要：
- 实现完整的认证端点（login/register/refresh）
- 添加用户密码验证
- 修改用户存储方式
- 涉及 4-8 个文件的改动

这个建议如果被直接执行，会导致**整个 API 立即不可用**（所有接口返回 401，无登录入口）。

**2. SEC-4 严重度描述不足**

报告用了"如果后续的 process_textbook 读取文件内容"的假设语气。实际已确认读取 — 应直接定性为"已确认的任意文件读取漏洞"，并升级措辞。

**3. ARC-1 修复建议未考虑影响范围最小化**

报告建议移除 `init_db_pool()` 或代理到 DI，但 `init_db_pool()` 被 6 个文件使用而 DI 的 `get_db_pool()` 仅被 `lifespan.py` 使用。更合理的修复是保留前者、废弃后者。

**4. ARC-3 遗漏了最严重的问题**

报告只提到 `initialize()` 全量加载，但 `search()` 方法每次查询也全量加载所有文档。后者才是真正的性能瓶颈。

**5. SEC-7 遗漏了 admin 无密码问题**

报告提到 InMemoryUserRepository 和硬编码用户，但未指出 admin 用户没有密码 — 这意味着即使接入认证系统，admin 账户也无法安全使用。

---

## 三、修订建议

### 对报告的修改

1. **SEC-1 修复建议** 应改为分阶段方案：
   - 短期：为敏感端点（cache/clear, cache/reset, graph/build, embeddings/update, textbook/process）添加 API Key 验证（利用现有的 `SecurityConfig.API_KEYS`）
   - 中期：实现完整认证系统后接入 AuthMiddleware

2. **SEC-4** 措辞从"如果后续...则构成风险"改为"已确认：任意文件读取漏洞"

3. **ARC-3** 补充：`search()` 方法每次查询都全量扫描，不仅是初始化问题

4. **优先级调整**: 将"一行代码修复"从 P0 移除，替换为"API Key 快速保护"作为 P0

### 报告整体结论

报告在**问题发现层面质量很高** — 12 个安全问题 + 7 个架构问题全部经过验证属实。但在**修复建议层面存在重大缺陷** — 特别是 SEC-1 的"一行修复"建议如果被直接执行会造成生产事故。建议在修复建议部分进行修订后再交付给开发团队。
