# 百度千帆API Key获取完整指南

**日期**: 2026-04-01
**目标**: 5分钟获取百度千帆API Key和100万tokens免费额度
**状态**: 完整步骤指南

---

## 🎯 快速答案

### 百度千帆 vs 百度智能云

**重要区别**:
- **百度千帆** → 大模型平台（ERNIE Bot等）✅ 我们要的
- **百度智能云** → 云服务器BCC等（你刚看的文档）❌ 不是这个

**千帆平台地址**: https://cloud.baidu.com/product/wenxinworkshop

---

## 📝 完整注册步骤（5-10分钟）

### 步骤1: 注册百度账号（2分钟）

```
1. 访问: https://cloud.baidu.com/
2. 点击右上角"注册"
3. 选择注册方式:
   - 手机号注册（推荐）
   - 百度账号登录
4. 填写信息:
   - 手机号
   - 验证码
   - 密码
5. 同意协议 → 注册
```

### 步骤2: 实名认证（3分钟）

```
1. 登录百度智能云控制台
   https://console.bce.baidu.com/

2. 进入"账号中心" → "实名认证"

3. 选择认证方式:
   - 个人认证（推荐）→ 身份证
   - 企业认证 → 营业执照

4. 上传证件:
   - 身份证正反面
   - 或手持身份证照片

5. 等待审核:
   - 通常1-5分钟
   - 最长24小时
```

**提示**: 实名认证是必需的，不认证无法创建API Key

### 步骤3: 开通千帆大模型平台（2分钟）

```
方式1: 直接访问（推荐）
----------------------
1. 访问: https://cloud.baidu.com/product/wenxinworkshop
2. 点击"立即使用"
3. 同意服务协议
4. 等待开通（通常即时）

方式2: 从控制台开通
------------------
1. 登录控制台: https://console.bce.baidu.com/
2. 产品列表 → "人工智能" → "千帆大模型平台"
3. 点击"开通服务"
```

### 步骤4: 创建应用获取API Key（3分钟）✅

```
1. 进入千帆控制台
   https://console.bce.baidu.com/qianfan/

2. 左侧菜单 → "API Key管理"
   或直接访问:
   https://console.bce.baidu.com/qianfan/iam/apiKey

3. 点击"创建API Key"

4. 填写信息:
   - API Key名称: 如"灵知系统"
   - 应用类型: 选择"后端应用"
   - 应用描述: 如"智能知识库系统"

5. 点击"确认创建"

6. 复制API Key（只显示一次！）
   - API Key: ak-xxxxxx
   - Secret Key: sk-xxxxxx

   ⚠️ 重要: 请立即复制保存，离开页面后无法再次查看Secret Key！
```

### 步骤5: 领取免费额度（自动）

```
开通千帆后自动获得:
✅ 100万tokens/月 免费额度
✅ 有效期: 永久（每月重置）
✅ 适用模型:
   - ERNIE-Bot 4.0
   - ERNIE-Bot 3.5
   - ERNIE-Speed
   - ERNIE-Tiny
```

---

## 🔑 API Key详细信息

### API Key组成

百度千帆的API密钥由两部分组成：

| 密钥 | 说明 | 示例 |
|------|------|------|
| **API Key** | 公钥，类似用户名 | `ak-24字符的字符串` |
| **Secret Key** | 私钥，类似密码 | `sk-24字符的字符串` |

### 使用方式

```python
# 方式1: 环境变量（推荐）
QWEN_API_KEY=ak-xxxxxx  # 只需API Key

# 方式2: 在代码中使用
API_KEY = "ak-xxxxxx"
SECRET_KEY = "sk-xxxxxx"  # 某些接口可能需要
```

---

## 💻 配置到灵知系统

### 方法1: 通过.env文件（推荐）

```bash
# 编辑.env文件
nano .env

# 添加以下行
QWEN_API_KEY=ak-你的API_Key
```

### 方法2: 通过环境变量

```bash
# 临时设置（当前会话有效）
export QWEN_API_KEY=ak-你的API_Key

# 永久设置（添加到~/.bashrc）
echo 'export QWEN_API_KEY=ak-你的API_Key' >> ~/.bashrc
source ~/.bashrc
```

### 方法3: 通过Python代码（测试用）

```python
import os

# 设置环境变量
os.environ["QWEN_API_KEY"] = "ak-你的API_Key"

# 或直接使用（不推荐生产环境）
API_KEY = "ak-你的API_Key"
```

---

## 🧪 测试API Key

### 方法1: 使用测试脚本

```bash
# 运行免费token池测试
python scripts/test_free_token_pool.py

# 查看千帆provider是否测试通过
```

### 方法2: 使用Python代码

```python
import asyncio
import httpx

async def test_qwen_api():
    """测试千帆API"""

    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        print("❌ 未配置QWEN_API_KEY")
        return

    url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "model": "ernie-speed-128k",  # 或 ernie-bot-4.0
        "messages": [
            {"role": "user", "content": "你好，请用一句话介绍你自己。"}
        ],
        "max_tokens": 100
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{url}?access_token={api_key}",
                headers=headers,
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                content = result["result"]
                print(f"✅ API Key有效")
                print(f"📝 响应: {content}")
            else:
                print(f"❌ HTTP {response.status_code}")
                print(f"错误: {response.text}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")

# 运行测试
asyncio.run(test_qwen_api())
```

### 方法3: 使用curl命令

```bash
# 测试API Key
curl -X POST "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token=你的API_Key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ernie-speed-128k",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 50
  }'
```

---

## 📊 免费额度详情

### 千帆免费套餐

| 模型 | 免费额度/月 | 特点 |
|------|------------|------|
| **ERNIE-Bot 4.0** | 100万tokens | 最新最强 |
| **ERNIE-Bot 3.5** | 包含在内 | 高性价比 |
| **ERNIE-Speed** | 包含在内 | 极速响应 |
| **ERNIE-Tiny** | 包含在内 | 轻量级 |

### 额度查询

```
1. 进入千帆控制台
   https://console.bce.baidu.com/qianfan/

2. 左侧菜单 → "用量统计"

3. 查看:
   - 当月使用量
   - 剩余额度
   - 使用明细
```

---

## 🔧 常见问题

### Q1: API Key和Secret Key有什么区别？

**A**:
- **API Key**: 公钥，用于标识身份，可以公开
- **Secret Key**: 私钥，用于签名验证，必须保密

千帆的大多数接口只需要API Key，但某些高级功能可能需要Secret Key。

### Q2: Secret Key丢失了怎么办？

**A**: 无法找回，必须删除旧的API Key重新创建：

```
1. 进入API Key管理
2. 找到对应的API Key
3. 点击"删除"
4. 重新创建新的API Key
```

### Q3: 免费额度用完会怎样？

**A**:
- 不会停止服务
- 超出部分按 ¥0.004/千tokens 计费
- 建议设置用量告警

### Q4: 如何设置用量告警？

**A**:
```
1. 进入千帆控制台
2. "用量统计" → "告警设置"
3. 设置告警阈值（如80%）
4. 添加告警通知方式（邮件/短信）
```

### Q5: API Key可以用于哪些模型？

**A**: 千帆API Key支持所有千帆模型：
- ERNIE-Bot系列
- ERNIE-Speed
- ERNIE-Tiny
- BES系列
- 等等

---

## 🚀 快速配置到系统

### 完整配置步骤

```bash
# 1. 编辑.env文件
cat >> .env << 'EOF'

# ========== 百度千帆 ==========
QWEN_API_KEY=ak-你的API_Key
# QWEN_SECRET_KEY=sk-你的Secret_Key  # 可选

EOF

# 2. 重启服务（如果在运行）
systemctl restart zhineng-kb

# 3. 测试API
python scripts/test_free_token_pool.py

# 4. 查看结果
# 应该看到 "千帆" provider 测试成功
```

### 验证配置

```python
# 测试代码
from backend.services.evolution.free_token_pool import get_free_token_pool

pool = get_free_token_pool()

# 查看千帆状态
status = pool.get_pool_status()
qwen_status = status["providers"]["qwen"]

print(f"可用: {qwen_status['available']}")
print(f"剩余: {qwen_status['remaining']} tokens")

# 测试调用
result = await pool.call_provider(
    "qwen",
    "你好"
)

if result["success"]:
    print("✅ 千帆API配置成功！")
else:
    print(f"❌ 错误: {result['error']}")
```

---

## 📚 相关资源

### 官方文档

- **千帆平台**: https://cloud.baidu.com/product/wenxinworkshop
- **控制台**: https://console.bce.baidu.com/qianfan/
- **API文档**: https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html
- **Python SDK**: https://github.com/baidubce/bce-qianfan-sdk

### 社区资源

- **千帆社区**: https://cloud.baidu.com/product-qianfan/forum
- **技术支持**: 4008-777-818

### 本系统相关

- **免费Token池**: `docs/FREE_TOKEN_POOL_DESIGN.md`
- **快速开始**: `docs/FREE_API_QUICK_START.md`
- **测试脚本**: `scripts/test_free_token_pool.py`

---

## ✅ 完成检查清单

- [ ] 已注册百度账号
- [ ] 已完成实名认证
- [ ] 已开通千帆大模型平台
- [ ] 已创建API Key
- [ ] 已复制保存API Key和Secret Key
- [ ] 已配置到.env文件
- [ ] 已运行测试验证
- [ ] 已确认100万tokens免费额度

---

**众智混元，万法灵通** ⚡🚀

**5分钟 = 100万tokens/月 永久免费**
