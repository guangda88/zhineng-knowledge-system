# Token池业务集成指南

**目标**: 将FreeTokenPool集成到灵知系统实际业务中

---

## 🎯 集成策略

### 阶段1: 立即启用（当前可用）

使用已测试通过的2个provider：
- **GLM**: 默认选择，快速响应
- **DeepSeek**: 复杂任务，强力推理

### 阶段2: 逐步扩展

修复其他provider后，自动扩展到更多免费额度

---

## 📝 集成方式

### 方式1: 直接使用FreeTokenPool（推荐）

```python
from backend.services.evolution.free_token_pool import get_free_token_pool, TaskType

# 获取Token池实例
pool = get_free_token_pool()

# 智能选择最优provider
provider = await pool.select_provider(
    task_type=TaskType.GENERATION,
    complexity="medium"
)

# 调用API
result = await pool.call_provider(
    provider,
    "你的提示词",
    max_tokens=2000
)

if result["success"]:
    content = result["content"]
    tokens_used = result["tokens"]
    latency = result["latency_ms"]

    print(f"✅ 成功: {content[:100]}...")
    print(f"💰 Token使用: {tokens_used}")
    print(f"⏱️  延迟: {latency}ms")
else:
    print(f"❌ 失败: {result['error']}")
```

### 方式2: 封装为便捷函数

创建 `backend/services/ai_service.py`:

```python
"""AI服务统一接口"""
from typing import Optional
from backend.services.evolution.free_token_pool import get_free_token_pool, TaskType

_pool = None

def get_ai_service():
    """获取AI服务实例"""
    global _pool
    if _pool is None:
        _pool = get_free_token_pool()
    return _pool


async def generate_text(
    prompt: str,
    complexity: str = "medium",
    max_tokens: int = 2000,
    task_type: TaskType = TaskType.GENERATION
) -> dict:
    """
    生成文本（智能选择最优provider）

    Args:
        prompt: 提示词
        complexity: simple/medium/high
        max_tokens: 最大token数
        task_type: 任务类型

    Returns:
        {
            "success": bool,
            "content": str,
            "provider": str,
            "tokens": int,
            "latency_ms": int
        }
    """
    pool = get_ai_service()

    # 选择provider
    provider = await pool.select_provider(
        task_type=task_type,
        complexity=complexity
    )

    if not provider:
        return {
            "success": False,
            "error": "没有可用的provider"
        }

    # 调用
    result = await pool.call_provider(
        provider,
        prompt,
        max_tokens=max_tokens
    )

    return result


async def generate_with_fallback(
    prompt: str,
    max_retries: int = 3,
    max_tokens: int = 2000
) -> dict:
    """
    生成文本（自动重试和fallback）

    如果某个provider失败，自动尝试其他provider
    """
    pool = get_ai_service()

    for attempt in range(max_retries):
        # 选择可用的provider
        provider = await pool.select_provider()

        if not provider:
            return {
                "success": False,
                "error": "没有可用的provider"
            }

        result = await pool.call_provider(provider, prompt, max_tokens)

        if result["success"]:
            return result

        # 失败，尝试下一个
        print(f"⚠️  {provider} 失败，尝试其他provider...")

    return {
        "success": False,
        "error": f"所有provider尝试失败 ({max_retries}次)"
    }


# ============ 便捷函数 ============

async def chat(prompt: str) -> str:
    """简单对话（返回内容字符串）"""
    result = await generate_text(prompt, complexity="simple")
    return result["content"] if result["success"] else None


async def reason(prompt: str) -> str:
    """复杂推理（使用DeepSeek）"""
    result = await generate_text(prompt, complexity="high", task_type=TaskType.REASONING)
    return result["content"] if result["success"] else None


async def code_review(code: str) -> str:
    """代码审查（使用GLM Coding Plan）"""
    prompt = f"请审查以下代码:\n\n{code}"
    result = await generate_text(prompt, task_type=TaskType.TASK)
    return result["content"] if result["success"] else None
```

### 方式3: 在现有代码中替换

**之前的代码**:
```python
import openai

response = await openai.ChatCompletion.acreate(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    api_key=your_api_key
)
content = response["choices"][0]["message"]["content"]
```

**替换为**:
```python
from backend.services.ai_service import generate_text

result = await generate_text(prompt)
content = result["content"]
```

---

## 🔌 实际业务集成示例

### 示例1: 知识库问答

**文件**: `backend/services/knowledge/qa_service.py`

```python
from backend.services.ai_service import generate_text

async def answer_question(question: str, context: str) -> str:
    """使用AI回答知识库问题"""

    prompt = f"""
    基于以下上下文回答问题:

    上下文:
    {context}

    问题: {question}

    请给出准确、简洁的回答。
    """

    result = await generate_text(
        prompt,
        complexity="medium",
        task_type=TaskType.KNOWLEDGE
    )

    if result["success"]:
        return result["content"]
    else:
        return "抱歉，我暂时无法回答这个问题。"
```

### 示例2: 文档摘要

**文件**: `backend/services/document/summarizer.py`

```python
from backend.services.ai_service import generate_text

async def summarize_document(text: str, max_length: int = 500) -> str:
    """生成文档摘要"""

    prompt = f"""
    请为以下文档生成摘要，不超过{max_length}字:

    {text[:4000]}  # 限制输入长度

    摘要应该:
    1. 包含主要观点
    2. 简洁明了
    3. 便于快速理解
    """

    result = await generate_text(
        prompt,
        max_tokens=1000,
        task_type=TaskType.GENERATION
    )

    return result["content"] if result["success"] else ""
```

### 示例3: 任务执行

**文件**: `backend/services/agent/task_executor.py`

```python
from backend.services.ai_service import generate_with_fallback

async def execute_task(task: str) -> dict:
    """执行Agent任务"""

    result = await generate_with_fallback(
        f"""
        请执行以下任务:
        {task}

        请详细说明你的思考和执行过程。
        """,
        max_retries=3,
        max_tokens=3000
    )

    if result["success"]:
        return {
            "status": "completed",
            "result": result["content"],
            "provider": result["provider"],
            "tokens": result["tokens"]
        }
    else:
        return {
            "status": "failed",
            "error": result["error"]
        }
```

---

## 📊 使用监控

### 查看Token池状态

```python
from backend.services.evolution.free_token_pool import get_free_token_pool

pool = get_free_token_pool()
status = pool.get_pool_status()

print(f"总额度: {status['total_quota']:,} tokens")
print(f"已使用: {status['total_used']:,} tokens")
print(f"剩余: {status['total_remaining']:,} tokens")
print(f"使用率: {status['usage_percentage']:.1f}%")

print("\n各provider状态:")
for name, info in status["providers"].items():
    if info["available"]:
        print(f"  {name}: {info['remaining']:,} tokens 剩余")
```

### 记录使用日志

```python
import logging

logger = logging.getLogger(__name__)

async def log_ai_usage(result: dict, prompt: str):
    """记录AI使用情况"""

    if result["success"]:
        logger.info(
            f"AI调用成功 | "
            f"Provider: {result['provider']} | "
            f"Tokens: {result['tokens']} | "
            f"延迟: {result['latency_ms']}ms | "
            f"提示词长度: {len(prompt)}"
        )
    else:
        logger.error(
            f"AI调用失败 | "
            f"错误: {result.get('error', 'Unknown')} | "
            f"提示词: {prompt[:100]}..."
        )
```

---

## ⚙️ 配置优化

### 1. 根据任务类型选择provider

```python
from backend.services.evolution.free_token_pool import TaskType

# 生成任务 - 使用GLM (快速)
await generate_text(prompt, task_type=TaskType.GENERATION)

# 推理任务 - 使用DeepSeek (强大)
await generate_text(prompt, task_type=TaskType.REASONING)

# 知识问答 - 使用千帆 (擅长中文)
await generate_text(prompt, task_type=TaskType.KNOWLEDGE)

# Agent任务 - 使用GLM Coding Plan
await generate_text(prompt, task_type=TaskType.TASK)
```

### 2. 设置复杂度

```python
# 简单任务 - 快速响应
await generate_text("你好", complexity="simple")

# 中等任务 - 平衡
await generate_text("总结这段文字", complexity="medium")

# 复杂任务 - 质量优先
await generate_text("解决这个数学难题", complexity="high")
```

---

## 🚀 快速开始

### 步骤1: 创建AI服务

```bash
# 创建服务文件
touch backend/services/ai_service.py
```

复制上面"方式2"的代码到 `ai_service.py`

### 步骤2: 在业务代码中使用

```python
# 在需要使用AI的地方导入
from backend.services.ai_service import chat, reason, code_review

# 使用
response = await chat("你好")
answer = await reason("这个数学题怎么解")
review = await code_review("def foo(): pass")
```

### 步骤3: 启动服务

```bash
# 重启灵知系统
systemctl restart zhineng-kb

# 或手动启动
python -m uvicorn backend.main:app --reload
```

---

## ✅ 验证集成

运行测试验证集成是否成功:

```bash
python -c "
import asyncio
from backend.services.ai_service import chat

async def test():
    response = await chat('你好，请介绍一下你自己')
    print(f'✅ AI响应: {response[:100]}...')

asyncio.run(test())
"
```

---

**集成完成后，您的系统将自动使用免费Token池，每月节省 ¥900+！**
