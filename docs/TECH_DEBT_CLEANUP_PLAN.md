# 技术债务清理计划

> 创建日期: 2026-03-31 | 基于: docs/TECHNICAL_DEBT.md | 执行方式: LingFlow Agent Workflow
> 工作流文件: `.lingflow/workflows/tech_debt_cleanup.yaml`

---

## 执行策略

### 原则

1. **安全第一**: P0 安全漏洞立即修复，不接受延期
2. **不退化**: 每次修改后跑测试，确保 pytest ≥383 通过
3. **小步提交**: 每个修复独立可验证
4. **优先级驱动**: P0 → P1 → P4-A/B/C/D 顺序执行

### 阶段规划

| 阶段 | 优先级 | 工期 | 修复项数 | 目标 |
|------|--------|------|---------|------|
| **Phase 1** | P0 安全 | Day 1 | 6 | 消除所有安全漏洞 |
| **Phase 2** | P1 架构 | Day 2-3 | 4 | 修复 FTS 索引、补充缺失表 |
| **Phase 3** | P4 质量 | Day 4-5 | 17 | 弃用 API、静默异常、死代码 |
| **Phase 4** | 验证 | Day 6-7 | — | 全量测试 + 文档更新 |

---

## Phase 1: P0 安全漏洞修复 (Day 1)

### S1: 硬编码 API 密钥 → 环境变量

**文件**: `backend/api/v1/external.py:30-42`

**方案**:
```python
# Before: 硬编码
self.valid_keys = {
    "lingzhi_dev_key_2026": {...},
    "lingzhi_prod_key_2026": {...},
}

# After: 从环境变量读取
import json, os
_keys_json = os.getenv("EXTERNAL_API_KEYS", "")
if _keys_json:
    self.valid_keys = json.loads(_keys_json)
elif os.getenv("ENVIRONMENT") == "development":
    self.valid_keys = {
        "dev-key-for-testing-only": {
            "name": "开发测试", "rate_limit": 1000,
            "permissions": ["search", "retrieve"], "active": True,
        }
    }
    logger.warning("使用开发模式默认 API 密钥，生产环境请设置 EXTERNAL_API_KEYS")
else:
    self.valid_keys = {}
```

**需同步修改**:
- `.env`: 添加 `EXTERNAL_API_KEYS` 配置

### S2: JWT 弱默认密钥 → 强制设置

**文件**: `backend/core/security.py:18`

**方案**:
```python
# Before:
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-min-32-characters-long")

# After:
_secret = os.getenv("SECRET_KEY")
if _secret:
    SECRET_KEY = _secret
elif os.getenv("ENVIRONMENT") == "development":
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)
    import logging
    logging.getLogger(__name__).warning("开发模式使用随机 JWT 密钥，重启后失效")
else:
    raise ValueError("生产环境必须设置 SECRET_KEY 环境变量")
```

### S3: 硬编码 DB 凭据 → 环境变量

**文件**: `backend/services/textbook_importer.py:288`

**方案**:
```python
# Before:
db_url = "postgresql://zhineng:zhineng123@localhost:5436/zhineng_kb"

# After:
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("错误: 请设置 DATABASE_URL 环境变量")
    sys.exit(1)
```

### S5: 命令注入 → 安全参数

**文件**: `backend/services/learning/innovation_manager.py:103`

**方案**:
```python
# Before:
subprocess.run(f"cd {self.project_root} && git checkout -b {branch_name}", shell=True, ...)

# After:
import shlex
subprocess.run(
    ["git", "checkout", "-b", branch_name],
    cwd=self.project_root,
    check=True, capture_output=True
)
```

### S6: 创建 .dockerignore

**文件**: `.dockerignore` (新建)

排除: `.git/`, `__pycache__/`, `venv/`, `backups/`, `data/`, `.env`, `docs/`, `tests/`

### S4: docker-compose 弱密码回退

**方案**: 添加注释警告，不改变默认值（避免破坏开发环境兼容性）

---

## Phase 2: P1 架构缺陷修复 (Day 2-3)

### P1-C: FTS 索引语言修复

**文件**: `scripts/migrations/add_indexes.sql:11`

```sql
-- Before:
CREATE INDEX idx_documents_content_fts ON documents USING gin(to_tsvector('english', content));

-- After:
DROP INDEX IF EXISTS idx_documents_content_fts;
CREATE INDEX idx_documents_content_fts ON documents USING gin(to_tsvector('chinese', content));
```

### P1-D: 补充缺失数据库表定义

创建 `scripts/migrations/create_textbook_tables.sql`，定义 `textbook_nodes` 和 `textbook_blocks` 表。

---

## Phase 3: P4 代码质量改善 (Day 4-5)

### P4-A: 弃用 API 替换 (6处)

| 文件 | 修改 |
|------|------|
| `services/enhanced_vector_service.py:224` | `get_event_loop()` → `get_running_loop()` |
| `cache/manager.py:444` | 同上 |
| `core/urgency_guard.py:88` | 同上 |
| `core/services.py:332` | 同上 |
| `cache/decorators.py:466` | 同上 |
| `services/retrieval/vector.py:33` | 同上 |

### P4-C: 静默吞异常修复 (7处)

为每个 `except ... pass` 添加 `logger.warning()` 日志记录。

### P4-D: 未使用导入清理 (2处)

- `services/hybrid_retrieval.py:21`: 移除 `import numpy as np`
- `services/audio/cohere_transcriber.py:13`: 移除 `import numpy as np`

### P4-E: 死代码移除 (2处)

- `services/textbook_importer.py:277-281`: 移除 `raise NotImplementedError` 后的不可达代码
- `services/retrieval/vector.py:65`: 移除未使用的 `embedding_api_url` 参数

---

## 延后项 (不在本轮修复)

| 优先级 | 项目 | 原因 |
|--------|------|------|
| P1-A | 导入路径统一 (44文件) | 影响面太大，需单独分支 |
| P1-B | 测试框架替换 | 需要大量重写，风险高 |
| P2 | 测试质量改善 | 非紧急，持续改善 |
| P3 | 未完成功能存根 | 业务功能，非技术债务 |
| P4-F | 44个端点错误处理 | 工作量大，用 FastAPI exception handler 统一解决 |
| P5 | Docker/部署 | 运维层面，不影响代码质量 |
| P6 | 性能优化 | 需要性能测试数据支撑 |

---

## 验收标准

1. P0 安全漏洞 100% 修复
2. pytest 通过数 ≥ 383 (不退化)
3. 无新增 flake8 错误
4. `docs/TECHNICAL_DEBT.md` 已更新修复状态
