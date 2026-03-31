# 生产环境配置与长期预防方案

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**创建时间**: 2026-03-30 21:50
**目标**: 杜绝 WatchFiles 热重载导致的线程累积和数据库膨胀问题

---

## 📋 问题根源回顾

### 原始问题
1. **WatchFiles 热重载** (--reload) 导致应用频繁重启
2. **进程累积**: 旧进程未正确关闭，僵尸进程堆积
3. **线程暴增**: 200+ 线程同时访问 openlist
4. **数据库膨胀**: openlist 重复索引 + WAL 未清理

---

## 🛠️ 立即修复（已完成）

### ✅ 1. 禁用热重载
```yaml
# docker-compose.yml
api:
  command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
  environment:
    ENVIRONMENT: production  # 标记为生产环境
```

**效果**:
- ✅ 不再自动重启
- ✅ 使用 2 个 worker 进程（更稳定）
- ✅ 清理了僵尸进程

---

### ⏳ 2. openlist 数据库优化

**手动执行脚本**（需要 root 权限）:
```bash
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_db.sh
```

**效果**:
- 预计释放 10-30GB 空间
- 清理 WAL 文件
- 重建数据库索引

---

## 🏗️ 生产环境最佳实践

### 方案 1: 使用 Gunicorn + Uvicorn Workers（推荐）⭐⭐⭐⭐⭐

**优点**:
- 进程管理更稳定
- 自动重启崩溃的 worker
- 更好的资源利用
- 生产环境标准配置

**配置**:

#### 1. 创建生产环境 Dockerfile

```dockerfile
# Dockerfile.production
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 生产环境启动命令（使用 gunicorn）
CMD ["gunicorn", "main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
```

#### 2. 创建生产环境 docker-compose 配置

```yaml
# docker-compose.production.yml
version: "3.8"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile.production
    container_name: zhineng-api-prod
    environment:
      PYTHONPATH: /app
      DATABASE_URL: postgresql://zhineng:${POSTGRES_PASSWORD:-zhineng123}@postgres:5432/zhineng_kb
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
      API_HOST: 0.0.0.0
      API_PORT: 8000
      LOG_LEVEL: INFO
      ENVIRONMENT: production
    # 不要挂载 backend 目录到容器中！
    # volumes:
    #   - ./backend:/app/backend  # ❌ 移除这行
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always  # 使用 always 而不是 unless-stopped
    networks:
      - zhineng-network
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
```

#### 3. 启动生产环境

```bash
# 使用生产环境配置
docker-compose -f docker-compose.production.yml up -d

# 查看日志
docker-compose -f docker-compose.production.yml logs -f api

# 查看进程状态
docker exec zhineng-api-prod ps aux
```

---

### 方案 2: 使用 Systemd 管理（适合主机部署）⭐⭐⭐⭐

**优点**:
- 系统级进程管理
- 自动重启
- 日志管理
- 开机自启

**配置**:

#### 1. 创建 systemd 服务文件

```ini
# /etc/systemd/system/zhineng-api.service
[Unit]
Description=Zhineng Knowledge System API
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=zhineng
Group=zhineng
WorkingDirectory=/home/ai/zhineng-knowledge-system
Environment="PATH=/home/ai/zhineng-knowledge-system/venv/bin"
Environment="PYTHONPATH=/home/ai/zhineng-knowledge-system/backend"
EnvironmentFile=/home/ai/zhineng-knowledge-system/.env.prod

# 使用 gunicorn 启动
ExecStart=/home/ai/zhineng-knowledge-system/venv/bin/gunicorn \
    main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile /var/log/zhineng/api/access.log \
    --error-logfile /var/log/zhineng/api/error.log \
    --log-level info

# 重启策略
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitInterval=60

# 资源限制
MemoryMax=2G
CPUQuota=200%

# 日志
StandardOutput=append:/var/log/zhineng/api/systemd.log
StandardError=append:/var/log/zhineng/api/systemd.error.log

[Install]
WantedBy=multi-user.target
```

#### 2. 创建日志目录

```bash
sudo mkdir -p /var/log/zhineng/api
sudo chown zhineng:zhineng /var/log/zhineng/api
sudo chmod 755 /var/log/zhineng/api
```

#### 3. 启用并启动服务

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable zhineng-api

# 启动服务
sudo systemctl start zhineng-api

# 查看状态
sudo systemctl status zhineng-api

# 查看日志
sudo journalctl -u zhineng-api -f
```

---

### 方案 3: 开发/生产环境分离⭐⭐⭐⭐⭐

**目录结构**:
```
/home/ai/zhineng-knowledge-system/
├── docker-compose.yml                 # 开发环境（默认）
├── docker-compose.production.yml      # 生产环境
├── docker-compose.staging.yml         # 预发布环境
├── backend/
│   ├── Dockerfile                     # 开发环境 Dockerfile
│   ├── Dockerfile.production          # 生产环境 Dockerfile
│   └── config/
│       ├── development.py             # 开发环境配置
│       ├── production.py              # 生产环境配置
│       └── staging.py                 # 预发布环境配置
```

**使用方法**:
```bash
# 开发环境（使用 --reload）
docker-compose up -d

# 生产环境
docker-compose -f docker-compose.production.yml up -d

# 预发布环境
docker-compose -f docker-compose.staging.yml up -d
```

---

## 📊 监控与告警

### 1. 进程监控

```python
# backend/monitoring/process_monitor.py
import psutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ProcessMonitor:
    """进程监控器"""

    def __init__(self, max_zombie_processes: int = 5):
        self.max_zombie_processes = max_zombie_processes
        self.current_process = psutil.Process()

    def check_zombie_processes(self) -> dict:
        """检查僵尸进程"""
        try:
            children = self.current_process.children(recursive=True)
            zombie_count = 0

            for child in children:
                try:
                    if child.status() == psutil.STATUS_ZOMBIE:
                        zombie_count += 1
                        logger.warning(f"僵尸进程检测: PID {child.pid}")
                except psutil.NoSuchProcess:
                    pass

            result = {
                "zombie_count": zombie_count,
                "total_children": len(children),
                "threshold_exceeded": zombie_count > self.max_zombie_processes
            }

            if result["threshold_exceeded"]:
                logger.error(f"僵尸进程数量超过阈值: {zombie_count} > {self.max_zombie_processes}")
                # 发送告警

            return result

        except Exception as e:
            logger.error(f"检查僵尸进程失败: {e}")
            return {"error": str(e)}

    def check_thread_count(self) -> dict:
        """检查线程数量"""
        try:
            thread_count = self.current_process.num_threads()
            children = self.current_process.children(recursive=True)

            total_threads = thread_count + sum(
                child.num_threads() for child in children
                if child.is_running()
            )

            result = {
                "main_threads": thread_count,
                "total_threads": total_threads,
                "children_count": len(children)
            }

            if total_threads > 200:
                logger.error(f"线程数量异常: {total_threads} > 200")
                # 发送告警

            return result

        except Exception as e:
            logger.error(f"检查线程数量失败: {e}")
            return {"error": str(e)}

# 定期检查
async def periodic_process_check(interval: int = 300):
    """定期进程检查"""
    monitor = ProcessMonitor()

    while True:
        try:
            zombie_result = monitor.check_zombie_processes()
            thread_result = monitor.check_thread_count()

            logger.info(f"进程监控: 僵尸={zombie_result.get('zombie_count', 0)}, "
                       f"线程={thread_result.get('total_threads', 0)}")

        except Exception as e:
            logger.error(f"进程监控失败: {e}")

        await asyncio.sleep(interval)
```

### 2. 数据库监控

```python
# backend/monitoring/database_monitor.py
import asyncpg
import logging

logger = logging.getLogger(__name__)

class DatabaseMonitor:
    """数据库监控器"""

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def check_connection_count(self) -> dict:
        """检查数据库连接数"""
        try:
            conn = await asyncpg.connect(self.db_url)

            # 查询连接数
            result = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state = 'active'
            """)

            await conn.close()

            if result > 100:
                logger.warning(f"数据库连接数过高: {result} > 100")

            return {"connection_count": result}

        except Exception as e:
            logger.error(f"检查数据库连接数失败: {e}")
            return {"error": str(e)}

    async def check_long_running_queries(self) -> dict:
        """检查长时间运行的查询"""
        try:
            conn = await asyncpg.connect(self.db_url)

            # 查询运行时间超过 60 秒的查询
            result = await conn.fetch("""
                SELECT pid, now() - query_start as duration, query
                FROM pg_stat_activity
                WHERE state = 'active'
                AND now() - query_start > interval '60 seconds'
                ORDER BY duration DESC
            """)

            await conn.close()

            if result:
                logger.warning(f"发现 {len(result)} 个长时间运行的查询")

            return {"long_queries": len(result), "queries": result}

        except Exception as e:
            logger.error(f"检查长时间运行的查询失败: {e}")
            return {"error": str(e)}
```

### 3. openlist 监控

```bash
#!/bin/bash
# scripts/monitor_openlist.sh

# openlist 数据库监控脚本

DB_FILE="/opt/openlist/data/data.db"
MAX_SIZE_GB=70

while true; do
    # 检查数据库大小
    DB_SIZE_BYTES=$(du -sb "$DB_FILE" 2>/dev/null | cut -f1)
    DB_SIZE_GB=$((DB_SIZE_BYTES / 1024 / 1024 / 1024))

    echo "[$(date)] openlist 数据库大小: ${DB_SIZE_GB}GB"

    if [ $DB_SIZE_GB -gt $MAX_SIZE_GB ]; then
        echo "[$(date)] ⚠️  openlist 数据库超过阈值: ${DB_SIZE_GB}GB > ${MAX_SIZE_GB}GB"

        # 发送告警（示例：写入 syslog）
        logger -p local0.warning "openlist database size exceeded: ${DB_SIZE_GB}GB"

        # 可以在这里触发自动清理
        # /path/to/optimize_openlist_db.sh
    fi

    # 检查服务状态
    if ! systemctl is-active --quiet openlist; then
        echo "[$(date)] ❌ openlist 服务未运行"
        logger -p local0.error "openlist service is not running"
    fi

    sleep 3600  # 每小时检查一次
done
```

---

## 📝 配置管理

### 环境变量管理

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING

# 数据库配置
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# Redis 配置
REDIS_POOL_SIZE=20
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# 安全配置
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=your-domain.com
CORS_ORIGINS=https://your-domain.com

# openlist 配置
OPENLIST_SCAN_INTERVAL=86400  # 24 小时扫描一次
OPENLIST_ENABLE_WATCH=false   # 禁用文件监控
```

### 配置验证

```python
# backend/config/validation.py
from pydantic import Field, validator
from typing import List

class ProductionConfig(BaseSettings):
    """生产环境配置"""

    ENVIRONMENT: str = Field("production", regex="^(production|staging)$")

    # 安全配置
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., min_length=32)
    ALLOWED_HOSTS: List[str] = Field(...)

    # 性能配置
    DATABASE_POOL_SIZE: int = Field(20, ge=10, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(10, ge=5, le=50)

    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = Field(60, ge=10, le=1000)

    @validator('DEBUG')
    def debug_must_be_false_in_production(cls, v, values):
        if values.get('ENVIRONMENT') == 'production' and v:
            raise ValueError('DEBUG must be False in production')
        return v

    @validator('SECRET_KEY')
    def secret_key_must_be_secure(cls, v):
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters')
        if v == 'change-me':
            raise ValueError('SECRET_KEY must be changed in production')
        return v
```

---

## 🔄 CI/CD 集成

### 自动化部署流程

```yaml
# .github/workflows/production-deploy.yml
name: Production Deployment

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Build production image
        run: |
          docker build \
            -f backend/Dockerfile.production \
            -t zhineng-api:${{ github.sha }} \
            -t zhineng-api:latest \
            .

      - name: Deploy to production
        run: |
          docker-compose -f docker-compose.production.yml up -d

      - name: Health check
        run: |
          for i in {1..30}; do
            if curl -f http://localhost:8008/health; then
              echo "Health check passed"
              exit 0
            fi
            echo "Waiting for service to be ready... ($i/30)"
            sleep 2
          done
          echo "Health check failed"
          exit 1

      - name: Notify on failure
        if: failure()
        run: |
          # 发送告警通知
          echo "Deployment failed!"
```

---

## 📋 部署检查清单

### 部署前检查

- [ ] 禁用 DEBUG 模式
- [ ] 设置安全的 SECRET_KEY
- [ ] 配置 ALLOWED_HOSTS
- [ ] 配置 CORS origins
- [ ] 禁用 --reload 参数
- [ ] 使用生产级启动命令（gunicorn）
- [ ] 配置日志轮转
- [ ] 配置监控和告警
- [ ] 执行数据库备份
- [ ] 执行 openlist VACUUM

### 部署后验证

- [ ] 检查服务状态（systemctl status 或 docker ps）
- [ ] 检查进程数量（ps aux | grep uvicorn）
- [ ] 检查日志（tail -f logs/api.log）
- [ ] 检查健康检查（curl http://localhost:8000/health）
- [ ] 检查数据库连接
- [ ] 检查 openlist 连接
- [ ] 检查监控指标（Prometheus/Grafana）

---

## 🎯 总结

### 已完成的修复

1. ✅ 禁用 WatchFiles 热重载
2. ✅ 使用生产级启动命令（uvicorn --workers 2）
3. ✅ 清理僵尸进程
4. ✅ 修复健康检查错误
5. ✅ 优化单例等待逻辑
6. ✅ 创建 openlist 优化脚本

### 长期预防措施

1. ⏳ 使用 Gunicorn + Uvicorn Workers
2. ⏳ 开发/生产环境配置分离
3. ⏳ 实施进程和数据库监控
4. ⏳ 配置日志轮转和告警
5. ⏳ 建立 CI/CD 流程
6. ⏳ 定期执行 openlist VACUUM

### 下一步行动

**立即执行**（今天）:
```bash
# 执行 openlist 数据库优化
sudo bash /home/ai/zhineng-knowledge-system/scripts/optimize_openlist_db.sh
```

**本周执行**:
1. 实施 Gunicorn + Uvicorn Workers 配置
2. 配置进程监控
3. 设置日志轮转

**下周执行**:
1. 建立 CI/CD 流程
2. 配置告警系统
3. 编写运维文档

---

**文档创建时间**: 2026-03-30 21:50
**维护者**: DevOps Team
**审核者**: Tech Lead
