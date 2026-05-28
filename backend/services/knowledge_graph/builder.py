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
ENTITY_TYPE_MERIDIAN = "经络"
ENTITY_TYPE_ACTION = "动作"
ENTITY_TYPE_SYMPTOM = "病症"
ENTITY_TYPE_HERB = "药材"
ENTITY_TYPE_FORMULA = "方剂"
ENTITY_TYPE_THEORY = "理论"
ENTITY_TYPE_ORG = "组织"


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
        "丹田",
        "调身",
        "调息",
        "调心",
        "运用意识",
        "内求法",
        "三传并用",
        "仁",
        "义",
        "礼",
        "智",
        "信",
        "孝",
        "道",
        "无为",
        "禅",
        "定",
        "慧",
        "觉悟",
        "中庸",
        "天人合一",
        "精气神",
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
        "心包",
        "小肠",
        "大肠",
    ],
    ENTITY_TYPE_CLASSIC: [
        "黄帝内经",
        "伤寒论",
        "金匮要略",
        "本草纲目",
        "难经",
        "温病条辨",
        "神农本草经",
        "千金方",
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
        "心经",
        "金刚经",
        "坛经",
        "楞严经",
        "法华经",
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
        "禅宗",
        "净土宗",
        "天台宗",
        "华严宗",
    ],
    ENTITY_TYPE_PERSON: [
        "庞明",
        "庞鹤鸣",
        "冯广德",
        "樊志诚",
        "黄帝",
        "岐伯",
        "张仲景",
        "华佗",
        "孙思邈",
        "李时珍",
        "孔子",
        "孟子",
        "荀子",
        "朱熹",
        "王阳明",
        "老子",
        "庄子",
        "列子",
        "释迦牟尼",
        "达摩",
        "慧能",
        "玄奘",
        "张三丰",
    ],
    ENTITY_TYPE_POINT: [
        "百会",
        "膻中",
        "气海",
        "关元",
        "命门",
        "涌泉",
        "足三里",
        "合谷",
        "太冲",
        "内关",
        "神阙",
        "中脘",
        "天枢",
        "大椎",
        "风池",
        "太溪",
        "三阴交",
        "血海",
        "曲池",
        "肩井",
        "肾俞",
        "肝俞",
        "脾俞",
        "肺俞",
        "心俞",
        "印堂",
        "太阳",
        "劳宫",
    ],
    ENTITY_TYPE_MERIDIAN: [
        "手太阴肺经",
        "手阳明大肠经",
        "足阳明胃经",
        "足太阴脾经",
        "手少阴心经",
        "手太阳小肠经",
        "足太阳膀胱经",
        "足少阴肾经",
        "手厥阴心包经",
        "手少阳三焦经",
        "足少阳胆经",
        "足厥阴肝经",
        "任脉",
        "督脉",
        "冲脉",
        "带脉",
    ],
    ENTITY_TYPE_ACTION: [
        "站桩",
        "打坐",
        "吐纳",
        "导引",
        "行气",
        "采气",
        "发气",
        "拉气",
        "组场",
        "收功",
        "调身",
        "调息",
        "调心",
    ],
    ENTITY_TYPE_SYMPTOM: [
        "头痛",
        "眩晕",
        "失眠",
        "心悸",
        "咳嗽",
        "哮喘",
        "胃痛",
        "腹痛",
        "便秘",
        "腹泻",
        "水肿",
        "痹症",
        "中风",
        "消渴",
    ],
    ENTITY_TYPE_HERB: [
        "人参",
        "黄芪",
        "当归",
        "白术",
        "茯苓",
        "甘草",
        "川芎",
        "白芍",
        "熟地黄",
        "桂枝",
        "麻黄",
        "柴胡",
        "黄芩",
        "半夏",
        "陈皮",
        "丹参",
    ],
    ENTITY_TYPE_FORMULA: [
        "四君子汤",
        "四物汤",
        "八珍汤",
        "六味地黄丸",
        "逍遥散",
        "桂枝汤",
        "麻黄汤",
        "小柴胡汤",
        "大柴胡汤",
        "补中益气汤",
        "归脾汤",
    ],
    ENTITY_TYPE_THEORY: [
        "混元整体理论",
        "阴阳五行学说",
        "藏象学说",
        "经络学说",
        "气血津液学说",
        "病因学说",
        "辨证论治",
        "天人相应",
        "形神合一",
        "理法方药",
    ],
    ENTITY_TYPE_ORG: [
        "石家庄智能气功进修学院",
        "华夏智能气功培训中心",
        "智能气功研究会",
        "中国中医药研究院",
        "北京中医药大学",
    ],
}

# 关系类型
RELATION_CONTAINS = "包含"
RELATION_RELATED = "相关"
RELATION_BELONGS_TO = "属于"
RELATION_REFERENCES = "引用"
RELATION_EVOLVED_FROM = "演变自"
RELATION_CORRESPONDS = "对应"
RELATION_FOUNDED = "创立"
RELATION_AUTHORED = "著述"
RELATION_TEACHES = "师承"
RELATION_TREATS = "治疗"
RELATION_ENTERS = "归经"
RELATION_LOCATED_ON = "位于"


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
        types = {type_a, type_b}

        # --- 人物关系 ---
        # 人物 ↔ 人物: 师承
        if type_a == ENTITY_TYPE_PERSON and type_b == ENTITY_TYPE_PERSON:
            return RELATION_TEACHES

        # 人物 ↔ 功法: 创立
        if types == {ENTITY_TYPE_PERSON, ENTITY_TYPE_GONGFA}:
            return RELATION_FOUNDED

        # 人物 ↔ 典籍: 著述
        if types == {ENTITY_TYPE_PERSON, ENTITY_TYPE_CLASSIC}:
            return RELATION_AUTHORED

        # 人物 ↔ 流派: 属于/创立
        if types == {ENTITY_TYPE_PERSON, ENTITY_TYPE_SCHOOL}:
            return RELATION_FOUNDED

        # 人物 ↔ 理论: 创立
        if types == {ENTITY_TYPE_PERSON, ENTITY_TYPE_THEORY}:
            return RELATION_FOUNDED

        # 人物 ↔ 组织: 属于
        if types == {ENTITY_TYPE_PERSON, ENTITY_TYPE_ORG}:
            return RELATION_BELONGS_TO

        # --- 功法关系 ---
        # 功法 ↔ 概念
        if types == {ENTITY_TYPE_GONGFA, ENTITY_TYPE_CONCEPT}:
            return RELATION_RELATED

        # 功法 ↔ 功法
        if type_a == ENTITY_TYPE_GONGFA and type_b == ENTITY_TYPE_GONGFA:
            return RELATION_RELATED

        # 功法 ↔ 流派
        if types == {ENTITY_TYPE_GONGFA, ENTITY_TYPE_SCHOOL}:
            return RELATION_BELONGS_TO

        # 功法 ↔ 动作: 包含
        if types == {ENTITY_TYPE_GONGFA, ENTITY_TYPE_ACTION}:
            return RELATION_CONTAINS

        # --- 概念关系 ---
        # 概念 ↔ 概念
        if type_a == ENTITY_TYPE_CONCEPT and type_b == ENTITY_TYPE_CONCEPT:
            return RELATION_RELATED

        # --- 典籍关系 ---
        # 典籍 ↔ 流派
        if types == {ENTITY_TYPE_CLASSIC, ENTITY_TYPE_SCHOOL}:
            return RELATION_BELONGS_TO

        # 典籍 ↔ 理论: 引用
        if types == {ENTITY_TYPE_CLASSIC, ENTITY_TYPE_THEORY}:
            return RELATION_REFERENCES

        # --- 脏腑关系 ---
        # 脏腑 ↔ 概念
        if types == {ENTITY_TYPE_ORGAN, ENTITY_TYPE_CONCEPT}:
            return RELATION_CORRESPONDS

        # 脏腑 ↔ 经络: 对应
        if types == {ENTITY_TYPE_ORGAN, ENTITY_TYPE_MERIDIAN}:
            return RELATION_CORRESPONDS

        # 脏腑 ↔ 病症: 对应
        if types == {ENTITY_TYPE_ORGAN, ENTITY_TYPE_SYMPTOM}:
            return RELATION_CORRESPONDS

        # --- 经络关系 ---
        # 经络 ↔ 穴位: 包含
        if types == {ENTITY_TYPE_MERIDIAN, ENTITY_TYPE_POINT}:
            return RELATION_CONTAINS

        # --- 穴位关系 ---
        # 穴位 ↔ 病症: 治疗
        if types == {ENTITY_TYPE_POINT, ENTITY_TYPE_SYMPTOM}:
            return RELATION_TREATS

        # --- 药材关系 ---
        # 药材 ↔ 经络: 归经
        if types == {ENTITY_TYPE_HERB, ENTITY_TYPE_MERIDIAN}:
            return RELATION_ENTERS

        # 药材 ↔ 脏腑: 归经
        if types == {ENTITY_TYPE_HERB, ENTITY_TYPE_ORGAN}:
            return RELATION_ENTERS

        # 药材 ↔ 病症: 治疗
        if types == {ENTITY_TYPE_HERB, ENTITY_TYPE_SYMPTOM}:
            return RELATION_TREATS

        # --- 方剂关系 ---
        # 方剂 ↔ 药材: 包含
        if types == {ENTITY_TYPE_FORMULA, ENTITY_TYPE_HERB}:
            return RELATION_CONTAINS

        # 方剂 ↔ 病症: 治疗
        if types == {ENTITY_TYPE_FORMULA, ENTITY_TYPE_SYMPTOM}:
            return RELATION_TREATS

        # 方剂 ↔ 经络: 归经
        if types == {ENTITY_TYPE_FORMULA, ENTITY_TYPE_MERIDIAN}:
            return RELATION_ENTERS

        # --- 理论关系 ---
        # 理论 ↔ 概念: 包含
        if types == {ENTITY_TYPE_THEORY, ENTITY_TYPE_CONCEPT}:
            return RELATION_CONTAINS

        # 理论 ↔ 流派: 属于
        if types == {ENTITY_TYPE_THEORY, ENTITY_TYPE_SCHOOL}:
            return RELATION_BELONGS_TO

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
            ("武术", "智能气功", "功法体系", ["站桩", "吐纳", "太极拳"]),
            ("武术", "中医", "经络/穴位", ["经络", "穴位", "气血", "脏腑"]),
            ("哲学", "儒家", "思想渊源", ["仁", "义", "礼", "中庸", "天人合一"]),
            ("哲学", "道家", "思想渊源", ["道", "无为", "阴阳"]),
            ("哲学", "佛家", "思想渊源", ["禅", "定", "慧", "觉悟"]),
            ("心理学", "智能气功", "意识/调心", ["调心", "运用意识", "意元体"]),
            ("心理学", "哲学", "意识研究", ["意识", "认知", "心理"]),
            ("科学", "智能气功", "现代研究", ["混元气", "意元体", "气场"]),
            ("佛家", "古籍", "经典传承", ["心经", "金刚经", "坛经"]),
            ("中医", "哲学", "身体哲学", ["阴阳", "五行", "天人合一"]),
            ("智能气功", "道家", "修炼体系", ["丹田", "精气神", "混元气"]),
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
