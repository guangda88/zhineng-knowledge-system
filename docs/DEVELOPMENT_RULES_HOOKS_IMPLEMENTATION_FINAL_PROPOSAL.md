# 开发规则修改与Hooks实施 - 最终方案

**文档版本**: 1.0.0
**创建日期**: 2026-03-29
**作者**: AI架构师
**项目**: 灵知（LingZhi）系统
**状态**: 待确认

---

## 目录

1. [执行总结](#1-执行总结)
2. [问题回顾](#2-问题回顾)
3. [最小化修改方案](#3-最小化修改方案)
4. [Hooks讨论成果](#4-hooks讨论成果)
5. [最终方案：文档简化 + Hooks强化](#5-最终方案文档简化--hooks强化)
6. [实施计划](#6-实施计划)
7. [文件清单](#7-文件清单)

---

## 1. 执行总结

### 1.1 背景

**从第一手资料代码分析报告和评估报告的反思**：
- 从这次评估和讨论中，我们得到了很多宝贵的教训和启示
- 我们需要将这些教训和启示转化为具体的开发规则
- 我们需要确保规则和规划不流于形式，深入到每一个AI的行动当中

### 1.2 核心洞察

**规则落地的关键**：

```
文档 (CLAUDE.md) → AI可能"遗忘"或"选择性执行"
        ↓
  Hooks (自动触发) → 强制执行 ⭐ 关键层
        ↓
  Permissions (权限) → 最后防线
```

**当前系统缺少Hooks层，这就是规则容易流于形式的根本原因。**

### 1.3 最终方案

**推荐方案**：**文档简化 + Hooks强化**

**理由**：
1. **规则文档简化**：新增1个小节 + 修改2个小节，避免规则膨胀
2. **Hooks强化**：P0级Hook立即实施，P1级Hook2周内实施，核心检查机制逐步实施
3. **真正落地**：Hooks自动强制执行，避免规则流于形式
4. **AI约束**：AI无法绕过Hooks检查，确保规则执行

---

## 2. 问题回顾

### 2.1 发现的问题

**第一手资料代码分析报告的问题**：
1. 分析范围不完整（仅分析了backend目录的138个文件）
2. 部分数据不准确（如测试覆盖率、测试用例数等）
3. 基于无法运行的数据做出决策（如8%测试覆盖率）

**评估报告的发现**：
1. Pydantic依赖问题导致系统无法运行
2. 14处未定义变量导致代码错误
3. zhineng-api容器处于unhealthy状态
4. 测试文件数不准确（报告说16个，实际27个）
5. 测试用例数不准确（报告说30个，实际27个）
6. 测试覆盖率无法验证（Pydantic问题导致测试无法运行）
7. 项目规模被低估（报告分析了138个，实际324个）

### 2.2 根本原因分析

**根本原因**：
1. 没有严格遵守"先讨论后动手"的治理原则
2. 分析范围不完整，遗漏了重要的数据
3. 没有充分验证数据的准确性
4. 基于无法验证的数据做出决策
5. 没有优先考虑紧急问题
6. **当前系统缺少Hooks层，这就是规则容易流于形式的根本原因**

### 2.3 得到的教训和启示

**主要教训**：
1. 严格遵守治理原则
2. 完整的数据分析
3. 准确的数据报告
4. 基于真实数据的决策
5. 紧急问题优先
6. 验证和再验证
7. 讨论和共识
8. 承认错误和改进

**主要启示**：
1. 治理原则的重要性
2. 数据的重要性
3. 讨论的重要性
4. 紧急问题的重要性
5. **Hooks强制执行的重要性** ⭐

---

## 3. 最小化修改方案

### 3.1 修改内容

**修改内容**：
1. **新增**：在第4章"Git工作流规范"中增加"4.4 规则修改流程"（带Hook引用）
2. **修改**：在第13章"禁止事项"中增加"禁止忽视紧急问题"（带Hook引用）
3. **修改**：在第12章"代码审查规范"中增加"12.1 数据验证"（带Hook引用）

**总计**：新增1个小节，修改2个小节

### 3.2 具体修改内容

#### 3.2.1 新增：第4章"Git工作流规范"中增加"4.4 规则修改流程" (带Hook引用)

```markdown
### 4.4 规则修改流程

**原则**：
- [ ] 修改规则和规划之前，必须进行充分的讨论
- [ ] 修改规则和规划必须基于真实数据
- [ ] 修改规则和规划必须得到共识

**流程（人工层）**：
1. 数据收集阶段
   - [ ] 收集完整的数据
   - [ ] 验证数据的准确性
   - [ ] 确保数据是基于真实的测量

2. 讨论阶段
   - [ ] 组织充分的讨论
   - [ ] 收集各方的意见
   - [ ] 识别讨论的共识和分歧
   - [ ] 解决讨论的分歧

3. 决策和执行阶段
   - [ ] 基于充分讨论做出决策
   - [ ] 确保决策是基于真实数据的
   - [ ] 获得各方对决策的认可
   - [ ] 按照决策执行修改
   - [ ] 验证修改的效果

**强制执行（技术层 - 详见 `HOOKS_IMPLEMENTATION_GUIDE.md`）**：

**触发条件**：
当 AI 或开发者尝试修改 `DEVELOPMENT_RULES.md` 或 `PHASED_IMPLEMENTATION_PLAN.md` 时触发。

**执行机制**：
`AIActionWrapper` 将拦截 `modify_rules` 类型的操作，并执行以下检查：

| 检查项 | 检查逻辑 | 违规后果 |
|--------|---------|---------|
| **是否已讨论** | `action_data['discussed'] == true` | ❌ 拒绝执行，返回错误："规则修改前必须经过讨论（引用 4.4.1）" |
| **基于真实数据** | `action_data['data_source'] != 'assumption'` | ❌ 拒绝执行，返回错误："必须基于真实测量数据修改规则（引用 4.4.2）" |
| **是否达成共识** | `action_data['consensus'] == true` | ❌ 拒绝执行，返回错误："规则修改必须获得团队共识（引用 4.4.3）" |

**代码示例**：
```python
# backend/core/ai_action_wrapper.py (根据 HOOKS_IMPLEMENTATION_GUIDE.md)

def _check_modify_rules(self, action_data: Dict[str, Any]) -> bool:
    # 检查 4.4.1: 是否已讨论
    if not action_data.get("discussed"):
        raise PermissionError("违反规则 4.4.1: 规则修改前必须经过讨论")

    # 检查 4.4.2: 基于真实数据
    if action_data.get("data_source") == "assumption":
        raise PermissionError("违反规则 4.4.2: 必须基于真实测量数据修改规则")

    # 检查 4.4.3: 是否达成共识
    if not action_data.get("consensus"):
        raise PermissionError("违反规则 4.4.3: 规则修改必须获得团队共识")

    return True
```

**注意**：
- 这是通过 `RulesChecker` Hook 自动强制执行的
- AI 无法绕过这个检查
- 详见 `HOOKS_IMPLEMENTATION_GUIDE.md` 中的 "规则修改流程" 章节
```

#### 3.2.2 修改：第13章"禁止事项"中增加"禁止忽视紧急问题" (带Hook引用)

```markdown
### 13.1 严格禁止

1. ❌ 硬编码密码/密钥
2. ❌ SQL 注入风险代码
3. ❌ 提交敏感数据
4. ❌ 跳过测试直接合并
5. ❌ 在 main 分支直接开发
6. ❌ **忽视紧急问题**（技术强制执行）

### 13.3 紧急问题说明（带强制执行逻辑）

**紧急问题判定（技术标准）**：
```yaml
# 定义紧急问题状态
urgency_checks:
  - name: "system_health"
    check: "GET /health"
    condition: "status != 200"
  - name: "api_container"
    check: "docker ps --filter name=zhineng-api"
    condition: "status contains 'unhealthy'"
  - name: "import_errors"
    check: "python -m flake8 backend --select=F821"
    condition: "result.count > 0"
```

**强制执行机制（`UrgencyGuard` Hook）**：

当系统处于"紧急状态"时，`UrgencyGuard` Hook 将拦截所有非紧急操作。

**执行逻辑**：
1. **检查系统状态**：每次行动前，运行 `urgency_checks`。
2. **判定状态**：如果任一检查失败，系统进入"紧急模式"。
3. **拦截操作**：
   - ✅ **允许**：`fix_urgent_issue`、`debug_system`、`restart_service`。
   - ❌ **拒绝**：`add_tests`、`refactor_code`、`modify_documentation`、`improve_coverage`。

**代码示例**：
```python
# backend/core/urgency_guard.py (根据 HOOKS_IMPLEMENTATION_GUIDE.md)

class UrgencyGuard:
    async def check_and_intercept(self, action_type: str, action_data: Dict):
        if self.is_emergency_mode():
            if action_type not in self.ALLOWED_URGENT_ACTIONS:
                raise PermissionError(
                    f"违反规则 13.1: 系统处于紧急状态（{self.current_emergencies}）。"
                    f"只允许修复紧急问题，禁止执行 '{action_type}'。"
                )
```

**注意**：
- 这是通过 `UrgencyGuard` Hook 自动强制执行的
- AI 无法绕过这个检查
- 详见 `HOOKS_IMPLEMENTATION_GUIDE.md` 中的 "紧急问题拦截" 章节
```

#### 3.2.3 修改：第12章"代码审查规范"中增加"12.1 数据验证" (带Hook引用)

```markdown
### 12.1 数据验证（带强制执行）

**数据验证要求**：
- [ ] 确保数据是真实的（基于静态分析或运行测试）
- [ ] 确保数据是准确的（经过二次验证）
- [ ] 确保数据是完整的（覆盖所有范围）

**强制执行机制（`DataVerificationGate` Hook）**：

在生成报告或进行决策前，必须通过 `DataVerificationGate`。

**执行逻辑**：
1. **元数据检查**：所有报告必须包含 `data_source: "static_analysis"` 或 `data_source: "runtime_test"`。
2. **有效性检查**：如果是 `runtime_test`，系统会自动验证该测试是否真实运行过（通过检查 CI/CD 日志或测试运行历史）。
3. **拦截虚假数据**：如果 `data_source: "assumption"` 或 `based_on: "guess"`，直接拦截并标记为"违规规则 12.1"。

**代码示例**：
```python
# backend/core/data_verification_gate.py (根据 HOOKS_IMPLEMENTATION_GUIDE.md)

def verify_report_data(self, report: Dict) -> bool:
    source = report.get("metadata", {}).get("data_source")
    if not source:
        raise ValueError("违反规则 12.1: 报告必须声明数据来源")

    if source == "assumption":
        raise ValueError("违反规则 12.1: 禁止基于假设生成决策报告")

    # 验证静态分析是否真实运行过
    if source == "static_analysis":
        if not self.has_recent_flake8_run():
            raise ValueError("违反规则 12.1: 数据来源声称是静态分析，但未发现近期的分析记录")

    return True
```

**注意**：
- 这是通过 `DataVerificationGate` Hook 自动强制执行的
- AI 无法绕过这个检查
- 详见 `HOOKS_IMPLEMENTATION_GUIDE.md` 中的 "数据验证" 章节
```

---

## 4. Hooks讨论成果

### 4.1 风险点识别

**关键发现**：
- **最高风险操作**：数据库DROP、`rm -rf data/*`、`docker-compose down -v`
- **最容易被忽视**：规则文件修改、配置文件修改、Git强制操作
- **必须保护的数据**：`data.db` (310MB)、`textbooks.db`、PostgreSQL volumes

### 4.2 优先级排序

**实施计划**：

**P0级（立即实施）**：
1. **数据库保护Hook**：保护数据库DROP操作
2. **文件删除Hook**：保护`rm -rf data/*`操作
3. **Volume删除Hook**：保护`docker-compose down -v`操作

**P1级（2周内实施）**：
1. **规则文件修改Hook**：保护`DEVELOPMENT_RULES.md`、`PHASED_IMPLEMENTATION_PLAN.md`修改
2. **配置文件修改Hook**：保护配置文件修改
3. **Git强制操作Hook**：保护Git强制操作（如`git push --force`）

**P2级（可选）**：
1. **生产部署Hook**：保护生产部署
2. **批量修改Hook**：保护批量修改

**P3级（不实施）**：
1. **普通文件修改Hook**：影响开发效率

**平衡点**：保护关键资源，但不影响开发效率

### 4.3 检查机制设计

**四种核心机制**：

1. **批准令牌**：有时效性的授权机制
2. **风险评分**：智能评估操作风险 (1-10分)
3. **上下文感知**：理解环境和意图
4. **白名单机制**：避免过度保护

**智能决策流程**：
```
白名单 → 风险评分 → 上下文分析 → 执行检查
```

### 4.4 潜在问题

**8类问题**：

1. **技术问题**：Hook无法触发、执行失败、性能影响
2. **策略问题**：过度保护、保护不足、绕过机制
3. **维护问题**：规则维护、测试验证

**解决方案**：每个问题都有具体的应对策略

---

## 5. 最终方案：文档简化 + Hooks强化

### 5.1 方案对比

| 维度 | 方案A：只修改规则文档 | 方案B：文档简化 + Hooks强化 |
|------|-------------------|---------------------|
| **规则修改量** | 新增2个章节 + 修改4个章节 | 新增1个小节 + 修改2个小节 |
| **执行机制** | 依赖人工自觉 | Hooks自动强制执行 |
| **AI约束** | AI可以绕过 | AI无法绕过 |
| **流于形式** | 容易流于形式 | 不易流于形式 |
| **开发效率** | 影响不大 | 影响不大（P0级Hook不影响）|
| **可维护性** | 规则越多，维护成本越高 | Hooks需要维护，但规则简化了 |

### 5.2 推荐方案

**文档简化**：
- 只保留核心原则
- 删除冗长的检查清单
- 强调关键禁止事项

**Hooks实施**：
- **3个P0级Hook立即实施**：数据库保护、文件删除、Volume删除
- **6个核心检查机制**：批准令牌、风险评分、上下文感知、白名单机制、规则修改流程、紧急问题拦截、数据验证
- **让规则自动执行**

---

## 6. 实施计划

### 6.1 第一阶段：更新规则文档（1-2天）

**任务**：
1. [ ] 在 `DEVELOPMENT_RULES.md` 中新增 `4.4 规则修改流程`（带Hook引用）
2. [ ] 在 `DEVELOPMENT_RULES.md` 中修改 `13.1 严格禁止`（带Hook引用）
3. [ ] 在 `DEVELOPMENT_RULES.md` 中修改 `12.1 数据验证`（带Hook引用）
4. [ ] 更新 `DEVELOPMENT_RULES.md` 的版本号

**预期收益**：
- 规则文档简化
- 规则文档与Hooks集成

### 6.2 第二阶段：实现P0级Hooks（3-4天）

**任务**：
1. [ ] 实现数据库保护Hook
2. [ ] 实现文件删除Hook
3. [ ] 实现Volume删除Hook
4. [ ] 集成到 `AIActionWrapper` 中
5. [ ] 测试Hooks的有效性

**预期收益**：
- 保护关键资源
- 避免灾难性操作

### 6.3 第三阶段：实现P1级Hooks（5-10天）

**任务**：
1. [ ] 实现规则文件修改Hook
2. [ ] 实现配置文件修改Hook
3. [ ] 实现Git强制操作Hook
4. [ ] 集成到 `AIActionWrapper` 中
5. [ ] 测试Hooks的有效性

**预期收益**：
- 保护规则和规划
- 保护配置文件
- 保护Git历史

### 6.4 第四阶段：实现核心检查机制（11-20天）

**任务**：
1. [ ] 实现批准令牌机制
2. [ ] 实现风险评分机制
3. [ ] 实现上下文感知机制
4. [ ] 实现白名单机制
5. [ ] 集成到 `AIActionWrapper` 中
6. [ ] 测试检查机制的有效性

**预期收益**：
- 智能决策
- 避免过度保护
- 提高开发效率

---

## 7. 文件清单

| 文件路径 | 类型 | 说明 |
|---------|------|------|
| **最终方案文档** | | |
| `docs/DEVELOPMENT_RULES_HOOKS_IMPLEMENTATION_FINAL_PROPOSAL.md` | 文档 | 开发规则修改与Hooks实施 - 最终方案 |

---

**文档结束**

**生成时间**: 2026-03-29
**生成者**: AI架构师
**版本**: 1.0.0
**状态**: 待确认
