"""报告生成器

生成各类知识报告：
- 学术报告
- 研究综述
- 课程笔记
- 实践总结
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from .base import BaseGenerator, GenerationRequest, GenerationResult, GenerationStatus, OutputFormat

logger = logging.getLogger(__name__)


class ReportGenerator(BaseGenerator):
    """报告生成器"""

    # 支持的报告类型
    REPORT_TYPES = {
        "academic": "学术报告",
        "review": "研究综述",
        "notes": "课程笔记",
        "practice": "实践总结",
        "analysis": "专题分析",
    }

    def __init__(self, output_dir: str = "data/outputs/reports"):
        super().__init__()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def validate_request(self, request: GenerationRequest) -> bool:
        """验证请求参数"""
        if not request.topic:
            return False

        report_type = request.parameters.get("report_type")
        if report_type not in self.REPORT_TYPES:
            logger.warning(f"未知的报告类型: {report_type}")
            return False

        return True

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """生成报告"""
        try:
            self.logger.info(f"开始生成报告: {request.topic}")

            # 获取报告参数
            report_type = request.parameters.get("report_type", "academic")
            sections = request.parameters.get("sections", [])
            include_references = request.parameters.get("include_references", True)
            language = request.parameters.get("language", "zh")

            # 构建报告内容
            content = await self._build_report_content(
                topic=request.topic,
                report_type=report_type,
                sections=sections,
                include_references=include_references,
                language=language,
            )

            # 保存报告
            output_path = await self._save_report(
                task_id=request.task_id, content=content, output_format=request.output_format
            )

            return GenerationResult(
                task_id=request.task_id,
                status=GenerationStatus.COMPLETED,
                output_path=output_path,
                output_url=f"/outputs/reports/{os.path.basename(output_path)}",
                metadata={
                    "report_type": report_type,
                    "word_count": len(content),
                    "sections_count": len(sections),
                },
                completed_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"报告生成失败: {e}", exc_info=True)
            return GenerationResult(
                task_id=request.task_id, status=GenerationStatus.FAILED, error_message=str(e)
            )

    async def _build_report_content(
        self,
        topic: str,
        report_type: str,
        sections: List[str],
        include_references: bool,
        language: str,
    ) -> str:
        """构建报告内容"""

        # 如果没有指定章节，使用默认结构
        if not sections:
            sections = self._get_default_sections(report_type)

        # 从知识库检索相关信息
        from backend.core.database import get_db_pool

        pool = get_db_pool()

        # 为每个章节检索相关内容
        section_contents = []
        for section in sections:
            search_results = []
            if pool:
                try:
                    async with pool.acquire() as conn:
                        rows = await conn.fetch(
                            "SELECT id, title, content, category FROM documents "
                            "WHERE title ILIKE $1 OR content ILIKE $1 LIMIT 5",
                            f"%{topic} {section}%",
                        )
                        search_results = [
                            {
                                "id": r["id"],
                                "title": r["title"],
                                "content": r["content"],
                                "category": r["category"],
                            }
                            for r in rows
                        ]
                except Exception as e:
                    logger.warning(f"Report generation search failed: {e}")

            # 整理内容
            section_text = await self._synthesize_section(
                section_title=section, search_results=search_results, topic=topic
            )
            section_contents.append(section_text)

        # 组装完整报告
        report = f"""# {topic}

**报告类型**: {self.REPORT_TYPES.get(report_type, report_type)}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 目录

{self._generate_toc(sections)}

---

{"".join(section_contents)}

---

"""

        if include_references:
            report += await self._generate_references(topic)

        return report

    def _get_default_sections(self, report_type: str) -> List[str]:
        """获取默认章节结构"""
        default_structures = {
            "academic": ["引言", "理论基础", "核心概念", "实践方法", "案例分析", "结论与展望"],
            "review": ["研究背景", "文献综述", "研究方法", "主要发现", "研究不足", "未来方向"],
            "notes": ["核心要点", "重要概念", "实践指导", "注意事项", "思考题"],
            "practice": ["练习目的", "准备工作", "步骤详解", "要点提示", "常见问题", "进阶指导"],
            "analysis": ["问题概述", "原因分析", "解决方案", "实施建议", "预期效果"],
        }

        return default_structures.get(report_type, ["概述", "详细内容", "总结"])

    async def _synthesize_section(
        self, section_title: str, search_results: List[Dict], topic: str
    ) -> str:
        """综合章节内容"""
        section = f"\n## {section_title}\n\n"

        if not search_results:
            section += f"*关于「{topic} - {section_title}」的内容，当前知识库中暂无详细信息。*\n\n"
            return section

        # 整合搜索结果
        for i, result in enumerate(search_results[:3], 1):
            content = result.get("content", "")
            source = result.get("metadata", {}).get("source", "未知来源")

            section += f"### {i}. {content[:100]}...\n\n"
            section += f"**来源**: {source}\n\n"

        return section

    def _generate_toc(self, sections: List[str]) -> str:
        """生成目录"""
        toc = ""
        for i, section in enumerate(sections, 1):
            toc += f"{i}. [{section}](#{section})\n"
        return toc

    async def _generate_references(self, topic: str) -> str:
        """生成参考文献"""
        return """
## 参考文献

1. 智能气功科学系列教材
2. 相关学术论文
3. 实践案例集
4. 专家讲座记录
"""

    async def _save_report(self, task_id: str, content: str, output_format: OutputFormat) -> str:
        """保存报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{task_id}_{timestamp}.{output_format.value}"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"报告已保存: {filepath}")
        return filepath

    async def generate_report_from_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """从模板生成报告"""
        # 预定义模板
        templates = {
            "daily_practice": """
# 每日练功报告

**日期**: {date}
**练功项目**: {practice_type}
**练功时长**: {duration}分钟

## 练功内容

{practice_content}

## 身体反应

{body_reaction}

## 心得体会

{experience}

## 下一步计划

{next_plan}
            """,
            "learning_summary": """
# 学习总结报告

**学习主题**: {topic}
**学习时间**: {date}
**学习时长**: {duration}小时

## 核心要点

{key_points}

## 理论理解

{theory_understanding}

## 实践体会

{practice_experience}

## 疑问与思考

{questions}

## 后续学习计划

{future_plan}
            """,
        }

        template = templates.get(template_name)
        if not template:
            raise ValueError(f"未找到模板: {template_name}")

        return template.format(**data)
