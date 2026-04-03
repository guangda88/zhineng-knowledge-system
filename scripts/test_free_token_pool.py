#!/usr/bin/env python3
"""免费Token池测试脚本

测试所有可用的免费API provider
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 添加backend到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class FreeTokenPoolTester:
    """免费Token池测试器"""

    def __init__(self):
        self.results = {}

    async def test_provider(
        self,
        name: str,
        api_key_env: str,
        api_url: str,
        test_prompt: str = "你好，请用一句话介绍自己。",
    ) -> Dict[str, Any]:
        """测试单个provider"""

        print(f"\n{'='*60}")
        print(f"🧪 测试 {name.upper()}")
        print("=" * 60)

        api_key = os.getenv(api_key_env)

        if not api_key:
            print(f"⚠️  未配置 {api_key_env}")
            return {"name": name, "success": False, "error": "未配置API密钥"}

        print(f"✅ 已配置 {api_key_env}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

                payload = {
                    "model": self.get_model_name(name),
                    "messages": [{"role": "user", "content": test_prompt}],
                    "max_tokens": 100,
                }

                start_time = datetime.now()

                response = await client.post(api_url, headers=headers, json=payload)

                latency = int((datetime.now() - start_time).total_seconds() * 1000)

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]

                    print(f"✅ {name} 测试成功")
                    print(f"⏱️  延迟: {latency}ms")
                    print(f"📝 响应: {content[:100]}...")

                    return {
                        "name": name,
                        "success": True,
                        "latency_ms": latency,
                        "response_preview": content[:100],
                    }
                else:
                    print(f"❌ HTTP {response.status_code}")
                    print(f"错误: {response.text[:200]}")

                    return {"name": name, "success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return {"name": name, "success": False, "error": str(e)}

    def get_model_name(self, provider: str) -> str:
        """获取provider的默认模型"""

        models = {
            "glm": "glm-4",
            "qwen": "qwen-max",
            "ernie": "ernie-4.0",
            "spark": "spark-4.0",
            "zhihu": "360GPT",
            "deepseek": "deepseek-chat",
            "hunyuan": "hunyuan-lite",
            "doubao": "ep-20241105111448-l7jgz",
            "moonshot": "moonshot-v1-8k",
            "minimax": "abab6.5s-chat",
        }

        return models.get(provider, "default")

    async def test_all_providers(self):
        """测试所有provider"""

        # 永久免费/月
        permanent_free = [
            (
                "GLM",
                "GLM_API_KEY",
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                "智谱AI - 100万tokens/月",
            ),
            (
                "千帆",
                "QWEN_API_KEY",
                "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
                "百度千帆 - 100万tokens/月",
            ),
            (
                "通义千问",
                "QWEN_DASHSCOPE_API_KEY",
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "阿里通义 - 100万tokens/月",
            ),
            (
                "360智脑",
                "ZHIHU_API_KEY",
                "https://api.360.cn/v1/chat/completions",
                "360智脑 - 100万tokens/月",
            ),
            (
                "讯飞星火",
                "SPARK_API_KEY",
                "https://spark-api.xf-yun.com/v1/chat/completions",
                "讯飞星火 - 50万tokens/月",
            ),
        ]

        # 新用户试用
        new_user_trials = [
            (
                "DeepSeek",
                "DEEPSEEK_API_KEY",
                "https://api.deepseek.com/v1/chat/completions",
                "DeepSeek - 500万tokens 30天",
            ),
            (
                "混元",
                "HUNYUAN_API_KEY",
                "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                "腾讯混元 - 100万tokens 30天",
            ),
            (
                "豆包",
                "DOUBAO_API_KEY",
                "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                "字节豆包 - 200万tokens 30天",
            ),
            (
                "Moonshot",
                "MOONSHOT_API_KEY",
                "https://api.moonshot.cn/v1/chat/completions",
                "Kimi月之暗面 - 300万tokens 30天",
            ),
            (
                "Minimax",
                "MINIMAX_API_KEY",
                "https://api.minimax.chat/v1/text/chatcompletion_v2",
                "Minimax - 100万tokens 60天",
            ),
        ]

        all_providers = permanent_free + new_user_trials

        tasks = []
        for name, env_key, url, description in all_providers:
            print(f"\n📋 {description}")
            task = self.test_provider(name.lower(), env_key, url)
            tasks.append(task)

        # 并行测试
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        for result in results:
            if isinstance(result, dict):
                self.results[result["name"]] = result

    def print_summary(self):
        """打印测试总结"""

        print(f"\n{'='*60}")
        print("📊 免费Token池测试总结")
        print("=" * 60)

        total = len(self.results)
        success = sum(1 for r in self.results.values() if r.get("success"))
        failed = total - success

        print(f"\n总计: {total} 个provider")
        print(f"✅ 成功: {success} 个")
        print(f"❌ 失败: {failed} 个")
        print(f"成功率: {success/total*100:.1f}%")

        # 详细结果
        print(f"\n详细结果:")
        print(f"{'Provider':<15} {'状态':<8} {'延迟':<10} {'说明'}")
        print("-" * 60)

        for name, result in sorted(self.results.items()):
            status = "✅ 成功" if result.get("success") else "❌ 失败"
            latency = f"{result.get('latency_ms', 0)}ms" if result.get("success") else "-"
            error = result.get("error", "")[:30]

            print(f"{name:<15} {status:<8} {latency:<10} {error}")

        # 可用额度
        print(f"\n💰 可用免费额度:")

        if success >= 3:
            print(f"✅ 已配置 {success} 个provider")
            print(f"✅ 预计月度免费额度: {success * 100}万tokens")
            print(f"✅ 预计价值: ¥{success * 160}")
        else:
            print(f"⚠️  仅配置 {success} 个provider，建议至少配置3个")

        print(f"\n💡 下一步:")
        print(f"   1. 参考 docs/FREE_TOKEN_POOL_DESIGN.md")
        print(f"   2. 注册永久免费API（GLM、千帆、通义等）")
        print(f"   3. 注册新用户额度（DeepSeek、混元、豆包等）")
        print(f"   4. 总计可获得 3650万tokens/月 免费额度")

        print(f"\n{'='*60}\n")

    async def test_quota_status(self):
        """测试额度状态"""

        print(f"\n{'='*60}")
        print("📊 额度状态检查")
        print("=" * 60)

        # 这里可以添加实际的额度查询逻辑
        # 目前只显示配置的provider

        providers = {
            "GLM": {"quota": 1_000_000, "period": "月"},
            "千帆": {"quota": 1_000_000, "period": "月"},
            "通义千问": {"quota": 1_000_000, "period": "月"},
            "DeepSeek": {"quota": 5_000_000, "period": "30天"},
            "混元": {"quota": 1_000_000, "period": "30天"},
            "豆包": {"quota": 2_000_000, "period": "30天"},
        }

        print(f"\n{'Provider':<15} {'免费额度':<15} {'周期':<10} {'状态'}")
        print("-" * 60)

        for name, config in providers.items():
            env_key = f"{name.upper().replace(' ', '_')}_API_KEY"
            configured = os.getenv(env_key) is not None
            status = "✅ 已配置" if configured else "⚠️  未配置"

            print(f"{name:<15} {config['quota']:,} tokens   {config['period']:<10} {status}")


async def main():
    """主函数"""

    print("\n" + "=" * 60)
    print("🚀 免费Token池测试脚本")
    print("=" * 60)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tester = FreeTokenPoolTester()

    # 1. 测试所有provider
    await tester.test_all_providers()

    # 2. 打印总结
    tester.print_summary()

    # 3. 显示额度状态
    await tester.test_quota_status()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
