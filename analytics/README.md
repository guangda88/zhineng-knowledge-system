# 数据分析准备指南
# Data Analytics Preparation Guide

## 📋 目录
1. [概述](#概述)
2. [准备工作](#准备工作)
3. [数据生成](#数据生成)
4. [数据验证](#数据验证)
5. [性能分析](#性能分析)
6. [报告生成](#报告生成)
7. [使用示例](#使用示例)

## 📌 概述

本目录包含数据分析相关的所有工具和配置，用于：
- 生成测试数据
- 验证数据质量
- 分析系统性能
- 导出分析报告

## 🚀 准备工作

### 1. 环境检查

确保以下服务正在运行：

```bash
# 检查Docker容器
docker-compose ps

# 检查数据库连接
docker exec tcm-postgres pg_isready -U tcmuser

# 检查后端服务
curl http://localhost:8000/health
```

### 2. 依赖安装

所有脚本位于 `/home/ai/zhineng-knowledge-system/analytics/scripts/` 目录：

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts

# 检查Python版本
python3 --version  # 需要Python 3.12+
```

## 📊 数据生成

### 功能描述

生成用于测试和分析的示例数据：
- **用户数据**：100个测试用户
- **文档数据**：1000个中医文档
- **文档块**：文档的分块数据
- **标注数据**：5000条标注记录
- **搜索历史**：10000条搜索记录

### 使用方法

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
python3 data_generator.py
```

### 输出结果

- 测试数据插入到PostgreSQL数据库
- 统计信息保存到 `analytics/data/statistics.json`

## 🔍 数据验证

### 功能描述

验证数据质量，包括：
- **完整性**：必填字段是否完整
- **准确性**：数据是否准确
- **一致性**：数据是否一致
- **有效性**：数据格式是否有效
- **唯一性**：关键字段是否唯一

### 使用方法

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
python3 data_validator.py
```

### 输出结果

- 验证报告保存到 `analytics/reports/data_validation_report_*.json`
- 验证摘要保存到 `analytics/reports/validation_summary.txt`

### 质量指标

| 指标 | 说明 | 目标值 |
|--------|------|---------|
| 数据完整性 | 必填字段完整率 | > 99% |
| 数据准确性 | 数据格式正确率 | > 98% |
| 数据一致性 | 关联数据一致性 | > 99% |
| 数据有效性 | 业务规则符合率 | > 95% |
| 数据唯一性 | 唯一约束符合率 | 100% |

## ⚡ 性能分析

### 功能描述

分析系统性能，包括：
- **查询性能**：响应时间统计
- **系统健康**：资源使用情况
- **数据库性能**：查询执行时间
- **吞吐量测试**：并发处理能力

### 使用方法

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
python3 performance_analyzer.py
```

### 输出结果

- 性能报告保存到 `analytics/reports/performance_report_*.json`
- 性能摘要保存到 `analytics/reports/performance_summary.txt`

### 性能指标

| 指标 | 说明 | 目标值 |
|--------|------|---------|
| 平均响应时间 | P50查询响应时间 | < 100ms |
| P95响应时间 | 95%查询响应时间 | < 500ms |
| P99响应时间 | 99%查询响应时间 | < 1000ms |
| 吞吐量 | 每秒请求数（RPS） | > 100 RPS |
| 系统可用性 | 服务正常运行时间 | > 99.5% |

## 📥 数据导入

### 功能描述

批量导入外部数据到系统：
- 支持JSON格式
- 支持CSV格式
- 批量处理
- 错误处理和日志

### 使用方法

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
python3 data_importer.py
```

### 支持的数据格式

#### JSON格式示例

```json
{
  "users": [
    {
      "username": "user1",
      "email": "user1@example.com",
      "password_hash": "hash_value",
      "full_name": "User One"
    }
  ],
  "search_history": [
    {
      "user_id": 1,
      "query": "测试查询",
      "search_type": "keyword",
      "results_count": 10,
      "response_time_ms": 150
    }
  ]
}
```

## 🤖 一键执行

### 快速启动

使用主控制脚本执行所有分析任务：

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
./run_analytics.sh
```

### 选项说明

```bash
# 跳过数据生成
./run_analytics.sh --skip-generation

# 跳过数据验证
./run_analytics.sh --skip-validation

# 跳过性能分析
./run_analytics.sh --skip-performance

# 运行数据导入
./run_analytics.sh --run-import

# 显示帮助信息
./run_analytics.sh --help
```

## 📈 使用示例

### 示例1：完整分析流程

```bash
# 1. 启动所有服务
cd /home/ai/zhineng-knowledge-system
docker-compose up -d

# 2. 等待服务就绪
sleep 30

# 3. 运行完整分析
cd analytics/scripts
./run_analytics.sh

# 4. 查看报告
cat ../reports/summary_report_*.txt
```

### 示例2：仅生成测试数据

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
python3 data_generator.py

# 查看统计信息
cat ../data/statistics.json
```

### 示例3：仅验证数据质量

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
python3 data_validator.py

# 查看验证摘要
cat ../reports/validation_summary.txt
```

### 示例4：仅分析性能

```bash
cd /home/ai/zhineng-knowledge-system/analytics/scripts
python3 performance_analyzer.py

# 查看性能摘要
cat ../reports/performance_summary.txt
```

## 📁 目录结构

```
analytics/
├── config/
│   └── analytics_config.py      # 分析配置文件
├── data/
│   ├── statistics.json           # 数据统计
│   ├── cache/                  # 缓存目录
│   └── sample_*.json           # 示例数据
├── reports/
│   ├── data_validation_report_*.json   # 验证报告
│   ├── validation_summary.txt          # 验证摘要
│   ├── performance_report_*.json      # 性能报告
│   ├── performance_summary.txt         # 性能摘要
│   └── summary_report_*.txt          # 总体摘要
├── scripts/
│   ├── data_generator.py       # 数据生成器
│   ├── data_validator.py        # 数据验证器
│   ├── performance_analyzer.py  # 性能分析器
│   ├── data_importer.py        # 数据导入器
│   └── run_analytics.sh        # 主控制脚本
├── logs/
│   └── analytics.log          # 分析日志
└── README.md                  # 本文件
```

## 🔧 配置说明

所有分析配置位于 `config/analytics_config.py`：

### 数据源配置

```python
DATA_SOURCES = {
    DataSourceType.POSTGRES: {
        "host": "localhost",
        "port": 5432,
        "database": "tcm_knowledge",
        ...
    },
    ...
}
```

### 分析类型配置

```python
ANALYSIS_CONFIGS = {
    AnalysisType.DATA_QUALITY: {...},
    AnalysisType.PERFORMANCE: {...},
    ...
}
```

### 输出配置

```python
OUTPUT_CONFIG = {
    "default_format": OutputFormat.JSON,
    "report_dir": Path(".../analytics/reports"),
    ...
}
```

## 📊 中医内容说明

生成的测试数据包含以下中医相关内容：

### 中药材（TCM_HERBS）
- 人参、黄芪、当归、白术、茯苓、甘草等40种

### 中医方剂（TCM_FORMULAS）
- 四君子汤、四物汤、六味地黄丸、逍遥散等20种

### 中医疾病（TCM_DISEASES）
- 感冒、咳嗽、哮喘、胃痛、腹痛等20种

### 中医理论（TCM_THEORIES）
- 阴阳学说、五行学说、脏腑学说、气血津液等10种

## 🎯 数据分析目标

### 1. 数据质量保证
- 确保数据完整、准确、一致
- 验证数据符合业务规则
- 识别和修复数据问题

### 2. 性能优化
- 识别性能瓶颈
- 优化查询效率
- 提升系统响应速度

### 3. 数据洞察
- 分析用户行为模式
- 发现搜索趋势
- 优化数据存储策略

### 4. 决策支持
- 提供数据驱动的决策依据
- 支持系统优化方向
- 指导功能改进

## 🚨 注意事项

1. **数据库连接**
   - 确保PostgreSQL服务正在运行
   - 检查数据库连接配置

2. **权限问题**
   - 确保有足够的数据库权限
   - 检查文件系统读写权限

3. **资源限制**
   - 大数据量导入可能需要较长时间
   - 建议在低峰期执行

4. **数据备份**
   - 执行数据导入前建议备份数据库
   - 验证数据前建议创建快照

## 📞 问题排查

### 常见问题

**Q1: 数据库连接失败**
```bash
A: 检查PostgreSQL服务状态
   docker exec tcm-postgres pg_isready -U tcmuser
   
   检查网络连接
   ping localhost
```

**Q2: 数据生成很慢**
```bash
A: 减少生成的数据量
   修改 data_generator.py 中的 count 参数
   
   增加数据库连接池大小
   修改 DATABASE_URL 中的 pool_size
```

**Q3: 性能分析失败**
```bash
A: 确保后端服务正常运行
   docker-compose ps backend
   
   检查API端点是否可访问
   curl http://localhost:8000/health
```

## 📚 参考文档

- [数据库模型文档](../../services/web_app/backend/database/README.md)
- [性能优化指南](../../services/web_app/backend/database/performance_guide.md)
- [系统监控文档](../../services/system_monitor/README.md)

## 📝 更新日志

### v1.0.0 (2024-03-05)
- ✅ 初始版本发布
- ✅ 数据生成器
- ✅ 数据验证器
- ✅ 性能分析器
- ✅ 数据导入器
- ✅ 主控制脚本

---

**维护者**: TCM Knowledge Base Team  
**最后更新**: 2024-03-05
