"""跨域联合检索

自进化计划 E5: 一次查询返回多领域结果
基于 concept_map 自动识别查询中的跨域概念，按领域分组返回

用法:
    from backend.services.retrieval.cross_domain import cross_domain_search
    results = await cross_domain_search(pool, "意元体与阴阳的关系", top_k_per_domain=3)
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

from backend.services.knowledge_graph.concept_map import get_related_domains, get_concept_info

logger = logging.getLogger(__name__)


async def cross_domain_search(
    pool: asyncpg.Pool,
    query: str,
    top_k_per_domain: int = 3,
    limit: int = 20,
    pool_ref: Optional[asyncpg.Pool] = None,
) -> Dict[str, Any]:
    """跨域联合检索：按领域分组返回搜索结果

    Args:
        pool: 数据库连接池
        query: 用户查询
        top_k_per_domain: 每个领域最多返回的结果数
        limit: 总结果数上限
        pool_ref: 备用连接池（向后兼容）

    Returns:
        {
            "query": str,
            "domains": {"气功": [...], "哲学": [...], ...},
            "concepts": [...],
            "total": int,
            "domain_count": int,
        }
    """
    effective_pool = pool or pool_ref
    if not effective_pool:
        return {"query": query, "domains": {}, "concepts": [], "total": 0, "domain_count": 0}

    domains = get_related_domains(query)
    concepts = get_concept_info(query)

    if not domains:
        return {
            "query": query,
            "domains": {},
            "concepts": concepts,
            "total": 0,
            "domain_count": 0,
        }

    domain_results: Dict[str, List[Dict[str, Any]]] = {}
    total = 0

    for domain in domains:
        if total >= limit:
            break

        remaining = limit - total
        per_domain = min(top_k_per_domain, remaining)

        try:
            rows = await effective_pool.fetch(
                """
                SELECT dc.id, dc.document_id, dc.content, dc.chunk_index,
                       dc.similarity,
                       d.title, d.category, d.source,
                       dc.node_id
                FROM doc_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.category = $1
                  AND dc.search_vector @@ plainto_tsquery('simple', $2)
                ORDER BY dc.similarity DESC NULLS LAST
                LIMIT $3
                """,
                domain,
                query,
                per_domain,
            )

            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "title": row["title"],
                    "category": row["category"],
                    "source": row["source"],
                    "content": row["content"][:300] if row["content"] else "",
                    "chunk_index": row["chunk_index"],
                    "similarity": float(row["similarity"]) if row["similarity"] else 0,
                    "domain": domain,
                })

            if results:
                domain_results[domain] = results
                total += len(results)

        except Exception as e:
            logger.warning(f"跨域检索失败 [{domain}]: {e}")

    return {
        "query": query,
        "domains": domain_results,
        "concepts": concepts,
        "total": total,
        "domain_count": len(domain_results),
    }
