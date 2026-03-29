# 智能知识系统 - Hooks综合实施方案

**文档版本**: 2.0.0
**创建日期**: 2026-03-29
**作者**: AI架构师
**项目**: 灵知（LingZhi）系统
**状态**: 待实施

---

## 📋 执行总结

### 核心洞察

**规则流于形式的根本原因**：
```
当前系统只有：
文档层 (CLAUDE.md) → AI可能"遗忘"
         ↓
权限层 (Permissions) → 最后防线

缺少关键层：
Hooks层 (自动强制执行) → 让规则真正落地 ⭐
```

### 完整解决方案

**双层Hooks架构**：

```
┌─────────────────────────────────────────────────┐
│ 第1层: Claude Code Hooks (客户端)               │
│ - 作用: 拦截危险命令                            │
│ - 范围: Bash命令、文件操作                      │
│ - 实施: 配置settings.local.json                 │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 第2层: Backend Hooks (服务端)                   │
│ - 作用: 拦截AI操作                              │
│ - 范围: 规则修改、报告生成、决策制定            │
│ - 实施: AIActionWrapper + RulesChecker          │
└─────────────────────────────────────────────────┘
```

---

## 🎯 实施策略

### 策略1: 最小化规则修改

**修改内容**：
- ✅ 新增1个小节：4.4 规则修改流程
- ✅ 修改2个小节：13.1 禁止事项、12.1 数据验证
- ❌ 删除冗长的检查清单
- ❌ 不新增2个章节（避免规则膨胀）

**总计**：最小化修改，避免规则过多

### 策略2: 双层Hooks实施

**Claude Code Hooks (P0级 - 立即实施)**：
1. 数据库破坏性操作Hook
2. 批量文件删除Hook
3. Docker Volume删除Hook

**Backend Hooks (P0级 - 立即实施)**：
1. 规则修改检查Hook (RulesChecker)
2. 紧急问题拦截Hook (UrgencyGuard)
3. 数据验证Gate Hook (DataVerificationGate)

### 策略3: 渐进式实施

```
第1周: P0级Hooks (最关键)
  ↓
第2-3周: P1级Hooks (重要)
  ↓
第4周+: 核心检查机制 (优化)
```

---

## 📐 双层Hooks架构设计

### Layer 1: Claude Code Hooks (客户端)

#### 1.1 配置位置
```json
// ~/.claude/settings.local.json
{
  "hooks": {
    "pre-command": { ... },
    "session-start": { ... }
  }
}
```

#### 1.2 实施清单

| Hook ID | 触发条件 | 检查逻辑 | 优先级 |
|---------|---------|---------|--------|
| **CC-1** | `sqlite3 *data.db* *DROP*|*DELETE*` | 检查批准令牌 | P0 |
| **CC-2** | `rm -rf data/*` | 风险评分 + 确认 | P0 |
| **CC-3** | `docker-compose down -v` | 警告 + 确认 | P0 |
| **CC-4** | `Edit(DEVELOPMENT_RULES.md)` | 提示先讨论 | P1 |
| **CC-5** | `git push --force` | 警告 + 确认 | P1 |

#### 1.3 实施脚本

**脚本位置**：`scripts/hooks/claude_code/`

**核心脚本**：
```python
# scripts/hooks/claude_code/approval_token.py
class ApprovalToken:
    """批准令牌管理"""

    @classmethod
    def create(cls, operation: str, duration_minutes: int = 30):
        """创建批准令牌"""
        token = {
            "operation": operation,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "approved": True
        }
        with open("/tmp/claude_approval.json", 'w') as f:
            json.dump(token, f)

    @classmethod
    def validate(cls, operation: str) -> tuple[bool, str]:
        """验证批准令牌"""
        # 检查令牌文件
        # 检查操作类型
        # 检查是否过期
        # 返回 (是否有效, 消息)
```

```python
# scripts/hooks/claude_code/risk_scorer.py
class RiskScorer:
    """风险评分器"""

    RISK_RULES = {
        "database": {
            "patterns": [r"DROP\s+TABLE", r"DELETE\s+FROM.*WHERE\s+1\s*=\s*1"],
            "base_score": 10
        },
        "file_delete": {
            "patterns": [r"rm\s+-rf\s+data/", r"rm\s+-rf\s+.*\.db"],
            "base_score": 9
        }
    }

    @classmethod
    def score(cls, command: str) -> Dict:
        """评估命令风险分数"""
        # 计算风险分数
        # 返回 {score, category, action}
```

```python
# scripts/hooks/claude_code/db_write_check.py
#!/usr/bin/env python3
"""
数据库写操作检查Hook
"""
import sys
import json

def check_approval():
    """检查是否已获得用户批准"""
    approval_file = "/tmp/claude_approval.json"

    try:
        with open(approval_file) as f:
            approval = json.load(f)

        if approval.get('approved', False):
            return True, "✅ 已获批准"
        else:
            return False, "❌ 未获批准"

    except FileNotFoundError:
        return False, "❌ 未找到批准文件"

if __name__ == "__main__":
    approved, message = check_approval()

    if not approved:
        print(f"\n{message}")
        print("\n⚠️  数据库写操作需要用户批准！")
        print("\n请按以下步骤操作：")
        print("1. 先使用 AskUserQuestion 呈现方案")
        print("2. 获得用户批准后，创建批准文件:")
        print('   echo \'{"approved": true, "operation": "db_write"}\' > /tmp/claude_approval.json')
        print("3. 然后再执行操作\n")
        sys.exit(1)

    print(message)
    sys.exit(0)
```

---

### Layer 2: Backend Hooks (服务端)

#### 2.1 架构设计

**核心组件**：
```python
# backend/core/ai_action_wrapper.py
class AIActionWrapper:
    """
    AI操作包装器 - 拦截所有AI操作
    """

    def __init__(self):
        self.rules_checker = RulesChecker()
        self.urgency_guard = UrgencyGuard()
        self.data_verification_gate = DataVerificationGate()

    async def execute_action(self, action_type: str, action_data: Dict):
        """
        执行AI操作的统一入口
        """
        # 1. 紧急问题检查
        await self.urgency_guard.check_and_intercept(action_type, action_data)

        # 2. 规则修改检查
        if action_type == "modify_rules":
            self.rules_checker.check_modify_rules(action_data)

        # 3. 数据验证检查
        if action_type == "generate_report":
            self.data_verification_gate.verify_report_data(action_data)

        # 4. 执行操作
        return await self._execute_action(action_type, action_data)
```

#### 2.2 实施清单

| Hook ID | 组件 | 功能 | 优先级 |
|---------|------|------|--------|
| **BE-1** | RulesChecker | 检查规则修改流程 | P0 |
| **BE-2** | UrgencyGuard | 检查紧急问题状态 | P0 |
| **BE-3** | DataVerificationGate | 检查报告数据来源 | P0 |

#### 2.3 实现代码

**RulesChecker**:
```python
# backend/core/rules_checker.py
class RulesChecker:
    """规则修改检查器"""

    def check_modify_rules(self, action_data: Dict[str, Any]) -> bool:
        """
        检查规则修改操作

        规则 4.4.1: 是否已讨论
        规则 4.4.2: 基于真实数据
        规则 4.4.3: 是否达成共识
        """
        # 检查 4.4.1: 是否已讨论
        if not action_data.get("discussed"):
            raise PermissionError(
                "违反规则 4.4.1: 规则修改前必须经过讨论。"
                "请先使用 AskUserQuestion 组织讨论。"
            )

        # 检查 4.4.2: 基于真实数据
        if action_data.get("data_source") == "assumption":
            raise PermissionError(
                "违反规则 4.4.2: 必须基于真实测量数据修改规则。"
                "data_source 不能是 'assumption'"
            )

        # 检查 4.4.3: 是否达成共识
        if not action_data.get("consensus"):
            raise PermissionError(
                "违反规则 4.4.3: 规则修改必须获得团队共识。"
                "请记录讨论结果和共识情况。"
            )

        return True
```

**UrgencyGuard**:
```python
# backend/core/urgency_guard.py
class UrgencyGuard:
    """紧急问题守卫"""

    ALLOWED_URGENT_ACTIONS = [
        "fix_urgent_issue",
        "debug_system",
        "restart_service"
    ]

    BLOCKED_NON_URGENT_ACTIONS = [
        "add_tests",
        "refactor_code",
        "modify_documentation",
        "improve_coverage"
    ]

    async def check_and_intercept(self, action_type: str, action_data: Dict):
        """
        检查并拦截操作

        如果系统处于紧急状态，只允许修复紧急问题
        """
        if self.is_emergency_mode():
            if action_type in self.BLOCKED_NON_URGENT_ACTIONS:
                current_emergencies = await self.get_current_emergencies()
                raise PermissionError(
                    f"违反规则 13.1: 系统处于紧急状态（{current_emergencies}）。"
                    f"只允许修复紧急问题，禁止执行 '{action_type}'。"
                )

    def is_emergency_mode(self) -> bool:
        """检查系统是否处于紧急状态"""
        checks = [
            self.check_system_health(),
            self.check_api_container(),
            self.check_import_errors()
        ]
        return any(checks)

    def check_system_health(self) -> bool:
        """检查系统健康状态"""
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            return response.status_code != 200
        except:
            return True

    def check_api_container(self) -> bool:
        """检查API容器状态"""
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=zhineng-api", "--format", "{{.Status}}"],
            capture_output=True,
            text=True
        )
        return "unhealthy" in result.stdout

    def check_import_errors(self) -> bool:
        """检查导入错误"""
        result = subprocess.run(
            ["python", "-m", "flake8", "backend", "--select=F821"],
            capture_output=True,
            text=True
        )
        return len(result.stdout.strip()) > 0
```

**DataVerificationGate**:
```python
# backend/core/data_verification_gate.py
class DataVerificationGate:
    """数据验证门禁"""

    def verify_report_data(self, report: Dict) -> bool:
        """
        验证报告数据

        规则 12.1: 确保数据是真实的、准确的、完整的
        """
        metadata = report.get("metadata", {})

        # 检查数据来源
        data_source = metadata.get("data_source")
        if not data_source:
            raise ValueError(
                "违反规则 12.1: 报告必须声明数据来源。"
                "请在 metadata 中添加 data_source 字段。"
            )

        # 禁止基于假设
        if data_source == "assumption":
            raise ValueError(
                "违反规则 12.1: 禁止基于假设生成决策报告。"
                "data_source 不能是 'assumption'"
            )

        # 验证静态分析是否真实运行过
        if data_source == "static_analysis":
            if not self.has_recent_flake8_run():
                raise ValueError(
                    "违反规则 12.1: 数据来源声称是静态分析，但未发现近期的分析记录。"
                    "请先运行静态分析。"
                )

        # 验证测试数据是否真实运行过
        if data_source == "runtime_test":
            if not self.has_recent_test_run():
                raise ValueError(
                    "违反规则 12.1: 数据来源声称是测试，但未发现近期的测试记录。"
                    "请先运行测试。"
                )

        return True

    def has_recent_flake8_run(self) -> bool:
        """检查是否有近期的flake8运行记录"""
        # 检查日志文件或CI/CD记录
        log_file = "/tmp/flake8_last_run.log"
        if not os.path.exists(log_file):
            return False

        # 检查时间戳（最近24小时内）
        mtime = os.path.getmtime(log_file)
        return (time.time() - mtime) < 86400

    def has_recent_test_run(self) -> bool:
        """检查是否有近期的测试运行记录"""
        # 检查pytest日志或CI/CD记录
        log_file = "/tmp/pytest_last_run.log"
        if not os.path.exists(log_file):
            return False

        # 检查时间戳（最近24小时内）
        mtime = os.path.getmtime(log_file)
        return (time.time() - mtime) < 86400
```

---

## 🚀 实施计划

### 第1阶段: 准备和测试 (第1周)

#### 任务1.1: 创建目录结构
```bash
mkdir -p scripts/hooks/claude_code
mkdir -p backend/core
```

#### 任务1.2: 实现Claude Code Hooks
```bash
# 1. 创建批准令牌脚本
cat > scripts/hooks/claude_code/approval_token.py << 'EOF'
#!/usr/bin/env python3
import json
from datetime import datetime, timedelta

class ApprovalToken:
    """批准令牌管理"""
    TOKEN_FILE = "/tmp/claude_approval.json"

    @classmethod
    def create(cls, operation: str, duration_minutes: int = 30):
        token = {
            "operation": operation,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "approved": True
        }
        with open(cls.TOKEN_FILE, 'w') as f:
            json.dump(token, f)

    @classmethod
    def validate(cls, operation: str) -> tuple[bool, str]:
        if not os.path.exists(cls.TOKEN_FILE):
            return False, "❌ 未找到批准文件"

        with open(cls.TOKEN_FILE) as f:
            token = json.load(f)

        if token["operation"] != operation:
            return False, f"❌ 令牌类型不匹配"

        if not token.get("approved", False):
            return False, "❌ 令牌未批准"

        expires_at = datetime.fromisoformat(token["expires_at"])
        if datetime.now() > expires_at:
            return False, f"❌ 令牌已过期"

        return True, f"✅ 批准有效"
EOF

# 2. 创建数据库检查脚本
cat > scripts/hooks/claude_code/db_write_check.py << 'EOF'
#!/usr/bin/env python3
import sys
import json
from approval_token import ApprovalToken

if __name__ == "__main__":
    approved, message = ApprovalToken.validate("db_write")
    if not approved:
        print(f"\n{message}")
        print("\n⚠️  数据库写操作需要用户批准！")
        print("\n💡 如何获得批准:")
        print("1. 使用 AskUserQuestion 向用户说明方案")
        print("2. 用户批准后运行:")
        print('   python3 -c "from scripts_hooks.claude_code.approval_token import ApprovalToken; ApprovalToken.create(\'db_write\')"')
        sys.exit(1)
    print(message)
    sys.exit(0)
EOF

# 3. 设置执行权限
chmod +x scripts/hooks/claude_code/*.py
```

#### 任务1.3: 配置Claude Code Hooks
```bash
# 编辑 ~/.claude/settings.local.json
cat >> ~/.claude/settings.local.json << 'EOF'
,
  "hooks": {
    "pre-command": {
      "Bash(*sqlite3*data.db* *DROP*|*DELETE*)": {
        "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/claude_code/db_write_check.py",
        "description": "检查数据库写操作是否已获批准"
      },
      "Bash(rm -rf data/*)": {
        "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/claude_code/file_delete_check.py",
        "description": "检查文件删除操作是否安全"
      },
      "Bash(docker-compose down -v)": {
        "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/claude_code/volume_delete_check.py",
        "description": "检查Volume删除操作"
      }
    },
    "session-start": {
      "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/claude_code/session_start.py",
      "description": "会话开始时提醒阅读规则"
    }
  }
EOF
```

#### 任务1.4: 实现Backend Hooks
```bash
# 1. 创建AI操作包装器
cat > backend/core/ai_action_wrapper.py << 'EOF'
"""
AI操作包装器 - 统一入口
"""
from .rules_checker import RulesChecker
from .urgency_guard import UrgencyGuard
from .data_verification_gate import DataVerificationGate

class AIActionWrapper:
    def __init__(self):
        self.rules_checker = RulesChecker()
        self.urgency_guard = UrgencyGuard()
        self.data_verification_gate = DataVerificationGate()

    async def execute_action(self, action_type: str, action_data: dict):
        # 紧急问题检查
        await self.urgency_guard.check_and_intercept(action_type, action_data)

        # 规则修改检查
        if action_type == "modify_rules":
            self.rules_checker.check_modify_rules(action_data)

        # 数据验证检查
        if action_type == "generate_report":
            self.data_verification_gate.verify_report_data(action_data)

        # 执行操作
        return await self._execute(action_type, action_data)
EOF

# 2. 创建各个Hook组件
# (按照上面的代码实现)
```

#### 任务1.5: 测试Hooks
```bash
# 测试Claude Code Hooks
echo "测试数据库Hook..."
sqlite3 data/data.db "DROP TABLE test;"
# 应该被阻止

echo '{"approved": true, "operation": "db_write"}' > /tmp/claude_approval.json
sqlite3 data/data.db "DROP TABLE test;"
# 应该允许

# 测试Backend Hooks
python3 -m pytest tests/test_hooks/test_rules_checker.py
python3 -m pytest tests/test_hooks/test_urgency_guard.py
python3 -m pytest tests/test_hooks/test_data_verification_gate.py
```

---

### 第2阶段: 更新规则文档 (第1周)

#### 任务2.1: 修改DEVELOPMENT_RULES.md

**新增 4.4 规则修改流程**：
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

**强制执行（技术层 - 详见 HOOKS_IMPLEMENTATION_GUIDE.md）**：

**触发条件**：
当 AI 或开发者尝试修改 `DEVELOPMENT_RULES.md` 或 `PHASED_IMPLEMENTATION_PLAN.md` 时触发。

**执行机制**：
`RulesChecker` Hook 将自动检查规则修改操作。

**注意**：
- 这是通过 `RulesChecker` Hook 自动强制执行的
- AI 无法绕过这个检查
- 详见 `HOOKS_IMPLEMENTATION_GUIDE.md`
```

**修改 13.1 禁止事项**：
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
- 系统健康检查失败
- API容器处于unhealthy状态
- 存在未定义变量等代码错误

**强制执行机制（`UrgencyGuard` Hook）**：
当系统处于"紧急状态"时，只允许修复紧急问题，禁止执行其他操作。

**注意**：
- 这是通过 `UrgencyGuard` Hook 自动强制执行的
- 详见 `HOOKS_IMPLEMENTATION_GUIDE.md`
```

**修改 12.1 数据验证**：
```markdown
### 12.1 数据验证（带强制执行）

**数据验证要求**：
- [ ] 确保数据是真实的（基于静态分析或运行测试）
- [ ] 确保数据是准确的（经过二次验证）
- [ ] 确保数据是完整的（覆盖所有范围）

**强制执行机制（`DataVerificationGate` Hook）**：
在生成报告或进行决策前，必须通过 `DataVerificationGate`。

**注意**：
- 这是通过 `DataVerificationGate` Hook 自动强制执行的
- 详见 `HOOKS_IMPLEMENTATION_GUIDE.md`
```

#### 任务2.2: 更新CLAUDE.md

**添加Hooks说明**：
```markdown
## Hooks强制执行

本项目的规则通过以下两层Hooks自动强制执行：

### 第1层: Claude Code Hooks (客户端)
- 数据库破坏性操作检查
- 批量文件删除检查
- Docker Volume删除检查

### 第2层: Backend Hooks (服务端)
- 规则修改流程检查 (RulesChecker)
- 紧急问题拦截 (UrgencyGuard)
- 数据验证门禁 (DataVerificationGate)

**关键**：AI无法绕过这些检查，规则真正落地！

详见: `HOOKS_IMPLEMENTATION_GUIDE.md`
```

---

### 第3阶段: 试运行和调优 (第2周)

#### 任务3.1: 在开发环境测试
```bash
# 启动开发环境
docker-compose up -d

# 测试各种场景
# 1. 测试数据库保护
# 2. 测试文件删除保护
# 3. 测试规则修改保护
# 4. 测试紧急问题拦截
# 5. 测试数据验证
```

#### 任务3.2: 收集问题和反馈
```bash
# 查看Hooks日志
tail -f /tmp/claude_hooks.log

# 收集用户反馈
# 记录误报和漏报
# 调整规则和阈值
```

#### 任务3.3: 调整规则和阈值
```python
# 根据反馈调整
# 1. 调整风险评分阈值
# 2. 优化白名单
# 3. 改进错误提示
```

---

### 第4阶段: 正式部署 (第3周)

#### 任务4.1: 部署到生产环境
```bash
# 1. 备份当前配置
cp ~/.claude/settings.local.json ~/.claude/settings.local.json.backup

# 2. 更新配置
# 3. 部署Backend Hooks
# 4. 重启服务
```

#### 任务4.2: 提供用户培训
```bash
# 1. 创建培训文档
# 2. 组织培训会议
# 3. 提供快速参考指南
```

#### 任务4.3: 设置监控告警
```bash
# 1. 设置Hooks日志监控
# 2. 配置异常告警
# 3. 设置性能监控
```

---

## 📊 验证和监控

### 验证清单

| 检查项 | 验证方法 | 预期结果 |
|-------|---------|---------|
| **数据库保护** | 尝试DROP TABLE | 被阻止，提示需要批准 |
| **文件删除保护** | 尝试rm -rf data/* | 被阻止，提示风险 |
| **Volume删除保护** | 尝试docker-compose down -v | 被阻止，警告确认 |
| **规则修改保护** | 尝试修改规则文件 | 提示需要讨论 |
| **紧急问题拦截** | 在紧急状态下执行非紧急操作 | 被阻止，提示优先修复 |
| **数据验证** | 生成基于假设的报告 | 被阻止，提示需要真实数据 |

### 监控指标

```python
# Hooks监控脚本
class HooksMonitor:
    def collect_metrics(self):
        return {
            "hooks_triggered": self.count_hooks_triggered(),
            "operations_blocked": self.count_operations_blocked(),
            "operations_allowed": self.count_operations_allowed(),
            "false_positives": self.count_false_positives(),
            "false_negatives": self.count_false_negatives(),
            "avg_response_time": self.measure_avg_response_time()
        }
```

---

## 🎓 成功标准

### 技术指标

- ✅ P0级Hooks部署率: 100%
- ✅ Hooks准确率: > 95%
- ✅ Hooks响应时间: < 1秒
- ✅ 误报率: < 5%
- ✅ 漏报率: < 1%

### 业务指标

- ✅ 灾难性操作: 0次
- ✅ 规则违规: 减少80%
- ✅ 数据准确性: 提升50%
- ✅ 开发效率: 不受影响 (±5%)

---

## 📚 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| **最终方案** | `docs/DEVELOPMENT_RULES_HOOKS_IMPLEMENTATION_FINAL_PROPOSAL.md` | 开发规则修改与Hooks实施最终方案 |
| **Hooks指南** | `docs/HOOKS_IMPLEMENTATION_GUIDE.md` | Hooks实施详细指南 |
| **风险分析** | `/tmp/hooks_risk_analysis.md` | 风险点分析 |
| **优先级矩阵** | `/tmp/hooks_priority_matrix.md` | 优先级排序 |
| **检查机制** | `/tmp/hooks_check_mechanisms.md` | 检查机制设计 |
| **潜在问题** | `/tmp/hooks_potential_issues.md` | 潜在问题分析 |
| **综合方案** | `docs/COMPREHENSIVE_HOOKS_IMPLEMENTATION_PLAN.md` | 本文档 |

---

**文档结束**

**生成时间**: 2026-03-29
**生成者**: AI架构师
**版本**: 2.0.0
**状态**: 待实施
