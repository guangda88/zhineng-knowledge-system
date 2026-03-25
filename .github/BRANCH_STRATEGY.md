# Git 分支策略

本文档定义智能知识系统的Git分支管理策略。

## 分支结构

```
main (生产分支，稳定版本)
  ↑
develop (开发分支，集成测试)
  ↑
feature/xxx (功能分支)
fix/xxx (修复分支)
```

## 分支说明

### main 分支
- **用途**: 生产环境分支，保持稳定可发布状态
- **保护规则**:
  - 禁止直接推送
  - 需要Pull Request合并
  - 需要至少1个审查批准
  - 需要通过CI检查
- **合并来源**: 仅接受来自 `develop` 分支的PR

### develop 分支
- **用途**: 开发集成分支，包含下一个版本的最新开发成果
- **保护规则**:
  - 需要Pull Request合并
  - 需要通过CI检查
- **合并来源**: 接受来自 `feature/*` 和 `fix/*` 的PR

### feature/* 分支
- **用途**: 新功能开发
- **命名规范**: `feature/<功能描述>`
- **创建来源**: 从 `develop` 创建
- **合并目标**: 开发完成后PR回 `develop`
- **生命周期**: 合并后可删除

### fix/* 分支
- **用途**: Bug修复
- **命名规范**: `fix/<问题描述>`
- **创建来源**: 从 `develop` 创建
- **合并目标**: 修复完成后PR回 `develop`
- **生命周期**: 合并后可删除

## 工作流程

### 1. 开发新功能
```bash
# 从develop创建feature分支
git checkout develop
git pull origin develop
git checkout -b feature/添加向量检索功能

# 开发并提交
git add .
git commit -m "feat: 添加向量检索功能"

# 推送到远程
git push -u origin feature/添加向量检索功能

# 创建PR到develop
```

### 2. 修复Bug
```bash
# 从develop创建fix分支
git checkout develop
git pull origin develop
git checkout -b fix/修复搜索超时问题

# 修复并提交
git add .
git commit -m "fix: 修复搜索超时问题"

# 推送到远程
git push -u origin fix/修复搜索超时问题

# 创建PR到develop
```

### 3. 发布到生产
```bash
# 从develop创建release分支
git checkout develop
git pull origin develop
git checkout -b release/v1.2.0

# 进行发布准备（版本号更新、CHANGELOG更新等）
git commit -m "chore: 准备v1.2.0发布"

# 合并到main
git checkout main
git merge --no-ff release/v1.2.0
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin main --tags

# 合并回develop
git checkout develop
git merge --no-ff release/v1.2.0
git push origin develop

# 删除release分支
git branch -d release/v1.2.0
```

## Conventional Commits 规范

所有提交消息必须遵循以下格式:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具相关
- `ci`: CI配置

### Scope 范围
常见范围: `api`, `database`, `auth`, `cache`, `monitoring`, `ui`

### 示例
```bash
feat(api): 添加向量搜索端点
fix(database): 修复连接池泄漏问题
docs(readme): 更新安装说明
perf(cache): 优化Redis缓存策略
```

## 分支保护规则

### main 分支
| 规则 | 状态 |
|------|------|
| 禁止直接推送 | ✅ |
| 要求PR审查 | ✅ (1人) |
| 要求状态检查通过 | ✅ |
| 要求分支最新 | ✅ |

### develop 分支
| 规则 | 状态 |
|------|------|
| 要求PR审查 | ✅ (1人) |
| 要求状态检查通过 | ✅ |
| 要求分支最新 | ✅ |

## 版本号规范

遵循语义化版本 (Semantic Versioning): `MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的API变更
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的Bug修复

示例: `v1.2.3`
