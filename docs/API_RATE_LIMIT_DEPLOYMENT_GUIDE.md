# API速率限制解决方案部署指南

**目标**: 解决GLM API 1302速率限制错误
**预期效果**: 从每小时5-10次降至<1次

---

## 一、快速部署（5分钟）

### Step 1: 验证Redis连接

```bash
# 检查Redis是否运行
docker-compose ps redis

# 如果没有运行，启动Redis
docker-compose up -d redis
```

### Step 2: 更新.env配置

```bash
# 编辑 .env 文件
nano .env

# 添加以下配置（如果还没有）
REDIS_URL=redis://localhost:6379/0
DEEPSEEK_API_KEY=your_api_key_here

# 速率限制配置
GLM_API_MAX_CALLS_PER_MINUTE=50
```

### Step 3: 测试速率限制器

```python
# 测试速率限制器是否工作
cd /home/ai/zhineng-knowledge-system

# 启动Python
python3 - <<'EOF'
from common.rate_limiter import DistributedRateLimiter

# 初始化
limiter = DistributedRateLimiter(
    max_calls=5,  # 测试用：每分钟5次
    period=60
)

# 测试获取许可
if limiter.acquire("test", timeout=10):
    print("✅ Rate limiter is working!")
else:
    print("❌ Rate limiter timeout")
EOF
```

**预期输出**: `✅ Rate limiter is working!`

### Step 4: 集成到现有API调用

**找到所有调用LLM API的地方**:

1. 推理模块: `backend/services/reasoning/base.py`
2. 推理模块: `backend/services/reasoning/cot.py`
3. 推理模块: `backend/services/reasoning/react.py`
4. 推理模块: `backend/services/reasoning/graph_rag.py`

**在每个API调用前添加**:

```python
from common.llm_api_wrapper import get_llm_client, GLMRateLimitException

# 在API调用处
async def my_api_function(prompt: str):
    client = get_llm_client()

    try:
        response = await client.call_api(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        return response
    except GLMRateLimitException as e:
        # 速率限制错误，已自动重试5次
        logger.error(f"API call failed after retries: {e}")
        raise
```

---

## 二、集成示例（针对推理模块）

### 2.1 更新BaseReasoner

**文件**: `backend/services/reasoning/base.py`

**修改位置**: `__init__`方法

```python
from common.llm_api_wrapper import get_llm_client, GLMRateLimitException

class BaseReasoner(ABC):
    """推理器基类"""

    def __init__(self, api_key: str = "", api_url: str = ""):
        """初始化推理器"""
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = "base"

        # 添加：获取LLM客户端（带速率限制）
        try:
            self.llm_client = get_llm_client(
                api_key=api_key or self._get_default_api_key(),
                api_url=api_url
            )
        except Exception as e:
            logger.warning(f"Failed to initialize LLM client: {e}")
            self.llm_client = None
```

### 2.2 更新具体的推理器

**文件**: `backend/services/reasoning/cot.py`

**修改位置**: `reason`方法

```python
async def reason(
    self,
    question: str,
    context: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> ReasoningResult:
    """执行CoT推理"""

    start_time = time.time()
    query_type = self.analyze_query(question)

    # 添加：使用带速率限制的API调用
    if self.llm_client:
        try:
            # 构建消息
            messages = self._build_messages(question, context, query_type)

            # 调用API（自动处理速率限制和重试）
            response = await self.llm_client.call_api(
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=30
            )

            # 解析响应
            answer = response["choices"][0]["message"]["content"]

        except GLMRateLimitException as e:
            logger.error(f"CoT reasoning failed due to rate limit: {e}")
            # 返回降级结果
            return ReasoningResult(
                answer="抱歉，由于API调用频繁，请稍后重试。",
                query_type=query_type,
                confidence=0.0,
                reasoning_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"CoT reasoning failed: {e}")
            raise
    else:
        # 原有的API调用逻辑
        # ...
        pass
```

---

## 三、启用监控（今天完成）

### Step 1: 添加监控初始化

**文件**: `backend/main.py` 或 `backend/core/lifespan.py`

```python
from common.api_monitor import get_api_monitor

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("Starting API monitoring...")

    # 在后台任务中定期输出统计
    async def log_stats():
        while True:
            await asyncio.sleep(300)  # 每5分钟输出一次
            stats = get_api_monitor().get_stats()
            logger.info(f"API Stats: {stats}")

    # 启动监控任务
    asyncio.create_task(log_stats())

    yield

    # 关闭时
    logger.info("Shutting down...")
```

### Step 2: 在API调用处添加监控

```python
from common.api_monitor import record_api_call

# 在API调用处
async def call_api():
    start_time = time.time()

    try:
        response = await api_call()
        tokens_used = response.get("usage", {}).get("total_tokens", 0)

        # 记录成功的调用
        record_api_call(
            success=True,
            is_rate_limit=False,
            tokens_used=tokens_used,
            response_time=time.time() - start_time
        )

        return response

    except Exception as e:
        # 检查是否是1302错误
        is_rate_limit = "1302" in str(e) or "rate limit" in str(e).lower()

        # 记录失败
        record_api_call(
            success=False,
            is_rate_limit=is_rate_limit,
            tokens_used=0,
            response_time=time.time() - start_time
        )

        raise
```

### Step 3: 添加监控端点

**创建文件**: `backend/api/v1/monitoring.py`

```python
"""API监控端点"""

from fastapi import APIRouter
from common.api_monitor import get_api_monitor

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@router.get("/stats")
async def get_api_stats():
    """获取API统计信息"""
    return get_api_monitor().get_stats()

@router.get("/rate-limit-stats")
async def get_rate_limit_stats(window_minutes: int = 60):
    """获取速率限制统计"""
    return get_api_monitor().get_rate_limit_stats(window_minutes)

@router.post("/reset-stats")
async def reset_stats():
    """重置统计信息"""
    get_api_monitor().reset_stats()
    return {"status": "success", "message": "Stats reset"}
```

### Step 4: 注册监控路由

**文件**: `backend/api/v1/__init__.py`

```python
# 添加导入
from api.v1.monitoring import router as monitoring_router

# 注册路由
app.include_router(monitoring_router)
```

---

## 四、验证部署

### 验证清单

运行以下命令验证部署：

```bash
# 1. 检查文件是否存在
ls -la backend/common/rate_limiter.py
ls -la backend/common/llm_api_wrapper.py
ls -la backend/common/api_monitor.py

# 2. 测试导入
python3 -c "from backend.common.rate_limiter import DistributedRateLimiter; print('✅ Import OK')"

# 3. 测试Redis连接
python3 -c "
from backend.common.rate_limiter import DistributedRateLimiter
limiter = DistributedRateLimiter(max_calls=5, period=60)
if limiter.acquire('test', timeout=5):
    print('✅ Redis connection OK')
else:
    print('❌ Redis connection failed')
"

# 4. 检查监控端点
curl http://localhost:8001/api/v1/monitoring/stats
```

### 预期输出

```
✅ Import OK
✅ Redis connection OK
{
  "total_calls": 0,
  "successful_calls": 0,
  "failed_calls": 0,
  "rate_limit_hits": 0,
  "total_tokens": 0,
  ...
}
```

---

## 五、监控效果

### 部署前

```
每小时1302错误: 5-10次
API成功率: 95-98%
请求峰值: 不受控
```

### 部署后（预期）

```
每小时1302错误: <1次
API成功率: >99.5%
请求峰值: 平滑控制
监控可见: 实时统计
```

---

## 六、故障排查

### 问题1: Redis连接失败

**症状**: `Redis connection failed`

**解决**:
```bash
# 检查Redis是否运行
docker-compose ps redis

# 查看Redis日志
docker-compose logs redis

# 重启Redis
docker-compose restart redis
```

### 问题2: 速率限制器不工作

**症状**: 仍然出现1302错误

**解决**:
1. 降低`max_calls_per_minute`值（如50→30）
2. 检查是否有多个进程未使用速率限制器
3. 检查Redis中是否有旧的速率限制数据

```bash
# 清空Redis中的速率限制数据
redis-cli FLUSHDB
```

### 问题3: 性能下降

**症状**: API调用变慢

**原因**: 速率限制器在等待

**解决**:
1. 这是正常行为，避免触发1302错误
2. 如果过于频繁，可以考虑提高`max_calls_per_minute`
3. 优化代码，减少不必要的API调用

---

## 七、后续优化

### 短期（本周）

- [ ] 完成所有推理模块的集成
- [ ] 启用监控端点
- [ ] 配置告警（邮件/钉钉/企业微信）
- [ ] 验证效果（观察1302错误频率）

### 中期（下周）

- [ ] 实现请求队列
- [ ] 添加智能调度
- [ ] 优化并发策略
- [ ] 成本优化（缓存、批量处理）

### 长期（下月）

- [ ] 自适应速率调整
- [ ] 预测性限流
- [ ] 监控dashboard
- [ ] 自动告警和自修复

---

## 八、总结

### 核心改进

1. ✅ **分布式速率限制** - 跨进程协调，避免峰值
2. ✅ **智能重试机制** - 自动处理1302错误
3. ✅ **实时监控** - 追踪API调用和错误
4. ✅ **告警机制** - 异常情况及时通知

### 预期效果

- 📉 1302错误: 每小时5-10次 → <1次
- 📈 API成功率: 95-98% → >99.5%
- ⏱️ 请求平滑: 峰值控制，避免突发
- 📊 可视化: 实时监控，数据驱动

---

**部署完成后，请运行验证步骤确认效果。**
