"""学习和进化API路由

提供自学习、自主搜索、创新管理等功能
"""

from typing import List

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from backend.services.learning.autonomous_search import AutonomousSearchService
from backend.services.learning.github_monitor import GitHubMonitorService
from backend.services.learning.innovation_manager import InnovationManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["学习与进化"])


# ==================== 请求/响应模型 ====================


class TechUpdateSuggestion(BaseModel):
    """技术更新建议"""

    id: str
    title: str
    description: str
    url: str
    type: str
    tags: List[str]
    relevance: float
    potential_benefit: str
    implementation_difficulty: str
    suggested_approach: str


class SearchRequest(BaseModel):
    """自主搜索请求"""

    question: str
    max_rounds: int = 3
    confidence_threshold: float = 0.7


class SearchResponse(BaseModel):
    """自主搜索响应"""

    question: str
    answer: str
    confidence: float
    sources: List[str]
    rounds: int
    total_results: int


class ExperimentBranchRequest(BaseModel):
    """创建实验分支请求"""

    proposal_id: str


class MVPTestRequest(BaseModel):
    """MVP测试请求"""

    proposal_id: str
    test_commands: List[str]


class MergeToMainRequest(BaseModel):
    """合并到主分支请求"""

    proposal_id: str


class RejectProposalRequest(BaseModel):
    """拒绝提案请求"""

    proposal_id: str
    reason: str


# ==================== API端点 ====================


@router.get("/updates/check")
async def check_tech_updates(days_back: int = 7) -> List[TechUpdateSuggestion]:
    """检查技术更新"""
    try:
        monitor = GitHubMonitorService()
        suggestions = await monitor.check_and_suggest()

        return [
            TechUpdateSuggestion(
                id=s["id"],
                title=s["title"],
                description=s["description"],
                url=s["url"],
                type=s["type"],
                tags=s["tags"],
                relevance=s["relevance"],
                potential_benefit=s["potential_benefit"],
                implementation_difficulty=s["implementation_difficulty"],
                suggested_approach=s["suggested_approach"],
            )
            for s in suggestions
        ]
    except Exception as e:
        logger.error(f"检查技术更新失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检查技术更新失败: {e}")


@router.get("/updates/proposals")
async def get_innovation_proposals() -> dict:
    """获取创新提案列表"""
    try:
        manager = InnovationManager()
        summary = manager.get_proposal_summary()

        return summary
    except Exception as e:
        logger.error(f"获取创新提案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取创新提案失败: {e}")


@router.post("/updates/{proposal_id}/branch")
async def create_experiment_branch(proposal_id: str, request: ExperimentBranchRequest) -> dict:
    """
    创建实验分支

    为选定的创新提案创建实验分支，用于MVP验证

    - **proposal_id**: 提案ID
    - 自动创建 `exp/{proposal_id}` 分支

    返回分支创建结果
    """
    manager = InnovationManager()
    result = await manager.create_experiment_branch(proposal_id)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/updates/{proposal_id}/test")
async def run_mvp_test(
    proposal_id: str, request: MVPTestRequest, background_tasks: BackgroundTasks
) -> dict:
    """
    运行MVP测试

    在实验分支上运行测试命令，验证新技术的可行性

    - **proposal_id**: 提案ID
    - **test_commands**: 测试命令列表

    在后台异步执行测试
    """
    manager = InnovationManager()

    # 在后台运行测试
    async def run_test():
        result = await manager.run_mvp_test(proposal_id, request.test_commands)
        # 这里可以保存结果到数据库或发送通知
        return result

    # 添加到后台任务
    background_tasks.add_task(run_test)

    return {
        "status": "started",
        "message": f"MVP测试已启动，提案ID: {proposal_id}",
        "test_commands_count": len(request.test_commands),
    }


@router.post("/updates/{proposal_id}/merge")
async def merge_to_main(proposal_id: str, request: MergeToMainRequest) -> dict:
    """
    合并到主分支

    将通过验证的实验分支合并到主分支

    - **proposal_id**: 提案ID

    返回合并结果
    """
    manager = InnovationManager()
    result = await manager.merge_to_main(proposal_id)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.post("/updates/{proposal_id}/reject")
async def reject_proposal(proposal_id: str, request: RejectProposalRequest) -> dict:
    """
    拒绝创新提案

    拒绝一个创新提案，记录拒绝原因

    - **proposal_id**: 提案ID
    - **reason**: 拒绝原因

    返回操作结果
    """
    manager = InnovationManager()
    result = await manager.reject_proposal(proposal_id, request.reason)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.post("/search/autonomous", response_model=SearchResponse)
async def autonomous_search(request: SearchRequest) -> SearchResponse:
    """自主网络搜索"""
    try:
        search_service = AutonomousSearchService()
        result = await search_service.search_until_satisfied(
            question=request.question,
            max_rounds=request.max_rounds,
            confidence_threshold=request.confidence_threshold,
        )

        return SearchResponse(
            question=result["question"],
            answer=result["answer"],
            confidence=result["confidence"],
            sources=result["sources"],
            rounds=result["rounds"],
            total_results=result["total_results"],
        )
    except Exception as e:
        logger.error(f"自主搜索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"自主搜索失败: {e}")


@router.get("/learning/status")
async def get_learning_status() -> dict:
    """获取系统学习状态"""
    try:
        manager = InnovationManager()
        monitor = GitHubMonitorService()

        recent_updates = await monitor.check_updates(days_back=1)
        proposal_summary = manager.get_proposal_summary()

        return {
            "last_update_check": "刚刚",
            "recent_tech_updates": len(recent_updates),
            "total_proposals": proposal_summary["total"],
            "pending_proposals": len(manager.get_pending_proposals()),
            "high_priority_proposals": len(proposal_summary["high_priority"]),
            "system_status": "active",
            "learning_capabilities": {
                "github_monitoring": True,
                "autonomous_search": True,
                "experimental_testing": True,
                "auto_merge": False,
            },
        }
    except Exception as e:
        logger.error(f"获取学习状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取学习状态失败: {e}")
