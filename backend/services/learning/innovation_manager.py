"""创新实验管理器

管理新技术的实验、验证、合并流程
"""
import asyncio
import logging
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """实验状态"""
    PROPOSED = "proposed"  # 已提议
    APPROVED = "approved"  # 已批准
    IN_PROGRESS = "in_progress"  # 进行中
    TESTING = "testing"  # 测试中
    PASSED = "passed"  # 通过
    FAILED = "failed"  # 失败
    MERGED = "merged"  # 已合并
    REJECTED = "rejected"  # 已拒绝


@dataclass
class InnovationProposal:
    """创新提案"""
    id: str
    title: str
    description: str
    url: str
    source_repo: str
    type: str
    tags: List[str]
    relevance: float
    potential_benefit: str
    implementation_difficulty: str
    suggested_approach: str
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    created_at: datetime = field(default_factory=datetime.now)
    user_feedback: List[str] = field(default_factory=list)
    experimental_results: Optional[Dict[str, Any]] = None
    branch_name: Optional[str] = None


class InnovationManager:
    """创新管理器"""

    def __init__(self, project_root: str = "/home/ai/zhineng-knowledge-system"):
        self.project_root = project_root
        self.proposals: List[InnovationProposal] = []
        self.experiment_branch_prefix = "exp/"

    async def check_and_suggest(self) -> List[Dict[str, Any]]:
        """检查并建议创新"""
        from .github_monitor import GitHubMonitorService

        monitor = GitHubMonitorService()
        suggestions = await monitor.suggest_innovations()

        # 保存为提案
        for suggestion in suggestions:
            proposal = InnovationProposal(
                id=self._generate_id(),
                title=suggestion['title'],
                description=suggestion['description'],
                url=suggestion['url'],
                source_repo=suggestion['url'].split('/github.com/')[1].split('/commits')[0] if 'github.com' in suggestion['url'] else suggestion['url'].split('/')[3],
                type=suggestion['type'],
                tags=suggestion['tags'],
                relevance=suggestion['relevance'],
                potential_benefit=suggestion['potential_benefit'],
                implementation_difficulty=suggestion['implementation_difficulty'],
                suggested_approach=suggestion['suggested_approach']
            )
            self.proposals.append(proposal)

        return suggestions

    def _generate_id(self) -> str:
        """生成唯一ID"""
        return f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def create_experiment_branch(
        self,
        proposal_id: str
    ) -> Dict[str, str]:
        """创建实验分支"""
        proposal = self._get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        # 生成分支名
        branch_name = f"{self.experiment_branch_prefix}{proposal.id}"
        proposal.branch_name = branch_name

        try:
            # 创建新分支
            subprocess.run(
                f"cd {self.project_root} && git checkout -b {branch_name}",
                shell=True,
                check=True,
                capture_output=True
            )

            logger.info(f"Created experimental branch: {branch_name}")

            return {
                'status': 'success',
                'branch': branch_name,
                'message': f'实验分支 "{branch_name}" 已创建'
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create branch: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def run_mvp_test(
        self,
        proposal_id: str,
        test_commands: List[str]
    ) -> Dict[str, Any]:
        """运行MVP测试"""
        proposal = self._get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        results = []
        proposal.status = ExperimentStatus.IN_PROGRESS

        for i, command in enumerate(test_commands):
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )

                test_result = {
                    'command': command,
                    'exit_code': result.returncode,
                    'stdout': result.stdout[:1000],  # 限制输出长度
                    'stderr': result.stderr[:1000],
                    'success': result.returncode == 0
                }

                results.append(test_result)

                if not test_result['success']:
                    # 测试失败，停止后续测试
                    break

            except subprocess.TimeoutExpired:
                results.append({
                    'command': command,
                    'error': '命令执行超时（5分钟）',
                    'success': False
                })
                break
            except Exception as e:
                results.append({
                    'command': command,
                    'error': str(e),
                    'success': False
                })
                break

        # 评估测试结果
        all_passed = all(r.get('success', False) for r in results)

        if all_passed:
            proposal.status = ExperimentStatus.PASSED
        else:
            proposal.status = ExperimentStatus.FAILED

        proposal.experimental_results = {
            'test_results': results,
            'all_passed': all_passed,
            'tested_at': datetime.now().isoformat()
        }

        return {
            'proposal_id': proposal_id,
            'status': proposal.status.value,
            'results': results,
            'all_passed': all_passed
        }

    async def merge_to_main(
        self,
        proposal_id: str
    ) -> Dict[str, str]:
        """合并到主分支"""
        proposal = self._get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ExperimentStatus.PASSED:
            return {
                'status': 'error',
                'message': f'提案未通过测试，无法合并。当前状态: {proposal.status.value}'
            }

        if not proposal.branch_name:
            return {
                'status': 'error',
                'message': '实验分支不存在'
            }

        try:
            # 切换到主分支
            subprocess.run(
                f"cd {self.project_root} && git checkout main",
                shell=True,
                check=True
            )

            # 拉取最新代码
            subprocess.run(
                f"cd {self.project_root} && git pull origin main",
                shell=True,
                check=True
            )

            # 合并实验分支
            subprocess.run(
                f"cd {self.project_root} && git merge {proposal.branch_name} --no-ff",
                shell=True,
                check=True
            )

            # 推送到远程
            subprocess.run(
                f"cd {self.project_root} && git push origin main",
                shell=True,
                check=True
            )

            proposal.status = ExperimentStatus.MERGED

            logger.info(f"Merged proposal {proposal_id} to main branch")

            return {
                'status': 'success',
                'message': f'已成功合并到主分支: {proposal.title}'
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to merge: {e}")
            return {
                'status': 'error',
                'message': f'合并失败: {str(e)}'
            }

    async def reject_proposal(
        self,
        proposal_id: str,
        reason: str
    ) -> Dict[str, str]:
        """拒绝提案"""
        proposal = self._get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        proposal.status = ExperimentStatus.REJECTED
        proposal.user_feedback.append(f"拒绝原因: {reason}")

        return {
            'status': 'success',
            'message': f'提案已拒绝: {reason}'
        }

    def _get_proposal(self, proposal_id: str) -> Optional[InnovationProposal]:
        """获取提案"""
        for proposal in self.proposals:
            if proposal.id == proposal_id:
                return proposal
        return None

    def get_pending_proposals(self) -> List[InnovationProposal]:
        """获取待处理的提案"""
        return [
            p for p in self.proposals
            if p.status in [
                ExperimentStatus.PROPOSED,
                ExperimentStatus.APPROVED,
                ExperimentStatus.IN_PROGRESS
            ]
        ]

    def get_proposal_summary(self) -> Dict[str, Any]:
        """获取提案摘要"""
        return {
            'total': len(self.proposals),
            'by_status': {
                status.value: len([p for p in self.proposals if p.status == status])
                for status in ExperimentStatus
            },
            'high_priority': [
                {
                    'id': p.id,
                    'title': p.title,
                    'relevance': p.relevance,
                    'benefit': p.potential_benefit
                }
                for p in self.proposals
                if p.relevance > 0.8 and p.status == ExperimentStatus.PROPOSED
            ]
        }
