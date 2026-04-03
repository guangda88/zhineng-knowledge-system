"""定时任务调度器

定期执行学习相关任务：监控GitHub、评估更新等
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class LearningScheduler:
    """学习任务调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.github_monitor = None
        self.innovation_manager = None

    async def start(self):
        """启动调度器"""
        from backend.services.learning.github_monitor import GitHubMonitorService
        from backend.services.learning.innovation_manager import InnovationManager

        self.github_monitor = GitHubMonitorService()
        self.innovation_manager = InnovationManager()

        # 每天检查GitHub更新（凌晨2点）
        self.scheduler.add_job(
            self._check_github_updates,
            trigger=CronTrigger(hour=2, minute=0),
            id="github_update_check",
        )

        # 每周评估提案（周日下午3点）
        self.scheduler.add_job(
            self._evaluate_proposals,
            trigger=CronTrigger(day_of_week="sun", hour=15, minute=0),
            id="proposal_evaluation",
        )

        # 每月生成学习报告（每月1号凌晨）
        self.scheduler.add_job(
            self._generate_learning_report,
            trigger=CronTrigger(day=1, hour=3, minute=0),
            id="monthly_report",
        )

        self.scheduler.start()
        logger.info("Learning scheduler started")

    async def stop(self):
        """停止调度器"""
        self.scheduler.shutdown()
        logger.info("Learning scheduler stopped")

    async def _check_github_updates(self):
        """检查GitHub更新"""
        logger.info("Running scheduled GitHub update check")

        try:
            updates = await self.github_monitor.check_updates(days_back=1)

            if updates:
                logger.info(f"Found {len(updates)} updates from GitHub")

                # 如果发现高相关性的更新，可以发送通知
                high_relevance = [u for u in updates if u.relevance > 0.8]
                if high_relevance:
                    await self._notify_new_updates(high_relevance)

        except Exception as e:
            logger.error(f"Error in GitHub update check: {e}")

    async def _evaluate_proposals(self):
        """评估提案"""
        logger.info("Running scheduled proposal evaluation")

        try:
            pending = self.innovation_manager.get_pending_proposals()

            for proposal in pending:
                # 检查提案是否过期（超过30天未处理）
                if (datetime.now() - proposal.created_at).days > 30:
                    logger.warning(f"Proposal {proposal.id} is stale (30 days old)")

                    # 可以自动标记为过期
                    proposal.user_feedback.append("系统自动标记：提案已过期30天")

        except Exception as e:
            logger.error(f"Error in proposal evaluation: {e}")

    async def _generate_learning_report(self):
        """生成学习报告"""
        logger.info("Generating monthly learning report")

        try:
            summary = self.innovation_manager.get_proposal_summary()

            report = {
                "report_date": datetime.now().isoformat(),
                "report_period": "上月",
                "total_proposals": summary["total"],
                "approved_proposals": summary["by_status"].get("approved", 0),
                "merged_proposals": summary["by_status"].get("merged", 0),
                "rejected_proposals": summary["by_status"].get("rejected", 0),
                "pending_proposals": len(self.innovation_manager.get_pending_proposals()),
                "learning_trends": self._analyze_learning_trends(),
            }

            # 保存报告到文件
            report_path = f"logs/learning_reports/{datetime.now().strftime('%Y%m')}_report.json"
            import json

            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            logger.info(f"Monthly learning report saved to {report_path}")

        except Exception as e:
            logger.error(f"Error generating learning report: {e}")

    async def _notify_new_updates(self, updates: list):
        """通知新更新"""
        # 这里可以实现各种通知方式：
        # - 发送邮件
        # - 写入日志
        # - 保存到数据库
        # - 发送到通知服务

        for update in updates:
            logger.info(f"New high-relevance update: {update.title}")

        # 保存到通知文件
        notification = {
            "timestamp": datetime.now().isoformat(),
            "count": len(updates),
            "updates": [
                {"title": u.title, "repo": u.repo_name, "relevance": u.relevance} for u in updates
            ],
        }

        import json

        with open("data/learning_notifications/latest.json", "w", encoding="utf-8") as f:
            json.dump(notification, f, ensure_ascii=False, indent=2)

    def _analyze_learning_trends(self) -> dict:
        """分析学习趋势"""
        summary = self.innovation_manager.get_proposal_summary()

        return {
            "most_active_categories": self._get_top_categories(),
            "average_relevance": self._calculate_avg_relevance(summary),
            "success_rate": self._calculate_success_rate(summary),
            "learning_velocity": self._calculate_learning_velocity(),
        }

    def _get_top_categories(self) -> List[str]:
        """获取最活跃的分类"""
        # 统计各分类的提案数量
        categories = {}
        for proposal in self.innovation_manager.proposals:
            for tag in proposal.tags:
                categories[tag] = categories.get(tag, 0) + 1

        # 返回Top 5
        sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        return [cat[0] for cat in sorted_categories[:5]]

    def _calculate_avg_relevance(self, summary: dict) -> float:
        """计算平均相关性"""
        if not self.innovation_manager.proposals:
            return 0.0

        total_relevance = sum(p.relevance for p in self.innovation_manager.proposals)
        return total_relevance / len(self.innovation_manager.proposals)

    def _calculate_success_rate(self, summary: dict) -> float:
        """计算成功率"""
        total = summary["total"]
        if total == 0:
            return 0.0

        passed = summary["by_status"].get("passed", 0)
        merged = summary["by_status"].get("merged", 0)

        return (passed + merged) / total if total > 0 else 0.0

    def _calculate_learning_velocity(self) -> str:
        """计算学习速度"""
        # 计算过去30天的提案数量
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_proposals = [
            p for p in self.innovation_manager.proposals if p.created_at >= thirty_days_ago
        ]

        count = len(recent_proposals)

        if count > 10:
            return "高"
        elif count > 5:
            return "中"
        else:
            return "低"


# 全局调度器实例
_learning_scheduler: Optional[LearningScheduler] = None


def get_learning_scheduler() -> LearningScheduler:
    """获取学习调度器实例"""
    global _learning_scheduler
    if _learning_scheduler is None:
        _learning_scheduler = LearningScheduler()
    return _learning_scheduler
