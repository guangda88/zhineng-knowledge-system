# 安全审计报告 — 2026-04-05

> **审计范围**: zhineng-knowledge-system 全栈深度审计
> **审计类型**: 上帝视角深入审计 + 自审计交叉验证
> **审计文件数**: 70+ 文件覆盖所有层级

---

## 审计总结

| 严重度 | 数量 | 已修复 |
|--------|------|--------|
| 🔴 CRITICAL | 3 | ✅ 3 |
| 🟠 HIGH | 1 | ✅ 1 |
| 🟡 MEDIUM | 5 | ✅ 5 |
| **合计** | **9** | **✅ 9** |

---

## 已修复漏洞

### P1 — 路径遍历（CRITICAL）

**影响端点**:
- `POST /api/v1/audio/import` — `audio_path` 参数
- `POST /api/v1/annotation/ocr/batch` — `pdf_path` 参数
- `POST /api/v1/annotation/transcription/batch` — `audio_path` 参数

**风险**: 攻击者可传入 `../../etc/passwd` 等路径读取服务器任意文件。

**修复方案**:
1. 新增 `validate_absolute_file_path()` 函数（`backend/utils/path_validation.py`）
   - 解析绝对路径后检查是否落在项目允许的子目录内
   - 拒绝 `..` 路径组件
   - 验证符号链接目标
   - 校验文件扩展名白名单
2. 在 `audio.py`、`annotation.py` 的端点入口处调用验证
3. 在 `audio_service.py` 的 `import_with_transcript()` 服务层再次验证

**修改文件**:
- `backend/utils/path_validation.py` — 新增 `validate_absolute_file_path()`
- `backend/api/v1/audio.py` — ImportRequest 路径验证
- `backend/api/v1/annotation.py` — BatchOCRRequest/BatchTranscriptionRequest 路径验证
- `backend/services/audio/audio_service.py` — 服务层双重验证

---

### P2 — 上传文件名路径遍历（CRITICAL）

**影响**: `POST /api/v1/audio/upload` — `UploadFile.filename` 未清洗

**风险**: `../../etc/cron.d/malicious` 作为文件名可写入任意路径。

**修复方案**:
- 使用 `Path(original_name).name` 剥离目录组件
- 额外检查 `..` 残留

**修改文件**: `backend/services/audio/audio_service.py:330-332`

---

### P3 — aiohttp 连接泄露（CRITICAL）

**影响**: 每次 LLM API 调用创建新 `aiohttp.ClientSession`，不复用。

**风险**: 高并发下耗尽文件描述符，导致服务不可用。

**修复方案**:
- 在 `LLMAPIClient` 类中添加 `_session` 实例属性
- 懒初始化 + 自动检测 session.closed 状态
- 新增 `async close()` 清理方法

**修改文件**: `backend/common/llm_api_wrapper.py`

---

### P4 — RBAC 静默降级（HIGH）

**影响**: `GET /api/v1/analytics/dashboard` — 管理员权限检查失败时静默允许匿名访问。

**风险**: 未授权用户可查看管理仪表板数据。

**修复方案**:
- 移除 `try/except ImportError` 静默降级
- 权限服务不可用时返回 HTTP 503 Service Unavailable

**修改文件**: `backend/api/v1/analytics.py:459-464`

---

### P5 — 闭包变量捕获 bug（MEDIUM）

**影响**: `enhanced_vector_service.py` 批量嵌入时闭包捕获 `batch` 变量引用。

**风险**: 在 `run_in_executor` 并发场景下可能编码错误的批次数据。

**修复方案**:
- 使用默认参数 `def _encode_batch(b=batch):` 强制早绑定

**修改文件**: `backend/services/enhanced_vector_service.py:351`

---

### P6 — 其他修复（MEDIUM）

| 问题 | 修复 | 文件 |
|------|------|------|
| Nginx 无安全响应头 | 添加 X-Content-Type-Options, X-Frame-Options, CSP 等 | `nginx/nginx.conf` |
| 硬编码绝对路径 `/home/ai/LingYi/src` | 改用环境变量 `LINGYI_SRC_PATH` | `backend/api/v1/discuss.py` |
| API 错误泄露内部信息 | 移除 `detail=f"...{e}"` 模式 | `backend/api/v1/audio.py` |
| 响应消息泄露文件路径 | 移除响应中的路径信息 | `backend/api/v1/annotation.py` |

---

## 自审计纠正

对原始审计的交叉验证，纠正了以下不准确发现：

| 原始发现 | 纠正结果 |
|----------|----------|
| "~95% 端点无认证" | **夸大** — 全局 AuthMiddleware 保护 `/api/*`，JWT 正常工作 |
| ".env 在 Git 中" | **错误** — `.gitignore` 排除，`git ls-files .env` 为空 |
| ".dockerignore 不存在" | **错误** — 文件存在且内容正确 |
| "限流盲目信任 X-Forwarded-For" | **错误** — 使用可信代理模型 |

---

## 测试结果

```
877 passed, 1 failed (pre-existing), 14 warnings
```

1 个失败用例 (`test_pipeline_api::test_task_detail`) 为预存问题（Event loop closed），与本次修复无关。

---

## 修改文件清单

| 文件 | 修改类型 |
|------|----------|
| `backend/utils/path_validation.py` | 新增 `validate_absolute_file_path()` |
| `backend/services/audio/audio_service.py` | 路径验证 + 文件名清洗 |
| `backend/api/v1/audio.py` | 端点路径验证 + 错误脱敏 |
| `backend/api/v1/annotation.py` | 批量端点路径验证 + 路径脱敏 |
| `backend/common/llm_api_wrapper.py` | 会话复用 + close() |
| `backend/api/v1/analytics.py` | RBAC 强制执行 |
| `backend/services/enhanced_vector_service.py` | 闭包早绑定 |
| `backend/api/v1/discuss.py` | 环境变量替代硬编码路径 |
| `nginx/nginx.conf` | 安全响应头 |
| `README.md` | 安全特性 + 变更日志更新 |
