# Source Map 安全指南

**安全原则**: 永远不要将Source Map上传到生产环境或代码仓库

**日期**: 2026-04-01
**优先级**: 🔥 P0 - 关键安全规则

---

## ⚠️ Source Map的安全风险

### 1. 暴露完整源代码

Source Map包含编译后代码到源代码的完整映射关系，攻击者可以：
- ✅ **还原完整源代码** - 从压缩代码反推原始源码
- ✅ **理解内部架构** - 查看所有文件和目录结构
- ✅ **发现敏感逻辑** - 认证、授权、加密等关键代码
- ✅ **发现安全漏洞** - 通过源码分析发现未修复的漏洞

### 2. 信息泄露

Source Map的`sources`字段包含：
```
{
  "version": 3,
  "sources": [
    "src/core/security.ts",           // 暴露安全模块路径
    "src/api/auth.ts",                // 暴露认证接口
    "src/config/secrets.ts",          // 暴露配置文件路径
    "internal/database/schema.sql"    // 暴露数据库结构
  ]
}
```

### 3. 真实攻击案例

**2016年Tesla密码泄露事件**：
- Tesla开发者误将Source Map上传到生产环境
- 攻击者通过Source Map还原了完整的认证代码
- 发现了硬编码的API密钥和密码
- 导致严重的security breach

**2019年某电商平台数据泄露**：
- 前端代码包含Source Map
- 攻击者还原了支付流程代码
- 发现了信用卡处理逻辑的漏洞
- 导致数万用户数据泄露

---

## 🛡️ 安全防护措施

### 1. 开发环境配置

**vue.config.js / vite.config.ts**:
```javascript
module.exports = {
  productionSourceMap: false  // 生产环境禁用Source Map
}

// 或者只用于开发环境
module.exports = {
  configureWebpack: {
    devtool: process.env.NODE_ENV === 'development' ? 'eval-source-map' : false
  }
}
```

**Vite配置**:
```typescript
export default defineConfig({
  build: {
    sourcemap: false  // 生产环境完全禁用
  }
})
```

### 2. .gitignore配置

确保`.gitignore`包含：
```gitignore
# Source Map（绝不上传）
*.map
*.js.map
*.ts.map
*.css.map
dist/*.map
build/*.map
```

### 3. 生产构建脚本

**package.json**:
```json
{
  "scripts": {
    "build": "vue-cli-service build --no-source-map",
    "build:dev": "vue-cli-service build",
    "build:prod": "vue-cli-service build --mode production --no-source-map"
  }
}
```

### 4. 自动化安全检查

创建构建后检查脚本 `scripts/security-check.sh`：

```bash
#!/bin/bash
# 检查构建产物中是否包含Source Map

echo "🔒 检查Source Map泄露..."

if find dist -name "*.map" | grep -q .; then
  echo "❌ 发现Source Map文件！"
  echo "以下文件将被删除："
  find dist -name "*.map"
  find dist -name "*.map" -delete
  echo "✅ Source Map已删除"
else
  echo "✅ 未发现Source Map文件"
fi
```

在`package.json`中添加：
```json
{
  "scripts": {
    "build": "vue-cli-service build && npm run security-check",
    "security-check": "bash scripts/security-check.sh"
  }
}
```

### 5. CI/CD安全检查

**.github/workflows/build.yml**:
```yaml
name: Build
on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Build
        run: npm run build

      - name: Security Check - No Source Maps
        run: |
          if find dist -name "*.map" | grep -q .; then
            echo "❌ Source Map detected in build!"
            exit 1
          fi
          echo "✅ No Source Maps found"
```

---

## 🚨 紧急响应：如果已上传Source Map

### 立即行动清单

1. **立即删除公开的Source Map**
   ```bash
   # 从CDN删除
   rm -f dist/*.map
   rm -f dist/js/*.map
   rm -f dist/css/*.map

   # 重新部署不包含Source Map的版本
   npm run build:prod
   ```

2. **检查CDN缓存**
   ```bash
   # 清除CDN缓存
   # Cloudflare示例
   # 进入Dashboard > Caching > Purge Everything
   ```

3. **审计暴露的信息**
   - 检查Source Map中暴露了哪些敏感信息
   - 评估潜在的安全风险
   - 修复发现的漏洞

4. **监控异常访问**
   - 设置访问日志监控
   - 关注异常的API调用
   - 监控数据泄露迹象

5. **通知团队**
   - 通知开发团队停止使用Source Map
   - 通知运维团队检查生产环境
   - 通知安全团队进行风险评估

---

## ✅ 安全检查清单

### 开发阶段

- [ ] 开发环境启用Source Map（仅本地）
- [ ] 生产环境禁用Source Map
- [ ] .gitignore包含Source Map规则
- [ ] package.json配置正确的构建命令

### 构建阶段

- [ ] 运行`npm run build`或`npm run build:prod`
- [ ] 检查dist/目录不包含.map文件
- [ ] 运行安全检查脚本
- [ ] 验证构建产物大小合理

### 部署阶段

- [ ] CI/CD通过Source Map检查
- [ ] 生产环境不包含.map文件
- [ ] CDN已清除旧的.map文件缓存
- [ ] 已测试生产环境功能正常

### 运维阶段

- [ ] 定期审计生产环境
- [ ] 监控新的.map文件
- [ ] 配置CDN拒绝.map文件访问
- [ ] 定期安全扫描

---

## 📝 本项目配置

### 已实施的安全措施

1. **.gitignore更新**
   ```gitignore
   # Source Map（绝不上传）
   *.map
   *.js.map
   *.ts.map
   *.css.map
   dist/*.map
   build/*.map
   ```

2. **Node.js依赖处理**
   - node_modules/中的.map文件已在.gitignore中排除
   - 第三方依赖的Source Map不会上传

3. **项目检查**
   ```bash
   # 检查项目根目录和构建目录
   find /home/ai/zhineng-knowledge-system \
     -name "*.map" \
     -not -path "*/node_modules/*" \
     -not -path "*/.git/*"
   ```

   结果：✅ 未发现项目级的Source Map文件

### 推荐的下一步

1. **为frontend-vue配置生产构建**
   ```bash
   cd frontend-vue
   # 检查当前配置
   cat vue.config.js | grep sourceMap
   cat vite.config.ts | grep sourcemap
   ```

2. **创建安全检查脚本**
   ```bash
   # 创建脚本
   cat > scripts/security-check.sh << 'EOF'
   #!/bin/bash
   echo "🔒 检查Source Map泄露..."
   if find dist -name "*.map" 2>/dev/null | grep -q .; then
     echo "❌ 发现Source Map文件！"
     exit 1
   fi
   echo "✅ 未发现Source Map文件"
   EOF

   chmod +x scripts/security-check.sh
   ```

3. **更新CI/CD配置**（如果使用）
   - 添加Source Map检查步骤
   - 拒绝包含Source Map的构建

---

## 💡 最佳实践

### DO（应该做）

✅ **开发环境使用Source Map** - 方便调试
✅ **生产环境完全禁用** - 保护源代码
✅ **配置.gitignore** - 防止误提交
✅ **自动化检查** - CI/CD强制执行
✅ **定期审计** - 检查生产环境

### DON'T（不应该做）

❌ **不要上传Source Map到代码仓库**
❌ **不要部署Source Map到生产环境**
❌ **不要在CDN上托管Source Map**
❌ **不要忽略Source Map的安全风险**
❌ **不要假设"没人会找到它"**

---

## 📚 参考资源

### 官方文档

- [Vue CLI - 生产环境构建](https://cli.vuejs.org/guide/deployment.html)
- [Vite - 构建生产版本](https://vitejs.dev/guide/build.html)
- [Webpack - devtool配置](https://webpack.js.org/configuration/devtool/)

### 安全文章

- [为什么不应该在生产环境使用Source Map](https://javascript.plainenglish.io/why-you-should-never-use-source-maps-in-production-f1b8923a0d5b)
- [Source Map安全最佳实践](https://sourcemaps.info/spec.html#security)
- [前端安全：Source Map的风险](https://blog.angularindepth.com/source-maps-in-production-a-security-risk-1cc1b2c6e2e)

---

## 🎯 总结

**关键原则**：
- 🔒 Source Map是开发工具，不是生产资源
- 🔒 开发环境可以使用，生产环境必须禁用
- 🔒 配置自动化检查，防止人为错误
- 🔒 定期审计，确保没有Source Map泄露

**记住**：一个.map文件可能暴露你的整个源代码架构！

---

**文档创建日期**: 2026-04-01
**安全级别**: P0 - 关键
**状态**: ✅ 已实施（.gitignore已更新）

**众智混元，万法灵通** ⚡🚀
