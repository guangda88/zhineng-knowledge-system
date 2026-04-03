# 百度千帆API Key快速获取指南

**目标**: 5分钟获取API Key和100万tokens/月免费额度

---

## 步骤1: 注册/登录百度账号（1分钟）

```
1. 访问: https://cloud.baidu.com/
2. 点击右上角"登录"或"注册"
3. 推荐使用手机号注册（更快捷）
```

## 步骤2: 实名认证（3分钟）⚠️ 必需

```
1. 登录后进入控制台: https://console.bce.baidu.com/
2. 点击右上角头像 → "账号中心" → "实名认证"
3. 选择"个人认证"
4. 上传身份证正反面照片
5. 等待审核（通常1-5分钟，最长24小时）
```

**提示**: 不认证无法创建API Key

## 步骤3: 开通千帆平台（1分钟）

```
方式1: 直接访问（推荐）
1. 访问: https://cloud.baidu.com/product/wenxinworkshop
2. 点击"立即使用"
3. 同意服务协议
4. 等待开通（通常即时）

方式2: 从控制台开通
1. 在控制台产品列表中找到"人工智能"
2. 点击"千帆大模型平台"
3. 点击"开通服务"
```

## 步骤4: 创建API Key（2分钟）⭐ 关键步骤

```
1. 进入千帆控制台
   https://console.bce.baidu.com/qianfan/

2. 左侧菜单点击"API Key管理"
   或直接访问:
   https://console.bce.baidu.com/qianfan/iam/apiKey

3. 点击"创建API Key"按钮

4. 填写信息:
   - API Key名称: 灵知系统
   - 应用类型: 后端应用
   - 应用描述: 智能知识库系统

5. 点击"确认创建"

6. ⚠️ 立即复制保存（只显示一次！）
   - API Key: ak-xxxxxx...
   - Secret Key: sk-xxxxxx...

   建议保存到安全的地方，如密码管理器
```

## 步骤5: 领取免费额度（自动）

开通后自动获得：
- ✅ 100万tokens/月
- ✅ 永久免费（每月重置）
- ✅ 适用模型: ERNIE-Bot 4.0, 3.5, Speed, Tiny

## 步骤6: 配置到灵知系统

```bash
# 方式1: 添加到.env文件（推荐）
echo "QWEN_API_KEY=ak-你的API_Key" >> .env

# 方式2: 临时设置（当前会话）
export QWEN_API_KEY=ak-你的API_Key

# 方式3: 永久设置
echo 'export QWEN_API_KEY=ak-你的API_Key' >> ~/.bashrc
source ~/.bashrc
```

## 步骤7: 验证配置

```bash
# 运行测试脚本
python scripts/test_free_token_pool.py

# 应该看到:
# ✅ 千帆 测试成功
# ⏱️  延迟: XXXms
# 📝 响应: ...
```

---

## 常见问题

### Q: 必须实名认证吗？
A: 是的，不认证无法创建API Key

### Q: Secret Key丢失了怎么办？
A: 无法找回，必须删除旧Key重新创建

### Q: 免费额度用完会怎样？
A: 超出部分按¥0.004/千tokens计费，建议设置用量告警

### Q: 如何查看剩余额度？
A: 控制台 → "用量统计" 可查看详细使用情况

---

## 完成！🎉

您现在拥有：
- 100万tokens/月永久免费额度
- 可在灵知系统中直接使用
- 系统会自动智能调度和管理

**众智混元，万法灵通** ⚡🚀
