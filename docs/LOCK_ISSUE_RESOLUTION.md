# 数据库锁死问题总结

## 问题现象

执行古籍数据导入时，多个进程导致数据库表锁死：

```
PID    │ 操作                           │ 锁类型  │ 等待
────────┼────────────────────────────────┼─────────┼──────
158759 │ INSERT ... ON CONFLICT         │ IO      │ 5 35
159654 │ TRUNCATE guji_documents        │ Lock    │ 34 49
160248 │ SELECT COUNT(*)                │ Lock    │ 22 48
```

## 根本原因

1. **多进程并发竞争**
   - 同时启动了多个导入脚本
   - 没有进程互斥机制

2. **长事务持有锁**
   - 使用单个事务处理大量数据
   - 锁持有时间过长

3. **锁冲突操作顺序不当**
   - TRUNCATE 需要 ACCESS EXCLUSIVE 锁
   - 与 INSERT/CREATE INDEX 冲突

## 解决方案

### 1. 导入管理器 (`backend/services/import_manager.py`)

**功能:**
- 文件锁机制防止多进程并发
- 数据库任务注册表跟踪运行状态
- 信号处理确保资源清理
- 自动超时和回滚

**使用方法:**
```python
async with ImportManager("guji_import") as mgr:
    conn = mgr.conn
    # 执行导入
```

### 2. 安全导入脚本 (`scripts/import_guji_safe.py`)

**改进:**
- 小事务批量提交 (2000条/批)
- ON CONFLICT DO NOTHING 避免冲突
- 独立事务，每批提交后释放锁
- 详细的进度日志

### 3. 防范措施总结

| 措施 | 实现方式 |
|------|----------|
| 进程互斥 | 文件锁 (fcntl) + 数据库任务表 |
| 事务控制 | 小批量提交，避免长事务 |
| 超时处理 | lock_timeout=5s, statement_timeout=300s |
| 资源清理 | 信号处理器 (SIGTERM/SIGINT) |
| 状态跟踪 | import_tasks 表记录任务状态 |

## 后续步骤

1. 所有批量导入脚本改用 `ImportManager`
2. 设置定时清理过期锁文件
3. 监控长时间运行的事务
4. 建立导入任务优先级队列

## 验证

运行新的安全导入脚本：
```bash
python scripts/import_guji_safe.py
```

如果遇到锁冲突，会提示：
```
导入失败: 任务 guji_import 已在运行
锁信息: /tmp/zhineng_imports/guji_import.lock
```

强制解锁：
```bash
python backend/services/import_manager.py guji_import --force-unlock
```
