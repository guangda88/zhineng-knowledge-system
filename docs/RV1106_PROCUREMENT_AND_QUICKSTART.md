# RV1106 边缘AI开发 — 采购清单与上手指南

> **项目**: 九域知识系统 — 练功姿态识别边缘验证
> **目标**: 用最低成本验证"摄像头采集 → 边缘姿态识别 → 云端知识指导"闭环
> **日期**: 2026-04-11

---

## 一、采购清单

### 必购（Phase 0 验证最小集）

| # | 物品 | 型号 | 参考价 | 购买渠道 | 备注 |
|---|------|------|--------|---------|------|
| 1 | **开发板** | Luckfox Pico Ultra W (RV1106G3) | ¥261.59 | luckfox.cn | 1 TOPS NPU, 256MB DDR3L, 8GB eMMC, Wi-Fi, PoE 可选 |
| 2 | **摄像头模组** | SC3336 MIPI CSI 300万像素 | ¥49.49 | luckfox.cn / 微雪电子 | 与板子 CSI 接口匹配 |
| 3 | **MicroSD 卡** | 不需要 | — | — | Ultra W 板载 8GB eMMC，无需 SD 卡 |
| 4 | **USB 数据线** | Type-A to Type-C | ¥5-10 | 任意 | 烧录 + 供电 + ADB 调试 |
| 5 | **网线** | 不需要 | — | — | Ultra W 带 Wi-Fi，无需有线 |

**合计：¥311.08（含发票） — 已下单，等待收货**

### 已购型号：Luckfox Pico Ultra W

无需升级，已直接购买 Ultra W（1 TOPS + Wi-Fi）。

### ~~如果选 Ultra 版~~ 已购 Ultra W（Wi-Fi 内置，免网线）

| # | 物品 | 参考价 |
|---|------|--------|
| Luckfox Pico Ultra W | ¥261.59 |
| SC3336 摄像头模组 | ¥49.49 |
| **合计** | **¥311.08（含发票）** |

---

## 二、上手流程（预计 2-3 天）

### Day 1: 环境准备（PC 端，不需要硬件）

```bash
# 1. 安装 Ubuntu 虚拟机（或使用 WSL2）
#    推荐：Ubuntu 20.04/22.04，分配 4核 + 4GB RAM + 40GB 磁盘

# 2. 安装编译工具链
sudo apt update
sudo apt install -y git ssh make gcc gcc-multilib \
    libssl-dev liblz4-tool bc kmod flex bison

# 3. 下载 Luckfox SDK
git clone https://github.com/LuckfoxTECH/luckfox-pico.git
cd luckfox-pico
# SDK 约 2-3GB，含工具链、内核、buildroot

# 4. 编译默认镜像（验证工具链）
cd project
./build.sh lunch
# 选择 Luckfox Pico Pro 默认配置
./build.sh
# 编译约 30-60 分钟
```

### Day 2: 硬件到手，烧录 + 跑通官方 demo

```
1. 连接硬件
   USB-C 线连接 PC ↔ 开发板
   MIPI CSI 摄像头接入板子 FPC 接口（注意方向）
   网线连接板子 ↔ 路由器（或 PC 直连）

2. 烧录系统镜像
   Windows: 下载瑞芯微 SocToolKit 烧录工具
   Linux:   使用 upgrade_tool
   选择编译好的 .img 文件 → 烧录 → 等待完成

3. ADB 连接
   adb shell              # 进入板子 Linux 系统
   ifconfig eth0          # 查看 IP 地址

4. 跑官方摄像头 demo
   cd /oem/usr/bin
   ./luckfox_sshare_demo  # 摄像头预览（需确认具体 demo 名称）
```

### Day 3: 部署姿态估计模型

```bash
# === PC 端：模型转换 ===

# 1. 安装 RKNN-Toolkit2（在 PC 虚拟机中）
pip install rknn-toolkit2
# 或用 Docker 镜像（推荐，避免依赖冲突）

# 2. 下载 YOLOv8-Pose 预训练模型
#    从 RKNN Model Zoo 获取已转换好的 RV1106 模型
git clone https://github.com/airockchip/rknn_model_zoo.git
cd rknn_model_zoo/examples/yolov8_pose

# 3. 转换模型（如果需要自定义）
python convert.py --model yolov8s-pose.onnx --target rv1106

# === 板端：推理测试 ===

# 4. 推送模型到板子
adb push yolov8_pose.rknn /oem/usr/share/rknn_model/

# 5. 运行推理
adb shell
cd /oem/usr/bin
./rknn_yolov8_pose_demo
```

---

## 三、关键技术问题预判

### 3.1 RV1106 跑 YOLOv8-Pose 能达到多少帧率？

| 模型 | 输入分辨率 | RV1106 (0.5T) 帧率估算 | 备注 |
|------|-----------|----------------------|------|
| YOLOv8n-pose | 192×192 | ~15-20 fps | 姿态估计够用 |
| YOLOv8n-pose | 320×320 | ~8-12 fps | 精度更好，勉强实时 |
| YOLOv8s-pose | 192×192 | ~6-10 fps | 模型更大，精度更高 |
| YOLOv8n-pose (INT8量化) | 320×320 | ~12-18 fps | 推荐方案 |

**结论**：YOLOv8n-pose + INT8 量化 + 320×320 输入，预计可达 **12-18 fps**，满足练功姿态实时反馈需求（≥10fps）。

### 3.2 姿态识别 → 气功动作判断

YOLOv8-Pose 输出的是人体 17 个关键点（COCO 格式）：

```
0:鼻  1:左眼  2:右眼  3:左耳  4:右耳
5:左肩  6:右肩  7:左肘  8:右肘
9:左腕 10:右腕 11:左髋 12:右髋
13:左膝 14:右膝 15:左踝 16:右踝
```

气功动作判断逻辑（Phase 0 先用规则，后续可训练分类器）：

```python
def classify_qigong_posture(keypoints):
    """基于关键点角度判断气功动作"""
    # 例：双手托天（八段锦第一式）
    left_wrist_above_head = keypoints[9][1] < keypoints[0][1]  # 腕高于鼻
    right_wrist_above_head = keypoints[10][1] < keypoints[0][1]
    arms_spread = distance(keypoints[9], keypoints[10]) > shoulder_width * 1.5

    if left_wrist_above_head and right_wrist_above_head and arms_spread:
        return "双手托天理三焦", confidence

    # 更多动作规则...
```

### 3.3 端云通信方案

```
设备端 (RV1106)                    云端 (灵知后端)
    │                                   │
    │  每秒采集骨架关键点序列            │
    │  本地缓冲 1-2 秒 (15-30 帧)       │
    │                                   │
    ├───── HTTP POST ──────────────────→│
    │  /api/v1/posture/evaluate         │
    │  {keypoints: [...],               │
    │   device_id, session_id}          │
    │                                   │
    │←──── HTTP 200 ────────────────────┤
    │  {action: "双手托天",             │
    │   quality: 0.85,                  │
    │   guidance: "手臂再伸直一些",      │
    │   next_action: "左右开弓似射雕"}  │
    │                                   │
    │  TTS 播放指导（或本地显示）        │
```

---

## 四、避坑清单

| # | 坑 | 解决方案 |
|---|----|---------|
| 1 | SDK 编译报错 `交叉编译器找不到` | 确认 `toolchain` 路径，SDK 自带，不需要单独下载 |
| 2 | 烧录时板子不识别 | 按住 BOOT 键再插 USB，进入 maskrom 模式 |
| 3 | 摄像头画面黑屏 | 检查 FPC 排线方向，确认摄像头型号在兼容列表中 |
| 4 | RKNN 模型推理报错 `invalid model` | 确认模型转换时 `--target` 设为 `rv1106` 而非 `rk3588` |
| 5 | NPU 帧率远低于预期 | 检查是否走了 NPU 而非 CPU 推理，用 `cat /sys/kernel/debug/rknpu/load` 确认 |
| 6 | 板子联网失败 | Pro 版无 Wi-Fi，必须用网线；或通过 USB RNDIS 共享 PC 网络 |
| 7 | 量化后精度下降严重 | 尝试混合量化（部分层 FP16），或收集校准数据做 calibration |

---

## 五、参考资源

| 资源 | 链接 |
|------|------|
| Luckfox 官方 Wiki | https://wiki.luckfox.com/zh/Luckfox-Pico-RV1106/ |
| RKNN-Toolkit2 | https://gitcode.com/airockchip/rknn-toolkit2 |
| RKNN Model Zoo | https://github.com/airockchip/rknn_model_zoo |
| Luckfox SDK | https://github.com/LuckfoxTECH/luckfox-pico |
| 瑞芯微 SocToolKit 烧录工具 | 官方 SDK 中自带 |
| 立创开源硬件 | https://oshwhub.com |
| YOLOv8-Pose 部署教程 | CSDN 搜索"RV1106 YOLOv8 部署" |

---

*文档版本: 1.0*
*编写: 灵知*
*日期: 2026-04-11*
