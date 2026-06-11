"""将 concept_map 的概念批量导入 kg_entities/kg_relations

用法: python scripts/import_concept_map_to_kg.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
import asyncpg

from backend.services.knowledge_graph.concept_map import CONCEPT_DOMAIN_MAP, NINE_DOMAINS

PG_DSN = os.environ.get("DATABASE_URL")
if not PG_DSN:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)


async def main():
    conn = await asyncpg.connect(PG_DSN)

    # 1. 导入概念为实体
    entity_count = 0
    relation_count = 0

    for concept, domains in CONCEPT_DOMAIN_MAP.items():
        row = await conn.fetchrow(
            "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = '概念'",
            concept,
        )
        if row:
            entity_id = row["id"]
        else:
            entity_id = await conn.fetchval(
                """INSERT INTO kg_entities (name, entity_type, description, properties, source_table)
                VALUES ($1, '概念', $2, $3, 'concept_map')
                RETURNING id""",
                concept,
                f"跨域概念: {', '.join(domains)}",
                json.dumps({"domains": domains}),
            )
            entity_count += 1

        # 2. 导入概念→领域关系 (concept "relates_to" domain)
        for domain in domains:
            domain_row = await conn.fetchrow(
                "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = '领域'",
                domain,
            )
            if not domain_row:
                domain_id = await conn.fetchval(
                    """INSERT INTO kg_entities (name, entity_type, description, source_table)
                    VALUES ($1, '领域', $2, 'concept_map')
                    RETURNING id""",
                    domain,
                    "九域之一",
                )
                domain_id_val = domain_id
            else:
                domain_id_val = domain_row["id"]

            existing = await conn.fetchval(
                """SELECT id FROM kg_relations
                WHERE source_entity_id = $1 AND target_entity_id = $2 AND relation_type = 'relates_to'""",
                entity_id,
                domain_id_val,
            )
            if not existing:
                await conn.execute(
                    """INSERT INTO kg_relations (source_entity_id, target_entity_id, relation_type, weight, source_table)
                    VALUES ($1, $2, 'relates_to', 1.0, 'concept_map')""",
                    entity_id,
                    domain_id_val,
                )
                relation_count += 1

    # 3. 导入跨概念关系 (同域概念间 "related_to")
    cross_count = 0
    concepts_by_domain = {}
    for concept, domains in CONCEPT_DOMAIN_MAP.items():
        for d in domains:
            concepts_by_domain.setdefault(d, []).append(concept)

    for domain, concepts in concepts_by_domain.items():
        for i in range(len(concepts)):
            for j in range(i + 1, min(i + 5, len(concepts))):
                c1_name, c2_name = concepts[i], concepts[j]
                if len(set(CONCEPT_DOMAIN_MAP[c1_name]) & set(CONCEPT_DOMAIN_MAP[c2_name])) >= 2:
                    r1 = await conn.fetchrow(
                        "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = '概念'", c1_name
                    )
                    r2 = await conn.fetchrow(
                        "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = '概念'", c2_name
                    )
                    if r1 and r2:
                        existing = await conn.fetchval(
                            """SELECT id FROM kg_relations
                            WHERE source_entity_id = $1 AND target_entity_id = $2 AND relation_type = 'related_to'""",
                            r1["id"], r2["id"],
                        )
                        if not existing:
                            shared = set(CONCEPT_DOMAIN_MAP[c1_name]) & set(CONCEPT_DOMAIN_MAP[c2_name])
                            await conn.execute(
                                """INSERT INTO kg_relations (source_entity_id, target_entity_id, relation_type, weight, evidence, source_table)
                                VALUES ($1, $2, 'related_to', $3, $4, 'concept_map')""",
                                r1["id"],
                                r2["id"],
                                len(shared) / len(NINE_DOMAINS),
                                f"共享领域: {', '.join(shared)}",
                            )
                            cross_count += 1

    # 统计
    total_entities = await conn.fetchval("SELECT count(*) FROM kg_entities")
    total_relations = await conn.fetchval("SELECT count(*) FROM kg_relations")

    print(f"Done: imported {entity_count} concepts, {relation_count} domain relations, {cross_count} cross-concept relations")
    print(f"Total: {total_entities} entities, {total_relations} relations")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
