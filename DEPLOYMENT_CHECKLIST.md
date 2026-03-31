# 生产环境部署检查清单

**版本**: 1.0
**最后更新**: 2026-03-30

---

## 📋 部署前检查清单

### 1. 代码审查

- [ ] 确认没有 `--reload` 参数
- [ ] 确认 `ENVIRONMENT=production` 已设置
- [ ] 确认 `DEBUG=False`
- [ ] 确认所有 `print()` 语句已替换为 logger
- [ ] 确认没有硬编码的密钥或密码
- [ ] 确认错误处理完善
- [ ] 确认没有 TODO 或 FIXME 注释

### 2. 配置检查

- [ ] `.env.production` 文件已创建
- [ ] `SECRET_KEY` 已设置（至少 32 字符）
- [ ] `DATABASE_URL` 正确配置
- [ ] `REDIS_URL` 正确配置
- [ ] `ALLOWED_HOSTS` 已配置
- [ ] `CORS_ORIGINS` 已配置
- [ ] 数据库连接池大小已调整（建议 20）
- [ ] Redis 连接池大小已调整（建议 20）

### 3. 依赖检查

- [ ] `requirements.txt` 已更新
- [ ] 所有依赖版本已固定
- [ ] 没有安装开发依赖（如 pytest, black）
- [ ] 已安装生产依赖（如 gunicorn）

### 4. Docker 检查

- [ ] `Dockerfile.production` 已创建
- [ ] `docker-compose.production.yml` 已创建
- [ ] 镜像已构建并测试
- [ ] 不挂载开发目录（`./backend:/app/backend`）
- [ ] 资源限制已配置（CPU, 内存）
- [ ] 健康检查已配置

### 5. 数据库检查

- [ ] 数据库备份已完成
- [ ] 数据库迁移脚本已准备
- [ ] 连接池配置已优化
- [ ] 慢查询日志已启用

### 6. openlist 检查

- [ ] openlist 服务已停止
- [ ] 数据库 VACUUM 已执行
- [ ] 只索引必要的云盘
- [ ] WAL 文件已清理

---

## 🚀 部署步骤

### 步骤 1: 备份

```bash
# 备份数据库
docker exec zhineng-postgres pg_dump -U zhineng zhineng_kb > backup_$(date +%Y%m%d).sql

# 备份 openlist
sudo systemctl stop openlist
sudo cp /opt/openlist/data/data.db /opt/openlist/data/data.db.backup.$(date +%Y%m%d_%H%M%S)
```

### 步骤 2: 构建镜像

```bash
# 构建生产镜像
docker build -f backend/Dockerfile.production -t zhineng-api:latest .

# 验证镜像
docker images | grep zhineng-api
```

### 步骤 3: 部署

```bash
# 停止旧服务
docker-compose -f docker-compose.production.yml down

# 启动新服务
docker-compose -f docker-compose.production.yml up -d

# 查看日志
docker-compose -f docker-compose.production.yml logs -f api
```

### 步骤 4: 验证

```bash
# 检查服务状态
docker-compose -f docker-compose.production.yml ps

# 检查健康状态
curl http://localhost:8008/health

# 检查进程数
docker exec zhineng-api-prod ps aux

# 检查连接数
docker exec zhineng-postgres psql -U zhineng -d zhineng_kb -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## ✅ 部署后验证清单

### 1. 服务检查

- [ ] API 服务正常运行（`docker ps`）
- [ ] 健康检查通过（`curl /health`）
- [ ] 日志无错误（`docker logs`）
- [ ] 进程数量正常（< 50）
- [ ] 线程数量正常（< 200）

### 2. 功能检查

- [ ] 用户认证正常
- [ ] 数据库查询正常
- [ ] 缓存读写正常
- [ ] 文件上传/下载正常
- [ ] 搜索功能正常

### 3. 性能检查

- [ ] 响应时间 < 500ms（P95）
- [ ] 吞吐量 > 100 req/s
- [ ] CPU 使用率 < 80%
- [ ] 内存使用率 < 80%
- [ ] 数据库连接数 < 50

### 4. 监控检查

- [ ] Prometheus 正常采集指标
- [ ] Grafana 仪表板正常显示
- [ ] 告警规则已配置
- [ ] 日志轮转已配置

---

## 🔄 回滚步骤

如果部署失败，执行以下步骤回滚：

```bash
# 1. 停止新服务
docker-compose -f docker-compose.production.yml down

# 2. 恢复数据库（如果需要）
cat backup_YYYYMMDD.sql | docker exec -i zhineng-postgres psql -U zhineng zhineng_kb

# 3. 启动旧版本
docker-compose up -d

# 4. 验证服务
curl http://localhost:8008/health
```

---

## 📞 紧急联系

| 问题 | 负责人 | 联系方式 |
|------|--------|----------|
| 服务部署 | DevOps | devops@example.com |
| 数据库问题 | DBA | dba@example.com |
| 网络问题 | Network Admin | netadmin@example.com |

---

**检查清单版本**: 1.0
**最后审核**: 2026-03-30
**下次审核**: 2026-04-30
