"""免费Token储蓄池实现

智能调度多个免费API provider，最大化利用免费额度

V1.3.0: 使用统一超时配置
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 导入统一超时配置
try:
    from backend.config.timeouts import OperationType, get_timeout

    USE_UNIFIED_TIMEOUTS = True
except ImportError:
    USE_UNIFIED_TIMEOUTS = False
    logger.warning("统一超时配置未启用，使用默认值")

# 导入监控器
try:
    from backend.services.evolution.token_monitor import get_token_monitor

    TOKEN_MONITOR_ENABLED = True
except ImportError:
    TOKEN_MONITOR_ENABLED = False
    logger.warning("TokenMonitor未启用，API调用不会被记录")


class TaskType(Enum):
    """任务类型"""

    GENERATION = "generation"  # 文本生成
    REASONING = "reasoning"  # 逻辑推理
    KNOWLEDGE = "knowledge"  # 知识检索
    TASK = "task"  # Agent任务
    RECOGNITION = "recognition"  # OCR/识别
    VOICE = "voice"  # 语音处理
    IMAGE = "image"  # 图像处理


@dataclass
class ProviderConfig:
    """Provider配置"""

    name: str
    api_key_env: str
    api_url: str
    model: str
    monthly_quota: int = 1_000_000
    new_user_quota: int = 0
    reset_period: str = "monthly"  # monthly, onetime
    priority: int = 99
    cost_per_1k: float = 0.0
    strengths: List[str] = field(default_factory=list)


@dataclass
class ProviderStatus:
    """Provider状态"""

    name: str
    available: bool = False
    monthly_used: int = 0
    monthly_remaining: int = 0
    daily_used: int = 0
    last_reset: datetime = None
    next_reset: datetime = None
    success_rate: float = 1.0
    avg_latency_ms: float = 0.0


class QuotaTracker:
    """额度追踪器"""

    def __init__(self):
        self.usage: Dict[str, Dict[str, int]] = {}  # {provider: {date: tokens}}

    def record_usage(self, provider: str, tokens: int, date: datetime.date = None):
        """记录使用量"""
        if date is None:
            date = datetime.now().date()

        if provider not in self.usage:
            self.usage[provider] = {}

        date_str = str(date)
        if date_str not in self.usage[provider]:
            self.usage[provider][date_str] = 0

        self.usage[provider][date_str] += tokens
        logger.info(f"{provider}: 使用 +{tokens} tokens")

    def get_monthly_usage(self, provider: str) -> int:
        """获取月度使用量"""
        if provider not in self.usage:
            return 0

        today = datetime.now().date()
        month_start = today.replace(day=1)

        total = 0
        for date_str, tokens in self.usage[provider].items():
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date >= month_start:
                total += tokens

        return total

    def get_daily_usage(self, provider: str) -> int:
        """获取今日使用量"""
        if provider not in self.usage:
            return 0

        today_str = str(datetime.now().date())
        return self.usage[provider].get(today_str, 0)


class FreeTokenPool:
    """免费Token储蓄池"""

    def __init__(self):
        # 初始化provider配置
        self.providers = self._init_providers()
        self.status = self._init_status()
        self.tracker = QuotaTracker()

        # 获取API密钥
        self._load_api_keys()

        # 初始化监控器
        self.monitor = None
        if TOKEN_MONITOR_ENABLED:
            try:
                self.monitor = get_token_monitor()
                logger.info("TokenMonitor已启用")
            except Exception as e:
                logger.warning(f"TokenMonitor初始化失败: {e}")

    def _init_providers(self) -> Dict[str, ProviderConfig]:
        """初始化provider配置"""

        return {
            # ========== 包月服务（最高优先级） ==========
            "glm_coding": ProviderConfig(
                name="GLM Coding Plan",
                api_key_env="GLM_CODING_PLAN_KEY",
                api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
                model="glm-4",
                monthly_quota=100_000_000,  # 包月，设置大额度
                reset_period="monthly",
                priority=0,  # 最高优先级
                strengths=["代码生成", "复杂推理", "开发调试"],
            ),
            # ========== 永久免费 ==========
            "glm": ProviderConfig(
                name="GLM",
                api_key_env="GLM_API_KEY",
                api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
                model="glm-4",
                monthly_quota=1_000_000,
                priority=1,
                strengths=["通用对话", "代码生成", "长文本"],
            ),
            "qwen": ProviderConfig(
                name="千帆",
                api_key_env="QWEN_API_KEY",
                api_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
                model="ernie-4.0",
                monthly_quota=1_000_000,
                priority=2,
                strengths=["知识问答", "中文理解"],
            ),
            "tongyi": ProviderConfig(
                name="通义千问",
                api_key_env="QWEN_DASHSCOPE_API_KEY",
                api_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                model="qwen-max",
                monthly_quota=1_000_000,
                priority=3,
                strengths=["长上下文", "多模态"],
            ),
            # ========== 新用户试用 ==========
            "deepseek": ProviderConfig(
                name="DeepSeek",
                api_key_env="DEEPSEEK_API_KEY",
                api_url="https://api.deepseek.com/v1/chat/completions",
                model="deepseek-chat",
                monthly_quota=5_000_000,
                reset_period="onetime",
                priority=1,
                cost_per_1k=0.001,
                strengths=["推理", "代码", "数学"],
            ),
            "hunyuan": ProviderConfig(
                name="混元",
                api_key_env="HUNYUAN_API_KEY",
                api_url="https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                model="hunyuan-lite",
                new_user_quota=1_000_000,
                reset_period="onetime",
                priority=4,
                strengths=["对话", "知识"],
            ),
            "doubao": ProviderConfig(
                name="豆包",
                api_key_env="DOUBAO_API_KEY",
                api_url="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                model="doubao-pro",
                new_user_quota=2_000_000,
                reset_period="onetime",
                priority=5,
                strengths=["实时响应", "高并发"],
            ),
        }

    def _init_status(self) -> Dict[str, ProviderStatus]:
        """初始化provider状态"""

        status = {}
        for name, config in self.providers.items():
            status[name] = ProviderStatus(
                name=name,
                monthly_remaining=config.monthly_quota,
                last_reset=datetime.now(),
                next_reset=self._calculate_next_reset(config.reset_period),
            )

        return status

    def _calculate_next_reset(self, reset_period: str) -> datetime:
        """计算下次重置时间"""
        if reset_period == "monthly":
            # 下个月1号
            today = datetime.now()
            next_month = today.replace(day=28) + timedelta(days=4)  # 确保跨月
            return next_month.replace(day=1, hour=0, minute=0, second=0)
        else:
            # 一次性额度，30天后
            return datetime.now() + timedelta(days=30)

    def _load_api_keys(self):
        """加载API密钥"""
        for name, config in self.providers.items():
            api_key = os.getenv(config.api_key_env)
            if api_key:
                self.status[name].available = True
                logger.info(f"{name}: API密钥已加载")
            else:
                self.status[name].available = False
                logger.warning(f"{name}: 未配置 {config.api_key_env}")

    async def select_provider(
        self,
        task_type: TaskType = TaskType.GENERATION,
        complexity: str = "medium",
        require_realtime: bool = False,
    ) -> Optional[str]:
        """选择最优provider

        策略：
        1. 可用性检查
        2. 剩余额度检查
        3. 优先级排序
        4. 任务匹配度
        """

        # 获取可用provider
        available = [
            (name, status)
            for name, status in self.status.items()
            if status.available and status.monthly_remaining > 1000  # 至少剩1000 tokens
        ]

        if not available:
            logger.error("没有可用的provider！")
            return None

        # 按优先级排序
        available.sort(key=lambda x: self.providers[x[0]].priority)

        # 考虑复杂度
        if complexity == "high":
            # 复杂任务 → 优先使用推理强的
            available.sort(key=lambda x: x[0] == "deepseek", reverse=True)
        elif complexity == "simple" and not require_realtime:
            # 简单任务 → 优先使用便宜的
            available.sort(key=lambda x: self.providers[x[0]].cost_per_1k)

        # 考虑剩余额度（负载均衡）
        available.sort(key=lambda x: x[1].monthly_remaining, reverse=True)

        # 选择最优
        selected_name = available[0][0]
        selected_status = available[0][1]

        logger.info(
            f"选择provider: {selected_name} "
            f"(剩余: {selected_status.monthly_remaining:,} tokens)"
        )

        return selected_name

    async def call_provider(
        self, provider_name: str, prompt: str, max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """调用provider"""

        if provider_name not in self.providers:
            return {"success": False, "error": f"未知provider: {provider_name}"}

        config = self.providers[provider_name]
        api_key = os.getenv(config.api_key_env)

        if not api_key:
            return {"success": False, "error": "未配置API密钥"}

        try:
            # 使用统一超时配置
            timeout = get_timeout(OperationType.AI_CHAT) if USE_UNIFIED_TIMEOUTS else 30.0

            async with httpx.AsyncClient(timeout=timeout) as client:
                headers = {"Content-Type": "application/json"}

                payload = {
                    "model": config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                }

                start_time = datetime.now()

                # 百度千帆使用access_token作为查询参数
                if provider_name == "qwen":
                    url = f"{config.api_url}?access_token={api_key}"
                else:
                    # 其他provider使用标准Bearer token
                    headers["Authorization"] = f"Bearer {api_key}"
                    url = config.api_url

                response = await client.post(url, headers=headers, json=payload)
                latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                if response.status_code == 200:
                    result = response.json()

                    # 处理不同的响应格式
                    content = None

                    # 格式1: 标准OpenAI格式
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"]
                    # 格式2: 百度千帆格式
                    elif "result" in result:
                        content = result["result"]
                    # 格式3: Minimax格式
                    elif "reply" in result:
                        content = result["reply"]
                    else:
                        logger.error(f"{provider_name}: 未知的响应格式 - {result}")
                        return {
                            "success": False,
                            "error": "Unknown response format",
                            "provider": provider_name,
                            "response": result,
                        }

                    # 估算token使用
                    input_tokens = len(prompt) // 2  # 粗略估算
                    output_tokens = len(content) // 2
                    total_tokens = input_tokens + output_tokens

                    # 记录使用量
                    self.tracker.record_usage(provider_name, total_tokens)
                    self.status[provider_name].monthly_used += total_tokens
                    self.status[provider_name].monthly_remaining -= total_tokens
                    self.status[provider_name].avg_latency_ms = latency_ms

                    logger.info(
                        f"{provider_name}: 成功 " f"({total_tokens} tokens, {latency_ms}ms)"
                    )

                    # 记录到监控器
                    if self.monitor:
                        self.monitor.record_call(
                            provider=provider_name,
                            success=True,
                            tokens=total_tokens,
                            latency_ms=latency_ms,
                            prompt_length=len(prompt),
                        )

                    return {
                        "success": True,
                        "content": content,
                        "provider": provider_name,
                        "tokens": total_tokens,
                        "latency_ms": latency_ms,
                    }
                else:
                    error_msg = response.text[:200]
                    logger.error(f"{provider_name}: HTTP {response.status_code} - {error_msg}")

                    # 记录到监控器
                    if self.monitor:
                        self.monitor.record_call(
                            provider=provider_name,
                            success=False,
                            error=f"HTTP {response.status_code}",
                            prompt_length=len(prompt),
                        )

                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "provider": provider_name,
                        "details": error_msg,
                    }

        except Exception as e:
            logger.error(f"{provider_name}: 调用失败 - {e}")

            # 记录到监控器
            if self.monitor:
                self.monitor.record_call(
                    provider=provider_name, success=False, error=str(e), prompt_length=len(prompt)
                )

            return {
                "success": False,
                "error": str(e),
                "provider": provider_name,
            }

    def get_pool_status(self) -> Dict:
        """获取储蓄池状态"""

        total_quota = sum(
            config.monthly_quota or config.new_user_quota for config in self.providers.values()
        )

        total_used = sum(status.monthly_used for status in self.status.values())

        total_remaining = total_quota - total_used

        return {
            "total_quota": total_quota,
            "total_used": total_used,
            "total_remaining": total_remaining,
            "usage_percentage": (total_used / total_quota * 100) if total_quota > 0 else 0,
            "providers": {
                name: {
                    "available": status.available,
                    "quota": self.providers[name].monthly_quota
                    or self.providers[name].new_user_quota,
                    "used": status.monthly_used,
                    "remaining": status.monthly_remaining,
                    "success_rate": status.success_rate,
                    "avg_latency_ms": status.avg_latency_ms,
                }
                for name, status in self.status.items()
            },
        }


# 全局单例
_free_token_pool = None


def get_free_token_pool() -> FreeTokenPool:
    """获取免费Token池单例"""
    global _free_token_pool
    if _free_token_pool is None:
        _free_token_pool = FreeTokenPool()
    return _free_token_pool


async def test_free_token_pool():
    """测试免费Token池"""

    print("\n" + "=" * 60)
    print("🚀 免费Token池测试")
    print("=" * 60)

    pool = get_free_token_pool()

    # 显示池状态
    status = pool.get_pool_status()
    print("\n📊 Token池状态:")
    print(f"总额度: {status['total_quota']:,} tokens")
    print(f"已使用: {status['total_used']:,} tokens")
    print(f"剩余: {status['total_remaining']:,} tokens")
    print(f"使用率: {status['usage_percentage']:.1f}%")

    # 选择provider
    print("\n🔍 选择最优provider...")
    provider = await pool.select_provider()

    if provider:
        print(f"✅ 选中: {provider}")

        # 测试调用
        print("\n🧪 测试调用...")
        result = await pool.call_provider(provider, "请用一句话介绍你自己。")

        if result["success"]:
            print("✅ 调用成功")
            print(f"📝 响应: {result['content'][:100]}...")
            print(f"📊 Token使用: {result['tokens']}")
            print(f"⏱️  延迟: {result['latency_ms']}ms")
        else:
            print(f"❌ 调用失败: {result['error']}")
    else:
        print("❌ 没有可用的provider")

    # 最终状态
    final_status = pool.get_pool_status()
    print("\n📊 最终状态:")
    for name, info in final_status["providers"].items():
        if info["available"]:
            print(f"  {name}: {info['remaining']:,} tokens 剩余")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_free_token_pool())
