"""
智能气功资料路径解析规则引擎

基于文件路径和文件名自动提取维度信息
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TeachingLevel(Enum):
    """教学层次"""

    DA_ZHUAN = "大专课程"
    JIAO_LIAN_YUAN = "教练员班"
    SHI_ZI = "师资班"
    KANG_FU = "康复班"
    XUE_SHU = "学术交流会"
    ZHUANTI = "专题班"
    GONGKAI = "公开讲座"


class Discipline(Enum):
    """教材归属"""

    GAI_LUN = "概论"
    HUN_YUAN = "混元整体理论"
    JING_YI = "精义"
    GONG_FA = "功法学"
    CHAO_CHANG = "超常智能"
    CHUAN_TONG = "传统气功知识"
    WEN_HUA = "气功与文化"
    LI_SHI = "气功史"
    KE_YAN = "现代科学研究"
    FEI_JIAO_CAI = "非教材"


class MediaType(Enum):
    """媒体格式"""

    AUDIO = "音频"
    VIDEO = "视频"
    DOCUMENT = "文档"
    TEXT = "文字"
    IMAGE = "图片"


class TheorySystem(Enum):
    """理论体系"""

    HUN_YUAN = "混元整体理论"
    TRADITIONAL = "传统理论借鉴"
    MODERN = "现代科学结合"


@dataclass
class DimensionResult:
    """维度解析结果"""

    teaching_level: Optional[str] = None
    discipline: Optional[str] = None
    media_format: Optional[str] = None
    speaker: str = "庞明主讲"
    content_topic: List[str] = field(default_factory=list)
    gongfa_stage: Optional[str] = None
    gongfa_method: Optional[str] = None
    theory_system: str = "混元整体理论"
    content_depth: Optional[str] = None
    presentation: Optional[str] = None
    course_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，过滤None值"""
        return {
            k: v
            for k, v in {
                "teaching_level": self.teaching_level,
                "discipline": self.discipline,
                "media_format": self.media_format,
                "speaker": self.speaker,
                "content_topic": self.content_topic,
                "gongfa_stage": self.gongfa_stage,
                "gongfa_method": self.gongfa_method,
                "theory_system": self.theory_system,
                "content_depth": self.content_depth,
                "presentation": self.presentation,
                "course_type": self.course_type,
            }.items()
            if v is not None and v != [] and v != ""
        }


class QigongPathParser:
    """
    智能气功资料路径解析器

    从文件路径和文件名中自动提取维度信息
    """

    # 教学关键词映射
    TEACHING_KEYWORDS = {
        "大专班": TeachingLevel.DA_ZHUAN,
        "大专": TeachingLevel.DA_ZHUAN,
        "教练员班": TeachingLevel.JIAO_LIAN_YUAN,
        "教练员": TeachingLevel.JIAO_LIAN_YUAN,
        "师资班": TeachingLevel.SHI_ZI,
        "师资": TeachingLevel.SHI_ZI,
        "康复班": TeachingLevel.KANG_FU,
        "康复": TeachingLevel.KANG_FU,
        "学术交流": TeachingLevel.XUE_SHU,
        "学术": TeachingLevel.XUE_SHU,
        "专题": TeachingLevel.ZHUANTI,
        "讲座": TeachingLevel.GONGKAI,
    }

    # 教材关键词映射
    DISCIPLINE_KEYWORDS = {
        "概论": Discipline.GAI_LUN,
        "混元整体理论": Discipline.HUN_YUAN,
        "混元整体": Discipline.HUN_YUAN,
        "精义": Discipline.JING_YI,
        "功法学": Discipline.GONG_FA,
        "超常智能": Discipline.CHAO_CHANG,
        "传统气功": Discipline.CHUAN_TONG,
        "气功与文化": Discipline.WEN_HUA,
        "气功史": Discipline.LI_SHI,
        "现代科学": Discipline.KE_YAN,
    }

    # 文件扩展名映射
    EXTENSION_MAP: Dict[str, MediaType] = {
        # 音频
        ".mp3": MediaType.AUDIO,
        ".wav": MediaType.AUDIO,
        ".m4a": MediaType.AUDIO,
        ".flac": MediaType.AUDIO,
        ".ogg": MediaType.AUDIO,
        # 视频
        ".mp4": MediaType.VIDEO,
        ".mpg": MediaType.VIDEO,
        ".mpeg": MediaType.VIDEO,
        ".avi": MediaType.VIDEO,
        ".mov": MediaType.VIDEO,
        ".wmv": MediaType.VIDEO,
        ".rm": MediaType.VIDEO,
        ".rmvb": MediaType.VIDEO,
        # 文档
        ".pdf": MediaType.DOCUMENT,
        ".doc": MediaType.DOCUMENT,
        ".docx": MediaType.DOCUMENT,
        # 文字
        ".txt": MediaType.TEXT,
        ".md": MediaType.TEXT,
        # 图片
        ".jpg": MediaType.IMAGE,
        ".jpeg": MediaType.IMAGE,
        ".png": MediaType.IMAGE,
        ".bmp": MediaType.IMAGE,
        ".tiff": MediaType.IMAGE,
    }

    # 功法关键词
    GONGFA_KEYWORDS: Dict[str, str] = {
        "捧气贯顶": "捧气贯顶法",
        "形神庄": "形神庄",
        "形神桩": "形神庄",
        "五元庄": "五元庄",
        "五元桩": "五元庄",
        "五元": "五元庄",
        "中脉混元": "中脉混元功",
        "中线混元": "中线混元功",
        "混化归元": "混化归元功",
        "三心并": "三心并站庄",
        "拉气": "拉气",
        "组场": "组场",
        "收功": "收功",
        "自发功": "自发功",
        "练气八法": "练气八法",
    }

    # 功法阶段映射
    GONGFA_STAGE_MAP: Dict[str, str] = {
        "捧气贯顶法": "外混元",
        "三心并站庄": "外混元",
        "形神庄": "内混元",
        "五元庄": "内混元",
        "中脉混元功": "中混元",
        "中线混元功": "中混元",
        "混化归元功": "中混元",
        "自发功": "静动功",
    }

    # 内容主题关键词映射
    CONTENT_TOPIC_KEYWORDS: Dict[str, str] = {
        # 理论类
        "混元气": "深层理论",
        "意元体": "深层理论",
        "意识": "深层理论",
        "道德": "深层理论",
        "优化生命": "基础理论",
        "混元论": "基础理论",
        "整体论": "基础理论",
        "内求法": "方法论",
        "三传并用": "方法论",
        # 功法类
        "调身": "调身",
        "调息": "调息",
        "呼吸": "调息",
        "调心": "调心",
        "意念": "调心",
        "运用意识": "调心",
        "收功": "收功",
        "超常智能": "超常智能",
        "组场": "组场",
        # 应用类
        "医学": "医学应用",
        "治疗": "医学应用",
        "诊断": "医学应用",
        "农业": "农业应用",
        "工业": "工业应用",
        "教育": "教育应用",
        # 综合类
        "发展": "发展历程",
        "历史": "发展历程",
        "人物": "人物",
        "组织": "组织建设",
        "重大事件": "重大事件",
        "答疑": "答疑解惑",
    }

    # 功法阶段到内容深度映射
    STAGE_DEPTH_MAP: Dict[str, str] = {
        "外混元": "初级",
        "内混元": "中级",
        "中混元": "高级",
        "静动功": "中级",
    }

    @classmethod
    def _match_keyword_in_parts(cls, parts, keyword_map, attr_name):
        """在路径组件中匹配关键词，返回匹配的枚举值"""
        for part in parts:
            for keyword, enum_val in keyword_map.items():
                if keyword in part:
                    return enum_val.value
        return None

    @classmethod
    def _infer_presentation(cls, media_format):
        """根据媒体格式推断传播形式"""
        mapping = {
            MediaType.AUDIO.value: "讲课",
            MediaType.VIDEO.value: "讲课",
            MediaType.DOCUMENT.value: "书籍/教材",
            MediaType.TEXT.value: "笔记",
        }
        return mapping.get(media_format)

    @classmethod
    def _infer_course_type(cls, teaching_level):
        """根据教学层次推断课程类型"""
        if teaching_level in ["大专课程", "师资班", "教练员班"]:
            return "系统授课"
        if teaching_level == "公开讲座":
            return "公开讲座"
        if teaching_level == "学术交流会":
            return "学术交流"
        return None

    @classmethod
    def _parse_gongfa(cls, filename, result):
        """从文件名解析功法信息"""
        for keyword, gongfa in cls.GONGFA_KEYWORDS.items():
            if keyword in filename:
                result.gongfa_method = gongfa
                result.gongfa_stage = cls.GONGFA_STAGE_MAP.get(gongfa, "通用")
                if "功法类" not in result.content_topic:
                    result.content_topic.append("功法类")
                sub_topic = {"组场": "组场", "拉气": "调身", "收功": "收功"}.get(gongfa)
                if sub_topic:
                    result.content_topic.append(sub_topic)
                return

    @classmethod
    def _parse_theory_system(cls, parts, filename):
        """从路径和文件名解析理论体系"""
        path_str = "/".join(parts).lower()
        if "健身气功" in path_str or "八段锦" in filename:
            return "传统理论借鉴", "通用"
        if "传统" in path_str or "儒释道" in path_str:
            return "传统理论借鉴", None
        return None, None

    @classmethod
    def _classify_topic(cls, topic):
        """根据内容主题返回一级分类"""
        theory = {"深层理论", "基础理论", "方法论"}
        gongfa = {"调身", "调息", "调心", "收功"}
        applied = {"医学应用", "农业应用", "工业应用", "教育应用"}
        general = {"发展历程", "人物", "组织建设", "重大事件", "答疑解惑"}
        if topic in theory:
            return "理论类"
        if topic in gongfa:
            return "功法类"
        if topic in applied:
            return "应用类"
        if topic in general:
            return "综合类"
        return None

    @classmethod
    def _parse_content_topics(cls, filename, stem, result):
        """从文件名解析内容主题"""
        for keyword, topic in cls.CONTENT_TOPIC_KEYWORDS.items():
            if keyword in filename or keyword in stem:
                category = cls._classify_topic(topic)
                if category and category not in result.content_topic:
                    result.content_topic.append(category)
                if topic not in result.content_topic:
                    result.content_topic.append(topic)
                return

    @classmethod
    def parse(cls, file_path: str) -> DimensionResult:
        """
        解析文件路径，提取维度信息

        Args:
            file_path: 文件路径

        Returns:
            DimensionResult 解析结果
        """
        path = Path(file_path)
        parts = path.parts
        filename = path.name
        stem = path.stem

        result = DimensionResult()

        result.teaching_level = cls._match_keyword_in_parts(
            parts, cls.TEACHING_KEYWORDS, "teaching_level"
        )
        result.discipline = cls._match_keyword_in_parts(
            parts, cls.DISCIPLINE_KEYWORDS, "discipline"
        )
        result.media_format = cls.EXTENSION_MAP.get(path.suffix.lower(), MediaType.DOCUMENT).value
        result.presentation = cls._infer_presentation(result.media_format)
        result.course_type = cls._infer_course_type(result.teaching_level)

        cls._parse_gongfa(filename, result)

        theory, stage_override = cls._parse_theory_system(parts, filename)
        if theory:
            result.theory_system = theory
        if stage_override:
            result.gongfa_stage = stage_override

        cls._parse_content_topics(filename, stem, result)

        if not result.gongfa_stage:
            result.gongfa_stage = "通用"

        result.content_depth = cls._infer_depth(result)

        return result

    @classmethod
    def _infer_depth(cls, result: DimensionResult) -> str:
        """根据功法阶段和教学层次推断内容深度"""
        # 优先使用功法阶段推断
        if result.gongfa_stage:
            depth = cls.STAGE_DEPTH_MAP.get(result.gongfa_stage)
            if depth:
                return depth

        # 根据教学层次推断
        if result.teaching_level == "康复班":
            return "入门"
        elif result.teaching_level == "大专课程":
            return "专家"
        elif result.teaching_level == "师资班":
            return "高级"
        elif result.teaching_level == "教练员班":
            return "中级"

        # 默认中级
        return "中级"

    @classmethod
    def parse_batch(cls, file_paths: List[str]) -> Dict[str, DimensionResult]:
        """
        批量解析文件路径

        Args:
            file_paths: 文件路径列表

        Returns:
            {file_path: DimensionResult} 字典
        """
        results = {}
        for path in file_paths:
            try:
                results[path] = cls.parse(path)
            except Exception as e:
                print(f"Error parsing {path}: {e}")
                results[path] = DimensionResult()  # 返回空结果
        return results


# 便捷函数
def parse_qigong_dimensions(file_path: str) -> Dict[str, Any]:
    """
    解析智能气功资料维度

    Args:
        file_path: 文件路径

    Returns:
        维度信息字典
    """
    return QigongPathParser.parse(file_path).to_dict()


# 使用示例
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "/大专班/精义/34/285明了调息的目的和作用C.mpg",
        "/音频/教练员班/混元气理论2.1.mp3",
        "/健身气功/健身气功八段锦/README.md",
        "/资料/形神庄教学/形神庄详解.pdf",
        "/庞明讲课/组场技术/组场方法与作用.doc",
    ]

    print("=" * 80)
    print("智能气功路径解析测试")
    print("=" * 80)

    for path in test_cases:
        print(f"\n路径: {path}")
        result = QigongPathParser.parse(path)
        dims = result.to_dict()
        for key, value in dims.items():
            if isinstance(value, list):
                print(f"  {key}: {', '.join(value)}")
            else:
                print(f"  {key}: {value}")
