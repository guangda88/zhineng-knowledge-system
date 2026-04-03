#!/bin/bash
# 百度千帆API Key配置验证脚本

echo "================================================"
echo "🔍 百度千帆API Key 配置检查"
echo "================================================"
echo ""

# 检查.env文件
if [ ! -f .env ]; then
    echo "❌ .env 文件不存在"
    exit 1
fi

# 检查QWEN_API_KEY
if grep -q "QWEN_API_KEY=your_qwen_api_key_here" .env; then
    echo "❌ QWEN_API_KEY 未配置（仍是占位符）"
    echo ""
    echo "📝 请按以下步骤配置："
    echo "1. 访问: https://console.bce.baidu.com/qianfan/iam/apiKey"
    echo "2. 创建API Key"
    echo "3. 运行: nano .env"
    echo "4. 替换 your_qwen_api_key_here 为您的真实密钥"
    echo "5. 保存后运行此脚本验证"
    exit 1
elif grep -q "^QWEN_API_KEY=ak-" .env; then
    API_KEY=$(grep "^QWEN_API_KEY=ak-" .env | cut -d'=' -f2)
    echo "✅ QWEN_API_KEY 已配置"
    echo "🔑 密钥: ${API_KEY:0:20}..."
    echo ""

    # 运行测试
    echo "🧪 运行测试..."
    python scripts/test_free_token_pool.py 2>&1 | grep -A 10 "千帆"
else
    echo "⚠️  QWEN_API_KEY 配置可能不正确"
    echo "请检查.env文件中的配置"
    exit 1
fi

echo ""
echo "================================================"
echo "✅ 配置完成！"
echo "================================================"
