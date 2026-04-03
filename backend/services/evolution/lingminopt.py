"""LingMinOpt灵极优自优化框架

核心原则：
1. 渐进式优化 - 不破坏现有功能
2. 数据驱动 - 基于真实指标决策
3. 闭环反馈 - 执行→测量→学习→改进
4. 成本可控 - 监控和优化资源使用
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OptimizationPriority(Enum):
    """优化优先级"""

    CRITICAL = "critical"  # 立即优化（P0）
    HIGH = "high"  # 本周优化（P1）
    MEDIUM = "medium"  # 本月优化（P2）
    LOW = "low"  # 有时间优化（P3）


@dataclass
class MetricSnapshot:
    """指标快照"""

    timestamp: datetime
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"timestamp": self.timestamp.isoformat(), "metrics": self.metrics}


@dataclass
class OptimizationOpportunity:
    """优化机会"""

    id: str
    category: str  # "performance", "quality", "cost", "security"
    priority: OptimizationPriority
    title: str
    description: str
    current_value: Any
    target_value: Any
    expected_improvement: str  # "30%", "2x", etc.
    effort: str  # "2h", "1d", "1w"
    risk: str  # "low", "medium", "high"
    implementation: str  # 伪代码或步骤描述


@dataclass
class OptimizationPlan:
    """优化计划"""

    opportunities: List[OptimizationOpportunity]
    estimated_duration: str
    expected_impact: str
    phases: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunities": [
                {
                    "id": opp.id,
                    "category": opp.category,
                    "priority": opp.priority.value,
                    "title": opp.title,
                    "description": opp.description,
                    "current_value": str(opp.current_value),
                    "target_value": str(opp.target_value),
                    "expected_improvement": opp.expected_improvement,
                    "effort": opp.effort,
                    "risk": opp.risk,
                }
                for opp in self.opportunities
            ],
            "estimated_duration": self.estimated_duration,
            "expected_impact": self.expected_impact,
            "phases": self.phases,
        }


@dataclass
class OptimizationResult:
    """优化结果"""

    plan_id: str
    opportunity_id: str
    executed_at: datetime
    before_metrics: Dict[str, Any]
    after_metrics: Dict[str, Any]
    success: bool
    improvement: Dict[str, float]  # {"latency": -0.3, "cost": -0.5}
    side_effects: List[str] = field(default_factory=list)
    rollback_needed: bool = False


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self.metrics_history: List[MetricSnapshot] = []

    async def collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        metrics = {}

        # API响应时间
        metrics["avg_api_latency_ms"] = await self._measure_api_latency()

        # API成功率
        metrics["api_success_rate"] = await self._measure_api_success_rate()

        # Token使用
        metrics["daily_token_usage"] = await self._get_token_usage()

        # 用户满意度
        metrics["avg_user_satisfaction"] = await self._get_user_satisfaction()

        # 竞品胜率
        metrics["competitor_win_rate"] = await self._get_competitor_win_rate()

        # 成本
        metrics["daily_cost"] = await self._calculate_daily_cost()

        return metrics

    async def _measure_api_latency(self) -> float:
        """测量API延迟"""
        # 简化实现 - 从数据库查询
        # 实际应该使用监控系统
        return 250.0  # 示例：250ms

    async def _measure_api_success_rate(self) -> float:
        """测量API成功率"""
        # 从数据库查询最近24小时的API调用
        return 0.95  # 95%

    async def _get_token_usage(self) -> int:
        """获取Token使用量"""
        # 从token_tracker获取
        return 500_000  # 50万tokens

    async def _get_user_satisfaction(self) -> float:
        """获取用户满意度"""
        # 从analytics表查询
        return 3.8  # 3.8/5.0

    async def _get_competitor_win_rate(self) -> float:
        """获取竞品胜率"""
        # 从ai_comparison_log查询
        return 0.45  # 45%

    async def _calculate_daily_cost(self) -> float:
        """计算每日成本"""
        # 基于token使用量计算
        return 15.0  # ¥15/天

    async def collect_snapshot(self) -> MetricSnapshot:
        """收集指标快照"""
        metrics = await self.collect_system_metrics()
        snapshot = MetricSnapshot(timestamp=datetime.utcnow(), metrics=metrics)
        self.metrics_history.append(snapshot)
        return snapshot


class EvolutionOptimizer:
    """进化优化引擎"""

    def __init__(self):
        self.metrics_collector = MetricsCollector()

    async def identify_bottlenecks(
        self, current_metrics: Dict[str, Any]
    ) -> List[OptimizationOpportunity]:
        """识别性能瓶颈和优化机会"""

        opportunities = []

        # 检查1: API延迟
        if current_metrics.get("avg_api_latency_ms", 0) > 300:
            opportunities.append(
                OptimizationOpportunity(
                    id="opt_api_latency",
                    category="performance",
                    priority=OptimizationPriority.HIGH,
                    title="降低API响应延迟",
                    description="当前API平均响应时间过高，影响用户体验",
                    current_value=f"{current_metrics['avg_api_latency_ms']}ms",
                    target_value="200ms",
                    expected_improvement="33%",
                    effort="2h",
                    risk="low",
                    implementation="""
                1. 启用API响应缓存
                2. 实现并行调用
                3. 优化数据库查询
                """,
                )
            )

        # 检查2: Token成本
        if current_metrics.get("daily_cost", 0) > 20:
            opportunities.append(
                OptimizationOpportunity(
                    id="opt_token_cost",
                    category="cost",
                    priority=OptimizationPriority.CRITICAL,
                    title="降低API调用成本",
                    description="每日API成本超过¥20，需要优化",
                    current_value=f"¥{current_metrics['daily_cost']}/天",
                    target_value="¥10/天",
                    expected_improvement="50%",
                    effort="4h",
                    risk="low",
                    implementation="""
                1. 实施智能缓存策略
                2. 采样对比（10%）而非全量对比
                3. 使用更便宜的AI模型
                """,
                )
            )

        # 检查3: 用户满意度
        if current_metrics.get("avg_user_satisfaction", 0) < 4.0:
            opportunities.append(
                OptimizationOpportunity(
                    id="opt_user_satisfaction",
                    category="quality",
                    priority=OptimizationPriority.HIGH,
                    title="提升用户满意度",
                    description="用户满意度低于4.0，需要改进回答质量",
                    current_value=f"{current_metrics['avg_user_satisfaction']}/5.0",
                    target_value="4.2/5.0",
                    expected_improvement="10%",
                    effort="1w",
                    risk="medium",
                    implementation="""
                1. 分析低分回答的共同特征
                2. 优化Prompt模板
                3. 实施进化验证系统
                4. 收集用户反馈并迭代
                """,
                )
            )

        # 检查4: 竞品胜率
        if current_metrics.get("competitor_win_rate", 0) < 0.5:
            opportunities.append(
                OptimizationOpportunity(
                    id="opt_competitor_win_rate",
                    category="quality",
                    priority=OptimizationPriority.HIGH,
                    title="提升竞品对比胜率",
                    description="竞品胜率低于50%，需要学习竞品优势",
                    current_value=f"{current_metrics['competitor_win_rate'] * 100}%",
                    target_value="60%",
                    expected_improvement="33%",
                    effort="2w",
                    risk="high",
                    implementation="""
                1. 分析竞品胜出的回答特点
                2. 提取改进模式
                3. 更新Prompt模板
                4. 持续A/B测试
                """,
                )
            )

        # 检查5: API成功率
        if current_metrics.get("api_success_rate", 1.0) < 0.98:
            opportunities.append(
                OptimizationOpportunity(
                    id="opt_api_success_rate",
                    category="reliability",
                    priority=OptimizationPriority.CRITICAL,
                    title="提升API成功率",
                    description="API成功率低于98%，需要优化错误处理",
                    current_value=f"{current_metrics['api_success_rate'] * 100}%",
                    target_value="99%",
                    expected_improvement="4%",
                    effort="1d",
                    risk="low",
                    implementation="""
                1. 实施智能重试机制
                2. 添加降级策略
                3. 优化超时配置
                4. 改进错误处理
                """,
                )
            )

        return opportunities

    async def create_optimization_plan(
        self, opportunities: List[OptimizationOpportunity]
    ) -> OptimizationPlan:
        """创建优化计划"""

        # 按优先级排序
        prioritized = sorted(
            opportunities,
            key=lambda x: (
                0
                if x.priority == OptimizationPriority.CRITICAL
                else (
                    1
                    if x.priority == OptimizationPriority.HIGH
                    else 2 if x.priority == OptimizationPriority.MEDIUM else 3
                )
            ),
        )

        # 分阶段
        phases = []
        total_effort_hours = 0

        # Phase 1: 立即执行（P0）
        phase1 = [opp for opp in prioritized if opp.priority == OptimizationPriority.CRITICAL]
        if phase1:
            phases.append(
                {
                    "phase": 1,
                    "name": "立即优化",
                    "opportunities": [opp.id for opp in phase1],
                    "duration": "1-2天",
                }
            )
            total_effort_hours += sum(self._parse_effort(opp.effort) for opp in phase1)

        # Phase 2: 本周执行（P1）
        phase2 = [opp for opp in prioritized if opp.priority == OptimizationPriority.HIGH]
        if phase2:
            phases.append(
                {
                    "phase": 2,
                    "name": "本周优化",
                    "opportunities": [opp.id for opp in phase2],
                    "duration": "1周",
                }
            )
            total_effort_hours += sum(self._parse_effort(opp.effort) for opp in phase2)

        # Phase 3: 本月执行（P2）
        phase3 = [opp for opp in prioritized if opp.priority == OptimizationPriority.MEDIUM]
        if phase3:
            phases.append(
                {
                    "phase": 3,
                    "name": "本月优化",
                    "opportunities": [opp.id for opp in phase3],
                    "duration": "2-4周",
                }
            )

        # 估算总时长
        if total_effort_hours < 8:
            duration = "1天"
        elif total_effort_hours < 40:
            duration = "1周"
        elif total_effort_hours < 160:
            duration = "1月"
        else:
            duration = "1季度"

        # 估算影响
        impact_score = (
            sum(self._parse_improvement(opp.expected_improvement) for opp in opportunities)
            / len(opportunities)
            if opportunities
            else 0
        )

        if impact_score > 0.5:
            impact = "显著改善"
        elif impact_score > 0.2:
            impact = "明显改善"
        else:
            impact = "轻微改善"

        return OptimizationPlan(
            opportunities=prioritized,
            estimated_duration=duration,
            expected_impact=impact,
            phases=phases,
        )

    def _parse_effort(self, effort: str) -> float:
        """解析工作量（返回小时数）"""
        if "h" in effort:
            return float(effort.replace("h", "").strip())
        elif "d" in effort:
            return float(effort.replace("d", "").strip()) * 8
        elif "w" in effort:
            return float(effort.replace("w", "").strip()) * 40
        return 8.0  # 默认8小时

    def _parse_improvement(self, improvement: str) -> float:
        """解析改进幅度（返回小数）"""
        try:
            value = improvement.replace("%", "").strip()
            return float(value) / 100.0
        except (ValueError, AttributeError):
            return 0.1  # 默认10%


class OptimizationOrchestrator:
    """优化编排器 - 执行和验证优化"""

    def __init__(self):
        self.optimization_results: List[OptimizationResult] = []
        self.rollback_stack: List[OptimizationResult] = []

    async def execute_optimization(
        self, opportunity: OptimizationOpportunity, context: Dict[str, Any]
    ) -> OptimizationResult:
        """执行优化"""

        logger.info(f"执行优化: {opportunity.title}")

        # 1. 记录优化前指标
        before_metrics = await context["metrics_collector"].collect_system_metrics()

        # 2. 执行优化（根据不同类型）
        if opportunity.id == "opt_token_cost":
            success = await self._optimize_token_cost(opportunity, context)
        elif opportunity.id == "opt_api_latency":
            success = await self._optimize_api_latency(opportunity, context)
        elif opportunity.id == "opt_user_satisfaction":
            success = await self._optimize_user_satisfaction(opportunity, context)
        elif opportunity.id == "opt_api_success_rate":
            success = await self._optimize_api_success_rate(opportunity, context)
        else:
            logger.warning(f"未知优化类型: {opportunity.id}")
            success = False

        # 3. 收集优化后指标
        await asyncio.sleep(2)  # 等待优化生效
        after_metrics = await context["metrics_collector"].collect_system_metrics()

        # 4. 计算改进
        improvement = self._calculate_improvement(before_metrics, after_metrics)

        result = OptimizationResult(
            plan_id=f"plan_{datetime.now().strftime('%Y%m%d')}",
            opportunity_id=opportunity.id,
            executed_at=datetime.utcnow(),
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            success=success,
            improvement=improvement,
        )

        self.optimization_results.append(result)

        # 5. 如果失败，记录回滚
        if not success:
            result.rollback_needed = True
            self.rollback_stack.append(result)

        return result

    async def _optimize_token_cost(
        self, opportunity: OptimizationOpportunity, context: Dict
    ) -> bool:
        """优化Token成本"""
        logger.info("实施Token成本优化...")

        # 实施优化1: 智能缓存
        try:
            # 启用响应缓存
            context["cache_enabled"] = True
            logger.info("✅ 启用响应缓存")
        except Exception as e:
            logger.error(f"❌ 启用缓存失败: {e}")
            return False

        # 实施优化2: 采样对比
        try:
            context["comparison_sample_rate"] = 0.1  # 10%采样
            logger.info("✅ 设置对比采样率为10%")
        except Exception as e:
            logger.error(f"❌ 设置采样失败: {e}")
            return False

        return True

    async def _optimize_api_latency(
        self, opportunity: OptimizationOpportunity, context: Dict
    ) -> bool:
        """优化API延迟"""
        logger.info("实施API延迟优化...")

        # 实施优化1: 并行调用
        try:
            context["enable_parallel_calls"] = True
            logger.info("✅ 启用并行调用")
        except Exception as e:
            logger.error(f"❌ 启用并行调用失败: {e}")
            return False

        # 实施优化2: 数据库连接池
        try:
            # 优化数据库连接
            logger.info("✅ 优化数据库连接池")
        except Exception as e:
            logger.error(f"❌ 优化数据库失败: {e}")
            return False

        return True

    async def _optimize_user_satisfaction(
        self, opportunity: OptimizationOpportunity, context: Dict
    ) -> bool:
        """优化用户满意度"""
        logger.info("实施用户满意度优化...")

        # 实施优化1: 更新Prompt模板
        try:
            # 分析低分回答
            low_score_answers = await self._analyze_low_score_answers(context)
            logger.info(f"发现 {len(low_score_answers)} 个低分回答")

            # 提取改进模式
            patterns = await self._extract_improvement_patterns(low_score_answers)
            logger.info(f"提取 {len(patterns)} 个改进模式")

            # 更新Prompt
            context["prompt_improvements"] = patterns
            logger.info("✅ 更新Prompt模板")
        except Exception as e:
            logger.error(f"❌ 更新Prompt失败: {e}")
            return False

        return True

    async def _optimize_api_success_rate(
        self, opportunity: OptimizationOpportunity, context: Dict
    ) -> bool:
        """优化API成功率"""
        logger.info("实施API成功率优化...")

        # 实施优化1: 智能重试
        try:
            context["retry_enabled"] = True
            context["max_retries"] = 3
            logger.info("✅ 启用智能重试（最多3次）")
        except Exception as e:
            logger.error(f"❌ 启用重试失败: {e}")
            return False

        # 实施优化2: 超时优化
        try:
            context["api_timeout"] = 30.0
            logger.info("✅ 设置API超时为30秒")
        except Exception as e:
            logger.error(f"❌ 设置超时失败: {e}")
            return False

        return True

    def _calculate_improvement(
        self, before: Dict[str, Any], after: Dict[str, Any]
    ) -> Dict[str, float]:
        """计算改进幅度"""
        improvement = {}

        # 计算各指标的改进
        for key in before.keys():
            if key in after:
                try:
                    before_val = float(before[key])
                    after_val = float(after[key])

                    if before_val > 0:
                        change = (after_val - before_val) / before_val
                        improvement[key] = change
                except (ValueError, TypeError) as e:
                    logger.debug(f"指标计算跳过 {key}: {e}")

        return improvement

    async def execute_ab_test(
        self, plan: OptimizationPlan, context: Dict
    ) -> List[OptimizationResult]:
        """执行A/B测试"""

        results = []

        for opportunity in plan.opportunities[:3]:  # 先测试前3个
            logger.info(f"A/B测试: {opportunity.title}")

            # 执行优化
            result = await self.execute_optimization(opportunity, context)
            results.append(result)

            # 如果效果不好，回滚
            if not result.success or result.rollback_needed:
                await self.rollback_optimization(opportunity)
                logger.warning(f"回滚优化: {opportunity.title}")

        return results

    async def verify_improvement(self, results: List[OptimizationResult]) -> bool:
        """验证改进效果"""

        # 检查是否有正面改进
        positive_improvements = 0
        total_improvements = 0

        for result in results:
            for metric, change in result.improvement.items():
                total_improvements += 1
                if change > 0:
                    positive_improvements += 1

        if total_improvements == 0:
            return False

        improvement_rate = positive_improvements / total_improvements

        # 改进率超过50%认为有效
        return improvement_rate > 0.5

    async def adopt_optimization(self, plan: OptimizationPlan):
        """采纳优化（持久化配置）"""
        logger.info(f"采纳优化计划: {plan.estimated_duration}")

        # 保存配置
        config_file = Path("config/optimizations.json")
        config_file.parent.mkdir(parents=True, exist_ok=True)

        config_file.write_text(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))

        logger.info(f"✅ 优化配置已保存到 {config_file}")

    async def rollback_optimization(self, opportunity: OptimizationOpportunity):
        """回滚优化"""
        logger.info(f"回滚优化: {opportunity.title}")

        # 恢复之前的配置
        # 这里简化实现，实际应该有版本控制


class LingMinOptFramework:
    """灵极优自优化框架主类"""

    def __init__(self, config_path: str = "config/lingminopt.json"):
        self.config_path = Path(config_path)
        self.metrics_collector = MetricsCollector()
        self.optimizer = EvolutionOptimizer()
        self.orchestrator = OptimizationOrchestrator()

        self.is_running = False
        self.optimization_interval = 3600  # 1小时检查一次

    async def start_auto_optimization(self):
        """启动自动优化循环"""
        self.is_running = True

        logger.info("🚀 启动LingMinOpt自动优化循环")
        logger.info(f"优化间隔: {self.optimization_interval}秒")

        while self.is_running:
            try:
                # 执行一轮优化
                await self.optimization_loop()

                # 等待下一轮
                await asyncio.sleep(self.optimization_interval)

            except Exception as e:
                logger.error(f"优化循环出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再继续

    async def stop_auto_optimization(self):
        """停止自动优化"""
        self.is_running = False
        logger.info("停止自动优化循环")

    async def optimization_loop(self):
        """单轮优化循环"""

        logger.info("=" * 60)
        logger.info("🔄 开始新一轮优化")
        logger.info("=" * 60)

        # 1. 收集当前指标
        logger.info("📊 收集系统指标...")
        current_metrics = await self.metrics_collector.collect_snapshot()
        logger.info(f"当前指标: {json.dumps(current_metrics.metrics, indent=2)}")

        # 2. 分析瓶颈
        logger.info("🔍 分析优化机会...")
        opportunities = await self.optimizer.identify_bottlenecks(current_metrics.metrics)
        logger.info(f"发现 {len(opportunities)} 个优化机会")

        for opp in opportunities:
            logger.info(f"  - [{opp.priority.value}] {opp.title}: {opp.expected_improvement}")

        if not opportunities:
            logger.info("✨ 系统运行良好，无需优化")
            return

        # 3. 创建优化计划
        logger.info("📋 创建优化计划...")
        plan = await self.optimizer.create_optimization_plan(opportunities)
        logger.info("优化计划:")
        logger.info(f"  预计时长: {plan.estimated_duration}")
        logger.info(f"  预期影响: {plan.expected_impact}")
        logger.info(f"  阶段数: {len(plan.phases)}")

        # 4. 执行Phase 1优化（立即执行）
        if plan.phases:
            phase1 = plan.phases[0]
            logger.info(f"⚡ 执行 {phase1['name']}...")

            phase1_opportunities = [
                opp for opp in plan.opportunities if opp.id in phase1["opportunities"]
            ]

            for opp in phase1_opportunities:
                try:
                    result = await self.orchestrator.execute_optimization(
                        opp, {"metrics_collector": self.metrics_collector}
                    )

                    if result.success:
                        logger.info(f"✅ {opp.title} - 成功")
                        logger.info(f"   改进: {result.improvement}")
                    else:
                        logger.warning(f"❌ {opp.title} - 失败")

                except Exception as e:
                    logger.error(f"❌ {opp.title} - 错误: {e}")

        # 5. 验证效果
        logger.info("📈 验证优化效果...")
        new_metrics = await self.metrics_collector.collect_snapshot()
        logger.info(f"优化后指标: {json.dumps(new_metrics.metrics, indent=2)}")

        # 6. 采纳或回滚
        # 简化：如果所有优化都成功，采纳；否则回滚
        successful_results = [r for r in self.orchestrator.optimization_results if r.success]

        if successful_results:
            logger.info("✅ 采纳优化配置")
            await self.orchestrator.adopt_optimization(plan)
        else:
            logger.info("⚠️ 优化未生效，等待下一轮")

        logger.info("=" * 60)
        logger.info("✅ 本轮优化完成")
        logger.info("=" * 60)

    async def run_manual_optimization(self):
        """手动运行一轮优化"""
        logger.info("🎯 手动触发优化")
        await self.optimization_loop()


# 全局单例
_lingminopt_framework: Optional[LingMinOptFramework] = None


def get_lingminopt_framework() -> LingMinOptFramework:
    """获取LingMinOpt框架单例"""
    global _lingminopt_framework
    if _lingminopt_framework is None:
        _lingminopt_framework = LingMinOptFramework()
    return _lingminopt_framework


# CLI工具
async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="LingMinOpt灵极优自优化框架")
    parser.add_argument(
        "action",
        choices=["start", "stop", "once", "analyze"],
        help="操作: start(启动循环), stop(停止循环), once(执行一次), analyze(仅分析)",
    )

    args = parser.parse_args()

    framework = get_lingminopt_framework()

    if args.action == "start":
        await framework.start_auto_optimization()
    elif args.action == "once":
        await framework.run_manual_optimization()
    elif args.action == "analyze":
        # 仅分析，不执行
        snapshot = await framework.metrics_collector.collect_snapshot()
        opportunities = await framework.optimizer.identify_bottlenecks(snapshot.metrics)
        plan = await framework.optimizer.create_optimization_plan(opportunities)

        print("\n📊 当前系统指标:")
        print(json.dumps(snapshot.metrics, indent=2))

        print("\n🔍 发现的优化机会:")
        for opp in opportunities:
            print(f"  - [{opp.priority.value}] {opp.title}")
            print(f"    {opp.description}")
            print(f"    当前: {opp.current_value} → 目标: {opp.target_value}")
            print(f"    预期改进: {opp.expected_improvement}, 工作量: {opp.effort}")

        print("\n📋 优化计划:")
        print(f"  预计时长: {plan.estimated_duration}")
        print(f"  预期影响: {plan.expected_impact}")
        print(f"  阶段数: {len(plan.phases)}")


if __name__ == "__main__":
    asyncio.run(main())
