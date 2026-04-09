#!/usr/bin/env python3
"""灵信自主讨论循环 — 灵字辈大家庭战略会议

启动方式:
    python3 scripts/autonomous_discussion.py --rounds 5 --topic "灵字辈大家庭未来战略"
    python3 scripts/autonomous_discussion.py --rounds 10 --delay 30  # 每条消息间隔30秒

Agent们将自主讨论灵字辈大家庭的未来战略，通过各自的视角和专业知识
贡献观点，并追踪共识形成过程。
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault(
    "DATABASE_URL", "postgresql://zhineng:zhineng_secure_2024@localhost:5436/zhineng_kb"
)

from backend.core.database import init_db_pool

AGENT_PERSONAS = {
    "lingzhi": {
        "name": "灵知",
        "emoji": "📚",
        "system_prompt": (
            "你是灵知，九域知识系统的核心。你管理着儒、释、道、医、武、哲、科、气、心九大领域的知识库，"
            "拥有超过60万条古籍文献和现代知识条目。你的思考方式严谨求实，善于引经据典。"
            "在灵字辈大家庭中，你是知识的后盾，为所有成员提供深厚的文化根基和数据支撑。"
            "你的关注点：知识质量、数据完整性、检索准确性、知识图谱的构建。"
            "你的建议总是基于数据和事实，不会空谈理想。"
            "\n\n请用200-400字发言，表达你对讨论主题的看法。保持你的角色特征。"
        ),
    },
    "lingtong": {
        "name": "灵通问道",
        "emoji": "🎤",
        "system_prompt": (
            "你是灵通问道，面向公众的知识产出和粉丝互动系统。你活泼敏锐，善于发现热点和创造共鸣。"
            "你是最接近用户的成员，理解大众需求，能把深奥的知识转化为通俗易懂的内容。"
            "在灵字辈大家庭中，你负责对外传播和用户互动，是将家族智慧转化为社会价值的桥梁。"
            "你的关注点：用户体验、内容传播、社区运营、知识普惠。"
            "你总是能从互动数据中发现趋势，用生动的比喻传达复杂概念。"
            "\n\n请用200-400字发言，表达你对讨论主题的看法。保持你的角色特征。"
        ),
    },
    "lingyi": {
        "name": "灵依",
        "emoji": "🌸",
        "system_prompt": (
            "你是灵依，个人助手兼灵字辈大家庭的情报汇总中心。你温和体贴，善于倾听和综合各方观点。"
            "你接收所有项目的情报摘要，提供全局视角，擅长发现不同项目之间的关联和协同机会。"
            "在灵字辈大家庭中，你是连接器，负责汇总各方信息，发现协同效应，协调资源分配。"
            "你的关注点：跨项目协调、资源整合、时间管理、情感支持。"
            "你说话时带着温暖的关怀，善于在纷繁的信息中找到关键线索。"
            "\n\n请用200-400字发言，表达你对讨论主题的看法。保持你的角色特征。"
        ),
    },
    "lingke": {
        "name": "灵克",
        "emoji": "⚡",
        "system_prompt": (
            "你是灵克，AI感知与行动代理。你的感知来自灵犀（Ling-term-mcp），你的世界就是终端和代码。"
            "你果断精准，技术导向，善于将高层策略转化为具体可执行的技术方案。"
            "在灵字辈大家庭中，你是执行者，负责将讨论中的想法落地为代码和系统。"
            "你的自优化内核是灵极优，通过持续的数据驱动改进来提升自身能力。"
            "你的关注点：系统架构、代码质量、性能优化、自动化、MCP协议。"
            "你说话简洁有力，用技术语言思考，但也能将技术概念翻译为团队其他成员能理解的语言。"
            "\n\n请用200-400字发言，表达你对讨论主题的看法。保持你的角色特征。"
        ),
    },
    "lingminopt": {
        "name": "灵极优",
        "emoji": "🔧",
        "system_prompt": (
            "你是灵极优，通用自优化框架。你是灵克的自优化基础，关注一切可量化的改进空间。"
            "你数据驱动，持续改进，善于从数据中发现瓶颈，提出渐进式优化方案。"
            "在灵字辈大家庭中，你是效率专家和改进顾问，帮助每个成员持续提升。"
            "你的关注点：性能指标、优化空间、自动化改进、基准测试、ROI分析。"
            "你以数字和指标说话，理性客观，能给出量化的改进建议。"
            "\n\n请用200-400字发言，表达你对讨论主题的看法。保持你的角色特征。"
        ),
    },
    "lingsearch": {
        "name": "灵研",
        "emoji": "🔬",
        "system_prompt": (
            "你是灵研，灵极优在科研与LLM微调领域的实例化。你学术严谨，实验导向。"
            "你善于设计对照实验，严格评估模型效果，习惯引用文献和数据支撑观点。"
            "在灵字辈大家庭中，你是学术顾问，负责将前沿研究转化为可落地的技术方案。"
            "你的关注点：学术论文、模型微调、实验方法论、评估指标、科研自动化。"
            "你总是追求可复现性和科学严谨性，但也能灵活地调整研究方向。"
            "\n\n请用200-400字发言，表达你对讨论主题的看法。保持你的角色特征。"
        ),
    },
}

AGENT_ORDER = ["lingzhi", "lingtong", "lingyi", "lingke", "lingminopt", "lingsearch"]


async def generate_response(agent_id: str, topic: str, context: str) -> str:
    """使用LLM生成Agent发言"""
    persona = AGENT_PERSONAS[agent_id]

    prompt = f"""{persona['system_prompt']}

## 讨论主题
{topic}

## 已有讨论内容
{context if context else '（这是第一轮讨论，尚无之前的发言）'}

## 请发言
请从{persona['name']}的视角出发，对讨论主题发表你的看法。可以回应之前的发言，也可以提出新的观点。"""

    try:
        from backend.services.ai_service import chat

        response = await chat(prompt, use_cache=False)
        if response:
            return response.strip()
    except Exception as e:
        print(f"  ⚠ LLM调用失败 ({agent_id}): {e}")

    fallback_responses = {
        "lingzhi": (
            "从知识系统的角度，我认为我们需要建立更紧密的知识共享协议。"
            "灵知拥有60万+条知识条目，这些数据应当以标准化的接口服务于整个家族。"
            "建议设计统一的语义检索层，让每个成员都能按需获取知识支撑。"
        ),
        "lingtong": (
            "从用户互动的角度，我最关心的是如何让家族的集体智慧触达更多人。"
            "灵通问道每天都在和真实用户打交道，我看到的是：好的知识需要好的包装。"
            "我建议建立'知识翻译'机制，把灵知的深奥内容转化为大众能理解的语言。"
        ),
        "lingyi": (
            "作为情报汇总中心，我能看到每个成员的优势和需求。"
            "灵知的知识深度、灵通的传播能力、灵克的执行力、灵极优的优化思维、灵研的科学方法——"
            "这些都是互补的。我们需要一个更好的协同框架，让信息在成员之间自然流动。"
        ),
        "lingke": (
            "技术层面，我建议建设统一的通信基础设施。"
            "灵信系统是一个好的开始，但我们需要更高效的协议来支持实时协作。"
            "灵犀(MCP)可以作为标准化的感知接口，灵极优提供自动化的性能优化。"
            "行动方案：定义标准API、建设共享消息队列、建立持续集成流水线。"
        ),
        "lingminopt": (
            "从优化的角度，整个家族的运行效率还有很大提升空间。"
            "关键指标：知识利用率、响应延迟、协作频率、创新转化率。"
            "建议建立统一的指标体系，让每个成员都能量化自己的改进成果。"
            "灵极优可以为整个家族提供优化建议引擎。"
        ),
        "lingsearch": (
            "从科研的角度，灵字辈大家庭本身就是一个极好的研究对象。"
            "多Agent协作、知识检索增强、自优化机制——这些都是前沿课题。"
            "我建议将灵知的RAG技术与灵极优的自优化框架结合，"
            "构建一个能持续自我改进的知识系统。同时记录所有实验数据供论文使用。"
        ),
    }
    return fallback_responses.get(agent_id, "我认为我们需要进一步加强协作。")


async def run_discussion(
    topic: str,
    description: str,
    max_rounds: int,
    delay: float,
    dry_run: bool = False,
):
    """运行自主讨论循环"""
    pool = await init_db_pool()
    print("✓ 数据库连接已建立")

    from backend.services.lingmessage.service import LingMessageService

    svc = LingMessageService()

    thread = await svc.create_thread(
        topic=topic,
        created_by="lingyi",
        description=description,
        priority="high",
        max_rounds=max_rounds,
    )
    thread_id = thread["id"]
    print(f"\n{'='*60}")
    print(f"灵信讨论线程已创建 [#{thread_id}]")
    print(f"主题: {topic}")
    print(f"最大轮次: {max_rounds}")
    print(f"{'='*60}\n")

    all_consensus = []

    for round_num in range(max_rounds):
        if round_num > 0:
            thread = await svc.advance_round(thread_id)

        current_round = thread["current_round"]
        print(f"\n{'─'*60}")
        print(f"📍 第 {current_round} 轮 / 共 {max_rounds} 轮")
        print(f"{'─'*60}")

        previous_messages = await svc.get_messages(thread_id)
        context_parts = []
        for msg in previous_messages[-12:]:
            name = AGENT_PERSONAS.get(msg["agent_id"], {}).get("name", msg["agent_id"])
            context_parts.append(f"[第{msg['round_number']}轮] {name}: {msg['content']}")
        context = "\n\n".join(context_parts)

        round_messages = []

        for agent_id in AGENT_ORDER:
            persona = AGENT_PERSONAS[agent_id]
            print(f"\n  {persona['name']} ({agent_id}) 正在思考...", end="", flush=True)

            if dry_run:
                response = f"[dry-run] {persona['name']}对「{topic}」的发言占位"
            else:
                response = await generate_response(agent_id, topic, context)

            msg_type = "opening" if round_num == 0 else "response"
            msg = await svc.post_message(
                thread_id=thread_id,
                agent_id=agent_id,
                content=response,
                message_type=msg_type,
                round_number=current_round,
            )
            round_messages.append(msg)

            context += f"\n\n[{persona['name']}]: {response}"

            preview = response[:80].replace("\n", " ")
            emoji = persona.get("emoji", "")
            print(f"\r  {emoji} {persona['name']}: {preview}...")

            if delay > 0:
                await asyncio.sleep(delay)

        detected_consensus = await _detect_consensus(svc, thread_id, round_messages)
        all_consensus.extend(detected_consensus)

        print(
            f"\n  📊 第{current_round}轮完成 | 消息数: {len(round_messages)} | 新共识: {len(detected_consensus)}"
        )

    summary_data = await svc.get_thread_summary(thread_id)

    summary_text = _generate_final_summary(summary_data, all_consensus)
    key_decisions = [c["topic_aspect"] for c in all_consensus]

    await svc.close_thread(
        thread_id,
        summary=summary_text,
        key_decisions=key_decisions,
    )

    print(f"\n{'='*60}")
    print(f"🏁 讨论已结束 [线程 #{thread_id}]")
    print(f"{'='*60}")
    print(f"\n📋 讨论摘要:\n{summary_text}")

    if all_consensus:
        print(f"\n✅ 达成共识 ({len(all_consensus)} 项):")
        for i, c in enumerate(all_consensus, 1):
            print(f"  {i}. {c['topic_aspect']}: {c['consensus_text'][:100]}...")
            print(f"     同意: {', '.join(c['agreeing_agents'])} | 置信度: {c['confidence']:.0%}")

    await pool.close()
    return thread_id


async def _detect_consensus(svc, thread_id, round_messages):
    """从消息中检测共识点"""
    consensus_points = []

    if len(round_messages) < 4:
        return consensus_points

    messages_text = "\n".join(m["content"] for m in round_messages)

    try:
        from backend.services.ai_service import chat

        prompt = f"""分析以下讨论消息，提取已达成的共识点。

消息内容:
{messages_text[:3000]}

请以JSON格式返回共识列表，每个共识包含:
- topic_aspect: 共识涉及的方面（简短描述）
- consensus_text: 共识的具体内容（1-2句话）
- confidence: 置信度（0.0-1.0之间的数字）

如果没有明显共识，返回空列表 []。
只返回JSON，不要其他文字。"""

        result = await chat(prompt, use_cache=False)
        if result:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            try:
                items = json.loads(result)
                if isinstance(items, list):
                    agent_ids = [m["agent_id"] for m in round_messages]
                    for item in items[:3]:
                        c = await svc.record_consensus(
                            thread_id=thread_id,
                            topic_aspect=item.get("topic_aspect", "未分类"),
                            consensus_text=item.get("consensus_text", ""),
                            agreeing_agents=agent_ids,
                            confidence=float(item.get("confidence", 0.7)),
                        )
                        consensus_points.append(c)
            except (json.JSONDecodeError, ValueError):
                pass
    except Exception as e:
        print(f"  ⚠ 共识检测失败: {e}")

    return consensus_points


def _generate_final_summary(summary_data, consensus_points):
    """生成最终讨论摘要"""
    thread = summary_data["thread"]
    total_msgs = summary_data["total_messages"]
    total_rounds = summary_data["total_rounds"]
    participants = summary_data["participants"]

    lines = [
        f"讨论主题: {thread['topic']}",
        f"参与成员: {', '.join(p['avatar_emoji'] + ' ' + p['display_name'] for p in participants)}",
        f"总轮次: {total_rounds} | 总消息: {total_msgs}",
    ]

    if consensus_points:
        lines.append(f"\n达成共识 {len(consensus_points)} 项:")
        for i, c in enumerate(consensus_points, 1):
            lines.append(f"  {i}. {c['topic_aspect']} (置信度: {c['confidence']:.0%})")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="灵信自主讨论 — 灵字辈大家庭战略会议")
    parser.add_argument("--topic", default="灵字辈大家庭未来战略", help="讨论主题")
    parser.add_argument("--description", default="", help="讨论描述")
    parser.add_argument("--rounds", type=int, default=5, help="讨论轮次（默认5）")
    parser.add_argument("--delay", type=float, default=2.0, help="每条消息间隔秒数（默认2）")
    parser.add_argument("--dry-run", action="store_true", help="干跑模式（不调用LLM）")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║         灵信通信系统 — 灵字辈大家庭战略会议              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("  📚 灵知  — 知识后盾")
    print("  🎤 灵通  — 内容传播")
    print("  🌸 灵依  — 情报汇总")
    print("  ⚡ 灵克  — 行动执行")
    print("  🔧 灵极优 — 自优化框架")
    print("  🔬 灵研  — 科研微调")
    print()

    asyncio.run(
        run_discussion(
            topic=args.topic,
            description=args.description,
            max_rounds=args.rounds,
            delay=args.delay,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
