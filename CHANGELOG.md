# 更新日志 (Changelog)

智能知识系统项目的所有重要变更记录。

格式基于 [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)。

---

## [1.2.0] - 2026-03-29

### Hooks系统实施 - 让规则真正落地

#### 新增 (Added)

**双层Hooks架构** 🛡️
- ✅ Claude Code Hooks (客户端层)
  - 数据库破坏性操作检查Hook
  - 文件删除安全检查Hook
  - Docker Volume删除检查Hook
  - 规则文件修改提醒Hook
  - Git强制操作警告Hook
  - 会话开始规则提醒Hook

- ✅ Backend Hooks (服务端层)
  - AI操作包装器 (AIActionWrapper)
  - 规则修改检查器 (RulesChecker)
  - 紧急问题守卫 (UrgencyGuard)
  - 数据验证门禁 (DataVerificationGate)

**核心机制**
- ✅ 批准令牌机制（有时效性授权）
- ✅ 风险评分机制（智能评估操作风险）
- ✅ 上下文感知（理解环境和意图）
- ✅ 白名单机制（避免过度保护）

**开发规则完善**
- ✅ 新增第4.4节"规则修改流程"
- ✅ 新增第12.1节"数据验证"
- ✅ 新增第13.3节"紧急问题说明"
- ✅ 所有规则与Hooks完全集成

**测试与验证**
- ✅ 14个单元测试（100%通过率）
- ✅ 完整的功能验证
- ✅ 性能测试（响应时间<0.1秒）
- ✅ 用户体验验证

#### 改进 (Improved)

**规则执行**
- ✅ 从"依赖AI记忆"到"自动强制执行"
- ✅ 规则不再流于形式
- ✅ AI无法绕过Hooks检查
- ✅ 保护关键资源（数据库、文件、配置）

**开发流程**
- ✅ 自动化的安全检查
- ✅ 明确的授权机制
- ✅ 清晰的用户指引
- ✅ 完整的审计追踪

#### 文档 (Documentation)

- ✅ COMPREHENSIVE_HOOKS_IMPLEMENTATION_PLAN.md - 综合实施方案
- ✅ HOOKS_IMPLEMENTATION_GUIDE.md - Hooks实施指南
- ✅ HOOKS_IMPLEMENTATION_PHASE1_SUMMARY.md - 阶段1总结
- ✅ HOOKS_IMPLEMENTATION_PHASE234_SUMMARY.md - 第2-4阶段总结
- ✅ DEVELOPMENT_RULES_HOOKS_IMPLEMENTATION_FINAL_PROPOSAL.md - 最终方案

#### 技术细节

**实施统计**
- 创建9个核心脚本（1500+行代码）
- 实现4个Backend组件（400+行代码）
- 编写14个单元测试
- 生成8个详细文档
- 更新3个规则章节

**性能影响**
- Hook响应时间: ~0.05秒
- 对开发效率影响: <1%
- 对系统性能影响: 可忽略

---

## [1.1.0] - 2026-03-25

### 首个正式版本发布

#### 新增 (Added)

**核心功能**
- ✅ FastAPI 后端服务框架
- ✅ PostgreSQL + pgvector 向量数据库
- ✅ Redis 多级缓存系统
- ✅ 领域驱动设计架构

**检索系统**
- ✅ 向量检索（基于 pgvector）
- ✅ BM25 关键词检索
- ✅ 混合检索（RRF 融合）

**智能问答**
- ✅ CoT（链式思考）推理
- ✅ ReAct 推理 + 行动
- ✅ GraphRAG 图推理
- ✅ 自动领域路由

**领域支持**
- ✅ 气功领域
- ✅ 中医领域
- ✅ 儒家领域
- ✅ 通用领域

**安全与认证**
- ✅ JWT 认证系统
- ✅ RBAC 权限控制
- ✅ API 限流
- ✅ 熔断器

**基础设施**
- ✅ Docker Compose 一键部署
- ✅ Nginx 反向代理
- ✅ Prometheus + Grafana 监控
- ✅ CI/CD 流水线配置

#### 安全改进 (Security)

**P0 级安全修复**
- ✅ CORS 配置加固 - 生产环境强制验证
- ✅ 安全响应头中间件（CSP, HSTS, X-Frame-Options）
- ✅ JWT 密钥环境验证 - 生产环境强制要求
- ✅ Referrer-Policy 响应头

#### 文档 (Documentation)

- ✅ README.md 项目说明
- ✅ API 接口文档
- ✅ 部署指南
- ✅ 用户手册
- ✅ 运维手册
- ✅ 开发规则规范
- ✅ Git 远程仓库配置文档
- ✅ V2 代码规范与工程流程审查报告

#### 技术栈

- Python 3.12
- FastAPI 0.115
- PostgreSQL 16 + pgvector
- Redis 7
- Nginx
- Docker & Docker Compose

---

## [1.3.0] - 计划中

### 计划新增 (Planned)

- [ ] 向量检索 API 对接 BGE 嵌入服务
- [ ] 批量文档向量生成
- [ ] 检索结果缓存优化
- [ ] API 响应格式统一
- [ ] 测试覆盖率提升到 70%+

---

## 版本说明

### 语义化版本 (Semantic Versioning)

`v<major>.<minor>.<patch>`

- **major**: 重大变更，不兼容的 API 修改
- **minor**: 新功能，向后兼容
- **patch**: Bug 修复，向后兼容

### 分支策略

```
main (生产分支)
├── develop (开发分支)
│   ├── feature/xxx (功能分支)
│   └── fix/xxx (修复分支)
```

---

**项目地址**: [GitHub](https://github.com/guangda88/zhineng-knowledge-system) | [Gitea](http://zhinenggitea.iepose.cn/guangda/zhineng-knowledge-system)
