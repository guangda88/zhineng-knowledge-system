# -*- coding: utf-8 -*-
"""
数据验证工具
Data Validator

验证数据质量，包括完整性、准确性、一致性、有效性、唯一性等
"""

import sys
sys.path.insert(0, '/home/ai/zhineng-knowledge-system/services/web_app/backend')

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import json
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import selectinload

from database.models import (
    User, Document, DocumentChunk, Annotation,
    SearchHistory, ProcessingJob
)
from common.logging_config import setup_logging

logger = setup_logging(__name__)

# =============================================================================
# 数据质量指标
# =============================================================================

class DataQualityMetric:
    """数据质量指标"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.pass_count = 0
        self.fail_count = 0
        self.total_count = 0
        self.issues = []

    def add_pass(self, count: int = 1):
        """添加通过记录"""
        self.pass_count += count
        self.total_count += count

    def add_fail(self, issue: str):
        """添加失败记录"""
        self.fail_count += 1
        self.total_count += 1
        self.issues.append(issue)

    def get_score(self) -> float:
        """获取得分（0-100）"""
        if self.total_count == 0:
            return 100.0
        return (self.pass_count / self.total_count) * 100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "score": self.get_score(),
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "total_count": self.total_count,
            "sample_issues": self.issues[:10],
            "total_issues": len(self.issues),
        }

# =============================================================================
# 数据验证器类
# =============================================================================

class DataValidator:
    """数据验证器"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.metrics = {}

    async def validate_all(self) -> Dict[str, Any]:
        """验证所有数据"""
        logger.info("=" * 50)
        logger.info("Starting Data Validation")
        logger.info("=" * 50)

        results = {}

        # 验证用户数据
        results["users"] = await self._validate_users()

        # 验证文档数据
        results["documents"] = await self._validate_documents()

        # 验证文档块数据
        results["document_chunks"] = await self._validate_document_chunks()

        # 验证标注数据
        results["annotations"] = await self._validate_annotations()

        # 验证搜索历史数据
        results["search_history"] = await self._validate_search_history()

        # 验证处理任务数据
        results["processing_jobs"] = await self._validate_processing_jobs()

        # 验证数据一致性
        results["consistency"] = await self._validate_consistency()

        # 计算总体得分
        results["overall_score"] = self._calculate_overall_score(results)

        logger.info("=" * 50)
        logger.info(f"Overall Data Quality Score: {results['overall_score']:.2f}%")
        logger.info("=" * 50)

        return results

    async def _validate_users(self) -> Dict[str, Any]:
        """验证用户数据"""
        logger.info("Validating users...")

        metric = DataQualityMetric(
            "用户数据质量",
            "验证用户数据的完整性和准确性"
        )

        # 1. 完整性：必填字段
        required_fields = ["username", "email", "password_hash"]
        for field in required_fields:
            result = await self.session.execute(
                select(func.count(User.id)).where(
                    getattr(User, field).is_(None)
                )
            )
            null_count = result.scalar()
            if null_count > 0:
                metric.add_fail(f"用户{field}字段为空的数量: {null_count}")
            else:
                metric.add_pass()

        # 2. 唯一性：用户名和邮箱
        for field in ["username", "email"]:
            result = await self.session.execute(
                select(User.id, field)
                .group_by(field)
                .having(func.count(User.id) > 1)
            )
            duplicates = result.fetchall()
            if duplicates:
                metric.add_fail(f"用户{field}存在重复: {len(duplicates)}个")
            else:
                metric.add_pass()

        # 3. 有效性：邮箱格式
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        result = await self.session.execute(
            select(User.email)
        )
        emails = [row[0] for row in result]
        for email in emails:
            if not re.match(email_pattern, email):
                metric.add_fail(f"无效邮箱格式: {email}")
                break
        else:
            metric.add_pass()

        # 4. 有效性：用户名长度
        result = await self.session.execute(
            select(func.count(User.id)).where(
                func.length(User.username) < 3
            )
        )
        short_username_count = result.scalar()
        if short_username_count > 0:
            metric.add_fail(f"用户名长度不足3字符: {short_username_count}个")
        else:
            metric.add_pass()

        # 5. 一致性：密码哈希不为空
        result = await self.session.execute(
            select(func.count(User.id)).where(
                func.length(User.password_hash) == 0
            )
        )
        empty_password_count = result.scalar()
        if empty_password_count > 0:
            metric.add_fail(f"密码哈希为空: {empty_password_count}个")
        else:
            metric.add_pass()

        self.metrics["users"] = metric
        return metric.to_dict()

    async def _validate_documents(self) -> Dict[str, Any]:
        """验证文档数据"""
        logger.info("Validating documents...")

        metric = DataQualityMetric(
            "文档数据质量",
            "验证文档数据的完整性和有效性"
        )

        # 1. 完整性：必填字段
        required_fields = ["title", "content", "uploader_id"]
        for field in required_fields:
            result = await self.session.execute(
                select(func.count(Document.id)).where(
                    getattr(Document, field).is_(None)
                )
            )
            null_count = result.scalar()
            if null_count > 0:
                metric.add_fail(f"文档{field}字段为空: {null_count}个")
            else:
                metric.add_pass()

        # 2. 有效性：标题长度
        result = await self.session.execute(
            select(func.count(Document.id)).where(
                func.length(Document.title) == 0
            )
        )
        empty_title_count = result.scalar()
        if empty_title_count > 0:
            metric.add_fail(f"文档标题为空: {empty_title_count}个")
        else:
            metric.add_pass()

        # 3. 有效性：内容长度
        result = await self.session.execute(
            select(func.count(Document.id)).where(
                func.length(Document.content) < 10
            )
        )
        short_content_count = result.scalar()
        if short_content_count > 0:
            metric.add_fail(f"文档内容过短: {short_content_count}个")
        else:
            metric.add_pass()

        # 4. 一致性：文件扩展名
        valid_extensions = [".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"]
        result = await self.session.execute(
            select(func.count(Document.id)).where(
                ~Document.extension.in_(valid_extensions)
            )
        )
        invalid_ext_count = result.scalar()
        if invalid_ext_count > 0:
            metric.add_fail(f"无效文件扩展名: {invalid_ext_count}个")
        else:
            metric.add_pass()

        # 5. 一致性：文件大小
        result = await self.session.execute(
            select(func.count(Document.id)).where(
                or_(
                    Document.file_size < 0,
                    Document.file_size > 50 * 1024 * 1024  # 50MB
                )
            )
        )
        invalid_size_count = result.scalar()
        if invalid_size_count > 0:
            metric.add_fail(f"无效文件大小: {invalid_size_count}个")
        else:
            metric.add_pass()

        self.metrics["documents"] = metric
        return metric.to_dict()

    async def _validate_document_chunks(self) -> Dict[str, Any]:
        """验证文档块数据"""
        logger.info("Validating document chunks...")

        metric = DataQualityMetric(
            "文档块数据质量",
            "验证文档块数据的完整性和一致性"
        )

        # 1. 完整性：必填字段
        required_fields = ["document_id", "content", "chunk_index"]
        for field in required_fields:
            result = await self.session.execute(
                select(func.count(DocumentChunk.id)).where(
                    getattr(DocumentChunk, field).is_(None)
                )
            )
            null_count = result.scalar()
            if null_count > 0:
                metric.add_fail(f"文档块{field}字段为空: {null_count}个")
            else:
                metric.add_pass()

        # 2. 一致性：块大小
        result = await self.session.execute(
            select(func.count(DocumentChunk.id)).where(
                or_(
                    func.length(DocumentChunk.content) < 100,
                    func.length(DocumentChunk.content) > 10000
                )
            )
        )
        invalid_size_count = result.scalar()
        if invalid_size_count > 0:
            metric.add_fail(f"文档块大小异常: {invalid_size_count}个")
        else:
            metric.add_pass()

        # 3. 一致性：关联文档存在
        result = await self.session.execute(
            select(func.count(DocumentChunk.id)).where(
                ~DocumentChunk.document_id.in_(
                    select(Document.id)
                )
            )
        )
        orphan_count = result.scalar()
        if orphan_count > 0:
            metric.add_fail(f"孤立的文档块: {orphan_count}个")
        else:
            metric.add_pass()

        self.metrics["document_chunks"] = metric
        return metric.to_dict()

    async def _validate_annotations(self) -> Dict[str, Any]:
        """验证标注数据"""
        logger.info("Validating annotations...")

        metric = DataQualityMetric(
            "标注数据质量",
            "验证标注数据的完整性和有效性"
        )

        # 1. 完整性：必填字段
        required_fields = ["document_id", "user_id", "content"]
        for field in required_fields:
            result = await self.session.execute(
                select(func.count(Annotation.id)).where(
                    getattr(Annotation, field).is_(None)
                )
            )
            null_count = result.scalar()
            if null_count > 0:
                metric.add_fail(f"标注{field}字段为空: {null_count}个")
            else:
                metric.add_pass()

        # 2. 有效性：偏移量
        result = await self.session.execute(
            select(func.count(Annotation.id)).where(
                Annotation.end_offset < Annotation.start_offset
            )
        )
        invalid_offset_count = result.scalar()
        if invalid_offset_count > 0:
            metric.add_fail(f"无效偏移量: {invalid_offset_count}个")
        else:
            metric.add_pass()

        # 3. 一致性：关联文档和用户存在
        for field, table in [("document_id", Document), ("user_id", User)]:
            result = await self.session.execute(
                select(func.count(Annotation.id)).where(
                    ~getattr(Annotation, field).in_(
                        select(table.id)
                    )
                )
            )
            orphan_count = result.scalar()
            if orphan_count > 0:
                metric.add_fail(f"孤立标注（{field}）: {orphan_count}个")
            else:
                metric.add_pass()

        self.metrics["annotations"] = metric
        return metric.to_dict()

    async def _validate_search_history(self) -> Dict[str, Any]:
        """验证搜索历史数据"""
        logger.info("Validating search history...")

        metric = DataQualityMetric(
            "搜索历史数据质量",
            "验证搜索历史数据的完整性和有效性"
        )

        # 1. 完整性：必填字段
        required_fields = ["user_id", "query", "search_type"]
        for field in required_fields:
            result = await self.session.execute(
                select(func.count(SearchHistory.id)).where(
                    getattr(SearchHistory, field).is_(None)
                )
            )
            null_count = result.scalar()
            if null_count > 0:
                metric.add_fail(f"搜索历史{field}字段为空: {null_count}个")
            else:
                metric.add_pass()

        # 2. 有效性：查询不为空
        result = await self.session.execute(
            select(func.count(SearchHistory.id)).where(
                func.length(SearchHistory.query) == 0
            )
        )
        empty_query_count = result.scalar()
        if empty_query_count > 0:
            metric.add_fail(f"空查询: {empty_query_count}个")
        else:
            metric.add_pass()

        # 3. 有效性：响应时间
        result = await self.session.execute(
            select(func.count(SearchHistory.id)).where(
                SearchHistory.response_time_ms < 0
            )
        )
        invalid_time_count = result.scalar()
        if invalid_time_count > 0:
            metric.add_fail(f"无效响应时间: {invalid_time_count}个")
        else:
            metric.add_pass()

        # 4. 一致性：关联用户存在
        result = await self.session.execute(
            select(func.count(SearchHistory.id)).where(
                ~SearchHistory.user_id.in_(
                    select(User.id)
                )
            )
        )
        orphan_count = result.scalar()
        if orphan_count > 0:
            metric.add_fail(f"孤立搜索历史: {orphan_count}个")
        else:
            metric.add_pass()

        self.metrics["search_history"] = metric
        return metric.to_dict()

    async def _validate_processing_jobs(self) -> Dict[str, Any]:
        """验证处理任务数据"""
        logger.info("Validating processing jobs...")

        metric = DataQualityMetric(
            "处理任务数据质量",
            "验证处理任务数据的完整性和有效性"
        )

        # 1. 完整性：必填字段
        required_fields = ["document_id", "file_path", "status"]
        for field in required_fields:
            result = await self.session.execute(
                select(func.count(ProcessingJob.id)).where(
                    getattr(ProcessingJob, field).is_(None)
                )
            )
            null_count = result.scalar()
            if null_count > 0:
                metric.add_fail(f"处理任务{field}字段为空: {null_count}个")
            else:
                metric.add_pass()

        self.metrics["processing_jobs"] = metric
        return metric.to_dict()

    async def _validate_consistency(self) -> Dict[str, Any]:
        """验证数据一致性"""
        logger.info("Validating data consistency...")

        metric = DataQualityMetric(
            "数据一致性",
            "验证跨表数据的一致性"
        )

        # 1. 用户-文档一致性
        result = await self.session.execute(
            select(func.count(Document.id)).where(
                ~Document.uploader_id.in_(
                    select(User.id)
                )
            )
        )
        orphan_docs = result.scalar()
        if orphan_docs > 0:
            metric.add_fail(f"孤立文档（无有效上传者）: {orphan_docs}个")
        else:
            metric.add_pass()

        # 2. 文档-文档块一致性
        result = await self.session.execute(
            select(func.count(DocumentChunk.id)).where(
                ~DocumentChunk.document_id.in_(
                    select(Document.id)
                )
            )
        )
        orphan_chunks = result.scalar()
        if orphan_chunks > 0:
            metric.add_fail(f"孤立文档块（无有效文档）: {orphan_chunks}个")
        else:
            metric.add_pass()

        # 3. 用户-搜索历史一致性
        result = await self.session.execute(
            select(func.count(SearchHistory.id)).where(
                ~SearchHistory.user_id.in_(
                    select(User.id)
                )
            )
        )
        orphan_histories = result.scalar()
        if orphan_histories > 0:
            metric.add_fail(f"孤立搜索历史（无有效用户）: {orphan_histories}个")
        else:
            metric.add_pass()

        self.metrics["consistency"] = metric
        return metric.to_dict()

    def _calculate_overall_score(self, results: Dict[str, Any]) -> float:
        """计算总体得分"""
        total_score = 0.0
        count = 0

        for table_name, table_result in results.items():
            if table_name != "overall_score":
                score = table_result.get("score", 0)
                total_score += score
                count += 1

        if count > 0:
            return total_score / count
        return 0.0

    async def export_report(self, results: Dict[str, Any], output_dir: Path):
        """导出验证报告"""
        logger.info("Exporting validation report...")

        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成JSON报告
        report_file = output_dir / f"data_validation_report_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"✅ Validation report exported to {report_file}")

        # 生成摘要
        summary_file = output_dir / "validation_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write("数据质量验证摘要\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"总体得分: {results['overall_score']:.2f}%\n\n")

            for table_name, table_result in results.items():
                if table_name != "overall_score":
                    f.write(f"\n{table_result['name']}\n")
                    f.write("-" * 50 + "\n")
                    f.write(f"得分: {table_result['score']:.2f}%\n")
                    f.write(f"通过: {table_result['pass_count']}\n")
                    f.write(f"失败: {table_result['fail_count']}\n")
                    f.write(f"总数: {table_result['total_count']}\n")
                    f.write(f"问题: {table_result['total_issues']}\n")

        logger.info(f"✅ Summary exported to {summary_file}")


# =============================================================================
# 主函数
# =============================================================================

async def main():
    """主函数"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker

    DATABASE_URL = "postgresql+asyncpg://tcm_admin:tcm_secure_pass_2024@localhost:5432/tcm_kb"
    OUTPUT_DIR = Path("/home/ai/zhineng-knowledge-system/analytics/reports")

    logger.info("=" * 50)
    logger.info("Starting Data Validation")
    logger.info("=" * 50)

    try:
        # 创建数据库引擎
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20
        )

        session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

        # 创建验证器
        async with session_factory() as session:
            validator = DataValidator(session)

            # 执行验证
            results = await validator.validate_all()

            # 导出报告
            await validator.export_report(results, OUTPUT_DIR)

        logger.info("=" * 50)
        logger.info("Data Validation Complete")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Error validating data: {e}", exc_info=True)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
