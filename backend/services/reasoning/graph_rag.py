"""GraphRAG 推理模块

实现基于知识图谱的增强检索和推理
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .base import BaseReasoner, ReasoningResult, ReasoningStep

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """实体节点"""

    id: str
    name: str
    type: str  # 如：人物、概念、功法、穴位等
    description: str = ""
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "aliases": self.aliases,
        }


@dataclass
class Relation:
    """关系边"""

    source: str  # 源实体ID
    target: str  # 目标实体ID
    relation_type: str  # 关系类型：相关、包含、治疗、属于等
    weight: float = 1.0  # 关系权重

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "weight": self.weight,
        }


@dataclass
class KnowledgeGraph:
    """知识图谱"""

    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: List[Relation] = field(default_factory=list)

    def add_entity(self, entity: Entity) -> None:
        """添加实体"""
        self.entities[entity.id] = entity

    def add_relation(self, relation: Relation) -> None:
        """添加关系"""
        self.relations.append(relation)

    def get_neighbors(self, entity_id: str) -> List[Tuple[str, str, float]]:
        """获取邻居节点

        Returns:
            [(neighbor_id, relation_type, weight), ...]
        """
        neighbors = []
        for rel in self.relations:
            if rel.source == entity_id:
                neighbors.append((rel.target, rel.relation_type, rel.weight))
            elif rel.target == entity_id:
                neighbors.append((rel.source, rel.relation_type, rel.weight))
        return neighbors

    def find_path(self, start: str, end: str, max_depth: int = 3) -> Optional[List[str]]:
        """查找两个实体间的路径（BFS）

        Args:
            start: 起始实体ID
            end: 目标实体ID
            max_depth: 最大深度

        Returns:
            实体ID路径，如果不存在则返回None
        """
        if start not in self.entities or end not in self.entities:
            return None

        if start == end:
            return [start]

        queue = [(start, [start])]
        visited = {start}

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            neighbors = self.get_neighbors(current)
            for neighbor, _, _ in neighbors:
                if neighbor == end:
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于可视化）"""
        return {
            "entities": [e.to_dict() for e in self.entities.values()],
            "relations": [r.to_dict() for r in self.relations],
        }


class EntityExtractor:
    """实体抽取器

    从文本中抽取实体和关系
    """

    # 气功领域常见实体模式
    PATTERNS = {
        "功法": r"(八段锦|五禽戏|太极拳|六字诀|易筋经|形意拳|八卦掌)",
        "穴位": r"(百会|膻中|气海|关元|命门|涌泉|足三里|合谷|太冲)",
        "概念": r"(气|丹田|经络|气血|阴阳|虚实|寒热|表里)",
        "动作": r"(站桩|打坐|吐纳|导引|行气|采气|发气)",
        "脏腑": r"(心|肝|脾|肺|肾|胃|胆|膀胱|三焦)",
    }

    def __init__(self):
        self.entity_id_counter = 0

    def extract_entities(self, text: str) -> List[Entity]:
        """从文本中抽取实体

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        entities = []

        for entity_type, pattern in self.PATTERNS.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group()
                # 检查是否已存在
                if not any(e.name == name for e in entities):
                    entities.append(
                        Entity(id=f"entity_{self.entity_id_counter}", name=name, type=entity_type)
                    )
                    self.entity_id_counter += 1

        return entities

    def extract_relations(self, text: str, entities: List[Entity]) -> List[Relation]:
        """从文本中抽取关系

        Args:
            text: 输入文本
            entities: 已抽取的实体

        Returns:
            关系列表
        """
        relations = []

        # 简单关系抽取：共现
        entity_names = [e.name for e in entities]
        for i, name1 in enumerate(entity_names):
            for name2 in entity_names[i + 1 :]:
                # 检查两个实体是否在短距离内共现
                pattern = f"{name1}.{{0,50}}{name2}|{name2}.{{0,50}}{name1}"
                if re.search(pattern, text):
                    # 推断关系类型
                    rel_type = self._infer_relation_type(name1, name2)
                    relations.append(
                        Relation(
                            source=f"entity_{i}",
                            target=f"entity_{entity_names.index(name2)}",
                            relation_type=rel_type,
                            weight=1.0,
                        )
                    )

        return relations

    def _infer_relation_type(self, entity1: str, entity2: str) -> str:
        """推断两个实体间的关系类型"""
        # 这里可以添加更复杂的推断逻辑
        return "相关"


class GraphRAGReasoner(BaseReasoner):
    """GraphRAG 推理器

    使用知识图谱进行多跳推理
    """

    def __init__(self, api_key: str = "", api_url: str = ""):
        super().__init__(api_key, api_url)
        self.model_name = "deepseek-chat"
        self.kg = KnowledgeGraph()
        self.extractor = EntityExtractor()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建HTTP客户端（使用连接池）"""
        if self._http_client is None:
            async with self._client_lock:
                if self._http_client is None:
                    self._http_client = httpx.AsyncClient(
                        timeout=60.0,
                        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    )
        return self._http_client

    async def close(self) -> None:
        """关闭HTTP客户端连接"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def reason(
        self, question: str, context: Optional[List[Dict[str, Any]]] = None, **kwargs
    ) -> ReasoningResult:
        """执行GraphRAG推理

        Args:
            question: 用户问题
            context: 上下文文档
            **kwargs: 其他参数

        Returns:
            推理结果
        """
        start_time = time.time()

        # 分析问题类型
        query_type = self.analyze_query(question)

        # 从问题中抽取实体
        question_entities = self.extractor.extract_entities(question)

        # 从上下文构建知识图谱
        if context:
            await self._build_kg_from_context(context)

        # 查找相关实体和关系
        subgraph = self._extract_relevant_subgraph(question_entities)

        # 执行多跳推理
        reasoning_steps = self._perform_multi_hop_reasoning(question_entities, subgraph)

        # 生成答案
        answer = await self._generate_graph_answer(
            question, question_entities, subgraph, reasoning_steps
        )

        reasoning_time = time.time() - start_time

        return ReasoningResult(
            answer=answer,
            query_type=query_type,
            steps=[
                ReasoningStep(step_number=i + 1, content=step)
                for i, step in enumerate(reasoning_steps)
            ],
            sources=context or [],
            confidence=self._calculate_confidence(subgraph, question_entities),
            reasoning_time=reasoning_time,
            model_used=f"{self.model_name}+GraphRAG",
        )

    async def _build_kg_from_context(self, context: List[Dict[str, Any]]) -> None:
        """从上下文构建知识图谱

        Args:
            context: 上下文文档列表
        """
        for doc in context:
            content = doc.get("content", "")

            # 抽取实体
            entities = self.extractor.extract_entities(content)

            # 抽取关系
            relations = self.extractor.extract_relations(content, entities)

            # 添加到知识图谱
            for entity in entities:
                # 检查实体是否已存在
                existing = next(
                    (e for e in self.kg.entities.values() if e.name == entity.name), None
                )
                if existing:
                    entity.id = existing.id
                else:
                    self.kg.add_entity(entity)

            for relation in relations:
                self.kg.add_relation(relation)

    def _extract_relevant_subgraph(self, query_entities: List[Entity]) -> Dict[str, Any]:
        """提取相关的子图

        Args:
            query_entities: 查询中的实体

        Returns:
            子图数据
        """
        subgraph = {"entities": {}, "relations": []}

        # 找到查询实体在KG中的对应节点
        query_entity_ids = []
        for qe in query_entities:
            for eid, entity in self.kg.entities.items():
                if entity.name == qe.name:
                    query_entity_ids.append(eid)
                    subgraph["entities"][eid] = entity
                    break

        # 获取邻居节点（2跳）
        visited = set(query_entity_ids)
        for eid in query_entity_ids:
            neighbors = self.kg.get_neighbors(eid)
            for neighbor_id, rel_type, weight in neighbors:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    subgraph["entities"][neighbor_id] = self.kg.entities.get(
                        neighbor_id, Entity(id=neighbor_id, name=neighbor_id, type="unknown")
                    )

        # 获取相关关系
        for eid in visited:
            for rel in self.kg.relations:
                if rel.source in visited and rel.target in visited:
                    subgraph["relations"].append(rel)

        return subgraph

    def _perform_multi_hop_reasoning(
        self, query_entities: List[Entity], subgraph: Dict[str, Any]
    ) -> List[str]:
        """执行多跳推理

        Args:
            query_entities: 查询实体
            subgraph: 子图

        Returns:
            推理步骤列表
        """
        steps = []

        if len(query_entities) >= 2:
            # 尝试找到实体间的关系路径
            entity_ids = [e.id for e in query_entities if e.id in subgraph["entities"]]

            if len(entity_ids) >= 2:
                # 查找路径
                path = self.kg.find_path(entity_ids[0], entity_ids[1], max_depth=3)

                if path:
                    steps.append(
                        f"发现实体间路径: {' → '.join([self.kg.entities.get(pid, pid).name if isinstance(pid, str) else pid for pid in path])}"
                    )

                    # 分析路径上的关系
                    for i in range(len(path) - 1):
                        for rel in subgraph["relations"]:
                            if rel.source == path[i] and rel.target == path[i + 1]:
                                steps.append(
                                    f"关系: {self.kg.entities.get(rel.source, rel.source).name} --[{rel.relation_type}]--> {self.kg.entities.get(rel.target, rel.target).name}"
                                )
                                break

        # 添加相关实体信息
        if len(subgraph["entities"]) > len(query_entities):
            related = [
                e.name
                for e in subgraph["entities"].values()
                if e.name not in [qe.name for qe in query_entities]
            ]
            if related:
                steps.append(f"相关实体: {', '.join(related[:5])}")

        return steps

    async def _generate_graph_answer(
        self,
        question: str,
        query_entities: List[Entity],
        subgraph: Dict[str, Any],
        reasoning_steps: List[str],
    ) -> str:
        """生成基于图谱的答案

        Args:
            question: 原始问题
            query_entities: 查询实体
            subgraph: 子图
            reasoning_steps: 推理步骤

        Returns:
            生成的答案
        """
        if not reasoning_steps:
            return f"关于问题'{question}'，基于知识图谱分析，需要更多信息来回答。"

        # 构建提示词
        prompt = f"""基于以下知识图谱推理结果回答问题：

问题：{question}

识别的实体：{', '.join([e.name for e in query_entities])}

推理过程：
{chr(10).join([f'{i + 1}. {step}' for i, step in enumerate(reasoning_steps)])}

请给出详细的答案：
"""

        # 调用LLM生成答案（使用速率限制器）
        if self.llm_client:
            try:
                from backend.common.llm_api_wrapper import GLMRateLimitException

                response = await self.llm_client.call_api(
                    messages=[
                        {"role": "system", "content": "你是一个基于知识图谱的推理助手。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                )
                return response["choices"][0]["message"]["content"]

            except GLMRateLimitException as e:
                logger.error(f"Rate limit exceeded: {e}")
                # 继续到模拟答案

            except Exception as e:
                logger.error(f"LLM API call failed: {e}")
                # 继续到模拟答案

        # 降级到原始HTTP客户端
        elif self.api_key:
            try:
                client = await self._get_client()
                response = await client.post(
                    self.api_url or "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": "你是一个基于知识图谱的推理助手。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1500,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"LLM API call failed: {e}")

        # 模拟答案
        answer = f"""基于知识图谱的分析：

{chr(10).join([f'{i + 1}. {step}' for i, step in enumerate(reasoning_steps)])}

结论：
通过图谱推理，发现{' → '.join([e.name for e in query_entities[:3]])}之间存在关联关系。
"""

        return answer

    def _calculate_confidence(
        self, subgraph: Dict[str, Any], query_entities: List[Entity]
    ) -> float:
        """计算置信度"""
        entity_coverage = len([e for e in query_entities if e.id in subgraph["entities"]])
        base_confidence = min(entity_coverage * 0.2, 0.4)
        relation_bonus = min(len(subgraph["relations"]) * 0.05, 0.4)

        return round(min(base_confidence + relation_bonus, 1.0), 2)

    def get_graph_data(self) -> Dict[str, Any]:
        """获取图谱数据（用于可视化）

        Returns:
            图谱数据
        """
        return self.kg.to_dict()

    def add_entity_direct(self, entity: Entity) -> None:
        """直接添加实体到图谱"""
        self.kg.add_entity(entity)

    def add_relation_direct(self, relation: Relation) -> None:
        """直接添加关系到图谱"""
        self.kg.add_relation(relation)
