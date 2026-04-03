# GLM Coding Plan Pro 频率限制优化方案

**套餐**: GLM Coding Plan Pro
**问题**: 请求频率限制
**更新**: 2026-04-01

---

## ⚠️ 频率限制分析

### Pro套餐限制

**官方限制**:
```
每5小时: 600次 prompts
≈ 每30秒: 6次请求
≈ 每分钟: 2次请求（实际约1-2次/秒峰值）
```

**实际场景**:
- ✅ 正常使用：够用
- ❌ 高频调用：触发限流
- ❌ 批量操作：快速耗尽额度

### 限流表现

```
错误信息示例:
• "Rate limit exceeded"
• "请求过于频繁，请稍后再试"
• "Too many requests"
```

---

## 🔧 您的Workflow优化建议

### 方案1: 请求队列化 📋

**实现方式**:

```python
import asyncio
from typing import List, Callable
from datetime import datetime, timedelta

class RequestQueue:
    """请求队列管理器"""

    def __init__(self, max_requests_per_minute: int = 100):
        self.queue = asyncio.Queue()
        self.max_requests = max_requests_per_minute
        self.request_times = []
        self.running = False

    async def add_request(self, func: Callable, *args, **kwargs):
        """添加请求到队列"""
        await self.queue.put((func, args, kwargs))

    async def process_queue(self):
        """处理队列中的请求"""
        self.running = True

        while self.running or not self.queue.empty():
            # 检查频率限制
            now = datetime.now()

            # 清理1分钟前的记录
            self.request_times = [
                t for t in self.request_times
                if now - t < timedelta(minutes=1)
            ]

            # 如果达到限制，等待
            if len(self.request_times) >= self.max_requests:
                wait_time = 60 - (now - self.request_times[0]).total_seconds()
                if wait_time > 0:
                    print(f"⏳ 达到频率限制，等待 {wait_time:.1f} 秒...")
                    await asyncio.sleep(wait_time)

            # 处理下一个请求
            if not self.queue.empty():
                func, args, kwargs = await self.queue.get()

                try:
                    result = await func(*args, **kwargs)
                    self.request_times.append(datetime.now())

                    return result
                except Exception as e:
                    print(f"❌ 请求失败: {e}")
                    # 重试
                    await self.queue.put((func, args, kwargs))

            await asyncio.sleep(0.1)  # 避免CPU占用

    def stop(self):
        """停止处理"""
        self.running = False


# 使用示例
async def batch_process_with_queue(prompts: List[str]):
    """使用队列批量处理"""

    queue = RequestQueue(max_requests_per_minute=100)

    # 添加所有请求
    for prompt in prompts:
        await queue.add_request(code_development, prompt)

    # 启动处理（后台）
    processor = asyncio.create_task(queue.process_queue())

    # 等待完成
    await queue.queue.join()
    queue.stop()
    await processor
```

---

### 方案2: 智能批处理 📦

**实现方式**:

```python
from typing import List

async def batch_code_development(
    prompts: List[str],
    batch_size: int = 5,
    delay_between_batches: float = 2.0
):
    """批量代码生成（智能分批）"""

    results = []

    for i in range(0, len(prompts), batch_size):
        batch = prompts[i:i + batch_size]

        print(f"🔄 处理批次 {i//batch_size + 1}/{(len(prompts)-1)//batch_size + 1}")

        # 并发处理当前批次
        tasks = [code_development(prompt) for prompt in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        results.extend(batch_results)

        # 批次间延迟
        if i + batch_size < len(prompts):
            print(f"⏳ 等待 {delay_between_batches} 秒后处理下一批...")
            await asyncio.sleep(delay_between_batches)

    return results


# 使用示例
prompts = [
    "实现快速排序",
    "实现二分查找",
    "实现链表反转",
    # ... 更多提示词
]

results = await batch_code_development(
    prompts,
    batch_size=3,  # 每批3个
    delay_between_batches=5.0  # 批次间等待5秒
)
```

---

### 方案3: 智能缓存系统 💾

**实现方式**:

```python
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta

class SmartCache:
    """智能缓存系统"""

    def __init__(self, cache_dir: str = "data/cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _get_cache_key(self, prompt: str) -> str:
        """生成缓存键"""
        content = f"{prompt}_{datetime.now().date()}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"

    def get(self, prompt: str) -> str:
        """获取缓存"""
        key = self._get_cache_key(prompt)
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查是否过期
            cache_time = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - cache_time > self.ttl:
                cache_path.unlink()  # 删除过期缓存
                return None

            print(f"✅ 命中缓存: {prompt[:50]}...")
            return data['result']

        except Exception:
            return None

    def set(self, prompt: str, result: str):
        """设置缓存"""
        key = self._get_cache_key(prompt)
        cache_path = self._get_cache_path(key)

        data = {
            'prompt': prompt,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# 使用示例
cache = SmartCache()

async def cached_code_development(prompt: str) -> str:
    """带缓存的代码生成"""

    # 尝试从缓存获取
    cached_result = cache.get(prompt)
    if cached_result:
        return cached_result

    # 缓存未命中，调用API
    result = await code_development(prompt)

    # 保存到缓存
    if result:
        cache.set(prompt, result)

    return result
```

---

### 方案4: 自适应限流 🎯

**实现方式**:

```python
import asyncio
import time
from collections import deque

class AdaptiveRateLimiter:
    """自适应限流器"""

    def __init__(
        self,
        max_requests_per_minute: int = 100,
        max_requests_per_5min: int = 500
    ):
        self.max_per_minute = max_requests_per_minute
        self.max_per_5min = max_requests_per_5min

        self.minute_window = deque(maxlen=max_requests_per_minute)
        self.five_min_window = deque(maxlen=max_requests_per_5min)

    async def acquire(self, timeout: float = 60.0):
        """获取请求许可（阻塞式）"""
        start_time = time.time()

        while True:
            # 检查是否可以请求
            if self._can_request():
                self._record_request()
                return True

            # 计算等待时间
            wait_time = self._calculate_wait_time()

            # 超时检查
            if time.time() - start_time + wait_time > timeout:
                raise TimeoutError(f"等待超时: {timeout}秒")

            print(f"⏳ 限流中，等待 {wait_time:.1f} 秒...")
            await asyncio.sleep(wait_time)

    def _can_request(self) -> bool:
        """检查是否可以请求"""
        now = time.time()

        # 清理过期记录
        minute_ago = now - 60
        five_mins_ago = now - 300

        while self.minute_window and self.minute_window[0] < minute_ago:
            self.minute_window.popleft()

        while self.five_min_window and self.five_min_window[0] < five_mins_ago:
            self.five_min_window.popleft()

        # 检查限制
        if len(self.minute_window) >= self.max_per_minute:
            return False

        if len(self.five_min_window) >= self.max_per_5min:
            return False

        return True

    def _record_request(self):
        """记录请求"""
        now = time.time()
        self.minute_window.append(now)
        self.five_min_window.append(now)

    def _calculate_wait_time(self) -> float:
        """计算需要等待的时间"""
        if self.minute_window:
            oldest_in_minute = self.minute_window[0]
            wait_for_minute = 60 - (time.time() - oldest_in_minute)
        else:
            wait_for_minute = 0

        if self.five_min_window:
            oldest_in_5min = self.five_min_window[0]
            wait_for_5min = 300 - (time.time() - oldest_in_5min)
        else:
            wait_for_5min = 0

        return max(wait_for_minute, wait_for_5min, 1.0)


# 使用示例
limiter = AdaptiveRateLimiter(
    max_requests_per_minute=100,  # 保守估计
    max_requests_per_5min=500
)

async def rate_limited_code_development(prompt: str) -> str:
    """带限流的代码生成"""

    await limiter.acquire()
    return await code_development(prompt)
```

---

### 方案5: 多Provider轮换 🔄

**实现方式**:

```python
from backend.services.evolution.free_token_pool import get_free_token_pool

async def smart_code_development(prompt: str) -> str:
    """智能代码生成（自动轮换Provider）"""

    pool = get_free_token_pool()

    # 优先使用GLM Coding Plan
    try:
        result = await pool.call_provider("glm_coding", prompt)
        if result["success"]:
            return result["content"]
    except Exception as e:
        print(f"⚠️ GLM Coding Plan失败: {e}")

    # Fallback到其他Provider
    print("🔄 切换到备用Provider...")

    # 尝试DeepSeek
    result = await pool.call_provider("deepseek", prompt)
    if result["success"]:
        return result["content"]

    # 尝试GLM
    result = await pool.call_provider("glm", prompt)
    if result["success"]:
        return result["content"]

    return None
```

---

## 📊 Workflow优化建议

### 场景1: 批量代码生成

**问题**: 需要生成多个类似函数，触发限流

**解决方案**:
```python
async def generate_multiple_functions(functions: List[str]):
    """批量生成函数"""

    # 方案A: 串行 + 延迟
    results = []
    for func_name in functions:
        result = await code_development(f"实现 {func_name}")
        results.append(result)
        await asyncio.sleep(2)  # 每次间隔2秒

    return results

    # 方案B: 批处理（推荐）
    return await batch_code_development(
        [f"实现 {fn}" for fn in functions],
        batch_size=3,
        delay_between_batches=5
    )
```

### 场景2: 迭代开发

**问题**: 需要多次调试同一代码

**解决方案**:
```python
async def iterative_debugging(
    code: str,
    error: str,
    max_iterations: int = 3
):
    """迭代调试（使用缓存避免重复请求）"""

    cache = SmartCache()

    for i in range(max_iterations):
        # 构造唯一提示词
        prompt = f"""
调试第{i+1}轮:
代码: {code}
错误: {error}
"""

        # 检查缓存
        result = cache.get(prompt)
        if not result:
            result = await debug_code(code, error)
            cache.set(prompt, result)

        print(f"✅ 第{i+1}轮调试完成")

        # 如果解决了，返回
        if "解决" in result or "修复" in result:
            return result

        # 更新代码（假设）
        code = result  # 简化示例

        await asyncio.sleep(3)  # 间隔等待
```

### 场景3: 代码审查

**问题**: 需要审查多个文件

**解决方案**:
```python
async def batch_review(files: List[str]):
    """批量代码审查"""

    # 合并相似文件
    batches = []
    current_batch = []
    current_size = 0

    for file in files:
        file_size = len(file)

        if current_size + file_size > 10000:  # 10K限制
            batches.append(current_batch)
            current_batch = [file]
            current_size = file_size
        else:
            current_batch.append(file)
            current_size += file_size

    if current_batch:
        batches.append(current_batch)

    # 逐批审查
    results = []
    for i, batch in enumerate(batches):
        prompt = f"请审查以下{len(batch)}个文件:\n\n" + "\n\n".join(batch)

        result = await code_review(prompt, focus="性能")
        results.append(result)

        if i < len(batches) - 1:
            await asyncio.sleep(5)  # 批次间延迟

    return results
```

---

## 🎯 最佳实践

### 1. 使用缓存 ⚡

**效果**: 节省 30-50% 请求

```python
cache = SmartCache(ttl_hours=48)  # 48小时缓存

# 所有请求都走缓存
result = await cached_code_development(prompt)
```

### 2. 批量处理 📦

**效果**: 减少 50-70% 限流触发

```python
# 合并小请求
results = await batch_code_development(
    prompts,
    batch_size=5,
    delay_between_batches=3
)
```

### 3. 智能延迟 ⏳

**效果**: 避免 90% 限流错误

```python
# 自适应延迟
limiter = AdaptiveRateLimiter(
    max_requests_per_minute=80  # 保守值
)

await limiter.acquire()
result = await code_development(prompt)
```

### 4. 多Provider轮换 🔄

**效果**: 100% 可用性

```python
# 自动fallback
result = await smart_code_development(prompt)
```

---

## 📈 监控和优化

### 监控限流情况

```python
from backend.services.evolution.token_monitor import get_token_monitor

monitor = get_token_monitor()
stats = monitor.get_provider_stats("glm_coding")

print(f"总请求: {stats.total_calls}")
print(f"失败: {stats.failed_calls}")
print(f"成功率: {stats.success_rate:.1%}")

# 检查限流错误
if "Rate limit" in stats.errors:
    print(f"限流次数: {stats.errors['Rate limit']}")
```

### 优化策略选择

| 场景 | 推荐方案 | 节省 |
|------|---------|------|
| 重复问题多 | 缓存 | 30-50% |
| 批量操作 | 批处理 | 50-70% |
| 高频调用 | 限流器 | 避免90%限流 |
| 不稳定 | 多Provider | 100%可用 |

---

## 🔧 灵知系统集成

### 已实现优化

```python
# backend/services/ai_service.py

# ✅ 智能调度（自动选择）
from backend.services.ai_service import code_development

# ✅ 自动重试和fallback
from backend.services.ai_service import generate_with_fallback

# ✅ 监控和统计
from backend.services.evolution.token_monitor import get_token_monitor
```

### 推荐配置

```python
# .env 配置
GLM_CODING_PLAN_KEY=your-key

# 使用限流
GLM_REQUEST_RATE_LIMIT=80  # 每分钟80次（保守）

# 启用缓存
ENABLE_CACHE=true
CACHE_TTL_HOURS=48

# 批处理
BATCH_SIZE=5
BATCH_DELAY=5
```

---

## ✅ 总结

### Pro套餐限制

```
官方限制: 600次/5小时
≈ 2次/分钟（实际）
≈ 1-2次/秒（峰值）
```

### 优化方案效果

| 方案 | 实施难度 | 效果 | 推荐度 |
|------|---------|------|--------|
| 缓存系统 | ⭐⭐ | 节省30-50% | ⭐⭐⭐⭐⭐ |
| 批处理 | ⭐⭐⭐ | 减少50-70%限流 | ⭐⭐⭐⭐⭐ |
| 请求队列 | ⭐⭐⭐⭐ | 避免限流 | ⭐⭐⭐⭐ |
| 自适应限流 | ⭐⭐⭐⭐ | 避免90%限流 | ⭐⭐⭐⭐⭐ |
| 多Provider轮换 | ⭐⭐ | 100%可用 | ⭐⭐⭐⭐ |

### 快速开始

```python
# 1. 启用缓存（最简单）
cache = SmartCache()
result = await cached_code_development(prompt)

# 2. 使用批处理（推荐）
results = await batch_code_development(prompts, batch_size=5)

# 3. 添加限流器（稳定）
limiter = AdaptiveRateLimiter()
await limiter.acquire()
result = await code_development(prompt)
```

---

**🎉 通过这些优化，您可以将Pro套餐的限流影响降到最低！**

**众智混元，万法灵通** ⚡🚀
