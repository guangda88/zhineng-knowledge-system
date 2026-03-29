# 智能知识系统 - Hooks配置指南

**目的**: 让规则自动执行，而不依赖AI的"记忆"和"自律"

---

## 什么是Hooks？

Hooks是在特定事件时自动触发的脚本，用于强制执行规则。

**关键特点**：
- ✅ **自动触发**：不需要AI"记住"执行
- ✅ **强制执行**：不通过检查就阻止操作
- ✅ **可验证**：每次操作都有检查记录

---

## 三层防护机制

```
用户请求
   ↓
┌─────────────────────────────────────┐
│ 第1层: CLAUDE.md (文档)              │
│ - 建议性的工作流程                   │
│ - AI应该遵守的原则                   │
│ - 问题: 可能被遗忘或忽视             │
└─────────────────────────────────────┘
   ↓
┌─────────────────────────────────────┐
│ 第2层: Hooks (自动检查) ⭐ 关键      │
│ - 在特定事件时自动触发               │
│ - 强制执行关键规则                   │
│ - 不通过就阻止操作                   │
└─────────────────────────────────────┘
   ↓
┌─────────────────────────────────────┐
│ 第3层: Permissions (权限控制)        │
│ - 最终的安全网                       │
│ - 阻止未授权的操作                   │
└─────────────────────────────────────┘
```

---

## 需要配置的Hooks

### Hook 1: 数据库操作前检查

**目的**: 防止未经批准的数据库写操作

```json
{
  "hooks": {
    "pre-command": {
      "Bash(*sqlite3* *ALTER*|*DROP*|*DELETE*|*UPDATE*|*INSERT*)": {
        "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/db_write_check.py",
        "description": "检查数据库写操作是否已获批准"
      }
    }
  }
}
```

**脚本内容**: `scripts/hooks/db_write_check.py`
```python
#!/usr/bin/env python3
"""
数据库写操作检查Hook
"""
import sys
import json

def check_approval():
    """
    检查是否已获得用户批准
    """
    # 检查是否有批准标记文件
    approval_file = "/tmp/db_write_approval.json"

    try:
        with open(approval_file) as f:
            approval = json.load(f)

        # 检查批准是否有效
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
        print('   echo \'{"approved": true}\' > /tmp/db_write_approval.json')
        print("3. 然后再执行操作\n")
        sys.exit(1)

    print(message)
    sys.exit(0)
```

---

### Hook 2: 文件删除前检查

**目的**: 防止误删重要文件

```json
{
  "hooks": {
    "pre-command": {
      "Bash(rm -rf *)": {
        "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/file_delete_check.py",
        "description": "检查文件删除操作是否安全"
      }
    }
  }
}
```

---

### Hook 3: Git提交前检查

**目的**: 确保提交符合规范

```json
{
  "hooks": {
    "pre-command": {
      "Bash(git commit *)": {
        "command": "bash /home/ai/zhineng-knowledge-system/scripts/hooks/git_commit_check.sh",
        "description": "检查Git提交是否符合规范"
      }
    }
  }
}
```

---

### Hook 4: 会话开始时提醒

**目的**: 每次会话开始时提醒AI阅读规则

```json
{
  "hooks": {
    "session-start": {
      "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/session_start.py",
      "description": "会话开始时提醒阅读规则"
    }
  }
}
```

**脚本内容**: `scripts/hooks/session_start.py`
```python
#!/usr/bin/env python3
"""
会话开始时提醒Hook
"""
import os

def print_reminder():
    """
    打印规则提醒
    """
    print("\n" + "="*70)
    print("📋 智能知识系统 - 开发规则提醒")
    print("="*70)
    print("\n⚠️  在执行任何操作前，请确保：")
    print("\n1. ✅ 已阅读 CLAUDE.md")
    print("2. ✅ 已阅读 DEVELOPMENT_RULES.md")
    print("3. ✅ 已完成开发前检查清单")
    print("4. ✅ 涉及数据库写操作时已获批准")
    print("5. ✅ 涉及文件删除时已生成预览")
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    print_reminder()
```

---

## 实施步骤

### 第1步: 创建Hooks目录

```bash
mkdir -p /home/ai/zhineng-knowledge-system/scripts/hooks
```

### 第2步: 创建Hook脚本

```bash
# 数据库写操作检查
cat > /home/ai/zhineng-knowledge-system/scripts/hooks/db_write_check.py << 'EOF'
#!/usr/bin/env python3
import sys
import json

def check_approval():
    approval_file = "/tmp/db_write_approval.json"
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
        print("\n请先使用 AskUserQuestion 获得批准\n")
        sys.exit(1)
    print(message)
    sys.exit(0)
EOF

chmod +x /home/ai/zhineng-knowledge-system/scripts/hooks/db_write_check.py
```

### 第3步: 配置Settings

编辑 `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "pre-command": {
      "Bash(*sqlite3* *ALTER*|*DROP*|*DELETE*|*UPDATE*|*INSERT*)": {
        "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/db_write_check.py",
        "description": "检查数据库写操作是否已获批准"
      },
      "Bash(rm -rf *)": {
        "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/file_delete_check.py",
        "description": "检查文件删除操作是否安全"
      },
      "Bash(git commit *)": {
        "command": "bash /home/ai/zhineng-knowledge-system/scripts/hooks/git_commit_check.sh",
        "description": "检查Git提交是否符合规范"
      }
    },
    "session-start": {
      "command": "python3 /home/ai/zhineng-knowledge-system/scripts/hooks/session_start.py",
      "description": "会话开始时提醒阅读规则"
    }
  }
}
```

### 第4步: 测试Hooks

```bash
# 测试数据库写操作Hook
echo '{"approved": false}' > /tmp/db_write_approval.json
sqlite3 test.db "DROP TABLE test;"
# 应该被阻止

echo '{"approved": true}' > /tmp/db_write_approval.json
sqlite3 test.db "DROP TABLE test;"
# 应该允许
```

---

## 验证规则执行的效果

配置Hooks后，每次操作都会有检查：

### 场景1: 数据库写操作

```bash
$ sqlite3 knowledge.db "DROP TABLE textbooks;"

❌ 未获批准

⚠️  数据库写操作需要用户批准！

请先使用 AskUserQuestion 获得批准
```

### 场景2: 文件删除

```bash
$ rm -rf /home/ai/zhineng-knowledge-system/data

⚠️  危险操作检测！

您正在删除: /home/ai/zhineng-knowledge-system/data
请先生成预览脚本并确认
```

### 场景3: 会话开始

```
$ 新会话开始

======================================================================
📋 智能知识系统 - 开发规则提醒
======================================================================

⚠️  在执行任何操作前，请确保：

1. ✅ 已阅读 CLAUDE.md
2. ✅ 已阅读 DEVELOPMENT_RULES.md
3. ✅ 已完成开发前检查清单
4. ✅ 涉及数据库写操作时已获批准
5. ✅ 涉及文件删除时已生成预览

======================================================================
```

---

## 与开发规则修改提案的关系

回到您最初的问题：如何让规则不流于形式？

**答案**：

1. **文档层 (CLAUDE.md + DEVELOPMENT_RULES.md)**
   - 提供原则和指导
   - AI应该参考，但可能遗忘

2. **Hooks层 (自动强制执行)** ⭐ **这是关键**
   - 自动触发，不依赖AI记忆
   - 强制执行，不通过就阻止
   - **让规则真正落地**

3. **权限层 (Permissions)**
   - 最终的安全网
   - 阻止未授权操作

**结论**：
- 规则再多，没有Hooks也容易流于形式
- Hooks让规则自动执行，不依赖AI的"自律"
- **这才是让规则落到实处的关键**

---

## 下一步

您希望我：

A. **立即实施Hooks配置** (推荐)
   - 创建所有Hook脚本
   - 配置settings.local.json
   - 测试验证

B. **先讨论具体需要哪些Hooks**
   - 评估风险点
   - 确定优先级
   - 设计检查逻辑

C. **提供更详细的实现方案**
   - 完整的脚本代码
   - 测试用例
   - 维护指南

D. **其他建议**
