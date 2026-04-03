# GLM Coding Plan 快速参考

**更新**: 2026-04-01

---

## 🤖 支持的模型（7个）

### 最新旗舰 ⭐
| 模型 | 发布 | 特点 | 推荐场景 |
|------|------|------|---------|
| **GLM-5.1** | 2026.03 | 最新旗舰 | 所有场景 |
| **GLM-5** | 2026.02 | 744B/40B, 200K上下文 | 复杂Agent任务 |
| **GLM-5-Turbo** | - | OpenClaw优化 | 工具调用 |

### 通用系列
| 模型 | 特点 |
|------|------|
| **GLM-4.7** | 高性能，代码生成 |
| **GLM-4.6** | 通用版本 |
| **GLM-4.6V** | 视觉理解 |
| **GLM-4.5** | 成本优化 |

---

## 🔌 MCP Servers（5个）

| MCP | 功能 | 使用场景 |
|-----|------|---------|
| **Vision MCP** | 视觉理解 | 截图分析、UI理解 |
| **Web Search MCP** | 网络搜索 | 实时信息 |
| **Web Reader MCP** | 网页提取 | 文档抓取 |
| **Zread MCP** | 开源仓库 | 代码库分析 |
| **ZAI MCP** | 通用能力 | 综合工具 |

---

## 💻 快速使用

### 在灵知系统中

```python
# 方式1: 自动使用GLM-5（优先级最高）
from backend.services.ai_service import code_development

code = await code_development("实现快速排序")

# 方式2: 调试
from backend.services.ai_service import debug_code

fix = await debug_code(code, error_msg)

# 方式3: 代码审查
from backend.services.ai_service import code_review

review = await code_review(code, focus="性能")
```

### Claude Code配置

```json
{
  "env": {
    "ZHIPU_API_KEY": "your-glm-coding-key"
  },
  "mcpServers": {
    "zhipu-vision": {
      "command": "npx",
      "args": ["-y", "@zhipuai/zhipu-vision-mcp"]
    },
    "zread": {
      "command": "npx",
      "args": ["-y", "@zhipuai/zread-mcp"]
    }
  }
}
```

---

## 📊 当前配置

### 您的使用数据
- **Token消耗**: 2.6T (260万/30天)
- **日均**: 86,667 tokens/天
- **成本**: 包月，比按量节省60-70%

### 系统状态
- ✅ API Key已配置
- ✅ Token池优先级0（最高）
- ✅ 自动智能调度
- ✅ 监控已启用

---

## 🎯 模型选择建议

```python
# 最强性能
model = "glm-5.1"

# Agent任务
model = "glm-5"

# 工具调用
model = "glm-5-turbo"

# 日常使用（性价比）
model = "glm-4.7"
```

---

## 📚 详细文档

完整指南: `docs/GLM_CODING_PLAN_COMPLETE_GUIDE.md`

官方文档: https://docs.bigmodel.cn/coding-plan/overview

---

**🎉 您拥有7个模型 + 5个MCP服务器的完整访问权限！**
