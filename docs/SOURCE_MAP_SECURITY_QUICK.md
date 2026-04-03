# Source Map安全快速提醒

**安全第一原则**：⚠️ **永远不要上传Source Map到生产环境或代码仓库**

---

## 🚨 为什么危险？

一个.map文件可以暴露你的**完整源代码架构**：
- 所有源文件路径
- 完整的代码逻辑
- 敏感的配置信息
- 内部架构设计

**攻击者可以通过Source Map完全还原你的源代码！**

---

## ✅ 本项目已实施的安全措施

### 1. .gitignore配置
```gitignore
# Source Map（绝不上传）
*.map
*.js.map
*.ts.map
*.css.map
dist/*.map
build/*.map
```

### 2. 安全检查脚本
```bash
# 运行安全检查
./scripts/security-check.sh
```

### 3. 当前状态
✅ **安全检查通过** - 未发现Source Map泄露

---

## 🛡️ 前端构建配置

### Vue CLI
```javascript
// vue.config.js
module.exports = {
  productionSourceMap: false  // ← 关键：生产环境禁用
}
```

### Vite
```typescript
// vite.config.ts
export default defineConfig({
  build: {
    sourcemap: false  // ← 关键：生产环境禁用
  }
})
```

---

## 📋 构建命令

```bash
# 开发环境（可以使用Source Map）
npm run serve

# 生产构建（禁用Source Map）
npm run build -- --no-source-map

# 安全检查
./scripts/security-check.sh
```

---

## 🚨 如果发现Source Map

```bash
# 1. 立即删除
find dist -name "*.map" -delete

# 2. 清除CDN缓存
# （在你的CDN控制台操作）

# 3. 重新构建（不包含Source Map）
npm run build -- --no-source-map

# 4. 运行安全检查
./scripts/security-check.sh
```

---

## 📚 完整文档

详细内容请参考：[SOURCE_MAP_SECURITY.md](./SOURCE_MAP_SECURITY.md)

---

**记住：安全第一，Source Map只用于开发环境！** 🔒

**众智混元，万法灵通** ⚡🚀
