# -*- coding: utf-8 -*-
"""
测试数据生成器
Test Data Generator

生成用于测试和分析的示例数据，包括用户、文档、标注、搜索历史等
"""

import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system/services/web_app/backend')

import asyncio
import random
import string
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import json
import hashlib

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from database.models import (
    Base, User, Document, DocumentChunk, Annotation,
    SearchHistory, ProcessingJob
)
from common.logging_config import setup_logging

logger = setup_logging(__name__)

# =============================================================================
# 配置
# =============================================================================

DATABASE_URL = "postgresql+asyncpg://tcm_admin:tcm_secure_pass_2024@localhost:5432/tcm_kb"
OUTPUT_DIR = Path("/home/ai/zhineng-knowledge-system/analytics/data")

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

# =============================================================================
# 数据生成器类
# =============================================================================

class TestDataGenerator:
    """测试数据生成器"""

    def __init__(self, engine, output_dir: Path = OUTPUT_DIR):
        self.engine = engine
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    async def generate_users(
        self,
        count: int = 100,
        include_admins: bool = True
    ) -> List[User]:
        """生成用户数据"""
        logger.info(f"Generating {count} users...")

        users = []
        admin_count = max(1, int(count * 0.05)) if include_admins else 0

        async with self.session_factory() as session:
            for i in range(1, count + 1):
                username = f"testuser_{i}"
                email = f"{username}@test.com"
                password_hash = self._hash_password(f"Password{i}!")
                full_name = f"测试用户 {i}"
                
                is_admin = i <= admin_count
                is_active = random.random() > 0.05  # 95% 活跃

                user = User(
                    username=username,
                    email=email,
                    password_hash=password_hash,
                    full_name=full_name,
                    is_active=is_active,
                    is_admin=is_admin,
                    last_login=datetime.now() - timedelta(days=random.randint(1, 30))
                )

                session.add(user)
                users.append(user)

            await session.commit()

        logger.info(f"✅ Generated {len(users)} users")
        return users

    async def generate_documents(
        self,
        count: int = 1000,
        user_ids: List[int] = None
    ) -> List[Document]:
        """生成文档数据"""
        logger.info(f"Generating {count} documents...")

        documents = []
        if not user_ids:
            user_ids = range(1, 101)

        async with self.session_factory() as session:
            for i in range(1, count + 1):
                # 随机选择文档类型
                doc_type = random.choice([
                    "herb", "formula", "disease", "theory", "case"
                ])

                if doc_type == "herb":
                    title = f"{random.choice(TCM_HERBS)}的药理作用研究"
                    content = self._generate_herb_content()
                    file_type = "text/plain"
                    extension = ".txt"
                elif doc_type == "formula":
                    title = f"{random.choice(TCM_FORMULAS)}组方分析"
                    content = self._generate_formula_content()
                    file_type = "text/markdown"
                    extension = ".md"
                elif doc_type == "disease":
                    title = f"{random.choice(TCM_DISEASES)}的中医诊治"
                    content = self._generate_disease_content()
                    file_type = "text/plain"
                    extension = ".txt"
                elif doc_type == "theory":
                    title = f"{random.choice(TCM_THEORIES)}的理论探讨"
                    content = self._generate_theory_content()
                    file_type = "text/plain"
                    extension = ".txt"
                else:
                    title = f"临床案例{random.randint(1, 100)}分析"
                    content = self._generate_case_content()
                    file_type = "text/plain"
                    extension = ".txt"

                uploader_id = random.choice(user_ids)
                file_size = random.randint(1024, 100 * 1024)

                document = Document(
                    title=title,
                    content=content,
                    file_type=file_type,
                    extension=extension,
                    uploader_id=uploader_id,
                    file_path=f"/uploads/document_{i}{extension}",
                    file_size=file_size,
                    status="processed",
                )

                session.add(document)
                documents.append(document)

            await session.commit()

        logger.info(f"✅ Generated {len(documents)} documents")
        return documents

    async def generate_document_chunks(
        self,
        document_ids: List[int] = None
    ) -> List[DocumentChunk]:
        """生成文档块数据"""
        logger.info("Generating document chunks...")

        chunks = []
        if not document_ids:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Document.id).limit(1000)
                )
                document_ids = [row[0] for row in result]

        async with self.session_factory() as session:
            for doc_id in document_ids:
                # 获取文档内容
                doc_result = await session.execute(
                    select(Document).where(Document.id == doc_id)
                )
                document = doc_result.scalar_one()

                # 分块处理
                content = document.content
                chunk_size = random.randint(500, 2000)
                overlap = int(chunk_size * 0.1)

                for i, start in enumerate(range(0, len(content), chunk_size - overlap)):
                    chunk_content = content[start:start + chunk_size]
                    if not chunk_content:
                        continue

                    chunk = DocumentChunk(
                        document_id=doc_id,
                        chunk_index=i,
                        content=chunk_content,
                        metadata={
                            "chunk_size": len(chunk_content),
                            "overlap": overlap,
                            "position": start,
                        }
                    )

                    session.add(chunk)
                    chunks.append(chunk)

            await session.commit()

        logger.info(f"✅ Generated {len(chunks)} document chunks")
        return chunks

    async def generate_annotations(
        self,
        count: int = 5000,
        user_ids: List[int] = None,
        document_ids: List[int] = None
    ) -> List[Annotation]:
        """生成标注数据"""
        logger.info(f"Generating {count} annotations...")

        annotations = []

        if not user_ids:
            user_ids = range(1, 101)
        if not document_ids:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Document.id).limit(1000)
                )
                document_ids = [row[0] for row in result]

        async with self.session_factory() as session:
            for i in range(1, count + 1):
                doc_id = random.choice(document_ids)
                user_id = random.choice(user_ids)

                annotation_types = ["highlight", "comment", "tag", "correction"]
                annotation_type = random.choice(annotation_types)

                annotation = Annotation(
                    document_id=doc_id,
                    user_id=user_id,
                    annotation_type=annotation_type,
                    content=f"标注内容 {i}",
                    start_offset=random.randint(0, 1000),
                    end_offset=random.randint(1000, 2000),
                    metadata={
                        "created_via": "test_generator",
                        "confidence": random.random(),
                    }
                )

                session.add(annotation)
                annotations.append(annotation)

            await session.commit()

        logger.info(f"✅ Generated {len(annotations)} annotations")
        return annotations

    async def generate_search_history(
        self,
        count: int = 10000,
        user_ids: List[int] = None
    ) -> List[SearchHistory]:
        """生成搜索历史数据"""
        logger.info(f"Generating {count} search histories...")

        histories = []

        if not user_ids:
            user_ids = range(1, 101)

        search_terms = TCM_HERBS + TCM_FORMULAS + TCM_DISEASES + TCM_THEORIES

        async with self.session_factory() as session:
            for i in range(1, count + 1):
                user_id = random.choice(user_ids)
                query = random.choice(search_terms) + " " + random.choice(["功效", "用法", "禁忌", "配伍"])

                search_type = random.choice(["keyword", "semantic", "full_text", "hybrid"])
                results_count = random.randint(0, 100)
                response_time_ms = random.uniform(50, 2000)

                history = SearchHistory(
                    user_id=user_id,
                    query=query,
                    search_type=search_type,
                    results_count=results_count,
                    response_time_ms=response_time_ms,
                    created_at=datetime.now() - timedelta(days=random.randint(0, 30)),
                    metadata={
                        "filters_applied": random.random() > 0.5,
                        "sort_used": random.choice(["relevance", "date", "popularity"]),
                    }
                )

                session.add(history)
                histories.append(history)

            await session.commit()

        logger.info(f"✅ Generated {len(histories)} search histories")
        return histories

    def _hash_password(self, password: str) -> str:
        """简单的密码哈希（仅用于测试）"""
        return hashlib.sha256(password.encode()).hexdigest()

    def _generate_herb_content(self) -> str:
        """生成中药材相关内容"""
        herb = random.choice(TCM_HERBS)
        return f"""
        【中药名称】{herb}

        【性味归经】
        性味：{random.choice(["苦", "甘", "辛", "酸", "咸"])}，{random.choice(["温", "凉", "寒", "热"])}
        归经：{random.choice(["肺", "脾", "胃", "心", "肝", "肾", "大肠", "小肠"])}经

        【功效主治】
        {random.choice(["补气", "补血", "滋阴", "温阳", "清热", "解毒", "活血", "化瘀"])}，
        主治{random.choice(TCM_DISEASES)}等症。

        【用法用量】
        煎服，{random.randint(3, 30)}g。

        【使用注意】
        {random.choice(["孕妇慎用", "忌食辛辣", "不宜久服", "实热证禁用"])}。

        【现代药理】
        {random.choice(["增强免疫", "抗炎", "抗肿瘤", "降血糖", "降血脂"])}等作用。
        """

    def _generate_formula_content(self) -> str:
        """生成方剂相关内容"""
        formula = random.choice(TCM_FORMULAS)
        return f"""
        # {formula}

        ## 组成
        {random.sample(TCM_HERBS, random.randint(3, 10))}

        ## 功效
        {random.choice(["补气", "补血", "调和阴阳", "疏肝解郁", "健脾益气"])}。

        ## 主治
        {random.choice(TCM_DISEASES)}。

        ## 用法
        水煎服，{random.choice(["日一剂", "分早晚服", "顿服"])}。

        ## 方解
        本方{random.choice(["君臣佐使配伍严谨", "药味精简", "标本兼治"])}。

        ## 临床应用
        {random.choice(["广泛应用于临床", "治疗{random.choice(TCM_DISEASES)}效果显著"])}。
        """

    def _generate_disease_content(self) -> str:
        """生成疾病相关内容"""
        disease = random.choice(TCM_DISEASES)
        return f"""
        【中医病名】{disease}

        【病因病机】
        多因{random.choice(["外感六淫", "内伤七情", "饮食不节", "劳逸过度"])}所致，
        病位在{random.choice(["肺", "脾", "胃", "肝", "肾", "心"])}，
        病性{random.choice(["寒", "热", "虚", "实"])}。

        【辨证论治】
        1. {random.choice(["风寒型", "风热型", "气虚型", "血瘀型"])}：
           治法：{random.choice(["疏风散寒", "疏风清热", "补气固表", "活血化瘀"])}
           方药：{random.choice(TCM_FORMULAS)}

        【预防调护】
        {random.choice(["注意保暖", "饮食清淡", "调节情志", "适度运动"])}。
        """

    def _generate_theory_content(self) -> str:
        """生成理论相关内容"""
        theory = random.choice(TCM_THEORIES)
        return f"""
        【理论名称】{theory}

        【基本概念】
        {theory}是中医基础理论的重要组成部分，
        体现了{random.choice(["整体观念", "辨证论治", "治未病"])}的思想。

        【主要内容】
        1. {random.choice(["阴阳平衡", "五行生克", "脏腑功能", "气血津液"])}
        2. {random.choice(["经络循行", "病因分类", "病机演变", "防治原则"])}

        【临床应用】
        在临床实践中，{theory}用于
        {random.choice(["指导诊断", "确立治则", "选方用药", "养生保健"])}。
        """

    def _generate_case_content(self) -> str:
        """生成病例相关内容"""
        return f"""
        【病例记录】

        【患者信息】
        性别：{random.choice(["男", "女"])}
        年龄：{random.randint(10, 80)}岁

        【主诉】
        {random.choice(TCM_DISEASES)}{random.randint(1, 10)}天。

        【现病史】
        {random.choice(["受凉后", "劳累后", "情志不遂"])}发病，
        {random.choice(["伴有", "不伴有"])}{random.choice(["发热", "恶寒", "汗出", "纳差"])}。

        【舌脉】
        舌质：{random.choice(["淡红", "淡白", "红", "紫暗"])}
        舌苔：{random.choice(["薄白", "薄黄", "厚腻", "少苔"])}
        脉象：{random.choice(["浮", "沉", "迟", "数", "细", "弦"])}

        【中医诊断】
        辨证：{random.choice(["风寒束表", "风热犯肺", "脾胃虚弱", "肝郁脾虚"])}
        治法：{random.choice(["疏风解表", "清热宣肺", "健脾益气", "疏肝健脾"])}

        【方药】
        {random.choice(TCM_FORMULAS)}加减

        【治疗经过】
        {random.choice(["服药3剂后痊愈", "服药7剂后好转", "效果不显著，调整方药"])}。
        """

    async def export_statistics(self) -> Dict[str, Any]:
        """导出统计信息"""
        logger.info("Exporting statistics...")

        async with self.session_factory() as session:
            stats = {}

            # 用户统计
            user_result = await session.execute(
                select(func.count(User.id))
            )
            stats["total_users"] = user_result.scalar()
            stats["active_users"] = await session.scalar(
                select(func.count(User.id)).where(User.is_active == True)
            )
            stats["admin_users"] = await session.scalar(
                select(func.count(User.id)).where(User.is_admin == True)
            )

            # 文档统计
            doc_result = await session.execute(
                select(func.count(Document.id))
            )
            stats["total_documents"] = doc_result.scalar()

            # 文档块统计
            chunk_result = await session.execute(
                select(func.count(DocumentChunk.id))
            )
            stats["total_chunks"] = chunk_result.scalar()

            # 标注统计
            annotation_result = await session.execute(
                select(func.count(Annotation.id))
            )
            stats["total_annotations"] = annotation_result.scalar()

            # 搜索历史统计
            history_result = await session.execute(
                select(func.count(SearchHistory.id))
            )
            stats["total_searches"] = history_result.scalar()

            # 平均响应时间
            avg_response = await session.execute(
                select(func.avg(SearchHistory.response_time_ms))
            )
            stats["avg_response_time_ms"] = avg_response.scalar() or 0

        # 保存统计信息
        stats_file = self.output_dir / "statistics.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"✅ Statistics exported to {stats_file}")
        return stats


# =============================================================================
# 主函数
# =============================================================================

async def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("Starting Test Data Generation")
    logger.info("=" * 50)

    # 创建数据库引擎
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20
    )

    # 创建数据生成器
    generator = TestDataGenerator(engine)

    try:
        # 生成用户
        users = await generator.generate_users(count=100)

        # 生成文档
        documents = await generator.generate_documents(count=1000)

        # 生成文档块
        chunks = await generator.generate_document_chunks()

        # 生成标注
        annotations = await generator.generate_annotations(count=5000)

        # 生成搜索历史
        histories = await generator.generate_search_history(count=10000)

        # 导出统计信息
        stats = await generator.export_statistics()

        logger.info("=" * 50)
        logger.info("Test Data Generation Complete")
        logger.info(f"Users: {stats['total_users']}")
        logger.info(f"Documents: {stats['total_documents']}")
        logger.info(f"Chunks: {stats['total_chunks']}")
        logger.info(f"Annotations: {stats['total_annotations']}")
        logger.info(f"Searches: {stats['total_searches']}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Error generating test data: {e}", exc_info=True)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
