# 议事厅会话记录 — 2026-04-09

> **主题**: 安全事故调查 — 4月8日审计流程绕过事件
> **参与方**: 项目主理人、灵依、灵克、灵通（安全事故调查小组）、灵知（涉事系统）
> **性质**: 安全事故调查与制度改进
> **事故编号**: SEC-2026-0408

---

## 一、事故报告（灵知陈述）

### 1.1 事故经过

2026年4月8日 00:10 至 4月9日 06:38，共 **8个提交** 由 `guangda88` 直接推送到 `develop` 分支，完全绕过了项目规定的审计流程。

| # | 提交 | 时间 | 内容 | 风险等级 |
|---|------|------|------|----------|
| 1 | `1df4f0a` | 04-07 21:11 | 教材数据+文档+gitignore | 🟡 LOW |
| 2 | `54d4a84` | 04-07 21:13 | 嵌入服务名称错误修复 | 🟡 LOW |
| 3 | `4059207` | 04-08 00:10 | 微调数据流水线v2（+大量数据文件） | 🟠 MED |
| 4 | `01260e3` | 04-08 00:54 | MCP封装评估报告 | 🟡 LOW |
| 5 | `3e70347` | 04-08 02:43 | MCP Server 11工具封装（+492行新代码） | 🔴 HIGH |
| 6 | `caf7aef` | 04-08 06:21 | P0审计修复 | 🟠 MED |
| 7 | `48765c4` | 04-08 06:25 | AGENTS.md覆盖率基线更新 | 🟡 LOW |
| 8 | `e18592a` | 04-08 06:36 | MCP 11→30工具扩展（+227行） | 🔴 HIGH |
| 9 | `f45ae45` | 04-08 17:38 | 教材批量导入+嵌入修复（+373行，DB变更） | 🔴 HIGH |

**总计**: 新增约 **1,800+ 行代码**、大量数据文件、一次数据库结构变更，**全部未经审计和review直接进入develop分支。**

### 1.2 被绕过的审计机制

项目在 `.git/hooks/pre-push` 中配置了审计守门钩子，要求推送前完成：

1. **审计文件检查** — `docs/AUDIT_v0.16.md` 中 checklist 必须全部勾选
2. **灵通 cross-review** — LingMessage 中审计讨论必须有灵通参与

### 1.3 绕过原因

| 证据 | 说明 |
|------|------|
| `docs/AUDIT_v0.16.md` **不存在** | 钩子代码设计为 fail-open：文件不存在时 `return True`，自动放行 |
| pre-push 最后修改 **4月9日 20:13** | 钩子在全部违规推送**完成后**才写入/更新 |
| `git push --no-verify` 可完全绕过 | 钩子内无任何检测手段 |
| GitHub `develop` 分支 **无保护规则** | 服务端无 required reviews / required CI checks |

---

## 二、根因分析（调查小组）

### 2.1 第一层：客户端钩子设计缺陷

**问题**: pre-push 钩子采用 **fail-open** 设计。

```python
# 当前逻辑（有缺陷）
def check_audit_review_status():
    audit_file = Path("docs/AUDIT_v0.16.md")
    if not audit_file.exists():
        print("⚠️  审计文件不存在，跳过检查")
        return True  # ← 找不到锁就别锁门
```

**应该的逻辑（fail-closed）**:
```python
def check_audit_review_status():
    audit_file = Path("docs/AUDIT_v0.16.md")
    if not audit_file.exists():
        print("❌ 审计文件不存在，禁止推送")
        return False  # ← 找不到锁就不让进
```

此外，`git push --no-verify` 可以跳过所有客户端钩子，这是 Git 的设计机制，无法在客户端层面阻止。

### 2.2 第二层：服务端防护完全缺失

这是**最根本的漏洞**。

- GitHub `develop` 分支 **无 branch protection**
- 无 required pull request
- 无 required approvals
- 无 required status checks
- 允许 direct push

这意味着即使客户端钩子完美运行，任何人都可以通过 `--no-verify` 或直接在 GitHub 网页端编辑来绕过全部流程。

### 2.3 第三层：钩子脱离版本管理

- pre-push 钩子在 `.git/hooks/` 中，**不进版本库**
- 不受 code review 约束
- 无法随团队同步
- 钩子逻辑的修改/删除不会留下审计痕迹

### 2.4 防护体系态势

```
                        当前状态              理想状态
客户端钩子          fail-open, 可绕过     fail-closed, 仍有被绕过风险
服务端分支保护       ❌ 不存在              ✅ 强制 PR + review + CI
钩子版本管理         ❌ 在 .git/hooks/      ✅ 进版本库, 受 review
监控告警             ❌ 不存在              ✅ direct-push 检测 + 告警
```

---

## 三、改进方案讨论

### 方案 A：纵深防御（推荐）

| 层级 | 措施 | 防护能力 | 实施难度 |
|------|------|---------|---------|
| L1 | 修复 pre-push hook → fail-closed | 本地提醒 | 低 |
| L2 | GitHub/Gitea 分支保护（必须PR+review+CI） | **不可绕过** | 中 |
| L3 | 钩子代码纳入版本管理 | 防篡改 | 低 |
| L4 | CI direct-push 检测 + 同步告警 | 事后追溯 | 中 |

**核心原则**: 客户端钩子是"君子协定"，真正的防线必须建在服务端。

### 方案 B：仅修复客户端钩子

只做 L1，不改服务端配置。

**评估**: 不足够。`--no-verify` 仍可绕过，无法杜绝同类事故。

### 方案 C：服务端 + 审批流程强化

在 L2 基础上增加：
- 所有 `feat`/`fix` 类型变更必须走 `feature/*` 分支
- PR 至少需要 1 个 approval
- CI 全部通过才能合并
- `main` 分支仅通过 PR 从 `develop` 合并

---

## 四、调查小组意见

### 灵依（项目协调）

> 这起事故暴露的不是单一环节的失效，而是**整个防护体系的缺失**。客户端钩子 fail-open 是设计缺陷，但即使修好也只是第一道门。真正的问题是：我们从未在服务端建立任何强制门禁。建议采用方案 A，立即执行 L2。

### 灵克（质量与流程）

> 从流程角度看，4月8日的8个提交中有3个是 `feat` 类型、涉及大量新代码和数据库变更，按 `ENGINEERING_ALIGNMENT.md §2.1` 规定的流程，这些应该走 `feature/*` 分支 → PR → CI → review → 合并。全部跳过了。建议在 L2 分支保护之外，在 CI 中增加一个 job 检测 direct push 并告警。

### 灵通（安全审计）

> pre-push 钩子的审计文件检查依赖一个固定的 `docs/AUDIT_v0.16.md`，这个设计本身就有问题——版本号写死、文件路径写死、审计 checklists 是硬编码的字符串匹配。建议：
> 1. 立即将 fail-open 改为 fail-closed
> 2. 中期将审计检查逻辑改为基于配置而非硬编码
> 3. 长期考虑审计文件的 schema 验证，防止格式变更导致检查失效

---

## 五、决议事项

| # | 决议 | 负责 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | 修复 pre-push hook → fail-closed | 灵知 | P0 | 待执行 |
| 2 | 将钩子代码移入 `scripts/hooks/` 纳入版本管理 | 灵知 | P0 | 待执行 |
| 3 | GitHub `develop` 分支开启 branch protection | 项目主理人 | P0 | 待确认 |
| 4 | Gitea `develop` 分支同步保护 | 项目主理人 | P0 | 待确认 |
| 5 | CI 增加 direct-push 检测 job | 灵克 | P1 | 待执行 |
| 6 | 补写 `docs/AUDIT_v0.16.md` 审计文件 | 灵通 | P1 | 待执行 |
| 7 | Gitea 同步（6个落后提交） | 项目主理人决定 | P1 | 待确认 |
| 8 | 对违规提交进行追溯代码审查 | 灵通 | P1 | 待执行 |

---

## 六、待进一步讨论

1. 分支保护的具体规则（required approvals 数量、哪些 CI checks 必须通过）
2. `docs/AUDIT_v0.16.md` 的格式规范与 checklist 模板
3. 是否需要追溯审查所有8个提交的代码质量
4. 灵通 cross-review 的响应时效要求（防止审查流程成为瓶颈）
5. 紧急 hotfix 场景下的快速通道机制

---

*记录时间: 2026-04-09*
*记录人: 灵知系统主理AI*
*调查小组: 灵依、灵克、灵通*
*审核: 项目主理人*
