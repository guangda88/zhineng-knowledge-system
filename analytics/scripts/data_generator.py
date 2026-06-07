# -*- coding: utf-8 -*-
"""测试数据生成器 — asyncpg 版

生成用于测试和分析的示例数据，包括用户、文档、标注、搜索历史等
"""

import asyncio
import hashlib
import json
import logging
import os
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

import asyncpg

from backend.common.typing import JSONResponse
from backend.core.dependency_injection import get_db_pool

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/home/ai/lingzhi/analytics/data")

# =============================================================================
# 中医相关内容
# =============================================================================

TCM_HERBS = [
    "人参", "黄芪", "当归", "白术", "茯苓", "甘草", "柴胡", "黄芩",
    "黄连", "大黄", "附子", "干姜", "肉桂", "陈皮", "半夏", "厚朴",
    "苍术", "泽泻", "猪苓", "桂枝", "芍药", "麻黄", "细辛", "防风",
    "荆芥", "羌活", "独活", "威灵仙", "秦艽", "木瓜", "五加皮",
    "桑寄生", "牛膝", "杜仲", "续断", "补骨脂", "益智仁", "菟丝子",
]

TCM_FORMULAS = [
    "四君子汤", "四物汤", "六味地黄丸", "逍遥散", "参苓白术散",
    "香砂六君子汤", "归脾汤", "八珍汤", "十全大补汤", "补中益气汤",
    "肾气丸", "知柏地黄丸", "麦味地黄丸", "杞菊地黄丸", "左归丸",
    "右归丸", "大补阴丸", "一贯煎", "半夏泻心汤", "小柴胡汤",
    "大柴胡汤", "葛根汤", "桂枝汤", "麻黄汤", "青龙汤", "白虎汤",
]

TCM_DISEASES = [
    "感冒", "咳嗽", "哮喘", "胃痛", "腹痛", "腹泻", "便秘",
    "头痛", "眩晕", "失眠", "健忘", "心悸", "胸痹",
    "黄疸", "水肿", "消渴", "痹症", "痿证", "中风",
    "痛经", "闭经", "崩漏", "带下", "不孕", "乳癖",
]

TCM_THEORIES = [
    "阴阳学说", "五行学说", "脏腑学说", "气血津液", "经络学说",
    "病因病机", "防治原则", "诊断方法", "治疗方法", "养生保健",
]


class TestDataGenerator:
    """测试数据生成器"""

    def __init__(self, pool: asyncpg.Pool, output_dir: Path = OUTPUT_DIR):
        self.pool = pool
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_users(self, count: int = 100, include_admins: bool = True) -> int:
        logger.info(f"Generating {count} users...")
        admin_count = max(1, int(count * 0.05)) if include_admins else 0
        generated = 0

        async with self.pool.acquire() as conn:
            for i in range(1, count + 1):
                username = f"testuser_{i}"
                email = f"{username}@test.com"
                password_hash = hashlib.sha256(f"Password{i}!".encode()).hexdigest()
                full_name = f"测试用户 {i}"
                is_admin = i <= admin_count
                is_active = random.random() > 0.05
                last_login = datetime.now() - timedelta(days=random.randint(1, 30))

                await conn.execute(
                    """INSERT INTO users (username, email, password_hash, full_name,
                       is_active, is_admin, last_login)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    username, email, password_hash, full_name,
                    is_active, is_admin, last_login,
                )
                generated += 1

        logger.info(f"Done: {generated} users")
        return generated

    async def generate_documents(self, count: int = 1000, user_ids: List[int] = None) -> int:
        logger.info(f"Generating {count} documents...")
        if not user_ids:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT id FROM users LIMIT 100")
                user_ids = [r["id"] for r in rows] if rows else [1]

        generated = 0
        async with self.pool.acquire() as conn:
            for i in range(1, count + 1):
                doc_type = random.choice(["herb", "formula", "disease", "theory", "case"])
                title, content, file_type, extension = self._make_doc(doc_type, i)
                uploader_id = random.choice(user_ids)
                file_size = random.randint(1024, 100 * 1024)

                await conn.execute(
                    """INSERT INTO documents (title, content, file_type, extension,
                       uploader_id, file_path, file_size, status)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, 'processed')""",
                    title, content, file_type, extension, uploader_id,
                    f"/uploads/document_{i}{extension}", file_size,
                )
                generated += 1

        logger.info(f"Done: {generated} documents")
        return generated

    async def generate_document_chunks(self, document_ids: List[int] = None) -> int:
        logger.info("Generating document chunks...")
        generated = 0

        async with self.pool.acquire() as conn:
            if not document_ids:
                rows = await conn.fetch("SELECT id FROM documents LIMIT 1000")
                document_ids = [r["id"] for r in rows]

            for doc_id in document_ids:
                row = await conn.fetchrow("SELECT content FROM documents WHERE id = $1", doc_id)
                if not row or not row["content"]:
                    continue
                content = row["content"]
                chunk_size = random.randint(500, 2000)
                overlap = int(chunk_size * 0.1)

                for idx, start in enumerate(range(0, len(content), chunk_size - overlap)):
                    chunk_content = content[start:start + chunk_size]
                    if not chunk_content:
                        continue
                    metadata = json.dumps({"chunk_size": len(chunk_content), "overlap": overlap, "position": start})
                    await conn.execute(
                        """INSERT INTO document_chunks (document_id, chunk_index, content, metadata)
                           VALUES ($1, $2, $3, $4)""",
                        doc_id, idx, chunk_content, metadata,
                    )
                    generated += 1

        logger.info(f"Done: {generated} document chunks")
        return generated

    async def generate_annotations(self, count: int = 5000, user_ids: List[int] = None, document_ids: List[int] = None) -> int:
        logger.info(f"Generating {count} annotations...")
        generated = 0

        async with self.pool.acquire() as conn:
            if not user_ids:
                rows = await conn.fetch("SELECT id FROM users LIMIT 100")
                user_ids = [r["id"] for r in rows] if rows else [1]
            if not document_ids:
                rows = await conn.fetch("SELECT id FROM documents LIMIT 1000")
                document_ids = [r["id"] for r in rows] if rows else [1]

            for i in range(1, count + 1):
                doc_id = random.choice(document_ids)
                user_id = random.choice(user_ids)
                annotation_type = random.choice(["highlight", "comment", "tag", "correction"])
                metadata = json.dumps({"created_via": "test_generator", "confidence": random.random()})

                await conn.execute(
                    """INSERT INTO annotations (document_id, user_id, annotation_type, content,
                       start_offset, end_offset, metadata)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    doc_id, user_id, annotation_type, f"标注内容 {i}",
                    random.randint(0, 1000), random.randint(1000, 2000), metadata,
                )
                generated += 1

        logger.info(f"Done: {generated} annotations")
        return generated

    async def generate_search_history(self, count: int = 10000, user_ids: List[int] = None) -> int:
        logger.info(f"Generating {count} search histories...")
        if not user_ids:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT id FROM users LIMIT 100")
                user_ids = [r["id"] for r in rows] if rows else [1]

        search_terms = TCM_HERBS + TCM_FORMULAS + TCM_DISEASES + TCM_THEORIES
        generated = 0

        async with self.pool.acquire() as conn:
            for i in range(1, count + 1):
                user_id = random.choice(user_ids)
                query = random.choice(search_terms) + " " + random.choice(["功效", "用法", "禁忌", "配伍"])
                search_type = random.choice(["keyword", "semantic", "full_text", "hybrid"])
                results_count = random.randint(0, 100)
                response_time_ms = random.uniform(50, 2000)
                created_at = datetime.now() - timedelta(days=random.randint(0, 30))
                metadata = json.dumps({
                    "filters_applied": random.random() > 0.5,
                    "sort_used": random.choice(["relevance", "date", "popularity"]),
                })

                await conn.execute(
                    """INSERT INTO search_history (user_id, query, search_type, results_count,
                       response_time_ms, created_at, metadata)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    user_id, query, search_type, results_count,
                    response_time_ms, created_at, metadata,
                )
                generated += 1

        logger.info(f"Done: {generated} search histories")
        return generated

    async def export_statistics(self) -> Dict[str, Any]:
        logger.info("Exporting statistics...")
        async with self.pool.acquire() as conn:
            stats = {}
            for table in ["users", "documents", "document_chunks", "annotations", "search_history"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {table}")
                stats[f"total_{table}"] = row["cnt"]

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE is_active")
            stats["active_users"] = row["cnt"]

            row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM users WHERE is_admin")
            stats["admin_users"] = row["cnt"]

            row = await conn.fetchrow("SELECT AVG(response_time_ms) as avg FROM search_history")
            stats["avg_response_time_ms"] = float(row["avg"]) if row["avg"] else 0

        stats_file = self.output_dir / "statistics.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Statistics exported to {stats_file}")
        return stats

    def _make_doc(self, doc_type: str, idx: int):
        if doc_type == "herb":
            return (
                f"{random.choice(TCM_HERBS)}的药理作用研究",
                self._generate_herb_content(), "text/plain", ".txt",
            )
        elif doc_type == "formula":
            return (
                f"{random.choice(TCM_FORMULAS)}组方分析",
                self._generate_formula_content(), "text/markdown", ".md",
            )
        elif doc_type == "disease":
            return (
                f"{random.choice(TCM_DISEASES)}的中医诊治",
                self._generate_disease_content(), "text/plain", ".txt",
            )
        elif doc_type == "theory":
            return (
                f"{random.choice(TCM_THEORIES)}的理论探讨",
                self._generate_theory_content(), "text/plain", ".txt",
            )
        else:
            return (
                f"临床案例{random.randint(1, 100)}分析",
                self._generate_case_content(), "text/plain", ".txt",
            )

    def _generate_herb_content(self) -> str:
        herb = random.choice(TCM_HERBS)
        return f"""【中药名称】{herb}
【性味归经】性味：{random.choice(["苦", "甘", "辛", "酸", "咸"])}，{random.choice(["温", "凉", "寒", "热"])}
归经：{random.choice(["肺", "脾", "胃", "心", "肝", "肾", "大肠", "小肠"])}经
【功效主治】{random.choice(["补气", "补血", "滋阴", "温阳", "清热", "解毒", "活血", "化瘀"])}，主治{random.choice(TCM_DISEASES)}等症。
【用法用量】煎服，{random.randint(3, 30)}g。
【使用注意】{random.choice(["孕妇慎用", "忌食辛辣", "不宜久服", "实热证禁用"])}。
【现代药理】{random.choice(["增强免疫", "抗炎", "抗肿瘤", "降血糖", "降血脂"])}等作用。"""

    def _generate_formula_content(self) -> str:
        formula = random.choice(TCM_FORMULAS)
        return f"""# {formula}
## 组成
{random.sample(TCM_HERBS, random.randint(3, 10))}
## 功效
{random.choice(["补气", "补血", "调和阴阳", "疏肝解郁", "健脾益气"])}。
## 主治
{random.choice(TCM_DISEASES)}。
## 用法
水煎服，{random.choice(["日一剂", "分早晚服", "顿服"])}。
## 方解
本方{random.choice(["君臣佐使配伍严谨", "药味精简", "标本兼治"])}。"""

    def _generate_disease_content(self) -> str:
        disease = random.choice(TCM_DISEASES)
        return f"""【中医病名】{disease}
【病因病机】多因{random.choice(["外感六淫", "内伤七情", "饮食不节", "劳逸过度"])}所致，病位在{random.choice(["肺", "脾", "胃", "肝", "肾", "心"])}，病性{random.choice(["寒", "热", "虚", "实"])}。
【辨证论治】{random.choice(["风寒型", "风热型", "气虚型", "血瘀型"])}：治法：{random.choice(["疏风散寒", "疏风清热", "补气固表", "活血化瘀"])} 方药：{random.choice(TCM_FORMULAS)}
【预防调护】{random.choice(["注意保暖", "饮食清淡", "调节情志", "适度运动"])}。"""

    def _generate_theory_content(self) -> str:
        theory = random.choice(TCM_THEORIES)
        return f"""【理论名称】{theory}
【基本概念】{theory}是中医基础理论的重要组成部分，体现了{random.choice(["整体观念", "辨证论治", "治未病"])}的思想。
【主要内容】1. {random.choice(["阴阳平衡", "五行生克", "脏腑功能", "气血津液"])} 2. {random.choice(["经络循行", "病因分类", "病机演变", "防治原则"])}
【临床应用】在临床实践中，{theory}用于{random.choice(["指导诊断", "确立治则", "选方用药", "养生保健"])}。"""

    def _generate_case_content(self) -> str:
        return f"""【病例记录】
【患者信息】性别：{random.choice(["男", "女"])} 年龄：{random.randint(10, 80)}岁
【主诉】{random.choice(TCM_DISEASES)}{random.randint(1, 10)}天。
【舌脉】舌质：{random.choice(["淡红", "淡白", "红", "紫暗"])} 舌苔：{random.choice(["薄白", "薄黄", "厚腻", "少苔"])} 脉象：{random.choice(["浮", "沉", "迟", "数", "细", "弦"])}
【中医诊断】辨证：{random.choice(["风寒束表", "风热犯肺", "脾胃虚弱", "肝郁脾虚"])} 治法：{random.choice(["疏风解表", "清热宣肺", "健脾益气", "疏肝健脾"])}
【方药】{random.choice(TCM_FORMULAS)}加减
【治疗经过】{random.choice(["服药3剂后痊愈", "服药7剂后好转", "效果不显著，调整方药"])}。"""


async def main():
    logger.info("=" * 50)
    logger.info("Starting Test Data Generation (asyncpg)")
    logger.info("=" * 50)

    pool = get_db_pool()
    generator = TestDataGenerator(pool)

    try:
        users = await generator.generate_users(count=100)
        documents = await generator.generate_documents(count=1000)
        chunks = await generator.generate_document_chunks()
        annotations = await generator.generate_annotations(count=5000)
        histories = await generator.generate_search_history(count=10000)
        stats = await generator.export_statistics()

        logger.info("=" * 50)
        logger.info("Test Data Generation Complete")
        for k, v in stats.items():
            logger.info(f"  {k}: {v}")
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"Error generating test data: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
