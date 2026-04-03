# API测试报告

**测试时间**: 2026-04-01 18:56:57
**测试状态**: ✅ 部分完成

---

## 📊 测试结果总览

| Provider | 状态 | 延迟 | 说明 |
|----------|------|------|------|
| GLM (智谱) | ✅ 成功 | 1025ms | 完美运行 |
| DeepSeek | ✅ 成功 | 2530ms | 完美运行 |
| 千帆 | ⚠️ 格式问题 | - | 已修复响应解析 |
| 通义千问 | ❌ HTTP 404 | - | 模型名称错误 |
| 讯飞星火 | ❌ HTTP 401 | - | 认证方式错误 |
| 混元 | ❌ HTTP 400 | - | 模型名称错误 |
| 豆包 | ❌ HTTP 404 | - | 模型名称错误 |
| Moonshot | ❌ HTTP 429 | - | 账户余额不足 |
| Minimax | ❌ NoneType | - | 响应格式问题 |
| 360智脑 | ❌ 未配置 | - | 缺失API Key |

**成功率**: 2/10 (20%)
**可用额度**: 600万tokens (GLM 100万 + DeepSeek 500万)

---

## ✅ 可用Provider

### 1. GLM (智谱AI)
- **状态**: ✅ 完全可用
- **延迟**: 1025ms
- **免费额度**: 100万tokens/月
- **模型**: glm-4
- **适用场景**: 通用对话、代码生成、长文本

### 2. DeepSeek
- **状态**: ✅ 完全可用
- **延迟**: 2530ms
- **免费额度**: 500万tokens (30天)
- **模型**: deepseek-chat
- **适用场景**: 复杂推理、数学、代码

---

## ⚠️ 需要修复的Provider

### 1. 千帆 (百度)
**问题**: 响应格式不同
**修复**: ✅ 已在free_token_pool.py中修复
**状态**: 待重新测试

**修复内容**:
```python
# 支持千帆格式: {"result": "...", "usage": {...}}
elif "result" in result:
    content = result["result"]
```

### 2. 通义千问 (阿里)
**问题**: HTTP 404 - 模型名称错误
**需要**: 修正模型名称映射

**当前配置**:
```python
model="ernie-4.0"  # 错误！这是千帆的模型名
```

**应该改为**:
```python
model="qwen-max"  # 通义千问的正确模型名
```

### 3. 讯飞星火
**问题**: HTTP 401 - 认证失败
**需要**: 使用正确的认证方式

**讯飞使用API Key而非Bearer token**:
```python
headers = {
    "Authorization": api_key,  # 直接使用API Key
    "Content-Type": "application/json"
}
```

### 4. 混元 (腾讯)
**问题**: HTTP 400 - 模型不存在
**需要**: 修正模型名称

### 5. 豆包 (字节)
**问题**: HTTP 404 - 模型不存在
**需要**: 使用正确的endpoint ID

### 6. Moonshot (Kimi)
**问题**: HTTP 429 - 账户余额不足
**需要**: 充值或检查账户状态

### 7. Minimax
**问题**: 响应格式解析失败
**修复**: ✅ 已在free_token_pool.py中添加Minimax格式支持

### 8. 360智脑
**问题**: 未配置API Key
**需要**: 用户申请并配置

---

## 🔧 已实施的修复

### 1. 响应格式统一处理

**位置**: `backend/services/evolution/free_token_pool.py`

**修复内容**:
```python
# 支持多种响应格式
if "choices" in result:  # OpenAI标准格式
    content = result["choices"][0]["message"]["content"]
elif "result" in result:  # 百度千帆格式
    content = result["result"]
elif "reply" in result:  # Minimax格式
    content = result["reply"]
```

### 2. 测试脚本修复

**位置**: `scripts/test_free_token_pool.py`

**修复内容**:
```python
from dotenv import load_dotenv
load_dotenv()  # 加载.env文件
```

---

## 📋 待办事项

### P0 - 立即修复
- [ ] 修正通义千问模型名称 (`ernie-4.0` → `qwen-max`)
- [ ] 修正讯飞星火认证方式
- [ ] 修正混元模型名称
- [ ] 修正豆包endpoint ID

### P1 - 本周完成
- [ ] 重新测试所有provider
- [ ] 配置360智脑API Key
- [ ] 检查Moonshot账户状态

### P2 - 可选
- [ ] 优化模型配置
- [ ] 添加重试机制
- [ ] 实现fallback逻辑

---

## 💡 建议

### 当前可用策略

立即可用2个provider，已足够启动：

```python
# 策略1: 优先使用GLM (永久免费，延迟低)
provider = "glm"  # 1025ms, 100万/月

# 策略2: 复杂任务使用DeepSeek (推理强)
provider = "deepseek"  # 2530ms, 500万/30天

# 智能选择
if complexity == "high":
    provider = "deepseek"
else:
    provider = "glm"
```

### 免费额度利用

**当前可用**:
- GLM: 100万tokens/月 = ¥160
- DeepSeek: 500万tokens = ¥50
- **总计**: 600万tokens = ¥210

**待解锁**:
- 千帆: 100万/月 = ¥150 (已修复，待测试)
- 通义: 100万/月 = ¥150 (需修正模型名)
- 混元: 100万/30天 = ¥80 (需修正模型名)
- 豆包: 200万/30天 = ¥240 (需修正endpoint)

---

## 🎯 下一步

1. **修正模型配置** - 更新provider配置中的模型名称
2. **重新测试** - 运行 `python scripts/test_free_token_pool.py`
3. **启用Token池** - 在实际业务中使用可用的2个provider
4. **监控使用** - 记录调用统计和性能指标

---

**报告生成**: 2026-04-01
**下次测试**: 修复完成后
