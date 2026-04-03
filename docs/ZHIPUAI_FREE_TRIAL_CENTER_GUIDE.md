# 智谱AI免费模型试用中心完整指南

**更新**: 2026-04-01
**试用中心**: [https://bigmodel.cn/trialcenter](https://bigmodel.cn/trialcenter/modeltrial/text)

---

## 🎯 试用中心概览

智谱AI提供**完全免费**的模型试用服务，涵盖5大模态：

| 模态 | 试用链接 | 状态 |
|------|---------|------|
| **文本** | [文本模型试用](https://bigmodel.cn/trialcenter/modeltrial/text) | ✅ 免费 |
| **视觉** | [视觉模型试用](https://bigmodel.cn/trialcenter/modeltrial/vision) | ✅ 免费 |
| **图像** | [图像模型试用](https://bigmodel.cn/trialcenter/modeltrial/image) | ✅ 免费 |
| **视频** | [视频模型试用](https://bigmodel.cn/trialcenter/modeltrial/video) | ✅ 免费 |
| **语音** | [语音模型试用](https://bigmodel.cn/trialcenter/modeltrial/voice) | ✅ 免费 |

---

## 📝 文本模型试用

### GLM系列模型

**可用模型**:
- **GLM-5.1** ⭐ 最新旗舰
- **GLM-5** - 744B参数，200K上下文
- **GLM-5-Turbo** - OpenClaw优化
- **GLM-4.7** - 高性能旗舰
- **GLM-4-Flash** - 极速版本
- **GLM-4-Air** - 轻量级
- **GLM-4-Plus** - 增强版

### 试用额度

```
✅ 完全免费
✅ 无需订阅
✅ 即开即用
✅ 在线体验
```

### 适用场景

- 代码生成
- 文本创作
- 知识问答
- 逻辑推理
- 长文本处理

### API调用

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-free-trial-key",  # 试用中心获取
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

response = client.chat.completions.create(
    model="glm-5.1",  # 使用最新模型
    messages=[
        {"role": "user", "content": "你好"}
    ]
)

print(response.choices[0].message.content)
```

---

## 👁️ 视觉模型试用

### GLM-4V系列

**可用模型**:
- **GLM-4V** - 多模态视觉模型
- **GLM-4.6V** - 增强视觉理解
- **CogVLM** - 视觉语言模型

### 能力特点

```
✅ 图像理解
✅ OCR识别
✅ 表格提取
✅ 图表分析
✅ 截图理解
✅ UI界面分析
✅ 手写识别
✅ 复杂场景理解
```

### 试用方式

**在线试用**: 直接上传图片测试

**API调用**:
```python
from openai import OpenAI

client = OpenAI(
    api_key="your-free-trial-key",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)

response = client.chat.completions.create(
    model="glm-4v",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "描述这张图片"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://example.com/image.jpg"
                    }
                }
            ]
        }
    ]
)
```

---

## 🖼️ 图像模型试用

### CogView系列

**可用模型**:
- **CogView-3** - 图像生成
- **CogView-3-Plus** - 增强版
- **GLM-4V-Image** - 图像理解

### 能力特点

```
✅ 文生图
✅ 图像编辑
✅ 图像风格化
✅ 高清生成
✅ 多样化输出
```

### 试用方式

**在线试用**:
- 输入提示词
- 选择风格
- 生成图像

**API调用**:
```python
import requests

url = "https://open.bigmodel.cn/api/paas/v4/images/generations"

headers = {
    "Authorization": "Bearer your-free-trial-key",
    "Content-Type": "application/json"
}

data = {
    "model": "cogview-3",
    "prompt": "一只可爱的猫",
    "size": "1024x1024"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

---

## 🎬 视频模型试用

### CogVideo系列

**可用模型**:
- **CogVideoX** - 视频生成
- **CogVideoX-2** - 增强版
- **CogVideoX-Pro** - 专业版

### 能力特点

```
✅ 文生视频
✅ 图生视频
✅ 默认6秒视频
✅ 风格参数
✅ 情感氛围
✅ 镜头运动
✅ 高清输出
```

### 参数配置

```python
data = {
    "model": "cogvideox",
    "prompt": "一只猫在花园里玩耍",
    "video_seconds": 6,  # 视频时长
    "style": "realistic",  # 风格
    "camera_movement": "pan"  # 镜头运动
}
```

---

## 🎤 语音模型试用

### GLM-4-Voice系列

**可用模型**:
- **GLM-4-Voice** - 情感语音模型
- **GLM-4-Voice-Emotional** - 情感增强
- **GLM-4-Voice-Realtime** - 实时语音

### 能力特点

```
✅ 端到端情感语音合成
✅ 多种音色
✅ 情感表达
✅ 实时通话
✅ 高音质
✅ 低延迟
```

### 试用方式

**在线试用**:
- 输入文本
- 选择音色
- 生成语音

**API调用**:
```python
import requests

url = "https://open.bigmodel.cn/api/paas/v4/audio/speech"

headers = {
    "Authorization": "Bearer your-free-trial-key",
    "Content-Type": "application/json"
}

data = {
    "model": "glm-4-voice",
    "input": "你好，欢迎使用智谱AI",
    "voice": "female_gentle"  # 音色选择
}

response = requests.post(url, headers=headers, json=data)

# 保存音频
with open("output.mp3", "wb") as f:
    f.write(response.content)
```

---

## 🚀 集成到灵知系统

### 配置多模态Provider

```python
# backend/services/evolution/free_token_pool.py

"glm_text_trial": ProviderConfig(
    name="GLM文本试用",
    api_key_env="GLM_TRIAL_API_KEY",
    api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
    model="glm-5.1",
    monthly_quota=1_000_000,  # 免费试用额度
    reset_period="monthly",
    priority=5,  # 作为补充
    strengths=["文本生成", "免费试用"],
),

"glm_vision": ProviderConfig(
    name="GLM视觉",
    api_key_env="GLM_TRIAL_API_KEY",
    api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
    model="glm-4v",
    monthly_quota=500_000,
    priority=6,
    strengths=["图像理解", "OCR", "多模态"],
),
```

### 添加到.env

```bash
# 智谱AI免费试用
GLM_TRIAL_API_KEY=your-trial-key
```

---

## 💡 使用策略

### 与GLM Coding Plan配合

```
优先级策略:
1. GLM Coding Plan (Pro) → 代码开发（优先）
2. GLM免费试用 → 实验性功能
3. 其他Provider → 补充
```

### 使用场景分配

**GLM Coding Plan (Pro)**:
- ✅ 代码生成
- ✅ 代码调试
- ✅ 代码审查
- ✅ 项目开发

**GLM免费试用**:
- ✅ 图像理解（GLM-4V）
- ✅ 视频生成（CogVideoX）
- ✅ 语音合成（GLM-4-Voice）
- ✅ 图像生成（CogView）
- ✅ 新功能测试

---

## 📊 试用限制

### 通用限制

```
⚠️ 速率限制: 存在（未公开具体数值）
⚠️ 并发限制: 较低
⚠️ 额度限制: 每日/每月限额
⚠️ 功能限制: 部分高级功能不可用
```

### 解决方案

```python
# 1. 添加重试机制
async def call_with_retry(prompt, max_retries=3):
    for i in range(max_retries):
        try:
            result = await code_development(prompt)
            return result
        except RateLimitError:
            if i < max_retries - 1:
                await asyncio.sleep(2 ** i)  # 指数退避
            else:
                raise

# 2. 使用多Provider
async def smart_call(prompt):
    # 优先试用
    result = await call_trial_model(prompt)
    if result["success"]:
        return result

    # Fallback到Coding Plan
    return await code_development(prompt)
```

---

## 🎯 快速开始

### 步骤1: 获取试用Key

1. 访问: https://bigmodel.cn/trialcenter
2. 选择模态（文本/视觉/图像/视频/语音）
3. 点击"立即试用"
4. 注册/登录
5. 获取API Key

### 步骤2: 配置到系统

```bash
# 添加到.env
echo "GLM_TRIAL_API_KEY=your-trial-key" >> .env
```

### 步骤3: 测试

```python
# 测试文本模型
from backend.services.ai_service import chat

response = await chat("你好")
print(response)
```

---

## 🔗 相关资源

### 官方链接
- **试用中心**: https://bigmodel.cn/trialcenter
- **开放平台**: https://open.bigmodel.cn/
- **官方文档**: https://docs.bigmodel.cn/

### 本地文档
- **GLM Coding Plan指南**: `docs/GLM_CODING_PLAN_RESOURCE_PACKAGES.md`
- **频率限制优化**: `docs/GLM_CODING_PLAN_RATE_LIMIT_OPTIMIZATION.md`

---

## ✅ 总结

### 免费资源总览

```
✅ 5大模态完全免费
✅ GLM-5.1最新旗舰
✅ 在线试用 + API
✅ 即开即用
✅ 无需订阅
```

### 最佳组合

```
开发主力:
• GLM Coding Plan (Pro) - 代码开发

免费补充:
• GLM免费试用 - 多模态能力
• 图像理解、视频生成、语音合成

效果:
• 最大化利用免费资源
• 覆盖所有开发场景
• 降低成本60-70%
```

### 下一步

1. ✅ 获取试用API Key
2. ✅ 配置到系统
3. ✅ 测试多模态功能
4. ✅ 与Coding Plan配合使用

---

**🎉 智谱AI免费试用中心 + GLM Coding Plan = 完整AI能力！**

**众智混元，万法灵通** ⚡🚀

---

**Sources:**
- [智谱AI开放平台](https://open.bigmodel.cn/)
- [智谱AI官网](https://www.zhipuai.cn/zh)
- [BigModel开放平台](https://bigmodel.cn/)
