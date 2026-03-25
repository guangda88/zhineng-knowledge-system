# 贡献指南

感谢你对智能知识系统的关注！我们欢迎所有形式的贡献。

## 目录

- [行为准则](#行为准则)
- [开发流程](#开发流程)
- [分支策略](#分支策略)
- [提交规范](#提交规范)
- [PR流程](#pr流程)
- [代码规范](#代码规范)
- [测试要求](#测试要求)
- [文档规范](#文档规范)
- [CI/CD流程](#cicd流程)

---

## 行为准则

- 尊重所有贡献者
- 接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

## 开发流程

### 1. 获取任务

1. 从 [Issues](https://github.com/guangda88/zhineng-knowledge-system/issues) 中选择一个任务
2. 或创建新的 Issue 描述你想要实现的功能或修复的bug
3. 等待维护者确认和分配

### 2. 创建分支

```bash
# 确保你的本地仓库是最新状态
git checkout main
git pull origin main

# 创建功能分支
git checkout -b feature/your-feature-name

# 或者创建修复分支
git checkout -b bugfix/your-bugfix-name
```

### 3. 开发

- 遵循[代码规范](#代码规范)
- 编写[测试](#测试要求)
- 更新相关[文档](#文档规范)

### 4. 提交代码

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```bash
git commit -m "feat: 添加用户认证功能"
git commit -m "fix: 修复登录页面的显示问题"
git commit -m "docs: 更新API文档"
```

详见[提交规范](#提交规范)。

### 5. 推送代码

```bash
git push origin feature/your-feature-name
```

### 6. 创建PR

在GitHub上创建Pull Request，使用项目提供的[PR模板](.github/PULL_REQUEST_TEMPLATE.md)。

---

## 分支策略

我们采用 GitFlow 分支管理策略：

```
main (生产环境)
  ↑
  └── develop (开发环境)
        ↑
        ├── feature/* (功能分支)
        ├── bugfix/* (修复分支)
        ├── hotfix/* (紧急修复分支)
        └── release/* (发布分支)
```

### 分支说明

| 分支类型 | 命名规范 | 来源 | 目标 | 说明 |
|---------|---------|------|------|------|
| main | - | develop | - | 生产环境代码，受保护 |
| develop | - | main/* | main | 开发环境代码 |
| feature | feature/* | develop | develop | 新功能开发 |
| bugfix | bugfix/* | develop | develop | bug修复 |
| hotfix | hotfix/* | main | main, develop | 生产紧急修复 |
| release | release/* | develop | main, develop | 发布准备 |

---

## 提交规范

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

### 提交格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug修复 |
| `docs` | 文档更新 |
| `style` | 代码格式调整（不影响功能） |
| `refactor` | 重构（不是新功能也不是修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具变更 |
| `revert` | 回退提交 |

### Scope 范围

常见的 scope 包括：
- `backend` - 后端代码
- `frontend` - 前端代码
- `api` - API相关
- `db` - 数据库相关
- `auth` - 认证授权
- `docs` - 文档
- `ci` - CI/CD相关

### 示例

```bash
# 简单提交
git commit -m "feat: 添加用户注册功能"

# 带范围的提交
git commit -m "feat(auth): 添加OAuth2登录支持"

# 带详细说明的提交
git commit -m "fix(api): 修复用户查询接口的分页问题

修复了当页码超出范围时返回空结果的问题。
现在会自动调整到最后一页。

Closes #123"
```

---

## PR流程

### 1. 创建PR前检查

- [ ] 代码通过所有本地测试
- [ ] 代码通过 flake8 静态检查
- [ ] 提交信息符合规范
- [ ] 代码有适当的注释
- [ ] 更新了相关文档
- [ ] 新功能有对应的测试
- [ ] 测试覆盖率不低于 60%

### 2. 创建PR

1. 在GitHub上创建Pull Request
2. 填写[PR模板](.github/PULL_REQUEST_TEMPLATE.md)中的所有必填项
3. 关联相关的Issue (使用 `Closes #123` 或 `Fixes #123`)
4. 设置适当的标签 (bug, enhancement, documentation等)

### 3. PR审查

- PR会自动通知 CODEOWNERS 文件中定义的审查者
- 至少需要一名审查者批准
- 解决所有审查意见
- 所有CI检查必须通过

### 4. 合并

- 使用 Squash and Merge 方式合并
- 保持提交历史的整洁
- 合并后删除功能分支

---

## 代码规范

### Python (后端)

- 遵循 [PEP 8](https://pep.python.org/pep-0008/) 规范
- 使用 4 空格缩进
- 行长度限制为 100 字符
- 函数和类之间空两行
- 类型注解推荐但不强制

```python
# 良好的示例
def calculate_score(user_id: int, weights: dict[str, float]) -> float:
    """计算用户知识得分。

    Args:
        user_id: 用户ID
        weights: 权重配置

    Returns:
        计算后的得分
    """
    # 实现代码
    pass
```

### JavaScript/TypeScript (前端)

- 遵循 [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
- 使用 2 空格缩进
- 使用 ES6+ 语法
- TypeScript 类型必须定义

```typescript
// 良好的示例
interface UserProps {
  id: number;
  name: string;
  onEdit: (id: number) => void;
}

const UserCard: React.FC<UserProps> = ({ id, name, onEdit }) => {
  return (
    <div className="user-card">
      <h3>{name}</h3>
      <button onClick={() => onEdit(id)}>编辑</button>
    </div>
  );
};
```

### 通用规范

1. **命名规范**
   - 变量/函数: `snake_case` (Python) / `camelCase` (JS)
   - 类: `PascalCase`
   - 常量: `UPPER_SNAKE_CASE`
   - 私有成员: 前缀下划线 `_private`

2. **注释规范**
   - 函数/类必须有文档字符串
   - 复杂逻辑需要行内注释
   - 注释说明"为什么"而不是"是什么"

3. **错误处理**
   - 不要使用裸 `except`
   - 记录适当的错误信息
   - 向上传播需要处理的异常

---

## 测试要求

### 测试覆盖率目标

- 整体代码覆盖率: **>= 60%**
- 核心模块覆盖率: **>= 80%**

### 测试类型

1. **单元测试**: 测试单个函数/方法
2. **集成测试**: 测试模块间交互
3. **E2E测试**: 测试完整用户流程

### 编写测试

```python
# Python单元测试示例
import pytest

def test_user_creation():
    user = User(name="测试用户", email="test@example.com")
    assert user.name == "测试用户"
    assert user.is_active is True

def test_user_creation_invalid_email():
    with pytest.raises(ValidationError):
        User(name="测试", email="invalid-email")
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定文件测试
pytest tests/test_user.py

# 生成覆盖率报告
pytest --cov=backend --cov-report=html --cov-report=term-missing
```

---

## 文档规范

### 代码文档

- 所有公共API必须有文档字符串
- 使用 Google 风格或 NumPy 风格的 docstring
- 复杂算法需要详细注释

### 项目文档

- **README.md**: 项目介绍、快速开始、贡献指南
- **docs/API.md**: API接口文档
- **docs/ARCHITECTURE.md**: 系统架构文档
- **CHANGELOG.md**: 版本变更记录

### 文档更新时机

- 新增功能: 更新API文档和使用示例
- Bug修复: 更新相关文档中的错误描述
- 配置变更: 更新部署文档
- 架构调整: 更新架构文档

---

## CI/CD流程

### CI 工作流

每次 push 或创建 PR 时，会自动触发 CI 检查：

1. **代码质量检查 (flake8)**
   - 检查代码风格是否符合 PEP 8
   - 行长度不超过 100 字符
   - 无语法错误和未使用的导入

2. **单元测试 (pytest)**
   - 运行所有单元测试
   - 生成覆盖率报告
   - 覆盖率目标: 60%

3. **安全扫描 (Bandit)**
   - 检查常见安全问题
   - 生成安全报告

### CI 检查命令

本地运行相同的检查：

```bash
# flake8 代码检查
flake8 . --config=.flake8

# 运行测试并生成覆盖率
pytest tests/ -v --cov=backend --cov-report=term-missing

# 安全扫描
pip install bandit
bandit -r backend/
```

### 状态检查

所有 CI 检查必须通过后，PR 才能合并。检查项包括：
- [ ] Lint 通过 (flake8)
- [ ] 测试通过 (pytest)
- [ ] 覆盖率 >= 60%
- [ ] 安全扫描通过 (可选警告)

---

## 获取帮助

如果你有任何问题：

1. 查看 [Issues](https://github.com/guangda88/zhineng-knowledge-system/issues)
2. 在 [Discussions](https://github.com/guangda88/zhineng-knowledge-system/discussions) 中讨论
3. 联系维护者

---

## 许可证

通过贡献代码，你同意你的贡献将使用项目的 [LICENSE](LICENSE) 进行许可。

---

再次感谢你的贡献！
