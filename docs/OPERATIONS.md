# 智能知识系统 - 运维手册

本手册面向运维人员，提供系统监控、备份恢复、故障排查等运维操作的详细指南。

---

## 目录

- [运维概述](#运维概述)
- [系统监控](#系统监控)
- [日志管理](#日志管理)
- [备份恢复](#备份恢复)
- [故障排查](#故障排查)
- [性能优化](#性能优化)
- [安全维护](#安全维护)
- [应急响应](#应急响应)

---

## 运维概述

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                │
│                   Web UI / API 客户端                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                       负载均衡                               │
│                       Nginx :8008                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                       应用层                                 │
│                    FastAPI :8001                             │
├─────────────────────────┬───────────────────────────────────┤
│                       │                                       │
┌──────────────▼────┐ ┌──▼──────────┐ ┌──────────────────┐ │
│   PostgreSQL     │ │    Redis     │ │   AI 服务        │ │
│   :5436          │ │    :6381     │ │   (外部 API)     │ │
└───────────────────┘ └─────────────┘ └──────────────────┘ │
                                                          │
┌──────────────────────────────────────────────────────────┤
│                       监控层                               │
│  Prometheus :9090  │  Grafana :3000  │  Exporters       │
└──────────────────────────────────────────────────────────┘
```

### 服务端口

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| Nginx | 8008 | HTTP | Web 入口 |
| API | 8001 | HTTP | API 服务 |
| PostgreSQL | 5436 | TCP | 数据库 |
| Redis | 6381 | TCP | 缓存 |
| Prometheus | 9090 | HTTP | 监控指标 |
| Grafana | 3000 | HTTP | 监控面板 |

### 检查清单

日常运维检查项：

- [ ] 所有服务运行状态
- [ ] 系统健康检查
- [ ] 磁盘空间使用
- [ ] 内存使用情况
- [ ] 错误日志检查
- [ ] 备份完成确认

---

## 系统监控

### Prometheus 监控

#### 访问 Prometheus

```bash
# Web 界面
http://your-server:9090

# 常用查询
# 请求速率
rate(http_requests_total[5m])

# P95 响应时间
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# 错误率
rate(http_requests_total{status=~"5.."}[5m])
```

#### 关键指标

| 指标 | 类型 | 说明 |
|------|------|------|
| http_requests_total | Counter | 总请求数 |
| http_request_duration_seconds | Histogram | 请求耗时 |
| gateway_query_total | Counter | 网关请求数 |
| gateway_query_success | Counter | 成功请求数 |
| gateway_query_error | Counter | 失败请求数 |
| app_startup | Counter | 应用启动次数 |

### Grafana 仪表板

#### 访问 Grafana

```bash
URL: http://your-server:3000
用户名: admin
密码: admin123 (首次登录后请修改)
```

#### 核心仪表板

1. **系统概览** (overview.json)
   - 请求总量和速率
   - 响应时间分布
   - 错误率趋势
   - 服务健康状态

2. **数据库监控**
   - 连接池使用
   - 查询性能
   - 存储增长

3. **缓存监控**
   - 命中率
   - 内存使用
   - 键数量

### 健康检查

#### API 健康检查

```bash
# 基础健康检查
curl http://localhost:8001/health

# 详细健康检查
curl http://localhost:8001/api/v1/health?detailed=true

# 特定组件检查
curl http://localhost:8001/api/v1/health/database
curl http://localhost:8001/api/v1/health/redis
```

#### 健康检查响应

```json
{
  "status": "healthy",
  "timestamp": "2026-03-25T10:30:00",
  "checks": [
    {
      "name": "database",
      "status": "healthy",
      "message": "Connection OK"
    },
    {
      "name": "redis",
      "status": "healthy",
      "message": "Connection OK"
    }
  ]
}
```

#### 脚本化检查

```bash
#!/bin/bash
# scripts/health_check.sh

services=("postgres" "redis" "api" "nginx")
all_healthy=true

for service in "${services[@]}"; do
  if docker-compose ps $service | grep -q "Up"; then
    echo "✓ $service: running"
  else
    echo "✗ $service: NOT running"
    all_healthy=false
  fi
done

# API 健康检查
if curl -s http://localhost:8001/health | grep -q "ok"; then
  echo "✓ API: healthy"
else
  echo "✗ API: unhealthy"
  all_healthy=false
fi

if [ "$all_healthy" = true ]; then
  echo "All systems operational"
  exit 0
else
  echo "Some services need attention"
  exit 1
fi
```

---

## 日志管理

### 日志位置

| 服务 | 日志位置 |
|------|----------|
| API | 容器 stdout |
| Nginx | /var/log/nginx/ |
| PostgreSQL | /var/log/postgresql/ |
| 应用日志 | ./logs/app.log |

### 查看日志

#### Docker 日志

```bash
# 查看所有服务日志
docker-compose logs

# 跟踪日志
docker-compose logs -f

# 查看特定服务
docker-compose logs -f api
docker-compose logs -f postgres

# 查看最近 100 行
docker-compose logs --tail=100 api

# 查看特定时间范围
docker-compose logs --since 2026-03-25T00:00:00 api
```

#### Nginx 日志

```bash
# 访问日志
docker-compose exec nginx tail -f /var/log/nginx/access.log

# 错误日志
docker-compose exec nginx tail -f /var/log/nginx/error.log

# 分析访问日志
docker-compose exec nginx cat /var/log/nginx/access.log | \
  awk '{print $7}' | sort | uniq -c | sort -rn | head -20
```

#### PostgreSQL 日志

```bash
# 查看数据库日志
docker-compose exec postgres tail -f /var/log/postgresql/postgresql.log

# 查看慢查询
docker-compose exec postgres cat /var/log/postgresql/postgresql-slow.log
```

### 日志轮转

配置日志轮转（/etc/logrotate.d/zhineng-kb）：

```
/home/ai/zhineng-knowledge-system/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ai ai
    sharedscripts
    postrotate
        docker-compose exec api kill -USR1 1
    endscript
}
```

### 日志分析

```bash
# 统计错误数量
docker-compose logs api | grep -i error | wc -l

# 查找异常
docker-compose logs api | grep -i "exception\|error\|traceback"

# 分析请求耗时
docker-compose logs api | grep "process_time" | \
  awk -F'process_time=' '{print $2}' | awk '{sum+=$1; count++} END {print "Avg:", sum/count}'
```

---

## 备份恢复

### 备份策略

#### 备份类型

| 类型 | 频率 | 保留期 | 说明 |
|------|------|--------|------|
| 完整备份 | 每天 | 7 天 | 数据库全量备份 |
| 增量备份 | 每小时 | 24 小时 | WAL 归档（可选） |
| 配置备份 | 每周 | 4 周 | 配置文件备份 |

#### 备份位置

- 本地备份目录: `./backups/`
- 远程备份: 配置 rsync 或对象存储

### 执行备份

#### 使用备份脚本

```bash
# 完整备份
./scripts/backup.sh all

# 仅备份数据库
./scripts/backup.sh db

# 仅备份上传文件
./scripts/backup.sh uploads

# 仅备份配置
./scripts/backup.sh config

# 列出备份
./scripts/backup.sh list

# 清理旧备份
./scripts/backup.sh clean
```

#### 手动备份

```bash
# 数据库备份
docker-compose exec -T postgres pg_dump -U zhineng zhineng_kb | \
  gzip > backups/db_manual_$(date +%Y%m%d_%H%M%S).sql.gz

# 配置备份
tar -czf backups/config_$(date +%Y%m%d_%H%M%S).tar.gz \
  docker-compose.yml .env backend/config.py
```

### 自动备份

#### Crontab 配置

```bash
# 编辑 crontab
crontab -e

# 添加以下条目
0 2 * * * cd /home/ai/zhineng-knowledge-system && ./scripts/backup.sh all
0 3 * * 0 cd /home/ai/zhineng-knowledge-system && ./scripts/backup.sh clean
```

### 数据恢复

#### 使用恢复脚本

```bash
# 查看可用备份
ls -lh backups/

# 恢复数据库
./scripts/recover.sh backups/db_20260325_020000.sql.gz

# 或手动恢复
gunzip -c backups/db_20260325_020000.sql.gz | \
  docker-compose exec -T postgres psql -U zhineng zhineng_kb
```

#### 恢复流程

1. **停止应用服务**

```bash
docker-compose stop api nginx
```

2. **恢复数据库**

```bash
gunzip -c backups/db_backup.sql.gz | \
  docker-compose exec -T postgres psql -U zhineng zhineng_kb
```

3. **验证数据**

```bash
docker-compose exec postgres psql -U zhineng zhineng_kb -c \
  "SELECT COUNT(*) FROM documents;"
```

4. **重启服务**

```bash
docker-compose start api nginx
```

---

## 故障排查

### 服务无法启动

#### 问题: 容器启动失败

**排查步骤**:

```bash
# 检查容器状态
docker-compose ps

# 查看日志
docker-compose logs api

# 检查配置
docker-compose config

# 检查端口占用
netstat -tulpn | grep -E ':(8001|5436|6381)'
```

**常见原因**:

| 原因 | 解决方案 |
|------|----------|
| 端口被占用 | 修改 docker-compose.yml 中的端口映射 |
| 配置错误 | 检查 .env 文件配置 |
| 镜像损坏 | 重新构建镜像: `docker-compose build --no-cache` |
| 资源不足 | 检查系统资源，增加限制 |

#### 问题: 数据库连接失败

**排查步骤**:

```bash
# 检查 PostgreSQL 状态
docker-compose ps postgres

# 进入容器测试
docker-compose exec postgres psql -U zhineng -d zhineng_kb

# 检查网络
docker network inspect zhineng-network

# 检查连接
docker-compose exec api env | grep DATABASE_URL
```

**常见原因**:

| 原因 | 解决方案 |
|------|----------|
| 数据库未就绪 | 等待健康检查通过 |
| 连接字符串错误 | 检查 DATABASE_URL 配置 |
| 网络隔离 | 确保容器在同一网络 |
| 资源限制 | 增加 PostgreSQL 内存限制 |

### 性能问题

#### 问题: API 响应慢

**排查步骤**:

```bash
# 检查资源使用
docker stats

# 查看慢查询
docker-compose exec postgres cat /var/log/postgresql/postgresql-slow.log

# 检查缓存命中率
docker-compose exec redis redis-cli -a redis123 INFO stats

# 分析请求日志
docker-compose logs api | grep "process_time" | \
  awk -F'process_time=' '{if ($2 > 1.0) print $0}'
```

**优化方案**:

1. **数据库优化**

```sql
-- 创建索引
CREATE INDEX CONCURRENTLY idx_documents_content_gin ON documents USING gin(to_tsvector('chinese', content));

-- 更新统计信息
ANALYZE documents;

-- 清理死元组
VACUUM ANALYZE documents;
```

2. **缓存优化**

```bash
# 增加缓存
docker-compose exec redis redis-cli -a redis123 CONFIG SET maxmemory 1gb
```

3. **连接池调优**

```python
# config.py
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 10
```

#### 问题: 内存不足

**排查步骤**:

```bash
# 查看内存使用
free -h

# 查看容器内存
docker stats --no-stream

# 查看进程内存
docker-compose exec api ps aux --sort=-%mem | head
```

**解决方案**:

```yaml
# docker-compose.yml
services:
  api:
    mem_limit: 1g
    mem_reservation: 512m
```

### 磁盘空间问题

#### 问题: 磁盘空间不足

**排查步骤**:

```bash
# 检查磁盘使用
df -h

# 查找大文件
find . -type f -size +100M -exec ls -lh {} \;

# Docker 磁盘使用
docker system df
```

**清理方案**:

```bash
# 清理 Docker 资源
docker system prune -a

# 清理旧日志
docker-compose logs api > logs/api_backup.log
docker-compose exec api truncate -s 0 /app/logs/*.log

# 清理备份
./scripts/backup.sh clean
```

---

## 性能优化

### 数据库优化

#### 索引优化

```sql
-- 检查索引使用
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- 创建缺失的索引
CREATE INDEX CONCURRENTLY idx_documents_category_created
ON documents(category, created_at DESC);

-- 向量索引
CREATE INDEX CONCURRENTLY idx_documents_embedding_opt
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = ceil(sqrt(SELECT count(*) FROM documents)));
```

#### 查询优化

```sql
-- 查看慢查询
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- 更新表统计信息
ANALYZE documents;

-- 清理死元组
VACUUM documents;
```

### 应用优化

#### 连接池配置

```python
# backend/config.py
DATABASE_CONFIG = {
    "min_size": 5,
    "max_size": 20,
    "max_queries": 50000,
    "max_inactive_connection_lifetime": 300,
}
```

#### 缓存策略

```python
# backend/cache/manager.py
CACHE_CONFIG = {
    "document_ttl": 3600,      # 文档缓存 1 小时
    "search_ttl": 300,         # 搜索结果 5 分钟
    "embedding_ttl": 86400,    # 嵌入向量 24 小时
    "max_size": 10000,         # 最大缓存项
}
```

### Nginx 优化

```nginx
# nginx/nginx.conf
worker_processes auto;
worker_connections 2048;

# 启用缓存
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=1g;

location /api/v1/documents {
    proxy_cache api_cache;
    proxy_cache_valid 200 5m;
    proxy_pass http://zhineng-api:8000;
}
```

---

## 安全维护

### 密码管理

#### 定期更换密码

```bash
# 生成新密码
openssl rand -base64 32

# 更新 .env 文件
POSTGRES_PASSWORD=new_password_here
REDIS_PASSWORD=new_password_here

# 重启服务
docker-compose up -d postgres redis
```

#### 密码策略

- 最小长度: 16 字符
- 包含大小写字母、数字、特殊字符
- 每 90 天更换一次
- 不重复使用最近 5 次的密码

### 证书管理

#### TLS 证书更新

```bash
# 使用 Let's Encrypt
certbot certonly --webroot -w /var/www/html -d yourdomain.com

# 复制证书
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/

# 重启 Nginx
docker-compose restart nginx
```

### 安全加固

#### 系统加固

```bash
# 更新系统
apt update && apt upgrade -y

# 配置防火墙
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# 禁用 root 登录
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd
```

#### 容器安全

```yaml
# docker-compose.yml
services:
  api:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

---

## 应急响应

### 故障等级

| 等级 | 描述 | 响应时间 |
|------|------|----------|
| P0 | 系统完全不可用 | 15 分钟 |
| P1 | 核心功能受影响 | 1 小时 |
| P2 | 部分功能异常 | 4 小时 |
| P3 | 轻微问题 | 1 天 |

### 应急流程

#### 1. 故障发现

```bash
# 检查告警
curl http://localhost:8001/api/v1/health?detailed=true

# 查看监控
# 访问 Grafana 仪表板
```

#### 2. 初步评估

```bash
# 确认影响范围
docker-compose ps
docker-compose logs --tail=50

# 记录当前状态
./scripts/snapshot.sh
```

#### 3. 临时修复

```bash
# 重启问题服务
docker-compose restart api

# 回滚到上一版本
git checkout HEAD~1
docker-compose up -d --build api
```

#### 4. 根本分析

```bash
# 收集日志
docker-compose logs api > logs/failure_$(date +%Y%m%d_%H%M%S).log

# 分析问题
./scripts/analyze_failure.sh
```

#### 5. 永久修复

```bash
# 实施修复
# 更新代码
# 测试验证
# 部署上线
```

### 紧急联系方式

| 角色 | 联系方式 |
|------|----------|
| 运维负责人 | ops@example.com |
| 技术负责人 | tech@example.com |
| 管理层 | management@example.com |

---

## 附录

### 常用命令

```bash
# 服务管理
docker-compose up -d          # 启动服务
docker-compose down           # 停止服务
docker-compose restart        # 重启服务
docker-compose ps             # 查看状态

# 日志查看
docker-compose logs -f api    # 跟踪日志
docker-compose logs --tail=100 api  # 最近 100 行

# 进入容器
docker-compose exec api bash
docker-compose exec postgres psql -U zhineng zhineng_kb

# 资源清理
docker system prune -a        # 清理未使用资源
docker volume prune           # 清理未使用卷

# 备份恢复
./scripts/backup.sh all       # 备份
./scripts/recover.sh backup   # 恢复
```

### 监控命令

```bash
# 系统资源
htop                          # CPU/内存
iotop                        # 磁盘 I/O
netstat -tulpn               # 网络连接

# Docker 资源
docker stats                 # 容器资源
docker top <container>       # 容器进程

# 应用指标
curl http://localhost:8001/api/v1/stats      # 统计信息
curl http://localhost:8001/api/v1/health     # 健康检查
curl http://localhost:8001/api/v1/metrics    # Prometheus 指标
```

---

**版本**: 1.0.0
**更新日期**: 2026-03-25
**维护者**: 运维团队
