# 性能测试报告模板

## 测试信息

| 项目 | 值 |
|------|-----|
| 测试名称 | {{ test_name }} |
| 测试时间 | {{ test_time }} |
| 测试人员 | {{ tester }} |
| 测试环境 | {{ environment }} |
| 目标主机 | {{ target_host }} |

## 测试配置

| 参数 | 值 |
|------|-----|
| 并发用户数 | {{ users }} |
| 启动速率 | {{ spawn_rate }} users/s |
| 测试时长 | {{ run_time }} |
| 用户类型 | {{ user_class }} |

## 测试结果概要

### 整体性能

| 指标 | 结果 | 目标 | 状态 |
|------|------|------|------|
| 总请求数 | {{ total_requests }} | - | - |
| 失败请求数 | {{ total_failures }} | < 1% | {{ failure_rate_status }} |
| 平均 RPS | {{ avg_rps }} | > 100 | {{ rps_status }} |
| P50 响应时间 | {{ p50 }}ms | < 200ms | {{ p50_status }} |
| P95 响应时间 | {{ p95 }}ms | < 1000ms | {{ p95_status }} |
| P99 响应时间 | {{ p99 }}ms | < 2000ms | {{ p99_status }} |

### 端点性能详情

| 端点 | 请求数 | 失败率 | P50 | P95 | P99 | 状态 |
|------|--------|--------|-----|-----|-----|------|
{% for endpoint in endpoints %}
| {{ endpoint.name }} | {{ endpoint.requests }} | {{ endpoint.fail_rate }}% | {{ endpoint.p50 }}ms | {{ endpoint.p95 }}ms | {{ endpoint.p99 }}ms | {{ endpoint.status }} |
{% endfor %}

## 性能分析

### 达标情况

{% if goals_met %}
✅ 以下性能目标已达成:
{% for goal in goals_met %}
- {{ goal }}
{% endfor %}
{% endif %}

{% if goals_not_met %}
❌ 以下性能目标未达成:
{% for goal in goals_not_met %}
- {{ goal }}
{% endfor %}
{% endif %}

### 瓶颈分析

{% for bottleneck in bottlenecks %}
#### {{ bottleneck.endpoint }}

- **问题**: {{ bottleneck.issue }}
- **影响**: {{ bottleneck.impact }}
- **建议**: {{ bottleneck.recommendation }}

{% endfor %}

## 优化建议

### 高优先级

{% for item in high_priority %}
1. **{{ item.title }}**
   - 描述: {{ item.description }}
   - 预期收益: {{ item.benefit }}

{% endfor %}

### 中优先级

{% for item in medium_priority %}
1. **{{ item.title }}**
   - 描述: {{ item.description }}

{% endfor %}

### 低优先级

{% for item in low_priority %}
1. **{{ item.title }}**
   - 描述: {{ item.description }}

{% endfor %}

## 附录

### 测试环境详情

- **CPU**: {{ cpu_info }}
- **内存**: {{ memory_info }}
- **磁盘**: {{ disk_info }}
- **网络**: {{ network_info }}
- **数据库**: {{ database_info }}
- **缓存**: {{ cache_info }}

### 时间序列数据

![响应时间趋势](response_time_chart.png)

![请求速率趋势](requests_per_second_chart.png)

### 原始数据

- CSV 报告: [下载]({{ csv_file }})
- JSON 数据: [下载]({{ json_file }})

---

*报告由性能测试系统自动生成*
