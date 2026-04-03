# GLM Coding Plan 完整指南

**更新时间**: 2026-04-01
**官方文档**: [智谱AI开放文档](https://docs.bigmodel.cn/coding-plan/overview)

---

## 🤖 支持的模型列表

### GLM-5系列（最新旗舰）

所有 **GLM Coding Plan** 用户（Max、Pro、Lite）均可使用：

#### 1. GLM-5.1 ⭐ 最新
- **发布时间**: 2026年3月27日
- **定位**: 最新旗舰版本
- **特点**:
  - 对标 Claude Opus 级别
  - 所有 Coding Plan 用户均可调用
  - 最强性能

#### 2. GLM-5
- **发布时间**: 2026年2月12日
- **参数规模**: 744B 总参数，40B 激活参数
- **上下文**: 支持 200K
- **特点**:
  - 面向 Agentic Engineering 打造
  - 擅长复杂系统工程与长程 Agent 任务
  - 在 SWE-bench-Verified 和 Terminal Bench 2.0 表现优异
  - Coding 与 Agent 能力达到开源 SOTA 水平

#### 3. GLM-5-Turbo
- **定位**: OpenClaw 专用优化模型
- **特点**:
  - 专门针对 OpenClaw（智谱的Agent框架）场景深度优化
  - 工具调用能力强
  - 指令遵循优秀
  - 定时与持续性任务优化
  - 长链路任务优化

### GLM-4系列

#### 4. GLM-4.7
- **定位**: 高性能旗舰
- **支持**: Coding Plan 部分套餐
- **特点**: 平衡性能与成本

#### 5. GLM-4.6 / GLM-4.6V
- **GLM-4.6**: 通用版本
- **GLM-4.6V**: 视觉理解版本

#### 6. GLM-4.5
- **定位**: 早期版本
- **特点**: 成本优化

### 模型对比

| 模型 | 参数 | 上下文 | 定位 | 推荐场景 |
|------|------|--------|------|---------|
| **GLM-5.1** | - | - | 最新旗舰 | 所有场景 |
| **GLM-5** | 744B/40B | 200K | Agentic | 复杂Agent任务 |
| **GLM-5-Turbo** | - | - | OpenClaw优化 | Agent工具调用 |
| **GLM-4.7** | - | - | 高性能 | 代码生成 |
| **GLM-4.6V** | - | - | 视觉理解 | 图像分析 |

---

## 🔌 MCP Servers（模型上下文协议服务器）

智谱AI提供多个专用MCP服务器，扩展AI能力：

### 1. 视觉理解MCP Server 📸

**文档**: [视觉理解MCP](https://docs.bigmodel.cn/coding-plan/mcp/vision-mcp-server)

**功能**:
- 基于 GLM-4.6V 的视觉理解能力
- 为 Claude Code、Cline 等 MCP 兼容客户端提供图像分析
- 支持截图理解、UI分析、图表解读

**使用场景**:
- 截图分析
- UI界面理解
- 图表数据提取
- 代码截图转代码

**配置**:
```json
{
  "mcpServers": {
    "zhipu-vision": {
      "command": "npx",
      "args": ["-y", "@zhipuai/zhipu-vision-mcp"],
      "env": {
        "ZHIPU_API_KEY": "your-api-key"
      }
    }
  }
}
```

### 2. Web搜索MCP Server 🔍

**功能**:
- 强大的网络搜索能力
- 实时信息获取
- 多源信息整合

**使用场景**:
- 实时信息查询
- 技术文档搜索
- 问题排查

### 3. Web Reader MCP Server 📄

**功能**:
- 网页内容提取
- HTML解析
- 文本清理

**使用场景**:
- 文档抓取
- 网页分析
- 内容提取

### 4. Zread MCP - 开源仓库MCP 📦

**文档**: [Zread MCP](https://docs.bigmodel.cn/coding-plan/mcp/zread-mcp-server)

**功能**:
- 理解开源项目结构
- 分析文档和代码
- 代码库导航

**使用场景**:
- 开源项目理解
- 代码库分析
- 技术文档查询

**示例**:
```python
# 分析GitHub项目
result = await zread_mcp.analyze_repo(
    owner="vitejs",
    repo="vite"
)
```

### 5. ZAI MCP Server 🛠️

**功能**:
- 通用能力扩展
- 综合工具集

**使用场景**:
- 多功能组合
- 复杂任务编排

---

## 💻 集成工具

### Claude Code

**配置方式**:

1. **安装MCP插件**
```bash
# Claude Code会自动识别MCP服务器
```

2. **配置模型**
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

3. **选择模型**
```bash
# 在Claude Code中使用
/model glm-5.1
```

### Cline

**配置**:
```json
{
  "zhipuApiKey": "your-api-key",
  "mcpServers": {
    "zhipu-vision": {...},
    "zread": {...}
  }
}
```

### Kilo Code

**功能**:
- VS Code扩展
- 支持MCP
- 代码生成、调试、项目管理

---

## 🎯 使用指南

### 在灵知系统中使用

#### 方式1: 通过Token池

```python
from backend.services.ai_service import code_development

# 使用GLM-5（系统自动选择）
code = await code_development("实现一个LRU缓存")
```

#### 方式2: 指定模型

```python
from backend.services.evolution.free_token_pool import get_free_token_pool

pool = get_free_token_pool()

# 指定使用GLM-5.1
result = await pool.call_provider(
    "glm_coding",
    prompt="使用GLM-5.1生成代码",
    max_tokens=4000
)
```

### 配置到.env

```bash
# GLM Coding Plan API Key
GLM_CODING_PLAN_KEY=your-api-key

# 可选：指定默认模型
GLM_DEFAULT_MODEL=glm-5.1
```

---

## 📊 计费说明

### 套餐级别

| 套餐 | 价格 | 额度 | 适用模型 |
|------|------|------|---------|
| **Lite** | ¥20/月起 | 约120次/5小时 | GLM-4.7 |
| **Pro** | 中等 | 更多额度 | GLM-5系列 |
| **Max** | 高级 | 最大额度 | 全部模型 |

### 高峰模式计费

- GLM-5.1、GLM-5、GLM-5-Turbo 作为**高阶模型**
- 按"高峰模式"计费
- 对标 Claude Opus

### 成本优势

**包月 vs 按量**:
- 包月使用越多越划算
- 当前您使用：260万tokens/30天
- 比按量付费节省 **60-70%**

---

## 🚀 最佳实践

### 模型选择策略

```python
# 1. 最强性能 → GLM-5.1
if task_complexity == "highest":
    model = "glm-5.1"

# 2. Agent任务 → GLM-5
elif task_type == "agent":
    model = "glm-5"

# 3. 工具调用 → GLM-5-Turbo
elif need_tool_calling:
    model = "glm-5-turbo"

# 4. 日常使用 → GLM-4.7
else:
    model = "glm-4.7"
```

### MCP使用建议

**视觉任务**:
```python
# 使用Vision MCP
await vision_mcp.analyze_image(screenshot_path)
```

**开源项目分析**:
```python
# 使用Zread MCP
await zread_mcp.analyze_repo("owner/repo")
```

**实时信息**:
```python
# 使用Web Search MCP
await web_search_mcp.search("最新技术动态")
```

---

## 📚 相关资源

### 官方文档
- **Coding Plan概览**: https://docs.bigmodel.cn/coding-plan/overview
- **Vision MCP**: https://docs.bigmodel.cn/coding-plan/mcp/vision-mcp-server
- **Zread MCP**: https://docs.bigmodel.cn/coding-plan/mcp/zread-mcp-server
- **GLM-5-Turbo**: https://docs.bigmodel.cn/coding-plan/models/glm-5-turbo

### 开发工具
- **Claude Code**: Anthropic的AI开发环境
- **Cline**: VS Code AI助手
- **Kilo Code**: 智谱AI的VS Code扩展

### 本系统集成
- **配置文件**: `.env`
- **AI服务**: `backend/services/ai_service.py`
- **Token池**: `backend/services/evolution/free_token_pool.py`

---

## ✅ 总结

### 支持的模型（7个）

1. **GLM-5.1** ⭐ 最新旗舰
2. **GLM-5** - 744B参数，200K上下文
3. **GLM-5-Turbo** - OpenClaw优化
4. **GLM-4.7** - 高性能
5. **GLM-4.6** - 通用版本
6. **GLM-4.6V** - 视觉理解
7. **GLM-4.5** - 成本优化

### MCP服务器（5个）

1. **Vision MCP** - 视觉理解
2. **Web Search MCP** - 网络搜索
3. **Web Reader MCP** - 网页提取
4. **Zread MCP** - 开源仓库
5. **ZAI MCP** - 通用能力

### 集成状态

✅ **已配置**: GLM Coding Plan API Key
✅ **已集成**: Token池（优先级0）
✅ **已测试**: 代码生成功能
✅ **可用**: 7个模型 + 5个MCP服务器

---

**🎉 您的GLM Coding Plan已完全配置，支持所有最新模型和MCP能力！**

**众智混元，万法灵通** ⚡🚀

---

**Sources:**
- [智谱AI开放文档 - Coding Plan](https://docs.bigmodel.cn/coding-plan/overview)
- [IT之家 - GLM-5.1发布](https://www.ithome.com/0/933/487.htm)
- [视觉理解MCP文档](https://docs.bigmodel.cn/coding-plan/mcp/vision-mcp-server)
