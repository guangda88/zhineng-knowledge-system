# 部署日志模板

## 部署信息

| 项目 | 内容 |
|------|------|
| **部署ID** | DEPLOY-YYYYMMDD-HHMMSS |
| **部署类型** | 📋 [ ] 标准部署  [ ] 零停机部署  [ ] 回滚  [ ] 紧急修复 |
| **执行人** | 姓名 |
| **开始时间** | YYYY-MM-DD HH:MM:SS |
| **结束时间** | YYYY-MM-DD HH:MM:SS |
| **总耗时** | X 分钟 |

## 部署前检查

### 系统环境

- [ ] Docker版本: `docker --version`
- [ ] Docker Compose版本: `docker-compose --version`
- [ ] 磁盘空间: `df -h`
- [ ] 内存使用: `free -h`
- [ ] CPU负载: `uptime`

### 服务状态

- [ ] postgres: 运行中 / 停止
- [ ] redis: 运行中 / 停止
- [ ] api: 运行中 / 停止
- [ ] nginx: 运行中 / 停止

### 备份验证

- [ ] 最近备份时间:
- [ ] 备份文件: `./scripts/deploy_backup.sh list`
- [ ] 备份完整性: 已验证

## 部署步骤

### 1. 预部署备份

```bash
./scripts/deploy_backup.sh pre-deploy
```

**结果**: ✅ 成功 / ❌ 失败

**备份文件**:
- 数据库: `db_YYYYMMDD_HHMMSS.sql.gz`
- 配置: `config_YYYYMMDD_HHMMSS.tar.gz`
- 数据: `data_YYYYMMDD_HHMMSS.tar.gz`

### 2. 代码更新

```bash
git pull origin main
git log -1 --oneline
```

**最新提交**: commit_hash - commit_message

**结果**: ✅ 成功 / ❌ 失败

### 3. 配置更新

- [ ] .env 文件更新
- [ ] docker-compose.yml 更新
- [ ] nginx配置更新

**变更说明**:


### 4. 镜像构建

```bash
docker-compose build
```

**构建时间**: X 分钟

**结果**: ✅ 成功 / ❌ 失败

### 5. 服务启动

```bash
docker-compose up -d
```

**启动容器**:
- zhineng-postgres: ✅ / ❌
- zhineng-redis: ✅ / ❌
- zhineng-api: ✅ / ❌
- zhineng-nginx: ✅ / ❌

### 6. 健康检查

```bash
./scripts/health_check.sh
```

**检查结果**:
- 容器状态: ✅ 通过 / ❌ 失败
- 数据库连接: ✅ 通过 / ❌ 失败
- API服务: ✅ 通过 / ❌ 失败
- 前端服务: ✅ 通过 / ❌ 失败

**详细输出**:
```
# 粘贴健康检查输出
```

### 7. 版本快照

```bash
./scripts/rollback.sh create
```

**版本号**: v_YYYYMMDD_HHMMSS

## 部署结果

### 状态汇总

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 备份创建 | ✅ / ❌ | |
| 代码更新 | ✅ / ❌ | |
| 镜像构建 | ✅ / ❌ | |
| 服务启动 | ✅ / ❌ | |
| 健康检查 | ✅ / ❌ | |
| 版本快照 | ✅ / ❌ | |

**总体结果**: ✅ 成功 / ❌ 失败 / ⚠️ 部分成功

### 服务访问

- 前端: http://localhost:8008
- API: http://localhost:8001
- Grafana: http://localhost:3000

### 问题记录

| 问题 | 严重程度 | 解决方案 | 状态 |
|------|----------|----------|------|
| |  [ ] 高  [ ] 中  [ ] 低 | | [ ] 已解决  [ ] 跟踪中 |

## 回滚信息（如需要）

### 回滚原因


### 回滚步骤

```bash
./scripts/rollback.sh rollback <version>
```

### 回滚结果

- [ ] 回滚成功
- [ ] 服务恢复正常
- [ ] 健康检查通过

## 备注



## 签名

**执行人**: ________________ 日期: ________

**审核人**: ________________ 日期: ________

---

## 附：命令输出日志

### 备份输出
\`\`\`
./scripts/deploy_backup.sh pre-deploy
# 粘贴输出
\`\`\`

### 构建输出
\`\`\`
docker-compose build
# 粘贴输出
\`\`\`

### 启动输出
\`\`\`
docker-compose up -d
# 粘贴输出
\`\`\`

### 健康检查输出
\`\`\`
./scripts/health_check.sh
# 粘贴输出
\`\`\`
