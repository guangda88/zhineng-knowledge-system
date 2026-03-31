# 🚀 安全加固部署指南

**最后更新**: 2026-03-31
**适用版本**: v1.0.0

---

## 📋 部署前检查清单

### 1. 代码修改已应用

```bash
# 验证所有修复已应用
bash scripts/security_check.sh
# 预期输出: ✅ Security checks passed!
```

### 2. 环境准备

```bash
# 检查 JWT 密钥文件
ls -lh jwt_*.pem
# 应该看到:
# jwt_private.pem
# jwt_public.pem

# 如果不存在，运行：
# python3 -c "
# from cryptography.hazmat.primitives.asymmetric import rsa
# from cryptography.hazmat.primitives import serialization
# private_key = rsa.generate_private_key(65537, 2048)
# with open('jwt_private.pem', 'wb') as f:
#     f.write(private_key.private_bytes(
#         encoding=serialization.Encoding.PEM,
#         format=serialization.PrivateFormat.PKCS8,
#         encryption_algorithm=serialization.NoEncryption()
#     ))
# public_key = private_key.public_key()
# with open('jwt_public.pem', 'wb') as f:
#     f.write(public_key.public_bytes(
#         encoding=serialization.Encoding.PEM,
#         format=serialization.PublicFormat.SubjectPublicKeyInfo
#     ))
# print('✅ JWT keys generated')
# "
```

### 3. 环境变量配置

```bash
# 创建环境变量文件
cp .env.production .env

# 生成强密钥
export SECRET_KEY=$(openssl rand -hex 32)

# 编辑 .env 文件，填入真实值
nano .env

# 必须配置的项目:
# ✅ DATABASE_URL - 数据库连接（使用强密码）
# ✅ SECRET_KEY - 应用密钥（至少32字符）
# ✅ ALLOWED_ORIGINS - CORS 白名单
# ✅ JWT_PRIVATE_KEY_PATH - JWT 私钥路径
# ✅ JWT_PUBLIC_KEY_PATH - JWT 公钥路径
```

### 4. 安装 Pre-commit Hook

```bash
# 安装 pre-commit hook
cp .git/hooks/pre-commit.security .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 验证安装
ls -l .git/hooks/pre-commit
```

---

## 🚀 部署步骤

### 步骤 1: 停止当前服务

```bash
# 停止所有服务
docker-compose down

# 等待所有容器停止
docker ps
# 应该看不到 zhineng-* 的容器
```

### 步骤 2: 备份数据（可选但推荐）

```bash
# 备份数据库
docker exec zhineng-postgres pg_dump -U zhineng zhineng_kb > backup_$(date +%Y%m%d).sql

# 备份环境变量
cp .env .env.backup.$(date +%Y%m%d)
```

### 步骤 3: 更新配置

```bash
# 确保环境变量文件存在
if [ ! -f .env ]; then
    echo "❌ .env 文件不存在！"
    echo "请先创建 .env 文件:"
    echo "cp .env.production .env"
    echo "nano .env  # 填入真实值"
    exit 1
fi

# 验证关键配置
if grep -q "CHANGE_THIS" .env; then
    echo "❌ .env 包含默认值，请修改为真实值！"
    exit 1
fi

echo "✅ 配置文件检查通过"
```

### 步骤 4: 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 等待服务启动
sleep 10

# 检查服务状态
docker-compose ps
# 应该看到所有服务都是 "Up" 状态
```

### 步骤 5: 验证部署

```bash
# 1. 检查健康端点
curl http://localhost:8000/health
# 预期: {"status":"ok"}

# 2. 检查数据库
docker exec zhineng-postgres pg_isready -U zhineng
# 预期: 返回 "accepting connections"

# 3. 检查日志
docker-compose logs --tail=50 api
# 应该看到 "FastAPI application initialized with security enhancements"

# 4. 测试速率限制
curl -I http://localhost:8000/health
# 应该看到速率限制响应头

# 5. 检查资源限制
docker stats --no-stream
# 应该看到所有容器都有资源限制
```

---

## 🔒 安全验证测试

### 测试 1: JWT 认证

```bash
# 1. 登录获取令牌
TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}' \
  | jq -r '.access_token')

# 2. 使用令牌访问受保护的端点
curl http://localhost:8000/api/v2/user/profile \
  -H "Authorization: Bearer $TOKEN"
# 预期: 返回用户信息

# 3. 测试无效令牌
curl http://localhost:8000/api/v2/user/profile \
  -H "Authorization: Bearer invalid_token"
# 预期: 401 Unauthorized
```

### 测试 2: 输入验证

```bash
# 测试 XSS 防护
curl -X POST http://localhost:8000/api/v2/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"<script>alert(1)</script>","content":"test"}'
# 预期: 400 Bad Request - suspicious content

# 测试 SQL 注入防护
curl -X POST http://localhost:8000/api/v2/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"Test OR 1=1","content":"test"}'
# 预期: 400 Bad Request 或被清理
```

### 测试 3: 速率限制

```bash
# 快速发送多个请求
for i in {1..70}; do
  curl -s http://localhost:8000/health &
done
wait

# 应该看到一些请求返回 429
```

### 测试 4: CORS 配置

```bash
# 从不允许的来源测试
curl -X OPTIONS http://localhost:8000/health \
  -H "Origin: http://evil.com" \
  -H "Access-Control-Request-Method: GET"
# 预期: CORS 错误或无 Access-Control-Allow-Origin 头
```

---

## 📊 监控配置

### 配置 Crontab 监控任务

```bash
# 编辑 crontab
crontab -e

# 添加以下任务：
*/10 * * * * cd /home/ai/zhineng-knowledge-system && bash scripts/emergency_memory_recovery.sh >> logs/emergency_recovery.log 2>&1
0 * * * * cd /home/ai/zhineng-knowledge-system && bash scripts/monitor_disk.sh >> logs/monitor_disk.log 2>&1
*/30 * * * * cd /home/ai/zhineng-knowledge-system && bash scripts/monitor_docker.sh >> logs/monitor_docker.log 2>&1
0 9 * * * cd /home/ai/zhineng-knowledge-system && bash scripts/daily_health_check.sh >> logs/daily_health.log 2>&1
0 0 * * 0 cd /home/ai/zhineng-knowledge-system && bash scripts/weekly_capacity_review.sh >> logs/weekly_capacity.log 2>&1

# 保存并退出
```

### 验证监控任务

```bash
# 查看已配置的任务
crontab -l

# 手动运行一次测试
bash scripts/emergency_memory_recovery.sh
bash scripts/monitor_disk.sh
```

---

## 🎯 性能优化建议

### 1. 数据库连接池优化

```python
# 已在 backend/main_optimized.py 中配置
pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=2,    # 最小连接数
    max_size=10,    # 最大连接数
    command_timeout=60
)
```

### 2. Redis 缓存优化

```python
# 启用缓存
from cache.decorators import cached_api_domain_stats

@cached_api_domain_stats(ttl=600)  # 缓存10分钟
async def get_domain_stats(domain_name: str):
    # ... 获取统计数据
    pass
```

### 3. 日志轮转

```bash
# 创建日志轮转配置
cat > /etc/logrotate.d/zhineng-knowledge-system << 'EOF'
/home/ai/zhineng-knowledge-system/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ai ai
}
EOF

# 测试配置
sudo logrotate -d /etc/logrotate.d/zhineng-knowledge-system
```

---

## 🚨 故障排查

### 问题 1: 服务启动失败

```bash
# 查看日志
docker-compose logs api

# 常见原因：
# 1. DATABASE_URL 未配置或错误
# 2. JWT 密钥文件不存在
# 3. 端口被占用

# 解决方法：
# 1. 检查 .env 文件
# 2. 生成 JWT 密钥
# 3. 修改 .env 中的 API_PORT
```

### 问题 2: JWT 认证失败

```bash
# 检查密钥文件
ls -l jwt_*.pem

# 检查配置
grep JWT .env

# 重新生成密钥（如果需要）
python3 -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
private_key = rsa.generate_private_key(65537, 2048)
with open('jwt_private.pem', 'wb') as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))
public_key = private_key.public_key()
with open('jwt_public.pem', 'wb') as f:
    f.write(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))
print('✅ JWT keys regenerated')
"

# 重启服务
docker-compose restart api
```

### 问题 3: 速率限制不工作

```bash
# 检查中间件是否加载
grep RateLimitMiddleware backend/main.py

# 检查配置
grep RATE_LIMIT .env

# 查看日志
docker-compose logs api | grep -i rate
```

### 问题 4: 磁盘空间不足

```bash
# 检查磁盘使用
df -h /

# 运行清理脚本
bash scripts/cleanup_disk_space.sh

# 如果还是不足，检查日志文件
du -sh logs/* | sort -rh | head -5

# 清理旧日志
find logs/ -name "*.log" -mtime +7 -delete
```

---

## 📞 支持和帮助

### 文档资源

1. **安全审查报告**: `COMPREHENSIVE_SECURITY_AUDIT_REPORT.md`
2. **预防机制文档**: `SECURITY_PREVENTION_MECHANISMS.md`
3. **完成报告**: `SECURITY_HARDENING_COMPLETION_REPORT.md`

### 快速参考

```bash
# 安全检查
bash scripts/security_check.sh

# 健康检查
bash scripts/daily_health_check.sh

# 内存恢复
bash scripts/emergency_memory_recovery.sh

# 查看日志
docker-compose logs -f --tail=100 api
```

---

## ✅ 部署成功标准

### 所有检查项通过

- [ ] 安全检查脚本通过
- [ ] JWT 密钥文件存在
- [ ] 环境变量配置正确
- [ ] 所有服务启动成功
- [ ] 健康检查返回 200
- [ ] JWT 认证工作正常
- [ ] 速率限制已启用
- [ ] 监控任务已配置
- [ ] 磁盘空间充足 (< 50%)
- [ ] 日志正常输出

### 性能指标正常

- [ ] API 响应时间 < 1s
- [ ] 内存使用率 < 70%
- [ ] 磁盘使用率 < 50%
- [ ] 容器资源限制生效

---

**部署指南版本**: 1.0
**最后更新**: 2026-03-31
**维护人员**: Claude Code
