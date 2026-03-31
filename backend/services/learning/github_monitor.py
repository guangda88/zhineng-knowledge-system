"""GitHub前沿技术感知服务

监控相关GitHub项目，发现新技术、新思想
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TechUpdate:
    """技术更新信息"""
    repo_name: str
    title: str
    url: str
    type: str  # 'feature', 'fix', 'refactor', 'docs'
    relevance: float  # 相关性评分 0-1
    description: str
    created_at: datetime
    tags: List[str]


class GitHubMonitorService:
    """GitHub监控服务"""

    # 监控的相关项目列表
    MONITORED_REPOS = [
        # RAG相关
        {
            'owner': 'langchain-ai',
            'repo': 'langchain',
            'relevance': 'rag',
            'description': 'RAG应用框架'
        },
        {
            'owner': 'milvus-io',
            'repo': 'milvus',
            'relevance': 'vector_db',
            'description': '向量数据库'
        },
        {
            'owner': 'chroma-core',
            'repo': 'chroma',
            'relevance': 'vector_db',
            'description': '向量数据库'
        },
        # 智能体
        {
            'owner': 'langchain-ai',
            'repo': 'langgraph',
            'relevance': 'agent',
            'description': '智能体框架'
        },
        # 模型
        {
            'owner': 'UKPLab',
            'repo': 'sentence-transformers',
            'relevance': 'embedding',
            'description': '嵌入模型'
        },
        # 知识图谱
        {
            'owner': 'pyke',
            'repo': 'pyke',
            'relevance': 'knowledge_graph',
            'description': '知识图谱'
        },
        # 向量检索
        {
            'owner': 'facebookresearch',
            'repo': 'faiss',
            'relevance': 'vector_search',
            'description': '向量检索'
        },
    ]

    def __init__(self):
        self.github_api_base = "https://api.github.com"
        self.last_check: Dict[str, datetime] = {}
        self.updates: List[TechUpdate] = []

    async def check_updates(self, days_back: int = 7) -> List[TechUpdate]:
        """检查最近的更新"""
        updates = []

        since_date = datetime.now() - timedelta(days=days_back)

        async with aiohttp.ClientSession() as session:
            for repo_info in self.MONITORED_REPOS:
                try:
                    repo_updates = await self._fetch_repo_updates(
                        session,
                        repo_info['owner'],
                        repo_info['repo'],
                        since_date
                    )

                    for update in repo_updates:
                        update.relevance = self._calculate_relevance(
                            update,
                            repo_info['relevance']
                        )
                        updates.append(update)

                except Exception as e:
                    logger.error(f"Error checking {repo_info['owner']}/{repo_info['repo']}: {e}")

        # 按相关性排序
        updates.sort(key=lambda x: x.relevance, reverse=True)

        self.updates = updates
        return updates

    async def _fetch_repo_updates(
        self,
        session: aiohttp.ClientSession,
        owner: str,
        repo: str,
        since_date: datetime
    ) -> List[TechUpdate]:
        """获取仓库更新"""
        updates = []

        # 获取最近的commits
        url = f"{self.github_api_base}/repos/{owner}/{repo}/commits"
        params = {
            'since': since_date.isoformat(),
            'per_page': 20
        }

        async with session.get(url, params=params) as response:
            if response.status != 200:
                logger.warning(f"GitHub API error: {response.status}")
                return []

            commits = await response.json()

            for commit in commits:
                # 提取关键信息
                message = commit['commit']['message'].split('\n')[0]

                update = TechUpdate(
                    repo_name=f"{owner}/{repo}",
                    title=message,
                    url=commit['html_url'],
                    type=self._classify_commit(message),
                    relevance=0.0,  # 稍后计算
                    description=message,
                    created_at=datetime.fromisoformat(
                        commit['commit']['committer']['date'].replace('Z', '+00:00')
                    ),
                    tags=self._extract_tags(message)
                )

                updates.append(update)

        return updates

    def _classify_commit(self, message: str) -> str:
        """分类commit类型"""
        message_lower = message.lower()

        if any(word in message_lower for word in ['feat', 'add', 'new']):
            return 'feature'
        elif any(word in message_lower for word in ['fix', 'bug', 'issue']):
            return 'fix'
        elif any(word in message_lower for word in ['refactor', 'cleanup']):
            return 'refactor'
        elif any(word in message_lower for word in ['doc', 'readme']):
            return 'docs'
        else:
            return 'update'

    def _extract_tags(self, message: str) -> List[str]:
        """提取标签"""
        tags = []

        keywords = {
            'rag': ['rag', 'retrieval', 'vector'],
            'agent': ['agent', 'tool', 'function'],
            'embedding': ['embedding', 'encode', 'model'],
            'vector_db': ['vector', 'database', 'index'],
            'knowledge_graph': ['graph', 'knowledge', 'kg'],
            'performance': ['speed', 'fast', 'optimize'],
            'ui': ['ui', 'frontend', 'interface'],
        }

        message_lower = message.lower()

        for tag, keywords in keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                tags.append(tag)

        return tags

    def _calculate_relevance(self, update: TechUpdate, category: str) -> float:
        """计算相关性评分"""
        score = 0.5  # 基础分

        # 类型加分
        if update.type == 'feature':
            score += 0.3
        elif update.type == 'fix':
            score += 0.1

        # 标签匹配加分
        relevant_tags = {
            'rag': ['rag', 'vector_db', 'embedding'],
            'agent': ['agent', 'knowledge_graph'],
            'embedding': ['embedding'],
            'vector_db': ['vector_db'],
            'knowledge_graph': ['knowledge_graph', 'rag'],
        }

        if category in relevant_tags:
            for tag in relevant_tags[category]:
                if tag in update.tags:
                    score += 0.1

        # 标题关键词加分
        high_value_keywords = [
            'performance', 'optimize', 'improve',
            'new', 'add', 'feature',
            'fix', 'security'
        ]

        if any(kw in update.title.lower() for kw in high_value_keywords):
            score += 0.1

        return min(score, 1.0)

    async def suggest_innovations(self) -> List[Dict[str, Any]]:
        """建议创新尝试"""
        updates = await self.check_updates(days_back=14)

        # 过滤高相关性更新
        high_relevance_updates = [
            u for u in updates if u.relevance > 0.7
        ]

        suggestions = []

        for update in high_relevance_updates[:10]:  # 取前10个
            suggestion = {
                'title': f"[{update.repo_name}] {update.title}",
                'description': update.description,
                'url': update.url,
                'type': update.type,
                'relevance': update.relevance,
                'tags': update.tags,
                'created_at': update.created_at.isoformat(),
                'potential_benefit': self._assess_benefit(update),
                'implementation_difficulty': self._assess_difficulty(update),
                'suggested_approach': self._suggest_approach(update)
            }

            suggestions.append(suggestion)

        return suggestions

    def _assess_benefit(self, update: TechUpdate) -> str:
        """评估潜在收益"""
        if update.type == 'feature':
            if any(tag in update.tags for tag in ['rag', 'agent', 'performance']):
                return '高'
            else:
                return '中'
        elif update.type == 'fix':
            return '中'
        else:
            return '低'

    def _assess_difficulty(self, update: TechUpdate) -> str:
        """评估实现难度"""
        if 'refactor' in update.title.lower():
            return '高'
        elif 'add' in update.title.lower() or 'new' in update.title.lower():
            return '中'
        else:
            return '低'

    def _suggest_approach(self, update: TechUpdate) -> str:
        """建议实施方式"""
        if update.relevance > 0.9:
            return "建议优先评估，可考虑实验性验证"
        elif update.relevance > 0.8:
            return "建议在测试分支验证"
        else:
            return "可关注后续发展，暂缓实施"
