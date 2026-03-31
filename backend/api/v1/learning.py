"""学习和进化API路由

提供自学习、自主搜索、创新管理等功能
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from core.database import get_async_session
from services.learning.github_monitor import GitHubMonitorService
from services.learning.innovation_manager import InnovationManager, InnovationProposal
from services.learning.autonomous_search import AutonomousSearchService

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
async def check_tech_updates(
    days_back: int = 7
) -> List[TechUpdateSuggestion]:
    """
    检查技术更新

    监控GitHub上的相关项目，发现新技术和新思想

    - **days_back**: 查询最近多少天的更新（默认7天）

    返回技术更新建议列表
    """
    monitor = GitHubMonitorService()
    suggestions = await monitor.check_and_suggest()

    return [
        TechUpdateSuggestion(
            id=s['id'],
            title=s['title'],
            description=s['description'],
            url=s['url'],
            type=s['type'],
            tags=s['tags'],
            relevance=s['relevance'],
            potential_benefit=s['potential_benefit'],
            implementation_difficulty=s['implementation_difficulty'],
            suggested_approach=s['suggested_approach']
        )
        for s in suggestions
    ]


@router.get("/updates/proposals")
async def get_innovation_proposals() -> dict:
    """
    获取创新提案列表

    返回所有创新提案及其状态
    """
    manager = InnovationManager()
    summary = manager.get_proposal_summary()

    return summary


@router.post("/updates/{proposal_id}/branch")
async def create_experiment_branch(
    proposal_id: str,
    request: ExperimentBranchRequest
) -> dict:
    """
    创建实验分支

    为选定的创新提案创建实验分支，用于MVP验证

    - **proposal_id**: 提案ID
    - 自动创建 `exp/{proposal_id}` 分支

    返回分支创建结果
    """
    manager = InnovationManager()
    result = await manager.create_experiment_branch(proposal_id)

    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result['error'])

    return result


@router.post("/updates/{proposal_id}/test")
async def run_mvp_test(
    proposal_id: str,
    request: MVPTestRequest,
    background_tasks: BackgroundTasks
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
        'status': 'started',
        'message': f'MVP测试已启动，提案ID: {proposal_id}',
        'test_commands_count': len(request.test_commands)
    }


@router.post("/updates/{proposal_id}/merge")
async def merge_to_main(
    proposal_id: str,
    request: MergeToMainRequest
) -> dict:
    """
    合并到主分支

    将通过验证的实验分支合并到主分支

    - **proposal_id**: 提案ID

    返回合并结果
    """
    manager = InnovationManager()
    result = await manager.merge_to_main(proposal_id)

    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@router.post("/updates/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    request: RejectProposalRequest
) -> dict:
    """
    拒绝创新提案

    拒绝一个创新提案，记录拒绝原因

    - **proposal_id**: 提案ID
    - **reason**: 拒绝原因

    返回操作结果
    """
    manager = InnovationManager()
    result = await manager.reject_proposal(proposal_id, request.reason)

    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@router.post("/search/autonomous", response_model=SearchResponse)
async def autonomous_search(
    request: SearchRequest
) -> SearchResponse:
    """
    自主网络搜索

    当系统无法回答问题时，自动上网搜索答案

    - **question**: 用户问题
    - **max_rounds**: 最大搜索轮次（默认3）
    - **confidence_threshold**: 置信度阈值（默认0.7）

    系统会：
    1. 第一轮：使用搜索引擎（Google、Bing、DuckDuckGo）
    2. 第二轮：搜索知识库（维基百科、arXiv）
    3. 第三轮：基于前两轮结果构建深度查询

    直到找到满意答案或达到最大轮次
    """
    search_service = AutonomousSearchService()
    result = await search_service.search_until_satisfied(
        question=request.question,
        max_rounds=request.max_rounds,
        confidence_threshold=request.confidence_threshold
    )

    return SearchResponse(
        question=result['question'],
        answer=result['answer'],
        confidence=result['confidence'],
        sources=result['sources'],
        rounds=result['rounds'],
        total_results=result['total_results']
    )


@router.get("/learning/status")
async def get_learning_status() -> dict:
    """
    获取系统学习状态

    返回系统的自学习、自进化状态摘要
    """
    manager = InnovationManager()
    monitor = GitHubMonitorService()

    # 获取最近的更新
    recent_updates = await monitor.check_updates(days_back=1)

    # 获取提案摘要
    proposal_summary = manager.get_proposal_summary()

    return {
        'last_update_check': '刚刚',
        'recent_tech_updates': len(recent_updates),
        'total_proposals': proposal_summary['total'],
        'pending_proposals': len(manager.get_pending_proposals()),
        'high_priority_proposals': len(proposal_summary['high_priority']),
        'system_status': 'active',
        'learning_capabilities': {
            'github_monitoring': True,
            'autonomous_search': True,
            'experimental_testing': True,
            'auto_merge': False  # 需要人工确认
        }
    }
