# Task 4: 渐进式 Agent Loop

**学习日期**: 2026-04-14
**来源**: learn-claude-code/agents/s01-s08 (8个渐进模块）
**任务**: 理解从最简循环到完整系统的渐进式学习路径

---

## What - 学到了什么

### 渐进式 Agent Loop 的核心哲学

learn-claude-code 实现了一个**从零到完整的渐进式教学框架**，每个模块都是独立可运行的，修改参数看效果。

**核心洞察**：每个新模块在上一模块的基础上**只添加一个核心概念**，不改变已有结构。

#### 8 个渐进模块概览

| 模块 | 核心概念 | 关键代码 | 代码行数 |
|-------|----------|---------|---------|
| **s01** | 最简代理循环 | `LoopState`, `run_one_turn()`, `agent_loop()` | ~165 |
| **s02** | 工具分发 | `TOOL_HANDLERS`, `normalize_messages()` | ~209 |
| **s03** | 会话规划 | `TodoManager`, `PlanItem`, `PLAN_REMINDER_INTERVAL=3` | ~335 |
| **s04** | 子代理隔离 | `run_subagent()`, `AgentTemplate` | ~ |
| **s05** | 技能按需加载 | `SkillRegistry`, `load_full_text()` | ~ |
| **s06** | 上下文压缩 | `persist_large_output()`, `summarize_history()` | ~ |
| **s07** | 权限系统 | (见 Task 1) | ~ |
| **s08** | Hook 协议 | (见 Task 2) | ~ |

---

### s01: 最简代理循环

**核心思想**：最小化的 ReAct 循环

```python
@dataclass
class LoopState:
    # 最小循环状态：历史、轮次计数、继续原因
    messages: list
    turn_count: int = 1
    transition_reason: str | None = None

def run_one_turn(state: LoopState) -> bool:
    """执行一轮，返回是否继续"""
    response = client.messages.create(
        model=MODEL,
        system=SYSTEM,
        messages=state.messages,
        tools=TOOLS,
        max_tokens=8000,
    )
    state.messages.append({"role": "assistant", "content": response.content})

    # 终止条件 1: 没有 tool_use
    if response.stop_reason != "tool_use":
        state.transition_reason = None
        return False

    # 执行工具
    results = execute_tool_calls(response.content)
    if not results:
        state.transition_reason = None
        return False

    state.messages.append({"role": "user", "content": results})
    state.turn_count += 1
    state.transition_reason = "tool_result"
    return True  # 继续循环

def agent_loop(state: LoopState) -> None:
    while run_one_turn(state):
        pass
```

**关键特性**：
1. **显式状态**：`LoopState` 类保存循环状态
2. **单一职责**：`run_one_turn()` 只做一件事（执行一轮）
3. **明确终止**：`response.stop_reason != "tool_use"` 时停止
4. **自描述**：`transition_reason` 记录为什么继续/停止

---

### s02: 工具分发 + 消息规范化

**核心思想**：循环不变，只添加工具

```python
# 核心洞察："The loop didn't change at all. I just added tools."

# 并发安全分类
CONCURRENCY_SAFE = {"read_file"}
CONCURRENCY_UNSAFE = {"write_file", "edit_file"}

# 工具处理映射
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

def normalize_messages(messages: list) -> list:
    """清理消息，API 调用前必须执行

    三个工作：
    1. Strip 内部元数据字段（API 不理解）
    2. 确保每个 tool_use 有匹配的 tool_result（插入占位符）
    3. 合并连续同角色消息（API 要求严格交替）
    """
    cleaned = []
    for msg in messages:
        clean = {"role": msg["role"]}
        # Strip 内部字段
        if isinstance(msg.get("content"), str):
            clean["content"] = msg["content"]
        elif isinstance(msg.get("content"), list):
            clean["content"] = [
                {k: v for k, v in block.items()
                 if not k.startswith("_")}
                for block in msg["content"]
                if isinstance(block, dict)
            ]
        else:
            clean["content"] = msg.get("content", "")
        cleaned.append(clean)

    # 查找孤儿 tool_use 并插入占位符
    existing_results = set()
    for msg in cleaned:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    existing_results.add(block.get("tool_use_id"))

    for msg in cleaned:
        if msg["role"] != "assistant" or not isinstance(msg.get("content"), list):
            continue
        for block in msg["content"]:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("id") not in existing_results:
                cleaned.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": block["id"],
                     "content": "(cancelled)"}
                ]})

    # 合并连续同角色消息
    if not cleaned:
        return cleaned
    merged = [cleaned[0]]
    for msg in cleaned[1:]:
        if msg["role"] == merged[-1]["role"]:
            prev = merged[-1]
            prev_c = prev["content"] if isinstance(prev["content"], list) \
                else [{"type": "text", "text": str(prev["content"])}]
            curr_c = msg["content"] if isinstance(msg["content"], list) \
                else [{"type": "text", "text": str(msg["content"])}]
            prev["content"] = prev_c + curr_c
        else:
            merged.append(msg)
    return merged
```

**关键特性**：
1. **工具处理映射**：`TOOL_HANDLERS` 字典分发到具体函数
2. **并发安全分类**：`CONCURRENCY_SAFE/UNSAFE` 声明工具属性
3. **消息规范化**：`normalize_messages()` 清理元数据、修复孤儿工具、合并同角色

---

### s03: 会话规划（TodoWrite）

**核心思想**：轻量级会话计划，不是持久化任务图

```python
@dataclass
class PlanItem:
    content: str
    status: str = "pending"  # pending, in_progress, completed
    active_form: str = ""  # 当前进行的分步描述

@dataclass
class PlanningState:
    items: list[PlanItem] = field(default_factory=list)
    rounds_since_update: int = 0  # 跟踪多少轮未更新计划

class TodoManager:
    PLAN_REMINDER_INTERVAL = 3  # 3 轮未更新提醒

    def update(self, items: list) -> str:
        """更新计划，验证约束"""
        # 约束 1: 最大 12 个项目
        if len(items) > 12:
            raise ValueError("Keep to session plan short (max 12 items)")

        # 约束 2: 只能有一个 in_progress
        in_progress_count = 0
        for index, raw_item in enumerate(items):
            status = str(raw_item.get("status", "pending")).lower()
            if status == "in_progress":
                in_progress_count += 1

        if in_progress_count > 1:
            raise ValueError("Only one plan item can be in_progress")

        self.state.items = normalized
        self.state.rounds_since_update = 0
        return self.render()

    def note_round_without_update(self) -> None:
        """记录一轮未更新计划"""
        self.state.rounds_since_update += 1

    def reminder(self) -> str | None:
        """如果 3 轮未更新，返回提醒"""
        if not self.state.items:
            return None
        if self.state.rounds_since_update < self.PLAN_REMINDER_INTERVAL:
            return None
        return "<reminder>Refresh your current plan before continuing.</reminder>"

    def render(self) -> str:
        """渲染计划为 Markdown"""
        lines = []
        for item in self.state.items:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]",
            }[item.status]
            line = f"{marker} {item.content}"
            if item.status == "in_progress" and item.active_form:
                line += f" ({item.active_form})"
            lines.append(line)

        completed = sum(1 for item in self.state.items if item.status == "completed")
        lines.append(f"\n({completed}/{len(self.state.items)} completed)")
        return "\n".join(lines)
```

**关键特性**：
1. **轻量级**：不是持久化任务图，仅当前会话
2. **约束验证**：最多 12 个项目，只能一个 `in_progress`
3. **主动提醒**：3 轮未更新自动提醒
4. **可视化渲染**：`[ ]`, `[>]`, `[x]` 标记状态

---

### s04: 子代理隔离

**核心思想**：子代理在新的消息上下文中运行，共享文件系统

```
Parent agent                     Subagent
+------------------+             +------------------+
| messages=[...]   |             | messages=[]      |  <-- fresh context
|                  |  dispatch   |                  |
| tool: task       | ---------->| while tool_use:  |
|   prompt="..."   |            |   call tools     |
|   description="" |            |   append results |
|   result = "..." |  summary   |                  |
| <--------- |             <--------- |
Parent context stays clean.
Subagent context is discarded.
```

**关键洞察**：`messages=[]` 给予上下文隔离

```python
def run_subagent(prompt: str) -> str:
    """子代理在新的消息上下文中运行"""
    sub_messages = [{"role": "user", "content": prompt}]  # fresh context
    for _ in range(30):  # safety limit
        response = client.messages.create(
            model=MODEL, system=SUBAGENT_SYSTEM, messages=sub_messages,
            tools=CHILD_TOOLS, max_tokens=8000,
        )
        sub_messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        # ... 执行工具 ...

    # 只有最终文本返回给父代理 —— 子代理上下文被丢弃
    return "".join(b.text for b in response.content if hasattr(b, "text")) or "(no summary)"
```

**与真实 Claude Code 对比**：

| 维度 | 教学实现 | 真实 Claude Code |
|-----|----------|----------------|
| **后端** | 仅 in-process | 5 种：in-process, tmux, iTerm2, fork, remote |
| **上下文隔离** | `messages=[]` | `createSubagentContext()` 隔离 ~20 个字段 |
| **工具过滤** | 手动筛选 | `resolveAgentTools()` 从父代理池过滤 |
| **代理定义** | 硬编码系统提示 | `.claude/agents/*.md` YAML frontmatter |

---

### s05: 技能按需加载

**核心思想**：两层技能模型 —— 系统提示中的廉价目录 + 按需加载完整内容

```python
class SkillRegistry:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.documents: dict[str, SkillDocument] = {}
        self._load_all()  # 扫描所有 SKILL.md

    def _load_all(self) -> None:
        """扫描 skills/ 目录，加载所有 SKILL.md"""
        for path in sorted(self.skills_dir.rglob("SKILL.md")):
            meta, body = self._parse_frontmatter(path.read_text())
            name = meta.get("name", path.parent.name)
            description = meta.get("description", "No description")
            manifest = SkillManifest(name=name, description=description, path=path)
            self.documents[name] = SkillDocument(manifest=manifest, body=body.strip())

    def describe_available(self) -> str:
        """生成廉价技能目录（仅名称+描述）"""
        if not self.documents:
            return "(no skills available)"
        lines = []
        for name in sorted(self.documents):
            manifest = self.documents[name].manifest
            lines.append(f"- {manifest.name}: {manifest.description}")
        return "\n".join(lines)

    def load_full_text(self, name: str) -> str:
        """仅在被请求时加载完整技能内容"""
        document = self.documents.get(name)
        if not document:
            return f"Error: Unknown skill '{name}'"

        return (
            f"<skill name=\"{document.manifest.name}\">\n"
            f"{document.body}\n"
            f"</skill>"
        )

# 系统提示仅包含廉价目录
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill when a task needs specialized instructions before you act.

Skills available:
{SKILL_REGISTRY.describe_available()}
"""
```

**关键特性**：
1. **廉价目录**：系统提示中仅列出名称+描述
2. **按需加载**：完整内容仅在模型请求时加载
3. **保持提示小**：避免将所有技能内容塞入提示

---

### s06: 上下文压缩

**核心思想**：大型工具输出持久化到磁盘，并用占位符标记

```python
CONTEXT_LIMIT = 50000
KEEP_RECENT_TOOL_RESULTS = 3  # 仅保留最近 3 个完整结果
PERSIST_THRESHOLD = 30000  # 超过 30KB 持久化
PREVIEW_CHARS = 2000  # 占位符中包含 2KB 预览
TOOL_RESULTS_DIR = WORKDIR / ".task_outputs" / "tool-results"

def persist_large_output(tool_use_id: str, output: str) -> str:
    """大型输出持久化到磁盘，返回占位符"""
    if len(output) <= PERSIST_THRESHOLD:
        return output

    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = TOOL_RESULTS_DIR / f"{tool_use_id}.txt"
    if not stored_path.exists():
        stored_path.write_text(output)

    preview = output[:PREVIEW_CHARS]
    rel_path = stored_path.relative_to(WORKDIR)
    return (
        "<persisted-output>\n"
        f"Full output saved to: {rel_path}\n"
        "Preview:\n"
        f"{preview}\n"
        "</persisted-output>"
    )

def micro_compact(messages: list) -> list:
    """微压缩：旧工具结果替换为占位符"""
    tool_results = collect_tool_result_blocks(messages)
    if len(tool_results) <= KEEP_RECENT_TOOL_RESULTS:
        return messages

    # 旧结果替换为占位符
    for _, _, block in tool_results[:-KEEP_RECENT_TOOL_RESULTS]:
        content = block.get("content", "")
        if not isinstance(content, str) or len(content) <= 120:
            continue
        block["content"] = "[Earlier tool result compacted. Re-run tool if you need full detail.]"
    return messages

def summarize_history(messages: list) -> str:
    """LLM 摘要历史"""
    conversation = json.dumps(messages, default=str)[:80000]
    prompt = (
        "Summarize this coding-agent conversation so work can continue.\n"
        "Preserve:\n"
        "1. The current goal\n"
        "2. Important findings and decisions\n"
        "3. Files read or changed\n"
        "4. Remaining work\n"
        "5. User constraints and preferences\n"
        "Be compact but concrete.\n\n"
        f"{conversation}"
    )
    response = client.messages.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )
    return response.content[0].text.strip()

def compact_history(messages: list, state: CompactState, focus: str | None = None) -> list:
    """压缩历史：持久化 + 微压缩 + LLM 摘要"""
    transcript_path = write_transcript(messages)

    summary = summarize_history(messages)
    if focus:
        summary += f"\n\nFocus to preserve next: {focus}"
    if state.recent_files:
        recent_lines = "\n".join(f"- {path}" for path in state.recent_files)
        summary += f"\n\nRecent files to reopen if needed:\n{recent_lines}"

    state.has_compacted = True
    state.last_summary = summary

    return [{"role": "user", "content": summary}]
```

**关键特性**：
1. **持久化大型输出**：>30KB 写入磁盘
2. **占位符**：包含 2KB 预览 + 文件路径
3. **微压缩旧结果**：仅保留最近 3 个完整结果
4. **LLM 摘要**：当整个对话过大时，生成摘要

---

### s07 + s08: 权限系统 + Hook 协议

已在 Task 1 和 Task 2 中详细学习。

---

## Why - 为什么重要

### 1. 渐进式学习的优势

| 学习方式 | 传统一次性学习 | 渐进式学习（learn-claude-code） |
|---------|--------------|-----------------------------|
| **认知负荷** | 高（一次学完所有概念） | 低（每次只学一个新概念） |
| **可调试性** | 差（难以定位哪个概念有问题） | 好（每个模块独立可运行） |
| **学习曲线** | 陡峭 | 平缓 |
| **迭代反馈** | 慢（需要重新学习全部） | 快（仅修复特定模块） |

### 2. 循环不变原则

所有 8 个模块的核心循环结构**完全不变**：

```python
def agent_loop(messages: list) -> None:
    while True:
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=normalize_messages(messages),  # s02+
            tools=TOOLS,
            max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown: {block.name}"
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})

        messages.append({"role": "user", "content": results})
```

**每次添加的功能都是外围的**：
- s01: 核心循环
- s02: 工具分发（`TOOL_HANDLERS`）+ 消息规范化（`normalize_messages`）
- s03: 计划提醒（插入 `<reminder>`）
- s04: 子代理工具（`task` 工具）
- s05: 技能加载（`load_skill` 工具）
- s06: 上下文压缩（修改消息内容）
- s07: 权限检查（工具调用前检查）
- s08: Hooks（预/后/停止钩子）

---

## How - 如何应用到 lingflowplus

### 改进方案：实现渐进式教学框架

#### 阶段 1：创建教学模块结构

```
lingflow_plus/teaching/
  ├── s01_minimal_loop.py       # 最简代理循环
  ├── s02_tool_dispatch.py      # 工具分发
  ├── s03_session_plan.py       # 会话规划
  ├── s04_subagent.py          # 子代理隔离
  ├── s05_skill_loading.py      # 技能按需加载
  ├── s06_context_compact.py    # 上下文压缩
  ├── s07_permission_system.py  # 权限系统
  ├── s08_hook_system.py       # Hook 协议
  ├── s_full.py                # 完整 capstone（整合所有）
  └── run_module.py            # 统一入口（python teaching/s01.py ...）
```

#### 阶段 2：实现教学模块

**s01_minimal_loop.py**（核心）：
```python
@dataclass(frozen=True)
class LoopState:
    messages: list
    turn_count: int = 1
    transition_reason: str | None = None

def run_one_turn(state: LoopState, provider, tools) -> bool:
    """执行一轮，返回是否继续"""
    response = provider.complete(
        messages=state.messages,
        tools=tools,
        max_tokens=8000,
    )
    state.messages.append({"role": "assistant", "content": response.content})

    # 终止条件：没有工具调用
    if not response.tool_calls:
        state.transition_reason = "no_tools"
        return False

    # 执行工具
    results = []
    for tool_call in response.tool_calls:
        output = execute_tool(tool_call.name, tool_call.arguments)
        results.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": output,
        })

    state.messages.append({"role": "user", "content": results})
    state.turn_count += 1
    state.transition_reason = "tool_result"
    return True

def agent_loop(state: LoopState, provider, tools):
    while run_one_turn(state, provider, tools):
        pass
```

**s02_tool_dispatch.py**（工具分发）：
```python
# 核心洞察："The loop didn't change at all. I just added tools."

TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"]),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    # ...
}

def normalize_messages(messages: list) -> list:
    """清理消息（strip 元数据、修复孤儿工具、合并同角色）"""
    # ... 实现 ...

# agent_loop() 完全不变
def agent_loop(state: LoopState, provider, tools):
    while run_one_turn(state, provider, tools):
        pass
```

**s03_session_plan.py**（会话规划）：
```python
@dataclass(frozen=True)
class PlanItem:
    content: str
    status: str = "pending"  # pending, in_progress, completed
    active_form: str = ""

@dataclass(frozen=True)
class PlanningState:
    items: tuple[PlanItem, ...] = ()
    rounds_since_update: int = 0

class TodoManager:
    PLAN_REMINDER_INTERVAL = 3

    def update(self, items: list) -> str:
        """更新计划，验证约束（最多 12 个，只能 1 个 in_progress）"""
        # ... 实现 ...

    def reminder(self) -> str | None:
        """3 轮未更新提醒"""
        if self.state.rounds_since_update < self.PLAN_REMINDER_INTERVAL:
            return None
        return "<reminder>Refresh your current plan before continuing.</reminder>"

    def render(self) -> str:
        """渲染 Markdown"""
        # ... 实现 ...

# agent_loop() 增加计划提醒
def agent_loop(state: LoopState, provider, tools, todo_manager):
    while True:
        # ... 原有循环 ...

        # 新增：检查是否需要计划提醒
        reminder = todo_manager.reminder()
        if reminder:
            # 插入提醒消息
            pass

        # 新增：如果使用 todo 工具，重置计数器
        if used_todo_tool:
            todo_manager.state.rounds_since_update = 0
        else:
            todo_manager.note_round_without_update()
```

#### 阶段 3：实现 s_full.py（完整整合）

```python
# s_full.py - 完整 capstone，整合所有概念

from s01_minimal_loop import LoopState, run_one_turn
from s02_tool_dispatch import TOOL_HANDLERS, normalize_messages
from s03_session_plan import TodoManager, PlanItem
from s04_subagent import run_subagent
from s05_skill_loading import SkillRegistry
from s06_context_compact import CompactState, compact_history

def agent_loop(
    messages: list,
    provider,
    tools,
    todo_manager: TodoManager,
    skill_registry: SkillRegistry,
    compact_state: CompactState,
):
    """完整代理循环，整合所有 8 个模块"""
    while True:
        # s02: 消息规范化
        normalized_messages = normalize_messages(messages)

        # s05: 注入技能目录到系统提示
        skill_catalog = skill_registry.describe_available()
        system_prompt = f"""You are a coding agent.
Skills available:
{skill_catalog}
"""

        # s01: 核心循环（一轮）
        response = provider.complete(
            messages=normalized_messages,
            tools=tools,
            system_prompt=system_prompt,
        )
        messages.append({"role": "assistant", "content": response.content})

        # 终止条件：没有工具调用
        if not response.tool_calls:
            # s08: Stop Hooks
            run_stop_hooks(response)
            break

        # s02: 工具分发（执行所有工具调用）
        results = []
        for tool_call in response.tool_calls:
            # s07: 权限检查
            if not check_permission(tool_call.name, tool_call.arguments):
                results.append({"error": "Permission denied"})
                continue

            # s02: 工具处理映射
            if tool_call.name == "task":
                # s04: 子代理
                output = run_subagent(tool_call.arguments["prompt"])
            elif tool_call.name == "load_skill":
                # s05: 按需加载技能
                output = skill_registry.load_full_text(tool_call.arguments["name"])
            else:
                # s02: 标准工具
                handler = TOOL_HANDLERS.get(tool_call.name)
                output = handler(**tool_call.arguments) if handler else f"Unknown: {tool_call.name}"

            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output,
            })

        # s03: 如果使用 todo，重置计数器；否则记录一轮
        if any(tc.name == "todo" for tc in response.tool_calls):
            todo_manager.state.rounds_since_update = 0
        else:
            todo_manager.note_round_without_update()
            reminder = todo_manager.reminder()
            if reminder:
                # 插入提醒
                messages.append({"role": "user", "content": reminder})

        # s06: 上下文压缩（检查是否需要压缩）
        if estimate_context_size(messages) > CONTEXT_LIMIT:
            messages = compact_history(messages, compact_state)

        # 添加工具结果到消息
        messages.append({"role": "user", "content": results})
```

#### 阶段 4：统一入口脚本

```python
# run_module.py - 统一入口（python teaching/s01.py ...）

import sys
from pathlib import Path

MODULES = {
    "s01": "s01_minimal_loop",
    "s02": "s02_tool_dispatch",
    # ... s03-s08
    "s_full": "s_full",
}

def run_module(module_name: str):
    """运行指定模块"""
    if module_name not in MODULES:
        print(f"Error: Unknown module '{module_name}'")
        print(f"Available: {', '.join(MODULES.keys())}")
        return

    module_path = Path(__file__).parent / f"{MODULES[module_name]}.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 假设每个模块都有 main() 入口
    if hasattr(module, "main"):
        module.main()
    else:
        print(f"Error: Module '{module_name}' has no main() function")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_module.py <module_name>")
        print(f"Available modules: {', '.join(MODULES.keys())}")
        sys.exit(1)

    run_module(sys.argv[1])
```

---

## Summary - 总结

| 模块 | 核心概念 | 灵族对应 |
|-------|----------|----------|
| **s01** | 最简循环（LoopState, run_one_turn） | lingflow 的基础架构 |
| **s02** | 工具分发（TOOL_HANDLERS, normalize_messages） | lingflow 的 ToolRouter |
| **s03** | 会话规划（TodoManager, PLAN_REMINDER_INTERVAL） | lingflow 的任务系统 |
| **s04** | 子代理隔离（run_subagent, messages=[]） | 无（灵族没有子代理） |
| **s05** | 技能按需加载（SkillRegistry, load_full_text） | lingflow 的技能系统 |
| **s06** | 上下文压缩（persist_large_output, summarize） | lingflow 的压缩系统 |
| **s07** | 权限系统（Permission Funnel） | lingflow 的权限系统（待增强） |
| **s08** | Hook 协议（pre/post/stop hooks） | lingflow 无（灵族有 Daemon） |

**关键洞察**：
1. **循环不变原则**：所有模块的核心循环结构完全不变
2. **渐进式添加**：每次只添加一个外围功能
3. **独立可运行**：每个模块都是独立的，可直接测试
4. **教学友好**：修改参数看效果，降低学习门槛

---

## Next Steps - 下一步

- [ ] Task 5: 工具系统设计 isConcurrencySafe()

---

**学习笔记完成日期**: 2026-04-14
**作者**: 灵通 (lingflow)
