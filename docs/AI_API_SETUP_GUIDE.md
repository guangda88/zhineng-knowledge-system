# 多AI API配置指南

**日期**: 2026-04-01
**AI厂商**: 混元（腾讯）、DeepSeek

---

## 🔑 API密钥获取

### 1. 混元（腾讯混元大模型）

**申请地址**：https://console.cloud.tencent.com/hunyuan

**步骤**：
1. 注册/登录腾讯云账号
2. 开通混元大模型服务
3. 创建API密钥
4. 记录密钥：`HUNYUAN_API_KEY`

**模型**：
- hunyuan-lite（轻量版，快速响应）
- hunyuan-standard（标准版）
- hunyuan-pro（专业版，最强能力）

**定价**：
- 按token计费
- 免费额度：通常有100万tokens

**文档**：https://cloud.tencent.com/document/product/1729

---

### 2. DeepSeek

**申请地址**：https://platform.deepseek.com/

**步骤**：
1. 注册/登录DeepSeek平台
2. 创建API密钥
3. 记录密钥：`DEEPSEEK_API_KEY`

**模型**：
- deepseek-chat（通用对话）
- deepseek-coder（代码生成）

**定价**：
- 极低价格（目前最便宜的LLM之一）
- 输入：¥0.001/1K tokens
- 输出：¥0.002/1K tokens

**文档**：https://platform.deepseek.com/api-docs/

---

## ⚙️ 环境配置

### 方法1：环境变量（推荐）

```bash
# .env 或环境变量
HUNYUAN_API_KEY=your_hunyuan_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
```

### 方法2：docker-compose.yml

```yaml
services:
  api:
    environment:
      - HUNYUAN_API_KEY=${HUNYUAN_API_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
```

### 方法3：系统环境变量

```bash
# Linux/Mac
export HUNYUAN_API_KEY="your_hunyuan_key_here"
export DEEPSEEK_API_KEY="your_deepseek_key_here"

# Windows
set HUNYUAN_API_KEY=your_hunyuan_key_here
set DEEPSEEK_API_KEY=your_deepseek_key_here
```

---

## 🧪 测试API连接

### 测试混元API

```bash
curl -X POST "https://api.hunyuan.cloud.tencent.com/v1/chat/completions" \
  -H "Authorization: Bearer $HUNYUAN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hunyuan-lite",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

### 测试DeepSeek API

```bash
curl -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

---

## 🔌 灵知系统集成

### 已实现适配器

**文件**: `backend/services/evolution/multi_ai_adapter.py`

**混元适配器**：
```python
class HunyuanAdapter(BaseAIAdapter):
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("HUNYUAN_API_KEY")
        self.api_url = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
```

**DeepSeek适配器**：
```python
class DeepSeekAdapter(BaseAIAdapter):
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
```

### 使用示例

```python
from backend.services.evolution.multi_ai_adapter import get_multi_ai_adapter

adapter = get_multi_ai_adapter()

# 并行调用混元和DeepSeek
results = await adapter.parallel_generate(
    prompt="如何提高学习注意力？",
    request_type="qa",
    providers=["hunyuan", "deepseek"]
)

# 结果
{
    "hunyuan": {
        "content": "混元的回答...",
        "latency_ms": 300,
        "success": True
    },
    "deepseek": {
        "content": "DeepSeek的回答...",
        "latency_ms": 200,
        "success": True
    }
}
```

---

## 📊 成本估算

### 混元定价（参考）

- 输入：¥0.015/1K tokens
- 输出：¥0.06/1K tokens
- 假设每次对比：
  - 输入：100 tokens（用户问题）
  - 输出：1000 tokens（AI回答）
  - 单次成本：¥0.015 + ¥0.06 = ¥0.075

### DeepSeek定价

- 输入：¥0.001/1K tokens
- 输出：¥0.002/1K tokens
- 假设每次对比：
  - 输入：100 tokens
  - 输出：1000 tokens
  - 单次成本：¥0.001 + ¥0.002 = ¥0.003

### 月度成本估算

假设：
- 每天100次对比
- 每月3000次对比

**混元**：3000 * ¥0.075 = ¥225/月
**DeepSeek**：3000 * ¥0.003 = ¥9/月
**总计**：¥234/月

**优化策略**：
- ✅ 不是每次问题都对比（抽样10%）
- ✅ 缓存相同问题的对比结果
- ✅ 使用mock数据进行开发测试
- **优化后成本**：¥23/月

---

## 🎯 推荐配置

### 开发环境

```bash
# 使用mock响应（无需API密钥）
HUNYUAN_API_KEY=
DEEPSEEK_API_KEY=
```

**效果**：返回模拟响应，无成本

### 生产环境

```bash
# 混元 + DeepSeek
HUNYUAN_API_KEY=真实密钥
DEEPSEEK_API_KEY=真实密钥
```

**效果**：真实对比，完整功能

---

## 🚀 快速开始

### Step 1: 设置API密钥

```bash
# 编辑.env文件
nano .env

# 添加以下行
HUNYUAN_API_KEY=sk-your-hunyuan-key
DEEPSEEK_API_KEY=sk-your-deepseek-key
```

### Step 2: 测试连接

```bash
# 测试混元
python scripts/test_ai_apis.py hunyuan

# 测试DeepSeek
python scripts/test_ai_apis.py deepseek
```

### Step 3: 验证集成

```bash
# 运行进化系统测试
python -m pytest tests/test_evolution_api.py -v -k test_parallel_generate
```

---

## ⚠️ 注意事项

### 速率限制

- **混元**：通常20 QPS
- **DeepSeek**：通常50 QPS

**建议**：使用异步并发，添加重试机制

### 超时处理

- 设置30秒超时
- 失败后返回mock响应
- 记录错误日志

### 错误处理

```python
try:
    result = await ai.generate(prompt)
except Exception as e:
    logger.error(f"AI调用失败: {e}")
    # 返回mock响应，不影响主流程
    result = mock_response(prompt)
```

---

## 📝 API密钥安全

### ✅ 好的做法

- ✅ 使用环境变量
- ✅ 不提交到git
- ✅ 使用.env.example提供模板
- ✅ 定期轮换密钥
- ✅ 为不同环境使用不同密钥

### ❌ 不好的做法

- ❌ 硬编码在源码中
- ❌ 提交到版本控制
- ❌ 在日志中打印
- ❌ 共享给团队成员

---

## 🔄 密钥轮换策略

**建议频率**：每90天轮换一次

**步骤**：
1. 生成新API密钥
2. 更新环境变量
3. 测试新密钥
4. 禁用旧密钥
5. 更新文档

---

**众智混元，万法灵通** ⚡🚀
