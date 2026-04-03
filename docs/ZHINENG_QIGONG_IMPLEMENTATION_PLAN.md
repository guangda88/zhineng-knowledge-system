# 智能气功资料维度体系实施规划

**文档编号**: ZQ-IMP-2026-PLAN
**制定日期**: 2026-04-02
**基于方案**: ZHINENG_QIGONG_DIMENSIONS_V4.0
**目标数据**: 13,564 篇气功文档

---

## 一、总体规划

### 1.1 实施目标

| 目标 | 指标 | 说明 |
|------|------|------|
| **覆盖率** | 第一期达到 50%+ 自动打标 | 通过路径解析实现 |
| **精度** | P0维度准确率 > 90% | 核心分类维度 |
| **效率** | 单文档打标 < 100ms | 规则引擎性能 |
| **成本** | 人工审核 < 10% | 优先高价值条目 |

### 1.2 时间规划

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        实施时间线（预计8周）                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Week 1-2: 第一期 - 基础设施建设                                              │
│  ├─ 数据库迁移（qigong_dims字段、词表）                                       │
│  ├─ 受控词表初始化（16维度+子项）                                             │
│  └─ 规则引擎框架搭建                                                         │
│                                                                              │
│  Week 3-4: 第一期 - 规则引擎开发                                              │
│  ├─ 路径解析规则开发                                                         │
│  ├─ 文件扩展名提取                                                           │
│  ├─ 关键词匹配规则                                                           │
│  └─ 批量打标执行                                                             │
│                                                                              │
│  Week 5-6: 第二期 - ASR转写（可选/并行）                                     │
│  ├─ MP3转写（2,367个）                                                       │
│  ├─ 视频转写（1,225个）                                                      │
│  └─ NLP增强打标                                                              │
│                                                                              │
│  Week 7: 第三期 - 人工审核与优化                                              │
│  ├─ 抽样审核（高价值条目）                                                    │
│  ├─ 规则调优                                                                 │
│  └─ 关联网络初始化                                                           │
│                                                                              │
│  Week 8: 验收与发布                                                          │
│  ├─ 功能验收                                                                 │
│  ├─ 性能测试                                                                 │
│  ├─ 文档交付                                                                 │
│  └─ 上线发布                                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、第一阶段：基础设施（Week 1-2）

### 2.1 任务清单

| ID | 任务 | 优先级 | 预计工时 | 负责人 |
|----|------|--------|---------|--------|
| 1.1 | 数据库迁移脚本编写 | P0 | 4h | 后端 |
| 1.2 | 受控词表数据准备 | P0 | 6h | 数据 |
| 1.3 | 维度服务API设计 | P0 | 4h | 后端 |
| 1.4 | 前端标注界面原型 | P1 | 8h | 前端 |
| 1.5 | 测试环境搭建 | P0 | 4h | 运维 |

### 2.2 数据库迁移

```sql
-- =====================================================
-- 迁移脚本 001: 添加维度字段
-- =====================================================

-- 1. 添加 qigong_dims JSONB 字段
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS qigong_dims JSONB DEFAULT '{}';

-- 2. 创建 GIN 索引
CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims
ON documents USING GIN (qigong_dims)
WHERE category = '气功';

-- 3. 创建部分索引（按维度查询优化）
CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_gongfa
ON documents ((qigong_dims->>'gongfa_method'))
WHERE qigong_dims ? 'gongfa_method' AND category = '气功';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_discipline
ON documents ((qigong_dims->>'discipline'))
WHERE qigong_dims ? 'discipline' AND category = '气功';

CREATE INDEX IF NOT EXISTS idx_documents_qigong_dims_teaching
ON documents ((qigong_dims->>'teaching_level'))
WHERE qigong_dims ? 'teaching_level' AND category = '气功';

-- 4. 创建触发器（自动更新 updated_at）
CREATE OR REPLACE FUNCTION documents_qigong_dims_update()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_qigong_dims_update
BEFORE UPDATE ON documents
FOR EACH ROW
WHEN (OLD.qigong_dims IS DISTINCT FROM NEW.qigong_dims)
EXECUTE FUNCTION documents_qigong_dims_update();

-- =====================================================
-- 迁移脚本 002: 创建受控词表
-- =====================================================

-- 维度词表
CREATE TABLE IF NOT EXISTS qigong_dimension_vocab (
  dimension_code  VARCHAR(50) PRIMARY KEY,
  dimension_name  VARCHAR(100) NOT NULL,
  category        VARCHAR(10) NOT NULL,
  priority        VARCHAR(10) NOT NULL DEFAULT 'P1',
  parent_code     VARCHAR(50),
  sub_items       JSONB NOT NULL DEFAULT '[]',
  auto_extract    BOOLEAN DEFAULT FALSE,
  description     TEXT,

  -- 演进支持
  status          VARCHAR(20) DEFAULT 'active',
  schema_version  VARCHAR(20) DEFAULT 'v4.0',
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW(),
  retired_at      TIMESTAMP,
  replacement_code VARCHAR(50),
  change_log      JSONB DEFAULT '[]'
);

-- 维度子项表
CREATE TABLE IF NOT EXISTS qigong_dimension_items (
  item_code       VARCHAR(100) PRIMARY KEY,
  dimension_code  VARCHAR(50) NOT NULL,
  item_name       VARCHAR(200) NOT NULL,
  parent_item_code VARCHAR(100),
  display_order   INTEGER DEFAULT 0,

  status          VARCHAR(20) DEFAULT 'active',
  since_version   VARCHAR(20) DEFAULT 'v4.0',
  deprecated_in   VARCHAR(20),
  replacement_code VARCHAR(100),

  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW(),

  FOREIGN KEY (dimension_code) REFERENCES qigong_dimension_vocab(dimension_code)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_dimension_vocab_cat
  ON qigong_dimension_vocab(category, priority);
CREATE INDEX IF NOT EXISTS idx_dimension_items_dim
  ON qigong_dimension_items(dimension_code, display_order);
```

### 2.3 受控词表初始化数据

```sql
-- =====================================================
-- 初始化数据: A类-内容维度
-- =====================================================

INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('theory_system', '理论体系归属', 'A', 'P0', '标识资料所属的理论体系'),
('content_topic', '内容主题', 'A', 'P0', '描述资料的具体内容主题，两级结构'),
('gongfa_system', '功法体系', 'A', 'P0', '按智能气功三阶段六步功法体系分类'),
('content_depth', '内容深度', 'A', 'P0', '描述资料的理论深度和适用对象'),
('discipline', '教材归属', 'A', 'P0', '对应智能气功科学九册教材体系')
ON CONFLICT (dimension_code) DO NOTHING;

-- theory_system 子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('theory_hunyuan', 'theory_system', '混元整体理论', 1),
('theory_traditional', 'theory_system', '传统理论借鉴', 2),
('theory_modern', 'theory_system', '现代科学结合', 3)
ON CONFLICT DO NOTHING;

-- content_topic 一级子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('topic_theory', 'content_topic', '理论类', 1),
('topic_gongfa', 'content_topic', '功法类', 2),
('topic_application', 'content_topic', '应用类', 3),
('topic_comprehensive', 'content_topic', '综合类', 4)
ON CONFLICT DO NOTHING;

-- gongfa_system 子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('gongfa_outer', 'gongfa_system', '外混元', 1),
('gongfa_inner', 'gongfa_system', '内混元', 2),
('gongfa_central', 'gongfa_system', '中混元', 3),
('gongfa_jingong', 'gongfa_system', '静功类', 4),
('gongfa_jingdong', 'gongfa_system', '静动功类', 5),
('gongfa_auxiliary', 'gongfa_system', '辅助功法', 6),
('gongfa_general', 'gongfa_system', '通用', 7)
ON CONFLICT DO NOTHING;

-- content_depth 子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('depth_intro', 'content_depth', '入门', 1),
('depth_beginner', 'content_depth', '初级', 2),
('depth_intermediate', 'content_depth', '中级', 3),
('depth_advanced', 'content_depth', '高级', 4),
('depth_expert', 'content_depth', '专家', 5),
('depth_research', 'content_depth', '研究级', 6)
ON CONFLICT DO NOTHING;

-- discipline 子项
INSERT INTO qigong_dimension_items (item_code, dimension_code, item_name, display_order) VALUES
('disc_intro', 'discipline', '概论', 1),
('disc_hunyuan', 'discipline', '混元整体理论', 2),
('disc_jingyi', 'discipline', '精义', 3),
('disc_gongfa', 'discipline', '功法学', 4),
('disc_supernormal', 'discipline', '超常智能', 5),
('disc_traditional', 'discipline', '传统气功知识', 6),
('disc_culture', 'discipline', '气功与文化', 7),
('disc_history', 'discipline', '气功史', 8),
('disc_research', 'discipline', '现代科学研究', 9),
('disc_none', 'discipline', '非教材', 10)
ON CONFLICT DO NOTHING;

-- =====================================================
-- 初始化数据: B类-情境维度
-- =====================================================

INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('timeline', '时间线', 'B', 'P1', '按智能气功发展历程划分时期'),
('location', '场所地点', 'B', 'P1', '记录资料产生的地点信息'),
('teaching_level', '教学层次', 'B', 'P1', '合并课程级别与对应受众'),
('presentation', '传播形式', 'B', 'P1', '描述资料的固有内容形态')
ON CONFLICT (dimension_code) DO NOTHING;

-- =====================================================
-- 初始化数据: C类-来源维度
-- =====================================================

INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('speaker', '主讲/作者', 'C', 'P1', '记录资料的主讲人或作者'),
('source_attribute', '来源属性', 'C', 'P2', '描述资料的来源、整理方式、权威等级')
ON CONFLICT (dimension_code) DO NOTHING;

-- =====================================================
-- 初始化数据: D类-技术维度
-- =====================================================

INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('media_format', '存在形式', 'D', 'P3', '描述资料的媒体格式'),
('tech_spec', '技术规格', 'D', 'P2', '合并载体介质与收录方式'),
('data_status', '完整状态', 'D', 'P3', '描述资料的完整性、处理状态和发布状态')
ON CONFLICT (dimension_code) DO NOTHING;

-- =====================================================
-- 初始化数据: E类-扩展维度
-- =====================================================

INSERT INTO qigong_dimension_vocab (dimension_code, dimension_name, category, priority, description) VALUES
('application_effect', '应用成效', 'E', 'P4', '记录资料中提到的应用效果数据'),
('related_resources', '关联网络', 'E', 'P4', '构建资料间的关联关系')
ON CONFLICT (dimension_code) DO NOTHING;
```

---

## 三、第二阶段：规则引擎（Week 3-4）

### 3.1 路径解析规则

```python
# backend/services/qigong/path_parser.py
"""
智能气功资料路径解析规则引擎
"""
import re
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


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


class QigongPathParser:
    """智能气功资料路径解析器"""

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
        "精义": Discipline.JING_YI,
        "功法学": Discipline.GONG_FA,
        "超常智能": Discipline.CHAO_CHANG,
        "传统气功": Discipline.CHUAN_TONG,
        "气功与文化": Discipline.WEN_HUA,
        "气功史": Discipline.LI_SHI,
        "现代科学": Discipline.KE_YAN,
    }

    # 文件扩展名映射
    EXTENSION_MAP = {
        # 音频
        ".mp3": MediaType.AUDIO,
        ".wav": MediaType.AUDIO,
        ".m4a": MediaType.AUDIO,
        ".flac": MediaType.AUDIO,
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
    GONGFA_KEYWORDS = {
        "捧气贯顶": "捧气贯顶法",
        "形神庄": "形神庄",
        "形神桩": "形神庄",
        "五元庄": "五元庄",
        "五元桩": "五元庄",
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
    GONGFA_STAGE_MAP = {
        "捧气贯顶法": "外混元",
        "三心并站庄": "外混元",
        "形神庄": "内混元",
        "五元庄": "内混元",
        "中脉混元功": "中混元",
        "中线混元功": "中混元",
        "混化归元功": "中混元",
        "自发功": "静动功",
    }

    @classmethod
    def parse(cls, file_path: str) -> Dict[str, Any]:
        """
        解析文件路径，提取维度信息

        Args:
            file_path: 文件路径

        Returns:
            维度信息字典
        """
        path = Path(file_path)
        parts = path.parts
        filename = path.name

        result = {
            "teaching_level": None,
            "discipline": None,
            "media_format": None,
            "speaker": "庞明主讲",  # 默认值
            "content_topic": [],
            "gongfa_stage": None,
            "gongfa_method": None,
            "theory_system": "混元整体理论",  # 默认值
        }

        # 解析教学层次
        for part in parts:
            for keyword, level in cls.TEACHING_KEYWORDS.items():
                if keyword in part:
                    result["teaching_level"] = level.value
                    break
            if result["teaching_level"]:
                break

        # 解析教材归属
        for part in parts:
            for keyword, disc in cls.DISCIPLINE_KEYWORDS.items():
                if keyword in part:
                    result["discipline"] = disc.value
                    break
            if result["discipline"]:
                break

        # 解析媒体格式
        ext = path.suffix.lower()
        result["media_format"] = cls.EXTENSION_MAP.get(ext, MediaType.DOCUMENT).value

        # 解析功法（从文件名）
        for keyword, gongfa in cls.GONGFA_KEYWORDS.items():
            if keyword in filename:
                result["gongfa_method"] = gongfa
                result["gongfa_stage"] = cls.GONGFA_STAGE_MAP.get(gongfa, "通用")
                # 添加到内容主题
                if "组场" not in result["content_topic"]:
                    result["content_topic"].append("功法类")
                break

        # 解析理论体系
        if "健身气功" in "/".join(parts) or "八段锦" in filename:
            result["theory_system"] = "传统理论借鉴"
            result["gongfa_stage"] = "通用"

        # 推断内容深度
        result["content_depth"] = cls._infer_depth(result)

        return result

    @classmethod
    def _infer_depth(cls, dims: Dict[str, Any]) -> str:
        """根据功法阶段推断内容深度"""
        stage = dims.get("gongfa_stage")
        stage_depth_map = {
            "外混元": "初级",
            "内混元": "中级",
            "中混元": "高级",
            "静动功": "中级",
        }
        return stage_depth_map.get(stage, "中级")


# 使用示例
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "/大专班/精义/34/285明了调息的目的和作用C.mpg",
        "/音频/教练员班/混元气理论2.1.mp3",
        "/健身气功/健身气功八段锦/README.md",
    ]

    for path in test_cases:
        print(f"\n路径: {path}")
        result = QigongPathParser.parse(path)
        for key, value in result.items():
            if value:
                print(f"  {key}: {value}")
```

### 3.2 批量打标服务

```python
# backend/services/qigong/batch_tagger.py
"""
批量打标服务
"""
import asyncpg
from typing import List, Dict, Any
from .path_parser import QigongPathParser


class QigongBatchTagger:
    """智能气功批量打标服务"""

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def tag_by_path_pattern(self, pattern: str = "%") -> Dict[str, int]:
        """
        按路径模式批量打标

        Args:
            pattern: LIKE 模式，默认全部

        Returns:
            统计信息
        """
        conn = await asyncpg.connect(self.db_url)

        try:
            # 查询需要打标的文档
            rows = await conn.fetch("""
                SELECT id, file_path, title, category
                FROM documents
                WHERE file_path LIKE $1
                  AND category = '气功'
                  AND (qigong_dims IS NULL OR qigong_dims = '{}'::jsonb)
                ORDER BY id
            """, pattern)

            stats = {
                "total": len(rows),
                "tagged": 0,
                "skipped": 0,
                "errors": 0,
            }

            for row in rows:
                try:
                    # 解析路径
                    dims = QigongPathParser.parse(row["file_path"])

                    # 更新数据库
                    await conn.execute("""
                        UPDATE documents
                        SET qigong_dims = $1::jsonb,
                            updated_at = NOW()
                        WHERE id = $2
                    """, dims, row["id"])

                    stats["tagged"] += 1

                except Exception as e:
                    print(f"Error tagging {row['id']}: {e}")
                    stats["errors"] += 1

            return stats

        finally:
            await conn.close()

    async def get_coverage_stats(self) -> Dict[str, Any]:
        """获取打标覆盖率统计"""
        conn = await asyncpg.connect(self.db_url)

        try:
            # 总数
            total = await conn.fetchval("""
                SELECT COUNT(*) FROM documents WHERE category = '气功'
            """)

            # 已打标
            tagged = await conn.fetchval("""
                SELECT COUNT(*) FROM documents
                WHERE category = '气功'
                  AND qigong_dims IS NOT NULL
                  AND qigong_dims != '{}'::jsonb
            """)

            # 各维度覆盖率
            dimensions = [
                "theory_system", "content_topic", "gongfa_system",
                "discipline", "teaching_level", "speaker"
            ]

            dim_coverage = {}
            for dim in dimensions:
                count = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM documents
                    WHERE category = '气功'
                      AND qigong_dims ? $1
                """, dim)
                dim_coverage[dim] = {
                    "count": count,
                    "coverage": f"{count / total * 100:.1f}%" if total else "0%"
                }

            return {
                "total": total,
                "tagged": tagged,
                "untagged": total - tagged,
                "coverage_rate": f"{tagged / total * 100:.1f}%" if total else "0%",
                "dimensions": dim_coverage,
            }

        finally:
            await conn.close()
```

---

## 四、第三阶段：ASR转写（Week 5-6，可选）

### 4.1 ASR服务集成

```python
# backend/services/qigong/asr_service.py
"""
ASR转写服务（使用FunASR）
"""
import asyncio
from pathlib import Path
from typing import Optional


class FunASRService:
    """FunASR转写服务"""

    def __init__(self, model: str = "paraformer-zh"):
        self.model = model
        self._load_model()

    def _load_model(self):
        """加载模型"""
        try:
            from funasr import AutoModel
            self.asr_model = AutoModel(
                model=self.model,
                device="cuda"  # 或 "cpu"
            )
        except ImportError:
            raise ImportError("请安装 funasr: pip install funasr")

    async def transcribe_file(
        self,
        audio_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        转写音频文件

        Args:
            audio_path: 音频文件路径
            output_path: 输出文本路径，默认与音频同目录

        Returns:
            转写文本
        """
        audio_file = Path(audio_path)
        if not output_path:
            output_path = audio_file.with_suffix(".txt")

        # 执行转写
        result = self.asr_model.generate(
            input=str(audio_file),
            batch_size_s=300,
            cache={},
            language="zh",
            use_itn=True,
        )

        text = result[0]["text"]

        # 保存文本
        Path(output_path).write_text(text, encoding="utf-8")

        return text

    async def transcribe_batch(
        self,
        audio_dir: str,
        pattern: str = "*.mp3",
        max_concurrent: int = 4
    ) -> dict:
        """
        批量转写

        Args:
            audio_dir: 音频目录
            pattern: 文件匹配模式
            max_concurrent: 最大并发数

        Returns:
            统计信息
        """
        audio_files = list(Path(audio_dir).rglob(pattern))

        stats = {
            "total": len(audio_files),
            "success": 0,
            "failed": 0,
        }

        semaphore = asyncio.Semaphore(max_concurrent)

        async def transcribe_one(audio_path):
            async with semaphore:
                try:
                    await self.transcribe_file(str(audio_path))
                    return {"path": str(audio_path), "status": "success"}
                except Exception as e:
                    return {"path": str(audio_path), "status": "failed", "error": str(e)}

        tasks = [transcribe_one(p) for p in audio_files]
        results = await asyncio.gather(*tasks)

        for r in results:
            if r["status"] == "success":
                stats["success"] += 1
            else:
                stats["failed"] += 1

        return stats
```

---

## 五、第四阶段：验收与发布（Week 7-8）

### 5.1 验收标准

| 验收项 | 标准 | 检查方法 |
|--------|------|---------|
| **数据迁移** | qigong_dims字段正常，索引生效 | SQL查询测试 |
| **词表完整性** | 16维度+子项完整导入 | 词表数据统计 |
| **自动打标覆盖率** | ≥50% 文档有维度数据 | 覆盖率统计查询 |
| **P0维度准确率** | ≥90% 抽样准确 | 人工审核100份 |
| **查询性能** | 维度过滤查询 <100ms | 性能测试 |
| **API完整性** | 增删改查接口可用 | API测试 |

### 5.2 上线检查清单

```
□ 数据库迁移脚本已执行并验证
□ 受控词表数据已完整导入
□ 规则引擎已测试主要路径模式
□ 批量打标已执行完成
□ 索引已创建并生效
□ API文档已更新
□ 监控告警已配置
□ 回滚方案已准备
```

---

## 六、风险管理

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 路径解析覆盖不足 | 打标率低 | 中 | 预留人工标注入口，持续优化规则 |
| ASR转写成本高 | 预算超支 | 中 | 分批转写，优先高价值内容 |
| 维度定义争议 | 需重新设计 | 低 | 预留演进机制，定期评审 |
| 性能问题 | 查询慢 | 低 | GIN索引，部分索引优化 |

---

## 七、后续优化方向

1. **知识图谱**: 基于关联网络构建知识图谱
2. **智能推荐**: 基于用户查询历史的维度推荐
3. **跨体系检索**: 支持智能气功与传统气功的对比查询
4. **多语言支持**: 扩展到英文、繁体中文资料
5. **用户反馈闭环**: 收集用户查询日志，优化维度权重

---

**文档编制**: 智能气功知识系统项目组
**版本**: 1.0
**日期**: 2026-04-02
