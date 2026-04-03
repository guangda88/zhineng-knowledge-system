# Pre-commit 钩子安装完成

**日期**: 2026-04-01
**状态**: ✅ 安装完成

---

## ✅ 安装成功

### 环境信息

- **Python**: 3.12.3
- **虚拟环境**: venv/
- **Pre-commit**: 4.5.1
- **钩子位置**: ~/.git-hooks/pre-commit

### 集成方式

由于项目使用了自定义的 `core.hooksPath`，pre-commit钩子已集成到现有的钩子目录中：

```bash
~/.git-hooks/pre-commit  # 自动调用项目级pre-commit
```

---

## 🔄 工作原理

### 提交时自动运行

每次执行 `git commit` 时，会自动运行以下检查：

1. **检查导入路径规范** ✅
   - 确保所有backend代码使用 `from backend.xxx` 格式
   - 自动识别不符合规范的导入

2. **代码格式化** (Black)
   - 自动格式化Python代码
   - 统一代码风格

3. **Import排序** (isort)
   - 自动排序导入语句
   - 与Black兼容

4. **代码检查** (flake8)
   - 检查代码质量问题
   - 检查文档字符串

5. **安全检查** (bandit)
   - 检查安全漏洞
   - 检查密钥泄露

6. **类型检查** (mypy)
   - 静态类型检查
   - 提前发现类型错误

---

## 🧪 测试验证

### 运行导入路径检查

```bash
$ venv/bin/pre-commit run check-imports --all-files
检查导入路径规范.........................................................Passed
```

### 测试结果

✅ **通过** - 所有文件的导入路径都符合规范

---

## 📋 可用的命令

### 手动运行所有检查

```bash
# 检查所有文件
venv/bin/pre-commit run --all-files

# 检查特定文件
venv/bin/pre-commit run check-imports --files backend/main.py

# 列出所有可用的钩子
venv/bin/pre-commit run --list-hooks
```

### 更新钩子版本

```bash
# 更新到最新版本
venv/bin/pre-commit autoupdate

# 查看可更新的钩子
venv/bin/pre-commit autoupdate --dry-run
```

### 跳过检查（不推荐）

```bash
# 跳过所有钩子
git commit --no-verify -m "your message"

# 跳过特定钩子
SKIP=check-imports git commit -m "your message"
```

---

## 🛠️ 故障排查

### 问题1: 钩子未运行

**症状**: 提交时没有看到pre-commit输出

**检查**:
```bash
# 验证钩子文件存在
ls -la ~/.git-hooks/pre-commit

# 验证钩子可执行
test -x ~/.git-hooks/pre-commit && echo "OK" || echo "Not executable"

# 手动运行钩子
~/.git-hooks/pre-commit
```

### 问题2: 检查失败

**症状**: 某些检查未通过

**解决**:
```bash
# 查看失败的详情
venv/bin/pre-commit run --all-files --verbose

# 自动修复可修复的问题
venv/bin/pre-commit run --all-files --fix

# 跳过失败的检查（仅用于调试）
SKIP=hook-name git commit -m "your message"
```

### 问题3: 速度太慢

**症状**: pre-commit运行时间过长

**优化**:
```bash
# 仅检查staged文件
venv/bin/pre-commit run  # 不加 --all-files

# 使用缓存（默认启用）
venv/bin/pre-commit run --all-files

# 禁用慢速钩子
# 编辑 .pre-commit-config.yaml，添加: skip: [hook-name]
```

---

## 📊 当前配置

### 已启用的钩子

| 钩子 | 功能 | 状态 |
|------|------|------|
| check-imports | 导入路径规范 | ✅ 已通过 |
| trailing-whitespace | 清理尾随空格 | ✅ |
| end-of-file-fixer | 确保换行符结尾 | ✅ |
| check-yaml | YAML语法检查 | ✅ |
| check-toml | TOML语法检查 | ✅ |
| check-json | JSON语法检查 | ✅ |
| check-added-large-files | 检查大文件 | ✅ |
| detect-private-key | 检测私钥泄露 | ✅ |
| check-merge-conflict | 检查合并冲突标记 | ✅ |
| black | 代码格式化 | ✅ |
| isort | Import排序 | ✅ |
| flake8 | 代码质量检查 | ✅ |
| bandit | 安全检查 | ✅ |
| mypy | 类型检查 | ✅ |
| shellcheck | Shell脚本检查 | ✅ |

### 文件过滤器

```
排除: venv/, .venv/, build/, dist/, migrations/, data/, logs/
包含: ^backend/.*\.py$ (导入路径检查)
```

---

## 🎯 最佳实践

### 提交前检查

1. **本地提交前**:
   ```bash
   # 手动运行一次，避免意外
   venv/bin/pre-commit run --all-files
   ```

2. **修复问题后**:
   ```bash
   # 再次检查确认
   venv/bin/pre-commit run --all-files
   ```

3. **正常提交**:
   ```bash
   git add .
   git commit -m "your message"  # 自动运行pre-commit
   ```

### 第一次使用

如果你第一次在项目上使用pre-commit：

```bash
# 1. 在所有文件上运行
venv/bin/pre-commit run --all-files

# 2. 可能会修复一些问题（自动修复）
git add .

# 3. 再次运行检查
venv/bin/pre-commit run --all-files

# 4. 现在可以正常提交了
git commit -m "your message"
```

---

## 💡 提示和技巧

### 自动修复

有些钩子可以自动修复问题：
```bash
# 使用 --fix 参数
venv/bin/pre-commit run --all-files --fix
```

### 并行运行

Pre-commit会自动并行运行钩子以提高速度：
```bash
# 默认并行
venv/bin/pre-commit run --all-files

# 查看并行度配置
grep "jobs" .pre-commit/config.yaml
```

### 查看日志

```bash
# 查看pre-commit日志
~/.cache/pre-commit/pre-commit.log

# 查看最近的运行结果
venv/bin/pre-commit run --all-files --show-diff-on-failure
```

---

## 🔄 持续维护

### 定期更新

```bash
# 每月更新一次钩子版本
venv/bin/pre-commit autoupdate

# 更新后测试
venv/bin/pre-commit run --all-files
```

### 添加新钩子

编辑 `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/author/hook
    rev: v1.0.0
    hooks:
      - id: hook-name
```

然后重新安装：
```bash
venv/bin/pre-commit install
```

---

## ✅ 安装确认

- [x] Pre-commit包已安装 (4.5.1)
- [x] 钩子文件已创建 (~/.git-hooks/pre-commit)
- [x] 钩子可执行
- [x] 测试运行通过
- [x] 所有检查已配置
- [x] 文档已完成

---

**众智混元，万法灵通** ⚡🚀

**Pre-commit钩子已成功安装并运行**
