# Feature 分支命名规范

本文档定义功能分支的命名规范，确保团队协作的一致性。

## 基本格式

```
<分支类型>/<功能简述>-<编号>
```

## 分支类型前缀

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能开发 | `feature/user-auth-001` |
| `fix/` | Bug修复 | `fix/login-timeout-002` |
| `hotfix/` | 生产紧急修复 | `hotfix/security-patch-003` |
| `refactor/` | 代码重构 | `refactor/cache-layer-004` |
| `docs/` | 文档更新 | `docs/api-guide-005` |
| `test/` | 测试相关 | `test/integration-tests-006` |
| `perf/` | 性能优化 | `perf/query-optimization-007` |
| `release/` | 版本发布 | `release/v1.2.0` |

## 命名规则

### 1. 使用小写字母
```
✅ feature/vector-search-001
❌ feature/VectorSearch-001
```

### 2. 使用连字符分隔单词
```
✅ feature/user-authentication-001
❌ feature/user_authentication_001
```

### 3. 包含任务/Issue编号
```
✅ feature/add-rag-pipeline-123
❌ feature/add-rag-pipeline
```

### 4. 使用描述性名称
```
✅ feature/semantic-search-with-rerank-124
❌ feature/new-search-124
```

### 5. 长度限制
- 分支名总长度不超过 50 字符
- 功能简述不超过 30 字符

## 常见场景示例

### API 开发
```bash
feature/add-chat-endpoint-125
feature/rag-api-refactor-126
feature/multi-domain-support-127
```

### 数据库
```bash
feature/add-vector-index-128
feature/optimize-query-performance-129
feature/migration-script-v2-130
```

### 认证授权
```bash
feature/jwt-refresh-token-131
feature/rbac-permission-system-132
feature/oauth2-integration-133
```

### 缓存
```bash
feature/redis-caching-layer-134
feature/cache-invalidation-strategy-135
```

### 监控
```bash
feature/prometheus-metrics-136
feature/health-check-endpoints-137
feature/logging-improvements-138
```

## Bug修复分支

### 非紧急Bug
```bash
fix/search-result-error-139
fix/database-connection-leak-140
fix/api-response-timeout-141
```

### 生产紧急修复
```bash
hotfix/security-vulnerability-001
hotfix/data-loss-prevention-002
hotfix/critical-memory-leak-003
```

## 重构分支

```bash
refactor/code-structure-142
refactor/remove-deprecated-code-143
refactor/improve-type-hints-144
```

## 文档分支

```bash
docs/update-readme-145
docs/api-documentation-146
docs/deployment-guide-147
```

## 分支创建命令

### 创建功能分支
```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name-<issue-number>
```

### 创建修复分支
```bash
git checkout develop
git pull origin develop
git checkout -b fix/your-fix-name-<issue-number>
```

### 创建热修复分支
```bash
git checkout main
git pull origin main
git checkout -b hotfix/your-hotfix-name-<issue-number>
```

## 分支删除

### 本地删除
```bash
git branch -d feature/your-feature-name-001
```

### 强制删除（未合并）
```bash
git branch -D feature/your-feature-name-001
```

### 远程删除
```bash
git push origin --delete feature/your-feature-name-001
```

## PR 标题规范

PR 标题应与分支名称对应，遵循 Conventional Commits:

```bash
# 分支名
feature/add-semantic-search-148

# PR 标题
feat(search): 添加语义搜索功能
```

## 注意事项

1. **一个分支一个功能**: 保持分支聚焦，避免混合多个不相关的变更
2. **及时同步**: 定期从上游分支同步最新变更
3. **及时清理**: 合并后及时删除已完成的分支
4. **命名清晰**: 好的分支名应该能描述分支的用途
