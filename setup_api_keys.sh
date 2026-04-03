#!/bin/bash
# 免费API Keys一键配置脚本

echo "=============================================="
echo "🔑 免费API Keys配置助手"
echo "=============================================="
echo ""

# 备份现有配置
if [ -f .env ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ 已备份现有配置到 .env.backup.$(date +%Y%m%d_%H%M%S)"
    echo ""
fi

echo "📝 请按提示输入您的API Keys（直接回车跳过）"
echo "=============================================="
echo ""

# 读取API Keys
read -p "1. GLM API Key (智谱): " glm_key
read -p "2. 千帆 API Key (百度): " qwen_key
read -p "3. 通义千问 API Key (阿里): " dashscope_key
read -p "4. 360智脑 API Key: " zhihu_key
read -p "5. 讯飞星火 API Key: " spark_key
read -p "6. 混元 API Key (腾讯): " hunyuan_key
read -p "7. 豆包 API Key (字节): " doubao_key
read -p "8. Kimi API Key (月之暗面): " moonshot_key
read -p "9. Minimax API Key: " minimax_key

echo ""
echo "=============================================="
echo "💾 正在更新配置..."
echo "=============================================="
echo ""

# 更新.env文件
if [ -n "$glm_key" ]; then
    if grep -q "^GLM_API_KEY=" .env; then
        sed -i "s/^GLM_API_KEY=.*/GLM_API_KEY=$glm_key/" .env
    else
        echo "GLM_API_KEY=$glm_key" >> .env
    fi
    echo "✅ GLM API Key 已配置"
fi

if [ -n "$qwen_key" ]; then
    if grep -q "^QWEN_API_KEY=" .env; then
        sed -i "s/^QWEN_API_KEY=.*/QWEN_API_KEY=$qwen_key/" .env
    else
        echo "QWEN_API_KEY=$qwen_key" >> .env
    fi
    echo "✅ 千帆 API Key 已配置"
fi

if [ -n "$dashscope_key" ]; then
    if grep -q "^QWEN_DASHSCOPE_API_KEY=" .env; then
        sed -i "s/^QWEN_DASHSCOPE_API_KEY=.*/QWEN_DASHSCOPE_API_KEY=$dashscope_key/" .env
    else
        echo "QWEN_DASHSCOPE_API_KEY=$dashscope_key" >> .env
    fi
    echo "✅ 通义千问 API Key 已配置"
fi

if [ -n "$zhihu_key" ]; then
    if grep -q "^ZHIHU_API_KEY=" .env; then
        sed -i "s/^ZHIHU_API_KEY=.*/ZHIHU_API_KEY=$zhihu_key/" .env
    else
        echo "ZHIHU_API_KEY=$zhihu_key" >> .env
    fi
    echo "✅ 360智脑 API Key 已配置"
fi

if [ -n "$spark_key" ]; then
    if grep -q "^SPARK_API_KEY=" .env; then
        sed -i "s/^SPARK_API_KEY=.*/SPARK_API_KEY=$spark_key/" .env
    else
        echo "SPARK_API_KEY=$spark_key" >> .env
    fi
    echo "✅ 讯飞星火 API Key 已配置"
fi

if [ -n "$hunyuan_key" ]; then
    if grep -q "^HUNYUAN_API_KEY=" .env; then
        sed -i "s/^HUNYUAN_API_KEY=.*/HUNYUAN_API_KEY=$hunyuan_key/" .env
    else
        echo "HUNYUAN_API_KEY=$hunyuan_key" >> .env
    fi
    echo "✅ 混元 API Key 已配置"
fi

if [ -n "$doubao_key" ]; then
    if grep -q "^DOUBAO_API_KEY=" .env; then
        sed -i "s/^DOUBAO_API_KEY=.*/DOUBAO_API_KEY=$doubao_key/" .env
    else
        echo "DOUBAO_API_KEY=$doubao_key" >> .env
    fi
    echo "✅ 豆包 API Key 已配置"
fi

if [ -n "$moonshot_key" ]; then
    if grep -q "^MOONSHOT_API_KEY=" .env; then
        sed -i "s/^MOONSHOT_API_KEY=.*/MOONSHOT_API_KEY=$moonshot_key/" .env
    else
        echo "MOONSHOT_API_KEY=$moonshot_key" >> .env
    fi
    echo "✅ Kimi API Key 已配置"
fi

if [ -n "$minimax_key" ]; then
    if grep -q "^MINIMAX_API_KEY=" .env; then
        sed -i "s/^MINIMAX_API_KEY=.*/MINIMAX_API_KEY=$minimax_key/" .env
    else
        echo "MINIMAX_API_KEY=$minimax_key" >> .env
    fi
    echo "✅ Minimax API Key 已配置"
fi

echo ""
echo "=============================================="
echo "✅ 配置完成！"
echo "=============================================="
echo ""
echo "🧪 运行测试验证配置："
echo "python scripts/test_free_token_pool.py"
echo ""
