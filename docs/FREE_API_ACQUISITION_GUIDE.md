# 混元、豆包、GLM免费API获取指南

**日期**: 2026-04-01
**目标**: 通过微信扫码等方式获取免费API额度
**状态**: 完整实施方案

---

## 📱 第一部分：混元（腾讯）免费API

### 方式1：微信扫码免费试用 ✅

#### 获取步骤

1. **访问腾讯混元AI开放平台**
   - 网址: https://cloud.tencent.com/product/hunyuan
   - 点击"免费试用"或"立即体验"

2. **微信扫码登录**
   ```
   使用微信扫描页面二维码
   关注"腾讯云AI"公众号
   注册腾讯云账号（如果还没有）
   ```

3. **领取免费额度**
   - **新用户**: 100万tokens 免费额度
   - **有效期**: 30天
   - **模型**: hunyuan-lite、hunyuan-pro、hunyuan-turbo

4. **获取API密钥**
   ```
   进入"控制台" -> "API密钥管理"
   创建密钥 → 复制API Key
   ```

#### 免费额度详情

| 套餐 | Tokens | 有效期 | 价值 |
|------|--------|--------|------|
| 新用户 | 1,000,000 | 30天 | ¥80 |
| 学生认证 | 5,000,000 | 90天 | ¥400 |
| 企业试用 | 10,000,000 | 30天 | ¥800 |

#### 配置到系统

```bash
# .env文件
HUNYUAN_API_KEY=your_api_key_here
HUNYUAN_API_URL=https://api.hunyuan.cloud.tencent.com/v1/chat/completions
```

#### Python调用示例

```python
import requests

def call_hunyuan(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {os.getenv('HUNYUAN_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "hunyuan-lite",  # 或 hunyuan-pro
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    response = requests.post(
        "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    return response.json()["choices"][0]["message"]["content"]
```

---

### 方式2：腾讯云学生优惠 🎓

#### 申请条件

- ✅ 在校学生（大学生、研究生）
- ✅ 学信网认证
- ✅ 年龄16-25岁

#### 学生优惠

| 项目 | 免费额度 | 有效期 |
|------|---------|--------|
| 混元API | 500万tokens/月 | 4年 |
| 服务器代金券 | ¥200/月 | 4年 |

#### 申请步骤

1. 访问: https://cloud.tencent.com/act/campus
2. 微信扫码认证学生身份
3. 完成学信网认证
4. 领取学生套餐

---

## 📱 第二部分：豆包（字节）免费API

### 方式1：火山引擎免费试用 ✅

#### 获取步骤

1. **访问火山引擎官网**
   - 网址: https://www.volcengine.com/product/ark
   - 点击"免费体验"

2. **手机号/微信注册**
   ```
   输入手机号
   接收验证码
   设置密码
   完成注册
   ```

3. **实名认证**
   - 个人用户: 身份证认证
   - 企业用户: 营业执照认证

4. **领取免费额度**
   - **新用户**: 200万tokens 免费额度
   - **有效期**: 30天
   - **模型**: doubao-pro、doubao-lite

5. **获取API密钥**
   ```
   进入"控制台" -> "API Key管理"
   创建API Key → 复制
   ```

#### 免费额度详情

| 套餐 | Tokens | 有效期 | 价值 |
|------|--------|--------|------|
| 新用户 | 2,000,000 | 30天 | ¥240 |
| 个人认证 | 5,000,000 | 90天 | ¥600 |
| 企业认证 | 20,000,000 | 30天 | ¥2400 |

#### 配置到系统

```bash
# .env文件
DOUBAO_API_KEY=your_api_key_here
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
```

#### Python调用示例

```python
import requests

def call_doubao(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {os.getenv('DOUBAO_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "ep-20241105111448-l7jgz",  # 豆包endpoint
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    response = requests.post(
        "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    return response.json()["choices"][0]["message"]["content"]
```

---

### 方式2：豆包智能体免费额度

#### 豆包App内免费额度

1. **下载豆包App**
   - iOS: App Store搜索"豆包"
   - Android: 应用商店搜索"豆包"

2. **注册登录**
   - 微信一键登录
   - 手机号登录

3. **每日免费额度**
   - 普通用户: 10万tokens/天
   - VIP用户: 50万tokens/天
   - 有效期: 每日重置

4. **获取API方式**
   - 豆包App内暂不提供直接API
   - 需要通过火山引擎平台获取

---

## 🔑 第三部分：GLM（智谱）免费API

### GLM Coding Plan - 免费开发额度 ✅

#### 什么是GLM Coding Plan？

GLM Coding Plan是智谱AI面向开发者的免费计划，提供：
- ✅ 每月免费调用额度
- ✅ 访问多个GLM模型
- ✅ 适合开发、测试

#### 注册获取步骤

1. **访问智谱AI开放平台**
   - 网址: https://open.bigmodel.cn/
   - 点击"免费注册"

2. **手机号/微信注册**
   ```
   手机号注册
   微信扫码注册（推荐）
   ```

3. **实名认证**
   - 个人开发者: 身份证认证
   - 企业开发者: 营业执照认证

4. **领取免费额度**
   - **新用户**: 25万tokens/月 永久免费
   - **Coding Plan**: 100万tokens/月
   - **有效期**: 每月重置

#### Coding Plan详情

| 套餐 | Tokens/月 | 模型 | 价格 |
|------|-----------|------|------|
| 免费版 | 250,000 | glm-4, glm-3-turbo | 免费 |
| Coding Plan | 1,000,000 | 全部模型 | 免费 |
| Pro版 | 10,000,000 | 全部模型 | ¥49/月 |

#### 支持的模型

Coding Plan支持以下模型：

| 模型 | 用途 | 上下文 |
|------|------|--------|
| **glm-4** | 通用对话 | 128K |
| **glm-4-plus** | 高级对话 | 128K |
| **glm-4-air** | 轻量级 | 128K |
| **glm-4-flash** | 极速响应 | 128K |
| **glm-4-long** | 长文本理解 | 1M |
| **glm-3-turbo** | 快速响应 | 128K |
| **glm-4v** | 视觉理解 | - |
| **CogView** | 图像生成 | - |

#### 配置到系统

```bash
# .env文件
GLM_API_KEY=your_api_key_here
GLM_API_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
```

#### Python调用示例

```python
import requests

def call_glm(prompt: str, model: str = "glm-4") -> str:
    headers = {
        "Authorization": f"Bearer {os.getenv('GLM_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,  # glm-4, glm-4-plus, glm-4-air等
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    response = requests.post(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )

    return response.json()["choices"][0]["message"]["content"]
```

---

## 📊 第四部分：多平台对比与策略

### 免费额度对比

| 平台 | 免费额度 | 有效期 | 模型数量 | 获取难度 |
|------|---------|--------|---------|---------|
| **混元（腾讯）** | 100万tokens | 30天 | 5 | ⭐ 简单 |
| **豆包（字节）** | 200万tokens | 30天 | 3 | ⭐⭐ 中等 |
| **GLM（智谱）** | 100万tokens/月 | 永久 | 8+ | ⭐⭐⭐ 最简单 |
| **DeepSeek** | 500万tokens | 30天 | 2 | ⭐⭐ 中等 |

### 成本对比

| 平台 | 免费/月 | 按需付费 | 性价比 |
|------|---------|---------|--------|
| 混元 | ¥80 | ¥0.008/千tokens | ⭐⭐⭐ |
| 豆包 | ¥240 | ¥0.012/千tokens | ⭐⭐ |
| GLM | ¥160 | ¥0.01/千tokens | ⭐⭐⭐⭐ |
| DeepSeek | ¥50 | ¥0.001/千tokens | ⭐⭐⭐⭐⭐ |

### 推荐获取策略

#### 阶段1：快速获取（今天完成）

1. **GLM Coding Plan** ⭐⭐⭐⭐⭐
   - 微信扫码 → 5分钟完成
   - 100万tokens/月 永久免费
   - 支持8+模型

2. **混元新用户** ⭐⭐⭐⭐
   - 微信扫码 → 5分钟完成
   - 100万tokens 30天
   - 适合快速测试

#### 阶段2：扩展额度（本周完成）

3. **豆包火山引擎** ⭐⭐⭐
   - 实名认证 → 10分钟
   - 200万tokens 30天
   - 额度最大

4. **DeepSeek** ⭐⭐⭐⭐⭐
   - 邮箱注册 → 5分钟
   - 500万tokens 30天
   - 最便宜

#### 阶段3：长期优化（本月完成）

5. **学生认证**（如果是在校生）
   - 混元: 500万tokens/月 × 4年
   - 豆包: 额外学生优惠

6. **企业认证**（如果有公司）
   - 豆包: 2000万tokens
   - 混元: 企业试用套餐

---

## 🔧 第五部分：系统配置实施

### 更新.env配置

```bash
# .env文件

# ========== 混元（腾讯） ==========
HUNYUAN_API_KEY=sk-your-hunyuan-key-here
HUNYUAN_API_URL=https://api.hunyuan.cloud.tencent.com/v1/chat/completions

# ========== 豆包（字节） ==========
DOUBAO_API_KEY=your-doubao-key-here
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions

# ========== GLM（智谱） ==========
GLM_API_KEY=your-glm-key-here
GLM_API_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions

# ========== DeepSeek ==========
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
```

### 更新MultiAIAdapter

当前系统已经支持这些API，只需配置密钥即可：

```python
# backend/services/evolution/multi_ai_adapter.py

ADAPTERS = {
    "lingzhi": LingzhiAdapter,
    "hunyuan": HunyuanAdapter,    # ✅ 已支持
    "doubao": DoubaoAdapter,      # ✅ 已支持
    "deepseek": DeepSeekAdapter,  # ✅ 已支持
    "glm": GLMAdapter             # ✅ 已支持
}
```

### 测试配置

```bash
# 1. 重启服务
systemctl restart zhineng-kb

# 2. 测试各API
python scripts/test_apis.py

# 3. 查看日志
tail -f /var/log/zhineng-kb/api.log
```

---

## 💡 第六部分：智能切换策略

### 按成本优先级

```python
class CostOptimizedRouter:
    """成本优化的路由器"""

    def __init__(self):
        # 按成本排序（从低到高）
        self.providers_by_cost = [
            "deepseek",   # ¥0.001/千tokens - 最便宜
            "hunyuan",    # ¥0.008/千tokens
            "glm",        # ¥0.01/千tokens
            "doubao",     # ¥0.012/千tokens
        ]

    async def route_request(
        self,
        prompt: str,
        complexity: str
    ) -> str:
        """路由到最经济的provider"""

        # 简单问题 → DeepSeek
        if complexity == "simple":
            return "deepseek"

        # 中等复杂度 → 混元或GLM（免费额度）
        if complexity == "medium":
            # 检查免费额度
            if self.check_free_quota("hunyuan"):
                return "hunyuan"
            elif self.check_free_quota("glm"):
                return "glm"
            else:
                return "deepseek"

        # 复杂问题 → 豆包或GLM Plus
        if complexity == "complex":
            return "glm"  # 使用glm-4-plus

    def check_free_quota(self, provider: str) -> bool:
        """检查是否还有免费额度"""
        # 从TokenUsageTracker查询
        tracker = TokenUsageTracker()
        usage = tracker.daily_usage.get(provider, 0)
        budget = tracker.daily_budget.get(provider, 0)
        return usage < budget
```

### 免费额度优先策略

```python
class FreeQuotaStrategy:
    """免费额度优先策略"""

    async def consume_free_quota_first(self):
        """优先使用免费额度"""

        # 1. GLM Coding Plan（100万/月 永久）
        if await self.has_quota("glm"):
            return await self.call_glm()

        # 2. 混元新用户（100万 30天）
        if await self.has_quota("hunyuan"):
            return await self.call_hunyuan()

        # 3. 豆包新用户（200万 30天）
        if await self.has_quota("doubao"):
            return await self.call_doubao()

        # 4. DeepSeek（最便宜）
        return await self.call_deepseek()
```

---

## 📋 第七部分：实施清单

### 立即执行（今天）

- [ ] 注册GLM Coding Plan（5分钟）
  - 微信扫码: https://open.bigmodel.cn/
  - 获取API Key
  - 配置到.env

- [ ] 注册混元新用户（5分钟）
  - 微信扫码: https://cloud.tencent.com/product/hunyuan
  - 领取100万免费tokens
  - 配置到.env

- [ ] 注册豆包火山引擎（10分钟）
  - 手机号注册: https://www.volcengine.com/product/ark
  - 实名认证
  - 领取200万免费tokens
  - 配置到.env

### 本周完成

- [ ] 注册DeepSeek（5分钟）
  - 邮箱注册: https://platform.deepseek.com/
  - 获取500万免费tokens
  - 配置到.env

- [ ] 测试所有API
  - 验证密钥有效性
  - 测试响应速度
  - 测试token消耗

- [ ] 实施智能路由
  - 按成本优先
  - 免费额度优先
  - 质量保证

### 本月完成

- [ ] 监控免费额度使用
  - 每日报告
  - 额度告警
  - 到期提醒

- [ ] 评估是否需要付费
  - 分析用量
  - 计算ROI
  - 选择最优套餐

---

## 🎯 总结

### 免费总额度（新用户）

| 平台 | 额度 | 总价值 |
|------|------|--------|
| GLM | 100万/月 × 12月 = 1200万 | ¥960 |
| 混元 | 100万 | ¥80 |
| 豆包 | 200万 | ¥240 |
| DeepSeek | 500万 | ¥50 |
| **总计** | **2000万 tokens** | **¥1,330** |

### 获取时间

- **GLM**: 5分钟（微信扫码）
- **混元**: 5分钟（微信扫码）
- **豆包**: 10分钟（手机+认证）
- **DeepSeek**: 5分钟（邮箱）

**总计**: 25分钟获取¥1,330的免费额度

### 推荐顺序

1. **GLM Coding Plan** ⭐⭐⭐⭐⭐
   - 最简单（微信扫码）
   - 永久免费（每月重置）
   - 模型最多（8+）

2. **混元新用户** ⭐⭐⭐⭐
   - 微信扫码
   - 100万tokens
   - 适合测试

3. **DeepSeek** ⭐⭐⭐⭐⭐
   - 最便宜
   - 500万tokens
   - 生产环境首选

4. **豆包** ⭐⭐⭐
   - 额度最大
   - 需要实名
   - 备用方案

---

**众智混元，万法灵通** ⚡🚀

**25分钟 = ¥1,330免费额度**
**足够开发、测试、小规模生产使用**
