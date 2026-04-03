# Sys_books.db V4 维度应用可行性评估报告

**数据源**: `/data/external/Sys_books.db`
**评估日期**: 2026-04-02
**数据规模**: 3,024,428 条书籍记录

---

## 一、数据概览

### 1.1 总体统计

| 指标 | 数值 |
|------|------|
| 总记录数 | 3,024,428 |
| 类别数 | 2,119 |
| 来源数 | 4 |
| 文件类型 | 2 |

### 1.2 智能气功相关数据

| 类别 | 记录数 | 说明 |
|------|--------|------|
| ZNQG 相关总量 | ~150,000 | 智能气功专门分类 |
| 百度云9080\ZNQG | 51,823 | 主分类 |
| 百度云2362\ZNQG新整理 | 37,518 | 整理后数据 |
| 智能 | 25,946 | 通用分类 |
| 115\Zhineng | 21,954 | 国学大师分类 |

---

## 二、数据结构与 V4 映射

### 2.1 现有字段分析

| 字段 | 类型 | V4 映射 | 可用性 |
|------|------|--------|--------|
| `category` | TEXT | teaching_level | ✅ 高 |
| `filename` | TEXT | content_topic, gongfa_method | ✅ 高 |
| `source` | TEXT | timeline (路径中年份) | ✅ 中 |
| `file_type` | TEXT | media_format | ✅ 高 |
| `author` | TEXT | speaker | ✅ 中 |
| `year` | TEXT | timeline | ✅ 中 |
| `path` | TEXT | 辅助信息 | ✅ 低 |

### 2.2 高价值细分类别

#### 音频资料 (~1,500 条)

```
ZNQG音频/
├── 1987-1988年北京海淀大学讲课 (??)
├── 1988.4全国形神庄辅导员培训班 (62)
├── 1988-1991石家庄进修学院 (65)
├── 师资班座谈录音 (66)
├── 1996.3月在骨干提高班上的讲话 (38)
├── 1996.5第五届全国智能气功科学学术交流会 (6)
└── ... (按时间/活动分类)
```

**V4 映射**:
- `category` → `teaching_level`: 辅导员班、师资班、骨干提高班
- `filename` → `content_topic`: 混元气理论、形神庄
- `category` 年份 → `timeline`: 1987-1996 各时期

#### 视频资料 (~100 条)

```
ZNQG视频/
├── 1988.4_石家庄_全国形神庄辅导员培训班 (多个)
├── 1993_辅导员班讲课_混元气理论
├── 1993_辅导员班讲课_运用意识
├── 1996_康复班讲课：怎样运用意识
├── 1997.7.15_庞老师在提高班上的讲课_关于气功医疗
├── 练气八法-前四法
└── ... (教学视频、宣传片、病例)
```

**V4 映射**:
- `filename` → `gongfa_method`: 形神庄、练气八法
- `filename` → `content_topic`: 混元气理论、运用意识、气功医疗
- `filename` → `teaching_level`: 辅导员班、康复班、提高班
- `filename` → `presentation`: 讲课 (视频格式)

---

## 三、V4 维度适配方案

### 3.1 直接映射字段

| V4 维度 | Sys_books 字段 | 提取规则 |
|---------|----------------|----------|
| `teaching_level` | category | 正则: "(辅导员班\|师资班\|康复班\|提高班\|大专)" |
| `content_topic` | filename | 正则: "(混元气理论\|形神庄\|运用意识\|组场)" |
| `gongfa_method` | filename | 正则: "(形神庄\|捧气贯顶\|五元庄\|练气八法)" |
| `media_format` | file_type/extension | 映射: "视频"→video, "音频"→audio |
| `timeline` | category (年份) | 正则: "(19\d{2})" |
| `speaker` | filename/author | 正则: "庞" → "庞明主讲" |

### 3.2 推断维度

| V4 维度 | 推断规则 |
|---------|----------|
| `theory_system` | 默认 "混元整体理论" |
| `content_depth` | 根据 teaching_level 推断 |
| `presentation` | 根据 media_format 推断 |
| `security_level` | 默认 "public" |

---

## 四、实施建议

### 4.1 Phase 1: 数据导出与清洗 (1周)

```sql
-- 导出智能气功相关数据
SELECT * FROM books
WHERE category LIKE '%ZNQG%'
   OR category LIKE '%智能%'
   OR category LIKE '%Zhineng%';
```

**清洗任务**:
1. 标准化 category 名称 (去除 "百度云9080\" 等前缀)
2. 提取 timeline 信息 (从 category 和 filename)
3. 识别 file_type (从 extension)

### 4.2 Phase 2: 批量打标 (2周)

```python
# 复用现有打标引擎
from backend.services.qigong import QigongContentParser

parser = QigongContentParser()
for book in sys_books:
    dims = parser.parse_from_title_content(
        book['filename'],
        book.get('content', '')
    )
    # 补充 Sys_books 特有信息
    if '1988' in book['category']:
        dims['timeline'] = '石家庄时期 (1989-1991)'
    # ...
```

### 4.3 Phase 3: 数据导入 (1周)

```sql
-- 导入到 documents 表
INSERT INTO documents (title, content, category, qigong_dims)
VALUES (
    sys_book['filename'],
    sys_book.get('content', ''),
    '气功',
    sys_book_dims::jsonb
);
```

---

## 五、预期效果

### 5.1 数据增量

| 来源 | 记录数 | V4 可应用数 |
|------|--------|-------------|
| 当前 documents 表 | 13,875 | 13,875 (100%) |
| Sys_books.db ZNQG | ~150,000 | ~50,000 (33%) |
| **合计** | **~163,875** | **~63,875** |

### 5.2 数据质量提升

| 维度 | 当前 | 导入后 |
|------|------|--------|
| timeline 覆盖率 | 0% | ~40% (有时间戳数据) |
| teaching_level 覆盖率 | 31% | ~60% (有明确分类) |
| 音频资料 | 2,794 | ~4,000 (新增 1,200+) |
| 视频资料 | 1,769 | ~1,900 (新增 100+) |

---

## 六、风险与挑战

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重复数据 | 文档去重问题 | 基于 filename + size 建立唯一键 |
| 内容缺失 | Sys_books 无 content 字段 | 仅基于 filename 打标，质量略低 |
| 类别混乱 | 前缀不一致 (百度云9080\ 等) | 预处理标准化 |
| 数据量巨大 | 15 万条处理耗时 | 分批处理，优先高价值数据 |

---

## 七、结论

### 7.1 可行性评估: ✅ 高度可行

**理由**:
1. **数据丰富**: Sys_books.db 包含 15 万条智能气功相关记录
2. **结构清晰**: category/filename 包含明确的维度信息
3. **时间覆盖**: 1987-2000 年代完整时间线
4. **类型完整**: 音频、视频、文本资料齐全

### 7.2 推荐执行顺序

```
1. 导出 ZNQG 音频资料 (~1,500 条) → 高价值，易处理
2. 导出 ZNQG 视频资料 (~100 条) → 补充视频库
3. 导出 ZNQG 主分类 (~15 万条) → 批量处理，分批导入
```

### 7.3 预期收益

- **数据量**: 13,875 → 63,875 (+360%)
- **时间覆盖**: 无 → 1987-2000 完整时间线
- **媒体资料**: 音频 +1,200，视频 +100
- **检索能力**: 新增按时间线、活动类型检索

---

## 八、扩展性分析：医学类资料

### 8.1 医学相关数据

Sys_books.db 包含以下医学相关类别：
- `百度云9080\中医学习与工作`: 63,995
- `古籍`: 335,437 (包含中医古籍)
- `哲社`: 125,849 (包含医学哲学)

### 8.2 V4 适配方案 (医学版)

| 气功 V4 | 医学 V4' | 说明 |
|---------|----------|------|
| theory_system | medical_system | 中医/西医/中西医结合 |
| content_topic | medical_topic | 诊断/治疗/方剂/经络 |
| gongfa_method | treatment_method | 针灸/推拿/方药/气功 |
| teaching_level | difficulty_level | 入门/临床/专科 |
| discipline | medical_discipline | 内科/外科/针灸/推拿 |

### 8.3 实施

可以基于 V4 框架创建医学维度体系：
- 复用数据结构 (JSONB + GIN 索引)
- 复用打标引擎 (修改关键词规则)
- 复用受控词表 (新增医学子项)

---

**执行人**: Claude AI
**下一步**: 开始 Phase 1 数据导出与清洗
