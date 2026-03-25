# 性能测试套件

智能知识系统的性能基准测试，使用 Locust 框架进行负载测试。

## 目录结构

```
tests/performance/
├── locustfile.py          # 主测试脚本
├── requirements.txt       # Python依赖
├── config.yml            # 测试配置（可选）
├── scripts/              # 辅助脚本
│   ├── run_test.sh       # 运行测试脚本
│   └── generate_report.py # 生成报告脚本
└── reports/              # 测试报告输出目录
```

## 性能目标

| 指标 | 目标值 |
|------|--------|
| P50 响应时间 | < 200ms |
| P95 响应时间 | < 1s |
| P99 响应时间 | < 2s |
| 并发用户 | 100 |

## 环境准备

### 1. 安装依赖

```bash
cd /home/ai/zhineng-knowledge-system
pip install -r tests/performance/requirements.txt
```

### 2. 启动被测服务

```bash
# 方式1: 使用 Docker Compose
docker-compose up -d

# 方式2: 直接运行
cd backend
python main.py
```

### 3. 验证服务可用

```bash
curl http://localhost:8000/health
```

## 运行测试

### 方式1: Web UI 模式（推荐用于调试）

```bash
cd /home/ai/zhineng-knowledge-system
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

访问 http://localhost:8089 进行可视化配置和监控。

### 方式2: 无头模式（推荐用于自动化测试）

```bash
# 基础测试
locust -f tests/performance/locustfile.py \
    --headless \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=2m

# 生成 HTML 报告
locust -f tests/performance/locustfile.py \
    --headless \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=2m \
    --html=reports/performance_report_$(date +%Y%m%d_%H%M%S).html
```

### 方式3: 分布式模式（适用于大规模测试）

**主节点:**
```bash
locust -f tests/performance/locustfile.py \
    --master \
    --host=http://localhost:8000 \
    --expect-workers=4
```

**工作节点:**
```bash
locust -f tests/performance/locustfile.py \
    --worker \
    --master-host=localhost
```

## 测试场景

### 1. 混合负载测试

模拟真实用户行为，包含所有端点：

- GET /api/v1/documents (权重: 2)
- GET /api/v1/search (权重: 4)
- POST /api/v1/ask (权重: 3)
- POST /api/v1/search/hybrid (权重: 2)

### 2. 读密集型测试

测试浏览和搜索性能：

```bash
locust -f tests/performance/locustfile.py \
    --user-class=ReadHeavyUser \
    --headless \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=2m
```

### 3. 写密集型测试

测试复杂查询性能：

```bash
locust -f tests/performance/locustfile.py \
    --user-class=WriteHeavyUser \
    --headless \
    --host=http://localhost:8000 \
    --users=50 \
    --spawn-rate=5 \
    --run-time=2m
```

### 4. 单端点专项测试

**搜索端点:**
```bash
locust -f tests/performance/locustfile.py \
    --user-class=SearchEndpointTest \
    --headless \
    --host=http://localhost:8000 \
    --users=200 \
    --spawn-rate=20 \
    --run-time=1m
```

**问答端点:**
```bash
locust -f tests/performance/locustfile.py \
    --user-class=AskEndpointTest \
    --headless \
    --host=http://localhost:8000 \
    --users=50 \
    --spawn-rate=5 \
    --run-time=2m
```

**混合检索端点:**
```bash
locust -f tests/performance/locustfile.py \
    --user-class=HybridSearchEndpointTest \
    --headless \
    --host=http://localhost:8000 \
    --users=50 \
    --spawn-rate=5 \
    --run-time=2m
```

**文档列表端点:**
```bash
locust -f tests/performance/locustfile.py \
    --user-class=DocumentsEndpointTest \
    --headless \
    --host=http://localhost:8000 \
    --users=200 \
    --spawn-rate=20 \
    --run-time=1m
```

## 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| TARGET_HOST | http://localhost:8000 | 目标服务器地址 |
| TARGET_USERS | 100 | 并发用户数 |
| SPAWN_RATE | 10 | 每秒启动用户数 |
| RUN_TIME | 2m | 测试运行时长 |

## 测试报告

### HTML 报告

```bash
# 生成带时间戳的报告
mkdir -p reports
locust -f tests/performance/locustfile.py \
    --headless \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=2m \
    --html=reports/report_$(date +%Y%m%d_%H%M%S).html \
    --csv=reports/report_$(date +%Y%m%d_%H%M%S)
```

### CSV 报告

生成的 CSV 文件包含：
- `stats`: 请求统计数据
- `stats_history`: 时间序列统计数据
- `failures`: 失败请求详情

### 控制台输出

测试结束时会在控制台输出性能摘要，包括：
- 各端点请求统计
- P50/P95/P99 响应时间
- 是否达到性能目标

## 性能基准

基于当前系统的预期性能基准：

| 端点 | P50 | P95 | P99 |
|------|-----|-----|-----|
| GET /api/v1/documents | < 100ms | < 300ms | < 500ms |
| GET /api/v1/search | < 150ms | < 500ms | < 800ms |
| POST /api/v1/ask | < 300ms | < 1s | < 2s |
| POST /api/v1/search/hybrid | < 200ms | < 800ms | < 1.5s |

## 常见问题

### 1. 连接超时

如果出现连接超时，检查：
- 目标服务是否正常运行
- 防火墙是否阻止连接
- 数据库连接池是否足够

### 2. 高失败率

常见原因：
- 速率限制触发
- 数据库连接耗尽
- 内存不足
- API 密钥未配置（对于需要 LLM 的端点）

### 3. 响应时间过长

优化建议：
- 添加数据库索引
- 启用缓存
- 增加数据库连接池大小
- 使用负载均衡

## 持续集成

### GitHub Actions 示例

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点运行
  workflow_dispatch:

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r tests/performance/requirements.txt

      - name: Start services
        run: docker-compose up -d

      - name: Wait for services
        run: sleep 30

      - name: Run performance tests
        run: |
          mkdir -p reports
          locust -f tests/performance/locustfile.py \
            --headless \
            --host=http://localhost:8000 \
            --users=100 \
            --spawn-rate=10 \
            --run-time=2m \
            --html=reports/report.html \
            --csv=reports/report

      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: performance-reports
          path: reports/
```

## 最佳实践

1. **测试环境隔离**: 使用独立的测试环境
2. **数据预热**: 运行正式测试前先预热缓存
3. **多次运行**: 运行多次测试取平均值
4. **资源监控**: 同时监控 CPU、内存、磁盘、网络
5. **渐进式测试**: 从小负载开始逐步增加
6. **真实数据**: 使用与生产环境相似的数据量

## 参考资料

- [Locust 官方文档](https://docs.locust.io/)
- [性能测试最佳实践](https://docs.locust.io/en/stable/testing-best-practices.html)
