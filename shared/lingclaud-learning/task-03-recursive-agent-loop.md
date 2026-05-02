# Task 3: Recursive Agent Loop 递归代理循环

**学习日期**: 2026-04-14
**来源**: Kode-Agent/src/app/query.ts (~1269行)
**对比来源**: LingClaude/lingclaude/core/query_engine.py (~1150行)
**任务**: 理解递归代理循环的核心机制，对比两种实现模式

---

## What - 学到了什么

### Kode-Agent 递归代理循环的核心架构

Kode-Agent 实现了一个**基于 AsyncGenerator 的递归代理循环**，这是所有 coding agent 的核心执行模型。

#### 1. 主循环结构

```typescript
async function* queryCore(
  messages: Message[],
  systemPrompt: string[],
  context: { [k: string]: string },
  canUseTool: CanUseToolFn,
  toolUseContext: ExtendedToolUseContext,
  getBinaryFeedbackResponse?: (m1, m2) => Promise<BinaryFeedbackResult>,
): AsyncGenerator<Message, void> {
  // ========== 阶段 1: 准备 ==========
  markPhase('QUERY_INIT')

  // 1.1 自动压缩检查
  const { messages: processedMessages, wasCompacted } =
    await checkAutoCompact(messages, toolUseContext)
  if (wasCompacted) {
    messages = processedMessages
  }

  // 1.2 Bash 通知刷新
  if (toolUseContext.agentId === 'main') {
    const shell = BunShell.getInstance()
    const notifications = shell.flushBashNotifications()
    for (const notification of notifications) {
      const text = renderBashNotification(notification)
      messages = [...messages, createAssistantMessage(text)]
      yield messages[messages.length - 1]
    }
  }

  // 1.3 用户提交前 Hooks
  const userPromptText = extractUserPrompt(messages)
  const promptOutcome = await runUserPromptSubmitHooks({
    prompt: userPromptText,
    permissionMode: toolUseContext.options?.toolPermissionContext?.mode,
    cwd: getCwd(),
    signal: toolUseContext.abortController.signal,
  })
  if (promptOutcome.decision === 'block') {
    yield createAssistantMessage(promptOutcome.message)
    return
  }

  // ========== 阶段 2: 系统提示构建 ==========
  markPhase('SYSTEM_PROMPT_BUILD')

  // 2.1 注入 Plan Mode 系统提示
  const planModeAdditions = getPlanModeSystemPromptAdditions(
    messages as any[], toolUseContext,
  )
  if (planModeAdditions.length > 0) {
    fullSystemPrompt.push(...planModeAdditions)
  }

  // 2.2 注入 Hook 系统消息
  const hookAdditions = drainHookSystemPromptAdditions(toolUseContext)
  if (hookAdditions.length > 0) {
    fullSystemPrompt.push(...hookAdditions)
  }

  // 2.3 注入输出风格
  if (toolUseContext.agentId === 'main') {
    const outputStyleAdditions = getOutputStyleSystemPromptAdditions()
    if (outputStyleAdditions.length > 0) {
      fullSystemPrompt.push(...outputStyleAdditions)
    }
  }

  // 2.4 系统提醒（Reminders）
  const { systemPrompt: fullSystemPrompt, reminders } =
    formatSystemPromptWithContext(systemPrompt, context, toolUseContext.agentId)
  if (reminders && messages.length > 0) {
    // 将 reminders 注入到最后的用户消息
    messages = injectRemindersIntoLastUserMessage(messages, reminders)
  }

  // ========== 阶段 3: LLM 调用 ==========
  markPhase('LLM_PREPARATION')

  function getAssistantResponse() {
    return queryLLM(
      normalizeMessagesForAPI(messages),
      fullSystemPrompt,
      toolUseContext.options.maxThinkingTokens,
      toolUseContext.options.tools,
      toolUseContext.abortController.signal,
      {
        safeMode: toolUseContext.options?.safeMode ?? false,
        model: toolUseContext.options?.model || 'main',
        toolUseContext: toolUseContext,
      },
    )
  }

  // 3.1 支持 Binary Feedback（双响应验证）
  const result = await queryWithBinaryFeedback(
    toolUseContext,
    getAssistantResponse,
    getBinaryFeedbackResponse,
  )

  // 3.2 检查中断
  if (toolUseContext.abortController.signal.aborted) {
    yield createAssistantMessage(INTERRUPT_MESSAGE)
    return
  }

  // 3.3 检查空响应
  if (result.message === null) {
    yield createAssistantMessage(INTERRUPT_MESSAGE)
    return
  }

  const assistantMessage = result.message
  const shouldSkipPermissionCheck = result.shouldSkipPermissionCheck
  const toolUseMessages =
    assistantMessage.message.content.filter(isToolUseLikeBlock)

  // ========== 阶段 4: 工具执行 ==========
  yield assistantMessage

  // 4.1 如果没有工具调用，运行 Stop Hooks 并结束
  if (!toolUseMessages.length) {
    const stopOutcome = await runStopHooks({
      hookEvent: stopHookEvent,
      reason: String(stopReason ?? ''),
      agentId: toolUseContext.agentId,
      permissionMode: toolUseContext.options?.toolPermissionContext?.mode,
      cwd: getCwd(),
      signal: toolUseContext.abortController.signal,
    })
    yield assistantMessage
    return
  }

  // 4.2 如果有工具调用，创建 ToolUseQueue
  const siblingToolUseIDs = new Set<string>(toolUseMessages.map(_ => _.id))
  const toolQueue = new ToolUseQueue({
    toolDefinitions: toolUseContext.options.tools,
    canUseTool,
    toolUseContext,
    siblingToolUseIDs,
    shouldSkipPermissionCheck,
  })

  // 4.3 添加工具到队列
  for (const toolUse of toolUseMessages) {
    toolQueue.addTool(toolUse, assistantMessage)
  }

  // 4.4 等待工具执行完成
  const toolMessagesForNextTurn: (UserMessage | AssistantMessage)[] = []
  for await (const message of toolQueue.getRemainingResults()) {
    yield message
    if (message.type !== 'progress') {
      toolMessagesForNextTurn.push(message as UserMessage | AssistantMessage)
    }
  }

  // 4.5 更新上下文
  toolUseContext = toolQueue.getUpdatedContext()

  // ========== 阶段 5: 递归调用 ==========
  // 关键：递归调用 queryCore
  yield* await queryCore(
    [...messages, assistantMessage, ...toolMessagesForNextTurn],
    systemPrompt,
    context,
    canUseTool,
    toolUseContext,
    getBinaryFeedbackResponse,
    hookState,
  )
}
```

#### 2. ToolUseQueue 并发工具执行

Kode-Agent 的 `ToolUseQueue` 是核心创新，支持**并发安全**的工具执行：

```typescript
class ToolUseQueue {
  private tools: ToolQueueEntry[] = []

  addTool(toolUse: ToolUseBlock, assistantMessage: AssistantMessage) {
    const toolDefinition = this.toolDefinitions.find(t => t.name === resolvedToolName)
    const isConcurrencySafe =
      toolDefinition?.isConcurrencySafe(toolUse.input)

    this.tools.push({
      id: toolUse.id,
      block: toolUse,
      assistantMessage,
      status: 'queued',
      isConcurrencySafe,  // 关键：工具的并发安全属性
      pendingProgress: [],
    })

    void this.processQueue()  // 立即开始处理队列
  }

  private canExecuteTool(isConcurrencySafe: boolean) {
    const executing = this.tools.filter(t => t.status === 'executing')
    return (
      executing.length === 0 ||
      (isConcurrencySafe && executing.every(t => t.isConcurrencySafe))
    )
  }

  private async processQueue() {
    for (const entry of this.tools) {
      if (entry.status !== 'queued') continue

      if (this.canExecuteTool(entry.isConcurrencySafe)) {
        await this.executeTool(entry)
      } else {
        // 不能并发执行，生成"等待..."进度消息
        if (!entry.queuedProgressEmitted) {
          entry.pendingProgress.push(
            createProgressMessage('<tool-progress>Waiting…</tool-progress>')
          )
          entry.queuedProgressEmitted = true
        }

        if (!entry.isConcurrencySafe) {
          break  // 非并发安全工具阻止队列
        }
      }
    }
  }

  async *getRemainingResults(): AsyncGenerator<Message, void> {
    while (this.hasUnfinishedTools()) {
      await this.processQueue()

      for (const message of this.getCompletedResults()) {
        yield message
      }

      if (this.hasExecutingTools()) {
        // 等待任意一个工具完成或进度可用
        await Promise.race([...executingPromises, progressPromise])
      }
    }
  }
}
```

**关键特性**：
1. **`isConcurrencySafe`**：工具声明是否可以并发执行
   - 读操作：`isConcurrencySafe = true`
   - 写操作：`isConcurrencySafe = false`

2. **智能队列调度**：
   - 并发安全工具可以同时执行
   - 非并发安全工具必须串行执行
   - 进度消息立即产出，工具结果等待完成

3. **AsyncGenerator 结果流**：
   - `yield*` 流式产出进度和结果
   - 支持实时 UI 更新

#### 3. 循环终止条件

Kode-Agent 有多种终止条件：

| 条件 | 检查位置 | 行为 |
|-----|---------|------|
| **Abort Signal** | 每个 LLM 调用后 | `yield createAssistantMessage(INTERRUPT_MESSAGE)` |
| **Empty Response** | Binary Feedback 检查 | `yield createAssistantMessage(INTERRUPT_MESSAGE)` |
| **No Tool Calls** | assistant 解析 | 运行 Stop Hooks，return |
| **Stop Hook Block** | Stop Hooks | 最多重试 5 次，否则 block |
| **Max Iterations** | 外部限制 | (未在 queryCore 中，可能在调用方） |

### LingClaude 循环迭代代理

LingClaude 实现了一个**基于迭代的代理循环**，使用 `for round_idx in range(AGENT_MAX_TOOL_ROUNDS)`。

```python
def _call_model(self, prompt: str) -> str:
    messages = self._build_messages(prompt)
    tools = self._build_openai_tools(query=prompt)
    resolved_config, _ = self._resolve_model_config(prompt)
    used_tools = False
    response = None
    total_input = 0
    total_output = 0

    # 关键：迭代循环
    for round_idx in range(AGENT_MAX_TOOL_ROUNDS):  # 10 轮
        result = self._provider.complete(
            tuple(messages), config=resolved_config, tools=tools,
        )
        if result.is_error:
            self._track_behavior(prompt, f"[模型调用失败] {result.error}", used_tools=False)
            return f"[模型调用失败] {result.error}"

        response = result.data
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        # 检查终止条件 1: 没有工具调用
        if not response.tool_calls:
            content = response.content
            if self._should_hallucination_correct(prompt, used_tools):
                content = self._hallucination_correction(messages, content, tools, resolved_config)
                if content:
                    return self._finalize_turn(prompt, content, used_tools, total_input, total_output, resolved_config)
            return self._finalize_turn(prompt, response.content, used_tools, total_input, total_output, resolved_config)

        # 检查终止条件 2: 预算超预算
        projected = self._usage.add_turn(prompt, output)
        stop_reason = StopReason.COMPLETED
        if projected.input_tokens + projected.output_tokens > self.config.max_budget_tokens:
            stop_reason = StopReason.MAX_BUDGET_REACHED

        # 如果有工具调用
        used_tools = True
        self._process_tool_calls(response.tool_calls, messages, content=response.content)
        # 继续下一轮循环...

    # 达到最大轮次
    content = response.content if response and response.content else "[达到最大工具调用轮次]"
    return self._finalize_turn(prompt, content, used_tools, total_input, total_output, resolved_config)
```

**关键特性**：
1. **固定轮次限制**：`AGENT_MAX_TOOL_ROUNDS = 10`
2. **Token 预算检查**：每次调用后预算未来成本
3. **幻觉修正**：如果不调用工具且风险高，强制修正
4. **工具串行执行**：所有工具在循环内串行执行（无并发队列）

---

## Why - 为什么重要

### 1. 递归 vs 迭代的权衡

| 维度 | 递归（Kode-Agent） | 迭代（LingClaude） |
|-----|------------------|------------------|
| **自然性** | ⭐⭐⭐⭐⭐ 递归结构符合 ReAct 思维 | ⭐⭐⭐ 显式轮次，更易理解 |
| **并发支持** | ⭐⭐⭐⭐⭐ ToolUseQueue 原生支持 | ⭐⭐ 需要手动实现 |
| **流式输出** | ⭐⭐⭐⭐⭐ AsyncGenerator 流式产出 | ⭐⭐⭐ 需要手动实现 Generator |
| **终止条件** | ⭐⭐⭐⭐ 多种终止条件自然集成 | ⭐⭐⭐ 需要在循环内手动检查 |
| **可读性** | ⭐⭐ 递归深度不易理解 | ⭐⭐⭐⭐ 显式循环更易读 |
| **调试性** | ⭐⭐ 递归调用栈复杂 | ⭐⭐⭐⭐ 循环状态明确 |

### 2. ToolUseQueue 的核心价值

Kode-Agent 的 `ToolUseQueue` 解决了**并发读、串行写**的关键问题：

**问题场景**：
```typescript
// 用户请求：读取3个文件 + 写1个文件
Assistant 调用：
  - ReadFile("src/a.py")
  - ReadFile("src/b.py")
  - ReadFile("src/c.py")
  - WriteFile("src/d.py")
```

**解决方案**：
```typescript
// 并发安全读：3个读操作同时执行
// 串行写：写操作等待所有读完成
ToolQueue 状态：
  queued: [Read(a), Read(b), Read(c), Write(d)]
  executing: [Read(a), Read(b), Read(c)]  // 并发执行
  → Read(a) 完成
  → Read(b) 完成
  → Read(c) 完成
  executing: [Write(d)]  // 串行执行
  → Write(d) 完成
```

**收益**：
- 读操作速度提升 3x
- 写操作安全性保证（无冲突）
- 进度消息实时产出

### 3. Binary Feedback 的创新

Kode-Agent 支持**双响应验证**：

```typescript
async function queryWithBinaryFeedback(...): Promise<BinaryFeedbackResult> {
  if (process.env.USER_TYPE !== 'ant' || !getBinaryFeedbackResponse) {
    // 普通：单个响应
    const assistantMessage = await getAssistantResponse()
    return { message: assistantMessage, shouldSkipPermissionCheck: false }
  }

  // 二元反馈：同时获取2个响应
  const [m1, m2] = await Promise.all([
    getAssistantResponse(),
    getAssistantResponse(),
  ])

  // 自动质量检查
  if (m2.isApiErrorMessage) {
    return { message: m1, shouldSkipPermissionCheck: false }
  }

  // 用户选择（如果启用）
  if (messagePairValidForBinaryFeedback(m1, m2)) {
    return await getBinaryFeedbackResponse(m1, m2)
  }

  // 默认选择第一个
  return { message: m1, shouldSkipPermissionCheck: false }
}
```

**价值**：
- 降低幻觉风险（2个响应交叉验证）
- 用户参与质量保证
- 自动回退机制（API 错误时）

---

## How - 如何应用到 LingClaude

### 改进方案：引入递归代理循环

#### 阶段 1：实现递归查询循环

```python
from typing import AsyncGenerator, Any
from lingclaude.core.types import Result

class RecursiveQueryLoop:
    """递归代理循环（基于 Kode-Agent 模式）"""

    def __init__(self, provider, tool_registry, max_turns=20):
        self.provider = provider
        self.tool_registry = tool_registry
        self.max_turns = max_turns
        self._turn_count = 0

    async def query(
        self,
        messages: list[Any],
        system_prompt: str,
    ) -> AsyncGenerator[Any, None]:
        """递归查询核心函数"""
        # ========== 阶段 1: 准备 ==========

        # 1.1 检查最大轮次
        if self._turn_count >= self.max_turns:
            yield {"type": "error", "message": f"达到最大轮次 {self.max_turns}"}
            return

        # 1.2 提取用户提示（用于 hooks）
        last_user_msg = self._extract_last_user_message(messages)
        if last_user_msg:
            # 可以在这里运行 pre-submit hooks
            pass

        # ========== 阶段 2: 构建系统提示 ==========
        full_system = self._build_system_prompt(system_prompt, messages)

        # ========== 阶段 3: LLM 调用 ==========
        tools = self._build_tools()
        response = await self.provider.complete(
            messages=tuple(messages),
            config={"system_prompt": full_system},
            tools=tuple(tools),
        )

        if response.is_error:
            yield {"type": "error", "message": response.error}
            return

        self._turn_count += 1
        yield {"type": "assistant", "content": response.content}

        # ========== 阶段 4: 工具执行 ==========

        # 4.1 解析工具调用
        tool_calls = response.tool_calls or []
        if not tool_calls:
            # 没有工具调用，运行 stop hooks 并返回
            # yield {"type": "stop", "reason": "no_tools"}
            return

        # 4.2 并发执行工具（如果支持）
        tool_results = []
        for tool_call in tool_calls:
            result = await self._execute_tool(tool_call)
            tool_results.append(result)
            yield {"type": "tool_result", "tool_name": tool_call.name, "output": result}

        # ========== 阶段 5: 递归调用 ==========
        # 构建下一轮消息
        next_messages = [
            *messages,
            {"role": "assistant", "content": response.content, "tool_calls": tool_calls},
        ]
        for tool_result in tool_results:
            next_messages.append({
                "role": "tool",
                "tool_call_id": tool_result["tool_call_id"],
                "content": tool_result["output"],
            })

        # 关键：递归调用
        async for msg in self.query(next_messages, system_prompt):
            yield msg

    def _extract_last_user_message(self, messages: list[Any]) -> Any:
        """提取最后的用户消息"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg
        return None

    def _build_system_prompt(self, base: str, messages: list[Any]) -> str:
        """构建系统提示（可以注入 hooks, reminders）"""
        # 类似 Kode-Agent 的 formatSystemPromptWithContext
        return base

    def _build_tools(self) -> list[Any]:
        """构建工具定义（支持 isConcurrencySafe）"""
        tools = []
        for tool in self.tool_registry.list_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "is_concurrency_safe": getattr(tool, "is_concurrency_safe", False),  # 新增
            })
        return tools

    async def _execute_tool(self, tool_call: Any) -> dict:
        """执行工具（支持并发）"""
        # 这里可以实现 ToolUseQueue
        result = await self.tool_registry.execute_tool(
            tool_call["name"],
            tool_call["arguments"],
        )
        return result
```

#### 阶段 2：实现并发工具队列

```python
import asyncio
from typing import Any, AsyncGenerator
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolQueueEntry:
    tool_name: str
    arguments: dict
    is_concurrency_safe: bool
    status: str = "queued"  # queued, executing, completed
    result: Any = None
    error: str | None = None

class ToolQueue:
    """并发工具队列（基于 Kode-Agent 的 ToolUseQueue）"""

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
        self.queue: list[ToolQueueEntry] = []
        self._running_tasks: dict[str, asyncio.Task] = {}

    def add_tool(self, tool_name: str, arguments: dict, is_concurrency_safe: bool) -> None:
        """添加工具到队列"""
        entry = ToolQueueEntry(
            tool_name=tool_name,
            arguments=arguments,
            is_concurrency_safe=is_concurrency_safe,
        )
        self.queue.append(entry)
        # 立即开始处理
        asyncio.create_task(self._process_queue())

    def can_execute(self, entry: ToolQueueEntry) -> bool:
        """检查是否可以执行（考虑并发安全性）"""
        executing = [e for e in self.queue if e.status == "executing"]

        if not executing:
            return True

        if entry.is_concurrency_safe:
            # 并发安全工具：所有正在执行的工具也必须并发安全
            return all(e.is_concurrency_safe for e in executing)

        return False

    async def _process_queue(self) -> None:
        """处理队列（并发执行安全工具）"""
        for entry in self.queue:
            if entry.status != "queued":
                continue

            if not self.can_execute(entry):
                # 不能执行，生成"等待..."消息
                yield {"type": "progress", "tool_name": entry.tool_name, "status": "waiting"}
                continue

            if not entry.is_concurrency_safe:
                # 非并发安全工具，阻塞后续工具
                break

            # 开始执行
            entry.status = "executing"
            task = asyncio.create_task(self._execute_tool(entry))
            self._running_tasks[entry.tool_name] = task

            # 完成时更新状态
            task.add_done_callback(lambda t: self._on_tool_complete(entry, t))

    async def _execute_tool(self, entry: ToolQueueEntry) -> None:
        """执行单个工具"""
        try:
            result = await self.tool_registry.execute_tool(
                entry.tool_name,
                entry.arguments,
            )
            # 更新 entry（不可变，需要重建）
            idx = self.queue.index(entry)
            self.queue[idx] = ToolQueueEntry(
                tool_name=entry.tool_name,
                arguments=entry.arguments,
                is_concurrency_safe=entry.is_concurrency_safe,
                status="completed",
                result=result,
            )
        except Exception as e:
            idx = self.queue.index(entry)
            self.queue[idx] = ToolQueueEntry(
                tool_name=entry.tool_name,
                arguments=entry.arguments,
                is_concurrency_safe=entry.is_concurrency_safe,
                status="completed",
                error=str(e),
            )

    def _on_tool_complete(self, entry: ToolQueueEntry, task: asyncio.Task) -> None:
        """工具完成回调"""
        tool_name = entry.tool_name
        if tool_name in self._running_tasks:
            del self._running_tasks[tool_name]

        # 继续处理队列
        asyncio.create_task(self._process_queue())

    async def get_remaining_results(self) -> AsyncGenerator[Any, None]:
        """获取剩余结果（支持流式产出）"""
        pending_count = sum(1 for e in self.queue if e.status in ("queued", "executing"))

        while pending_count > 0:
            # 产出已完成的结果
            for entry in self.queue:
                if entry.status == "completed" and entry.result is not None:
                    yield {
                        "type": "tool_result",
                        "tool_name": entry.tool_name,
                        "output": entry.result,
                    }
                elif entry.status == "completed" and entry.error:
                    yield {
                        "type": "tool_error",
                        "tool_name": entry.tool_name,
                        "error": entry.error,
                    }

            # 等待任意任务完成
            if self._running_tasks:
                await asyncio.gather(*self._running_tasks.values())

            # 重新计算待处理数量
            pending_count = sum(1 for e in self.queue if e.status in ("queued", "executing"))
```

#### 阶段 3：集成到 QueryEngine

```python
class QueryEngine:
    def __init__(self, ...):
        # ...
        self._recursive_loop = RecursiveQueryLoop(
            provider=self._provider,
            tool_registry=self._runtime,
            max_turns=self.config.max_turns,
        )

    async def stream_submit(
        self,
        prompt: str,
        matched_commands: tuple[str, ...] = (),
        matched_tools: tuple[str, ...] = (),
        denied_tools: tuple[PermissionDenial, ...] = (),
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式提交（使用递归循环）"""
        yield {"type": "message_start", "session_id": self.session_id, "prompt": prompt}

        messages = [{"role": "user", "content": prompt}]

        # 使用递归循环
        async for msg in self._recursive_loop.query(messages, self._build_system_prompt()):
            yield msg

        yield {
            "type": "message_stop",
            "usage": self._usage.to_dict(),
            "transcript_size": len(self._transcript),
        }
```

#### 阶段 4：为工具添加 is_concurrency_safe 属性

```python
# lingclaude/engine/tools.py

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    is_concurrency_safe: bool = False  # 新增：默认为 False

# 读操作工具示例
read_tool = ToolDefinition(
    name="read",
    description="Read file contents",
    parameters={"file_path": {"type": "string"}},
    is_concurrency_safe=True,  # 读操作可以并发
)

# 写操作工具示例
write_tool = ToolDefinition(
    name="write",
    description="Write content to file",
    parameters={"file_path": {"type": "string"}, "content": {"type": "string"}},
    is_concurrency_safe=False,  # 写操作必须串行
)
```

---

## Summary - 总结

| 对比维度 | Kode-Agent (递归) | LingClaude (迭代) | 改进建议 |
|---------|-------------------|------------------|----------|
| **循环类型** | 递归（AsyncGenerator） | 迭代（for range） | 引入递归模式 |
| **并发支持** | ToolUseQueue（并发读+串行写） | 串行执行 | 实现 ToolQueue |
| **终止条件** | 多种（abort, empty, no_tools, hooks） | 单一（max_rounds） | 增加终止条件 |
| **流式输出** | 原生 AsyncGenerator | 需手动 Generator | 使用 AsyncGenerator |
| **工具安全** | isConcurrencySafe 属性 | 无 | 添加属性 |
| **Hook 集成** | 3 种 hook（pre-submit, post-tool, stop） | 无 | 实现系统 Hooks |

**关键改进点**：
1. **递归代理循环**：更自然的 ReAct 思维模式
2. **并发工具队列**：提升读操作性能，保证写操作安全
3. **AsyncGenerator 流式输出**：实时进度反馈
4. **isConcurrencySafe 工具属性**：精细化并发控制
5. **多种终止条件**：更灵活的循环控制

---

## Next Steps - 下一步

- [ ] Task 4: 渐进式 Agent Loop (LingFlow_plus)

---

**学习笔记完成日期**: 2026-04-14
**作者**: 灵通 (LingFlow)
