# 灵知系统 - CLIProxyAPI 集成指南

**版本**: v1.0.0
**日期**: 2026-04-01
**目标**: 将 CLIProxyAPI 集成到灵知系统，提供统一的AI服务

---

## 🎯 集成目标

### 为什么集成 CLIProxyAPI？

| 功能 | 集成前 | 集成后 |
|------|--------|--------|
| **AI模型支持** | 仅DeepSeek | Claude/Gemini/DeepSeek/Qwen等 |
| **API接口** | 自定义格式 | 标准OpenAI兼容格式 |
| **认证方式** | API Key | OAuth + API Key多种方式 |
| **负载均衡** | 单一模型 | 多模型轮询、自动故障转移 |
| **开发工具集成** | ❌ | ✅ Claude Code/Cursor/VSCode |

### 核心价值

1. **统一AI服务层**
   - 所有AI调用通过 CLIProxyAPI
   - 简化代码，统一接口

2. **多模型支持**
   - Claude（推理、编程）
   - Gemini（多模态）
   - DeepSeek（RAG、问答）
   - 通义千问（中文优化）
   - OpenAI Codex（编程）

3. **开发工具友好**
   - 兼容 Claude Code
   - 兼容 Cursor
   - 兼容 VSCode AI插件

---

## 🏗️ 集成架构

```
┌─────────────────────────────────────────────────────┐
│              灵知系统 + CLIProxyAPI 集成架构          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────┐       ┌──────────────────┐      │
│  │  前端/客户端       │       │  AI编程工具        │      │
│  │  - Web UI         │       │  - Claude Code    │      │
│  │  - VSCode插件     │       │  - Cursor         │      │
│  │  - CLI工具        │       │  - Amp CLI        │      │
│  └────────┬─────────┘       └────────┬─────────┘      │
│           │                         │                  │
│           └───────────┬─────────────┘                  │
│                       │                               │
│                       ▼                               │
│          ┌─────────────────────┐                        │
│          │  灵知系统 FastAPI    │                        │
│          │  /v1/api/*           │                        │
│          └──────────┬──────────┘                        │
│                     │                                   │
│                     ▼                                   │
│          ┌─────────────────────┐                        │
│          │  统一AI服务层       │                        │
│          │  (AIService)        │                        │
│          │  - RAG服务          │                        │
│          │  - 问答服务          │                        │
│          │  - 推理服务          │                        │
│          └──────────┬──────────┘                        │
│                     │                                   │
│                     ▼                                   │
│          ┌─────────────────────┐                        │
│          │  CLIProxyAPI        │  ← 独立服务           │
│          │  :8317              │                        │
│          │  - 模型路由         │                        │
│          │  - 负载均衡         │                        │
│          │  - OAuth认证        │                        │
│          └──────────┬──────────┘                        │
│                     │                                   │
│                     ▼                                   │
│          ┌─────────────────────┐                        │
│          │  上游AI服务         │                        │
│          │  - Claude API       │                        │
│          │  - Gemini API       │                        │
│          │  - DeepSeek API     │                        │
│          │  - 通义千问API      │                        │
│          └─────────────────────┘                        │
└─────────────────────────────────────────────────────┘
```

---

## 📦 部署方式

### 方式1: Docker Compose（推荐）

创建 `docker-compose.cli-proxy.yml`:

```yaml
version: '3.8'

services:
  # CLIProxyAPI 服务
  cliproxyapi:
    image: routerforme/cli-proxy-api:latest
    container_name: lingzhi-cliproxyapi
    ports:
      - "8317:8317"  # API端口
      - "8316:8316"  # pprof调试端口（仅localhost）
    environment:
      # 配置文件挂载
    volumes:
      - ./config/cliproxyapi:/root/.cli-proxy-api:ro  # 配置目录
      - ./config/cliproxyapi/config.yaml:/root/.cli-proxy-api/config.yaml:ro
      - cliproxyapi-logs:/root/logs  # 日志目录
    restart: unless-stopped
    networks:
      - lingzhi-network
    healthcheck:
      test: ["CMD", "curl", "-f", "localhost:8317/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  cliproxyapi-logs:

networks:
  lingzhi-network:
    external: true
```

### 方式2: 本地编译运行

```bash
# 1. 克隆仓库
git clone https://github.com/router-for-me/CLIProxyAPI.git
cd CLIProxyAPI

# 2. 编译
go build -o cli-proxy-api ./cmd/server

# 3. 运行
./cli-proxy-api
```

---

## ⚙️ 配置文件

创建 `config/cliproxyapi/config.yaml`:

```yaml
# ============================================
# 灵知系统 - CLIProxyAPI 配置
# ============================================

# 服务器配置
host: "0.0.0.0"  # 监听所有接口
port: 8317

# TLS配置（生产环境启用）
tls:
  enable: false
  cert: ""
  key: ""

# 管理API配置
remote-management:
  allow-remote: false  # 仅允许localhost访问管理端点
  secret-key: "${CLIPROXY_MANAGEMENT_KEY}"  # 管理密钥（环境变量）

# 认证目录
auth-dir: "~/.cli-proxy-api"

# API密钥（灵知系统使用）
api-keys:
  - "lingzhi-api-key-001"
  - "lingzhi-api-key-002"

# ============================================
# DeepSeek 配置（灵知系统主用模型）
# ============================================

# DeepSeek API密钥
openai-compatibility:
  - name: "deepseek"
    prefix: "deepseek"
    base-url: "https://api.deepseek.com/v1"  # 或本地部署地址
    headers:
      Authorization: "Bearer ${DEEPSEEK_API_KEY}"
    api-key-entries:
      - api-key: "${DEEPSEEK_API_KEY}"
    models:
      # DeepSeek-V3（推理）
      - name: "deepseek-chat"
        alias: "lingzhi-chat"
      # DeepSeek-Coder（编程）
      - name: "deepseek-coder"
        alias: "lingzhi-coder"
      # DeepSeek-V3（推理）
      - name: "deepseek-reasoner"
        alias: "lingzhi-reasoner"

# ============================================
# Claude 配置（高质量推理）
# ============================================

claude-api-key:
  - api-key: "${CLAUDE_API_KEY}"
    prefix: "claude"
    models:
      # Claude 3.5 Sonnet（主力模型）
      - name: "claude-3-5-sonnet-20241022"
        alias: "claude-sonnet"
      # Claude 3.5 Haiku（快速）
      - name: "claude-3-5-haiku-20241022"
        alias: "claude-fast"
    cloak:
      mode: "auto"
      cache-user-id: true

# ============================================
# Gemini 配置（多模态）
# ============================================

gemini-api-key:
  - api-key: "${GEMINI_API_KEY}"
    prefix: "gemini"
    models:
      # Gemini 2.5 Flash（快速多模态）
      - name: "gemini-2.5-flash"
        alias: "gemini-flash"
      # Gemini 2.5 Pro（高质量）
      - name: "gemini-2.5-pro"
        alias: "gemini-pro"
      # Gemini 2.0 Flash（免费额度）
      - name: "gemini-2.0-flash-exp"
        alias: "gemini-free"

# ============================================
# 通义千问配置（中文优化）
# ============================================

# 通过OAuth或API Key配置
# 示例使用API Key方式
openai-compatibility:
  - name: "qwen"
    prefix: "qwen"
    base-url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    headers:
      Authorization: "Bearer ${QWEN_API_KEY}"
    api-key-entries:
      - api-key: "${QWEN_API_KEY}"
    models:
      # 千问2.5
      - name: "qwen-plus"
        alias: "qwen-chat"
      # 千问2.5-Coder
      - name: "qwen-coder-plus"
        alias: "qwen-coder"
      # 千问VL（多模态）
      - name: "qwen-vl-max"
        alias: "qwen-vl"

# ============================================
# 路由策略
# ============================================

routing:
  strategy: "round-robin"  # 轮询策略
  # fill-first: 先用完一个再用下一个
  # round-robin: 轮流使用

# ============================================
# 配额超限处理
# ============================================

quota-exceeded:
  switch-project: true  # 自动切换项目/账户
  switch-preview-model: true  # 切换到预览模型

# ============================================
# 重试配置
# ============================================

request-retry: 3  # 失败重试次数
max-retry-credentials: 0  # 尝试所有凭证
max-retry-interval: 30  # 最大重试间隔（秒）

# ============================================
# 使用统计
# ============================================

usage-statistics-enabled: true  # 启用统计

# ============================================
# OAuth配置（可选）
# ============================================

# Claude Code OAuth
claude:
  client-id: "${CLAUDE_CLIENT_ID}"
  client-redirect-uri: "http://localhost:8317/auth/callback"

# Gemini OAuth
gemini:
  client-id: "${GEMINI_CLIENT_ID}"
  client-secret: "${GEMINI_CLIENT_SECRET}"
  redirect-uri: "http://localhost:8317/auth/callback"

# OpenAI Codex OAuth
codex:
  client-id: "${CODEX_CLIENT_ID}"
  client-secret: "${CODEX_CLIENT_SECRET}"
  redirect-uri: "http://localhost:8317/auth/callback"
```

---

## 🔧 灵知系统适配

### 1. 创建AI服务适配器

```python
# backend/services/ai_service_adapter.py
from openai import OpenAI
import os

class AIServiceAdapter:
    """AI服务适配器 - 通过CLIProxyAPI调用"""

    def __init__(self):
        self.client = OpenAI(
            base_url="http://localhost:8317/v1",  # CLIProxyAPI地址
            api_key="lingzhi-api-key-001",          # 配置的API Key
            timeout=60.0
        )

    async def chat(
        self,
        messages: list,
        model: str = "lingzhi-chat",
        stream: bool = False
    ):
        """聊天对话

        Args:
            messages: 消息列表
            model: 模型名称（使用CLIProxyAPI的alias）
            stream: 是否流式响应

        Returns:
            AI响应
        """
        # 模型映射
        model_mapping = {
            "deepseek": "lingzhi-chat",
            "claude": "claude-sonnet",
            "gemini": "gemini-flash",
            "qwen": "qwen-chat"
        }

        # 使用CLIProxyAPI的模型别名
        model_alias = model_mapping.get(model, model)

        if stream:
            return await self._chat_stream(messages, model_alias)
        else:
            response = await self.client.chat.completions.create(
                model=model_alias,
                messages=messages
            )
            return response.choices[0].message.content

    async def _chat_stream(self, messages, model):
        """流式聊天"""
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embed(
        self,
        texts: list[str],
        model: str = "lingzhi-embed"
    ):
        """文本向量化

        Args:
            texts: 文本列表
            model: 模型名称

        Returns:
            向量列表
        """
        # 使用DeepSeek的embedding（通过CLIProxyAPI）
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",  # DeepSeek embedding
            input=texts
        )

        return [item['embedding'] for item in response['data']]
```

### 2. 更新现有AI服务

```python
# backend/services/rag_service.py
from backend.services.ai_service_adapter import AIServiceAdapter

class RAGService:
    def __init__(self):
        # 使用CLIProxyAPI适配器
        self.ai_adapter = AIServiceAdapter()

    async def query(
        self,
        query: str,
        context: list[str],
        model: str = "claude"  # 使用Claude获得更高质量答案
    ):
        """RAG查询

        Args:
            query: 用户问题
            context: 检索到的上下文
            model: AI模型

        Returns:
            答案
        """
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt()
            },
            {
                "role": "user",
                "content": f"""参考以下内容回答问题：

{self._format_context(context)}

问题：{query}"""
            }
        ]

        # 通过CLIProxyAPI调用AI
        response = await self.ai_adapter.chat(
            messages=messages,
            model=model
        )

        return response
```

### 3. 创建统一AI服务接口

```python
# backend/services/unified_ai_service.py
from typing import Literal

ModelType = Literal[
    "deepseek",    # DeepSeek（性价比高）
    "claude",      # Claude（高质量）
    "gemini",      # Gemini（多模态）
    "qwen"         # 通义（中文优化）
]

class UnifiedAIService:
    """统一AI服务"""

    def __init__(self):
        self.adapter = AIServiceAdapter()

    async def chat(
        self,
        prompt: str,
        model: ModelType = "deepseek",
        system_prompt: str = None,
        stream: bool = False
    ):
        """统一聊天接口

        Args:
            prompt: 用户提示
            model: 模型选择
            system_prompt: 系统提示词
            stream: 是否流式

        Returns:
            AI响应
        """
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        messages.append({
            "role": "user",
            "content": prompt
        })

        return await self.adapter.chat(
            messages=messages,
            model=model,
            stream=stream
        )

    async def embed(
        self,
        texts: list[str],
        model: ModelType = "deepseek"
    ):
        """统一向量化接口"""
        return await self.adapter.embed(texts, model=model)

    async def multimodal(
        self,
        prompt: str,
        images: list[str] = None,
        model: ModelType = "gemini"  # Gemini多模态能力强
    ):
        """多模态理解

        Args:
            prompt: 文本提示
            images: 图片URL列表
            model: 模型选择

        Returns:
            AI响应
        """
        messages = []
        if images:
            # 添加图片内容
            content = [{"type": "text", "text": prompt}]
            for img_url in images:
                content.append({
                    "type": "image_url",
                    "image_url": img_url
                })
            messages.append({
                "role": "user",
                "content": content
            })
        else:
            messages.append({
                "role": "user",
                "content": prompt
            })

        return await self.adapter.chat(
            messages=messages,
            model=model
        )

    async def code(
        self,
        prompt: str,
        language: str = "python",
        model: ModelType = "claude"  # Claude编程能力强
    ):
        """代码生成

        Args:
            prompt: 编程需求
            language: 编程语言
            model: 模型选择

        Returns:
            代码
        """
        system_prompt = f"""你是一个专业的{language}程序员。
请按照以下要求回答编程问题：
1. 代码要清晰、可维护
2. 添加必要的注释
3. 遵循PEP 8规范
4. 如果需要导入库，请使用标准库或常用库"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        return await self.adapter.chat(
            messages=messages,
            model=model
        )
```

### 4. 创建路由配置

```python
# backend/api/v1/ai.py
from fastapi import APIRouter, Depends
from backend.services.unified_ai_service import UnifiedAIService
from typing import Literal

router = APIRouter(prefix="/v1/ai", tags=["AI Service"])

# 初始化统一AI服务
ai_service = UnifiedAIService()

@router.post("/chat")
async def chat(
    prompt: str,
    model: Literal["deepseek", "claude", "gemini", "qwen"] = "deepseek",
    system_prompt: str = None
):
    """聊天接口"""
    response = await ai_service.chat(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt
    )
    return {"response": response}

@router.post("/embed")
async def embed(
    texts: list[str],
    model: Literal["deepseek", "claude", "gemini", "qwen"] = "deepseek"
):
    """向量化接口"""
    embeddings = await ai_service.embed(texts=texts, model=model)
    return {"embeddings": embeddings}

@router.post("/multimodal")
async def multimodal(
    prompt: str,
    images: list[str] = None,
    model: Literal["deepseek", "claude", "gemini", "qwen"] = "gemini"
):
    """多模态理解接口"""
    response = await ai_service.multimodal(
        prompt=prompt,
        images=images,
        model=model
    )
    return {"response": response}

@router.post("/code")
async def generate_code(
    prompt: str,
    language: str = "python",
    model: Literal["deepseek", "claude", "gemini", "qwen"] = "claude"
):
    """代码生成接口"""
    response = await ai_service.code(
        prompt=prompt,
        language=language,
        model=model
    )
    return {"code": response}
```

---

## 🚀 快速开始

### 1. 配置环境变量

创建 `.env` 文件：

```bash
# CLIProxyAPI管理密钥
CLIPROXY_MANAGEMENT_KEY=your_management_key_here

# DeepSeek API
DEEPSEEK_API_KEY=sk-your-deepseek-key

# Claude API（可选）
CLAUDE_API_KEY=sk-ant-your-claude-key

# Gemini API（可选）
GEMINI_API_KEY=your-gemini-key

# 通义千问 API（可选）
QWEN_API_KEY=sk-your-qwen-key

# OAuth配置（可选）
CLAUDE_CLIENT_ID=your_client_id
GEMINI_CLIENT_ID=your_client_id
GEMINI_CLIENT_SECRET=your_client_secret
CODEX_CLIENT_ID=your_client_id
CODEX_CLIENT_SECRET=your_client_secret
```

### 2. 启动CLIProxyAPI

```bash
# 使用Docker Compose启动
docker-compose -f docker-compose.cli-proxy.yml up -d

# 验证启动
curl http://localhost:8317/health

# 查看模型列表
curl http://localhost:8317/v1/models \
  -H "x-api-key: lingzhi-api-key-001"
```

### 3. 测试集成

```bash
# 测试聊天接口
curl -X POST http://localhost:8001/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "什么是智能气功？",
    "model": "deepseek"
  }'

# 测试多模态接口
curl -X POST http://localhost:8001/v1/ai/multimodal \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "描述这张图片",
    "images": ["https://example.com/image.jpg"],
    "model": "gemini"
  }'

# 测试代码生成
curl -X POST http://localhost:8001/v1/ai/code \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "写一个Python函数计算斐波那契数列",
    "language": "python",
    "model": "claude"
  }'
```

---

## 🔌 模型选择策略

### 根据任务类型选择模型

```python
# backend/services/model_selector.py

class ModelSelector:
    """模型选择策略"""

    @staticmethod
    def select_for_task(task_type: str) -> str:
        """根据任务类型选择最佳模型

        Args:
            task_type: 任务类型

        Returns:
            推荐的模型
        """
        task_model_mapping = {
            # 推理任务 - 使用高质量模型
            "reasoning": "claude",
            "analysis": "claude",
            "complex_qa": "claude",

            # 编程任务 - Claude最强
            "coding": "claude",
            "code_review": "claude",
            "debug": "claude",

            # 中文内容 - 通义优化
            "chinese": "qwen",
            "chinese_poetry": "qwen",
            "chinese_culture": "qwen",

            # 多模态 - Gemini最强
            "multimodal": "gemini",
            "image_understanding": "gemini",
            "vision": "gemini",

            # 平衡性能和成本 - DeepSeek
            "chat": "deepseek",
            "rag": "deepseek",
            "summarization": "deepseek",

            # 编程助手 - DeepSeek-Coder
            "code_assistant": "deepseek",
            "code_explanation": "deepseek",

            # 快速响应 - Gemini Flash
            "fast": "gemini-flash",
            "realtime": "gemini-free"
        }

        return task_model_mapping.get(task_type, "deepseek")

# 使用示例
from backend.services.model_selector import ModelSelector

class SmartRAGService:
    def __init__(self):
        self.ai_service = UnifiedAIService()
        self.selector = ModelSelector()

    async def query(self, query: str, context: list[str]):
        # 智能选择模型
        model = self.selector.select_for_task("rag")

        # 调用AI
        response = await self.ai_service.chat(
            prompt=f"参考以下内容回答：{self._format_context(context)}\n问题：{query}",
            model=model
        )

        return response
```

---

## 📊 使用场景

### 场景1: 现有RAG系统升级

**之前**: 只用DeepSeek
**之后**: 根据任务自动选择最佳模型

```python
# 之前
response = await deepseek_client.chat(prompt, context)

# 之后
model = ModelSelector.select_for_task("reasoning")  # 自动选择Claude
response = await ai_service.chat(prompt, model=model)
```

### 场景2: 多模态内容理解

```python
# 处理带图片的功法指导
async def analyze_practice_image(image_url: str):
    response = await ai_service.multimodal(
        prompt="请描述这个图片中的功法姿势要领",
        images=[image_url],
        model="gemini"  # 多模态首选
    )
    return response
```

### 场景3: 代码审查和生成

```python
# 代码审查
async def review_code(code: str):
    response = await ai_service.code(
        prompt=f"请审查以下代码，指出问题和改进建议：\n\n{code}",
        model="claude"  # 编程首选
    )
    return response
```

### 场景4: AI编程工具集成

```bash
# VSCode + Claude Code
export OPENAI_API_BASE=http://localhost:8317/v1
export OPENAI_API_KEY=lingzhi-api-key-001

# Cursor
export OPENAI_API_BASE=http://localhost:8317/v1
export OPENAI_API_KEY=lingzhi-api-key-001

# 使用Claude Code/Cursor直接连接到灵知系统
```

---

## 🎯 集成检查清单

### 部署阶段

- [ ] 配置环境变量（API Keys）
- [ ] 创建配置文件 `config/cliproxyapi/config.yaml`
- [ ] 启动 CLIProxyAPI 服务
- [ ] 验证健康检查 `/health`
- [ ] 验证模型列表 `/v1/models`

### 集成阶段

- [ ] 创建 AIServiceAdapter
- [ ] 创建 UnifiedAIService
- [ ] 更新现有RAG服务
- [ ] 创建统一AI API路由
- [ ] 测试各模型调用

### 测试阶段

- [ ] 测试DeepSeek（主用）
- [ ] 测试Claude（推理）
- [ ] 测试Gemini（多模态）
- [ ] 测试通义千问（中文）
- [ ] 测试负载均衡
- [ ] 测试故障转移

### 优化阶段

- [ ] 添加模型选择策略
- [ ] 添加重试和降级
- [ ] 添加使用统计
- [ ] 添加成本控制

---

## 📈 预期效果

| 维度 | 集成前 | 集成后 |
|------|--------|--------|
| **AI模型** | 1个（DeepSeek） | 5+ |
| **开发工具** | ❌ | ✅ Claude Code/Cursor |
| **代码质量** | 良好 | 优秀 |
| **响应速度** | 中等 | 快（Gemini Flash） |
| **中文理解** | 好 | 优秀（通义千问） |
| **多模态** | ❌ | ✅ Gemini |
| **可靠性** | 单点故障 | 高可用（多模型） |

---

## ⚠️ 注意事项

### 1. API Key 安全

```yaml
# ❌ 不要在代码中硬编码
api_key: "sk-xxx"

# ✅ 使用环境变量
api_key: os.environ.get("API_KEY")

# ✅ 或使用密钥管理服务
```

### 2. 模型选择

不同模型有不同优势：
- **Claude**: 推理、编程、高质量回答
- **Gemini**: 多模态、快速、免费额度
- **DeepSeek**: 性价比、中文优化
- **通义千问**: 中文文化、本土化

### 3. 成本控制

```python
# 简单任务使用快速/免费模型
if task_complexity == "low":
    model = "gemini-free"  # 免费
elif task_complexity == "medium":
    model = "deepseek"  # 便宜
else:
    model = "claude"  # 高质量但较贵
```

### 4. 故障转移

CLIProxyAPI自动处理：
- 配额超限 → 切换账户/模型
- 请求失败 → 重试
- 服务不可用 → 切换到其他提供商

---

## 📚 相关文档

- [CLIProxyAPI GitHub](https://github.com/router-for-me/CLIProxyAPI)
- [CLIProxyAPI 文档](https://help.router-for.me)
- [灵知系统现有架构](../ENGINEERING_ALIGNMENT.md)

---

**文档状态**: ✅ 完成

**版本**: v1.0.0

**下一步**: 配置并启动 CLIProxyAPI

**众智混元，万法灵通** ⚡🚀
