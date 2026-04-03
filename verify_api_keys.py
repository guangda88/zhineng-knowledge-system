#!/usr/bin/env python3
"""快速验证API Key配置"""
import os

from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

print("=" * 60)
print("✅ API Key配置验证")
print("=" * 60)
print()

# 检查各个API Key
api_keys = {
    "智谱GLM": "GLM_API_KEY",
    "GLM Coding Plan": "GLM_CODING_PLAN_KEY",
    "GLM 4.7 CC": "GLM_47_CC_KEY",
    "百度千帆": "QWEN_API_KEY",
    "豆包": "DOUBAO_API_KEY",
    "阿里百炼": "QWEN_DASHSCOPE_API_KEY",
    "阿里通义": "QWEN_CLI_API_KEY",
    "讯飞星火 APPID": "SPARK_APPID",
    "讯飞星火 Key": "SPARK_API_KEY",
    "混元 SecretId": "HUNYUAN_SECRET_ID",
    "混元 API Key": "HUNYUAN_API_KEY",
    "月之暗面 Kimi": "MOONSHOT_API_KEY",
    "Minimax": "MINIMAX_API_KEY",
    "DeepSeek": "DEEPSEEK_API_KEY",
}

configured = 0
total = len(api_keys)

for name, env_key in api_keys.items():
    value = os.getenv(env_key)
    if value and value != f"your_{env_key.lower()}_here":
        # 隐藏部分密钥保护隐私
        masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        print(f"✅ {name:<20} → {masked}")
        configured += 1
    else:
        print(f"❌ {name:<20} → 未配置")

print()
print("=" * 60)
print(f"配置完成度: {configured}/{total} ({configured/total*100:.1f}%)")
print("=" * 60)
print()

if configured >= 10:
    print("🎉 配置完成！您已拥有超过1000万tokens的免费额度！")
    print()
    print("📊 预估价值:")
    print("  • 永久免费: 450万tokens/月 = ¥635/月")
    print("  • 新用户试用: 1200万tokens = ¥750")
    print("  • 总价值: ¥1,385+")
    print()
    print("🧪 下一步: 运行完整测试")
    print("  python scripts/test_free_token_pool.py")
elif configured >= 5:
    print("⚠️  部分配置，建议完成所有配置以获得最大免费额度")
else:
    print("❌ 配置不完整，请检查.env文件")
