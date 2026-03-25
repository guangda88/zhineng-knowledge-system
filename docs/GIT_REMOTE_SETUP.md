# 智能知识系统 - Git 远程仓库配置

**更新日期**: 2026-03-25
**版本**: v1.1.0

---

## 远程仓库配置

### 仓库地址

| 仓库名称 | 平台 | 地址 |
|----------|------|------|
| github | GitHub | https://github.com/guangda88/zhineng-knowledge-system.git |
| gitea | Gitea | http://zhinenggitea.iepose.cn/guangda/zhineng-knowledge-system.git |

### 当前配置

```bash
$ git remote -v
github  https://github.com/guangda88/zhineng-knowledge-system.git (fetch)
github  https://github.com/guangda88/zhineng-knowledge-system.git (push)
gitea   http://zhinenggitea.iepose.cn/guangda/zhineng-knowledge-system.git (fetch)
gitea   http://zhinenggitea.iepose.cn/guangda/zhineng-knowledge-system.git (push)
```

### 配置命令

```bash
# 添加 GitHub 远程仓库
git remote add github https://github.com/guangda88/zhineng-knowledge-system.git

# 添加 Gitea 远程仓库
git remote add gitea http://zhinenggitea.iepose.cn/guangda/zhineng-knowledge-system.git
```

---

## 双仓库推送流程

### 标准推送命令

```bash
# 推送到 GitHub
git push github main --tags

# 推送到 Gitea
git push gitea main --tags
```

### 代理配置

由于网络原因，推送到 GitHub 需要使用 Clash 代理：

```bash
# 方法一：使用环境变量（推荐）
export all_proxy=socks5://127.0.0.1:7891
git push github main --tags
unset all_proxy

# 方法二：配置 Git 代理（临时）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
git push github main --tags
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### 代理端口说明

| 服务 | 地址 | 用途 |
|------|------|------|
| Clash HTTP | 127.0.0.1:7890 | HTTP/HTTPS 代理 |
| Clash SOCKS5 | 127.0.0.1:7891 | SOCKS5 代理 |

---

## v1.1.0 发布过程

### 发布时间线

| 时间 | 操作 | 状态 |
|------|------|------|
| 2026-03-25 | 初始化 Git 仓库 | ✅ |
| 2026-03-25 | 创建 main/develop 分支 | ✅ |
| 2026-03-25 | 完成首次提交 | ✅ |
| 2026-03-25 | 完成安全修复提交 | ✅ |
| 2026-03-25 | 创建 v1.1.0 标签 | ✅ |
| 2026-03-25 | 推送到 Gitea | ✅ |
| 2026-03-25 | 推送到 GitHub (需代理) | ✅ |

### 推送过程记录

#### 1. 初期尝试（失败）

```bash
# 直接推送失败 - 网络连接问题
git push github main --tags
# fatal: 无法访问 'https://github.com/...'：Failed to connect to github.com port 443
```

#### 2. 尝试 HTTP 代理（失败）

```bash
export http_proxy=http://127.0.0.1:7890
git push github main --tags
# fatal: Recv failure: 连接被对方重置
```

#### 3. 尝试 SOCKS5 代理（成功）

```bash
export all_proxy=socks5://127.0.0.1:7891
git push github main --tags
# 成功！
```

### 最终成功的命令

```bash
# 推送到 Gitea（无需代理）
git push gitea main --tags

# 推送到 GitHub（使用 SOCKS5 代理）
export all_proxy=socks5://127.0.0.1:7891
git push github main --tags
unset all_proxy
```

---

## 分支策略

```
main (生产分支)
├── develop (开发分支)
│   ├── feature/xxx (功能分支)
│   └── fix/xxx (修复分支)
```

### 发布流程

```bash
# 1. 在 develop 分支开发
git checkout develop

# 2. 完成功能后提交
git add .
git commit -m "feat: xxx"

# 3. 合并到 main
git checkout main
git merge develop

# 4. 创建版本标签
git tag -a v1.2.0 -m "Release v1.2.0"

# 5. 推送到双仓库
export all_proxy=socks5://127.0.0.1:7891
git push github main --tags
git push gitea main --tags
unset all_proxy
```

---

## 提交规范

遵循 Conventional Commits 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

| Type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档更新 |
| style | 代码格式调整 |
| refactor | 重构 |
| test | 测试相关 |
| chore | 构建/工具链 |
| security | 安全相关 |

### 示例

```
feat(retrieval): 添加向量检索API

- 实现 /api/search/vector 端点
- 集成 BGE 嵌入服务
- 添加单元测试

Closes #123
```

---

## 版本标签规范

采用语义化版本 (Semantic Versioning)：`v<major>.<minor>.<patch>`

- **major**: 重大变更，不兼容的 API 修改
- **minor**: 新功能，向后兼容
- **patch**: Bug 修复，向后兼容

### 创建标签

```bash
# 轻量标签
git tag v1.1.0

# 附注标签（推荐）
git tag -a v1.1.0 -m "Release v1.1.0: 描述内容"
```

### 推送标签

```bash
# 推送单个标签
git push github v1.1.0

# 推送所有标签
git push github --tags
```

---

## 常见问题

### Q: GitHub 推送失败？

A: 确认 Clash 代理正在运行，然后使用：

```bash
export all_proxy=socks5://127.0.0.1:7891
git push github main
unset all_proxy
```

### Q: 如何验证推送成功？

A: 查看远程标签：

```bash
git ls-remote --tags github
git ls-remote --tags gitea
```

### Q: 代理端口不通？

A: 检查 Clash 是否运行：

```bash
nc -zv 127.0.0.1 7891
curl -x socks5://127.0.0.1:7891 https://github.com
```

---

## GitHub Release 创建

由于 `gh` CLI 未安装，需要手动创建 Release：

1. 访问：https://github.com/guangda88/zhineng-knowledge-system/releases/new
2. 选择标签：`v1.1.0`
3. 标题：`v1.1.0 - 智能知识系统首个正式版本`
4. 复制发布说明（见下方模板）

### Release 说明模板

```markdown
# 智能知识系统 v1.1.0

> 基于RAG的气功、中医、儒家智能知识问答系统

## ✨ 功能特性

- FastAPI 后端服务
- 向量检索 (pgvector)
- 混合检索 (向量 + BM25)
- RAG 问答 (CoT/ReAct/GraphRAG)
- JWT + RBAC 认证

## 🔒 安全改进

- CORS 配置加固
- 安全响应头
- JWT 密钥验证

## 🚀 快速开始

\`\`\`bash
git clone https://github.com/guangda88/zhineng-knowledge-system.git
cd zhineng-knowledge-system
docker-compose up -d
\`\`\`
```

---

**最后更新**: 2026-03-25
