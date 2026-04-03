"""Token池使用监控

记录各provider的使用情况、成功率、延迟等指标
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class CallRecord:
    """单次调用记录"""

    timestamp: datetime
    provider: str
    success: bool
    tokens: int
    latency_ms: int
    error: str = None
    prompt_length: int = 0


@dataclass
class ProviderStats:
    """Provider统计信息"""

    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_latency_ms: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    last_call: datetime = None
    last_success: datetime = None
    last_failure: datetime = None
    errors: Dict[str, int] = field(default_factory=dict)


class TokenMonitor:
    """Token池监控器"""

    def __init__(self, data_dir: str = "data/monitoring"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.records: List[CallRecord] = []
        self.stats: Dict[str, ProviderStats] = {}

        # 加载历史数据
        self._load_stats()

        # 启动定期保存
        asyncio.create_task(self._periodic_save())

    def record_call(
        self,
        provider: str,
        success: bool,
        tokens: int = 0,
        latency_ms: int = 0,
        error: str = None,
        prompt_length: int = 0,
    ):
        """记录一次API调用"""

        record = CallRecord(
            timestamp=datetime.now(),
            provider=provider,
            success=success,
            tokens=tokens,
            latency_ms=latency_ms,
            error=error,
            prompt_length=prompt_length,
        )

        self.records.append(record)

        # 更新统计
        if provider not in self.stats:
            self.stats[provider] = ProviderStats(name=provider)

        stats = self.stats[provider]
        stats.total_calls += 1

        if success:
            stats.successful_calls += 1
            stats.total_tokens += tokens
            stats.total_latency_ms += latency_ms
            stats.avg_latency_ms = stats.total_latency_ms / stats.successful_calls
            stats.success_rate = stats.successful_calls / stats.total_calls
            stats.last_success = record.timestamp
        else:
            stats.failed_calls += 1
            stats.success_rate = stats.successful_calls / stats.total_calls
            stats.last_failure = record.timestamp

            # 记录错误
            if error:
                stats.errors[error] = stats.errors.get(error, 0) + 1

        stats.last_call = record.timestamp

        logger.info(
            f"TokenMonitor: {provider} - "
            f"{'✅' if success else '❌'} - "
            f"{tokens} tokens, {latency_ms}ms"
        )

    def get_provider_stats(self, provider: str) -> ProviderStats:
        """获取provider统计"""
        return self.stats.get(provider, ProviderStats(name=provider))

    def get_all_stats(self) -> Dict[str, ProviderStats]:
        """获取所有provider统计"""
        return self.stats.copy()

    def get_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取指定时间范围内的汇总"""

        cutoff = datetime.now() - timedelta(hours=hours)
        recent_records = [r for r in self.records if r.timestamp >= cutoff]

        total_calls = len(recent_records)
        successful_calls = sum(1 for r in recent_records if r.success)
        total_tokens = sum(r.tokens for r in recent_records)
        total_latency = sum(r.latency_ms for r in recent_records if r.success)

        # 按provider统计
        provider_summary = {}
        for record in recent_records:
            if record.provider not in provider_summary:
                provider_summary[record.provider] = {
                    "calls": 0,
                    "successful": 0,
                    "tokens": 0,
                    "latency": 0,
                }

            summary = provider_summary[record.provider]
            summary["calls"] += 1
            if record.success:
                summary["successful"] += 1
                summary["tokens"] += record.tokens
                summary["latency"] += record.latency_ms

        # 计算平均值
        for summary in provider_summary.values():
            if summary["successful"] > 0:
                summary["avg_latency"] = summary["latency"] / summary["successful"]
                summary["success_rate"] = summary["successful"] / summary["calls"]
            else:
                summary["avg_latency"] = 0
                summary["success_rate"] = 0

        return {
            "period_hours": hours,
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": total_calls - successful_calls,
            "overall_success_rate": successful_calls / total_calls if total_calls > 0 else 0,
            "total_tokens": total_tokens,
            "avg_latency_ms": total_latency / successful_calls if successful_calls > 0 else 0,
            "providers": provider_summary,
        }

    def get_best_provider(self, metric: str = "success_rate") -> str:
        """获取表现最好的provider"""

        if not self.stats:
            return None

        # 按指标排序
        if metric == "success_rate":
            best = max(self.stats.items(), key=lambda x: x[1].success_rate)
        elif metric == "avg_latency":
            best = min(self.stats.items(), key=lambda x: x[1].avg_latency_ms)
        elif metric == "total_calls":
            best = max(self.stats.items(), key=lambda x: x[1].total_calls)
        else:
            best = None

        return best[0] if best else None

    def format_summary(self, hours: int = 24) -> str:
        """格式化汇总报告"""

        summary = self.get_summary(hours)

        lines = [
            "=" * 70,
            f"📊 Token池使用监控报告 ({hours}小时)",
            "=" * 70,
            "",
            "📈 总体统计:",
            f"  总调用次数: {summary['total_calls']:,}",
            f"  成功: {summary['successful_calls']:,}",
            f"  失败: {summary['failed_calls']:,}",
            f"  成功率: {summary['overall_success_rate']:.1%}",
            f"  Token使用: {summary['total_tokens']:,}",
            f"  平均延迟: {summary['avg_latency_ms']:.0f}ms",
            "",
            "🎯 Provider表现:",
        ]

        # 按成功率排序
        providers_sorted = sorted(
            summary["providers"].items(), key=lambda x: x[1]["success_rate"], reverse=True
        )

        for provider, stats in providers_sorted:
            lines.append(
                f"  {provider}: "
                f"{stats['calls']}次调用, "
                f"{stats['success_rate']:.0%}成功率, "
                f"{stats['avg_latency']:.0f}ms平均延迟, "
                f"{stats['tokens']:,} tokens"
            )

        lines.extend(
            [
                "",
                "🏆 最佳Provider:",
                f"  成功率最高: {self.get_best_provider('success_rate') or 'N/A'}",
                f"  延迟最低: {self.get_best_provider('avg_latency') or 'N/A'}",
                f"  使用最多: {self.get_best_provider('total_calls') or 'N/A'}",
                "",
                "=" * 70,
            ]
        )

        return "\n".join(lines)

    def _load_stats(self):
        """加载历史统计"""

        stats_file = self.data_dir / "token_stats.json"

        if stats_file.exists():
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for name, stats_data in data.items():
                    stats = ProviderStats(name=name)
                    stats.__dict__.update(stats_data)
                    self.stats[name] = stats

                logger.info(f"TokenMonitor: 已加载历史统计 ({len(self.stats)}个provider)")

            except Exception as e:
                logger.error(f"TokenMonitor: 加载历史统计失败 - {e}")

    def _save_stats(self):
        """保存统计到文件"""

        stats_file = self.data_dir / "token_stats.json"

        try:
            data = {}
            for name, stats in self.stats.items():
                # 转换datetime为字符串
                stats_dict = stats.__dict__.copy()
                for key, value in stats_dict.items():
                    if isinstance(value, datetime):
                        stats_dict[key] = value.isoformat()

                data[name] = stats_dict

            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info("TokenMonitor: 统计已保存")

        except Exception as e:
            logger.error(f"TokenMonitor: 保存统计失败 - {e}")

    async def _periodic_save(self):
        """定期保存统计"""

        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟保存一次
                self._save_stats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TokenMonitor: 定期保存失败 - {e}")

    def export_records(self, hours: int = 24) -> List[Dict[str, Any]]:
        """导出指定时间范围内的记录"""

        cutoff = datetime.now() - timedelta(hours=hours)
        recent_records = [r for r in self.records if r.timestamp >= cutoff]

        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "provider": r.provider,
                "success": r.success,
                "tokens": r.tokens,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "prompt_length": r.prompt_length,
            }
            for r in recent_records
        ]


# 全局单例
_token_monitor = None


def get_token_monitor() -> TokenMonitor:
    """获取Token监控器单例"""
    global _token_monitor
    if _token_monitor is None:
        _token_monitor = TokenMonitor()
    return _token_monitor
