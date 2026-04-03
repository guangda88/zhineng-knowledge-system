# AI服务快速使用指南

**状态**: ✅ 已启用并测试通过

---

## 🎉 测试结果

```
✅ Token池正常运行
✅ 6个Provider可用
✅ 智能调度工作正常
✅ AI对话测试成功
```

**测试响应**:
> 你好，我是DeepSeek，一个由深度求索公司创造的AI助手，致力于用热情和细腻的方式为你提供帮助！😊

---

## 🚀 快速开始

### 1. 简单对话

```python
from backend.services.ai_service import chat

response = await chat("你好，请介绍一下你自己")
print(response)
```

### 2. 复杂推理

```python
from backend.services.ai_service import reason

answer = await reason("解释量子纠缠的原理")
print(answer)
```

### 3. 代码生成

```python
from backend.services.ai_service import generate_code

code = await generate_code("用Python实现快速排序")
print(code)
```

### 4. 文本摘要

```python
from backend.services.ai_service import summarize

summary = await summarize(long_text, max_length=200)
print(summary)
```

### 5. 信息提取

```python
from backend.services.ai_service import extract_info

email = await extract_info(text, "email地址")
phone = await extract_info(text, "电话号码")
```

---

## 📊 查看Token池状态

```python
from backend.services.ai_service import format_pool_status

print(format_pool_status())
```

**输出示例**:
```
📊 Token池状态
============================================================
总额度: 10,000,000 tokens
已使用: 0 tokens
剩余: 10,000,000 tokens
使用率: 0.0%

可用Provider:
  ✅ glm: 1,000,000 tokens (成功率: 100%, 延迟: 0ms)
  ✅ qwen: 1,000,000 tokens (成功率: 100%, 延迟: 0ms)
  ✅ tongyi: 1,000,000 tokens (成功率: 100%, 延迟: 0ms)
  ✅ deepseek: 5,000,000 tokens (成功率: 100%, 延迟: 0ms)
  ✅ hunyuan: 1,000,000 tokens (成功率: 100%, 延迟: 0ms)
  ✅ doubao: 1,000,000 tokens (成功率: 100%, 延迟: 0ms)
```

---

## 💡 实际应用示例

### 示例1: 知识库问答

```python
from backend.services.ai_service import chat

async def answer_question(question: str, context: str) -> str:
    prompt = f"""
    基于以下上下文回答问题:

    上下文: {context}

    问题: {question}

    请给出准确、简洁的回答。
    """

    response = await chat(prompt)
    return response
```

### 示例2: 文档分析

```python
from backend.services.ai_service import summarize, extract_info

async def analyze_document(text: str):
    # 生成摘要
    summary = await summarize(text)

    # 提取关键信息
    keywords = await extract_info(text, "关键词")
    topic = await extract_info(text, "主题")

    return {
        "summary": summary,
        "keywords": keywords,
        "topic": topic
    }
```

### 示例3: 智能助手

```python
from backend.services.ai_service import chat, reason

async def smart_assistant(query: str):
    # 简单问题用快速模式
    if len(query) < 50:
        return await chat(query)

    # 复杂问题用推理模式
    return await reason(query)
```

---

## 🔧 高级用法

### 指定复杂度

```python
from backend.services.ai_service import generate_text

# 简单任务（快速）
result = await generate_text(
    prompt="问候",
    complexity="simple"
)

# 复杂任务（质量优先）
result = await generate_text(
    prompt="解决数学难题",
    complexity="high"
)
```

### 自动重试

```python
from backend.services.ai_service import generate_with_fallback

# 自动尝试多个provider直到成功
result = await generate_with_fallback(
    prompt="重要任务",
    max_retries=3
)
```

### 查看详细信息

```python
result = await generate_text("测试")

if result["success"]:
    print(f"内容: {result['content']}")
    print(f"Provider: {result['provider']}")
    print(f"Token使用: {result['tokens']}")
    print(f"延迟: {result['latency_ms']}ms")
```

---

## 📈 性能监控

### 方式1: 查看状态

```python
from backend.services.ai_service import get_pool_status

status = get_pool_status()

print(f"总使用: {status['total_used']:,} tokens")
print(f"剩余: {status['total_remaining']:,} tokens")
```

### 方式2: 记录日志

```python
import logging

logger = logging.getLogger(__name__)

result = await chat("测试")

if result["success"]:
    logger.info(f"✅ AI调用成功 | Provider: {result['provider']} | Tokens: {result['tokens']}")
else:
    logger.error(f"❌ AI调用失败 | 错误: {result.get('error')}")
```

---

## ✅ 验证清单

- [x] Token池已创建
- [x] AI服务已实现
- [x] 简单对话测试通过
- [x] 状态查询正常
- [x] 6个Provider可用
- [x] 智能调度工作正常

---

## 🎯 下一步

1. **在业务中使用** - 替换现有的API调用
2. **监控使用情况** - 参见任务3
3. **优化配置** - 根据实际使用调整

---

**您的系统现在已经可以免费使用AI能力了！** 🎉
