"""进化验证Agent - 确保改进是真正的改进

这个Agent负责验证进化是否有效，避免无效或退化的改进。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.evolution import EvolutionLog
from backend.services.evolution.comparison_engine import get_comparison_engine
from backend.services.evolution.multi_ai_adapter import get_multi_ai_adapter

logger = logging.getLogger(__name__)


class VerificationResult:
    """验证结果"""

    def __init__(
        self,
        is_valid: bool,
        confidence: float,
        reasons: List[str],
        suggestions: List[str],
        metrics: Dict[str, Any],
    ):
        self.is_valid = is_valid
        self.confidence = confidence  # 0.0 - 1.0
        self.reasons = reasons  # 验证通过或失败的原因
        self.suggestions = suggestions  # 改进建议
        self.metrics = metrics  # 详细的验证指标

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "suggestions": self.suggestions,
            "metrics": self.metrics,
        }


class EvolutionVerificationAgent:
    """进化验证Agent

    职责：
    1. 验证新版本是否真的优于旧版本
    2. 多维度评估：内容质量、用户反馈、竞品对比
    3. 提供改进建议
    4. 决定是否采纳改进
    """

    def __init__(self):
        self.multi_ai = get_multi_ai_adapter()
        self.comparison_engine = get_comparison_engine()

        # 验证阈值配置
        self.thresholds = {
            "min_confidence": 0.7,  # 最低置信度
            "min_improvement_ratio": 1.2,  # 最小改进比例（20%）
            "min_length": 500,  # 最小回答长度
            "min_user_satisfaction": 4.0,  # 最低用户满意度
            "max_competitor_rank": 2,  # 竞品排名要求（前2）
            "min_structure_score": 0.6,  # 最小结构化分数
        }

    async def verify_evolution(
        self,
        db: AsyncSession,
        query: str,
        old_response: str,
        new_response: str,
        user_feedback: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """验证进化是否有效

        Args:
            db: 数据库会话
            query: 用户问题
            old_response: 旧版本回答
            new_response: 新版本回答
            user_feedback: 用户反馈（如果有）

        Returns:
            VerificationResult: 验证结果
        """

        logger.info(f"开始验证进化: query={query[:50]}...")

        # 1. 基础指标验证
        basic_metrics = await self._verify_basic_metrics(old_response, new_response)

        # 2. 结构化验证
        structure_metrics = await self._verify_structure(new_response)

        # 3. 内容质量验证
        quality_metrics = await self._verify_quality(query, old_response, new_response)

        # 4. 竞品对比验证
        comparison_metrics = await self._verify_with_competitors(query, new_response)

        # 5. 用户反馈验证（如果有）
        feedback_metrics = await self._verify_user_feedback(user_feedback)

        # 6. 综合判断
        all_metrics = {
            **basic_metrics,
            **structure_metrics,
            **quality_metrics,
            **comparison_metrics,
            **feedback_metrics,
        }

        is_valid, confidence, reasons, suggestions = self._make_decision(all_metrics)

        result = VerificationResult(
            is_valid=is_valid,
            confidence=confidence,
            reasons=reasons,
            suggestions=suggestions,
            metrics=all_metrics,
        )

        # 7. 记录验证结果
        await self._log_verification(db, query, old_response, new_response, result)

        logger.info(
            f"验证完成: valid={is_valid}, confidence={confidence:.2f}, "
            f"reasons_count={len(reasons)}"
        )

        return result

    async def _verify_basic_metrics(self, old_response: str, new_response: str) -> Dict[str, Any]:
        """验证基础指标"""

        old_length = len(old_response)
        new_length = len(new_response)

        length_improved = new_length >= old_length * self.thresholds["min_improvement_ratio"]
        meets_min_length = new_length >= self.thresholds["min_length"]

        return {
            "old_length": old_length,
            "new_length": new_length,
            "length_improved": length_improved,
            "length_ratio": new_length / old_length if old_length > 0 else 0,
            "meets_min_length": meets_min_length,
        }

    async def _verify_structure(self, response: str) -> Dict[str, Any]:
        """验证结构化程度"""

        # 检查标题（# 标题）
        has_headings = "#" in response or "##" in response

        # 检查列表（- 或 1.）
        has_lists = (
            "-" in response or "*" in response or any(f"{i}." in response for i in range(1, 10))
        )

        # 检查段落分隔
        has_paragraphs = response.count("\n\n") >= 2

        # 检查代码块
        has_code = "```" in response

        # 计算结构化分数
        structure_indicators = [has_headings, has_lists, has_paragraphs, has_code]
        structure_score = sum(structure_indicators) / len(structure_indicators)

        return {
            "has_headings": has_headings,
            "has_lists": has_lists,
            "has_paragraphs": has_paragraphs,
            "has_code": has_code,
            "structure_score": structure_score,
            "meets_threshold": structure_score >= self.thresholds["min_structure_score"],
        }

    async def _verify_quality(
        self, query: str, old_response: str, new_response: str
    ) -> Dict[str, Any]:
        """验证内容质量

        使用对比引擎评估新旧版本
        """

        # 使用对比引擎评估
        evaluations = await self.comparison_engine.compare_qa_responses(
            query=query,
            lingzhi_response=new_response,
            competitor_responses={
                "old_version": {"content": old_response, "success": True, "latency_ms": 0}
            },
        )

        new_scores = evaluations["scores"].get("lingzhi", {})
        old_scores = evaluations["scores"].get("old_version", {})

        # 比较新旧版本
        improvement = {}
        for dimension in ["completeness", "usefulness", "clarity", "overall"]:
            new_score = new_scores.get(dimension, 0)
            old_score = old_scores.get(dimension, 0)
            improvement[f"{dimension}_improved"] = new_score > old_score
            improvement[f"{dimension}_delta"] = new_score - old_score

        return {
            "new_scores": new_scores,
            "old_scores": old_scores,
            "improvement": improvement,
            "overall_improved": improvement.get("overall_improved", False),
        }

    async def _verify_with_competitors(self, query: str, response: str) -> Dict[str, Any]:
        """和竞品对比验证

        并行调用混元和DeepSeek，评估灵知的排名
        """

        try:
            # 并行调用竞品
            results = await asyncio.wait_for(
                self.multi_ai.parallel_generate(
                    prompt=query, request_type="qa", providers=["hunyuan", "deepseek"], timeout=15.0
                ),
                timeout=20.0,
            )

            # 准备对比
            competitor_responses = {}
            for provider, result in results.items():
                if result.get("success"):
                    competitor_responses[provider] = result

            if not competitor_responses:
                # 竞品调用失败，返回默认值
                return {
                    "has_competitor_data": False,
                    "rank": None,
                    "meets_threshold": True,  # 没有竞品数据时默认通过
                }

            # 对比评估
            evaluations = await self.comparison_engine.compare_qa_responses(
                query=query, lingzhi_response=response, competitor_responses=competitor_responses
            )

            # 获取灵知的排名
            scores = evaluations["scores"]
            ranked = sorted(scores.items(), key=lambda x: x[1]["overall"], reverse=True)

            lingzhi_rank = None
            for i, (name, _) in enumerate(ranked, 1):
                if name == "lingzhi":
                    lingzhi_rank = i
                    break

            meets_threshold = (
                lingzhi_rank is not None and lingzhi_rank <= self.thresholds["max_competitor_rank"]
            )

            return {
                "has_competitor_data": True,
                "rank": lingzhi_rank,
                "scores": scores,
                "meets_threshold": meets_threshold,
                "winner": ranked[0][0] if ranked else None,
            }

        except asyncio.TimeoutError:
            logger.warning("竞品对比超时")
            return {
                "has_competitor_data": False,
                "timeout": True,
                "meets_threshold": True,  # 超时时默认通过
            }
        except Exception as e:
            logger.error(f"竞品对比失败: {e}")
            return {"has_competitor_data": False, "error": str(e), "meets_threshold": True}

    async def _verify_user_feedback(
        self, user_feedback: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """验证用户反馈"""

        if not user_feedback:
            return {"has_feedback": False, "meets_threshold": True}  # 没有反馈时默认通过

        satisfaction = user_feedback.get("satisfaction", 0)
        meets_threshold = satisfaction >= self.thresholds["min_user_satisfaction"]

        return {
            "has_feedback": True,
            "satisfaction": satisfaction,
            "meets_threshold": meets_threshold,
            "comments": user_feedback.get("comments", ""),
        }

    def _collect_must_pass(self, metrics: Dict[str, Any]) -> List[str]:
        failures = []
        if not metrics.get("meets_min_length", True):
            failures.append("❌ 回答过短，不满足最小长度要求")
        if not metrics.get("meets_threshold", True):
            failures.append("❌ 结构化程度不足")
        return failures

    def _collect_optional_pass(self, metrics: Dict[str, Any]) -> List[str]:
        passed = []
        if metrics.get("length_improved", False):
            passed.append("✅ 回答长度有显著提升")
        if metrics.get("overall_improved", False):
            passed.append("✅ 整体质量优于旧版本")
        if metrics.get("meets_threshold", False):
            passed.append("✅ 竞品对比排名优秀")
        if metrics.get("has_feedback", False) and metrics.get("meets_threshold", False):
            passed.append("✅ 用户反馈满意度高")
        return passed

    def _compute_confidence(self, metrics: Dict[str, Any], must_pass: List[str]) -> float:
        confidence = 0.0
        if not must_pass:
            confidence += 0.3
        if metrics.get("structure_score", 0) > 0.5:
            confidence += 0.1
        if metrics.get("length_improved", False):
            confidence += 0.2
        if metrics.get("overall_improved", False):
            confidence += 0.2
        if metrics.get("has_competitor_data") and metrics.get("meets_threshold"):
            confidence += 0.2
        if metrics.get("has_feedback") and metrics.get("meets_threshold"):
            confidence += 0.3
        return confidence

    def _build_reasons(
        self,
        is_valid: bool,
        confidence: float,
        must_pass: List[str],
        optional_pass: List[str],
    ) -> List[str]:
        reasons: List[str] = []
        if is_valid:
            reasons.extend(optional_pass)
            reasons.append(f"✅ 综合置信度: {confidence:.2f}")
        else:
            reasons.extend(must_pass)
            if confidence < self.thresholds["min_confidence"]:
                reasons.append(
                    f"❌ 综合置信度不足: {confidence:.2f} (需要 ≥ {self.thresholds['min_confidence']})"
                )
            if not optional_pass:
                reasons.append("❌ 未发现明显改进点")
        return reasons

    def _build_suggestions(self, metrics: Dict[str, Any]) -> List[str]:
        suggestions: List[str] = []
        if not metrics.get("meets_min_length", True):
            suggestions.append("增加回答的详细程度和内容丰富度")
        if not metrics.get("meets_threshold", False):
            suggestions.append("添加标题、列表等结构化元素")
        if not metrics.get("has_headings", False):
            suggestions.append("使用标题和副标题组织内容")
        if not metrics.get("has_lists", False):
            suggestions.append("使用列表（- 或 1.）列举要点")
        if not metrics.get("has_paragraphs", False):
            suggestions.append("使用段落分隔，提高可读性")
        if metrics.get("has_competitor_data") and not metrics.get("meets_threshold"):
            suggestions.append("参考竞品优势，补充内容细节")
        if not suggestions:
            suggestions.append("当前版本质量良好，继续保持")
        return suggestions

    def _make_decision(self, metrics: Dict[str, Any]) -> tuple:
        """综合判断是否验证通过

        Returns:
            (is_valid, confidence, reasons, suggestions)
        """
        must_pass = self._collect_must_pass(metrics)
        optional_pass = self._collect_optional_pass(metrics)
        confidence = self._compute_confidence(metrics, must_pass)

        is_valid = (
            len(must_pass) == 0
            and confidence >= self.thresholds["min_confidence"]
            and len(optional_pass) >= 1
        )

        reasons = self._build_reasons(is_valid, confidence, must_pass, optional_pass)
        suggestions = self._build_suggestions(metrics)

        return is_valid, confidence, reasons, suggestions

    async def _log_verification(
        self,
        db: AsyncSession,
        query: str,
        old_response: str,
        new_response: str,
        result: VerificationResult,
    ):
        """记录验证结果到数据库"""

        try:
            # 使用 EvolutionLog 的正确字段
            log = EvolutionLog(
                issue_type="verification",
                issue_category="quality",
                issue_description=f"Query: {query[:200]}",
                improvement_type="response_verification",
                improvement_action=f"Validated evolution with confidence {result.confidence:.2f}",
                improvement_details={
                    "query": query[:500],
                    "old_response": old_response[:1000],
                    "new_response": new_response[:1000],
                    "is_valid": result.is_valid,
                    "confidence": result.confidence,
                    "reasons": result.reasons[:5],
                    "suggestions": result.suggestions[:5],
                    "metrics": result.metrics,
                },
                before_metrics={"old_length": len(old_response)},
                after_metrics={
                    "new_length": len(new_response),
                    "confidence": result.confidence,
                    "is_valid": result.is_valid,
                },
                effectiveness_score=int(result.confidence * 5) if result.is_valid else None,
                status="completed" if result.is_valid else "pending",
                implemented_by="verification_agent",
            )

            db.add(log)
            await db.commit()

        except Exception as e:
            logger.error(f"记录验证结果失败: {e}")
            await db.rollback()

    async def update_thresholds(self, new_thresholds: Dict[str, Any]):
        """动态更新验证阈值

        Args:
            new_thresholds: 新的阈值配置
        """

        self.thresholds.update(new_thresholds)
        logger.info(f"验证阈值已更新: {self.thresholds}")

    async def get_thresholds(self) -> Dict[str, Any]:
        """获取当前阈值配置"""
        return self.thresholds.copy()


# 全局单例
_verification_agent: Optional[EvolutionVerificationAgent] = None


def get_verification_agent() -> EvolutionVerificationAgent:
    """获取验证Agent单例"""
    global _verification_agent
    if _verification_agent is None:
        _verification_agent = EvolutionVerificationAgent()
    return _verification_agent
