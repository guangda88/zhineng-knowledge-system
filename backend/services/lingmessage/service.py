"""灵信通信服务

提供灵字辈Agent之间的跨项目讨论功能：
- 创建讨论线程
- 发送消息
- 推进讨论轮次
- 记录共识
- 生成讨论摘要
"""

import json
import logging
from typing import Any, Dict, List, Optional

from backend.core.database import get_db_pool

logger = logging.getLogger(__name__)


class LingMessageService:
    """灵信通信服务"""

    async def _pool(self):
        pool = get_db_pool()
        if pool is None:
            from backend.core.database import init_db_pool

            pool = await init_db_pool()
        return pool

    async def get_agents(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """获取所有Agent列表

        Args:
            active_only: 是否只返回活跃的Agent

        Returns:
            Agent列表
        """
        pool = await self._pool()
        sql = "SELECT * FROM lingmessage_agents"
        if active_only:
            sql += " WHERE is_active = true"
        sql += " ORDER BY agent_id"
        rows = await pool.fetch(sql)
        return [dict(row) for row in rows]

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取单个Agent信息

        Args:
            agent_id: Agent标识

        Returns:
            Agent信息字典，不存在返回None
        """
        pool = await self._pool()
        row = await pool.fetchrow("SELECT * FROM lingmessage_agents WHERE agent_id = $1", agent_id)
        return dict(row) if row else None

    async def create_thread(
        self,
        topic: str,
        created_by: str,
        description: Optional[str] = None,
        priority: str = "normal",
        max_rounds: int = 10,
    ) -> Dict[str, Any]:
        """创建讨论线程

        Args:
            topic: 讨论主题
            created_by: 创建者agent_id
            description: 讨论描述
            priority: 优先级 (normal, high, critical)
            max_rounds: 最大轮次

        Returns:
            创建的线程信息
        """
        pool = await self._pool()
        row = await pool.fetchrow(
            """
            INSERT INTO lingmessage_threads (topic, description, created_by, priority, max_rounds)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            topic,
            description,
            created_by,
            priority,
            max_rounds,
        )
        logger.info(f"线程创建: [{row['id']}] {topic} (by {created_by})")
        return dict(row)

    async def get_thread(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """获取讨论线程详情

        Args:
            thread_id: 线程ID

        Returns:
            线程信息字典
        """
        pool = await self._pool()
        row = await pool.fetchrow("SELECT * FROM lingmessage_threads WHERE id = $1", thread_id)
        return dict(row) if row else None

    async def list_threads(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """列出讨论线程

        Args:
            status: 按状态过滤 (active, closed, archived)
            limit: 每页数量
            offset: 偏移量

        Returns:
            包含threads和total的字典
        """
        pool = await self._pool()
        conditions = []
        params = []
        idx = 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        total = await pool.fetchval(f"SELECT COUNT(*) FROM lingmessage_threads {where}", *params)

        rows = await pool.fetch(
            f"""
            SELECT * FROM lingmessage_threads {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )
        return {
            "threads": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def post_message(
        self,
        thread_id: int,
        agent_id: str,
        content: str,
        message_type: str = "response",
        round_number: Optional[int] = None,
        parent_id: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """发送消息

        Args:
            thread_id: 线程ID
            agent_id: 发送者agent_id
            content: 消息内容
            message_type: 消息类型 (opening, response, summary, consensus, dissent)
            round_number: 轮次（为空时自动取线程当前轮次）
            parent_id: 回复的消息ID
            metadata: 附加元数据

        Returns:
            创建的消息信息
        """
        pool = await self._pool()

        if round_number is None:
            thread = await pool.fetchrow(
                "SELECT current_round FROM lingmessage_threads WHERE id = $1", thread_id
            )
            if not thread:
                raise ValueError(f"线程 {thread_id} 不存在")
            round_number = thread["current_round"]

        row = await pool.fetchrow(
            """
            INSERT INTO lingmessage_messages
                (thread_id, agent_id, content, message_type, round_number, parent_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            thread_id,
            agent_id,
            content,
            message_type,
            round_number,
            parent_id,
            json.dumps(metadata or {}, ensure_ascii=False),
        )
        return dict(row)

    async def get_messages(
        self,
        thread_id: int,
        round_number: Optional[int] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取线程中的消息

        Args:
            thread_id: 线程ID
            round_number: 按轮次过滤
            limit: 数量限制
            offset: 偏移量

        Returns:
            消息列表
        """
        pool = await self._pool()

        if round_number is not None:
            rows = await pool.fetch(
                """
                SELECT m.*, a.display_name, a.avatar_emoji
                FROM lingmessage_messages m
                JOIN lingmessage_agents a ON m.agent_id = a.agent_id
                WHERE m.thread_id = $1 AND m.round_number = $2
                ORDER BY m.created_at ASC
                LIMIT $3 OFFSET $4
                """,
                thread_id,
                round_number,
                limit,
                offset,
            )
        else:
            rows = await pool.fetch(
                """
                SELECT m.*, a.display_name, a.avatar_emoji
                FROM lingmessage_messages m
                JOIN lingmessage_agents a ON m.agent_id = a.agent_id
                WHERE m.thread_id = $1
                ORDER BY m.round_number ASC, m.created_at ASC
                LIMIT $2 OFFSET $3
                """,
                thread_id,
                limit,
                offset,
            )
        return [dict(r) for r in rows]

    async def advance_round(self, thread_id: int) -> Dict[str, Any]:
        """推进到下一轮讨论

        Args:
            thread_id: 线程ID

        Returns:
            更新后的线程信息

        Raises:
            ValueError: 线程不存在或已达最大轮次
        """
        pool = await self._pool()
        row = await pool.fetchrow(
            """
            UPDATE lingmessage_threads
            SET current_round = current_round + 1
            WHERE id = $1 AND current_round < max_rounds
            RETURNING *
            """,
            thread_id,
        )
        if not row:
            thread = await pool.fetchrow(
                "SELECT * FROM lingmessage_threads WHERE id = $1", thread_id
            )
            if not thread:
                raise ValueError(f"线程 {thread_id} 不存在")
            raise ValueError(
                f"线程已达最大轮次 ({thread['max_rounds']}), "
                f"当前轮次: {thread['current_round']}"
            )
        logger.info(f"线程 [{thread_id}] 推进到第 {row['current_round']} 轮")
        return dict(row)

    async def record_consensus(
        self,
        thread_id: int,
        topic_aspect: str,
        consensus_text: str,
        agreeing_agents: List[str],
        disagreeing_agents: Optional[List[str]] = None,
        confidence: float = 0.8,
    ) -> Dict[str, Any]:
        """记录共识

        Args:
            thread_id: 线程ID
            topic_aspect: 共识涉及的方面
            consensus_text: 共识内容
            agreeing_agents: 同意的Agent列表
            disagreeing_agents: 不同意的Agent列表
            confidence: 共识置信度 (0-1)

        Returns:
            创建的共识记录
        """
        pool = await self._pool()
        row = await pool.fetchrow(
            """
            INSERT INTO lingmessage_consensus
                (thread_id, topic_aspect, consensus_text, agreeing_agents,
                 disagreeing_agents, confidence)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            thread_id,
            topic_aspect,
            consensus_text,
            agreeing_agents,
            disagreeing_agents or [],
            confidence,
        )
        logger.info(
            f"共识记录 [{thread_id}]: {topic_aspect} "
            f"(同意: {len(agreeing_agents)}, 置信度: {confidence})"
        )
        return dict(row)

    async def get_consensus(self, thread_id: int) -> List[Dict[str, Any]]:
        """获取线程的所有共识

        Args:
            thread_id: 线程ID

        Returns:
            共识列表
        """
        pool = await self._pool()
        rows = await pool.fetch(
            """
            SELECT * FROM lingmessage_consensus
            WHERE thread_id = $1
            ORDER BY created_at ASC
            """,
            thread_id,
        )
        return [dict(r) for r in rows]

    async def close_thread(
        self, thread_id: int, summary: Optional[str] = None, key_decisions: Optional[List] = None
    ) -> Dict[str, Any]:
        """关闭讨论线程

        Args:
            thread_id: 线程ID
            summary: 总结文本
            key_decisions: 关键决策列表

        Returns:
            更新后的线程信息
        """
        pool = await self._pool()
        row = await pool.fetchrow(
            """
            UPDATE lingmessage_threads
            SET status = 'closed', closed_at = NOW(),
                summary = COALESCE($2, summary),
                key_decisions = COALESCE($3, key_decisions)
            WHERE id = $1
            RETURNING *
            """,
            thread_id,
            summary,
            json.dumps(key_decisions or [], ensure_ascii=False),
        )
        if not row:
            raise ValueError(f"线程 {thread_id} 不存在")
        logger.info(f"线程 [{thread_id}] 已关闭")
        return dict(row)

    async def get_thread_summary(self, thread_id: int) -> Dict[str, Any]:
        """获取完整的线程摘要（线程信息+消息+共识）

        Args:
            thread_id: 线程ID

        Returns:
            包含thread, messages, consensus的完整摘要
        """
        thread = await self.get_thread(thread_id)
        if not thread:
            raise ValueError(f"线程 {thread_id} 不存在")

        messages = await self.get_messages(thread_id)
        consensus = await self.get_consensus(thread_id)

        agents = await self.get_agents()
        agent_map = {a["agent_id"]: a for a in agents}

        participant_ids = set(m["agent_id"] for m in messages)
        participants = [
            {
                "agent_id": aid,
                "display_name": agent_map[aid]["display_name"],
                "avatar_emoji": agent_map[aid]["avatar_emoji"],
                "message_count": sum(1 for m in messages if m["agent_id"] == aid),
            }
            for aid in participant_ids
            if aid in agent_map
        ]

        rounds = {}
        for m in messages:
            r = m["round_number"]
            if r not in rounds:
                rounds[r] = []
            rounds[r].append(
                {
                    "agent_id": m["agent_id"],
                    "display_name": m.get("display_name", m["agent_id"]),
                    "avatar_emoji": m.get("avatar_emoji", ""),
                    "content": m["content"],
                    "message_type": m["message_type"],
                    "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
                }
            )

        return {
            "thread": thread,
            "participants": participants,
            "total_messages": len(messages),
            "total_rounds": thread["current_round"],
            "rounds": dict(sorted(rounds.items())),
            "consensus": consensus,
        }
