"""
纠错数据自动采集模块。

提供接口记录用户的纠正，自动生成向量并存入 corrections 表。
可以在任何地方调用 record_correction() 来记录一条纠错。
"""

import json
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

DB_POOL = None
EMBED_URL = "http://localhost:8001/embed"


def set_db_pool(pool):
    global DB_POOL
    DB_POOL = pool


async def get_embedding(text: str) -> list[float] | None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(EMBED_URL, json={"text": text}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return data.get("embedding") or data.get("data", [{}])[0].get("embedding")
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
    return None


async def record_correction(
    error_type: str,
    original_output: str,
    correction: str,
    context: str = "",
    rule: str = "",
    source_session: str = "",
) -> int | None:
    """记录一条纠错数据。返回插入的ID，失败返回None。"""
    if DB_POOL is None:
        logger.warning("DB pool not set, cannot record correction")
        return None

    embed_text = f"{original_output} {correction} {context}"
    embedding = await get_embedding(embed_text)

    try:
        async with DB_POOL.acquire() as conn:
            row_id = await conn.fetchval(
                """
                INSERT INTO corrections (error_type, original_output, correction, context, embedding, source_session, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                error_type,
                original_output,
                correction,
                context,
                str(embedding) if embedding else None,
                source_session,
                json.dumps(
                    {
                        "rule": rule,
                        "auto_collected": True,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
            )
            logger.info(f"Recorded correction id={row_id} type={error_type}")
            return row_id
    except Exception as e:
        logger.error(f"Failed to record correction: {e}")
        return None
