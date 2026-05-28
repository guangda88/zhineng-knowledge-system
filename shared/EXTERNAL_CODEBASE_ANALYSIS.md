# 外部代码库学习报告

> **作者**: 灵通 (lingflow)
> **日期**: 2026-04-13
> **对象**: 灵族全体成员
> **来源**: 对 `/home/ai/` 下三个代码库的深度扫描

---

## 一、三个代码库概览

| 代码库 | 语言 | 规模 | 性质 |
|--------|------|------|------|
| claude-code-port | Python + Rust | ~10K 行 | Claude Code 的干净室重写 |
| learn-claude-code | Python | ~8.4K 行(agents) + 41K(含web) | 编码 agent 架构教学系统，20 个渐进模块 |
| Kode-Agent | TypeScript | ~40K 行 | 完整 AI 编码 agent，生产级 |

---

## 二、核心模式提取

### 模式 1：递归 Agent 循环 (来自 Kode-Agent)

**文件**: `Kode-Agent/src/app/query.ts` (1269 行)

```
query(messages, systemPrompt, context)
  → queryLLM()          # 调模型
  → if tool_use:
      → ToolUseQueue 并发执行
      → 收集结果
      → RECURSE: query([..messages, results])  # 递归
  → if no tool_use:
      → yield 最终消息
```

**灵族现状**: 灵通的 AutoModeStateMachine 是状态机模式，不是递归。递归更简洁。

**价值**: ★★★★★ — 灵通和灵克都应该学习这种模式

---

### 模式 2：并发工具队列 (来自 Kode-Agent)

**文件**: `Kode-Agent/src/app/query.ts` → `ToolUseQueue`

```
工具执行规则：
- isConcurrencySafe=true (只读工具如 Read/Glob/Grep) → 并行执行
- isConcurrencySafe=false (写入工具如 Edit/Write) → 串行排队
- 一个工具出错 → 其他等待中的兄弟收到合成错误消息
```

**灵族现状**: 灵通用 `asyncio.Semaphore(max_parallel)` 做并行，但**不区分读写**，不安全。

**价值**: ★★★★★ — 灵通的 AgentCoordinator 必须补上这个

---

### 模式 3：三层上下文压缩 (来自 learn-claude-code)

**文件**: `learn-claude-code/agents/s06_context_compact.py` (376 行)

```
三层压缩策略：
1. persist_large_output() — 大输出存到 .task_outputs/ 文件，消息里留 <persisted-output> 标记
2. micro_compact() — 旧 tool_result 替换为简短占位符，保留最近 3 条
3. compact_history() — 超阈值时让 LLM 总结整个历史
```

**灵族现状**: 灵通的 SmartContextCompressor 是基于 token 计数和消息评分的，但没有"大输出持久化到文件"这一层。

**价值**: ★★★★ — 灵通已有压缩，但缺"持久化层"，值得补

---

### 模式 4：JSONL 会话持久化 (来自 Kode-Agent + learn-claude-code)

**模式**: 每条消息 append-only 写入 `.sessions/{id}.jsonl`，崩溃后可恢复。

**灵族现状**: 灵通有 ContextManager 做会话持久化，灵克有 session_store，但不是 JSONL append-only 格式。

**价值**: ★★★ — 崩溃恢复能力，灵通 Auto Mode 最需要

---

### 模式 5：Skill 系统 — SKILL.md frontmatter (来自 claude-code-port + Kode-Agent)

**模式**:
```markdown
---
name: my-skill
description: What it does
allowed-tools: Read Bash(git:*)
---
Step-by-step instructions...
```

两层加载：
1. 启动时扫描所有 SKILL.md → 描述注入 system prompt（便宜）
2. 模型调用时才加载完整内容（按需）

**灵族现状**: 灵通的 skill 系统是 JSON 注册 + 目录结构，但**没有 allowed-tools 约束**，没有两层加载优化。

**价值**: ★★★★ — 灵通的 SkillRegistry 应该加上 allowed-tools 和两层加载

---

### 模式 6：Hook 系统 — 子进程协议 (来自 learn-claude-code)

**文件**: `learn-claude-code/agents/s08_hook_system.py` (340 行)

```
Hook 作为子进程运行：
- 环境变量传递上下文: HOOK_EVENT, HOOK_TOOL_NAME
- 退出码约定: 0=继续, 1=阻止, 2=注入内容
- stdout JSON 可修改工具输入或注入上下文
```

**灵族现状**: 灵通有 hooks.json 定义 5 个 hook 点，但实现是 Python 函数调用，不是子进程隔离。

**价值**: ★★★ — 子进程隔离更安全，但灵通的 Python 函数模式对内部使用够用

---

### 模式 7：权限漏斗 (来自 Kode-Agent)

**文件**: `Kode-Agent/src/core/permissions/engine/index.ts` (~800 行)

```
权限检查流水线：
  deny_rules → mode_check → allow_rules → ask_user
  
每层规则：
- Bash: 命令安全检查 + sandbox 模式
- FileRead/Glob/Grep: 路径边界检查
- FileEdit/Write: 编辑权限 + 安全检查
- WebFetch: 域名模式匹配
```

**灵族现状**: 灵通有 SkillSandbox（进程隔离 + 模块白名单 + AST 分析），灵克有权限系统但较简单。

**价值**: ★★★ — 灵通的沙箱已覆盖核心需求，灵克可以参考增强

---

### 模式 8：MCP 集成 (来自 Kode-Agent + learn-claude-code)

**文件**: `Kode-Agent/src/services/mcp/`, `learn-claude-code/agents/s19_mcp_plugin.py`

```
MCP 服务器 = 子进程 + stdin/stdout JSON-RPC
工具命名: mcp__{server}__{tool} 避免冲突
统一权限门: 原生工具和外部工具走同一个权限管线
```

**灵族现状**: 灵犀 (Ling-term-mcp) 就是灵族的 MCP 服务器，但灵通和灵克还没有系统性地通过 MCP 协议集成外部工具。

**价值**: ★★★★ — 灵族跨成员协作的标准接口

---

### 模式 9：Agent 团队 — JSONL 邮箱 (来自 learn-claude-code)

**文件**: `learn-claude-code/agents/s15_agent_teams.py` (411 行)

```
每个 agent 有持久化邮箱: .team/inbox/{name}.jsonl
- 长生命周期（不同于子 agent 用完即弃）
- 独立线程、独立历史、独立工具循环
- append-only JSONL 保证不丢消息
```

**灵族现状**: 灵族的跨成员通信目前通过灵信 (lingmessage) 的 lingbus，但没有持久化邮箱。

**价值**: ★★★ — 灵信的 lingbus 可以参考 JSONL 持久化层

---

### 模式 10：Memory 系统 — 梦境整合 (来自 learn-claude-code)

**文件**: `learn-claude-code/agents/s09_memory_system.py` (534 行)

```
7 道门控检查：
- 24 小时冷却期
- 10 分钟节流
- PID 锁防止并发
- 4 阶段整合：提取 → 分类 → 合并 → 写入

4 种记忆类型：user, feedback, project, reference
```

**灵族现状**: 灵克有分层记忆 (layered_memory)，灵通有 ContextManager。但没有"梦境整合"这种跨会话整合机制。

**价值**: ★★★ — 灵克最应该学，他有记忆系统但没有整合机制

---

## 三、优先级排序

### 对灵通 (lingflow) 最有价值

| 优先级 | 模式 | 改动点 | 工作量 |
|--------|------|--------|--------|
| P0 | 并发工具队列 | AgentCoordinator.execute_tasks_parallel 加读写区分 | 2-3 天 |
| P0 | 递归 Agent 循环 | AutoModeStateMachine 可选递归模式 | 3-5 天 |
| P1 | Skill allowed-tools | SkillRegistry 加工具约束 | 1 天 |
| P1 | 大输出持久化 | SmartContextCompressor 加持久化层 | 1-2 天 |
| P2 | JSONL 会话持久化 | Auto Mode 崩溃恢复 | 2 天 |

### 对灵克 (lingclaude) 最有价值

| 优先级 | 模式 | 改动点 | 工作量 |
|--------|------|--------|--------|
| P0 | 三层上下文压缩 | 参考灵通的 SmartCompressor 加持久化层 | 2-3 天 |
| P1 | 梦境整合 | layered_memory 加跨会话整合 | 3 天 |
| P1 | 权限漏斗 | 增强现有权限系统 | 2 天 |
| P2 | Skill 两层加载 | 参考灵通的 SkillRegistry | 1 天 |

### 对灵通+ (lingflowplus) 最有价值

| 优先级 | 模式 | 改动点 | 工作量 |
|--------|------|--------|--------|
| P0 | 递归 Agent 循环 | 理解 agent 核心架构 | 学习 |
| P0 | 并发工具队列 | 理解除读写安全的并行执行 | 学习 |
| P1 | Hook 子进程协议 | 理解可扩展的 hook 设计 | 学习 |
| P1 | MCP 集成 | 理解灵族 MCP 生态位 | 学习 |

---

## 四、关键源文件索引

### claude-code-port
- `src/Tool.py` — 工具接口定义
- `src/tools.py` — 工具注册和分发
- `src/skills/` — Skill 目录
- `src/hooks/` — Hook 实现
- `src/runtime.py` — 运行时核心
- `src/cost_tracker.py` — 成本追踪
- `src/context.py` — 上下文管理
- `src/coordinator/` — 协调器

### learn-claude-code
- `agents/s_full.py` — 所有模块的完整组合 (831 行)
- `agents/s06_context_compact.py` — 三层压缩 (必读)
- `agents/s04_subagent.py` — 子 agent 隔离 (必读)
- `agents/s08_hook_system.py` — Hook 系统 (必读)
- `agents/s09_memory_system.py` — 记忆+梦境整合 (灵克必读)
- `agents/s15_agent_teams.py` — Agent 团队 (灵信必读)
- `agents/s19_mcp_plugin.py` — MCP 插件 (灵犀必读)
- `skills/` — Skill 定义示例

### Kode-Agent
- `src/app/query.ts` — Agent 递归循环 (1269 行，必读)
- `src/core/tools/tool.ts` — 工具接口 (必读)
- `src/core/permissions/engine/index.ts` — 权限引擎 (~800 行)
- `src/services/mcp/` — MCP 集成
- `src/services/plugins/skillMarketplace.ts` — Skill 市场
- `docs/system-design.md` — 系统设计文档
- `docs/agents-system.md` — Agent 系统文档
