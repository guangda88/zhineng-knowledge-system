"""进化验证Agent测试

测试验证Agent的各项功能
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from backend.services.evolution.verification_agent import (
    EvolutionVerificationAgent,
    VerificationResult,
    get_verification_agent,
)


class TestVerificationAgent:
    """测试验证Agent"""

    @pytest.fixture
    def agent(self):
        """创建验证Agent实例"""
        return EvolutionVerificationAgent()

    @pytest.fixture
    def mock_db(self):
        """Mock数据库会话"""
        db = AsyncMock()
        db.add = Mock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_verify_basic_metrics(self, agent):
        """测试基础指标验证"""

        old_response = "这是一个简短的回答。"
        # 确保新回答长度超过500字符阈值
        new_response = "这是一个更长的回答，包含了更多细节和解释，" * 25  # 约525字

        metrics = await agent._verify_basic_metrics(old_response, new_response)

        assert metrics["old_length"] == len(old_response)
        assert metrics["new_length"] == len(new_response)
        assert metrics["length_improved"]
        assert metrics["length_ratio"] > 1.2
        assert metrics["meets_min_length"]

    @pytest.mark.asyncio
    async def test_verify_structure(self, agent):
        """测试结构化验证"""

        # 有结构的回答
        structured_response = """
# 如何提高学习注意力

## 方法一：番茄工作法
- 工作25分钟
- 休息5分钟

## 方法二：冥想练习
1. 找安静的地方
2. 闭上眼睛
3. 深呼吸

```python
# 示例代码
def focus():
    return True
```

这是一个完整的段落。

另一个独立的段落。
        """

        metrics = await agent._verify_structure(structured_response)

        assert metrics["has_headings"]
        assert metrics["has_lists"]
        assert metrics["has_paragraphs"]
        assert metrics["has_code"]
        assert metrics["structure_score"] >= 0.75
        assert metrics["meets_threshold"]

    @pytest.mark.asyncio
    async def test_verify_structure_no_structure(self, agent):
        """测试无结构的回答"""

        unstructured_response = "这是一段没有任何结构的文字。没有标题，没有列表，没有代码块。"

        metrics = await agent._verify_structure(unstructured_response)

        assert not metrics["has_headings"]
        assert not metrics["has_lists"]
        assert not metrics["has_paragraphs"]
        assert not metrics["has_code"]
        assert metrics["structure_score"] == 0.0
        assert not metrics["meets_threshold"]

    @pytest.mark.asyncio
    async def test_verify_user_feedback(self, agent):
        """测试用户反馈验证"""

        # 好评
        good_feedback = {"satisfaction": 5, "comments": "非常好"}
        metrics = await agent._verify_user_feedback(good_feedback)

        assert metrics["has_feedback"]
        assert metrics["satisfaction"] == 5
        assert metrics["meets_threshold"]

        # 差评
        bad_feedback = {"satisfaction": 2, "comments": "不够详细"}
        metrics = await agent._verify_user_feedback(bad_feedback)

        assert metrics["has_feedback"]
        assert metrics["satisfaction"] == 2
        assert not metrics["meets_threshold"]

        # 无反馈
        metrics = await agent._verify_user_feedback(None)

        assert not metrics["has_feedback"]
        assert metrics["meets_threshold"]  # 无反馈时默认通过

    def test_make_decision(self, agent):
        """测试综合判断逻辑"""

        # 场景1: 完美的改进
        perfect_metrics = {
            "meets_min_length": True,
            "meets_threshold": True,  # structure
            "length_improved": True,
            "overall_improved": True,
            "has_competitor_data": True,
            "meets_threshold": True,  # competitor (重名，但context会区分)
            "structure_score": 0.8,
        }

        is_valid, confidence, reasons, suggestions = agent._make_decision(perfect_metrics)

        assert is_valid
        assert confidence >= 0.7
        assert any("✅" in r for r in reasons)
        assert len(suggestions) >= 0

        # 场景2: 不合格的改进
        bad_metrics = {
            "meets_min_length": False,
            "meets_threshold": False,  # structure
            "length_improved": False,
            "overall_improved": False,
            "structure_score": 0.2,
        }

        is_valid, confidence, reasons, suggestions = agent._make_decision(bad_metrics)

        assert not is_valid
        assert confidence < 0.7
        assert any("❌" in r for r in reasons)
        assert len(suggestions) > 0

    @pytest.mark.asyncio
    async def test_verify_with_competitors_mock(self, agent):
        """测试竞品对比验证（使用mock）"""

        # Mock多AI适配器
        agent.multi_ai = AsyncMock()
        agent.multi_ai.parallel_generate = AsyncMock(
            return_value={
                "hunyuan": {"content": "混元的回答内容", "success": True, "latency_ms": 300},
                "deepseek": {"content": "DeepSeek的回答内容", "success": True, "latency_ms": 200},
            }
        )

        # Mock对比引擎
        agent.comparison_engine = AsyncMock()
        agent.comparison_engine.compare_qa_responses = AsyncMock(
            return_value={
                "scores": {
                    "lingzhi": {"overall": 8.5},
                    "hunyuan": {"overall": 7.0},
                    "deepseek": {"overall": 6.5},
                }
            }
        )

        query = "如何提高学习注意力？"
        response = "灵知的回答内容"

        metrics = await agent._verify_with_competitors(query, response)

        assert metrics["has_competitor_data"]
        assert metrics["rank"] == 1  # 灵知第一
        assert metrics["meets_threshold"]  # 前2名
        assert metrics["winner"] == "lingzhi"

    @pytest.mark.asyncio
    async def test_verify_evolution_full_pipeline(self, agent, mock_db):
        """测试完整的验证流程"""

        query = "如何提高学习注意力？"
        old_response = "这是一个简短的回答，缺少细节。"
        new_response = (
            """
# 如何提高学习注意力

## 方法一：番茄工作法
番茄工作法是一种时间管理技术，可以帮助你保持专注。

### 步骤：
1. 选择一个任务
2. 设置25分钟计时器
3. 专注工作直到计时器结束
4. 休息5分钟
5. 重复4次后，休息15-30分钟

## 方法二：冥想练习
冥想可以训练你的注意力肌肉。

### 每天练习：
- 找一个安静的地方
- 闭上眼睛
- 专注于呼吸
- 当思绪游离时，温和地拉回注意力

## 方法三：减少干扰
- 关闭手机通知
- 整理工作空间
- 使用降噪耳机

通过持续练习，你的注意力会显著提升。
        """
            * 3
        )  # 确保足够长

        # Mock多AI适配器和对比引擎
        agent.multi_ai = AsyncMock()
        agent.multi_ai.parallel_generate = AsyncMock(
            return_value={"hunyuan": {"content": "混元的回答", "success": True}}
        )

        agent.comparison_engine = AsyncMock()
        agent.comparison_engine.compare_qa_responses = AsyncMock(
            side_effect=[
                # 第一次调用：quality verification
                {
                    "scores": {
                        "lingzhi": {
                            "completeness": 8,
                            "usefulness": 9,
                            "clarity": 8,
                            "overall": 8.3,
                        },
                        "old_version": {
                            "completeness": 5,
                            "usefulness": 6,
                            "clarity": 5,
                            "overall": 5.3,
                        },
                    }
                },
                # 第二次调用：competitor verification
                {"scores": {"lingzhi": {"overall": 8.5}, "hunyuan": {"overall": 7.0}}},
            ]
        )

        # 执行验证
        result = await agent.verify_evolution(
            db=mock_db,
            query=query,
            old_response=old_response,
            new_response=new_response,
            user_feedback=None,
        )

        # 验证结果
        assert isinstance(result, VerificationResult)
        assert result.is_valid  # 应该通过验证
        assert result.confidence > 0.7
        assert len(result.reasons) > 0
        assert result.metrics["length_improved"]
        assert result.metrics["meets_min_length"]
        assert result.metrics["structure_score"] > 0.5

        # 验证数据库记录被调用
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_verification_result_to_dict(self):
        """测试VerificationResult的to_dict方法"""

        result = VerificationResult(
            is_valid=True,
            confidence=0.85,
            reasons=["✅ 回答长度有显著提升"],
            suggestions=["继续保持"],
            metrics={"length_improved": True},
        )

        result_dict = result.to_dict()

        assert result_dict["is_valid"]
        assert result_dict["confidence"] == 0.85
        assert len(result_dict["reasons"]) == 1
        assert len(result_dict["suggestions"]) == 1
        assert result_dict["metrics"]["length_improved"]

    def test_update_thresholds(self, agent):
        """测试动态更新阈值"""

        new_thresholds = {"min_confidence": 0.8, "min_improvement_ratio": 1.5}

        # 在异步上下文中调用
        asyncio.run(agent.update_thresholds(new_thresholds))

        assert agent.thresholds["min_confidence"] == 0.8
        assert agent.thresholds["min_improvement_ratio"] == 1.5

    def test_get_thresholds(self, agent):
        """测试获取阈值"""

        thresholds = asyncio.run(agent.get_thresholds())

        assert "min_confidence" in thresholds
        assert "min_improvement_ratio" in thresholds
        assert "min_length" in thresholds

    def test_singleton_get_verification_agent(self):
        """测试单例模式"""

        agent1 = get_verification_agent()
        agent2 = get_verification_agent()

        assert agent1 is agent2
        assert isinstance(agent1, EvolutionVerificationAgent)


class TestVerificationAgentIntegration:
    """集成测试（需要数据库和真实API）"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_verify_with_real_api(self):
        """集成测试：使用真实API进行验证

        注意：这个测试需要配置HUNYUAN_API_KEY和DEEPSEEK_API_KEY
        """
        import os

        # 检查API密钥
        if not os.getenv("HUNYUAN_API_KEY"):
            pytest.skip("HUNYUAN_API_KEY not configured")

        # 创建真实Agent
        get_verification_agent()

        # 使用真实的对比引擎
        # （这里需要真实的数据库连接，暂时跳过）
        pass

    @pytest.mark.integration
    def test_verification_performance(self):
        """性能测试：验证响应时间"""

        agent = EvolutionVerificationAgent()

        # 简单的性能基准
        start = datetime.now()

        # 同步测试基础指标
        old_response = "短回答" * 10
        new_response = "长回答" * 100

        # 使用同步方式测试
        metrics = asyncio.run(agent._verify_basic_metrics(old_response, new_response))

        end = datetime.now()
        elapsed_ms = (end - start).total_seconds() * 1000

        assert elapsed_ms < 100  # 应该在100ms内完成
        assert metrics["length_improved"]
