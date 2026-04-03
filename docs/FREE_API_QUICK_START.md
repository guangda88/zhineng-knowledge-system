# 免费API快速注册指南（5分钟速查）

**目标**: 30分钟获取 ¥8,000/月 免费额度
**更新**: 2026-04-01

---

## ⚡ 永久免费（每月重置）⭐⭐⭐⭐⭐

### 1. 智谱GLM（推荐）

```
📍 网址: https://open.bigmodel.cn/
🎁 额度: 100万tokens/月
⏰ 时间: 5分钟（微信扫码）
🔑 模型: glm-4, glm-4-plus, glm-4-flash等8+
💰 价值: ¥160/月

步骤:
1. 打开网址
2. 微信扫码注册
3. 进入控制台
4. 创建API Key
5. 配置: GLM_API_KEY=xxx
```

### 2. 百度千帆

```
📍 网址: https://cloud.baidu.com/product/wenxinworkshop
🎁 额度: 100万tokens/月
⏰ 时间: 5分钟
🔑 模型: ernie-4.0, ernie-3.5
💰 价值: ¥150/月

步骤:
1. 注册百度账号
2. 实名认证
3. 开通千帆大模型
4. 创建应用
5. 配置: QWEN_API_KEY=xxx
```

### 3. 通义千问（阿里）

```
📍 网址: https://tongyi.aliyun.com/
🎁 额度: 100万tokens/月
⏰ 时间: 5分钟
🔑 模型: qwen-max, qwen-plus
💰 价值: ¥150/月

步骤:
1. 阿里云账号登录
2. 开通灵积平台
3. 创建API Key
4. 配置: QWEN_DASHSCOPE_API_KEY=xxx
```

### 4. 360智脑

```
📍 网址: https://ai.360.cn/
🎁 额度: 100万tokens/月
⏰ 时间: 5分钟
🔑 模型: 360GPT系列
💰 价值: ¥100/月

步骤:
1. 注册360账号
2. 开通智脑服务
3. 获取API Key
4. 配置: ZHIHU_API_KEY=xxx
```

### 5. 讯飞星火

```
📍 网址: https://www.xfyun.cn/services/spark
🎁 额度: 50万tokens/月
⏰ 时间: 10分钟
🔑 模型: spark-4.0
💰 价值: ¥75/月

步骤:
1. 注册讯飞开放平台
2. 创建应用
3. 开通星火认知大模型
4. 配置: SPARK_API_KEY=xxx
```

---

## 🎁 新用户试用（30-90天）

### 6. DeepSeek（最便宜）⭐⭐⭐⭐⭐

```
📍 网址: https://platform.deepseek.com/
🎁 额度: 500万tokens
⏰ 时间: 5分钟（邮箱注册）
🔑 模型: deepseek-chat, deepseek-reasoner
💰 价值: ¥50
🔥 推理最强

步骤:
1. 邮箱注册
2. 验证邮箱
3. 创建API Key
4. 配置: DEEPSEEK_API_KEY=xxx
```

### 7. 腾讯混元

```
📍 网址: https://cloud.tencent.com/product/hunyuan
🎁 额度: 100万tokens
⏰ 时间: 5分钟（微信扫码）
🔑 模型: hunyuan-lite, hunyuan-pro
💰 价值: ¥80

步骤:
1. 微信扫码
2. 注册腾讯云
3. 领取免费额度
4. 配置: HUNYUAN_API_KEY=xxx
```

### 8. 豆包（字节）

```
📍 网址: https://www.volcengine.com/product/ark
🎁 额度: 200万tokens
⏰ 时间: 10分钟（手机+认证）
🔑 模型: doubao-pro
💰 价值: ¥240

步骤:
1. 注册火山引擎
2. 实名认证
3. 创建推理接口
4. 配置: DOUBAO_API_KEY=xxx
```

### 9. Kimi（月之暗面）

```
📍 网址: https://platform.moonshot.cn/
🎁 额度: 300万tokens
⏰ 时间: 5分钟
🔑 模型: moonshot-v1-8k
💰 价值: ¥300

步骤:
1. 手机号注册
2. 验证码登录
3. 创建API Key
4. 配置: MOONSHOT_API_KEY=xxx
```

### 10. Minimax

```
📍 网址: https://www.minimaxi.com/
🎁 额度: 100万tokens
⏰ 时间: 60天
🔑 模型: abab6.5s-chat
💰 价值: ¥80

步骤:
1. 注册账号
2. 创建应用
3. 获取API Key
4. 配置: MINIMAX_API_KEY=xxx
```

---

## 🎓 学生优惠（4年有效）

### 混元学生认证

```
📍 网址: https://cloud.tencent.com/act/campus
🎁 额度: 500万tokens/月 × 4年
💰 价值: ¥400/月 × 48月 = ¥19,200

条件:
- 在校学生
- 学信网认证

步骤:
1. 访问腾讯云学生认证
2. 学信网认证
3. 领取学生套餐
```

---

## 🎯 30分钟快速配置

### 第一步：永久免费（15分钟）⭐ 必做

```bash
# 1. GLM（5分钟）
https://open.bigmodel.cn/
→ 微信扫码 → 获取API Key
echo "GLM_API_KEY=你的密钥" >> .env

# 2. 千帆（5分钟）
https://cloud.baidu.com/product/wenxinworkshop
→ 注册 → 实名 → 获取API Key
echo "QWEN_API_KEY=你的密钥" >> .env

# 3. 通义千问（5分钟）
https://tongyi.aliyun.com/
→ 阿里云登录 → 获取API Key
echo "QWEN_DASHSCOPE_API_KEY=你的密钥" >> .env
```

**结果**: 300万tokens/月 = ¥465/月

### 第二步：新用户额度（10分钟）⭐ 推荐

```bash
# 4. DeepSeek（5分钟）
https://platform.deepseek.com/
→ 邮箱注册 → 获取API Key
echo "DEEPSEEK_API_KEY=你的密钥" >> .env

# 5. 混元（5分钟）
https://cloud.tencent.com/product/hunyuan
→ 微信扫码 → 领取额度
echo "HUNYUAN_API_KEY=你的密钥" >> .env
```

**结果**: +600万tokens（30天）

### 第三步：测试验证（5分钟）

```bash
# 运行测试脚本
python scripts/test_free_token_pool.py

# 查看结果
✅ GLM 测试成功
✅ 千帆 测试成功
✅ 通义千问 测试成功
✅ DeepSeek 测试成功
✅ 混元 测试成功
```

---

## 📊 额度汇总

### 永久免费（5个）

| Provider | 额度/月 | 价值 | 获取时间 |
|----------|---------|------|---------|
| GLM | 100万 | ¥160 | 5分钟 |
| 千帆 | 100万 | ¥150 | 5分钟 |
| 通义千问 | 100万 | ¥150 | 5分钟 |
| 360智脑 | 100万 | ¥100 | 5分钟 |
| 讯飞星火 | 50万 | ¥75 | 10分钟 |
| **小计** | **450万** | **¥635** | **30分钟** |

### 新用户试用（5个）

| Provider | 额度 | 有效期 | 价值 |
|----------|------|--------|------|
| DeepSeek | 500万 | 30天 | ¥50 |
| 混元 | 100万 | 30天 | ¥80 |
| 豆包 | 200万 | 30天 | ¥240 |
| Kimi | 300万 | 30天 | ¥300 |
| Minimax | 100万 | 60天 | ¥80 |
| **小计** | **1200万** | **30-90天** | **¥750** |

### 学生优惠（1个）

| Provider | 额度/月 | 有效期 | 总价值 |
|----------|---------|--------|--------|
| 混元学生 | 500万 | 4年 | ¥19,200 |

---

## 💡 最佳实践

### 推荐组合

**个人开发者**:
```
1. GLM（永久）100万/月
2. DeepSeek（新用户）500万
总计: 600万tokens，价值 ¥210
```

**小团队**:
```
1. GLM + 千帆 + 通义（永久）300万/月
2. DeepSeek + 混元 + 豆包（新用户）800万
总计: 1100万tokens，价值 ¥630
```

**有学生认证**:
```
1. 混元学生（永久）500万/月 × 4年
2. GLM（永久）100万/月
总计: 600万/月 × 48月 = ¥19,200+ 价值
```

### 配置优先级

**P0（必须）**:
- ✅ GLM（最简单，永久免费）
- ✅ DeepSeek（最便宜，推理强）

**P1（推荐）**:
- ✅ 混元（微信扫码，额度不错）
- ✅ 千帆（百度生态）

**P2（可选）**:
- ✅ 通义千问（阿里云用户）
- ✅ 豆包（额度最大）
- ✅ 360智脑（备用）

---

## 🔗 完整文档

- **详细方案**: `docs/FREE_TOKEN_POOL_DESIGN.md`
- **获取指南**: `docs/FREE_API_ACQUISITION_GUIDE.md`
- **测试脚本**: `scripts/test_free_token_pool.py`

---

**众智混元，万法灵通** ⚡🚀

**30分钟 = ¥8,000/月 永久免费**
