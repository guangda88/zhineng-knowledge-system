# 灵知系统模型集成与Token优化方案

**日期**: 2026-04-01
**文档版本**: v1.0
**状态**: 完整分析与优化方案

---

## 📊 第一部分：模型集成现状

### 1. 外部模型API集成

#### 已集成的API服务（5个）

| API提供商 | 模型 | 用途 | API密钥状态 | 成本 |
|-----------|------|------|-------------|------|
| **混元（腾讯）** | hunyuan-lite | QA、播客生成 | ⚠️ 需配置 | ¥0.008/千tokens |
| **豆包（字节）** | doubao-pro | 通用问答 | ⚠️ 需配置 | ¥0.012/千tokens |
| **DeepSeek** | deepseek-chat | 代码、推理 | ⚠️ 需配置 | ¥0.001/千tokens |
| **GLM（智谱）** | glm-4 | 通用对话 | ⚠️ 需配置 | ¥0.01/千tokens |
| **灵知系统** | RAG-v1 | 内部RAG系统 | ✅ 已实现 | 内部计算 |

#### API调用架构

```
MultiAIAdapter（统一适配器）
├── LingzhiAdapter（内部RAG）
├── HunyuanAdapter（腾讯混元）
├── DoubaoAdapter（字节豆包）
├── DeepSeekAdapter（DeepSeek）
└── GLMAdapter（智谱GLM）
```

**特性**:
- ✅ 并行调用多个API
- ✅ 智能降级（API失败时使用mock）
- ✅ 超时控制（30秒）
- ✅ 统一响应格式

### 2. 本地模型部署

#### 已部署的本地模型（1个）

| 模型名称 | 类型 | 用途 | 部署状态 | 资源需求 |
|---------|------|------|---------|---------|
| **BGE-M3** | Embedding | 文本向量化 | ✅ 运行中 | 2GB+ GPU/内存 |

**BGE-M3 详细信息**:
- **模型**: BAAI/bge-m3
- **功能**: 文本嵌入向量生成
- **向量维度**: 1024维
- **支持语言**: 中文、多语言
- **部署方式**: FastAPI独立服务
- **服务端口**: 8001
- **设备**: CUDA（如果可用）或CPU

**API端点**:
```
POST /embed - 单文本嵌入
POST /embed_batch - 批量文本嵌入
GET /health - 健康检查
GET /info - 模型信息
```

#### 音频转写模型

| 模型 | 类型 | 用途 | 状态 |
|------|------|------|------|
| **Whisper** | 本地 | 音频转文本 | ✅ 可用 |
| **Cohere** | API | 音频转文本 | ⚠️ 需配置 |
| **听悟（阿里）** | API | 音频转文本 | ⚠️ 需配置 |

---

## 💰 第二部分：Token消费问题分析

### 当前Token使用情况（估算）

#### 日均消费场景

| 场景 | 调用次数/天 | 平均tokens/次 | 日消费tokens | 成本/天 |
|------|-------------|---------------|--------------|---------|
| 用户问答 | 1,000 | 500 | 500,000 | ¥5-15 |
| 文档检索 | 500 | 1,000 | 500,000 | ¥5-10 |
| 对比学习 | 100 | 5,000 | 500,000 | ¥1-5 |
| 音频转写 | 50 | 10,000 | 500,000 | ¥5-20 |
| **总计** | - | - | **2,500,000** | **¥16-50** |

#### 月度成本估算

- **乐观情况**: ¥16/天 × 30 = **¥480/月**
- **实际情况**: ¥30/天 × 30 = **¥900/月**
- **悲观情况**: ¥50/天 × 30 = **¥1,500/月**

### 成本驱动因素

1. **并发调用** - 多个API同时调用同一请求
2. **长上下文** - RAG检索包含大量文档片段
3. **对比学习** - 每次调用4-5个API进行对比
4. **重试机制** - 失败时自动重试增加消耗
5. **无缓存** - 相同问题重复处理

---

## 🚀 第三部分：Token优化方案

### 方案1：智能Token追踪系统（P0）✅

#### 实施目标

- 实时监控各provider的token使用
- 设置每日预算上限
- 超预算自动切换或降级

#### 实施方案

```python
class TokenUsageTracker:
    """Token使用追踪器"""

    def __init__(self):
        self.daily_budget = {
            "hunyuan": 1_000_000,      # 混元：100万tokens/天
            "doubao": 500_000,         # 豆包：50万tokens/天
            "deepseek": 3_000_000,     # DeepSeek：300万tokens/天
            "glm": 500_000,            # GLM：50万tokens/天
        }
        self.daily_usage = {k: 0 for k in self.daily_budget}
        self.cost_per_1k = {
            "hunyuan": 0.008,
            "doubao": 0.012,
            "deepseek": 0.001,
            "glm": 0.01,
        }

    async def track_usage(
        self,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int
    ):
        """追踪使用量"""
        total = prompt_tokens + completion_tokens
        self.daily_usage[provider] += total

        # 检查预算
        if self.daily_usage[provider] > self.daily_budget[provider]:
            logger.warning(f"{provider} 超预算！已用: {self.daily_usage[provider]}")
            return False  # 超预算
        return True

    def get_daily_cost(self) -> float:
        """计算每日成本"""
        total = 0
        for provider, usage in self.daily_usage.items():
            cost = (usage / 1000) * self.cost_per_1k[provider]
            total += cost
        return total

    def get_usage_report(self) -> Dict:
        """获取使用报告"""
        return {
            "date": datetime.now().date(),
            "usage_by_provider": self.daily_usage,
            "budget_by_provider": self.daily_budget,
            "budget_remaining": {
                k: self.daily_budget[k] - v
                for k, v in self.daily_usage.items()
            },
            "estimated_daily_cost": self.get_daily_cost(),
        }
```

**预期效果**:
- ✅ 实时成本监控
- ✅ 超预算自动告警
- ✅ 防止意外超支
- **成本降低**: 20-30%

---

### 方案2：智能缓存系统（P0）✅

#### 实施目标

- 缓存常见问题的回答
- 减少重复API调用
- L1（内存）+ L2（Redis）双层缓存

#### 实施方案

```python
class IntelligentCache:
    """智能缓存系统"""

    def __init__(self):
        # L1缓存：内存（热数据）
        self.l1_cache = LRUCache(maxsize=1000)
        self.l1_ttl = 300  # 5分钟

        # L2缓存：Redis（持久化）
        self.redis_client = redis.Redis()
        self.l2_ttl = 3600  # 1小时

    async def get_cached_response(
        self,
        question: str,
        provider: str
    ) -> Optional[str]:
        """获取缓存响应"""

        cache_key = self._generate_cache_key(question, provider)

        # 先查L1
        cached = self.l1_cache.get(cache_key)
        if cached:
            logger.info(f"L1缓存命中: {cache_key}")
            return cached

        # 再查L2
        cached = await self.redis_client.get(cache_key)
        if cached:
            logger.info(f"L2缓存命中: {cache_key}")
            # 回写L1
            self.l1_cache.put(cache_key, cached)
            return cached

        return None

    async def set_cached_response(
        self,
        question: str,
        provider: str,
        response: str
    ):
        """缓存响应"""
        cache_key = self._generate_cache_key(question, provider)

        # 写L1
        self.l1_cache.put(cache_key, response)

        # 写L2
        await self.redis_client.setex(
            cache_key,
            self.l2_ttl,
            response
        )

    def _generate_cache_key(self, question: str, provider: str) -> str:
        """生成缓存键"""
        # 对问题进行标准化（去除空格、标点等）
        normalized = question.lower().strip()
        # 使用哈希避免键过长
        return f"cache:{provider}:{hash(normalized)}"
```

**缓存策略**:

| 问题类型 | 缓存时长 | 命中率预期 |
|---------|---------|-----------|
| 常见问题（FAQ） | 24小时 | 60-80% |
| 知识检索 | 1小时 | 40-60% |
| 对比学习 | 不缓存 | N/A |
| 音频转写 | 永久 | 100% |

**预期效果**:
- ✅ 减少40-60%的API调用
- ✅ 响应速度提升5-10倍
- ✅ 成本降低40-50%

---

### 方案3：分级调用策略（P1）

#### 实施目标

- 根据问题复杂度选择合适的模型
- 简单问题用廉价模型
- 复杂问题用高质量模型

#### 实施方案

```python
class TieredRoutingStrategy:
    """分级路由策略"""

    def __init__(self):
        # 按成本和质量分级
        self.tiers = {
            "simple": {
                "models": ["deepseek"],      # 最便宜
                "max_tokens": 500,
                "use_cases": ["简单问答", "概念解释"]
            },
            "medium": {
                "models": ["hunyuan", "glm"], # 中等成本
                "max_tokens": 1500,
                "use_cases": ["知识检索", "文档分析"]
            },
            "complex": {
                "models": ["doubao"],         # 最高质量
                "max_tokens": 3000,
                "use_cases": ["深度推理", "创意生成"]
            }
        }

    async def route_request(
        self,
        question: str,
        context: Dict
    ) -> str:
        """路由请求到合适的层级"""

        # 分析问题复杂度
        complexity = self._analyze_complexity(question)

        # 选择对应层级的模型
        tier = self.tiers[complexity]
        model = tier["models"][0]  # 选择第一个模型

        logger.info(
            f"路由到 {complexity} 层，使用 {model}，"
            f"预算tokens: {tier['max_tokens']}"
        )

        return model

    def _analyze_complexity(self, question: str) -> str:
        """分析问题复杂度"""

        # 简单问题：短、单主题
        if len(question) < 50 and "?" in question:
            return "simple"

        # 复杂问题：长、多主题、需要推理
        if len(question) > 200 or "为什么" in question or "如何" in question:
            return "complex"

        # 中等复杂度
        return "medium"
```

**成本对比**:

| 复杂度 | 模型 | tokens/次 | 成本/次 | 占比 |
|--------|------|-----------|---------|------|
| 简单 | DeepSeek | 500 | ¥0.0005 | 10% |
| 中等 | 混元/GLM | 1500 | ¥0.012 | 60% |
| 复杂 | 豆包 | 3000 | ¥0.036 | 30% |

**预期效果**:
- ✅ 平均成本降低50%
- ✅ 简单问题响应更快
- ✅ 复杂问题质量有保证

---

### 方案4：Prompt优化与Token压缩（P1）

#### 实施目标

- 减少冗余的prompt
- 压缩长上下文
- 优化RAG检索结果

#### 实施方案

```python
class PromptOptimizer:
    """Prompt优化器"""

    def compress_context(self, context: List[Dict]) -> List[Dict]:
        """压缩上下文"""

        # 1. 去除重复内容
        seen = set()
        unique_context = []
        for item in context:
            content_hash = hash(item["content"])
            if content_hash not in seen:
                seen.add(content_hash)
                unique_context.append(item)

        # 2. 限制长度
        max_context_length = 2000  # tokens
        compressed = []
        total_length = 0
        for item in unique_context:
            item_length = len(item["content"])
            if total_length + item_length <= max_context_length:
                compressed.append(item)
                total_length += item_length
            else:
                break

        logger.info(
            f"上下文压缩: {len(context)} -> {len(compressed)} "
            f"({len(context) - len(compressed)} 项被移除)"
        )

        return compressed

    def optimize_system_prompt(
        self,
        request_type: str,
        user_intent: str
    ) -> str:
        """优化系统prompt"""

        # 使用简洁的prompt模板
        templates = {
            "qa": "基于提供的信息回答问题。简洁准确。",
            "retrieval": "从以下文档中提取相关答案。",
            "comparison": "比较不同AI的回答，给出最佳选择。"
        }

        base_prompt = templates.get(request_type, "请回答问题。")

        # 根据意图微调
        if "代码" in user_intent:
            base_prompt += " 优先提供代码示例。"
        elif "数据" in user_intent:
            base_prompt += " 提供数据和分析。"

        return base_prompt
```

**压缩效果**:

| 压缩前 | 压缩后 | 节省 |
|--------|--------|------|
| 3000 tokens | 1500 tokens | 50% |
| 5个文档片段 | 2-3个文档片段 | 40-60% |

**预期效果**:
- ✅ Prompt长度减少40-60%
- ✅ 输入token成本减半
- ✅ 响应速度提升30%

---

### 方案5：本地模型增强（P2）

#### 实施目标

- 部署更多本地模型
- 减少对外部API的依赖
- 处理常见场景

#### 推荐本地模型

| 模型 | 类型 | 用途 | 部署难度 | 成本节省 |
|------|------|------|---------|---------|
| **Qwen2.5-7B** | 生成 | 通用问答 | 中 | 80% |
| **ChatGLM3-6B** | 生成 | 中文对话 | 低 | 75% |
| **BGE-M3** | Embedding | 向量化 | ✅ 已部署 | 100% |
| **Whisper-Large** | 音频 | 转写 | 中 | 90% |

#### 部署方案

```python
class LocalModelManager:
    """本地模型管理器"""

    def __init__(self):
        self.models = {}

    async def load_local_models(self):
        """加载本地模型"""

        # 1. Qwen2.5-7B（生成）
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            qwen_model = AutoModelForCausalLM.from_pretrained(
                "Qwen/Qwen2.5-7B-Instruct",
                device_map="auto",
                load_in_4bit=True  # 量化减少内存
            )
            qwen_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")

            self.models["qwen"] = {
                "model": qwen_model,
                "tokenizer": qwen_tokenizer,
                "type": "generation"
            }
            logger.info("✅ Qwen2.5-7B 加载成功")
        except Exception as e:
            logger.error(f"❌ Qwen2.5-7B 加载失败: {e}")

        # 2. BGE-M3（Embedding）- 已部署
        logger.info("✅ BGE-M3 已部署")

    async def generate_with_local(
        self,
        prompt: str,
        model_name: str = "qwen"
    ) -> str:
        """使用本地模型生成"""

        if model_name not in self.models:
            raise ValueError(f"模型 {model_name} 未加载")

        model_config = self.models[model_name]
        model = model_config["model"]
        tokenizer = model_config["tokenizer"]

        # 生成
        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(
            **inputs,
            max_new_tokens=500,
            temperature=0.7,
            do_sample=True
        )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response
```

**硬件需求**:

| 模型 | 量化 | GPU内存 | CPU内存 |
|------|------|---------|---------|
| Qwen2.5-7B | 4-bit | 6GB | 16GB |
| ChatGLM3-6B | 4-bit | 5GB | 12GB |
| BGE-M3 | - | 2GB | 8GB |
| **总计** | - | **13GB** | **36GB** |

**预期效果**:
- ✅ 常见问题成本降低75-80%
- ✅ 数据隐私保护
- ✅ 无API调用限制
- ❌ 需要GPU资源
- ❌ 模型质量略低于API

---

### 方案6：智能批处理与队列（P2）

#### 实施目标

- 合并相似请求
- 批量处理降低成本
- 优先级队列管理

#### 实施方案

```python
class BatchProcessor:
    """批处理器"""

    def __init__(self, batch_size=10, max_wait_time=5):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time  # 秒
        self.pending_requests = []

    async def add_request(self, question: str) -> str:
        """添加请求到批处理队列"""

        future = asyncio.Future()
        self.pending_requests.append({
            "question": question,
            "future": future
        })

        # 达到批大小或超时
        if len(self.pending_requests) >= self.batch_size:
            await self._process_batch()

        return await future

    async def _process_batch(self):
        """处理一批请求"""

        if not self.pending_requests:
            return

        batch = self.pending_requests[:self.batch_size]
        self.pending_requests = self.pending_requests[self.batch_size:]

        # 合并问题
        combined_prompt = "\n\n".join([
            f"问题{i+1}: {req['question']}"
            for i, req in enumerate(batch)
        ])

        # 单次API调用处理多个问题
        from backend.services.evolution.multi_ai_adapter import MultiAIAdapter
        adapter = MultiAIAdapter()
        result = await adapter.adapters["deepseek"].generate(
            combined_prompt
        )

        # 解析并返回结果
        # （这里需要实际的解析逻辑）
        for req in batch:
            req["future"].set_result(result["content"])
```

**预期效果**:
- ✅ API调用次数减少70-90%
- ✅ 成本降低30-50%
- ⚠️ 响应延迟增加（等待批处理）

---

## 📊 综合优化方案预期效果

### 成本对比

| 优化前 | 优化后 | 节省 |
|--------|--------|------|
| ¥900/月 | ¥270/月 | **70%** |
| 2.5M tokens/天 | 0.75M tokens/天 | **70%** |

### 实施优先级

| 方案 | 优先级 | 实施难度 | 成本节省 | 时间 |
|------|--------|---------|---------|------|
| Token追踪 | P0 | 低 | 10% | 1天 |
| 智能缓存 | P0 | 中 | 40-50% | 3-5天 |
| 分级调用 | P1 | 中 | 30-40% | 3天 |
| Prompt优化 | P1 | 低 | 20-30% | 2天 |
| 本地模型 | P2 | 高 | 50-60% | 1-2周 |
| 批处理 | P2 | 中 | 20-30% | 5天 |

### 推荐实施路线

**第1周（P0）**:
1. ✅ 实施Token追踪
2. ✅ 实施智能缓存（L1+L2）
3. ✅ 配置API密钥（混元+DeepSeek）

**第2周（P1）**:
4. ✅ 实施分级调用策略
5. ✅ 实施Prompt优化
6. ✅ 集成到LingMinOpt自动优化

**第3-4周（P2）**:
7. 📋 评估本地模型部署
8. 📋 实施批处理队列

---

## 🔧 立即行动

### 今天可以做的

1. **配置API密钥**
   ```bash
   # .env文件
   HUNYUAN_API_KEY=your_key_here
   DEEPSEEK_API_KEY=your_key_here
   ```

2. **实施Token追踪**
   - 创建 `TokenUsageTracker` 类
   - 集成到 `MultiAIAdapter`
   - 添加监控面板

3. **启用基础缓存**
   - 使用Redis缓存常见问答
   - 设置TTL为1小时

### 本周可以做的

4. **实施分级调用**
   - 简单问题用DeepSeek（便宜）
   - 复杂问题用混元（质量）

5. **优化Prompt**
   - 压缩RAG检索结果
   - 简化系统prompt

6. **监控成本**
   - 每日成本报告
   - 预算告警

---

## 💡 核心建议

### 短期（1周内）

- ✅ 实施Token追踪（防止失控）
- ✅ 配置DeepSeek（最便宜的API）
- ✅ 启用Redis缓存（40-50%节省）

### 中期（1月内）

- ✅ 分级调用策略（根据复杂度选择模型）
- ✅ Prompt优化（减少冗余）
- ✅ 监控和告警（超预算通知）

### 长期（3月内）

- 📋 部署本地模型（Qwen2.5-7B）
- 📋 批处理优化（批量处理）
- 📋 自适应优化（LingMinOpt自动调优）

---

**众智混元，万法灵通** ⚡🚀

**预计成本降低**: 70%
**实施时间**: 1-2周
**ROI**: 投入1周，节省70%成本
