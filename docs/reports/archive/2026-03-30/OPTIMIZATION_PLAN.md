# 项目框架优化方案

> 基于 ARCHITECTURE_SECURITY_ANALYSIS.md 及 REPORT_AUDIT.md 的审计结论

---

## 设计原则

1. **每步可独立测试** — 不依赖后续步骤
2. **向后兼容** — 不破坏现有 API 契约
3. **最小改动面** — 每步只改必要的文件
4. **渐进式** — 先止血再治病

---

## Phase 1: 安全止血（P0 — 零风险修复）

### 1.1 教材处理路径遍历修复
- **文件**: `backend/services/textbook_service.py`, `backend/api/v1/textbook_processing.py`
- **改动**: 添加路径白名单 + 扩展名验证 + 符号链接检测
- **风险**: 低 — 仅影响 textbook 端点，不影响其他路由
- **测试**: 单元测试验证路径拦截

### 1.2 Docker Compose 修复
- **文件**: `docker-compose.yml`
- **改动**: 删除重复 command、移除 API 8001 端口暴露
- **风险**: 极低 — 纯配置文件，不影响代码逻辑
- **测试**: `docker-compose config` 验证

### 1.3 限流器 IP 获取逻辑修复
- **文件**: `backend/middleware/rate_limit.py`
- **改动**: 添加可信代理配置，不盲信 X-Forwarded-For
- **风险**: 低 — 仅影响限流行为，不影响业务逻辑
- **测试**: 单元测试验证 IP 解析

---

## Phase 2: 敏感端点 API Key 保护（P0 — 低风险新增）

### 2.1 添加管理 API Key 配置
- **文件**: `backend/config/security.py`
- **改动**: 新增 `ADMIN_API_KEYS: List[str]` 配置项
- **风险**: 极低 — 新增字段，有默认空列表

### 2.2 创建 API Key 依赖
- **文件**: `backend/core/dependency_injection.py`（或新文件）
- **改动**: 新增 `require_admin_key()` FastAPI 依赖函数
- **风险**: 极低 — 纯新增，不影响现有代码

### 2.3 保护敏感端点
- **文件**: `backend/api/v1/health.py`, `backend/api/v1/textbook_processing.py`, `backend/api/v1/reasoning.py`, `backend/api/v1/search.py`
- **改动**: 为 cache/clear、cache/reset、textbook/process、graph/build、embeddings/update 添加 API Key 依赖
- **风险**: 中 — 改变现有端点行为（需 Key 才能访问）
- **测试**: 有/无 Key 的请求测试

---

## Phase 3: 数据库连接池统一（P1 — 重构）

### 3.1 统一到 init_db_pool()
- **文件**: `backend/core/lifespan.py`
- **改动**: 将 DI 的 `get_db_pool()` 调用替换为 `init_db_pool()`
- **风险**: 中 — 改动启动逻辑
- **测试**: 启动验证 + API 测试

### 3.2 清理 DI 中的冗余连接池
- **文件**: `backend/core/dependency_injection.py`
- **改动**: 标记 `_db_pool` 和相关函数为废弃
- **风险**: 低 — 仅标记，不删除

---

## Phase 4: 安全加固（P2 — 锦上添花）

### 4.1 错误信息脱敏
- **文件**: `backend/api/v1/health.py` 等
- **改动**: 替换 `str(e)` 为通用错误消息
- **风险**: 低

### 4.2 DeepSeek API Key 统一配置
- **文件**: `backend/api/v1/reasoning.py`
- **改动**: 从 Config 读取而非 os.getenv
- **风险**: 低

---

## 不在本方案范围内（需独立规划）

- AuthMiddleware 接入（需先实现 login/register 端点，工作量大）
- Token 黑名单迁移 Redis
- RBAC 用户存储迁移数据库
- BM25 性能优化（架构级改动）
- 全局单例统一管理

---

## 实施顺序与回滚策略

| 步骤 | 完成标准 | 回滚方式 |
|------|---------|---------|
| 1.1 | 路径遍历测试通过 | git revert |
| 1.2 | docker-compose config 通过 | git revert |
| 1.3 | IP 解析测试通过 | git revert |
| 2.1-2.3 | API Key 测试通过，无 Key 端点仍可访问 | git revert |
| 3.1-3.2 | 启动正常，API 测试通过 | git revert |
| 4.1-4.2 | 错误信息不泄露内部细节 | git revert |
