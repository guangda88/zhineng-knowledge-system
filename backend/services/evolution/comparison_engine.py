"""对比评估引擎

对比灵知系统与其他AI的回答质量，识别改进方向
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """对比评估引擎"""

    def __init__(self):
        pass

    async def compare_qa_responses(
        self, query: str, lingzhi_response: str, competitor_responses: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """对比问答回答质量

        评估维度：
        1. 内容完整性
        2. 准确性
        3. 实用性
        4. 结构清晰度
        5. 回答长度
        """

        # 提取所有响应内容
        all_responses = {"lingzhi": {"content": lingzhi_response, "provider": "lingzhi"}}
        for provider, response in competitor_responses.items():
            if response.get("success"):
                all_responses[provider] = {
                    "content": response.get("content", ""),
                    "provider": provider,
                }

        # 1. 内容完整性分析
        completeness = await self._analyze_completeness(query, all_responses)

        # 2. 实用性评分
        usefulness = await self._score_usefulness(query, all_responses)

        # 3. 结构清晰度
        clarity = await self._evaluate_clarity(all_responses)

        # 4. 回答长度分析
        length_analysis = self._analyze_length(all_responses)

        # 综合评分
        scores = {}
        for provider in all_responses.keys():
            scores[provider] = {
                "completeness": completeness.get(provider, 0),
                "usefulness": usefulness.get(provider, 0),
                "clarity": clarity.get(provider, 0),
                "overall": (
                    completeness.get(provider, 0) * 0.3
                    + usefulness.get(provider, 0) * 0.4
                    + clarity.get(provider, 0) * 0.3
                ),
            }

        # 确定胜者
        winner = max(scores.items(), key=lambda x: x[1]["overall"])[0]

        # 生成改进建议
        suggestions = self._generate_suggestions(query, all_responses, scores, winner)

        return {
            "query": query,
            "scores": scores,
            "winner": winner,
            "completeness": completeness,
            "usefulness": usefulness,
            "clarity": clarity,
            "length_analysis": length_analysis,
            "suggestions": suggestions,
            "evaluated_at": datetime.now().isoformat(),
        }

    async def _analyze_completeness(
        self, query: str, responses: Dict[str, Dict[str, str]]
    ) -> Dict[str, float]:
        """分析内容完整性（0-10分）"""

        scores = {}

        # 提取关键词
        keywords = self._extract_keywords(query)

        for provider, response in responses.items():
            content = response["content"].lower()

            # 检查关键词覆盖
            covered_keywords = sum(1 for kw in keywords if kw in content)
            keyword_coverage = covered_keywords / len(keywords) if keywords else 0

            # 检查内容长度（太短可能不完整）
            length_score = min(1.0, len(content) / 500)  # 500字为满分

            # 检查结构完整性（是否有概述、详情、总结）
            has_overview = any(word in content for word in ["概述", "简介", "首先", "总的来说"])
            has_details = any(word in content for word in ["具体", "详细", "其次", "另外"])
            has_summary = any(word in content for word in ["总结", "总之", "综上"])
            structure_score = (
                (1 if has_overview else 0) * 0.3
                + (1 if has_details else 0) * 0.4
                + (1 if has_summary else 0) * 0.3
            )

            # 综合评分
            overall_score = (
                keyword_coverage * 0.3 + length_score * 0.3 + structure_score * 0.4
            ) * 10

            scores[provider] = round(overall_score, 1)

        return scores

    async def _score_usefulness(
        self, query: str, responses: Dict[str, Dict[str, str]]
    ) -> Dict[str, float]:
        """评分实用性（0-10分）"""

        scores = {}

        for provider, response in responses.items():
            content = response["content"]

            # 检查是否有具体建议
            has_specific_advice = any(
                word in content for word in ["建议", "可以", "方法", "步骤", "应该", "推荐"]
            )

            # 检查是否有例子
            has_examples = any(word in content for word in ["例如", "比如", "举例", "案例", "像"])

            # 检查是否有数据支撑
            has_data = bool(re.search(r"\d+", content))

            # 检查是否有参考资料（灵知系统特色）
            has_references = any(
                word in content for word in ["参考", "资料", "来源", "文献", "书籍"]
            )

            # 综合评分
            usefulness_score = (
                (1 if has_specific_advice else 0) * 0.4
                + (1 if has_examples else 0) * 0.2
                + (1 if has_data else 0) * 0.2
                + (1 if has_references else 0) * 0.2
            ) * 10

            scores[provider] = round(usefulness_score, 1)

        return scores

    async def _evaluate_clarity(self, responses: Dict[str, Dict[str, str]]) -> Dict[str, float]:
        """评估结构清晰度（0-10分）"""

        scores = {}

        for provider, response in responses.items():
            content = response["content"]

            # 检查是否有标题/小标题
            has_headings = bool(re.search(r"^#+\s", content, re.MULTILINE))

            # 检查是否有列表
            has_lists = any(
                marker in content
                for marker in ["1.", "2.", "3.", "- ", "* ", "• ", "第一", "第二", "第三"]
            )

            # 检查分段是否合理
            paragraphs = content.split("\n\n")
            good_paragraphs = sum(1 for p in paragraphs if 50 < len(p) < 500)
            paragraph_score = min(1.0, good_paragraphs / len(paragraphs)) if paragraphs else 0

            # 综合评分
            clarity_score = (
                (1 if has_headings else 0) * 0.3
                + (1 if has_lists else 0) * 0.4
                + paragraph_score * 0.3
            ) * 10

            scores[provider] = round(clarity_score, 1)

        return scores

    def _analyze_length(self, responses: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
        """分析回答长度"""

        analysis = {}

        for provider, response in responses.items():
            content = response["content"]
            length = len(content)
            word_count = len(content.replace(" ", ""))

            analysis[provider] = {
                "character_count": length,
                "word_count": word_count,
                "paragraph_count": len([p for p in content.split("\n\n") if p.strip()]),
                "estimated_reading_time_minutes": max(1, word_count // 500),  # 500字/分钟
            }

        return analysis

    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询关键词"""
        # 简单实现：分词并过滤停用词
        import jieba

        words = jieba.cut(query)

        # 停用词
        stopwords = {
            "的",
            "了",
            "是",
            "在",
            "和",
            "有",
            "我",
            "你",
            "他",
            "她",
            "它",
            "们",
            "这",
            "那",
            "就",
            "也",
            "都",
            "而",
            "及",
            "与",
            "或",
        }

        keywords = [w for w in words if len(w) > 1 and w not in stopwords]

        return keywords[:10]  # 返回前10个关键词

    def _generate_suggestions(
        self,
        query: str,
        responses: Dict[str, Dict[str, str]],
        scores: Dict[str, Dict[str, float]],
        winner: str,
    ) -> List[Dict[str, Any]]:
        """生成改进建议"""

        suggestions = []

        # 如果灵知系统不是胜者
        if winner != "lingzhi":
            _winner_score = scores[winner]["overall"]  # noqa: F841
            _lingzhi_score = scores["lingzhi"]["overall"]  # noqa: F841

            # 找出差距最大的维度
            lingzhi_scores = scores["lingzhi"]
            winner_scores = scores[winner]

            gaps = {}
            for dimension in ["completeness", "usefulness", "clarity"]:
                gap = winner_scores[dimension] - lingzhi_scores[dimension]
                if gap > 1:  # 差距大于1分
                    gaps[dimension] = gap

            # 生成建议
            if "completeness" in gaps:
                suggestions.append(
                    {
                        "type": "completeness",
                        "priority": "high",
                        "description": f"{winner}的完整性更好（差距{gaps['completeness']:.1f}分）",
                        "action": "add_knowledge",
                        "details": f"建议检查知识库，补充关于'{query}'的相关内容",
                    }
                )

            if "usefulness" in gaps:
                suggestions.append(
                    {
                        "type": "usefulness",
                        "priority": "high",
                        "description": f"{winner}的实用性更好（差距{gaps['usefulness']:.1f}分）",
                        "action": "improve_response_template",
                        "details": "建议增加具体建议和案例",
                    }
                )

            if "clarity" in gaps:
                suggestions.append(
                    {
                        "type": "clarity",
                        "priority": "medium",
                        "description": f"{winner}的结构更清晰（差距{gaps['clarity']:.1f}分）",
                        "action": "improve_formatting",
                        "details": "建议优化回答格式，增加标题和列表",
                    }
                )

        # 即使灵知系统是胜者，也检查是否有改进空间
        else:
            if scores["lingzhi"]["completeness"] < 8:
                suggestions.append(
                    {
                        "type": "completeness",
                        "priority": "low",
                        "description": "完整性有提升空间",
                        "action": "enhance_content",
                        "details": "虽然当前回答最好，但可以更全面",
                    }
                )

        return suggestions

    async def compare_podcast_responses(
        self, topic: str, lingzhi_output: str, competitor_outputs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """对比播客生成质量

        评估维度：
        1. 内容吸引力
        2. 结构合理性
        3. 语言风格
        4. 专业性
        """

        # 提取所有输出
        all_outputs = {"lingzhi": {"content": lingzhi_output, "provider": "lingzhi"}}
        for provider, output in competitor_outputs.items():
            if output.get("success"):
                all_outputs[provider] = {"content": output.get("content", ""), "provider": provider}

        # 评估各个维度
        engagement = await self._evaluate_engagement(all_outputs)
        structure = await self._evaluate_podcast_structure(all_outputs)
        style = await self._evaluate_language_style(all_outputs)
        professionalism = await self._evaluate_professionalism(all_outputs)

        # 综合评分
        scores = {}
        for provider in all_outputs.keys():
            scores[provider] = {
                "engagement": engagement.get(provider, 0),
                "structure": structure.get(provider, 0),
                "style": style.get(provider, 0),
                "professionalism": professionalism.get(provider, 0),
                "overall": (
                    engagement.get(provider, 0) * 0.3
                    + structure.get(provider, 0) * 0.3
                    + style.get(provider, 0) * 0.2
                    + professionalism.get(provider, 0) * 0.2
                ),
            }

        winner = max(scores.items(), key=lambda x: x[1]["overall"])[0]

        return {
            "topic": topic,
            "scores": scores,
            "winner": winner,
            "evaluated_at": datetime.now().isoformat(),
        }

    async def _evaluate_engagement(self, outputs: Dict[str, Dict[str, str]]) -> Dict[str, float]:
        """评估内容吸引力"""

        scores = {}

        for provider, output in outputs.items():
            content = output["content"]

            # 检查是否有开场白
            has_opening = any(
                word in content[:200] for word in ["大家好", "欢迎", "今天", "我们来聊", "本期节目"]
            )

            # 检查是否有互动性
            has_interaction = any(
                word in content for word in ["大家", "你们", "听众", "朋友们", "各位"]
            )

            # 检查是否有故事或案例
            has_story = any(word in content for word in ["故事", "案例", "曾经", "有一次", "记得"])

            # 综合评分
            engagement_score = (
                (1 if has_opening else 0) * 0.3
                + (1 if has_interaction else 0) * 0.3
                + (1 if has_story else 0) * 0.4
            ) * 10

            scores[provider] = round(engagement_score, 1)

        return scores

    async def _evaluate_podcast_structure(
        self, outputs: Dict[str, Dict[str, str]]
    ) -> Dict[str, float]:
        """评估播客结构"""

        scores = {}

        for provider, output in outputs.items():
            content = output["content"]

            # 检查是否有清晰的开场、主体、结尾
            lines = content.split("\n")
            _non_empty_lines = [line for line in lines if line.strip()]  # noqa: F841

            # 简单结构检查
            has_intro = any(word in content[:300] for word in ["介绍", "开始", "首先"])
            has_body = len(content) > 500
            has_outro = any(word in content[-300:] for word in ["总结", "结束", "感谢", "下次"])

            structure_score = (
                (1 if has_intro else 0) * 0.3
                + (1 if has_body else 0) * 0.4
                + (1 if has_outro else 0) * 0.3
            ) * 10

            scores[provider] = round(structure_score, 1)

        return scores

    async def _evaluate_language_style(
        self, outputs: Dict[str, Dict[str, str]]
    ) -> Dict[str, float]:
        """评估语言风格"""

        scores = {}

        for provider, output in outputs.items():
            content = output["content"]

            # 检查口语化程度
            colloquial_indicators = ["嗯", "啊", "呢", "吧", "哦", "那个", "这个", "就是说"]
            colloquial_count = sum(content.count(indicator) for indicator in colloquial_indicators)
            colloquial_score = min(1.0, colloquial_count / 20)  # 适度口语化

            # 检查句子长度（播客适合短句）
            sentences = re.split(r"[。！？]", content)
            avg_sentence_length = (
                sum(len(s) for s in sentences) / len(sentences) if sentences else 0
            )
            sentence_score = max(0, 1 - avg_sentence_length / 100)  # 句子越短越好

            style_score = (colloquial_score + sentence_score) / 2 * 10

            scores[provider] = round(style_score, 1)

        return scores

    async def _evaluate_professionalism(
        self, outputs: Dict[str, Dict[str, str]]
    ) -> Dict[str, float]:
        """评估专业性"""

        scores = {}

        for provider, output in outputs.items():
            content = output["content"]

            # 检查专业术语使用
            technical_terms = [
                "理论",
                "方法",
                "研究",
                "数据",
                "科学",
                "原理",
                "机制",
                "实践",
                "应用",
            ]
            tech_count = sum(1 for term in technical_terms if term in content)

            # 检查是否有引用或参考
            has_references = any(
                word in content for word in ["根据", "研究表明", "数据", "研究", "文献"]
            )

            # 综合评分
            professionalism_score = (
                min(1.0, tech_count / 5) * 0.5 + (1 if has_references else 0) * 0.5
            ) * 10

            scores[provider] = round(professionalism_score, 1)

        return scores


# 全局实例
_comparison_engine = None


def get_comparison_engine() -> ComparisonEngine:
    """获取对比评估引擎单例"""
    global _comparison_engine
    if _comparison_engine is None:
        _comparison_engine = ComparisonEngine()
    return _comparison_engine
