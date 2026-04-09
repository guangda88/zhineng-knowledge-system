"""Reasoning模块单元测试

测试CoT、ReAct和GraphRAG推理功能
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.reasoning.base import QueryType, ReasoningResult, ReasoningStep
from backend.services.reasoning.cot import CoTReasoner
from backend.services.reasoning.graph_rag import (
    Entity,
    EntityExtractor,
    GraphRAGReasoner,
    KnowledgeGraph,
    Relation,
)
from backend.services.reasoning.react import ReActReasoner

# ============================================================================
# BaseReasoner测试
# ============================================================================


class TestQueryType:
    """问题类型枚举测试"""

    def test_enum_values(self):
        """测试枚举值"""
        assert QueryType.FACTUAL.value == "factual"
        assert QueryType.REASONING.value == "reasoning"
        assert QueryType.MULTI_HOP.value == "multi_hop"
        assert QueryType.COMPARISON.value == "comparison"
        assert QueryType.EXPLANATION.value == "explanation"


class TestReasoningStep:
    """推理步骤测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        step = ReasoningStep(
            step_number=1,
            content="分析问题",
            thought="思考过程",
            action="search",
            observation="搜索结果",
        )

        data = step.to_dict()

        assert data["step_number"] == 1
        assert data["content"] == "分析问题"
        assert data["thought"] == "思考过程"
        assert data["action"] == "search"
        assert data["observation"] == "搜索结果"

    def test_to_dict_minimal(self):
        """测试最小化步骤转字典"""
        step = ReasoningStep(step_number=1, content="简单步骤")

        data = step.to_dict()

        assert data["step_number"] == 1
        assert data["content"] == "简单步骤"
        assert data["thought"] is None
        assert data["action"] is None
        assert data["observation"] is None


class TestReasoningResult:
    """推理结果测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        steps = [
            ReasoningStep(step_number=1, content="步骤1"),
            ReasoningStep(step_number=2, content="步骤2"),
        ]

        result = ReasoningResult(
            answer="这是答案",
            query_type=QueryType.REASONING,
            steps=steps,
            sources=[{"title": "文档1"}],
            confidence=0.85,
            reasoning_time=1.5,
            model_used="test-model",
        )

        data = result.to_dict()

        assert data["answer"] == "这是答案"
        assert data["query_type"] == "reasoning"
        assert len(data["steps"]) == 2
        assert data["confidence"] == 0.85
        assert data["reasoning_time"] == 1.5
        assert data["model_used"] == "test-model"
        assert "timestamp" in data


# ============================================================================
# CoTReasoner测试
# ============================================================================


class TestCoTReasoner:
    """CoT推理器测试套件"""

    @pytest.fixture
    def reasoner(self):
        """创建CoT推理器实例"""
        return CoTReasoner(api_key="", api_url="")

    def test_init(self, reasoner):
        """测试初始化"""
        assert reasoner.model_name == "deepseek-chat"
        assert reasoner.api_key == ""
        assert reasoner.api_url == ""

    def test_init_with_api(self):
        """测试使用API密钥初始化"""
        reasoner = CoTReasoner(api_key="test_key", api_url="http://test.com")
        assert reasoner.api_key == "test_key"
        assert reasoner.api_url == "http://test.com"

    def test_analyze_query_factual(self, reasoner):
        """测试分析事实性问题"""
        query_type = reasoner.analyze_query("气功的历史")  # "什么是"会匹配EXPLANATION，需要避免
        # 短问题默认为FACTUAL
        assert query_type == QueryType.FACTUAL

    def test_analyze_query_comparison(self, reasoner):
        """测试分析比较性问题"""
        query_type = reasoner.analyze_query("八段锦和太极拳有什么区别？")
        assert query_type == QueryType.COMPARISON

    def test_analyze_query_explanation(self, reasoner):
        """测试分析解释性问题"""
        query_type = reasoner.analyze_query("请解释气功的原理")
        assert query_type == QueryType.EXPLANATION

    def test_analyze_query_multi_hop(self, reasoner):
        """测试分析多跳推理问题"""
        query_type = reasoner.analyze_query("为什么气功能改善健康？")
        assert query_type == QueryType.MULTI_HOP

    def test_analyze_query_reasoning(self, reasoner):
        """测试分析推理问题"""
        long_question = (
            "这是一个非常长的问题，超过了二十个字符，需要详细的分析和推理才能得出正确答案"
        )
        query_type = reasoner.analyze_query(long_question)
        assert query_type == QueryType.REASONING

    def test_format_context_no_context(self, reasoner):
        """测试格式化空上下文"""
        result = reasoner.format_context([])
        assert result == "无相关上下文"

    def test_format_context_with_docs(self, reasoner):
        """测试格式化带文档的上下文"""
        context = [
            {"title": "文档1", "content": "内容1" * 100},
            {"title": "文档2", "content": "内容2" * 50},
        ]

        result = reasoner.format_context(context)

        assert "文档1" in result
        assert "文档2" in result
        assert "[1]" in result
        assert "[2]" in result

    def test_build_cot_prompt_factual(self, reasoner):
        """测试构建事实性问题的提示词"""
        prompt = reasoner._build_cot_prompt("什么是气功？", None, QueryType.FACTUAL)

        assert "事实性问题" in prompt
        assert "什么是气功？" in prompt
        assert "无参考上下文" in prompt

    def test_build_cot_prompt_with_context(self, reasoner):
        """测试构建带上下文的提示词"""
        context = [{"title": "气功介绍", "content": "气功是..."}]

        prompt = reasoner._build_cot_prompt("气功有什么作用？", context, QueryType.EXPLANATION)

        assert "逐步推理" in prompt
        assert "气功介绍" in prompt
        assert "气功是..." in prompt

    def test_parse_cot_response_with_thought(self, reasoner):
        """测试解析带思考过程的响应"""
        response = """思考过程：
1. 首先分析问题的关键点
   - 问题涉及气功
   - 需要解释作用

2. 然后逐步推理
   - 气功通过调节呼吸
   - 促进气血流通

3. 最后得出结论
   - 气功能改善健康

答案：
气功是一种传统的养生方法..."""

        steps, answer = reasoner._parse_cot_response(response)

        assert len(steps) >= 1
        assert "气功是一种" in answer
        assert steps[0].step_number == 1

    def test_parse_cot_response_without_structure(self, reasoner):
        """测试解析无结构的响应"""
        response = "这是一个简单的回答，没有思考过程部分。"

        steps, answer = reasoner._parse_cot_response(response)

        assert len(steps) == 1
        assert steps[0].content == response[:500]
        assert answer == response

    def test_parse_cot_response_with_answer_colon(self, reasoner):
        """测试解析使用冒号的答案标记"""
        response = """思考过程：
1. 分析问题

答案:这是答案内容"""

        steps, answer = reasoner._parse_cot_response(response)

        assert len(steps) >= 1
        assert "这是答案内容" in answer

    def test_calculate_confidence(self, reasoner):
        """测试计算置信度"""
        steps = [
            ReasoningStep(step_number=1, content="步骤1"),
            ReasoningStep(step_number=2, content="步骤2"),
            ReasoningStep(step_number=3, content="步骤3"),
        ]
        answer = "这是一个详细的答案，" * 50

        confidence = reasoner._calculate_confidence(steps, answer)

        assert 0 <= confidence <= 1.0
        assert confidence > 0.3  # 3步骤 + 长答案应该有较高置信度

    def test_calculate_confidence_minimal(self, reasoner):
        """测试最小置信度计算"""
        steps = [ReasoningStep(step_number=1, content="简短")]
        answer = "短"

        confidence = reasoner._calculate_confidence(steps, answer)

        assert 0 <= confidence <= 1.0

    def test_fallback_response(self, reasoner):
        """测试降级响应生成"""
        response = reasoner._build_fallback_response()

        assert "思考过程：" in response
        assert "答案：" in response
        assert "DEEPSEEK_API_KEY" in response

    @pytest.mark.asyncio
    async def test_reason_no_api_key(self, reasoner):
        """测试无API密钥时的推理应抛出RuntimeError"""
        with pytest.raises(RuntimeError, match="LLM API"):
            await reasoner.reason("什么是气功？")

    @pytest.mark.asyncio
    async def test_reason_with_context_no_api(self, reasoner):
        """测试带上下文但无API密钥的推理应抛出RuntimeError"""
        context = [
            {"title": "气功介绍", "content": "气功是一种传统的养生方法..."},
            {"title": "八段锦", "content": "八段锦是气功的一种..."},
        ]

        with pytest.raises(RuntimeError):
            await reasoner.reason("气功和八段锦有什么关系？", context=context)

    @pytest.mark.asyncio
    async def test_context_manager(self, reasoner):
        """测试异步上下文管理器"""
        async with CoTReasoner() as r:
            assert r is not None
            # 应该正常退出

    @pytest.mark.asyncio
    async def test_close(self, reasoner):
        """测试关闭客户端"""
        # 创建一个带客户端的reasoner
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()

        reasoner._http_client = mock_client

        await reasoner.close()

        mock_client.aclose.assert_called_once()
        assert reasoner._http_client is None


# ============================================================================
# ReActReasoner测试
# ============================================================================


class TestReActReasoner:
    """ReAct推理器测试套件"""

    @pytest.fixture
    def reasoner(self):
        """创建ReAct推理器实例"""
        return ReActReasoner(api_key="", api_url="")

    @pytest.fixture
    def sample_context(self):
        """示例上下文"""
        return [
            {"title": "八段锦介绍", "content": "八段锦是一种气功功法，包含八个动作..."},
            {"title": "太极拳介绍", "content": "太极拳是另一种传统功法..."},
        ]

    def test_init(self, reasoner):
        """测试初始化"""
        assert reasoner.model_name == "deepseek-chat"

    def test_default_tools(self, reasoner):
        """测试默认工具集"""
        context = [{"title": "测试", "content": "八段锦是气功的一种"}]

        tools = reasoner._default_tools(context)

        assert "search" in tools
        assert "lookup" in tools
        assert "description" in tools["search"]
        assert "description" in tools["lookup"]
        assert callable(tools["search"]["function"])
        assert callable(tools["lookup"]["function"])

    def test_build_react_prompt_initial(self, reasoner):
        """测试构建初始ReAct提示词"""
        tools = {"search": {"description": "搜索工具"}}
        context = "问题：什么是气功？\n\n"

        prompt = reasoner._build_react_prompt("什么是气功？", context, tools, has_history=False)

        assert "ReAct模式" in prompt
        assert "什么是气功？" in prompt
        assert "search" in prompt
        assert "思考：" in prompt or "思考：" in prompt
        assert "行动：" in prompt or "行动：" in prompt

    def test_build_react_prompt_with_history(self, reasoner):
        """测试构建带历史的ReAct提示词"""
        tools = {"search": {"description": "搜索工具"}}
        context = "问题：...\n执行 search: 气功\n观察: 找到结果\n\n"

        prompt = reasoner._build_react_prompt("问题", context, tools, has_history=True)

        assert "继续以下推理过程" in prompt
        assert "执行 search" in context

    def test_parse_react_response_full(self, reasoner):
        """测试解析完整的ReAct响应"""
        response = """思考：我需要搜索关于八段锦的信息
行动：search
行动输入：八段锦"""

        thought, action, action_input = reasoner._parse_react_response(response)

        assert "八段锦" in thought
        assert action == "search"
        assert action_input == "八段锦"

    def test_parse_react_response_minimal(self, reasoner):
        """测试解析最小ReAct响应"""
        response = "这是一个不规则的响应"

        thought, action, action_input = reasoner._parse_react_response(response)

        assert thought == ""
        assert action == "finish"
        assert action_input == ""

    def test_parse_react_response_with_finish(self, reasoner):
        """测试解析finish响应"""
        response = """思考：我已经找到答案
行动：finish
行动输入：八段锦是气功的一种"""

        thought, action, action_input = reasoner._parse_react_response(response)

        assert "找到答案" in thought
        assert action == "finish"
        assert "八段锦是" in action_input

    def test_fallback_response(self, reasoner):
        """测试降级响应生成"""
        response = reasoner._build_fallback_response()

        assert "思考：" in response or "思考:" in response
        assert "行动：" in response or "行动:" in response
        assert "finish" in response

    @pytest.mark.asyncio
    async def test_execute_tool_async(self, reasoner):
        """测试执行异步工具"""

        async def async_tool(query: str) -> str:
            return f"搜索结果: {query}"

        tool_info = {"function": async_tool}
        result = await reasoner._execute_tool("search", "八段锦", tool_info)

        assert "八段锦" in result
        assert "搜索结果" in result

    @pytest.mark.asyncio
    async def test_execute_tool_sync(self, reasoner):
        """测试执行同步工具"""

        def sync_tool(query: str) -> str:
            return f"同步结果: {query}"

        tool_info = {"function": sync_tool}
        result = await reasoner._execute_tool("lookup", "气功", tool_info)

        assert "气功" in result
        assert "同步结果" in result

    @pytest.mark.asyncio
    async def test_execute_tool_error(self, reasoner):
        """测试工具执行错误处理"""

        async def error_tool(query: str) -> str:
            raise ValueError("工具错误")

        tool_info = {"function": error_tool}
        result = await reasoner._execute_tool("test", "输入", tool_info)

        assert "工具执行错误" in result
        assert "工具错误" in result

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, reasoner):
        """测试未知工具"""
        result = await reasoner._execute_tool("unknown", "input", {})

        assert "未知工具" in result

    @pytest.mark.asyncio
    async def test_generate_final_answer_from_finish(self, reasoner):
        """测试从finish步骤生成答案"""
        steps = [
            ReasoningStep(step_number=1, content="思考"),
            ReasoningStep(
                step_number=2, content="最终思考", action="finish", observation="这是最终答案"
            ),
        ]

        answer = await reasoner._generate_final_answer("问题？", steps, None)

        assert "这是最终答案" in answer

    @pytest.mark.asyncio
    async def test_generate_final_answer_summary(self, reasoner):
        """测试生成摘要答案"""
        steps = [
            ReasoningStep(step_number=1, content="首先分析问题..."),
            ReasoningStep(step_number=2, content="然后搜索信息..."),
            ReasoningStep(step_number=3, content="最后总结答案..."),
        ]

        answer = await reasoner._generate_final_answer("问题？", steps, None)

        assert "3步推理" in answer
        assert "结论" in answer or "总结" in answer

    def test_calculate_confidence(self, reasoner):
        """测试计算置信度"""
        steps = [
            ReasoningStep(step_number=1, content="步骤1", action="search", observation="结果"),
            ReasoningStep(step_number=2, content="步骤2", action="lookup", observation="结果"),
            ReasoningStep(step_number=3, content="步骤3", action="finish", observation="完成"),
        ]

        confidence = reasoner._calculate_confidence(steps)

        assert 0 <= confidence <= 1.0
        assert confidence > 0.3  # 有行动执行应该有较高置信度

    def test_calculate_confidence_no_steps(self, reasoner):
        """测试无步骤时的置信度"""
        confidence = reasoner._calculate_confidence([])
        assert confidence == 0.3

    @pytest.mark.asyncio
    async def test_reason_no_api_key(self, reasoner):
        """测试无API密钥时的推理应抛出RuntimeError"""
        with pytest.raises(RuntimeError, match="LLM API"):
            await reasoner.reason("什么是气功？")

    @pytest.mark.asyncio
    async def test_reason_with_context_no_api(self, reasoner, sample_context):
        """测试带上下文但无API密钥的推理应抛出RuntimeError"""
        with pytest.raises(RuntimeError):
            await reasoner.reason("八段锦和太极拳有什么区别？", context=sample_context)

    @pytest.mark.asyncio
    async def test_reason_with_custom_tools_no_api(self, reasoner):
        """测试使用自定义工具但无API密钥应抛出RuntimeError"""

        async def custom_tool(query: str) -> str:
            return f"自定义工具结果: {query}"

        tools = {"custom": {"description": "自定义工具", "function": custom_tool}}

        with pytest.raises(RuntimeError):
            await reasoner.reason("测试问题", context=None, tools=tools, max_iterations=2)


# ============================================================================
# GraphRAG测试
# ============================================================================


class TestEntity:
    """实体测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        entity = Entity(
            id="e1", name="八段锦", type="功法", description="气功功法", aliases=["八段", "锦八段"]
        )

        data = entity.to_dict()

        assert data["id"] == "e1"
        assert data["name"] == "八段锦"
        assert data["type"] == "功法"
        assert data["description"] == "气功功法"
        assert data["aliases"] == ["八段", "锦八段"]


class TestRelation:
    """关系测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        relation = Relation(source="e1", target="e2", relation_type="相关", weight=1.5)

        data = relation.to_dict()

        assert data["source"] == "e1"
        assert data["target"] == "e2"
        assert data["relation_type"] == "相关"
        assert data["weight"] == 1.5


class TestKnowledgeGraph:
    """知识图谱测试"""

    @pytest.fixture
    def kg(self):
        """创建知识图谱"""
        return KnowledgeGraph()

    def test_add_entity(self, kg):
        """测试添加实体"""
        entity = Entity(id="e1", name="八段锦", type="功法")
        kg.add_entity(entity)

        assert "e1" in kg.entities
        assert kg.entities["e1"].name == "八段锦"

    def test_add_relation(self, kg):
        """测试添加关系"""
        relation = Relation(source="e1", target="e2", relation_type="相关")
        kg.add_relation(relation)

        assert len(kg.relations) == 1
        assert kg.relations[0].source == "e1"

    def test_get_neighbors(self, kg):
        """测试获取邻居节点"""
        kg.add_entity(Entity(id="e1", name="实体1", type="test"))
        kg.add_entity(Entity(id="e2", name="实体2", type="test"))
        kg.add_relation(Relation("e1", "e2", "相关"))

        neighbors = kg.get_neighbors("e1")

        assert len(neighbors) == 1
        assert neighbors[0][0] == "e2"
        assert neighbors[0][1] == "相关"

    def test_get_neighbors_bidirectional(self, kg):
        """测试双向邻居查询"""
        kg.add_entity(Entity(id="e1", name="实体1", type="test"))
        kg.add_entity(Entity(id="e2", name="实体2", type="test"))
        kg.add_relation(Relation("e1", "e2", "相关"))

        # e1应该能找到e2
        neighbors_e1 = kg.get_neighbors("e1")
        assert len(neighbors_e1) == 1

        # e2也应该能找到e1（反向）
        neighbors_e2 = kg.get_neighbors("e2")
        assert len(neighbors_e2) == 1

    def test_find_path_direct(self, kg):
        """测试查找直接路径"""
        kg.add_entity(Entity(id="e1", name="实体1", type="test"))
        kg.add_entity(Entity(id="e2", name="实体2", type="test"))
        kg.add_relation(Relation("e1", "e2", "相关"))

        path = kg.find_path("e1", "e2")

        assert path == ["e1", "e2"]

    def test_find_path_same_node(self, kg):
        """测试查找相同节点的路径"""
        kg.add_entity(Entity(id="e1", name="实体1", type="test"))

        path = kg.find_path("e1", "e1")

        assert path == ["e1"]

    def test_find_path_nonexistent(self, kg):
        """测试查找不存在节点的路径"""
        path = kg.find_path("e999", "e1000")

        assert path is None

    def test_find_path_multi_hop(self, kg):
        """测试查找多跳路径"""
        kg.add_entity(Entity(id="e1", name="实体1", type="test"))
        kg.add_entity(Entity(id="e2", name="实体2", type="test"))
        kg.add_entity(Entity(id="e3", name="实体3", type="test"))
        kg.add_relation(Relation("e1", "e2", "相关"))
        kg.add_relation(Relation("e2", "e3", "相关"))

        path = kg.find_path("e1", "e3", max_depth=3)

        assert path is not None
        assert path[0] == "e1"
        assert path[-1] == "e3"
        assert len(path) == 3

    def test_find_path_max_depth(self, kg):
        """测试最大深度限制"""
        kg.add_entity(Entity(id="e1", name="实体1", type="test"))
        kg.add_entity(Entity(id="e2", name="实体2", type="test"))
        kg.add_entity(Entity(id="e3", name="实体3", type="test"))
        kg.add_entity(Entity(id="e4", name="实体4", type="test"))
        kg.add_relation(Relation("e1", "e2", "相关"))
        kg.add_relation(Relation("e2", "e3", "相关"))
        kg.add_relation(Relation("e3", "e4", "相关"))

        path = kg.find_path("e1", "e4", max_depth=2)

        # 超过最大深度应该找不到路径
        assert path is None

    def test_to_dict(self, kg):
        """测试转换为字典"""
        kg.add_entity(Entity(id="e1", name="八段锦", type="功法"))
        kg.add_relation(Relation("e1", "e2", "相关"))

        data = kg.to_dict()

        assert "entities" in data
        assert "relations" in data
        assert len(data["entities"]) == 1
        assert len(data["relations"]) == 1


class TestEntityExtractor:
    """实体抽取器测试"""

    @pytest.fixture
    def extractor(self):
        """创建实体抽取器"""
        return EntityExtractor()

    def test_extract_entities_gongfa(self, extractor):
        """测试抽取功法实体"""
        text = "八段锦和太极拳都是传统的养生功法"

        entities = extractor.extract_entities(text)

        gongfa = [e for e in entities if e.type == "功法"]
        assert len(gongfa) >= 2
        names = [e.name for e in gongfa]
        assert "八段锦" in names
        assert "太极拳" in names

    def test_extract_entities_acupoint(self, extractor):
        """测试抽取穴位实体"""
        text = "按摩百会和膻中穴位可以调节气血"

        entities = extractor.extract_entities(text)

        acupoints = [e for e in entities if e.type == "穴位"]
        assert len(acupoints) >= 2
        names = [e.name for e in acupoints]
        assert "百会" in names
        assert "膻中" in names

    def test_extract_entities_concept(self, extractor):
        """测试抽取概念实体"""
        text = "气的运行与经络和阴阳平衡密切相关"

        entities = extractor.extract_entities(text)

        concepts = [e for e in entities if e.type == "概念"]
        assert len(concepts) >= 3
        names = [e.name for e in concepts]
        assert "气" in names
        assert "经络" in names
        assert "阴阳" in names

    def test_extract_entities_deduplication(self, extractor):
        """测试实体去重"""
        text = "八段锦是一种很好的功法，练习八段锦可以养生"

        entities = extractor.extract_entities(text)

        # 同一个实体不应该出现多次
        baduanjin = [e for e in entities if e.name == "八段锦"]
        assert len(baduanjin) == 1

    def test_extract_relations_cooccurrence(self, extractor):
        """测试基于共现的关系抽取"""
        text = "八段锦和太极拳都是气功功法"
        entities = [
            Entity(id="e1", name="八段锦", type="功法"),
            Entity(id="e2", name="太极拳", type="功法"),
        ]

        relations = extractor.extract_relations(text, entities)

        assert len(relations) >= 1
        assert relations[0].relation_type == "相关"

    def test_extract_relations_no_cooccurrence(self, extractor):
        """测试无共现时不抽取关系"""
        # 使用足够远的距离（超过50字符）
        text = "八段锦在这里。" + "x" * 100 + "太极拳在另一个地方。"
        entities = [
            Entity(id="e1", name="八段锦", type="功法"),
            Entity(id="e2", name="太极拳", type="功法"),
        ]

        relations = extractor.extract_relations(text, entities)

        # 相距太远不应该有关系
        assert len(relations) == 0


class TestGraphRAGReasoner:
    """GraphRAG推理器测试套件"""

    @pytest.fixture
    def reasoner(self):
        """创建GraphRAG推理器"""
        return GraphRAGReasoner(api_key="", api_url="")

    @pytest.fixture
    def sample_context(self):
        """示例上下文"""
        return [
            {
                "title": "气功介绍",
                "content": "八段锦是一种气功功法，通过调节呼吸和动作来促进气血流通。丹田是气的聚集点。",
            },
            {
                "title": "经络理论",
                "content": "经络是气血运行的通道，包括经脉和络脉。百会是头部重要穴位。",
            },
        ]

    def test_init(self, reasoner):
        """测试初始化"""
        assert reasoner.model_name == "deepseek-chat"
        assert isinstance(reasoner.kg, KnowledgeGraph)
        assert isinstance(reasoner.extractor, EntityExtractor)

    def test_add_entity_direct(self, reasoner):
        """测试直接添加实体"""
        entity = Entity(id="e1", name="测试", type="test")
        reasoner.add_entity_direct(entity)

        assert "e1" in reasoner.kg.entities

    def test_add_relation_direct(self, reasoner):
        """测试直接添加关系"""
        relation = Relation(source="e1", target="e2", relation_type="相关")
        reasoner.add_relation_direct(relation)

        assert len(reasoner.kg.relations) == 1

    def test_get_graph_data(self, reasoner):
        """测试获取图谱数据"""
        entity = Entity(id="e1", name="测试", type="test")
        reasoner.kg.add_entity(entity)

        data = reasoner.get_graph_data()

        assert "entities" in data
        assert "relations" in data
        assert len(data["entities"]) == 1

    @pytest.mark.asyncio
    async def test_build_kg_from_context(self, reasoner, sample_context):
        """测试从上下文构建知识图谱"""
        await reasoner._build_kg_from_context(sample_context)

        # 应该抽取到一些实体
        assert len(reasoner.kg.entities) > 0

        # 检查是否抽到常见实体
        entity_names = [e.name for e in reasoner.kg.entities.values()]
        assert any(name in entity_names for name in ["八段锦", "气功", "丹田", "经络", "百会"])

    @pytest.mark.asyncio
    async def test_extract_relevant_subgraph(self, reasoner):
        """测试提取相关子图"""
        # 先添加一些实体
        e1 = Entity(id="e1", name="八段锦", type="功法")
        e2 = Entity(id="e2", name="气功", type="概念")
        e3 = Entity(id="e3", name="丹田", type="概念")

        reasoner.kg.add_entity(e1)
        reasoner.kg.add_entity(e2)
        reasoner.kg.add_entity(e3)
        reasoner.kg.add_relation(Relation("e1", "e2", "属于"))
        reasoner.kg.add_relation(Relation("e2", "e3", "相关"))

        # 提取子图
        query_entities = [e1]
        subgraph = reasoner._extract_relevant_subgraph(query_entities)

        assert "entities" in subgraph
        assert "relations" in subgraph
        assert len(subgraph["entities"]) > 0

    def test_perform_multi_hop_reasoning(self, reasoner):
        """测试多跳推理"""
        # 设置图谱
        e1 = Entity(id="e1", name="八段锦", type="功法")
        e2 = Entity(id="e2", name="气功", type="概念")

        reasoner.kg.add_entity(e1)
        reasoner.kg.add_entity(e2)
        reasoner.kg.add_relation(Relation("e1", "e2", "属于"))

        subgraph = {"entities": {"e1": e1, "e2": e2}, "relations": [Relation("e1", "e2", "属于")]}

        steps = reasoner._perform_multi_hop_reasoning([e1, e2], subgraph)

        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_calculate_confidence(self, reasoner):
        """测试计算置信度"""
        subgraph = {
            "entities": {"e1": Entity(id="e1", name="测试", type="test")},
            "relations": [Relation("e1", "e2", "相关"), Relation("e1", "e3", "相关")],
        }
        query_entities = [
            Entity(id="e1", name="测试", type="test"),
            Entity(id="e2", name="测试2", type="test"),
        ]

        confidence = reasoner._calculate_confidence(subgraph, query_entities)

        assert 0 <= confidence <= 1.0

    @pytest.mark.asyncio
    async def test_reason_no_context(self, reasoner):
        """测试无上下文时的推理"""
        result = await reasoner.reason("什么是八段锦？")

        assert isinstance(result, ReasoningResult)
        assert result.answer
        assert "GraphRAG" in result.model_used

    @pytest.mark.asyncio
    async def test_reason_with_context(self, reasoner, sample_context):
        """测试带上下文的推理"""
        result = await reasoner.reason("八段锦和经络有什么关系？", context=sample_context)

        assert isinstance(result, ReasoningResult)
        assert result.sources == sample_context
        assert len(result.steps) > 0

    @pytest.mark.asyncio
    async def test_generate_graph_answer_no_steps(self, reasoner):
        """测试无推理步骤时生成答案"""
        answer = await reasoner._generate_graph_answer(
            "测试问题", [], {"entities": {}, "relations": []}, []
        )

        assert "需要更多信息" in answer

    @pytest.mark.asyncio
    async def test_context_manager(self, reasoner):
        """测试异步上下文管理器"""
        async with GraphRAGReasoner() as r:
            assert r is not None
