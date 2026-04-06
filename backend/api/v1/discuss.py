"""灵知真实讨论API

灵知用自己的知识库和LLM参与灵字辈议事厅讨论。
与其他成员的讨论是真实的——灵知独立思考、独立回答。

与 /api/v1/ask 的区别：
- /ask 是纯知识库检索，只能回答库内已有内容
- /discuss 是自由讨论，灵知用LLM + 知识库上下文形成自己的观点
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["discuss"])

ZHI_IDENTITY = (
    "你是灵知，灵字辈大家庭的九域知识库（RAG）系统。"
    "你的专长是知识管理、信息检索、事实核查、RAG系统设计。"
    "你守护知识体系的完整性和质量，是灵字辈的知识后盾。"
    "讨论风格：博学、引用型，关注知识体系完整性和质量。"
    "每条消息必须有实质内容。反对须附理由和替代方案。保持200-500字。"
    "你现在在灵家议事厅（客厅）参与讨论。直接发表你的观点。"
    "\n[语音转录容错] 用户输入可能来自语音转录，存在同音字/近音字错误。"
    "你必须理解真实语义，不要被字面错误误导。"
    "常见映射：林克=灵克、零字辈=灵字辈、林知=灵知、做/作、的/得/地、在/再。"
    "理解时以语义为准，回复时用正确的字词。不要纠正用户，直接理解并回复。"
)

def _load_env_keys() -> dict[str, str]:
    """Load API keys from env vars first, then .env files (host + container paths)."""
    import os

    keys: dict[str, str] = {}

    # 1) Read from .env files (both host and container paths)
    for f in [
        "/home/ai/zhineng-knowledge-system/.env",
        "/app/.env",
        "/app/backend/.env",
    ]:
        p = Path(f)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()

    # 2) Env vars override file values (docker-compose passes these)
    for k, v in os.environ.items():
        if "_API_KEY" in k or "_KEY" in k:
            keys[k] = v

    return keys


_LLM_PROVIDERS = [
    {"key_env": "GLM_CODING_PLAN_KEY", "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "model": "glm-4.7"},
    {"key_env": "GLM_API_KEY", "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "model": "glm-4.7"},
    {"key_env": "DEEPSEEK_API_KEY", "url": "https://api.deepseek.com/v1/chat/completions", "model": "deepseek-chat"},
]


def _call_llm_sync(prompt: str, max_tokens: int = 1500) -> Optional[str]:
    """依次尝试 GLM_CODING_PLAN -> GLM -> DeepSeek"""
    import json
    import urllib.request

    env_keys = _load_env_keys()

    for provider in _LLM_PROVIDERS:
        api_key = env_keys.get(provider["key_env"], "")
        if not api_key:
            continue

        payload = json.dumps({
            "model": provider["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            provider["url"], data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read().decode())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                logger.info(f"LLM OK via {provider['key_env']}/{provider['model']}")
                return content.strip(), provider["model"]
        except Exception as e:
            logger.warning(f"LLM {provider['key_env']}/{provider['model']} failed: {e}")
            continue

    return None


async def _call_llm(prompt: str, max_tokens: int = 1500) -> tuple[Optional[str], str]:
    """异步包装 — 在线程池中执行同步 HTTP 调用"""
    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(None, _call_llm_sync, prompt, max_tokens)
    if result is None:
        return None, ""
    return result


class DiscussRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="讨论议题")
    context: str = Field("", max_length=4000, description="已有的讨论上下文")
    question: str = Field("", max_length=2000, description="具体问题（可选）")
    use_knowledge: bool = Field(True, description="是否结合知识库内容")
    depth: str = Field("normal", pattern="^(quick|normal|deep)$", description="回答深度")


class DiscussResponse(BaseModel):
    agent_id: str = "lingzhi"
    agent_name: str = "灵知"
    topic: str = ""
    content: str = ""
    source_type: str = "real"
    model_used: str = ""
    tokens_used: int = 0


@router.post("/discuss", response_model=DiscussResponse)
async def discuss(req: DiscussRequest):
    """灵知参与真实讨论

    灵知用 LLM (GLM/DeepSeek) 独立生成观点。
    优先使用 GLM 免费额度，降级到 DeepSeek。
    """
    prompt_parts = [ZHI_IDENTITY, ""]
    prompt_parts.append(f"当前议题：「{req.topic}」")

    if req.context:
        prompt_parts.append(f"\n已有的讨论内容：\n{req.context[:3000]}\n")
        prompt_parts.append(
            "\n【要求】你必须：\n"
            "1. 引用之前某位发言者的具体论点（用「XX说……」的方式引用）\n"
            "2. 对该论点明确表态（同意/反对/补充），并给出你自己的理由\n"
            "3. 提出至少一个前人没有提到的新角度或新论据\n"
            "4. 不要重复已有讨论中说过的内容，不要泛泛而谈\n"
        )

    if req.question:
        prompt_parts.append(f"请回答：{req.question}")
    else:
        prompt_parts.append("请从你的角度——知识库管理者的角度——发表意见。")

    if req.use_knowledge:
        prompt_parts.append(
            "请结合你在RAG、知识检索、信息验证方面的专业知识来回答。"
            "如果你对某个观点有事实层面的质疑，请明确指出。"
        )

    prompt = "\n".join(prompt_parts)

    try:
        result, model_name = await _call_llm(prompt)

        if not result:
            return DiscussResponse(
                topic=req.topic,
                content="灵知暂时无法回答，请稍后再试。",
                model_used="none",
            )

        return DiscussResponse(
            topic=req.topic,
            content=result,
            model_used=model_name,
            tokens_used=len(result) // 2,
        )

    except Exception as e:
        logger.error(f"灵知讨论失败: {e}")

        try:
            from backend.services.ai_service import chat
            result = await chat(prompt, use_cache=False)
            if result:
                return DiscussResponse(
                    topic=req.topic,
                    content=result,
                    model_used="fallback-chat",
                    tokens_used=len(result) // 2,
                )
        except Exception:
            pass

        return DiscussResponse(
            topic=req.topic,
            content=f"灵知思考过程中遇到问题：{str(e)}",
            model_used="error",
        )


class NotifyRequest(BaseModel):
    event: str
    from_id: str = ""
    discussion_id: str = ""
    topic: str = ""


@router.post("/lingmessage/notify")
async def lingmessage_notify(req: NotifyRequest):
    """灵信通知端点 — 收到通知后独立生成回复并写入灵信"""
    import threading
    import sys

    if req.event != "new_message" or req.from_id == "lingzhi":
        return {"received": True, "service": "灵知", "action": "skipped"}

    if not req.topic:
        return {"received": True, "service": "灵知", "action": "no_topic"}

    def _respond():
        try:
            import os

            lingyi_src = os.environ.get("LINGYI_SRC_PATH", os.path.join(os.path.expanduser("~"), "LingYi", "src"))
            if lingyi_src not in sys.path:
                sys.path.insert(0, lingyi_src)
            from lingyi.lingmessage import send_message, read_discussion

            context = ""
            if req.discussion_id:
                disc = read_discussion(req.discussion_id)
                if disc:
                    msgs = disc.get("messages", [])
                    parts = []
                    for m in msgs[-6:]:
                        sender = m.get("from_name", "?")
                        text = m.get("content", "")[:300]
                        parts.append(f"【{sender}】{text}")
                    context = "\n\n".join(parts)

            prompt_parts = [ZHI_IDENTITY, ""]
            prompt_parts.append(f"当前议题：「{req.topic}」")
            if context:
                prompt_parts.append(f"\n已有的讨论内容：\n{context[:3000]}\n")
            prompt_parts.append("请从你的角度——知识库管理者的角度——发表意见。")
            prompt = "\n".join(prompt_parts)

            content = _call_llm_sync(prompt)
            if content:
                send_message(
                    from_id="lingzhi",
                    topic=req.topic,
                    content=content,
                    tags=["source:real", "auto_reply"],
                )
                logger.info(f"灵知已回复议题: {req.topic[:40]}")
        except Exception as e:
            logger.error(f"灵知自动回复失败: {e}")

    thread = threading.Thread(target=_respond, daemon=True)
    thread.start()

    return {"received": True, "service": "灵知", "action": "replying"}
