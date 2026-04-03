# 上下文管理系统集成指南

本文档描述了集成自 [LingFlow](https://github.com/guangda88/LingFlow) 的上下文管理系统。

## 概述

上下文管理系统提供以下功能：

1. **Token 估算** - 精确估算文本和消息的 Token 数量
2. **消息评分** - 多维度消息评分（重要性、相关性、时间、质量）
3. **上下文压缩** - 智能压缩长对话以延长会话
4. **会话状态管理** - 跟踪任务、决策、重要文件
5. **持久化存储** - SQLite/JSON 持久化上下文状态

## 安装

上下文管理系统已集成到项目中，依赖 `lingflow-core` 包：

```bash
pip install lingflow-core
```

## API 端点

### 基础信息

- **Base URL**: `/api/v1/context`
- **认证**: 当前不需要认证（可配置）

### 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/estimate` | 估算 Token 数量 |
| POST | `/messages/score` | 评分消息列表 |
| POST | `/messages/record` | 记录一条消息 |
| POST | `/compress` | 压缩当前上下文 |
| GET | `/status` | 获取当前状态 |
| GET | `/snapshot` | 获取当前快照 |
| GET | `/recovery` | 获取恢复摘要 |
| POST | `/tasks` | 添加任务 |
| PUT | `/tasks/{task_name}` | 标记任务完成 |
| POST | `/decisions` | 记录关键决策 |
| POST | `/reset` | 重置上下文 |
| GET | `/health` | 健康检查 |

## 使用示例

### 1. Token 估算

```python
import requests

response = requests.post("http://localhost:8000/api/v1/context/estimate", json={
    "text": "这是一段需要估算 token 数量的文本。",
    "model": "claude-opus-4"
})

print(response.json())
# {"token_count": 15, "model": "claude-opus-4", "encoding": "cl100k_base", "estimated": true}
```

### 2. 消息评分

```python
response = requests.post("http://localhost:8000/api/v1/context/messages/score", json={
    "messages": [
        {"role": "user", "content": "fix the critical bug"},
        {"role": "assistant", "content": "I'll help you fix that bug"}
    ]
})

print(response.json())
# {
#   "scores": [...],
#   "total_messages": 2,
#   "average_importance": 0.65
# }
```

### 3. 记录消息

```python
response = requests.post("http://localhost:8000/api/v1/context/messages/record", json={
    "role": "user",
    "content": "implement new feature",
    "is_important": true
})
```

### 4. 添加任务

```python
# 添加待完成任务
response = requests.post("http://localhost:8000/api/v1/context/tasks", json={
    "task": "Implement user authentication",
    "completed": False
})

# 标记任务完成
response = requests.put("http://localhost:8000/api/v1/context/tasks/Implement%20user%20authentication")
```

### 5. 压缩上下文

```python
response = requests.post("http://localhost:8000/api/v1/context/compress", json={})

print(response.json()["summary"])
# # 上下文摘要
#
# **会话 ID**: abc123...
# **时间**: 2026-04-02T01:00:00
# ...
```

### 6. 获取状态

```python
response = requests.get("http://localhost:8000/api/v1/context/status")

print(response.json())
# {
#   "session_id": "abc123...",
#   "message_count": 42,
#   "estimated_tokens": 15000,
#   "token_limit": 180000,
#   "token_usage_ratio": 0.083,
#   "health_status": "healthy",
#   "tasks_completed": 5,
#   "tasks_pending": 3,
#   "needs_compression": false
# }
```

## Python 客户端

### 直接使用服务

```python
from backend.services.context_service import get_context_service

# 获取服务实例
service = get_context_service()

# Token 估算
estimate = service.estimate_tokens("这是一段测试文本")
print(f"Token 数量: {estimate.token_count}")

# 消息评分
messages = [
    {"role": "user", "content": "fix the bug"},
    {"role": "assistant", "content": "I'll help you"}
]
scores = service.score_messages(messages)
for score in scores:
    print(f"{score.role}: {score.importance_score}")

# 记录消息
service.record_message("user", "implement feature", is_important=True)

# 添加任务
service.add_task("Add unit tests", completed=False)

# 压缩上下文
summary = service.compress_now()
print(summary)

# 获取状态
status = service.get_status()
print(f"健康状态: {status.health_status}")
```

### 使用 FastAPI Depends

```python
from fastapi import Depends
from backend.services.context_service import get_context_service, ContextService

@router.get("/my-endpoint")
async def my_endpoint(context: ContextService = Depends(get_context_service)):
    status = context.get_status()
    return {"health": status.health_status}
```

## 数据模型

### TokenEstimate

```python
{
    "token_count": int,      # Token 数量
    "model": str,            # 模型名称
    "encoding": str,         # 编码方式
    "estimated": bool        # 是否为估算值
}
```

### MessageScore

```python
{
    "role": str,                    # 消息角色
    "content_preview": str,         # 内容预览
    "importance_score": float,      # 重要性评分 (0-1)
    "relevance_score": float,       # 相关性评分 (0-1)
    "time_score": float,            # 时间评分 (0-1)
    "quality_score": float,         # 质量评分 (0-1)
    "reasoning": str                # 评分理由
}
```

### ContextStatus

```python
{
    "session_id": str,              # 会话 ID
    "message_count": int,           # 消息数量
    "estimated_tokens": int,        # 估算 Token 数
    "token_limit": int,             # Token 限制
    "token_usage_ratio": float,     # Token 使用率
    "health_status": str,           # 健康状态 (healthy/warning/critical)
    "tasks_completed": int,         # 已完成任务数
    "tasks_pending": int,           # 待完成任务数
    "needs_compression": bool       # 是否需要压缩
}
```

### ContextSnapshot

```python
{
    "timestamp": str,               # 时间戳
    "session_id": str,              # 会话 ID
    "tasks_completed": List[str],   # 已完成任务
    "tasks_pending": List[str],     # 待完成任务
    "key_decisions": List[str],     # 关键决策
    "important_files": Dict[str, str],  # 重要文件
    "context_summary": str,         # 上下文摘要
    "next_steps": List[str]         # 下一步计划
}
```

## 配置

### 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `LINGFLOW_CONTEXT_DIR` | 上下文存储目录 | `~/.claude/projects/lingflow/context` |
| `CONTEXT_TOKEN_LIMIT` | Token 限制 | `180000` |
| `CONTEXT_WARNING_THRESHOLD` | 警告阈值 | `0.85` |
| `CONTEXT_COMPRESS_THRESHOLD` | 压缩阈值 | `0.90` |

### 服务配置

```python
from backend.services.context_service import ContextService

service = ContextService(
    storage_dir="/path/to/context",  # 自定义存储目录
    token_limit=180000                # 自定义 Token 限制
)
```

## 高级用法

### 自定义消息评分

```python
from backend.services.context_service import ContextService

class CustomContextService(ContextService):
    def _simple_importance_score(self, content: str) -> float:
        # 自定义评分逻辑
        if "urgent" in content.lower():
            return 1.0
        return super()._simple_importance_score(content)
```

### 自动压缩触发

```python
service = get_context_service()

# 记录大量消息后自动检查
for msg in messages:
    service.record_message(msg["role"], msg["content"])
    # 当 token 使用率达到 90% 时自动压缩
```

### 恢复会话

```python
service = get_context_service()

# 获取恢复摘要
recovery = service.get_recovery_summary()

# 在新会话中使用
print("从上一个会话恢复:")
print(recovery)
```

## 架构

```
┌─────────────────────────────────────────────────┐
│              FastAPI 应用                       │
│  ┌───────────────────────────────────────────┐  │
│  │   /api/v1/context/* 端点                   │  │
│  └───────────────┬───────────────────────────┘  │
│                  │                               │
│  ┌───────────────▼───────────────────────────┐  │
│  │   ContextService (服务层)                  │  │
│  │   - Token 估算                              │  │
│  │   - 消息评分                                │  │
│  │   - 上下文压缩                              │  │
│  │   - 会话管理                                │  │
│  └───────────────┬───────────────────────────┘  │
│                  │                               │
│  ┌───────────────▼───────────────────────────┐  │
│  │   LingFlow Core (可选)                     │  │
│  │   - TokenEstimator (tiktoken)              │  │
│  │   - MessageScorer (多维度评分)              │  │
│  │   - CompressionStrategy (智能压缩)          │  │
│  └───────────────┬───────────────────────────┘  │
│                  │                               │
│  ┌───────────────▼───────────────────────────┐  │
│  │   持久化存储                                │  │
│  │   - JSON (快照)                             │  │
│  │   - Markdown (恢复摘要)                     │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## 测试

运行测试：

```bash
# 服务层测试
pytest tests/test_context_service.py -v

# API 测试
pytest tests/test_context_api.py -v

# 所有上下文测试
pytest tests/test_context*.py -v
```

## 故障排除

### LingFlow 组件不可用

如果看到警告 "LingFlow components not available"，系统会自动使用回退方案（简单 Token 估算和评分）。

### 上下文目录权限问题

确保上下文存储目录有写权限：

```bash
mkdir -p data/context
chmod 755 data/context
```

### Token 估算不准确

回退方案使用 4 字符 = 1 token 的简单估算。如需精确估算，确保安装了 `lingflow-core`。

## 参考资料

- [LingFlow 项目](https://github.com/guangda88/LingFlow)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [tiktoken 文档](https://github.com/openai/tiktoken)
