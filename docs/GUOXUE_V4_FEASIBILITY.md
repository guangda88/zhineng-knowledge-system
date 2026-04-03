# guoxue.db V4 维度应用可行性分析

**数据源**: `/lingzhi_ubuntu/database/guoxue.db`
**数据库大小**: 6.7 GB
**评估日期**: 2026-04-02

---

## 一、数据概览

### 1.1 数据结构

```
guoxue.db
├── wx (主表, 空)
├── wx200 (105,214 条)
├── wx1022, wx223, wx517... (多个微信文章表)
├── wx19540, wx22313... (数百个表)
└── 总记录数: 估计 100 万+ 条
```

### 1.2 内容样本分析

| 类型 | 示例 | 来源 |
|------|------|------|
| 禅宗语录 | "(幽州第二世住)僧问。如何出得三界..." | 禅宗典籍 |
| 风水文献 | "本地姜地理峦头诀" | 民间文献 |
| 历史文献 | "林则徐附奏东西各洋越窜夷船严行惩办片" | 历史档案 |
| 诗词作品 | "吕卿豪杰士，家世两申公..." | 古诗词 |
| 笔记小说 | "旦扮莺引旦俫扮红上...《红楼梦》相关" | 古典小说 |
| 方志史料 | "天童寺建于晋时..." | 地方志 |

---

## 二、V4 维度适配方案 (国学版 V4-GX)

### 2.1 气功 V4 → 国学 V4 映射

| 气功 V4 | 国学 V4-GX | 说明 |
|---------|------------|------|
| theory_system | discipline_type | 经史子集分类 |
| content_topic | content_category | 儒家/佛家/道家/史部 |
| gongfa_method | sub_discipline | 诗经/史记/论语等具体经典 |
| teaching_level | difficulty_level | 入门/中级/高级 |
| timeline | dynasty | 唐/宋/元/明/清 |
| speaker | author_or_source | 作者/来源 |
| media_format | document_type | 文本/碑刻/手抄 |

### 2.2 国学专属维度

| 维度 | 代码 | 说明 | 示例值 |
|------|------|------|--------|
| **经史分类** | jingshi_class | 四部分类法 | 经部/史部/子部/集部 |
| **朝代** | dynasty | 创作年代 | 唐/宋/元/明/清 |
| **文体** | genre | 文学体裁 | 诗/词/赋/散文/小说 |
| **主题** | theme | 内容主题 | 禅修/风水/医学/军事 |
| **版本** | edition | 版本类型 | 刻本/抄本/印本 |
| **作者** | author | 作者或编者 | 李白/杜甫/佚名 |

---

## 三、数据提取规则

### 3.1 从 body 内容提取

```python
def parse_guoxue_dimensions(body, table_name):
    dims = {
        'discipline_type': '子部',  # 默认
        'content_category': [],
        'dynasty': '清代',  # 默认
        'genre': '散文',
        'theme': [],
        'document_type': '文本',
    }

    # 提取朝代
    if '唐' in body or '唐代' in body:
        dims['dynasty'] = '唐代'
    elif '宋' in body or '宋代' in body:
        dims['dynasty'] = '宋代'
    elif '明' in body or '明代' in body:
        dims['dynasty'] = '明代'

    # 提取主题
    if '禅' in body or '僧' in body:
        dims['content_category'].append('佛家')
        dims['theme'].append('禅宗')
    elif '风水' in body or '堪舆' in body:
        dims['content_category'].append('子部')
        dims['theme'].append('风水')
    elif '诗' in body and not body.count('诗') > 2:
        dims['genre'] = '诗歌'

    return dims
```

### 3.2 从表名提取

| 表名模式 | 领域 | 说明 |
|---------|------|------|
| wx200 | 综合 | 综合国学 |
| wx19540 | 待分析 | 需要采样 |
| wx22313 | 待分析 | 需要采样 |
| wx517 | 待分析 | 需要采样 |

---

## 四、实施建议

### 4.1 Phase 1: 数据探索 (1周)

```sql
-- 采样分析各表内容
SELECT table_name, COUNT(*) as count
FROM (
    SELECT 'wx200' as table_name, COUNT(*) FROM wx200
    UNION ALL
    SELECT 'wx1022', COUNT(*) FROM wx1022
    UNION ALL
    SELECT 'wx223', COUNT(*) FROM wx223
    LIMIT 20
) t
ORDER BY count DESC;
```

**任务**:
1. 统计各表记录数和内容类型
2. 采样分析 20 个表的内容特征
3. 建立表名→内容类型映射

### 4.2 Phase 2: 维度设计 (1周)

```sql
-- 创建国学受控词表
CREATE TABLE guoxue_dimension_vocab (
    dimension_code VARCHAR(50) PRIMARY KEY,
    dimension_name VARCHAR(100),
    category VARCHAR(10),  -- J/S/Z/J (经史子集)
    sub_items JSONB
);
```

**核心维度**:
1. `jingshi_class`: 经部/史部/子部/集部
2. `dynasty`: 先秦/汉/唐/宋/元/明/清
3. `genre`: 诗/词/赋/散文/小说/戏曲
4. `theme`: 禅修/风水/医学/军事/经世

### 4.3 Phase 3: 批量打标 (2周)

```python
# 复用 V4 框架
class GuoxueContentParser:
    def parse_from_body(self, body, table_name):
        # 检测朝代关键词
        # 检测主题关键词
        # 检测文体特征
        # 返回国学 V4 维度
```

---

## 五、预期效果

| 指标 | 当前 (仅气功) | 导入国学后 |
|------|---------------|-----------|
| documents 表记录 | 13,875 | ~150,000 |
| 覆盖领域 | 气功 | 气功 + 国学 |
| 维度体系 | V4 (气功专用) | V4-GX (国学版) |
| 检索能力 | 气功检索 | 跨领域检索 |

---

## 六、与其他数据源对比

| 数据源 | 记录数 | 领域 | V4 适配 |
|--------|--------|------|---------|
| documents (现有) | 13,875 | 气功 | V4 (气功版) ✅ |
| Sys_books.db | 150,000 | 气功为主 | V4 (气功版) ✅ |
| guoxue.db | 1,000,000+ | 国学 | V4-GX (国学版) ✅ |
| 其他 (医学等) | 待评估 | 医学/中医 | V4-Med (医学版) ✅ |

---

## 七、结论

### 7.1 可行性评估: ✅ 高度可行

**理由**:
1. **数据量充足**: 100 万+ 条国学数据
2. **结构清晰**: 文本内容可直接分析
3. **分类标准**: 四部分类法成熟，可映射到 V4
4. **框架复用**: V4 JSONB 架构完全适用

### 7.2 实施建议

```
优先级 P0 (立即执行):
  ├── 采样分析 wx200 表 (10万+ 条)
  ├── 设计国学版受控词表
  └── 实现国学内容解析器

优先级 P1 (本月完成):
  ├── 批量打标 wx200 表
  ├── 建立国学检索接口
  └── 生成国学数据报告

优先级 P2 (下月执行):
  ├── 扩展到其他表 (wx1022, wx223...)
  ├── 建立跨领域关联检索
  └── 实现国学知识图谱
```

---

**评估人**: Claude AI
**下一步**: 开始 Phase 1 数据探索
