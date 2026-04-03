# P1-A 导入路径渐进式修复策略

**日期**: 2026-04-01
**策略**: 渐进式修复（新代码统一路径，旧代码保持不变）

---

## 📊 当前状态

### 已修复文件（13个）
- ✅ backend/main.py
- ✅ backend/api/v1/__init__.py
- ✅ backend/api/v1/*.py（11个文件）

### 测试影响
- ❌ 33个测试失败（asyncpg + TestClient事件循环冲突）
- ⚠️ 这是P1-B问题，与P1-A无关

---

## 🎯 渐进式修复策略

### 原则

**不破坏现有代码**：
- ✅ 已有的文件保持现状（即使导入路径混用）
- ✅ 仅在新文件和新修改中使用统一路径

**新代码规范**：
```python
# ✅ 正确（新代码）
from backend.services.xxx import YYY
from backend.api.v1.xxx import ZZZ

# ❌ 错误（新代码）
from services.xxx import YYY
from api.v1.xxx import ZZZ
```

**修改代码规范**：
```python
# 如果修改现有文件，只修改导入部分：
# 修改前
from services.xxx import YYY
from api.v1.zzz import WWW

# 修改后
from backend.services.xxx import YYY
from backend.api.v1.zzz import WWW

# 其他代码保持不变
```

---

## 📋 待修复文件分类

### 1. 新文件（立即修复）✅

**优先级：P0**
以下文件是新增的，必须使用统一路径：

**新增的API端点**：
- ✅ backend/api/v1/analytics.py - 已修复
- ✅ backend/api/v1/evolution.py - 已修复

**新增的服务**：
- ✅ backend/services/evolution/multi_ai_adapter.py - 已修复
- ✅ backend/services/evolution/comparison_engine.py - 已修复

### 2. 修改文件（修改时统一路径）

**优先级：P1**
以下文件如果需要修改，顺便统一导入路径：

**backend/middleware/**（3个文件待检查）**
**backend/services/**（部分文件待检查）**

### 3. 旧文件（暂时不修复）⏸️

**优先级：P2-P3**
**暂不修复**：
- backend/api/v1/*（已修复的除外）
- backend/models/*
- backend/services/*（大部分）

---

## 🛠️ 实施步骤

### Step 1: 创建代码规范文档

**文件**: `docs/CODE_STYLE.md`

```markdown
## 导入路径规范

### 统一规则

从2026-04-01起，所有新代码和修改代码必须使用：

```python
from backend.services.xxx import YYY
from backend.api.v1.xxx import ZZZ
from backend.models.xxx import WWW
from backend.core.xxx import VV
```

### 例外情况

**测试文件**：
```python
# 测试可以省略backend前缀
from backend.services.xxx import YYY  # 推荐
import sys; sys.path.insert(0, '..')
from services.xxx import YYY  # 允许但不推荐
```

**__init__.py文件**：
```python
# 在backend/xxx/__init__.py中
from .yyy import YYY  # 相对导入允许
```

### 自动检查

使用pre-commit钩子检查：
\`\`\`bash
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-imports
        name: Check import paths
        entry: python scripts/check_imports.py
        language: system
\`\`\`
```

### Step 2: 创建导入路径检查工具

**文件**: `scripts/check_imports.py`

```python
#!/usr/bin/env python3
"""检查Python文件的导入路径是否符合规范"""

import ast
import sys
from pathlib import Path


def check_imports(file_path):
    """检查单个文件的导入"""
    with open(file_path, 'r') as f:
        source = f.read()

    tree = ast.parse(source)

    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                # 检查是否是backend内部的模块
                if module.startswith(('api.', 'services.', 'models.',
                                       'core.', 'auth.', 'middleware.',
                                       'cache.', 'domains.', 'gateway.',
                                       'monitoring.', 'common.')):
                    if not module.startswith('backend.'):
                        issues.append({
                            'line': node.lineno,
                            'module': module,
                            'message': f'应该使用 "from backend.{module}"'
                        })

        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module and module.startswith(('api.', 'services.', 'models.',
                                            'core.', 'auth.', 'middleware.',
                                            'cache.', 'domains.', 'gateway.',
                                            'monitoring.', 'common.')):
                if not module.startswith('backend.'):
                    issues.append({
                        'line': node.lineno,
                        'module': module,
                        'message': f'应该使用 "from backend.{module}"'
                    })

    return issues


if __name__ == '__main__':
    file_path = sys.argv[1]
    issues = check_imports(file_path)

    if issues:
        print(f"❌ {file_path}: 发现 {len(issues)} 个导入路径问题")
        for issue in issues:
            print(f"  Line {issue['line']}: {issue['module']}")
            print(f"    {issue['message']}")
        sys.exit(1)
    else:
        print(f"✅ {file_path}: 导入路径符合规范")
        sys.exit(0)
```

### Step 3: 添加到pre-commit钩子

```bash
# 安装pre-commit
pip install pre-commit

# 创建.pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: local
    hooks:
      - id: check-imports
        name: 检查导入路径
        entry: python scripts/check_imports.py
        language: system
        files: ^backend/.*\.py$
EOF

# 安装钩子
pre-commit install
```

### Step 4: 渐进式修复优先级

**Week 1: 工具和规范**
- ✅ 创建检查工具
- ✅ 创建代码规范文档
- ✅ 添加pre-commit钩子

**Week 2-3: 新代码优先**
- ✅ 所有新文件使用统一路径
- ✅ 修改文件时顺便统一路径

**Week 4: 评估和决策**
- 评估新代码的统一路径效果
- 决定是否扩大到旧代码

---

## 📊 成功指标

### 短期（2周）

**指标**：
- ✅ 所有新文件100%使用统一路径
- ✅ pre-commit钩子启用
- ✅ 无新增混用导入路径

### 中期（1个月）

**指标**：
- ⏳ 50%的修改文件使用统一路径
- ⏳ 导入路径检查覆盖率 > 80%
- ⏳ 开发者习惯养成

### 长期（3个月）

**指标**：
- ⏳ 80%的代码使用统一路径
- ⏳ 旧代码逐步迁移
- ⏳ 完全移除sys.path hack

---

## 🎯 与P1-B测试框架的关系

**澄清**：33个测试失败是P1-B问题（asyncpg + TestClient），不是P1-A导致的。

**证据**：
- P1-A修复的文件：13个
- 测试失败：33个
- 失败原因：`RuntimeError: Event loop is closed`（asyncpg问题）

**结论**：P1-A和B是独立问题，可以分别解决。

---

## 💡 下一步行动

### 立即执行（今天）

1. ✅ 数据库迁移完成
2. ⏳ 创建导入路径检查工具
3. ⏳ 添加pre-commit钩子

### 本周完成

4. ⏳ 混元+DeepSeek API集成
5. ⏳ 搜索+问答前端集成
6. ⏳ 导入路径规范文档

### 本月完成

7. ⏳ 收集真实用户数据
8. ⏳ 第一轮对比学习
9. ⏳ 第一轮系统进化

---

## 📝 总结

**策略**：渐进式，不破坏现有代码
**重点**：新代码统一路径，旧代码保持现状
**工具**：pre-commit钩子自动检查
**目标**：3个月内80%代码统一

**优势**：
- ✅ 风险最低
- ✅ 不影响现有功能
- ✅ 开发者可接受
- ✅ 可持续改进

**众智混元，万法灵通** ⚡🚀
