"""课程生成器

自动生成课程结构、内容、练习等
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from .base import BaseGenerator, GenerationRequest, GenerationResult, GenerationStatus, OutputFormat

logger = logging.getLogger(__name__)


class CourseGenerator(BaseGenerator):
    """课程生成器"""

    def __init__(self, output_dir: str = "data/outputs/courses"):
        super().__init__()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def validate_request(self, request: GenerationRequest) -> bool:
        """验证请求参数"""
        if not request.topic:
            return False

        duration_weeks = request.parameters.get("duration_weeks", 8)
        if duration_weeks < 1 or duration_weeks > 52:
            return False

        return True

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """生成课程"""
        try:
            self.logger.info(f"开始生成课程: {request.topic}")

            # 获取参数
            target_audience = request.parameters.get("target_audience", "通用")
            duration_weeks = request.parameters.get("duration_weeks", 8)
            custom_chapters = request.parameters.get("chapters")
            include_exercises = request.parameters.get("include_exercises", True)

            # 构建课程结构
            course_structure = await self._build_course_structure(
                title=request.topic,
                target_audience=target_audience,
                duration_weeks=duration_weeks,
                custom_chapters=custom_chapters,
                include_exercises=include_exercises,
            )

            # 保存课程
            output_path = await self._save_course(
                task_id=request.task_id,
                structure=course_structure,
                output_format=request.output_format,
            )

            return GenerationResult(
                task_id=request.task_id,
                status=GenerationStatus.COMPLETED,
                output_path=output_path,
                output_url=f"/outputs/courses/{os.path.basename(output_path)}",
                metadata={
                    "course_title": request.topic,
                    "duration_weeks": duration_weeks,
                    "chapter_count": len(course_structure["chapters"]),
                    "target_audience": target_audience,
                },
                completed_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"课程生成失败: {e}", exc_info=True)
            return GenerationResult(
                task_id=request.task_id, status=GenerationStatus.FAILED, error_message=str(e)
            )

    async def _build_course_structure(
        self,
        title: str,
        target_audience: str,
        duration_weeks: int,
        custom_chapters: List[str],
        include_exercises: bool,
    ) -> Dict[str, Any]:
        """构建课程结构"""

        # 如果没有自定义章节，自动生成
        if not custom_chapters:
            custom_chapters = await self._generate_chapters(title, duration_weeks)

        chapters = []
        for week, chapter_title in enumerate(custom_chapters, 1):
            # 检索章节内容
            from backend.core.database import get_db_pool

            pool = get_db_pool()
            search_results = []
            if pool:
                try:
                    async with pool.acquire() as conn:
                        rows = await conn.fetch(
                            "SELECT id, title, content, category FROM documents "
                            "WHERE title ILIKE $1 OR content ILIKE $1 LIMIT 5",
                            f"%{title} {chapter_title}%",
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
                    logger.warning(f"Course generation search failed: {e}")

            # 构建章节
            chapter = {
                "week": week,
                "title": chapter_title,
                "content": self._synthesize_chapter_content(search_results),
                "learning_objectives": self._generate_learning_objectives(chapter_title),
                "key_concepts": self._extract_key_concepts(search_results),
            }

            if include_exercises:
                chapter["exercises"] = self._generate_exercises(chapter_title, search_results)

            chapters.append(chapter)

        return {
            "title": title,
            "target_audience": target_audience,
            "duration_weeks": duration_weeks,
            "created_at": datetime.now().isoformat(),
            "chapters": chapters,
        }

    async def _generate_chapters(self, title: str, week_count: int) -> List[str]:
        """生成章节标题"""
        # 基础章节模板
        base_chapters = [
            "导论与概述",
            "理论基础",
            "核心概念（一）",
            "核心概念（二）",
            "实践方法（一）",
            "实践方法（二）",
            "案例分析",
            "进阶应用",
            "总结与展望",
        ]

        # 根据周数调整
        if week_count <= len(base_chapters):
            return base_chapters[:week_count]
        else:
            # 如果周数更多，添加更多实践章节
            extended = base_chapters.copy()
            for i in range(week_count - len(base_chapters)):
                extended.append(f"专题研讨 {i + 1}")
            return extended

    def _synthesize_chapter_content(self, search_results: List[Dict]) -> str:
        """综合章节内容"""
        if not search_results:
            return "本章内容正在完善中，请参考相关教材和资料。"

        content_parts = []
        for result in search_results[:3]:
            content = result.get("content", "")
            if content:
                content_parts.append(content[:300])

        return "\n\n".join(content_parts)

    def _generate_learning_objectives(self, chapter_title: str) -> List[str]:
        """生成学习目标"""
        return [
            f"理解{chapter_title}的核心概念",
            "掌握相关的理论知识",
            "能够应用于实践",
            "培养分析问题和解决问题的能力",
        ]

    def _extract_key_concepts(self, search_results: List[Dict]) -> List[str]:
        """提取关键概念"""
        concepts = []
        for result in search_results[:5]:
            content = result.get("content", "")
            # 简单实现：提取长词汇作为概念
            words = content.split()
            concepts.extend([w for w in words if len(w) >= 4])

        return list(set(concepts))[:10]  # 返回前10个唯一概念

    def _generate_exercises(self, chapter_title: str, search_results: List[Dict]) -> List[Dict]:
        """生成练习题"""
        return [
            {
                "type": "choice",
                "question": f"关于{chapter_title}，以下说法正确的是？",
                "options": ["选项A", "选项B", "选项C", "选项D"],
                "answer": 0,
            },
            {"type": "essay", "question": f"请简述{chapter_title}的重要性。", "word_limit": 500},
            {
                "type": "practice",
                "question": f"请设计一个{chapter_title}的练习方案。",
                "duration_minutes": 30,
            },
        ]

    async def _save_course(
        self, task_id: str, structure: Dict[str, Any], output_format: OutputFormat
    ) -> str:
        """保存课程"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"course_{task_id}_{timestamp}.{output_format.value}"
        filepath = os.path.join(self.output_dir, filename)

        # 生成Markdown格式的课程内容
        content = self._format_course_as_markdown(structure)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"课程已保存: {filepath}")
        return filepath

    def _format_course_as_markdown(self, structure: Dict[str, Any]) -> str:
        """将课程格式化为Markdown"""
        lines = []

        lines.append(f"# {structure['title']}\n")
        lines.append(f"**目标受众**: {structure['target_audience']}\n")
        lines.append(f"**课程时长**: {structure['duration_weeks']}周\n")
        lines.append(f"**创建时间**: {structure['created_at']}\n")
        lines.append("\n---\n")

        for chapter in structure["chapters"]:
            lines.append(f"\n## 第{chapter['week']}周: {chapter['title']}\n")

            lines.append("### 学习目标\n")
            for obj in chapter.get("learning_objectives", []):
                lines.append(f"- {obj}")

            lines.append("\n### 关键概念\n")
            for concept in chapter.get("key_concepts", []):
                lines.append(f"- **{concept}**")

            lines.append("\n### 内容\n")
            lines.append(chapter.get("content", ""))

            if "exercises" in chapter:
                lines.append("\n### 练习题\n")
                for i, exercise in enumerate(chapter["exercises"], 1):
                    lines.append(f"\n**练习{i}** ({exercise['type']}):")
                    lines.append(f"{exercise['question']}")

        return "\n".join(lines)
