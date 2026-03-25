# 开发者环境设置指南

本文档描述如何配置智能知识系统的开发环境。

## 目录

- [快速安装](#快速安装)
- [手动安装](#手动安装)
- [预提交钩子](#预提交钩子)
- [IDE 配置](#ide-配置)
- [故障排查](#故障排查)

---

## 快速安装

运行自动安装脚本：

```bash
cd /home/ai/zhineng-knowledge-system
bash setup-dev-env.sh
```

该脚本会自动完成：
1. 创建/激活虚拟环境
2. 安装所有开发依赖
3. 安装预提交钩子
4. 验证配置

---

## 手动安装

### 1. 前置要求

- Python 3.12+
- Git
- pip

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装开发依赖

```bash
# 代码格式化
pip install black==24.10.0

# Import 排序
pip install isort==5.13.2

# 代码检查
pip install flake8==7.1.1
pip install flake8-docstrings flake8-bugbear flake8-comprehensions

# 安全检查
pip install bandit==1.8.0

# 类型检查
pip install mypy==1.14.1

# 预提交框架
pip install pre-commit

# 类型存根
pip install types-requests types-PyYAML
```

### 4. 安装预提交钩子

```bash
pre-commit install
```

### 5. 验证安装

```bash
# 运行所有钩子
pre-commit run --all-files
```

---

## 预提交钩子

### 配置的钩子

| 钩子 | 功能 | 自动修复 | 说明 |
|------|------|----------|------|
| black | 代码格式化 | ✅ | 统一代码风格 |
| isort | import 排序 | ✅ | 整理导入语句 |
| flake8 | 代码规范检查 | ❌ | 检测代码问题 |
| trailing-whitespace | 清理尾随空格 | ✅ | 移除行尾空格 |
| end-of-file-fixer | 文件换行符结尾 | ✅ | 确保文件以换行符结尾 |
| check-yaml | YAML 语法检查 | ❌ | 验证 YAML 文件 |
| check-toml | TOML 语法检查 | ❌ | 验证 TOML 文件 |
| check-json | JSON 语法检查 | ❌ | 验证 JSON 文件 |
| bandit | 安全检查 | ❌ | 检测安全问题 |
| mypy | 类型检查 | ❌ | 静态类型检查 |
| detect-private-key | 私钥检测 | ❌ | 防止提交密钥 |
| check-added-large-files | 大文件检查 | ❌ | 防止提交大文件 |

### 常用命令

```bash
# 手动运行所有钩子
pre-commit run --all-files

# 运行特定钩子
pre-commit run black --all-files

# 跳过钩子提交（紧急情况）
git commit --no-verify -m "message"

# 更新钩子到最新版本
pre-commit autoupdate

# 查看钩子差异
pre-commit run --show-diff-on-failure

# 卸载钩子
pre-commit uninstall
```

### 配置文件

- `.pre-commit-config.yaml` - 钩子配置
- `.flake8` - flake8 规则配置
- `pyproject.toml` - 项目和工具配置

---

## IDE 配置

### VS Code

创建 `.vscode/settings.json`:

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    },
    "editor.defaultFormatter": "ms-python.black-formatter"
  },
  "black-formatter.args": ["--line-length=100"],
  "isort.args": ["--profile=black", "--line-length=100"],
  "flake8.args": ["--max-line-length=100", "--extend-ignore=E203,W503"],
  "mypy.args": ["--ignore-missing-imports"]
}
```

推荐扩展：
- Python (ms-python.python)
- Black Formatter (ms-python.black-formatter)
- Pylance (ms-python.vscode-pylance)

### PyCharm

1. **Black 配置**:
   - Settings → Tools → External Tools
   - 添加 Black: `$ProjectFileDir$/venv/bin/black --line-length=100 $FilePath$`

2. **代码风格**:
   - Settings → Editor → Code Style → Python
   - 设置 Line length 为 100

---

## 故障排查

### 问题: 预提交钩子运行缓慢

**解决方案**: 使用 `pre-commit run --files <file>` 只检查改动的文件

### 问题: 虚拟环境未激活

**解决方案**:
```bash
source venv/bin/activate
```

### 问题: 钩子执行失败

**解决方案**:
```bash
# 清除缓存重新安装
pre-commit clean
pre-commit install --hook-type pre-commit
```

### 问题: 依赖冲突

**解决方案**:
```bash
# 创建干净的虚拟环境
rm -rf venv
python3 -m venv venv
source venv/bin/activate
bash setup-dev-env.sh
```

---

## 配置文件说明

### `.pre-commit-config.yaml`

定义所有预提交钩子及其行为。支持：
- 自动修复（如 black, isort）
- 仅检查（如 flake8, mypy）
- CI 配置（跳过自动修复钩子）

### `.flake8`

flake8 代码检查配置：
- `max-line-length`: 最大行长度（100）
- `ignore`: 忽略的错误码
- `exclude`: 排除的目录

### `pyproject.toml`

统一的项目配置文件，包含：
- black 配置
- isort 配置
- mypy 配置
- bandit 配置
- pytest 配置

---

## 更多信息

- [pre-commit 官方文档](https://pre-commit.com/)
- [Black 文档](https://black.readthedocs.io/)
- [flake8 文档](https://flake8.pycqa.org/)
- [isort 文档](https://pycqa.github.io/isort/)
