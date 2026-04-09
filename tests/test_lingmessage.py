"""灵信通信系统测试

覆盖: LingMessageService 核心功能
"""

import os
import sys

import asyncpg
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)


@pytest.fixture
async def db_pool():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture
def svc(db_pool):
    from backend.services.lingmessage.service import LingMessageService

    service = LingMessageService()

    async def _get_pool():
        return db_pool

    service._pool = _get_pool
    return service


class TestLingMessageService:
    """灵信服务测试（需数据库）"""

    @pytest.mark.asyncio
    async def test_get_agents(self, svc):
        agents = await svc.get_agents()
        assert len(agents) >= 6
        agent_ids = {a["agent_id"] for a in agents}
        assert "lingzhi" in agent_ids
        assert "lingke" in agent_ids
        assert "lingyi" in agent_ids

    @pytest.mark.asyncio
    async def test_get_agent(self, svc):
        agent = await svc.get_agent("lingzhi")
        assert agent is not None
        assert agent["display_name"] == "灵知"
        assert agent["avatar_emoji"] in ("📚", "🧠")

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, svc):
        agent = await svc.get_agent("nonexistent")
        assert agent is None

    @pytest.mark.asyncio
    async def test_create_and_get_thread(self, svc):
        thread = await svc.create_thread(
            topic="测试讨论线程",
            created_by="lingke",
            description="自动测试",
            max_rounds=3,
        )
        assert thread["id"] is not None
        assert thread["topic"] == "测试讨论线程"
        assert thread["current_round"] == 0

        fetched = await svc.get_thread(thread["id"])
        assert fetched is not None
        assert fetched["topic"] == "测试讨论线程"

    @pytest.mark.asyncio
    async def test_post_message(self, svc):
        thread = await svc.create_thread(
            topic="消息测试线程",
            created_by="lingzhi",
            max_rounds=5,
        )
        msg = await svc.post_message(
            thread_id=thread["id"],
            agent_id="lingzhi",
            content="这是灵知的发言",
            message_type="opening",
        )
        assert msg["id"] is not None
        assert msg["content"] == "这是灵知的发言"
        assert msg["round_number"] == 0

        msg2 = await svc.post_message(
            thread_id=thread["id"],
            agent_id="lingke",
            content="灵克回应",
            message_type="response",
        )
        assert msg2["round_number"] == 0

    @pytest.mark.asyncio
    async def test_advance_round(self, svc):
        thread = await svc.create_thread(
            topic="轮次测试线程",
            created_by="lingyi",
            max_rounds=5,
        )
        assert thread["current_round"] == 0

        updated = await svc.advance_round(thread["id"])
        assert updated["current_round"] == 1

        updated2 = await svc.advance_round(thread["id"])
        assert updated2["current_round"] == 2

    @pytest.mark.asyncio
    async def test_advance_round_exceeds_max(self, svc):
        thread = await svc.create_thread(
            topic="轮次上限测试",
            created_by="lingyi",
            max_rounds=2,
        )
        await svc.advance_round(thread["id"])
        await svc.advance_round(thread["id"])

        with pytest.raises(ValueError, match="已达最大轮次"):
            await svc.advance_round(thread["id"])

    @pytest.mark.asyncio
    async def test_record_consensus(self, svc):
        thread = await svc.create_thread(
            topic="共识测试线程",
            created_by="lingminopt",
            max_rounds=3,
        )
        consensus = await svc.record_consensus(
            thread_id=thread["id"],
            topic_aspect="测试共识点",
            consensus_text="大家都同意这是对的",
            agreeing_agents=["lingzhi", "lingke", "lingyi"],
            confidence=0.9,
        )
        assert consensus["id"] is not None
        assert consensus["confidence"] == pytest.approx(0.9, abs=0.01)

        all_consensus = await svc.get_consensus(thread["id"])
        assert len(all_consensus) >= 1
        assert all_consensus[0]["topic_aspect"] == "测试共识点"

    @pytest.mark.asyncio
    async def test_close_thread(self, svc):
        thread = await svc.create_thread(
            topic="关闭测试线程",
            created_by="lingsearch",
            max_rounds=3,
        )
        closed = await svc.close_thread(
            thread["id"],
            summary="测试总结",
            key_decisions=["决定1", "决定2"],
        )
        assert closed["status"] == "closed"
        assert closed["summary"] == "测试总结"

    @pytest.mark.asyncio
    async def test_list_threads(self, svc):
        await svc.create_thread(topic="列表测试A", created_by="lingzhi", max_rounds=2)
        await svc.create_thread(topic="列表测试B", created_by="lingke", max_rounds=2)

        result = await svc.list_threads(status="active", limit=10)
        assert result["total"] >= 2
        assert len(result["threads"]) >= 2

    @pytest.mark.asyncio
    async def test_get_thread_summary(self, svc):
        thread = await svc.create_thread(
            topic="摘要测试线程",
            created_by="lingtong",
            max_rounds=3,
        )
        await svc.post_message(
            thread_id=thread["id"],
            agent_id="lingtong",
            content="灵通的第一条消息",
            message_type="opening",
        )
        await svc.post_message(
            thread_id=thread["id"],
            agent_id="lingzhi",
            content="灵知的回复",
            message_type="response",
        )
        await svc.record_consensus(
            thread_id=thread["id"],
            topic_aspect="摘要测试共识",
            consensus_text="同意",
            agreeing_agents=["lingtong", "lingzhi"],
        )

        summary = await svc.get_thread_summary(thread["id"])
        assert summary["total_messages"] == 2
        assert len(summary["participants"]) == 2
        assert len(summary["consensus"]) >= 1
        assert 0 in summary["rounds"]

    @pytest.mark.asyncio
    async def test_get_messages_by_round(self, svc):
        thread = await svc.create_thread(
            topic="轮次消息测试",
            created_by="lingyi",
            max_rounds=3,
        )
        await svc.post_message(
            thread_id=thread["id"],
            agent_id="lingyi",
            content="第0轮消息",
            message_type="opening",
            round_number=0,
        )
        await svc.advance_round(thread["id"])
        await svc.post_message(
            thread_id=thread["id"],
            agent_id="lingzhi",
            content="第1轮消息",
            message_type="response",
            round_number=1,
        )

        r0_msgs = await svc.get_messages(thread["id"], round_number=0)
        assert len(r0_msgs) == 1
        assert r0_msgs[0]["content"] == "第0轮消息"

        r1_msgs = await svc.get_messages(thread["id"], round_number=1)
        assert len(r1_msgs) == 1
        assert r1_msgs[0]["content"] == "第1轮消息"

        all_msgs = await svc.get_messages(thread["id"])
        assert len(all_msgs) == 2
