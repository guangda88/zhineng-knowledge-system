"""反馈收集器

收集和分析用户反馈，识别优化机会
"""
import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta
from collections import Counter

from .lingminopt import OptimizationOpportunity, OptimizationSource, OptimizationPriority

logger = logging.getLogger(__name__)


class FeedbackCollector:
    """反馈收集器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 模拟反馈数据存储
        self.feedback_data = []

    async def collect_feedback(
        self,
        user_id: str,
        feedback_type: str,
        content: str,
        rating: int = None,
        metadata: Dict = None
    ) -> str:
        """
        收集用户反馈

        Args:
            user_id: 用户ID
            feedback_type: 反馈类型（bug, feature, improvement, complaint）
            content: 反馈内容
            rating: 评分（1-5）
            metadata: 额外元数据

        Returns:
            str: 反馈ID
        """
        feedback_id = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_id}"

        feedback = {
            "feedback_id": feedback_id,
            "user_id": user_id,
            "type": feedback_type,
            "content": content,
            "rating": rating,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }

        self.feedback_data.append(feedback)
        logger.info(f"收集反馈: {feedback_id}")

        return feedback_id

    async def analyze_feedback(self) -> Dict[str, Any]:
        """
        分析用户反馈

        生成反馈统计和洞察
        """
        if not self.feedback_data:
            return {"message": "暂无反馈数据"}

        # 按类型统计
        type_counts = Counter(f["type"] for f in self.feedback_data)

        # 按评分统计
        ratings = [f["rating"] for f in self.feedback_data if f.get("rating")]
        avg_rating = sum(ratings) / len(ratings) if ratings else None

        # 提取关键词
        all_content = " ".join(f["content"] for f in self.feedback_data)
        keywords = self._extract_keywords(all_content)

        # 识别热点问题
        hot_issues = self._identify_hot_issues()

        return {
            "total_feedback": len(self.feedback_data),
            "by_type": dict(type_counts),
            "average_rating": avg_rating,
            "top_keywords": keywords[:10],
            "hot_issues": hot_issues,
            "sentiment": self._analyze_sentiment(all_content)
        }

    async def identify_optportunities(self) -> List[OptimizationOpportunity]:
        """
        从反馈中识别优化机会
        """
        opportunities = []

        # 按类型分组
        feedback_by_type = {}
        for feedback in self.feedback_data:
            ftype = feedback["type"]
            if ftype not in feedback_by_type:
                feedback_by_type[ftype] = []
            feedback_by_type[ftype].append(feedback)

        # 分析Bug反馈
        if "bug" in feedback_by_type:
            bug_opportunities = await self._analyze_bug_feedbacks(
                feedback_by_type["bug"]
            )
            opportunities.extend(bug_opportunities)

        # 分析功能请求
        if "feature" in feedback_by_type:
            feature_opportunities = await self._analyze_feature_requests(
                feedback_by_type["feature"]
            )
            opportunities.extend(feature_opportunities)

        # 分析改进建议
        if "improvement" in feedback_by_type:
            improvement_opportunities = await self._analyze_improvement_suggestions(
                feedback_by_type["improvement"]
            )
            opportunities.extend(improvement_opportunities)

        return opportunities

    async def _analyze_bug_feedbacks(
        self,
        bug_feedbacks: List[Dict]
    ) -> List[OptimizationOpportunity]:
        """分析Bug反馈"""
        opportunities = []

        # 按相似度分组
        bug_groups = self._group_similar_feedbacks(bug_feedbacks)

        for group in bug_groups:
            if len(group) >= 3:  # 至少3人报告相同问题
                opportunity = OptimizationOpportunity(
                    id=f"opt_bug_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    title=f"修复Bug: {group[0]['content'][:50]}",
                    description=f"有{len(group)}位用户报告了此问题",
                    source=OptimizationSource.USER_FEEDBACK,
                    priority=OptimizationPriority.HIGH,
                    category="functionality",
                    current_state={"bug_reports": len(group)},
                    desired_state={"bug_reports": 0},
                    impact_estimate="影响用户体验",
                    effort_estimate="medium"
                )
                opportunities.append(opportunity)

        return opportunities

    async def _analyze_feature_requests(
        self,
        feature_feedbacks: List[Dict]
    ) -> List[OptimizationOpportunity]:
        """分析功能请求"""
        opportunities = []

        # 提取高频功能请求
        feature_keywords = Counter()
        for feedback in feature_feedbacks:
            keywords = self._extract_keywords(feedback["content"])
            for keyword in keywords:
                feature_keywords[keyword] += 1

        # 生成优化机会
        for feature, count in feature_keywords.most_common(5):
            if count >= 5:  # 至少5人请求
                opportunity = OptimizationOpportunity(
                    id=f"opt_feature_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    title=f"添加功能: {feature}",
                    description=f"有{count}位用户请求此功能",
                    source=OptimizationSource.USER_FEEDBACK,
                    priority=OptimizationPriority.MEDIUM,
                    category="functionality",
                    current_state={"feature_requested": True},
                    desired_state={"feature_implemented": True},
                    impact_estimate="提升用户满意度",
                    effort_estimate="high"
                )
                opportunities.append(opportunity)

        return opportunities

    async def _analyze_improvement_suggestions(
        self,
        improvement_feedbacks: List[Dict]
    ) -> List[OptimizationOpportunity]:
        """分析改进建议"""
        opportunities = []

        # 分析低评分反馈
        low_rating_feedbacks = [
            f for f in improvement_feedbacks
            if f.get("rating", 5) <= 3
        ]

        if len(low_rating_feedbacks) >= 5:
            opportunity = OptimizationOpportunity(
                id=f"opt_improvement_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                title="提升用户体验",
                description=f"有{len(low_rating_feedbacks)}位低评分反馈需要关注",
                source=OptimizationSource.USER_FEEDBACK,
                priority=OptimizationPriority.HIGH,
                category="usability",
                current_state={"avg_rating": 3.0},
                desired_state={"avg_rating": 4.5},
                impact_estimate="显著提升满意度",
                effort_estimate="medium"
            )
            opportunities.append(opportunity)

        return opportunities

    def _extract_keywords(self, text: str, top_n: int = 20) -> List[str]:
        """提取关键词"""
        # 简单实现：分词并统计词频
        import re
        from collections import Counter

        # 分词
        words = re.findall(r'\w+', text.lower())

        # 过滤停用词
        stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        words = [w for w in words if len(w) > 1 and w not in stopwords]

        # 统计词频
        word_counts = Counter(words)

        return [word for word, count in word_counts.most_common(top_n)]

    def _identify_hot_issues(self) -> List[Dict[str, Any]]:
        """识别热点问题"""
        # 最近7天的反馈
        cutoff = datetime.now() - timedelta(days=7)
        recent_feedbacks = [
            f for f in self.feedback_data
            if datetime.fromisoformat(f["created_at"]) > cutoff
        ]

        # 按内容相似度分组
        groups = self._group_similar_feedbacks(recent_feedbacks)

        hot_issues = []
        for group in groups[:5]:
            if len(group) >= 3:
                hot_issues.append({
                    "content": group[0]["content"],
                    "count": len(group),
                    "type": group[0]["type"]
                })

        return hot_issues

    def _group_similar_feedbacks(
        self,
        feedbacks: List[Dict],
        threshold: float = 0.7
    ) -> List[List[Dict]]:
        """按相似度分组反馈"""
        # 简化实现：使用关键词重叠度
        groups = []
        used = set()

        for i, feedback1 in enumerate(feedbacks):
            if i in used:
                continue

            group = [feedback1]
            keywords1 = set(self._extract_keywords(feedback1["content"]))

            for j, feedback2 in enumerate(feedbacks[i+1:], i+1):
                if j in used:
                    continue

                keywords2 = set(self._extract_keywords(feedback2["content"]))

                # 计算关键词重叠度
                if keywords1 and keywords2:
                    overlap = len(keywords1 & keywords2) / len(keywords1 | keywords2)
                    if overlap >= threshold:
                        group.append(feedback2)
                        used.add(j)

            if len(group) > 1:
                groups.append(group)
            used.add(i)

        return groups

    def _analyze_sentiment(self, text: str) -> str:
        """分析情感"""
        # 简化实现
        positive_words = {"好", "优秀", "喜欢", "满意", "棒", "赞"}
        negative_words = {"差", "不好", "失望", "糟糕", "讨厌", "慢"}

        words = set(self._extract_keywords(text))

        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
