"""
智能气功内容解析器

基于标题和内容文本提取维度信息，适用于无文件路径的数据库
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class DimensionResult:
    """维度解析结果"""

    theory_system: str = "混元整体理论"
    content_topic: List[str] = field(default_factory=list)
    gongfa_stage: Optional[str] = None
    gongfa_method: Optional[str] = None
    content_depth: str = "中级"
    discipline: Optional[str] = None
    teaching_level: Optional[str] = None
    speaker: str = "庞明主讲"
    media_format: str = "文档"
    presentation: str = "书籍/教材"
    security_level: str = "public"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，过滤None值"""
        return {
            k: v
            for k, v in {
                "theory_system": self.theory_system,
                "content_topic": self.content_topic,
                "gongfa_stage": self.gongfa_stage,
                "gongfa_method": self.gongfa_method,
                "content_depth": self.content_depth,
                "discipline": self.discipline,
                "teaching_level": self.teaching_level,
                "speaker": self.speaker,
                "media_format": self.media_format,
                "presentation": self.presentation,
                "security_level": self.security_level,
            }.items()
            if v is not None and v != [] and v != ""
        }


class QigongContentParser:
    """
    智能气功内容解析器

    从标题和内容文本中提取维度信息
    """

    # ========== 教材关键词 ==========
    DISCIPLINE_KEYWORDS: Dict[str, str] = {
        "概论": "概论",
        "智能气功科学概论": "概论",
        "混元整体理论": "混元整体理论",
        "混元整体": "混元整体理论",
        "精义": "精义",
        "智能气功科学精义": "精义",
        "功法学": "功法学",
        "超常智能": "超常智能",
        "传统气功": "传统气功知识",
        "气功与文化": "气功与文化",
        "气功史": "气功史",
        "现代科学": "现代科学研究",
    }

    # ========== 教学层次关键词 ==========
    TEACHING_KEYWORDS: Dict[str, str] = {
        "大专班": "大专课程",
        "大专": "大专课程",
        "大专教材": "大专课程",
        "教练员班": "教练员班",
        "教练员": "教练员班",
        "师资班": "师资班",
        "师资": "师资班",
        "康复班": "康复班",
        "康复": "康复班",
        "学术交流": "学术交流会",
        "学术": "学术交流会",
        "专题": "专题班",
        "讲座": "公开讲座",
        "公开": "公开讲座",
    }

    # ========== 功法关键词 ==========
    GONGFA_KEYWORDS: Dict[str, tuple] = {
        "捧气贯顶": ("捧气贯顶法", "外混元"),
        "形神庄": ("形神庄", "内混元"),
        "形神桩": ("形神庄", "内混元"),
        "五元庄": ("五元庄", "内混元"),
        "五元桩": ("五元庄", "内混元"),
        "五元": ("五元庄", "内混元"),
        "中脉混元": ("中脉混元功", "中混元"),
        "中线混元": ("中线混元功", "中混元"),
        "混化归元": ("混化归元功", "中混元"),
        "三心并": ("三心并站庄", "外混元"),
        "拉气": ("拉气", "通用"),
        "组场": ("组场", "通用"),
        "收功": ("收功", "通用"),
        "自发功": ("自发功", "静动功"),
        "练气八法": ("练气八法", "通用"),
        "六步": ("六步动功", "通用"),
    }

    # ========== 内容主题关键词 ==========
    CONTENT_TOPIC_KEYWORDS: Dict[str, tuple] = {
        # 理论类
        "混元气": ("理论类", "深层理论"),
        "意元体": ("理论类", "深层理论"),
        "意识": ("理论类", "深层理论"),
        "意识论": ("理论类", "深层理论"),
        "道德": ("理论类", "深层理论"),
        "道德论": ("理论类", "深层理论"),
        "优化生命": ("理论类", "基础理论"),
        "混元论": ("理论类", "基础理论"),
        "整体论": ("理论类", "基础理论"),
        "内求法": ("理论类", "方法论"),
        "三传并用": ("理论类", "方法论"),
        # 功法类
        "调身": ("功法类", "调身"),
        "调息": ("功法类", "调息"),
        "呼吸": ("功法类", "调息"),
        "调心": ("功法类", "调心"),
        "意念": ("功法类", "调心"),
        "运用意识": ("功法类", "调心"),
        "超常智能": ("功法类", "超常智能"),
        "组场": ("功法类", "组场"),
        "收功": ("功法类", "收功"),
        "自发功": ("功法类", "自发功"),
        # 应用类
        "医学": ("应用类", "医学应用"),
        "治疗": ("应用类", "医学应用"),
        "诊断": ("应用类", "医学应用"),
        "康复": ("应用类", "医学应用"),
        "农业": ("应用类", "农业应用"),
        "工业": ("应用类", "工业应用"),
        "教育": ("应用类", "教育应用"),
        "智能": ("应用类", "教育应用"),
    }

    # ========== 理论体系关键词 ==========
    THEORY_SYSTEM_KEYWORDS: Dict[str, str] = {
        "混元整体理论": "混元整体理论",
        "混元气": "混元整体理论",
        "意元体": "混元整体理论",
        "传统理论": "传统理论借鉴",
        "传统文化": "传统理论借鉴",
        "儒释道": "传统理论借鉴",
        "阴阳": "传统理论借鉴",
        "五行": "传统理论借鉴",
        "藏象": "传统理论借鉴",
        "现代科学": "现代科学结合",
        "生理学": "现代科学结合",
        "解剖学": "现代科学结合",
        "心理学": "现代科学结合",
        "科研": "现代科学结合",
    }

    # ========== 传统功法（非智能气功） ==========
    TRADITIONAL_GONGFA: Set[str] = {
        "八段锦",
        "五禽戏",
        "六字诀",
        "易筋经",
        "太极拳",
        "太极",
        "形意拳",
        "八卦掌",
    }

    # ========== 功法阶段到深度映射 ==========
    STAGE_DEPTH_MAP: Dict[str, str] = {
        "外混元": "初级",
        "内混元": "中级",
        "中混元": "高级",
        "静动功": "中级",
        "通用": "中级",
    }

    # ========== 安全级别关键词 ==========
    SECURITY_KEYWORDS: Dict[str, str] = {
        "restricted": "内部|保密|机密|秘密|仅限内部",
        "confidential": "内部资料|内部教学|未公开",
        "internal": "讲义|教案|备课|辅导|学员须知",
    }

    def __init__(self):
        """初始化解析器"""
        # 编译正则表达式提高性能
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则表达式"""
        self.gongfa_pattern = re.compile(
            "|".join(re.escape(k) for k in self.GONGFA_KEYWORDS.keys())
        )
        self.discipline_pattern = re.compile(
            "|".join(re.escape(k) for k in self.DISCIPLINE_KEYWORDS.keys())
        )
        self.teaching_pattern = re.compile(
            "|".join(re.escape(k) for k in self.TEACHING_KEYWORDS.keys())
        )
        self.traditional_pattern = re.compile(
            "|".join(re.escape(k) for k in self.TRADITIONAL_GONGFA)
        )

    def _parse_traditional_gongfa(self, title_lower: str, result: "DimensionResult") -> bool:
        if not self.traditional_pattern.search(title_lower):
            return False
        result.theory_system = "传统理论借鉴"
        result.gongfa_stage = "通用"
        result.content_topic = ["功法类", "动功"]
        for gongfa in self.TRADITIONAL_GONGFA:
            if gongfa in title_lower:
                result.gongfa_method = gongfa
                result.content_topic = ["功法类", "动功"]
                break
        return True

    def _parse_discipline(self, title: str, full_text: str, result: "DimensionResult") -> None:
        for keyword, value in self.DISCIPLINE_KEYWORDS.items():
            if keyword in title or keyword in full_text:
                result.discipline = value
                break

    def _parse_teaching_level(self, title: str, full_text: str, result: "DimensionResult") -> None:
        for keyword, value in self.TEACHING_KEYWORDS.items():
            if keyword in title or keyword in full_text:
                result.teaching_level = value
                break

    def _parse_gongfa_from_title(self, title: str, result: "DimensionResult") -> None:
        gongfa_match = self.gongfa_pattern.search(title)
        if gongfa_match:
            keyword = gongfa_match.group()
            method, stage = self.GONGFA_KEYWORDS[keyword]
            result.gongfa_method = method
            result.gongfa_stage = stage
            if "功法类" not in result.content_topic:
                result.content_topic.append("功法类")
            if method == "组场":
                result.content_topic.append("组场")
            elif method == "收功":
                result.content_topic.append("收功")
        else:
            result.gongfa_stage = "通用"

    def _parse_content_topics(
        self, title_lower: str, content: str, result: "DimensionResult"
    ) -> None:
        for keyword, (category, topic) in self.CONTENT_TOPIC_KEYWORDS.items():
            if keyword in title_lower or (content and keyword in content.lower()[:500]):
                if category not in result.content_topic:
                    result.content_topic.append(category)
                if topic not in result.content_topic:
                    result.content_topic.append(topic)

    def _parse_theory_system(
        self, title_lower: str, full_text: str, result: "DimensionResult"
    ) -> None:
        for keyword, system in self.THEORY_SYSTEM_KEYWORDS.items():
            if keyword in title_lower or keyword in full_text[:500]:
                result.theory_system = system
                break

    def _default_content_topic(self, result: "DimensionResult") -> None:
        if not result.content_topic:
            if result.theory_system == "传统理论借鉴":
                result.content_topic = ["功法类", "动功"]
            elif result.discipline:
                result.content_topic = ["理论类", "基础理论"]
            else:
                result.content_topic = ["综合类"]

    def parse_from_title_content(self, title: str, content: str = "") -> Dict[str, Any]:
        """
        从标题和内容解析维度信息

        Args:
            title: 文档标题
            content: 文档内容（可选）

        Returns:
            维度信息字典
        """
        result = DimensionResult()
        full_text = f"{title} {content}".lower()
        title_lower = title.lower()

        if not self._parse_traditional_gongfa(title_lower, result):
            self._parse_discipline(title, full_text, result)
            self._parse_teaching_level(title, full_text, result)
            self._parse_gongfa_from_title(title, result)
            self._parse_content_topics(title_lower, content, result)
            self._parse_theory_system(title_lower, full_text, result)

        result.content_depth = self._infer_depth(result, title_lower)
        result.media_format = self._detect_media_format(title)
        result.presentation = self._infer_presentation(result.media_format, result.teaching_level)
        result.security_level = self._detect_security_level(title_lower)
        self._default_content_topic(result)

        return result.to_dict()

    def _infer_depth(self, result: DimensionResult, title_lower: str) -> str:
        """推断内容深度"""
        # 优先使用功法阶段
        if result.gongfa_stage and result.gongfa_stage != "通用":
            return self.STAGE_DEPTH_MAP.get(result.gongfa_stage, "中级")

        # 根据教学层次推断
        if result.teaching_level:
            level_map = {
                "康复班": "入门",
                "公开讲座": "入门",
                "大专课程": "专家",
                "师资班": "高级",
                "教练员班": "中级",
                "学术交流会": "专家",
                "专题班": "中级",
            }
            return level_map.get(result.teaching_level, "中级")

        # 根据教材推断
        if result.discipline:
            discipline_map = {
                "概论": "入门",
                "精义": "专家",
                "功法学": "中级",
                "混元整体理论": "高级",
            }
            return discipline_map.get(result.discipline, "中级")

        # 根据标题关键词推断
        if any(kw in title_lower for kw in ["入门", "基础", "初级", "教程", "教材"]):
            return "入门"
        if any(kw in title_lower for kw in ["高级", "深化", "研究", "论文"]):
            return "研究级"

        return "中级"

    def _detect_media_format(self, title: str) -> str:
        """从标题检测媒体格式"""
        ext_map = {
            ".mp3": "音频",
            ".wav": "音频",
            ".m4a": "音频",
            ".mp4": "视频",
            ".mpg": "视频",
            ".mpeg": "视频",
            ".avi": "视频",
            ".mov": "视频",
            ".wmv": "视频",
            ".rmvb": "视频",
            ".rm": "视频",
            ".pdf": "文档",
            ".doc": "文档",
            ".docx": "文档",
            ".txt": "文字",
            ".md": "文字",
            ".jpg": "图片",
            ".jpeg": "图片",
            ".png": "图片",
        }
        title_lower = title.lower()
        for ext, format_type in ext_map.items():
            if ext in title_lower:
                return format_type
        return "文档"

    def _infer_presentation(self, media_format: str, teaching_level: str) -> str:
        """推断传播形式"""
        if media_format == "音频":
            return "讲课"
        elif media_format == "视频":
            return "讲课"
        elif media_format == "文档":
            return "书籍/教材"
        elif media_format == "文字":
            return "笔记"

        # 根据教学层次推断
        if teaching_level in ["大专课程", "师资班", "教练员班"]:
            return "讲课"
        elif teaching_level == "公开讲座":
            return "讲课"

        return "书籍/教材"

    def _detect_security_level(self, text: str) -> str:
        """检测安全级别"""
        # 按优先级检查
        for level, keywords in self.SECURITY_KEYWORDS.items():
            for keyword in keywords.split("|"):
                if keyword in text:
                    return level
        return "public"


# 便捷函数
def parse_qigong_from_content(title: str, content: str = "") -> Dict[str, Any]:
    """
    从标题和内容解析智能气功维度

    Args:
        title: 文档标题
        content: 文档内容（可选）

    Returns:
        维度信息字典
    """
    parser = QigongContentParser()
    return parser.parse_from_title_content(title, content)


# 批量解析函数
def parse_batch(items: List[tuple]) -> List[Dict[str, Any]]:
    """
    批量解析

    Args:
        items: [(id, title, content), ...] 列表

    Returns:
        维度信息字典列表
    """
    parser = QigongContentParser()
    results = []
    for doc_id, title, content in items:
        try:
            dims = parser.parse_from_title_content(title, content or "")
            results.append((doc_id, dims))
        except Exception as e:
            print(f"Error parsing doc {doc_id}: {e}")
            results.append((doc_id, {}))
    return results


# 使用示例
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        ("形神庄第一式教学", ""),
        ("大专班精义教材-意识论", ""),
        ("捧气贯顶法详解", ""),
        ("健身气功八段锦教学视频", ""),
        ("智能气功科学概论", ""),
        ("组场技术与运用", ""),
    ]

    print("=" * 80)
    print("智能气功内容解析测试")
    print("=" * 80)

    for title, content in test_cases:
        print(f"\n标题: {title}")
        result = parse_qigong_from_content(title, content)
        for key, value in result.items():
            if isinstance(value, list):
                print(f"  {key}: {', '.join(value)}")
            else:
                print(f"  {key}: {value}")
