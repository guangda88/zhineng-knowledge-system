"""
LLM 查询扩展服务

将用户短查询扩展为语义相关的多个搜索词，
解决关键词不匹配问题（如"类本质"→"类特性|人的本质|自由自觉"）。
"""

import logging
import time
from typing import List, Optional

from backend.common.llm_api_wrapper import get_llm_client

logger = logging.getLogger(__name__)

_EXPANSION_PROMPT = """你是一个中文检索查询扩展专家。用户输入一个查询词，你需要生成5-8个语义相关的搜索词（同义词、近义词、相关概念、上位/下位概念）。

规则：
1. 只输出搜索词，每行一个，不要编号不要解释
2. 包含原始查询词本身
3. 包含同义词、近义词
4. 包含相关概念词
5. 包含可能出现在原文中的不同表述方式

查询: {query}

相关搜索词:"""

_CACHE: dict[str, List[str]] = {}
_CACHE_MAX = 200

_RATE_LIMIT_COOLDOWN: float = 0.0
_RATE_LIMIT_WINDOW = 60.0


class RateLimitError(Exception):
    pass


def _is_rate_limited() -> bool:
    return time.monotonic() < _RATE_LIMIT_COOLDOWN


def _set_rate_limit_cooldown(seconds: float = 60.0) -> None:
    global _RATE_LIMIT_COOLDOWN
    _RATE_LIMIT_COOLDOWN = time.monotonic() + seconds
    logger.info(f"查询扩展: 429限流，切换到本地扩展 {seconds:.0f}s")


async def expand_query(query: str, max_terms: int = 8) -> List[str]:
    if query in _CACHE:
        return _CACHE[query][:max_terms]

    if _is_rate_limited():
        logger.debug("查询扩展: 限流冷却中，使用本地扩展")
        raise RateLimitError("DeepSeek API rate limit cooldown")

    try:
        client = get_llm_client()
        response = await client.call_api(
            messages=[
                {
                    "role": "system",
                    "content": "你是中文检索查询扩展专家。只输出搜索词列表，每行一个。",
                },
                {"role": "user", "content": _EXPANSION_PROMPT.format(query=query)},
            ],
            temperature=0.3,
            max_tokens=300,
            timeout=10,
        )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        terms = [
            line.strip()
            for line in content.strip().split("\n")
            if line.strip()
            and not line.strip().startswith(("#", "-", "*", "1", "2", "3", "4", "5"))
        ]

        terms = terms[:max_terms]

        if not terms:
            terms = [query]

        if query not in terms:
            terms.insert(0, query)

        _CACHE[query] = terms
        if len(_CACHE) > _CACHE_MAX:
            oldest = list(_CACHE.keys())[: _CACHE_MAX // 2]
            for k in oldest:
                del _CACHE[k]

        logger.info(f"查询扩展: '{query}' → {terms}")
        return terms

    except Exception as e:
        err_msg = str(e).lower()
        if any(kw in err_msg for kw in ("rate limit", "429", "速率", "too many", "quota")):
            _set_rate_limit_cooldown(60.0)
            raise RateLimitError(f"DeepSeek 429: {e}") from e
        logger.warning(f"查询扩展失败: {e}")
        return [query]


_SYNONYM_MAP: dict[str, list[str]] = {
    "类本质": ["类本质", "类特性", "人的本质", "人的本性", "自由自觉", "类存在", "类活动"],
    "气功": ["气功", "气功学", "气功科学", "练功", "修炼", "功法"],
    "混元气": ["混元气", "混元", "原始混元气", "混元整体"],
    "混元整体理论": ["混元整体理论", "混元整体观", "整体生命观", "混元气理论"],
    "意元体": ["意元体", "意识", "精神", "神明", "意识论"],
    "意识论": ["意识论", "意识哲学", "心灵哲学", "意识研究", "自我意识"],
    "道德": ["道德", "修养", "涵养道德", "德性", "道德论"],
    "组场": ["组场", "组场治病", "集体组场"],
    "超常智能": ["超常智能", "特异功能", "超常能力", "第六感"],
    "经络": ["经络", "经脉", "气脉", "经穴"],
    "三心并": ["三心并", "三心并站桩", "站桩"],
    "形神桩": ["形神桩", "形神庄", "鹤首龙头"],
    "庞明": ["庞明", "庞鹤鸣", "庞明教授", "智能气功创始人"],
    "马克思": ["马克思", "马克思主义", "马克思恩格斯", "唯物史观"],
    "人的本质": ["人的本质", "类本质", "人性", "人的本性", "人的类特性"],
    "智能气功": ["智能气功", "智能气功科学", "气功科学"],
    "整体观": ["整体观", "整体论", "整体生命观", "系统观"],
}


async def expand_query_simple(query: str) -> List[str]:
    result = [query]

    for key, synonyms in _SYNONYM_MAP.items():
        if key in query or query in key:
            result.extend(synonyms)
            break

    try:
        import jieba

        words = jieba.lcut(query)
        for w in words:
            w = w.strip()
            if len(w) > 1 and w not in result:
                for key, synonyms in _SYNONYM_MAP.items():
                    if w in key or key in w:
                        result.extend(synonyms)
                        break
    except ImportError:
        pass

    return list(dict.fromkeys(result))[:6]
