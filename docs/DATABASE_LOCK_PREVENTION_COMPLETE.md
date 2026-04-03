# 数据库锁死防范系统 - 完整方案

**版本**: v2.0
**日期**: 2026-04-02
**状态**: ✅ 已部署

---

## 📋 问题背景

### 历史事故 (2026-04-02)

6个进程并发导致数据库锁死：

```
PID    │ 操作                           │ 状态
────────┼────────────────────────────────┼────────────────────
158759 │ INSERT ... ON CONFLICT         │ 等待 IO (5-35秒)
159654 │ TRUNCATE guji_documents        │ 持有锁，等待 INSERT
160248 │ SELECT COUNT(*)                │ 等待 TRUNCATE
160317 │ SELECT pg_size_pretty()        │ 等待 TRUNCATE
160569 │ CREATE INDEX                   │ 等待 TRUNCATE
161352 │ DROP TABLE + CREATE TABLE      │ 持有锁
```

**锁链**: DROP → TRUNCATE → [SELECT, CREATE INDEX] → INSERT → IO

---

## 🛡️ 防范系统组件

### 1. ImportManager (核心)

**位置**: `backend/services/import_manager.py`

**功能**:
- 文件锁机制 (fcntl)
- 数据库任务注册表
- 信号处理 (SIGTERM/SIGINT)
- 自动超时 (lock_timeout=5s)

**使用方式**:
```python
from backend.services.import_manager import ImportManager

async with ImportManager("task_name") as mgr:
    conn = mgr.conn
    # 执行导入操作
```

### 2. 统一导入门卫

**位置**: `scripts/import_guard.py`

**功能**:
- 所有导入操作的统一入口
- 自动应用 ImportManager
- 任务状态查询
- 强制解锁功能

**使用方式**:
```bash
# 运行导入
python scripts/import_guard.py guji

# 查看状态
python scripts/import_guard.py --status

# 强制解锁
python scripts/import_guard.py --unlock guji
```

### 3. 锁监控工具

**位置**: `scripts/db_lock_monitor.py`

**功能**:
- 实时监控文件锁和数据库锁
- 检测阻塞查询
- 自动清理过期锁
- 终止僵死进程

**使用方式**:
```bash
# 检查状态
python scripts/db_lock_monitor.py

# 持续监控
python scripts/db_lock_monitor.py --watch --interval 5

# 清理过期锁
python scripts/db_lock_monitor.py --clean

# 终止所有导入进程
python scripts/db_lock_monitor.py --kill
```

### 4. 快速诊断工具

**位置**: `scripts/diagnose_locks.py`

**功能**:
- 一键诊断所有锁问题
- 自动修复建议
- 分类显示问题

**使用方式**:
```bash
# 快速诊断
python scripts/diagnose_locks.py

# 自动修复
python scripts/diagnose_locks.py --fix
```

### 5. Pre-commit Hook

**位置**: `.pre-commit-config.yaml`

**功能**:
- 检查导入脚本是否使用 ImportManager
- 提交前自动拦截不安全的脚本

**检查脚本**: `scripts/check_import_safety.py`

---

## 📊 防范机制流程图

```
用户启动导入
    │
    ▼
[import_guard.py] 统一入口
    │
    ▼
[ImportManager] 获取文件锁
    │
    ├── 失败 → 抛出 ImportLockError ❌
    │
    ▼ 成功
[检查数据库锁表]
    │
    ├── 已有运行 → 抛出异常 ❌
    │
    ▼ 无冲突
[注册任务到数据库]
    │
    ▼
[设置超时参数]
    │   ├─ lock_timeout = 5s
    │   └─ statement_timeout = 300s
    │
    ▼
[执行导入]
    │
    ▼
[信号处理] SIGTERM/SIGINT
    │
    ▼
[清理资源]
    │   ├─ 完成数据库任务
    │   └─ 释放文件锁
    │
    ▼
✅ 完成
```

---

## 🚨 应急处理流程

### 发现锁死的处理步骤

```bash
# 1. 快速诊断
python scripts/diagnose_locks.py

# 2. 查看详细状态
python scripts/db_lock_monitor.py

# 3. 尝试自动清理
python scripts/db_lock_monitor.py --clean

# 4. 如果无效，手动终止进程
python scripts/db_lock_monitor.py --kill

# 5. 强制解锁特定任务
python scripts/import_guard.py --unlock task_name

# 6. 最后手段：手动清理
rm -f /tmp/zhineng_imports/*.lock
docker exec zhineng-postgres psql -U zhineng -d zhineng_kb \
  -c "UPDATE import_locks SET status='killed' WHERE status='running';"
```

---

## 📖 开发规范

### 强制规则

1. **所有导入脚本必须使用 ImportManager**
   ```python
   # ✅ 正确
   from backend.services.import_manager import ImportManager

   async def main():
       async with ImportManager("my_import") as mgr:
           # 导入逻辑
           pass

   # ❌ 错误 - 直接运行
   async def main():
       conn = await asyncpg.connect(DATABASE_URL)
       # 导入逻辑
   ```

2. **使用统一入口运行导入**
   ```bash
   # ✅ 正确
   python scripts/import_guard.py guji

   # ❌ 错误 - 直接运行脚本可能绕过保护
   python scripts/import_guji_data.py
   ```

3. **批量操作分批提交**
   ```python
   # ✅ 正确 - 小事务
   batch_size = 1000
   for i in range(0, len(rows), batch_size):
       async with conn.transaction():
           await conn.executemany(query, rows[i:i+batch_size])

   # ❌ 错误 - 大事务
   async with conn.transaction():
       for row in all_100k_rows:
           await conn.execute(...)
   ```

---

## 📈 监控指标

| 指标 | 阈值 | 处理 |
|------|------|------|
| 锁等待时间 | > 5秒 | 检查阻塞 |
| 事务运行时间 | > 5分钟 | 检查长事务 |
| 锁文件存在 | > 1小时 | 清理过期锁 |
| 并发导入数 | > 1 | 拒绝启动 |

---

## 🧪 验证测试

```bash
# 1. 测试并发拒绝
# 终端1
python scripts/import_guard.py test_task &
# 终端2 - 应该被拒绝
python scripts/import_guard.py test_task

# 2. 测试锁监控
python scripts/db_lock_monitor.py

# 3. 测试自动清理
python scripts/diagnose_locks.py --fix

# 4. 测试 pre-commit hook
# 修改一个导入脚本，移除 ImportManager，然后提交
git add scripts/test_import.py
git commit -m "test"  # 应该被拦截
```

---

## 📚 相关文档

- [DATABASE_LOCK_PREVENTION.md](DATABASE_LOCK_PREVENTION.md) - 原始问题分析
- [DEVELOPMENT_RULES.md](../DEVELOPMENT_RULES.md#7-安全规范) - 开发规范
- [backend/services/import_manager.py](../backend/services/import_manager.py) - 核心实现

---

**维护者**: AI Agent
**最后更新**: 2026-04-02
