# 问题排查报告：zhinengAI jdxb 服务和 100.66.1.X 网段

报告时间: $(date '+%Y-%m-%d %H:%M:%S')

---

## 🚨 问题描述

1. **zhinengAI 的 jdxb 服务没有启动**
2. **100.66.1.X 网段不通**

---

## 📋 问题1：jdxb 服务未启动

### 服务信息

| 项目 | 配置 |
|------|------|
| **服务名称** | jdxb (owjdxb) |
| **容器名称** | owjdxb |
| **镜像名称** | ionewu/owjdxb:latest |
| **镜像大小** | 73.8MB |
| **网络模式** | host |
| **监听端口** | 9118 |
| **访问地址** | http://192.168.2.1:9118 |
| **状态** | ❌ 未启动（文档显示运行中，但用户报告未启动）|

### 服务详情

根据文档，该服务是一个独立的 Docker 容器，用于 IEPOSE 相关功能。

**镜像下载地址**: https://cdn.ionewu.com/upgrade/jdxb/x64/owjdxb_x64.img.tgz

### 排查步骤

#### 1. 检查容器状态

```bash
# 查看容器状态
docker ps -a | grep owjdxb

# 如果容器不存在，需要重新拉取镜像并运行
docker pull ionewu/owjdxb:latest

# 运行容器
docker run -d \
  --name owjdxb \
  --network host \
  ionewu/owjdxb:latest

# 或者使用 host 网络模式
docker run -d \
  --name owjdxb \
  --net host \
  ionewu/owjdxb:latest
```

#### 2. 检查容器日志

```bash
# 查看容器日志
docker logs owjdxb

# 查看最近的50行日志
docker logs --tail 50 owjdxb

# 实时查看日志
docker logs -f owjdxb
```

#### 3. 重启容器

```bash
# 重启容器
docker restart owjdxb

# 查看重启后的状态
docker ps | grep owjdxb
```

#### 4. 检查端口占用

```bash
# 检查9118端口是否被占用
netstat -tuln | grep 9118

# 或者使用 ss 命令
ss -tuln | grep 9118
```

#### 5. 访问服务

```bash
# 测试服务是否可访问
curl http://192.168.2.1:9118

# 或者使用浏览器访问
# http://192.168.2.1:9118
```

### 可能的问题和解决方案

#### 问题1: 容器不存在

**原因**: 容器被删除或从未创建

**解决方案**:
```bash
# 拉取镜像
docker pull ionewu/owjdxb:latest

# 运行容器
docker run -d \
  --name owjdxb \
  --net host \
  ionewu/owjdxb:latest

# 验证容器状态
docker ps | grep owjdxb
```

#### 问题2: 容器启动失败

**原因**: 配置错误、依赖问题或镜像问题

**解决方案**:
```bash
# 查看容器日志
docker logs owjdxb

# 如果容器存在但未运行，删除并重新创建
docker rm -f owjdxb
docker run -d \
  --name owjdxb \
  --net host \
  ionewu/owjdxb:latest
```

#### 问题3: 端口冲突

**原因**: 9118 端口被其他服务占用

**解决方案**:
```bash
# 查找占用9118端口的进程
sudo lsof -i :9118

# 如果有其他进程占用，停止该进程或更换端口

# 或者使用不同的端口运行容器
docker run -d \
  --name owjdxb \
  -p 9119:9118 \
  ionewu/owjdxb:latest
```

#### 问题4: 镜像拉取失败

**原因**: 网络问题、镜像仓库问题或认证问题

**解决方案**:
```bash
# 检查网络连接
ping cdn.ionewu.com

# 手动下载镜像
wget https://cdn.ionewu.com/upgrade/jdxb/x64/owjdxb_x64.img.tgz

# 解压镜像
tar -xzf owjdxb_x64.img.tgz

# 加载镜像
docker load < owjdxb_x64.img

# 运行容器
docker run -d \
  --name owjdxb \
  --net host \
  ionewu/owjdxb:latest
```

### 自动启动配置

为了确保容器在系统重启后自动启动，可以使用以下命令：

```bash
# 设置容器自动重启
docker update --restart=unless-stopped owjdxb

# 验证配置
docker inspect owjdxb | grep -A 10 RestartPolicy
```

### Docker Compose 配置（可选）

如果希望将 jdxb 服务纳入 Docker Compose 管理，可以创建一个独立的 `docker-compose.jdxb.yml` 文件：

```yaml
version: '3.8'

services:
  jdxb:
    image: ionewu/owjdxb:latest
    container_name: owjdxb
    network_mode: host
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9118"]
      interval: 30s
      timeout: 10s
      retries: 3
```

使用方法：
```bash
# 启动服务
docker-compose -f docker-compose.jdxb.yml up -d

# 查看状态
docker-compose -f docker-compose.jdxb.yml ps

# 查看日志
docker-compose -f docker-compose.jdxb.yml logs -f

# 停止服务
docker-compose -f docker-compose.jdxb.yml down
```

---

## 🌐 问题2：100.66.1.X 网段不通

### 网络拓扑

```
192.168.2.0/24 (本地局域网)
  ├─ 主节点: 192.168.2.1 (ZboxEN1070K)
  ├─ 次节点: 192.168.2.10 (备用Zbox)
  └─ 存储服务器: 192.168.2.1 (EN51660T-C)

100.66.1.0/24 (远程网段) - Dell R730
  └─ 远程备份节点: 100.66.1.7

10.0.0.0/24 (虚拟内网) - WireGuard VPN
  ├─ 主节点: 10.0.0.1 (ZboxEN1070K)
  ├─ 次节点: 10.0.0.2 (备用Zbox)
  └─ 远程备份节点: 10.0.0.3 (Dell R730)
```

### 连接信息

| 项目 | 配置 |
|------|------|
| **远程IP** | 100.66.1.7 |
| **虚拟IP** | 10.0.0.3 |
| **SSH端口** | 2222 |
| **SSH用户** | adminliuqing / ai |
| **SSH密钥** | ~/.ssh/id_rsa_dell |

### 排查步骤

#### 1. 检查本地网络连接

```bash
# 检查本地网络接口
ip addr show

# 检查路由表
ip route show

# 检查到100.66.1.7的路由
ip route get 100.66.1.7
```

#### 2. 检查VPN连接

```bash
# 检查WireGuard接口
ip link show wg0

# 检查WireGuard状态
sudo wg show

# 如果接口不存在，启动WireGuard
sudo wg-quick up wg0

# 检查VPN连接
ping 10.0.0.3
```

#### 3. 测试远程连接

```bash
# 测试SSH连接
ssh -p 2222 -i ~/.ssh/id_rsa_dell ai@100.66.1.7 "echo 'Connection successful'"

# 测试SSH连接（使用虚拟IP）
ssh -i ~/.ssh/id_rsa_dell ai@10.0.0.3 "echo 'Connection successful'"
```

#### 4. 检查防火墙规则

```bash
# 检查iptables规则
sudo iptables -L -n -v

# 检查ufw状态（如果使用）
sudo ufw status

# 检查WireGuard相关的防火墙规则
sudo iptables -L FORWARD -n -v | grep wg0
```

#### 5. 检查DNS解析

```bash
# 检查DNS解析
nslookup 100.66.1.7

# 或使用 dig
dig 100.66.1.7
```

### 可能的问题和解决方案

#### 问题1: VPN未建立

**原因**: WireGuard 服务未启动、配置错误或网络问题

**解决方案**:
```bash
# 检查WireGuard配置文件
sudo cat /etc/wireguard/wg0.conf

# 启动WireGuard
sudo wg-quick up wg0

# 设置开机自启动
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0

# 检查状态
sudo wg show

# 测试连接
ping 10.0.0.3
```

#### 问题2: 静态路由未配置

**原因**: 没有配置到100.66.1.0/24的静态路由

**解决方案**:
```bash
# 添加静态路由
sudo ip route add 100.66.1.0/24 via 192.168.2.1

# 临时添加（重启后失效）
sudo route add -net 100.66.1.0/24 gw 192.168.2.1

# 永久添加（Ubuntu/Debian）
echo "100.66.1.0/24 via 192.168.2.1" | sudo tee -a /etc/network/interfaces.d/static-routes

# 永久添加（使用netplan）
sudo nano /etc/netplan/01-static-routes.yaml
```

添加以下内容：
```yaml
network:
  version: 2
  ethernets:
    eth0:
      routes:
        - to: 100.66.1.0/24
          via: 192.168.2.1
```

应用配置：
```bash
sudo netplan apply
```

#### 问题3: 防火墙阻止连接

**原因**: 防火墙规则阻止了到100.66.1.X网段的连接

**解决方案**:
```bash
# 临时关闭防火墙（仅用于测试）
sudo ufw disable

# 或添加防火墙规则允许连接
sudo ufw allow from 100.66.1.0/24 to any
sudo ufw allow to 100.66.1.0/24 from any

# 重新启用防火墙
sudo ufw enable

# 或者使用iptables直接添加规则
sudo iptables -A INPUT -s 100.66.1.0/24 -j ACCEPT
sudo iptables -A OUTPUT -d 100.66.1.0/24 -j ACCEPT
```

#### 问题4: 远程服务器未启动

**原因**: Dell R730 服务器未启动或网络问题

**解决方案**:
```bash
# 检查远程服务器是否在线
ping 100.66.1.7

# 如果ping不通，需要检查：
# 1. 远程服务器是否启动
# 2. 远程服务器的网络连接
# 3. 中间路由器/防火墙的配置
# 4. ISP连接状态

# 联系远程服务器管理员确认服务器状态
```

#### 问题5: SSH密钥问题

**原因**: SSH密钥未正确配置或权限问题

**解决方案**:
```bash
# 检查SSH密钥权限
ls -la ~/.ssh/id_rsa_dell*

# 修复权限
chmod 600 ~/.ssh/id_rsa_dell
chmod 644 ~/.ssh/id_rsa_dell.pub

# 测试SSH连接
ssh -p 2222 -i ~/.ssh/id_rsa_dell -v ai@100.66.1.7

# 如果密钥不存在，生成新的SSH密钥
ssh-keygen -t ed25519 -f ~/.ssh/id_rsa_dell -C "ai@zhineng"

# 复制公钥到远程服务器
ssh-copy-id -i ~/.ssh/id_rsa_dell.pub -p 2222 ai@100.66.1.7
```

### VPN配置参考

#### 主节点 (ZboxEN1070K) - WireGuard Server

```bash
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <主节点私钥>
Address = 10.0.0.1/24
ListenPort = 51820
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
# Dell R730
PublicKey = <Dell公钥>
AllowedIPs = 10.0.0.3/32,100.66.1.0/24
Endpoint = 100.66.1.7:51820
PersistentKeepalive = 25
```

#### 远程备份节点 (Dell R730) - WireGuard Client

```bash
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <Dell私钥>
Address = 10.0.0.3/24
DNS = 8.8.8.8

[Peer]
# 主节点
PublicKey = <主节点公钥>
AllowedIPs = 10.0.0.0/24,192.168.2.0/24
Endpoint = <主节点公网IP>:51820
PersistentKeepalive = 25
```

### 监控服务访问

如果网络连接正常，可以访问以下监控服务：

| 服务 | 实际IP | 虚拟IP |
|------|--------|--------|
| **Prometheus** | http://100.66.1.7:9090 | http://10.0.0.3:9090 |
| **Grafana** | http://100.66.1.7:3000 | http://10.0.0.3:3000 |
| **Alertmanager** | http://100.66.1.7:9093 | http://10.0.0.3:9093 |

### 快速修复脚本

创建一个快速修复脚本：

```bash
#!/bin/bash
# quick_fix_jdxb_and_network.sh

echo "=========================================="
echo "快速修复 jdxb 服务和网络问题"
echo "=========================================="

# 1. 修复 jdxb 服务
echo "Step 1: 修复 jdxb 服务..."
if ! docker ps | grep -q owjdxb; then
    echo "容器不存在，正在启动..."
    docker run -d \
      --name owjdxb \
      --net host \
      --restart=unless-stopped \
      ionewu/owjdxb:latest
    echo "✅ jdxb 服务已启动"
else
    echo "✅ jdxb 服务正在运行"
fi

# 2. 检查 VPN 连接
echo "Step 2: 检查 VPN 连接..."
if ! ip link show | grep -q wg0; then
    echo "VPN 接口不存在，正在启动..."
    sudo wg-quick up wg0
    echo "✅ VPN 已启动"
else
    echo "✅ VPN 正在运行"
fi

# 3. 检查静态路由
echo "Step 3: 检查静态路由..."
if ! ip route show | grep -q "100.66.1.0/24"; then
    echo "添加静态路由..."
    sudo ip route add 100.66.1.0/24 via 192.168.2.1
    echo "✅ 静态路由已添加"
else
    echo "✅ 静态路由已存在"
fi

# 4. 测试连接
echo "Step 4: 测试连接..."
if ping -c 1 10.0.0.3 > /dev/null 2>&1; then
    echo "✅ VPN 连接正常"
else
    echo "❌ VPN 连接失败"
fi

if ping -c 1 100.66.1.7 > /dev/null 2>&1; then
    echo "✅ 远程服务器连接正常"
else
    echo "❌ 远程服务器连接失败"
fi

echo "=========================================="
echo "修复完成"
echo "=========================================="
```

使用方法：
```bash
chmod +x quick_fix_jdxb_and_network.sh
./quick_fix_jdxb_and_network.sh
```

---

## 📝 总结

### 问题1：jdxb 服务未启动

**原因**: 可能是容器被删除、启动失败或配置错误

**解决方案**:
1. 检查容器状态：`docker ps -a | grep owjdxb`
2. 查看容器日志：`docker logs owjdxb`
3. 重启容器：`docker restart owjdxb`
4. 如果容器不存在，重新拉取镜像并运行
5. 配置自动重启：`docker update --restart=unless-stopped owjdxb`

### 问题2：100.66.1.X 网段不通

**原因**: 可能是 VPN 未建立、静态路由未配置、防火墙阻止或远程服务器问题

**解决方案**:
1. 检查 VPN 连接：`sudo wg show`
2. 启动 VPN：`sudo wg-quick up wg0`
3. 添加静态路由：`sudo ip route add 100.66.1.0/24 via 192.168.2.1`
4. 测试连接：`ping 100.66.1.7` 或 `ping 10.0.0.3`
5. 测试 SSH 连接：`ssh -p 2222 -i ~/.ssh/id_rsa_dell ai@100.66.1.7`

### 建议的排查顺序

1. 首先修复 jdxb 服务（本地问题，更容易解决）
2. 然后排查网络连接（涉及多个组件，需要逐个检查）
3. 使用快速修复脚本进行批量修复
4. 如果问题仍然存在，检查日志和配置文件
5. 联系远程服务器管理员确认服务器状态

---

**报告生成者**: AI Server  
**报告日期**: $(date '+%Y-%m-%d %H:%M:%S')  
**下次检查**: 建议定期检查服务状态和网络连接
