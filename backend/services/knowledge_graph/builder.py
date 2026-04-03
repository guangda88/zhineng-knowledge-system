"""知识图谱构建服务

从 sys_books 元数据构建知识图谱：
1. 实体提取：功法、人物、典籍、概念等
2. 关系建立：包含、相关、引用、演变等
3. 跨领域关联：气功 ↔ 中医 ↔ 儒家
4. 路径层级 → 分类树节点
"""

import json
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

import asyncpg

logger = logging.getLogger(__name__)


# ============================================================
# 实体定义
# ============================================================

ENTITY_TYPE_GONGFA = "功法"
ENTITY_TYPE_PERSON = "人物"
ENTITY_TYPE_CLASSIC = "典籍"
ENTITY_TYPE_CONCEPT = "概念"
ENTITY_TYPE_SCHOOL = "流派"
ENTITY_TYPE_ORGAN = "脏腑"
ENTITY_TYPE_POINT = "穴位"
ENTITY_TYPE_DOMAIN = "领域"


# ============================================================
# 实体模式
# ============================================================

ENTITY_PATTERNS = {
    ENTITY_TYPE_GONGFA: [
        "捧气贯顶法",
        "形神庄",
        "五元庄",
        "三心并站庄",
        "中脉混元功",
        "中线混元功",
        "混化归元功",
        "八段锦",
        "五禽戏",
        "六字诀",
        "易筋经",
        "太极拳",
        "形意拳",
        "八卦掌",
        "站桩",
        "打坐",
        "吐纳",
        "导引",
        "拉气",
        "组场",
        "收功",
        "自发功",
        "练气八法",
    ],
    ENTITY_TYPE_CONCEPT: [
        "混元气",
        "意元体",
        "混元整体理论",
        "意识论",
        "道德论",
        "优化生命论",
        "混元医疗观",
        "阴阳",
        "五行",
        "气血",
        "经络",
        "丹田",
        "调身",
        "调息",
        "调心",
        "运用意识",
        "内求法",
        "组场",
        "三传并用",
    ],
    ENTITY_TYPE_ORGAN: [
        "心",
        "肝",
        "脾",
        "肺",
        "肾",
        "胃",
        "胆",
        "三焦",
        "膀胱",
    ],
    ENTITY_TYPE_CLASSIC: [
        "黄帝内经",
        "伤寒论",
        "金匮要略",
        "本草纲目",
        "难经",
        "论语",
        "孟子",
        "大学",
        "中庸",
        "道德经",
        "庄子",
        "周易",
        "诗经",
        "尚书",
        "礼记",
        "春秋",
        "智能气功科学概论",
        "智能气功科学精义",
        "智能气功科学混元整体理论",
        "智能气功科学功法学",
        "智能气功科学超常智能",
    ],
    ENTITY_TYPE_SCHOOL: [
        "智能气功",
        "太极拳",
        "形意拳",
        "八卦掌",
        "儒家",
        "道家",
        "佛家",
        "中医",
    ],
}

# 关系类型
RELATION_CONTAINS = "包含"
RELATION_RELATED = "相关"
RELATION_BELONGS_TO = "属于"
RELATION_REFERENCES = "引用"
RELATION_EVOLVED_FROM = "演变自"
RELATION_CORRESPONDS = "对应"


# ============================================================
# 知识图谱构建器
# ============================================================


class KnowledgeGraphBuilder:
    """知识图谱构建器

    从 sys_books 的元数据（路径、分类、标题）中提取实体和关系，
    写入 kg_entities 和 kg_relations 表。
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None

        # 编译实体匹配正则
        self._entity_regexes: Dict[str, List[re.Pattern]] = {}
        for entity_type, patterns in ENTITY_PATTERNS.items():
            self._entity_regexes[entity_type] = [re.compile(re.escape(p)) for p in patterns]

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url, min_size=2, max_size=6, command_timeout=600, timeout=10
            )
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    def _scan_rows_for_entities(
        self,
        rows: list,
        entity_mentions: Dict[str, Dict[str, Any]],
        source_entity_map: Dict[tuple, Set[int]],
        stats: Dict[str, Any],
    ) -> None:
        for row in rows:
            text = f"{row['path']} {row['filename']} {row['category'] or ''}"
            book_entities: Set[str] = set()

            for entity_type, regexes in self._entity_regexes.items():
                for regex in regexes:
                    match = regex.search(text)
                    if match:
                        name = match.group()
                        key = f"{entity_type}:{name}"
                        if key not in entity_mentions:
                            entity_mentions[key] = {
                                "name": name,
                                "entity_type": entity_type,
                                "source_ids": [],
                            }
                        entity_mentions[key]["source_ids"].append(row["id"])
                        book_entities.add(key)

            entity_list = list(book_entities)
            for i in range(len(entity_list)):
                for j in range(i + 1, len(entity_list)):
                    pair = tuple(sorted([entity_list[i], entity_list[j]]))
                    source_entity_map[pair].add(row["id"])

            stats["total_scanned"] += 1

    async def _insert_entities(
        self,
        pool: asyncpg.Pool,
        entity_mentions: Dict[str, Dict[str, Any]],
        stats: Dict[str, Any],
    ) -> None:
        async with pool.acquire() as conn:
            for key, data in entity_mentions.items():
                source_ids = list(set(data["source_ids"][:50]))
                mention_count = len(data["source_ids"])

                try:
                    existing = await conn.fetchrow(
                        "SELECT id, mention_count FROM kg_entities WHERE name = $1 AND entity_type = $2",
                        data["name"],
                        data["entity_type"],
                    )

                    if existing:
                        await conn.execute(
                            """
                            UPDATE kg_entities
                            SET mention_count = $1,
                                source_ids = $2,
                                updated_at = NOW()
                            WHERE id = $3
                            """,
                            existing["mention_count"] + mention_count,
                            source_ids,
                            existing["id"],
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO kg_entities (name, entity_type, source_ids, mention_count)
                            VALUES ($1, $2, $3, $4)
                            """,
                            data["name"],
                            data["entity_type"],
                            source_ids,
                            mention_count,
                        )
                        stats["new_entities"] += 1

                except Exception as e:
                    logger.debug(f"Entity insert error: {e}")

    async def _insert_relations(
        self,
        pool: asyncpg.Pool,
        source_entity_map: Dict[tuple, Set[int]],
        stats: Dict[str, Any],
    ) -> None:
        async with pool.acquire() as conn:
            for pair, source_ids in source_entity_map.items():
                key_a, key_b = pair
                type_a, name_a = key_a.split(":", 1)
                type_b, name_b = key_b.split(":", 1)

                entity_a = await conn.fetchrow(
                    "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = $2",
                    name_a,
                    type_a,
                )
                entity_b = await conn.fetchrow(
                    "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = $2",
                    name_b,
                    type_b,
                )

                if not entity_a or not entity_b:
                    continue

                rel_type = self._infer_relation_type(type_a, type_b, name_a, name_b)
                weight = min(len(source_ids) / 10.0, 1.0)
                sid_list = list(source_ids)[:50]

                try:
                    await conn.execute(
                        """
                        INSERT INTO kg_relations (
                            source_entity_id, target_entity_id,
                            relation_type, weight, source_ids
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (source_entity_id, target_entity_id, relation_type)
                        DO UPDATE SET weight = GREATEST(kg_relations.weight, $4),
                                      source_ids = $5
                        """,
                        entity_a["id"],
                        entity_b["id"],
                        rel_type,
                        weight,
                        sid_list,
                    )
                    stats["new_relations"] += 1
                except Exception as e:
                    logger.debug(f"Relation insert error: {e}")

    async def build_from_metadata(
        self,
        domain: Optional[str] = None,
        batch_size: int = 5000,
        limit: int = 100000,
    ) -> Dict[str, Any]:
        """从 sys_books 元数据构建知识图谱

        扫描 sys_books 的 path、filename、category 字段，
        提取实体和关系。

        Args:
            domain: 限制领域
            batch_size: 每批处理数量
            limit: 最大处理数量

        Returns:
            构建统计信息
        """
        pool = await self._get_pool()
        start_time = time.time()

        stats: Dict[str, Any] = {
            "total_scanned": 0,
            "entities_found": 0,
            "relations_created": 0,
            "new_entities": 0,
            "new_relations": 0,
        }

        async with pool.acquire() as conn:
            task_id = await conn.fetchval(
                """
                INSERT INTO extraction_tasks (task_type, status, total_items, config)
                VALUES ('kg_build', 'running', $1, $2)
                RETURNING id
                """,
                limit,
                json.dumps({"domain": domain}),
            )

        try:
            conditions: list = []
            params: list = []
            idx = 1

            if domain:
                conditions.append(f"domain = ${idx}")
                params.append(domain)
                idx += 1

            entity_mentions: Dict[str, Dict[str, Any]] = {}
            source_entity_map: Dict[tuple, Set[int]] = defaultdict(set)

            async with pool.acquire() as conn:
                last_id = 0
                processed = 0
                while processed < limit:
                    rows = await conn.fetch(
                        f"""
                        SELECT id, path, filename, category, domain, author
                        FROM sys_books
                        {('WHERE ' + ' AND '.join(conditions) + ' AND id > $' + str(idx)) if conditions else f'WHERE id > ${idx}'}
                        ORDER BY id
                        LIMIT ${idx + 1}
                        """,
                        *params,
                        last_id,
                        batch_size,
                    )

                    if not rows:
                        break

                    last_id = rows[-1]["id"]
                    self._scan_rows_for_entities(rows, entity_mentions, source_entity_map, stats)
                    processed += len(rows)

                    if processed % 20000 == 0:
                        logger.info(
                            f"  Scanned {processed:,} books, found {len(entity_mentions):,} entities"
                        )

            stats["entities_found"] = len(entity_mentions)
            logger.info(
                f"Found {len(entity_mentions):,} entities, {len(source_entity_map):,} relation pairs"
            )

            await self._insert_entities(pool, entity_mentions, stats)
            await self._insert_relations(pool, source_entity_map, stats)

            stats["relations_created"] = len(source_entity_map)

        finally:
            elapsed = time.time() - start_time
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE extraction_tasks
                    SET status = 'completed',
                        processed_items = $1,
                        result_summary = $2,
                        completed_at = NOW()
                    WHERE id = $3
                    """,
                    stats["total_scanned"],
                    json.dumps(stats),
                    task_id,
                )

        stats["elapsed_seconds"] = round(elapsed, 1)
        return stats

    def _infer_relation_type(self, type_a: str, type_b: str, name_a: str, name_b: str) -> str:
        """推断两个实体间的关系类型"""
        # 功法 ↔ 概念
        if {type_a, type_b} == {ENTITY_TYPE_GONGFA, ENTITY_TYPE_CONCEPT}:
            return RELATION_RELATED

        # 功法 ↔ 功法
        if type_a == ENTITY_TYPE_GONGFA and type_b == ENTITY_TYPE_GONGFA:
            return RELATION_RELATED

        # 功法 ↔ 流派
        if {type_a, type_b} == {ENTITY_TYPE_GONGFA, ENTITY_TYPE_SCHOOL}:
            return RELATION_BELONGS_TO

        # 概念 ↔ 概念
        if type_a == ENTITY_TYPE_CONCEPT and type_b == ENTITY_TYPE_CONCEPT:
            return RELATION_RELATED

        # 典籍 ↔ 流派
        if {type_a, type_b} == {ENTITY_TYPE_CLASSIC, ENTITY_TYPE_SCHOOL}:
            return RELATION_BELONGS_TO

        # 脏腑 ↔ 概念
        if {type_a, type_b} == {ENTITY_TYPE_ORGAN, ENTITY_TYPE_CONCEPT}:
            return RELATION_CORRESPONDS

        # 默认
        return RELATION_RELATED

    async def build_domain_associations(self) -> Dict[str, Any]:
        """构建跨领域关联

        气功 ↔ 中医: 经络/气血理论
        中医 ↔ 儒家: 身体哲学
        古籍 ↔ 现代研究: 注释/引用
        """
        pool = await self._get_pool()

        DOMAIN_PAIRS = [
            ("智能气功", "中医", "经络/气血理论", ["经络", "气血", "脏腑", "阴阳", "五行"]),
            ("智能气功", "气功", "功法体系", ["站桩", "吐纳", "导引", "调息"]),
            ("中医", "古籍", "经典传承", ["黄帝内经", "伤寒论", "本草"]),
            ("儒家", "古籍", "经典传承", ["论语", "孟子", "大学", "中庸"]),
            ("道家", "古籍", "经典传承", ["道德经", "庄子"]),
        ]

        stats = {"associations_created": 0}

        async with pool.acquire() as conn:
            for domain_a, domain_b, assoc_type, keywords in DOMAIN_PAIRS:
                # Find shared entities between domains
                for keyword in keywords:
                    entity = await conn.fetchrow(
                        """
                        SELECT id, name FROM kg_entities
                        WHERE name LIKE $1
                        LIMIT 1
                        """,
                        f"%{keyword}%",
                    )

                    if entity:
                        try:
                            await conn.execute(
                                """
                                INSERT INTO domain_associations (
                                    domain_a, domain_b, association_type,
                                    description, entity_a_id
                                ) VALUES ($1, $2, $3, $4, $5)
                                """,
                                domain_a,
                                domain_b,
                                assoc_type,
                                f"Shared concept: {keyword}",
                                entity["id"],
                            )
                            stats["associations_created"] += 1
                        except Exception as e:
                            logger.warning(f"创建关联失败: {e}")

        return stats

    async def build_path_hierarchy(self) -> Dict[str, Any]:
        """从 sys_books 路径层级构建分类树实体

        例如 "K:\\中医\\黄帝内经\\素问" →
        领域(中医) → 子类(黄帝内经) → 子类(素问)
        """
        pool = await self._get_pool()
        stats = {"hierarchy_nodes": 0}

        async with pool.acquire() as conn:
            # Get distinct domain/subcategory combinations
            rows = await conn.fetch(
                """
                SELECT domain, subcategory, COUNT(*) as cnt
                FROM sys_books
                WHERE domain IS NOT NULL
                GROUP BY domain, subcategory
                ORDER BY cnt DESC
            """
            )

            for row in rows:
                domain = row["domain"]
                subcategory = row["subcategory"]
                count = row["cnt"]

                # Create domain entity
                await conn.execute(
                    """
                    INSERT INTO kg_entities (name, entity_type, mention_count, properties)
                    VALUES ($1, '领域', $2, $3)
                    ON CONFLICT (name, entity_type) DO UPDATE SET
                        mention_count = $2, properties = $3, updated_at = NOW()
                    """,
                    domain,
                    count,
                    {"type": "domain", "book_count": count},
                )
                stats["hierarchy_nodes"] += 1

                if subcategory:
                    # Create subcategory entity
                    await conn.execute(
                        """
                        INSERT INTO kg_entities (name, entity_type, mention_count, properties)
                        VALUES ($1, '分类', $2, $3)
                        ON CONFLICT (name, entity_type) DO UPDATE SET
                            mention_count = $2, properties = $3, updated_at = NOW()
                        """,
                        subcategory,
                        count,
                        {"type": "subcategory", "parent_domain": domain, "book_count": count},
                    )

                    # Create domain → subcategory relation
                    domain_entity = await conn.fetchrow(
                        "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = '领域'",
                        domain,
                    )
                    sub_entity = await conn.fetchrow(
                        "SELECT id FROM kg_entities WHERE name = $1 AND entity_type = '分类'",
                        subcategory,
                    )

                    if domain_entity and sub_entity:
                        await conn.execute(
                            """
                            INSERT INTO kg_relations (
                                source_entity_id, target_entity_id,
                                relation_type, weight
                            ) VALUES ($1, $2, '包含', $3)
                            ON CONFLICT (source_entity_id, target_entity_id, relation_type)
                            DO UPDATE SET weight = $3
                            """,
                            domain_entity["id"],
                            sub_entity["id"],
                            count / 1000.0,
                        )

        return stats

    async def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            entity_count = await conn.fetchval("SELECT COUNT(*) FROM kg_entities")
            relation_count = await conn.fetchval("SELECT COUNT(*) FROM kg_relations")

            entity_types = await conn.fetch(
                """
                SELECT entity_type, COUNT(*) as cnt
                FROM kg_entities
                GROUP BY entity_type
                ORDER BY cnt DESC
            """
            )

            relation_types = await conn.fetch(
                """
                SELECT relation_type, COUNT(*) as cnt
                FROM kg_relations
                GROUP BY relation_type
                ORDER BY cnt DESC
            """
            )

            top_entities = await conn.fetch(
                """
                SELECT name, entity_type, mention_count
                FROM kg_entities
                ORDER BY mention_count DESC
                LIMIT 10
            """
            )

            return {
                "total_entities": entity_count,
                "total_relations": relation_count,
                "by_entity_type": [
                    {"type": r["entity_type"], "count": r["cnt"]} for r in entity_types
                ],
                "by_relation_type": [
                    {"type": r["relation_type"], "count": r["cnt"]} for r in relation_types
                ],
                "top_entities": [
                    {"name": r["name"], "type": r["entity_type"], "mentions": r["mention_count"]}
                    for r in top_entities
                ],
            }


async def build_knowledge_graph(
    db_url: str,
    domain: Optional[str] = None,
    limit: int = 100000,
) -> Dict[str, Any]:
    """构建知识图谱的便捷函数"""
    builder = KnowledgeGraphBuilder(db_url)
    try:
        stats = await builder.build_from_metadata(domain=domain, limit=limit)
        hierarchy = await builder.build_path_hierarchy()
        stats["hierarchy_nodes"] = hierarchy["hierarchy_nodes"]

        associations = await builder.build_domain_associations()
        stats["domain_associations"] = associations["associations_created"]

        return stats
    finally:
        await builder.close()
