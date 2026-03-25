# 网络排查、SafeLine 部署及监控体系建设方案

报告时间: $(date '+%Y-%m-%d %H:%M:%S')
执行节点: zhineng-ai (100.66.1.8 / 10.113.22.99)

---

## 1. 网络问题诊断结论

### 1.1 问题根因

经过深度诊断（ARP 检查、接口检查），发现 `zhineng-ai` 的 `enp5s0` 接口（IP: 100.66.1.8）在 ARP 层面无法解析 `100.66.1.1` (ZhinengNAS) 和 `100.66.1.7` (ZhinengServer) 的 MAC 地址。

**ARP 缓存显示**:
- `100.66.1.1` -> `incomplete` (on docker0/br-*)
- `100.66.1.7` -> `incomplete` (on docker0/br-*/enp4s0)

**结论**:
`zhineng-ai` 的 `100.66.1.8` IP 可能位于一个被隔离的 VLAN，或者网关/交换机配置仅允许特定 MAC/IP 对该网段进行通信。虽然路由表正确，但 L2 层面的广播/ARP 请求没有得到回应，导致无法建立连接。

### 1.2 临时解决方案

利用现有正常工作的网络链路（`10.113.22.0/24` 和 `192.168.31.0/24`）进行替代通信。

| 目标主机 | 推荐通信网段 | 备用网段 | 状态 |
|----------|---------------|----------|------|
| PC-20251210RIZC | 10.113.22.66 | 192.168.31.140 | ✅ 正常 |
| ZhinengNAS | 10.113.22.88 | 192.168.31.88 | ✅ 正常 |
| ZhinengAI-01 | 10.113.22.208 | 192.168.31.208 | ✅ 正常 |
| ZhinengServer | 10.113.22.90 | - | ✅ 正常 |

**行动**: 在本次部署中，**强制使用 `10.113.22.0/24` 网段** 作为集群内部管理、监控和数据同步的网络平面。

---

## 2. 总体部署方案

### 2.1 目标

1.  在 5 台主机上部署 SafeLine 安全防护。
2.  加固现有服务（SSH, Docker, 数据库）。
3.  建立基于 Prometheus + Grafana 的监控体系。

### 2.2 角色分配

| 主机 | IP (推荐) | 角色 | SafeLine | Node Exporter | 附加服务 |
|------|-----------|------|----------|---------------|----------|
| **zhineng-ai** | 10.113.22.99 | 控制节点 + AI 主节点 | ✅ | ✅ | Prometheus, Grafana, Docker 主控 |
| **ZhinengNAS** | 10.113.22.88 | 监控/存储节点 | ✅ | ✅ | 监控代理, AList |
| **ZhinengAI-01** | 10.113.22.208 | AI 从节点 | ✅ | ✅ | Docker 工作节点 |
| **ZhinengServer** | 10.113.22.90 | 备份/冷存储 | ✅ | ✅ | 备份服务, 文件服务 |
| **PC-20251210RIZC** | 10.113.22.66 | 开发/调试节点 | ✅ (需单独安装) | - | - |

---

## 3. SafeLine 部署方案

### 3.1 部署步骤 (Linux/Unix)

**前置条件**:
- 系统内核版本 > 4.18
- 端口 9443 未被占用 (用于 Web 控制台)

**操作步骤**:

1.  **下载并运行安装脚本**
    ```bash
    # 使用脚本安装
    bash scripts/deploy/install_safeline.sh

    # 或手动安装
    bash -c "$(curl -fsSLk https://waf-ce.chaitin.cn/release/latest/setup.sh)"
    ```

2.  **初始化控制台**
    - 访问 `https://<主机IP>:9443`
    - 根据页面提示设置管理员密码。
    - 激活服务（社区版可能需要注册）。

3.  **检查服务状态**
    ```bash
    docker ps | grep safeline
    ```

### 3.2 Windows PC 部署

SafeLine 原生仅支持 Linux。对于 Windows 10 PC，建议采取以下替代方案：

1.  **方案 A: 安装 WSL2 并在 WSL2 中部署 SafeLine**
    - 优点: 完整功能支持。
    - 缺点: 仅能保护 WSL2 内部的流量。

2.  **方案 B: 使用 Windows 自带防火墙 + Defender**
    - 启用 Windows Defender 实时保护。
    - 启用防火墙规则，仅允许必要端口入站。
    - 定期运行 Windows 更新。

3.  **方案 C: 安装其他 HIDS 软件** (如 Wazuh)

**建议**: Windows PC 主要用于开发，优先使用 WSL2 运行开发环境，同时在 WSL2 中部署 SafeLine。

---

## 4. 服务加固方案

### 4.1 自动化加固

执行提供的 `harden_services.sh` 脚本，执行以下操作：

1.  **系统更新**: 更新所有软件包。
2.  **防火墙 (UFW)**:
    - 默认拒绝入站。
    - 允许 SSH, SafeLine (9443), Node Exporter (9100)。
3.  **SSH 加固**:
    - 禁止 Root 直接登录。
    - 禁止密码认证 (强制使用 SSH Key)。
4.  **暴力破解防护 (Fail2ban)**:
    - 自动封禁尝试暴力破解 IP。
    - 保护 SSH 服务。

**手动加固**:
- **Docker**: 删除未使用的镜像、容器、网络。
- **数据库**: 修改默认端口，修改强密码。

---

## 5. 监控体系建设

### 5.1 架构设计

采用 **Pushgateway + Prometheus + Grafana** 模式，或标准的 **Pull 模式**。

考虑到网络拓扑，建议使用 **Pull 模式**，因为 `10.113.22.0/24` 通信正常。

```
[Client] <--9100-- [Node Exporter]
[Server]  <--9100-- [Node Exporter] <--pull-- [Prometheus (zhineng-ai)]
[NAS]     <--9100-- [Node Exporter]             |
[AI-01]   <--9100-- [Node Exporter]             v
                                           [Grafana (zhineng-ai)]
```

### 5.2 部署步骤

#### 步骤 1: 在所有 4 台 Linux 主机上部署 Node Exporter

```bash
# 在每台主机上执行
bash scripts/deploy/install_node_exporter.sh
```

验证:
```bash
curl http://<主机IP>:9100/metrics
```

#### 步骤 2: 在 zhineng-ai 上更新 Prometheus 配置

编辑 `prometheus.yml` (如果是 Docker 容器，需要挂载配置):

```yaml
scrape_configs:
  - job_name: 'zhineng-ai'
    static_configs:
      - targets: ['10.113.22.99:9100']

  - job_name: 'zhineng-nas'
    static_configs:
      - targets: ['10.113.22.88:9100']

  - job_name: 'zhineng-ai-01'
    static_configs:
      - targets: ['10.113.22.208:9100']

  - job_name: 'zhineng-server'
    static_configs:
      - targets: ['10.113.22.90:9100']
```

#### 步骤 3: 重启 Prometheus

```bash
# 如果是 Docker
docker restart prometheus
# 或
docker-compose restart prometheus
```

#### 步骤 4: 配置 Grafana Dashboard

1.  登录 Grafana (http://10.113.22.99:3000)。
2.  添加 Prometheus 数据源。
3.  导入 Node Exporter Full Dashboard (ID: 1860)。

---

## 6. 执行清单

### 主机: zhineng-ai (当前操作主机)

- [x] 网络诊断完成
- [ ] SafeLine 安装
- [ ] Node Exporter 安装
- [ ] Prometheus 更新配置
- [ ] 服务加固脚本执行

### 主机: ZhinengNAS (10.113.22.88)

- [ ] SSH 登录验证
- [ ] SafeLine 安装
- [ ] Node Exporter 安装
- [ ] 服务加固脚本执行

### 主机: ZhinengAI-01 (10.113.22.208)

- [ ] SSH 登录验证
- [ ] SafeLine 安装
- [ ] Node Exporter 安装
- [ ] 服务加固脚本执行

### 主机: ZhinengServer (10.113.22.90)

- [ ] SSH 登录验证
- [ ] SafeLine 安装
- [ ] Node Exporter 安装
- [ ] 服务加固脚本执行

### 主机: PC-20251210RIZC (10.113.22.66)

- [ ] WSL2 环境检查
- [ ] SafeLine 安装 (在 WSL2 中)
- [ ] 安全策略检查

---

## 7. 应急恢复预案

如果在部署 SafeLine 或防火墙加固后出现无法连接的情况：

1.  **通过物理/控制台连接**: 直接接入显示器键盘。
2.  **重置防火墙**:
    ```bash
    ufw disable
    # 如果是 iptables
    iptables -F
    iptables -X
    ```
3.  **检查 SSH 服务**:
    ```bash
    systemctl status sshd
    systemctl restart sshd
    ```
4.  **检查 SafeLine 状态**:
    ```bash
    docker ps | grep safeline
    # 如果导致问题，可临时停止
    docker stop <safeline_container_id>
    ```

---

## 8. 总结

本次方案的核心在于规避 `100.66.1.0/24` 网段的物理连通性问题，利用稳定的 `10.113.22.0/24` 网段构建内部管理平面。通过 SafeLine 提供主机级安全防护，Node Exporter + Prometheus 提供细粒度监控，最终实现一套稳固、可视、安全的 IT 基础设施。

---

**报告生成者**: AI Server  
**执行时间**: $(date '+%Y-%m-%d %H:%M:%S')
