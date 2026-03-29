# Git Smart Push - 智能代理推送系统

## 功能说明

自动检测网络连接状况，在推送失败时自动启用代理，推送完成后自动关闭代理。

## 使用方式

### 方式1: Git 命令（推荐）
```bash
# 推送当前分支
git smart-push

# 推送到指定远程
git smart-push github
git smart-push gitea

# 推送指定分支
git smart-push github feature/mvp-textbook-7
```

### 方式2: 直接执行脚本
```bash
./git-smart-push
./git-smart-push github
./git-smart-push github feature-mvp-textbook-7
```

### 方式3: 多仓库同时推送
```bash
# 推送到所有远程仓库
git smart-push
```

## 工作流程

```
1. 检测网络连接
   ├─ 连接正常 → 直接推送 → 完成
   └─ 连接失败 ↓

2. 启动 Clash 代理
   ├─ 启动成功 → 配置 Git 代理 → 推送 → 关闭代理
   └─ 启动失败 → 报错退出
```

## 配置说明

代理配置在 `.git/hooks/smart-push` 脚本中：

```bash
PROXY_HOST="127.0.0.1"
PROXY_PORT="7890"
CLASH_BIN="$HOME/.config/clash/clash"
CLASH_DIR="$HOME/.config/clash"
```

如需修改，编辑该文件。

## 特性

- ✓ 自动检测网络连接
- ✓ 失败时自动启动 Clash 代理
- ✓ 推送完成后自动关闭代理
- ✓ 支持多仓库同时推送
- ✓ 彩色日志输出
- ✓ 错误处理和重试

## 测试

```bash
# 测试当前分支
git smart-push
```

## 故障排查

### 代理启动失败
```bash
# 检查 Clash 文件是否存在
ls -la ~/.config/clash/clash

# 手动启动测试
~/.config/clash/clash -d ~/.config/clash

# 检查端口
ss -tlnp | grep 7890
```

### Git 代理未清除
```bash
# 手动清除
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### Clash 进程未关闭
```bash
# 查找进程
ps aux | grep clash

# 强制关闭
pkill -f clash
```

## 与普通 git push 的区别

| 特性 | git push | git smart-push |
|------|----------|----------------|
| 自动代理 | ❌ | ✅ |
| 网络检测 | ❌ | ✅ |
| 自动清理 | ❌ | ✅ |
| 多仓库 | ❌ | ✅ |
| 彩色日志 | ❌ | ✅ |

## 版本

v1.0.0 - 2026-03-29
