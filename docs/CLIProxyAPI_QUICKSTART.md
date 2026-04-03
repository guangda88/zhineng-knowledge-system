# CLIProxyAPI 集成快速开始

**灵知系统 × CLIProxyAPI 统一AI服务集成**

---

## 🎯 集成概述

通过集成 CLIProxyAPI，灵知系统获得了统一的AI服务能力：

✅ **多模型支持** - Claude, Gemini, DeepSeek, Qwen 一键切换
✅ **智能路由** - 根据任务类型自动选择最佳模型
✅ **成本优化** - 自动使用性价比最高的模型
✅ **负载均衡** - 多模型轮询，避免单点故障
✅ **统一接口** - OpenAI兼容API，无缝集成

---

## 📦 前置要求

### 必需

- Docker 和 Docker Compose
- 至少一个AI提供商的API Key：
  - **DeepSeek** (推荐，性价比高)
  - Claude, Gemini, Qwen (可选)

### 可选

- GitHub OAuth (用于Claude Code集成)
- Google OAuth (用于Gemini CLI集成)

---

## 🚀 快速开始 (5分钟部署)

### 步骤1: 获取API密钥

选择至少一个AI服务商并获取API Key：

| 提供商 | 获取地址 | 推荐用途 | 费用 |
|--------|---------|---------|------|
| **DeepSeek** | https://platform.deepseek.com/ | 默认聊天模型 | ¥1/百万tokens |
| **Claude** | https://console.anthropic.com/ | 高质量推理 | $3/百万tokens |
| **Gemini** | https://aistudio.google.com/app/apikey | 多模态处理 | 免费 |
| **Qwen** | https://dashscope.aliyun.com/ | 中文优化 | ¥0.5/百万tokens |

### 步骤2: 配置环境变量

```bash
# 复制环境变量模板
cp .env.cliproxyapi.template .env.cliproxyapi

# 编辑并添加您的API密钥
nano .env.cliproxyapi
```

最低配置示例：
```bash
# 至少配置一个API Key
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
```

### 步骤3: 运行安装脚本

```bash
# 自动部署CLIProxyAPI
bash scripts/setup_cliproxyapi.sh
```

脚本会自动：
- ✅ 检查Docker环境
- ✅ 创建配置目录
- ✅ 拉取Docker镜像
- ✅ 启动CLIProxyAPI服务
- ✅ 验证服务健康状态

### 步骤4: 验证安装

```bash
# 运行集成测试
python scripts/test_cliproxyapi_integration.py
```

预期输出：
```
============================================================
Test 1: Health Check
============================================================
✅ Health check passed

============================================================
Test 2: Basic Chat Completion
============================================================
✅ Chat completion successful
   Model: deepseek-chat
   Content: 你好！我是AI助手...
   Tokens: 42

...

🎉 All tests passed!
```

---

## 📖 使用指南

### 基础用法

```python
from backend.services.ai_service_adapter import AIServiceAdapter, TaskType

# 初始化适配器
adapter = AIServiceAdapter()

# 聊天对话
messages = [
    {"role": "system", "content": "你是一个友好的助手。"},
    {"role": "user", "content": "解释什么是混元灵通"}
]

response = await adapter.chat(
    messages=messages,
    task_type=TaskType.CHAT  # 自动选择DeepSeek
)

print(response["content"])
```

### 高级用法：智能模型选择

```python
# 推理任务 - 自动使用Claude
response = await adapter.chat(
    messages=[{"role": "user", "content": "分析混元灵通的哲学原理"}],
    task_type=TaskType.REASONING  # → Claude Opus
)

# 代码任务 - 自动使用Claude
response = await adapter.chat(
    messages=[{"role": "user", "content": "写一个Python函数"}],
    task_type=TaskType.CODING  # → Claude Sonnet
)

# 中文任务 - 自动使用Qwen
response = await adapter.chat(
    messages=[{"role": "user", "content": "解释组场发气"}],
    task_type=TaskType.CHINESE  # → Qwen Plus
)

# 多模态 - 自动使用Gemini
response = await adapter.chat(
    messages=[{"role": "user", "content": "分析这张图片"}],
    task_type=TaskType.MULTIMODAL  # → Gemini Flash
)
```

### RAG查询

```python
from backend.services.ai_service_adapter import UnifiedAIService

service = UnifiedAIService()

answer = await service.rag_query(
    query="什么是混元灵通？",
    context=[
        {"title": "智能气功基础", "content": "混元灵通是..."},
        {"title": "组场方法", "content": "组场通过..."}
    ]
)
```

### 音频分析

```python
# 总结音频转录
summary = await service.summarize_audio_transcript(
    transcript="长篇音频转录内容...",
    max_length=500
)

# 纠正ASR错误
corrected = await service.correct_asr_errors(
    transcript="可能有ASR错误的转录...",
    domain="qigong"  # 领域关键词
)

# 提取教学要点
points = await service.extract_teaching_points(
    transcript="教学录音转录..."
)
```

---

## 🔧 配置详解

### 模型映射表

| 任务类型 | 主模型 | 备用模型 | 原因 |
|---------|--------|---------|------|
| 推理 (REASONING) | Claude Opus | Claude Sonnet | 最佳推理质量 |
| 编码 (CODING) | Claude Sonnet | DeepSeek Chat | 强大编程能力 |
| 聊天 (CHAT) | DeepSeek Chat | Qwen Chat | 高性价比 |
| 中文 (CHINESE) | Qwen Chat | Gemini Flash | 中文优化 |
| 多模态 (MULTIMODAL) | Gemini Flash | Claude Sonnet | 快速多模态 |
| 分析 (ANALYSIS) | Claude Sonnet | DeepSeek Reasoner | 强大分析能力 |
| 总结 (SUMMARIZATION) | DeepSeek Chat | Qwen Chat | 低成本高质量 |

### 自定义配置

编辑 `config/cliproxyapi/config.yaml`:

```yaml
# 修改默认模型
LoadBalanceSettings:
  Strategy: "RoundRobin"  # 或 "Random", "LeastConnection"

# 调整限流
RateLimitSettings:
  RequestsPerMinute: 100  # 根据需要调整

# 启用缓存
CacheSettings:
  Enabled: true
  ExpirationMinutes: 60
```

---

## 🎭 实际应用场景

### 场景1: 智能问答

```python
# 用户提问混元灵通概念
answer = await service.rag_query(
    query="混元灵通是什么？",
    context=search_results  # 从向量检索获取
)
```

### 场景2: 音频转写后处理

```python
# 1. 获取faster-whisper转录
transcript = "智能气功的混元灵通理论认为..."

# 2. 纠正ASR错误
corrected = await service.correct_asr_errors(
    transcript=transcript,
    domain="qigong"
)

# 3. 生成摘要
summary = await service.summarize_audio_transcript(
    transcript=corrected,
    max_length=500
)

# 4. 提取教学要点
points = await service.extract_teaching_points(
    transcript=corrected
)
```

### 场景3: 多语言支持

```python
# 中文内容 - 自动使用Qwen
chinese_answer = await adapter.chat(
    messages=[{"role": "user", "content": "解释组场"}],
    task_type=TaskType.CHINESE
)

# 英文内容 - 自动使用Claude
english_answer = await adapter.chat(
    messages=[{"role": "user", "content": "Explain Qigong"}],
    task_type=TaskType.REASONING
)
```

---

## 📊 监控与调试

### 查看服务状态

```bash
# 检查服务健康
curl http://localhost:8317/health

# 查看可用模型
curl http://localhost:8317/v1/models

# 查看服务日志
docker logs -f lingzhi-cliproxyapi
```

### Prometheus指标

CLIProxyAPI提供Prometheus监控：

```bash
# 访问指标
curl http://localhost:9090/metrics
```

可用指标：
- `cliproxyapi_requests_total` - 总请求数
- `cliproxyapi_request_duration_seconds` - 请求延迟
- `cliproxyapi_errors_total` - 错误数

### 日志文件

```bash
# 查看日志
tail -f logs/cliproxyapi/cliproxyapi.log

# 搜索错误
grep ERROR logs/cliproxyapi/cliproxyapi.log
```

---

## ⚠️ 常见问题

### Q1: CLIProxyAPI启动失败

**检查**: Docker网络
```bash
docker network ls | grep lingzhi
# 如果不存在，创建:
docker network create lingzhi-network
```

### Q2: API调用失败

**检查**: API Key配置
```bash
# 确认环境变量已加载
docker-compose -f docker-compose.cli-proxy.yml config
```

### Q3: 模型返回错误

**检查**: 模型别名配置
```bash
# 查看配置的模型
curl http://localhost:8317/v1/models | jq
```

### Q4: 性能问题

**优化**: 启用缓存
```yaml
# config/cliproxyapi/config.yaml
CacheSettings:
  Enabled: true
  ExpirationMinutes: 60
```

---

## 🔐 安全最佳实践

### 1. 永远不要提交API密钥

```bash
# .gitignore
.env.cliproxyapi
config/cliproxyapi/secrets.yaml
```

### 2. 使用环境变量

```bash
# ✅ 好的做法
export DEEPSEEK_API_KEY="sk-xxx"

# ❌ 不好的做法
# 在代码中硬编码密钥
```

### 3. 定期轮换密钥

```bash
# 每3-6个月轮换一次API密钥
# 并监控API使用情况
```

### 4. 限流保护

```yaml
# 配置合理的限流
RateLimitSettings:
  RequestsPerMinute: 100
  ConcurrentRequests: 10
```

---

## 📈 下一步

集成完成后，您可以：

1. **扩展AI功能**
   - 集成到现有RAG服务
   - 添加音频转写后处理
   - 实现智能标注建议

2. **优化成本**
   - 根据实际使用调整模型选择
   - 启用结果缓存
   - 监控API使用量

3. **增强功能**
   - 添加OAuth认证
   - 实现多租户支持
   - 自定义模型路由策略

---

## 📚 相关文档

- 📖 [完整集成指南](docs/CLIProxyAPI_INTEGRATION_GUIDE.md)
- 🔧 [API参考](https://github.com/router-for-me/CLIProxyAPI)
- 📝 [变更日志](CHANGELOG.md)

---

**文档状态**: ✅ 完整

**最后更新**: 2026-04-01

**众智混元，万法灵通** ⚡🚀
