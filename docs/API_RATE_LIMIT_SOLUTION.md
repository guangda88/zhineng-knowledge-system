# API速率限制解决方案

**问题**: GLM API速率限制（错误代码1302）
**错误频率**: 每小时5-10次
**本周token消费**: 1,460,186,850（约14.6亿）

---

## 一、问题诊断

### 1.1 当前问题

- ❌ 多进程/线程无协调并发调用API
- ❌ 没有全局速率限制
- ❌ 每小时触发1302错误5-10次
- ❌ 没有统一的重试机制

### 1.2 Token消费分析

| 指标 | 数值 |
|------|------|
| 本周消费 | 14.6亿 tokens |
| 日均消费 | ~2.08亿 tokens |
| 时均消费 | ~866万 tokens |
| 分均消费 | ~14.4万 tokens |
| 秒均消费 | ~2400 tokens |

**结论**: 消费量很大，但如果合理分布，应该在API限制范围内。问题在于**并发峰值**。

---

## 二、立即解决方案（今天部署）

### 2.1 使用分布式速率限制器

**文件**: `backend/common/rate_limiter.py`（已创建）

**特性**:
- ✅ 基于Redis的全局速率限制
- ✅ 跨进程/线程协调
- ✅ 阻塞等待机制
- ✅ 超时控制

**使用示例**:

```python
from common.rate_limiter import DistributedRateLimiter

# 初始化全局限流器
limiter = DistributedRateLimiter(
    redis_url="redis://localhost:6379/0",
    max_calls=50,  # 每分钟最多50次调用（保守值）
    period=60,
    burst=10
)

# 在API调用前使用
def call_glm_api(prompt: str):
    # 等待获取许可（自动控制速率）
    if limiter.acquire("glm_api", timeout=30):
        # 执行API调用
        response = glm_api.call(prompt)
        return response
    else:
        raise Exception("API rate limit timeout")
```

### 2.2 添加智能重试机制

```python
import time
import random
import logging

logger = logging.getLogger(__name__)

class GLMRateLimitHandler:
    """GLM API速率限制处理器"""

    # 1302错误的重试配置
    RETRY_CONFIG = {
        "max_retries": 5,
        "initial_delay": 2.0,  # 初始延迟2秒
        "max_delay": 60.0,  # 最大延迟60秒
        "exponential_base": 2,  # 指数退避基数
    }

    @classmethod
    def call_with_retry(cls, api_func, *args, **kwargs):
        """
        带智能重试的API调用

        Args:
            api_func: API调用函数
            args, kwargs: 传递给API函数的参数

        Returns:
            API响应

        Raises:
            Exception: 重试失败后抛出最后一个异常
        """
        last_exception = None

        for attempt in range(cls.RETRY_CONFIG["max_retries"]):
            try:
                return api_func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                error_code = getattr(e, "code", None)
                error_msg = str(e)

                # 只对1302错误（速率限制）进行重试
                if "1302" not in error_msg:
                    # 其他错误直接抛出
                    raise

                # 1302错误：指数退避重试
                if attempt < cls.RETRY_CONFIG["max_retries"] - 1:
                    # 计算延迟时间（指数退避 + 随机抖动）
                    base_delay = cls.RETRY_CONFIG["initial_delay"]
                    exponential = cls.RETRY_CONFIG["exponential_base"] ** attempt
                    jitter = random.uniform(0, 1)
                    delay = min(
                        base_delay * exponential + jitter,
                        cls.RETRY_CONFIG["max_delay"]
                    )

                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}/{cls.RETRY_CONFIG['max_retries']}), "
                        f"retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                else:
                    logger.error(
                        f"Rate limit retry exhausted after {cls.RETRY_CONFIG['max_retries']} attempts"
                    )

        # 重试失败
        raise last_exception
```

### 2.3 实现请求队列

```python
import queue
import threading
from typing import Callable, Any

class APIRequestQueue:
    """API请求队列（平滑请求速率）"""

    def __init__(self, rate_per_second: float = 1.0):
        """
        初始化请求队列

        Args:
            rate_per_second: 每秒处理的请求数
        """
        self.queue = queue.Queue()
        self.rate_per_second = rate_per_second
        self.interval = 1.0 / rate_per_second
        self.workers = []
        self.running = False

    def submit(self, func: Callable, *args, **kwargs) -> Any:
        """
        提交任务到队列

        Args:
            func: 要执行的函数
            args, kwargs: 函数参数

        Returns:
            函数执行结果
        """
        result = queue.Queue()

        def task():
            try:
                output = func(*args, **kwargs)
                result.put(output)
            except Exception as e:
                result.put(e)

        self.queue.put(task)
        return result.get()

    def start(self, num_workers: int = 1):
        """启动工作线程"""
        self.running = True

        for i in range(num_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)

        logger.info(f"Started {num_workers} queue workers")

    def stop(self):
        """停止工作线程"""
        self.running = False
        for worker in self.workers:
            worker.join()

    def _worker(self):
        """工作线程"""
        while self.running:
            try:
                task = self.queue.get(timeout=1)
                if task is None:
                    continue

                task()

                # 控制速率
                time.sleep(self.interval)

            except Exception as e:
                logger.error(f"Worker error: {e}")
```

---

## 三、监控和日志（今天部署）

### 3.1 添加速率限制监控

```python
import logging
from datetime import datetime

class RateLimitMonitor:
    """速率限制监控"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rate_limit_hits = 0
        self.total_calls = 0
        self.start_time = datetime.now()

    def record_call(self, success: bool, is_rate_limit: bool = False):
        """记录API调用"""
        self.total_calls += 1

        if is_rate_limit:
            self.rate_limit_hits += 1
            self.logger.warning(f"Rate limit hit! Total: {self.rate_limit_hits}/{self.total_calls}")

    def get_stats(self):
        """获取统计信息"""
        uptime = (datetime.now() - self.start_time).total_seconds()

        return {
            "total_calls": self.total_calls,
            "rate_limit_hits": self.rate_limit_hits,
            "hit_rate": f"{(self.rate_limit_hits / self.total_calls * 100):.2f}%" if self.total_calls > 0 else "0%",
            "uptime_seconds": uptime,
            "calls_per_minute": self.total_calls / (uptime / 60) if uptime > 0 else 0
        }
```

### 3.2 添加告警机制

```python
class RateLimitAlertManager:
    """速率限制告警管理器"""

    def __init__(self, threshold_per_hour: int = 20):
        """
        初始化告警管理器

        Args:
            threshold_per_hour: 每小时告警阈值
        """
        self.threshold = threshold_per_hour
        self.reset_time = datetime.now()
        self.hit_count = 0

    def check_and_alert(self, is_rate_limit: bool):
        """检查并告警"""
        if is_rate_limit:
            self.hit_count += 1

            # 检查是否超过阈值
            time_passed = (datetime.now() - self.reset_time).total_seconds()

            if time_passed >= 3600:  # 1小时
                if self.hit_count >= self.threshold:
                    self.send_alert(self.hit_count)

                # 重置计数器
                self.hit_count = 0
                self.reset_time = datetime.now()

    def send_alert(self, count: int):
        """发送告警"""
        import smtplib
        from email.mime.text import MIMEText

        # 发送邮件告警（示例）
        msg = MIMEText(f"""
        Rate limit alert!

        In the last hour, there were {count} rate limit errors.

        Please check:
        1. Are there too many concurrent processes?
        2. Should we adjust the rate limit settings?
        3. Are there any runaway processes?

        Time: {datetime.now()}
        """)

        msg['Subject'] = f'⚠️ API Rate Limit Alert: {count} hits/hour'
        msg['From'] = 'alert@example.com'
        msg['To'] = 'admin@example.com'

        # 发送邮件（需要配置SMTP）
        # smtp.send_message(msg)

        # 或者使用其他告警渠道（钉钉、企业微信、Slack等）
```

---

## 四、配置优化（本周完成）

### 4.1 环境变量配置

```bash
# .env
# API速率限制配置
GLM_API_RATE_LIMIT_ENABLED=true
GLM_API_MAX_CALLS_PER_MINUTE=50
GLM_API_RATE_LIMIT_TIMEOUT=30
GLM_API_RETRY_ENABLED=true
GLM_API_MAX_RETRIES=5
```

### 4.2 分级速率限制

```python
class TieredRateLimiter:
    """分级速率限制器"""

    TIERS = {
        "free": {
            "max_calls": 30,
            "period": 60,
            "priority": 3
        },
        "standard": {
            "max_calls": 60,
            "period": 60,
            "priority": 2
        },
        "premium": {
            "max_calls": 120,
            "period": 60,
            "priority": 1
        }
    }

    def __init__(self, tier: str = "standard"):
        config = self.TIERS.get(tier, self.TIERS["standard"])
        self.limiter = DistributedRateLimiter(
            max_calls=config["max_calls"],
            period=config["period"]
        )
```

---

## 五、部署步骤

### Step 1: 立即部署（今天）

1. **添加速率限制器**
   ```bash
   # 文件已创建：backend/common/rate_limiter.py
   # 需要在调用API的地方集成
   ```

2. **添加监控和日志**
   ```bash
   # 在所有API调用处添加监控
   monitor.record_call(success=True, is_rate_limit=False)
   ```

3. **启用重试机制**
   ```bash
   # 在API调用处包装重试逻辑
   response = GLMRateLimitHandler.call_with_retry(api_func, prompt)
   ```

### Step 2: 本周优化

1. **实现请求队列**
   - 将API请求放入队列
   - 平滑处理速率

2. **添加告警**
   - 每小时超过20次1302错误时告警

3. **优化并发策略**
   - 减少并发数
   - 错峰处理

### Step 3: 长期优化

1. **实现智能调度**
   - 根据API响应动态调整速率
   - 预测并避免峰值

2. **成本优化**
   - 缓存常见查询结果
   - 批量处理请求

3. **监控dashboard**
   - 实时显示API调用速率
   - 可视化token消费

---

## 六、验证方案

### 验证清单

- [ ] 速率限制器已集成到所有API调用点
- [ ] 监控已启用，可以看到调用统计
- [ ] 重试机制已实现
- [ ] 1302错误有详细日志
- [ ] 告警机制已配置
- [ ] 配置了合理的速率限制阈值

### 成功标准

- [ ] 1302错误从每小时5-10次降至<1次
- [ ] API调用成功率>99%
- [ ] 可以看到实时监控数据
- [ ] 有清晰的告警机制

---

## 七、紧急处理（如果问题严重）

如果1302错误持续严重影响业务：

1. **立即降低并发**
   ```python
   # 将并发数从N降低到N/2
   max_workers = max_workers // 2
   ```

2. **添加固定延迟**
   ```python
   time.sleep(0.5)  # 每次API调用前等待500ms
   ```

3. **维护窗口**
   - 避开高峰时段（如工作时间）
   - 批量任务安排在夜间或周末

---

**建议**: 优先部署分布式速率限制器和重试机制，这两个方案可以立即解决大部分问题。
