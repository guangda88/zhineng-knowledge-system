# Task 1: Permission Funnel 权限漏斗

**学习日期**: 2026-04-14
**来源**: Kode-Agent/src/core/permissions/engine/index.ts (~800行)
**任务**: 学习 Kode-Agent 的分层权限检查机制

---

## What - 学到了什么

### Kode-Agent 权限漏斗的核心架构

Kode-Agent 实现了一个**三层权限漏斗**：

```
用户请求 → 权限模式检查 → 工具分类处理 → 路径/命令验证 → 返回 PermissionResult
```

#### 1. 权限模式 (PermissionMode)

```typescript
enum PermissionMode {
  'bypassPermissions'  // 绕过权限，但有安全底线
  'acceptEdits'        // 自动接受编辑操作
  'normal'             // 正常模式（默认 ask）
  'dontAsk'            // 不询问，自动拒绝未授权操作
}
```

**关键设计**：
- `bypassPermissions` 不是完全绕过，仍有**安全底线检查** (`safety floor`)
- 安全底线检查危险路径（如系统目录、配置文件）
- 可通过环境变量 `KODE_BYPASS_SAFETY_FLOOR=1` 禁用（不推荐）

#### 2. 工具分类 (Tool Classification)

Kode-Agent 将工具分为4类，每类有不同的检查逻辑：

| 工具类型 | 检查重点 | 安全级别 |
|---------|---------|---------|
| **BashTool** | 命令安全性、沙箱限制 | 高 |
| **文件工具** (FileRead/Edit/Write, Glob, Grep) | 路径规则、工作目录 | 中 |
| **网络工具** (WebFetch, WebSearch) | 域名白名单、URL 模式 | 中 |
| **交互工具** (SlashCommand, Skill, MCP) | 前缀匹配、通配符 | 低 |

#### 3. 规则匹配优先级

```typescript
denied > asked > allowed
```

具体匹配逻辑（以 FileEdit 为例）：

```typescript
// 1. 先检查 deny 规则
const deniedRule = matchPermissionRuleForPath({
  inputPath: candidate,
  toolPermissionContext: effectiveToolPermissionContext,
  operation: 'edit',
  behavior: 'deny',
})
if (deniedRule) return { result: false, message: 'Permission denied', shouldPromptUser: false }

// 2. 检查安全底线
const safety = getWriteSafetyCheckForPath(toolPath)
if ('message' in safety) return { result: false, message: safety.message }

// 3. 检查 ask 规则
const askedRule = matchPermissionRuleForPath({ ... behavior: 'ask' })
if (askedRule) return { result: false, message: 'Permission not granted yet' }

// 4. 检查 allow 规则
const allowRule = matchPermissionRuleForPath({ ... behavior: 'allow' })
if (allowRule) return { result: true }

// 5. 默认拒绝
return { result: false, suggestions: [...] }
```

#### 4. 路径安全检查

Kode-Agent 实现了**多维度路径安全检查**：

- **危险路径检测**：`getWriteSafetyCheckForPath()`
  - 系统关键路径：`/bin/`, `/usr/`, `/etc/`, `/boot/`, `/lib/`
  - 配置文件：`.ssh/`, `.aws/`, `.env`, `config.*`
  - Windows 系统路径：`C:\Windows\`, `C:\Program Files\`

- **工作目录检查**：`isPathInWorkingDirectories()`
  - 只有工作目录内的路径才能自动允许（在 acceptEdits 模式）

- **符号链接扩展**：`expandSymlinkPaths()`
  - 检查符号链接的所有可能目标路径
  - 防止通过符号链接绕过权限检查

#### 5. Bash 命令沙箱

Kode-Agent 实现了 `BunShellSandboxPlan`：

```typescript
function getBunShellSandboxPlan({
  command,
  dangerouslyDisableSandbox,
  toolUseContext
}): SandboxPlan {
  // 检查命令是否必须在沙箱中运行
  if (shouldBlockUnsandboxedCommand) {
    return { shouldBlockUnsandboxedCommand: true }
  }

  // 检查是否可以自动允许（沙箱保证安全）
  if (shouldAutoAllowBashPermissions) {
    return { shouldAutoAllowBashPermissions: true }
  }

  // 需要用户确认
  return { needsPermission: true }
}
```

**沙箱隔离**：
- 限制可访问的文件系统路径
- 限制网络访问
- 限制系统调用

### lingclaude 当前的权限系统

```python
@dataclass(frozen=True)
class PermissionContext:
    deny_names: frozenset[str]
    deny_prefixes: tuple[str, ...]

    def blocks(self, tool_name: str) -> bool:
        lowered = tool_name.lower()
        return lowered in self.deny_names or any(
            lowered.startswith(prefix) for prefix in self.deny_prefixes
        )
```

**功能**：
- 仅支持**精确匹配**和**前缀匹配**
- 没有路径规则、没有安全底线、没有多种模式
- 功能非常基础

---

## Why - 为什么重要

### 1. 外包项目的安全需求

**Kode-Agent 面向用户桌面应用**，需要：
- 防止 AI 误操作（删除系统文件、修改配置）
- 用户可控的权限分级（safe/needs-confirmation/blocked）
- 默认安全的策略（未授权操作默认拒绝）

### 2. lingclaude 的改进空间

当前 lingclaude 仅支持：
- **工具级拒绝**：完全禁止某些工具
- **前缀拒绝**：禁止某类工具（如 `bash:*`）

**缺少**：
- **操作分级**：读操作默认允许，写操作需要确认
- **路径规则**：允许访问 `project/**`，拒绝 `~/.ssh/**`
- **上下文感知**：不同项目有不同的权限策略
- **安全底线**：即使用户选择"全部允许"，仍阻止危险操作

---

## How - 如何应用到 lingclaude

### 改进方案：三层权限系统

#### 阶段 1：扩展 PermissionContext

```python
@dataclass(frozen=True)
class PermissionContext:
    # 工具级控制（现有）
    deny_names: frozenset[str] = field(default_factory=frozenset)
    deny_prefixes: tuple[str, ...] = ()

    # 新增：路径规则
    read_allowed: frozenset[str] = field(default_factory=frozenset)  # 允许读的路径
    read_denied: frozenset[str] = field(default_factory=frozenset)   # 拒绝读的路径
    write_allowed: frozenset[str] = field(default_factory=frozenset)  # 允许写的路径
    write_denied: frozenset[str] = field(default_factory=frozenset)  # 拒绝写的路径

    # 新增：权限模式
    mode: PermissionMode = PermissionMode.ASK  # BYPASS, ACCEPT_EDITS, ASK, DONT_ASK

    # 新增：安全底线
    safety_floor: bool = True  # 即使在 BYPASS 模式，也检查危险路径
```

#### 阶段 2：路径检查器

```python
def check_path_permission(
    path: str,
    operation: str,  # 'read' or 'write'
    context: PermissionContext,
    working_dirs: tuple[str, ...] = ()
) -> PermissionResult:
    """
    检查路径权限，返回 PermissionResult
    """
    # 1. 检查安全底线
    if context.safety_floor:
        if is_dangerous_path(path, operation):
            return PermissionResult(
                allowed=False,
                reason=f"安全底线：拒绝访问危险路径 {path}",
                severity="critical"
            )

    # 2. 检查拒绝规则（最高优先级）
    denied_rules = context.write_denied if operation == 'write' else context.read_denied
    for pattern in denied_rules:
        if match_path_pattern(path, pattern):
            return PermissionResult(
                allowed=False,
                reason=f"规则匹配：{pattern} 拒绝 {operation} {path}",
                severity="medium"
            )

    # 3. 检查允许规则
    allowed_rules = context.write_allowed if operation == 'write' else context.read_allowed
    for pattern in allowed_rules:
        if match_path_pattern(path, pattern):
            return PermissionResult(allowed=True, reason=f"规则匹配：{pattern} 允许 {operation}")

    # 4. 默认策略
    if context.mode == PermissionMode.ACCEPT_EDITS and operation == 'read':
        if is_in_working_dirs(path, working_dirs):
            return PermissionResult(allowed=True, reason="工作目录内默认允许")

    return PermissionResult(
        allowed=False,
        reason=f"未授权：{operation} {path}",
        severity="low",
        suggestions=[
            f"添加到 read_allowed: {path}",
            f"切换到 ACCEPT_EDITS 模式"
        ]
    )
```

#### 阶段 3：操作分级集成

在 `lingclaude/engine/` 中的工具实现中添加：

```python
# file_read.py
def execute_file_read(self, file_path: str, context: PermissionContext) -> dict:
    result = check_path_permission(file_path, 'read', context, self.working_dirs)
    if not result.allowed:
        if context.mode == PermissionMode.DONT_ASK:
            return {"error": result.reason}
        raise PermissionDenied(result.reason, suggestions=result.suggestions)

    # 继续执行读取操作
    ...
```

#### 阶段 4：配置示例

```yaml
# config.yaml
permissions:
  mode: "accept_edits"  # 默认模式
  safety_floor: true    # 启用安全底线

  # 路径规则（glob 模式）
  read_allowed:
    - "**/*.py"
    - "docs/**"
    - "/home/ai/project/**"

  write_denied:
    - "~/.ssh/**"
    - "/etc/**"
    - "/bin/**"
    - "**/.env"
    - "**/config.*"

  write_allowed:
    - "/home/ai/project/**"
    - "/tmp/**"

  # 工具级控制（向后兼容）
  deny_names:
    - "bash:sudo"
    - "bash:rm -rf /"

  deny_prefixes:
    - "bash:systemctl"
```

---

## Code - 代码示例

### 完整的 PermissionResult 类型

```python
@dataclass(frozen=True)
class PermissionResult:
    allowed: bool
    reason: str
    severity: str = "medium"  # critical, high, medium, low
    suggestions: tuple[str, ...] = ()
    should_prompt_user: bool = True

    @property
    def is_denied_forever(self) -> bool:
        """是否永久拒绝（如安全底线、模式设置）"""
        return self.severity in {"critical", "high"} or not self.should_prompt_user

    @property
    def can_suggest(self) -> bool:
        """是否可以提供配置建议"""
        return self.severity != "critical"
```

### 路径模式匹配器

```python
import fnmatch
import os
from pathlib import Path

def match_path_pattern(path: str, pattern: str) -> bool:
    """
    检查路径是否匹配 glob 模式

    Examples:
        match_path_pattern("/home/ai/project/src/main.py", "/home/ai/project/**/*.py")
            => True
        match_path_pattern("/home/ai/.ssh/id_rsa", "~/.ssh/**")
            => True
        match_path_pattern("/etc/passwd", "/etc/**")
            => False  # 如果 write_denied 包含 "/etc/**"
    """
    # 展开波浪号
    pattern = os.path.expanduser(pattern)
    path = os.path.abspath(path)

    # 如果模式以斜杠结尾，匹配所有子路径
    if pattern.endswith('/'):
        pattern += '**'

    return fnmatch.fnmatch(path, pattern)

def is_dangerous_path(path: str, operation: str) -> bool:
    """
    检查是否为危险路径（安全底线）

    写操作的危险路径：
    - /bin/, /usr/, /etc/, /lib/, /boot/, /sbin/
    - ~/.ssh/, ~/.aws/, ~/.kube/, ~/.config/
    - *.env, config.*, *.pem, *.key
    """
    path_lower = path.lower()

    if operation == 'write':
        system_paths = [
            '/bin/', '/usr/', '/etc/', '/lib/', '/boot/', '/sbin/',
            '/sys/', '/proc/', '/dev/'
        ]
        config_paths = ['.ssh/', '.aws/', '.kube/', '.config/', '.gnupg/']
        dangerous_files = ['.env', '.pem', '.key', '.p12']

        for sys_path in system_paths:
            if path.startswith(sys_path):
                return True

        for config_path in config_paths:
            if f'/{config_path}' in path or path.startswith(f'~/{config_path}'):
                return True

        for dangerous_file in dangerous_files:
            if path.endswith(dangerous_file):
                return True

    return False

def is_in_working_dirs(path: str, working_dirs: tuple[str, ...]) -> bool:
    """检查路径是否在工作目录内"""
    abs_path = os.path.abspath(path)
    for work_dir in working_dirs:
        abs_work_dir = os.path.abspath(work_dir)
        try:
            Path(abs_path).relative_to(abs_work_dir)
            return True
        except ValueError:
            continue
    return False
```

---

## Summary - 总结

| 对比维度 | Kode-Agent | lingclaude (当前) | lingclaude (改进后) |
|---------|-----------|------------------|-------------------|
| **权限模式** | 4种 (bypass, acceptEdits, ask, dontAsk) | 无 | 4种 |
| **路径规则** | 支持 (glob模式, 3种操作类型) | 不支持 | 支持 |
| **安全底线** | 有 (危险路径检查) | 无 | 有 |
| **工具分类** | 4类 (Bash, 文件, 网络, 交互) | 工具级 (全部相同) | 4类 |
| **规则优先级** | denied > asked > allowed | 无 | denied > asked > allowed |
| **建议系统** | 有 (suggestFilePermissionUpdates) | 无 | 有 |
| **上下文感知** | 有 (conversation-level) | 无 | 有 |

**关键改进点**：
1. **从工具级拒绝到路径级控制**
2. **从单一模式到分级策略**
3. **从完全绕过到安全底线**
4. **从默认允许到默认拒绝**

---

## Next Steps - 下一步

- [ ] Task 2: Memory Dream Consolidation 记忆巩固
- [ ] Task 3: Recursive Agent Loop 递归代理循环

---

**学习笔记完成日期**: 2026-04-14
**作者**: 灵通 (lingflow)
