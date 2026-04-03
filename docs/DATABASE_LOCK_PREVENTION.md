# 数据库锁死问题分析与防范措施

## 问题描述

在导入古籍数据时，多个并发进程导致数据库表锁死，造成以下情况：
- `TRUNCATE` 等待 `INSERT` 释放锁
- `INSERT` 等待 `TRUNCATE` 释放锁
- `CREATE INDEX` 等待 `TRUNCATE` 释放锁
- 互相等待形成死锁

## 根本原因分析

### 1. 多进程并发竞争
```
进程A: import_guji_data.py (后台运行)
进程B: import_guji_fast.py (新启动)
进程C: test_import (测试进程)
进程D: 数据库状态检查进程
```

### 2. 锁冲突操作
| 操作 | 锁类型 | 冲突操作 |
|------|--------|----------|
| TRUNCATE | ACCESS EXCLUSIVE | 所有DML/DDL |
| INSERT (批量) | ROW EXCLUSIVE | TRUNCATE, DROP |
| CREATE INDEX | SHARE | TRUNCATE, DROP |
| SELECT COUNT | ACCESS SHARE | TRUNCATE, DROP |

### 3. 代码设计问题
1. **没有进程互斥机制** - 多个导入脚本可以同时运行
2. **长时间事务** - 批量插入在单个事务中，锁持有时间过长
3. **缺乏超时处理** - 进程没有设置锁等待超时
4. **资源清理不彻底** - 失败的进程没有自动清理

## 防范措施

### 1. 进程互斥机制

```python
# 添加进程锁
import fcntl
import pathlib

def acquire_process_lock(name: str):
    """获取进程锁，防止并发运行"""
    lock_file = pathlib.Path(f"/tmp/{name}.lock")

    try:
        fd = lock_file.open('w')
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        return fd
    except IOError:
        raise RuntimeError(f"另一个 {name} 进程正在运行")

# 使用
with acquire_process_lock("guji_import"):
    # 执行导入逻辑
    pass
```

### 2. 数据库连接超时设置

```python
# 设置锁等待超时
await conn.execute("SET statement_timeout = '300s';")
await conn.execute("SET lock_timeout = '10s';")

# 如果获取锁超时，自动回滚并退出
try:
    async with conn.transaction():
        # 操作
        pass
except asyncpg.DeadlockDetectedError:
    logger.error("检测到死锁，正在回退...")
    raise
except asyncpg.LockNotAvailableError:
    logger.error("无法获取锁，可能有其他进程在运行")
    raise
```

### 3. 小事务批量提交

```python
# 错误做法 - 大事务
async with conn.transaction():
    for row in all_100k_rows:
        await conn.execute(...)

# 正确做法 - 小事务批量提交
batch_size = 1000
for i in range(0, len(all_rows), batch_size):
    batch = all_rows[i:i+batch_size]
    async with conn.transaction():
        await conn.executemany(query, batch)
    # 每批提交一次，释放锁
```

### 4. 进程健康检查和自动清理

```python
import signal
import atexit

class ImportProcess:
    def __init__(self):
        self.should_stop = False
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        atexit.register(self._cleanup)

    def _handle_sigterm(self, signum, frame):
        logger.info("收到终止信号，正在清理...")
        self.should_stop = True

    def _cleanup(self):
        # 清理资源
        pass

    def run(self):
        while not self.should_stop:
            # 执行操作
            pass
```

### 5. 导入任务管理表

```sql
-- 创建导入任务表
CREATE TABLE import_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL,  -- running, completed, failed
    pid INTEGER,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

-- 启动任务时检查
INSERT INTO import_tasks (task_name, status, pid)
VALUES ('guji_import', 'running', $1)
ON CONFLICT (task_name) DO UPDATE SET
    status = 'running',
    pid = EXCLUDED.pid,
    started_at = NOW()
WHERE status != 'running';

-- 如果没有插入/更新（状态为running），说明有其他进程在运行
```

### 6. 统一导入入口点

```python
# scripts/import_manager.py
class ImportManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.lock_file = None

    def __enter__(self):
        # 1. 检查文件锁
        self.lock_file = self._acquire_lock()

        # 2. 检查数据库锁
        conn = await asyncpg.connect(self.database_url)
        self._check_existing_imports(conn)
        await conn.close()

        # 3. 注册导入任务
        self._register_import_task()

        return self

    def __exit__(self, *args):
        # 清理资源
        self._release_lock()
        self._complete_import_task()
```

## 立即行动项

1. **杀死所有竞争进程** ✓
2. **实现进程锁机制**
3. **修改导入脚本使用小事务**
4. **添加超时和错误处理**
5. **创建统一导入管理器**

## 修改后的导入脚本结构

```python
import fcntl
import signal
import sys
from pathlib import Path

class SafeImportProcess:
    def __init__(self, task_name: str):
        self.task_name = task_name
        self.lock_file = None
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGTERM, self._cleanup)
        signal.signal(signal.SIGINT, self._cleanup)

    def acquire_lock(self):
        lock_path = Path(f"/tmp/{self.task_name}.lock")
        self.lock_file = lock_path.open('w')
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise RuntimeError(f"进程 {self.task_name} 已在运行")

    def _cleanup(self, signum=None, frame=None):
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
        sys.exit(0)

# 使用示例
def main():
    process = SafeImportProcess("guji_import")
    process.acquire_lock()

    asyncio.run(do_import())

if __name__ == "__main__":
    main()
```
