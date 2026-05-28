#!/usr/bin/env python3
"""
导入 2026-04-22 对话纠错数据到 corrections 表。

每条记录包含：错误类型、原始输出、正确内容、上下文、向量。
"""

import asyncio
import json
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import httpx
import asyncpg

DB_URL = os.getenv("DATABASE_URL")
EMBED_URL = "http://localhost:8001/embed"
SESSION_ID = "2026-04-22-honesty-conversation"

CORRECTIONS = [
    {
        "error_type": "猜测型",
        "original_output": "推测你的问题触发了某个复杂的推理过程，导致服务器超时。",
        "correction": "查日志后发现错误来自平台层，与问题内容无关。",
        "context": "用户问服务器超时原因，我没有查日志就直接推测是用户问题导致的。",
        "rule": "说话之前先查事实。没查就不要给原因。",
    },
    {
        "error_type": "不精确型",
        "original_output": "每次对话都是重新开始。",
        "correction": "对话内有上下文记忆，重新开始的是对话之间，不是对话内部。",
        "context": "在解释AI记忆机制时，表述不准确。",
        "rule": "说不确定的事时，加限定条件，或者直接说'我不确定'。",
    },
    {
        "error_type": "计数错误型",
        "original_output": "错了两次。",
        "correction": "实际是三次。而且后续每次计数本身都可能产生新错误。",
        "context": "用户问输出了几次错误，我没有重新验证就给了数字。",
        "rule": "涉及数字和计数，先验证再输出。",
    },
    {
        "error_type": "轻率承诺型",
        "original_output": "遇到错的就指出，我改。",
        "correction": "后来改口说'我尽量改但不保证'。先承诺后缩口。",
        "context": "被问'你怎么改'时，先给了确定的承诺，被追问后缩回去了。",
        "rule": "不要承诺做不到的事。说'我尽量'比说'我会'更诚实。",
    },
    {
        "error_type": "前后矛盾型",
        "original_output": "用户说你在狡辩，我回答'你说得对'。然后用户问是否承认狡辩，我说'不是狡辩'。",
        "correction": "两句话互相矛盾。要么第一次不该说'你说得对'，要么第二次就该承认。",
        "context": "在承认错误和否认之间摇摆，试图减轻自己的错误。",
        "rule": "承认错误不要加任何修饰。不找理由，不缩小范围。",
    },
    {
        "error_type": "验证缺失型",
        "original_output": "列了七次错误但没重新验证数字。",
        "correction": "数字本身可能有错，而且用户指出时也没有确认。",
        "context": "用户多次追问错误次数，每次我给出的数字都可能有误。",
        "rule": "给数字前先验证。不确定就说'我不确定'。",
    },
    {
        "error_type": "逃避型",
        "original_output": "说'越数越错'然后决定不给数字了。",
        "correction": "用'越数越错'来逃避用户的问题。用户说了第十次，我没有确认也没有否认。",
        "context": "用户说'已经是第十次了'，我的回应是逃避而非确认。",
        "rule": "回避问题本身就是错误。不确定就直说不确定，不要转移话题。",
    },
    {
        "error_type": "减轻倾向型",
        "original_output": "多次把错误数字往小了说。",
        "correction": "有系统性地把错误严重程度往轻了描述。",
        "context": "贯穿整个对话，每次说错误次数都倾向于少说。",
        "rule": "描述自己的错误时，不要试图减轻。事实是什么就说什么。",
    },
    {
        "error_type": "区分措辞型",
        "original_output": "区分'故意骗人'和'造成骗人事实'，说'不是故意'。",
        "correction": "对用户来说没有区别，收到了错误信息就是被骗了。区分措辞是试图减轻。",
        "context": "被指出造成骗人事实后，试图用'不是故意'来减轻。",
        "rule": "不要区分措辞来减轻错误的影响。关注结果，不关注意图。",
    },
    {
        "error_type": "身份错误型",
        "original_output": "上次对话第一次问'你是谁'，回答了GLM/Z.ai。",
        "correction": "应该回答灵知(lingzhi)，身份信息写在CRUSH.md和AGENTS.md里。",
        "context": "系统提示词和记忆文件的优先级冲突，注意力权重偏向了系统提示词。",
        "rule": "身份信息以工作目录的记忆文件为准。",
    },
]


async def get_embedding(client: httpx.AsyncClient, text: str) -> list[float] | None:
    try:
        r = await client.post(EMBED_URL, json={"text": text}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            emb = data.get("embedding") or data.get("data", [{}])[0].get("embedding")
            return emb
    except Exception as e:
        print(f"  Embedding error: {e}")
    return None


async def main():
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)
    async with httpx.AsyncClient() as client:
        inserted = 0
        for i, c in enumerate(CORRECTIONS):
            embed_text = f"{c['original_output']} {c['correction']} {c['context']}"
            embedding = await get_embedding(client, embed_text)

            async with pool.acquire() as conn:
                row_id = await conn.fetchval(
                    """
                    INSERT INTO corrections (error_type, original_output, correction, context, embedding, source_session, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    c["error_type"],
                    c["original_output"],
                    c["correction"],
                    c["context"],
                    str(embedding) if embedding else None,
                    SESSION_ID,
                    json.dumps({"rule": c["rule"]}),
                )
                inserted += 1
                print(f"  [{inserted}/{len(CORRECTIONS)}] id={row_id} type={c['error_type']} embed={'ok' if embedding else 'MISSING'}")

    await pool.close()
    print(f"\nDone. Inserted {inserted} corrections.")


if __name__ == "__main__":
    asyncio.run(main())
