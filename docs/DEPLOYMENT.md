# 智能知识系统 - 部署指南

本文档提供智能知识系统的完整部署指南，支持 Docker Compose 和 Kubernetes 两种部署方式。

---

## 目录

- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [Docker Compose 部署](#docker-compose-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [环境配置](#环境配置)
- [监控配置](#监控配置)
- [生产环境建议](#生产环境建议)
- [故障排查](#故障排查)

---

## 系统要求

### 最低配置

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 20 GB | 50 GB+ SSD |
| 操作系统 | Linux/macOS | Ubuntu 22.04 LTS |
| Docker | 20.10+ | 24.0+ |
| Docker Compose | 2.0+ | 2.20+ |

### 软件依赖

```bash
# Docker
docker --version  # >= 20.10

# Docker Compose
docker-compose --version  # >= 2.0
# 或
docker compose version

# Kubernetes (可选)
kubectl version --client  # >= 1.25
```

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-org/zhineng-knowledge-system.git
cd zhineng-knowledge-system
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置必要的参数
```

### 3. 启动服务

```bash
# 使用部署脚本
./scripts/deploy.sh start

# 或直接使用 Docker Compose
docker-compose up -d
```

### 4. 验证部署

```bash
# 健康检查
curl http://localhost:8001/health

# 访问 Web 界面
open http://localhost:8008

# 访问 API 文档
open http://localhost:8001/docs
```

---

## Docker Compose 部署

### 服务架构

```
┌─────────────────────────────────────────────────────────┐
│                       Nginx                             │
│                      :8008                              │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────┐
│                    API Gateway                          │
│                      :8001                              │
└─────┬─────────┬─────────┬─────────┬─────────┬──────────┘
      │         │         │         │         │
┌─────▼───┐ ┌──▼────┐ ┌──▼────┐ ┌──▼─────┐ ┌─▼─────┐
│Postgres │ │ Redis │ │Prometheus│ │Grafana│ │Exporters│
│ :5436   │ │ :6381 │ │ :9090    │ │ :3000 │ │         │
└─────────┘ └───────┘ └──────────┘ └───────┘ └─────────┘
```

### 完整部署步骤

#### 1. 准备配置文件

创建 `.env` 文件：

```bash
# 数据库配置
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_USER=zhineng
POSTGRES_DB=zhineng_kb

# Redis 配置
REDIS_PASSWORD=your_redis_password_here

# API 配置
API_PORT=8000
LOG_LEVEL=INFO

# AI API 配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_URL=https://api.deepseek.com/v1

# 监控配置
GRAFANA_ADMIN_PASSWORD=your_grafana_password
```

#### 2. 启动核心服务

```bash
# 启动数据库和缓存
docker-compose up -d postgres redis

# 等待数据库初始化
sleep 10

# 启动 API 服务
docker-compose up -d api

# 启动前端服务
docker-compose up -d nginx
```

#### 3. 启动监控服务

```bash
# 启动 Prometheus
docker-compose up -d prometheus

# 启动 Grafana
docker-compose up -d grafana

# 启动 Exporters
docker-compose up -d redis-exporter postgres-exporter
```

#### 4. 验证服务状态

```bash
# 检查所有容器
docker-compose ps

# 查看日志
docker-compose logs -f api

# 执行健康检查
./scripts/deploy.sh health
```

### 使用部署脚本

```bash
# 环境检查
./scripts/deploy.sh check

# 构建镜像
./scripts/deploy.sh build

# 启动服务
./scripts/deploy.sh start

# 停止服务
./scripts/deploy.sh stop

# 重启服务
./scripts/deploy.sh restart

# 查看状态
./scripts/deploy.sh status

# 查看日志
./scripts/deploy.sh logs [service]

# 健康检查
./scripts/deploy.sh health
```

### 数据持久化

Docker Compose 默认使用命名卷进行数据持久化：

```yaml
volumes:
  postgres_data:    # PostgreSQL 数据
  redis_data:       # Redis 数据
  prometheus_data:  # Prometheus 指标
  grafana_data:     # Grafana 配置和仪表板
```

备份和恢复：

```bash
# 备份
./scripts/backup.sh all

# 恢复
./scripts/recover.sh backup_file
```

---

## Kubernetes 部署

### 准备 K8s 清单文件

#### 1. 命名空间

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: zhineng-kb
```

#### 2. ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: zhineng-config
  namespace: zhineng-kb
data:
  LOG_LEVEL: "INFO"
  API_PORT: "8000"
  POSTGRES_HOST: "postgres-service"
  POSTGRES_PORT: "5432"
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
```

#### 3. Secret

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: zhineng-secret
  namespace: zhineng-kb
type: Opaque
data:
  POSTGRES_PASSWORD: <base64-encoded-password>
  REDIS_PASSWORD: <base64-encoded-password>
  DEEPSEEK_API_KEY: <base64-encoded-api-key>
```

生成 base64 编码：

```bash
echo -n "your_password" | base64
```

#### 4. PostgreSQL 部署

```yaml
# k8s/postgres.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: zhineng-kb
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: pgvector/pgvector:pg16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          value: "zhineng"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zhineng-secret
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          value: "zhineng_kb"
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        volumeMounts:
        - name: init-sql
          mountPath: /docker-entrypoint-initdb.d
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
      - name: init-sql
        configMap:
          name: init-sql-config
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: zhineng-kb
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: zhineng-kb
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

#### 5. Redis 部署

```yaml
# k8s/redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: zhineng-kb
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        args:
        - redis-server
        - --requirepass
        - $(REDIS_PASSWORD)
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: zhineng-secret
              key: REDIS_PASSWORD
        volumeMounts:
        - name: redis-storage
          mountPath: /data
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: zhineng-kb
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: zhineng-kb
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
```

#### 6. API 服务部署

```yaml
# k8s/api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: zhineng-kb
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: zhineng-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: "postgresql://zhineng:$(POSTGRES_PASSWORD)@postgres-service:5432/zhineng_kb"
        - name: REDIS_URL
          value: "redis://:$(REDIS_PASSWORD)@redis-service:6379/0"
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: zhineng-config
              key: LOG_LEVEL
        envFrom:
        - secretRef:
            name: zhineng-secret
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: zhineng-kb
spec:
  selector:
    app: api
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: zhineng-kb
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: api-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8000
```

#### 7. HPA (Horizontal Pod Autoscaler)

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: zhineng-kb
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### K8s 部署命令

```bash
# 创建命名空间
kubectl apply -f k8s/namespace.yaml

# 创建配置和密钥
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 部署数据库
kubectl apply -f k8s/postgres.yaml

# 部署缓存
kubectl apply -f k8s/redis.yaml

# 等待就绪
kubectl wait --for=condition=ready pod -l app=postgres -n zhineng-kb --timeout=60s
kubectl wait --for=condition=ready pod -l app=redis -n zhineng-kb --timeout=60s

# 部署 API 服务
kubectl apply -f k8s/api.yaml

# 配置自动扩缩容
kubectl apply -f k8s/hpa.yaml

# 查看状态
kubectl get all -n zhineng-kb

# 查看日志
kubectl logs -f deployment/api -n zhineng-kb
```

### 使用 Helm 部署

创建 Helm Chart：

```bash
# 创建 Chart 结构
helm create zhineng-kb

# 编辑 values.yaml
cat > zhineng-kb/values.yaml << EOF
replicaCount: 3

image:
  repository: zhineng-api
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8000

resources:
  limits:
    cpu: 500m
    memory: 1Gi
  requests:
    cpu: 250m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

postgres:
  enabled: true
  persistence:
    size: 10Gi

redis:
  enabled: true
  persistence:
    size: 2Gi
EOF

# 部署
helm install zhineng-kb ./zhineng-kb -n zhineng-kb --create-namespace

# 升级
helm upgrade zhineng-kb ./zhineng-kb -n zhineng-kb

# 回滚
helm rollback zhineng-kb -n zhineng-kb
```

---

## 环境配置

### 核心环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| DATABASE_URL | PostgreSQL 连接字符串 | - | 是 |
| REDIS_URL | Redis 连接字符串 | - | 是 |
| API_HOST | API 监听地址 | 0.0.0.0 | 否 |
| API_PORT | API 监听端口 | 8000 | 否 |
| LOG_LEVEL | 日志级别 | INFO | 否 |
| DEEPSEEK_API_KEY | DeepSeek API 密钥 | - | 是* |
| DEEPSEEK_API_URL | DeepSeek API 地址 | - | 否 |

* 仅推理服务需要

### 数据库配置

```bash
# PostgreSQL 连接字符串格式
postgresql://[user]:[password]@[host]:[port]/[database]

# 示例
DATABASE_URL=postgresql://zhineng:zhineng123@postgres:5432/zhineng_kb
```

### Redis 配置

```bash
# Redis 连接字符串格式
redis://:[password]@[host]:[port]/[db]

# 示例
REDIS_URL=redis://:redis123@redis:6379/0
```

---

## 监控配置

### Prometheus 配置

Prometheus 配置文件位于 `monitoring/prometheus/prometheus.yml`：

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'zhineng-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/api/v1/metrics/prometheus'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Grafana 仪表板

访问 Grafana: http://localhost:3000

默认凭据:
- 用户名: `admin`
- 密码: `admin123`

导入仪表板:
1. 登录 Grafana
2. 导航到 Dashboards -> Import
3. 上传 `monitoring/grafana/dashboards/overview.json`

### 告警规则 (可选)

创建告警规则文件 `monitoring/prometheus/alerts.yml`：

```yaml
groups:
- name: zhineng_alerts
  interval: 30s
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors/sec"

  - alert: HighResponseTime
    expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High response time detected"
      description: "P95 response time is {{ $value }} seconds"
```

---

## 生产环境建议

### 安全配置

1. **更改默认密码**

```bash
# 修改 .env 文件中的密码
POSTGRES_PASSWORD=your_strong_password
REDIS_PASSWORD=your_strong_password
GRAFANA_ADMIN_PASSWORD=your_strong_password
```

2. **启用 HTTPS**

```nginx
# nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # ... 其他配置
}
```

3. **配置防火墙**

```bash
# 仅开放必要端口
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw enable
```

4. **启用认证** (未实现)

```python
# 在 main.py 中添加 JWT 认证
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/api/v1/protected")
async def protected_route(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # 验证 token
    pass
```

### 性能优化

1. **数据库连接池**

```python
# config.py
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "20"))
DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
```

2. **Redis 缓存策略**

```python
# 配置缓存过期时间
CACHE_TTL = {
    "document": 3600,      # 文档缓存 1 小时
    "search": 300,         # 搜索结果缓存 5 分钟
    "embedding": 86400,    # 嵌入向量缓存 24 小时
}
```

3. **API 限流**

```python
# gateway/rate_limiter.py
RATE_LIMITS = {
    "default": 100,        # 每分钟 100 次请求
    "search": 50,          # 搜索 API 每分钟 50 次
    "reason": 20,          # 推理 API 每分钟 20 次
}
```

### 备份策略

1. **自动备份** (使用 Cron)

```bash
# 添加到 crontab
0 2 * * * /path/to/scripts/backup.sh all
```

2. **远程备份**

```bash
# 备份到远程服务器
scp backups/*.sql.gz user@remote-server:/backups/
```

3. **备份验证**

```bash
# 定期测试备份恢复
./scripts/restore.sh test_backup_file.sql
```

---

## 故障排查

### 常见问题

#### 1. 容器启动失败

```bash
# 查看日志
docker-compose logs api

# 检查配置
docker-compose config

# 重新构建
docker-compose build --no-cache api
```

#### 2. 数据库连接失败

```bash
# 检查 PostgreSQL 状态
docker-compose ps postgres

# 进入容器检查
docker-compose exec postgres psql -U zhineng -d zhineng_kb

# 检查网络
docker network ls
docker network inspect zhineng-network
```

#### 3. API 响应慢

```bash
# 检查资源使用
docker stats

# 查看慢查询日志
docker-compose exec postgres cat /var/log/postgresql/postgresql-slow.log

# 检查缓存状态
docker-compose exec redis redis-cli -a redis123 INFO stats
```

#### 4. 内存不足

```bash
# 限制容器内存
# 在 docker-compose.yml 中添加
services:
  api:
    mem_limit: 1g
    mem_reservation: 512m
```

### 日志查看

```bash
# 查看所有日志
docker-compose logs

# 跟踪日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api

# 查看最近 100 行
docker-compose logs --tail=100 api
```

### 健康检查

```bash
# 使用部署脚本
./scripts/deploy.sh health

# 手动检查
curl http://localhost:8001/health
curl http://localhost:8001/api/v1/domains
curl http://localhost:8001/api/v1/stats
```

---

## 卸载

### Docker Compose

```bash
# 停止并删除容器
docker-compose down

# 删除数据卷 (谨慎操作)
docker-compose down -v

# 删除镜像
docker-compose rmi
```

### Kubernetes

```bash
# 删除所有资源
kubectl delete namespace zhineng-kb

# 或逐个删除
kubectl delete -f k8s/

# 使用 Helm
helm uninstall zhineng-kb -n zhineng-kb
```
