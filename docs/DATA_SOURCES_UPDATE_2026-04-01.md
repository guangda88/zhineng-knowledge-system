# 灵知系统数据源配置更新报告

**更新日期**: 2026-04-01
**状态**: ✅ 已完成

---

## 更新概述

根据用户反馈，对灵知系统的书籍搜索数据源进行了全面重构和扩展，实现了更合理的分类体系和更丰富的数据源覆盖。

---

## 主要变更

### 1. 分类体系修正

#### 修正前的问题
- `guji` (典津) 和 `ctext` (中国哲学书电子化计划) 错误归类为 **儒家**
- `cbeta` 错误归类为 **中医**
- 分类体系不完整，缺少道家、武术、科学等类别

#### 修正后的分类体系

| 分类 | 说明 | 数据源数量 |
|------|------|-----------|
| **气功** | 灵知系统本地教材（智能气功等） | 1 |
| **佛家** | 佛教典籍和数字化平台 | 5 |
| **哲学** | 先秦诸子百家及中国哲学典籍 | 3 |
| **道家** | 道教典籍和道家思想文献 | 2 |
| **中医** | 中医古籍和医学典籍 | 3 |
| **武术** | 传统武术拳谱和典籍（待完善） | 1 |
| **科学** | 古代科技典籍（待完善） | 1 |

### 2. 新增数据源

#### 佛家数据源 (5个)

| 代码 | 名称 | URL | 描述 |
|------|------|-----|------|
| **cbeta** | CBETA大正藏 | https://cbetaonline.dila.edu.tw | 大正藏电子佛典 |
| **fojin** | FoJin佛典平台 | https://github.com/xr843/fojin | 聚合503个数据源，9200+文本，17800+卷 |
| **sat** | SAT大正藏 | https://suttacentral.net | Taisho Tripitaka 数据库 |
| **84000** | 84000译经会 | https://84000.co | 藏文大藏经翻译项目 |
| **bdrc** | 佛教数字资源中心 | https://library.bdrc.io | 藏文手稿IIIF影像 |

#### 道家数据源 (2个)

| 代码 | 名称 | URL | 描述 |
|------|------|-----|------|
| **homeinmists** | 白云深处人家 | http://www.homeinmists.com | 中华传统道文化数字图书馆，包含道藏5485卷 |
| **daozang** | 道藏 | - | 道教典籍总集，5485卷 |

#### 中医数据源 (3个)

| 代码 | 名称 | URL | 描述 |
|------|------|-----|------|
| **tcm_ancient** | 中医古籍数据集 | https://www.heywhale.com | 约700项中医药古籍文本，先秦至清末 |
| **huangdi** | 黄帝模型 | https://github.com/Zlasejd/HuangDI | 基于LLaMA的中医古籍知识模型 |
| **zhongyi_classics** | 中医经典 | - | 伤寒论、黄帝内经等经典著作 |

#### 武术数据源 (1个)

| 代码 | 名称 | 描述 |
|------|------|------|
| **wushu_local** | 武术典籍库 | 太极拳、形意拳、八卦掌、少林拳等经典拳谱 |

#### 科学数据源 (1个)

| 代码 | 名称 | 描述 |
|------|------|------|
| **science_ancient** | 古代科技典籍 | 梦溪笔谈、九章算术、齐民要术等科技著作 |

### 3. 修正的分类

| 数据源 | 修正前分类 | 修正后分类 | 原因 |
|--------|-----------|-----------|------|
| **ctext** | 儒家 | 哲学 | 涵盖先秦诸子百家，不限于儒家 |
| **guji** | 儒家 | 哲学 | 全球汉籍集成，包含多学派典籍 |
| **cbeta** | 中医 | 佛家 | 佛教大藏经，非医学典籍 |
| **local** | 其他 | 气功 | 明确为气功教材数据 |

### 4. 数据源能力配置

每个数据源都配置了以下能力标记：

| 能力 | 说明 | 示例数据源 |
|------|------|-----------|
| `supports_search` | 支持元数据搜索 | 大部分数据源 |
| `supports_fulltext` | 支持全文检索 | fojin, ctext, tcm_ancient |
| `has_local_fulltext` | 有本地全文数据 | local, daozang, wushu_local |
| `has_remote_fulltext` | 有远程全文API | fojin, cbeta, ctext |
| `supports_api` | 提供API接口 | 大部分API类型数据源 |

---

## 文件变更

### 修改的文件

1. **scripts/init_book_search_db.sql**
   - 更新数据源插入语句（第167-173行）
   - 更新表结构注释（category字段）
   - 添加base_url字段支持

2. **scripts/init_book_search_db_fixed.sql**
   - 同步更新数据源配置
   - 同步更新表结构注释

### SQL变更内容

```sql
-- 添加base_url字段支持
INSERT INTO data_sources (code, name_zh, name_en, base_url, description, ...)

-- 分类更新
category VARCHAR(50),  -- 气功/佛家/哲学/道家/中医/武术/科学/其他
```

---

## 数据源统计

| 分类 | API类型 | Local类型 | 总计 |
|------|---------|-----------|------|
| 气功 | 0 | 1 | 1 |
| 佛家 | 5 | 0 | 5 |
| 哲学 | 3 | 0 | 3 |
| 道家 | 1 | 1 | 2 |
| 中医 | 2 | 1 | 3 |
| 武术 | 0 | 1 | 1 |
| 科学 | 0 | 1 | 1 |
| **总计** | **11** | **5** | **16** |

---

## 待完善项

### 高优先级

1. **武术数据源**
   - 当前仅有框架，需要实际数据
   - 建议收录：太极拳、形意拳、八卦掌、少林拳等经典拳谱
   - 来源：纸质书籍数字化

2. **科学数据源**
   - 当前仅有框架，需要实际数据
   - 建议收录：《梦溪笔谈》、《九章算术》、《齐民要术》等

### 中优先级

3. **API集成实现**
   - 当前数据源已配置，但外部API实际调用功能需要实现
   - 需要开发针对每个数据源的导入器

4. **数据质量验证**
   - 验证各数据源的可用性
   - 测试API连接

### 低优先级

5. **数据源扩展**
   - 继续寻找更多专业数据源
   - 如：藏传佛教、南传佛教等其他分支

---

## 使用说明

### 应用更新

```bash
# 方式1：重新初始化数据库
psql -U your_user -d your_database -f scripts/init_book_search_db.sql

# 方式2：仅更新数据源
psql -U your_user -d your_database
```

```sql
-- 在psql中执行
BEGIN;

-- 删除旧数据源（保留已有的书籍关联）
DELETE FROM data_sources WHERE code IN (
    'local', 'guji', 'cbeta', 'ctext', 'zhonghua'
);

-- 插入新数据源
\i scripts/init_book_search_db.sql

COMMIT;
```

### 验证更新

```sql
-- 查看所有数据源
SELECT code, name_zh, category, access_type, sort_order
FROM data_sources
ORDER BY sort_order;

-- 按分类统计
SELECT category, COUNT(*) as count
FROM data_sources
GROUP BY category
ORDER BY category;
```

---

## 后续工作

1. ✅ 数据源配置更新 - **已完成**
2. ⏳ API导入器开发 - **待开始**
3. ⏳ 数据质量验证 - **待开始**
4. ⏳ 武术/科学数据收集 - **待开始**

---

## 参考资源

### 数据源官方网站

- **FoJin**: https://github.com/xr843/fojin
- **CTEXT**: https://ctext.org
- **CBETA**: https://cbetaonline.dila.edu.tw
- **白云深处人家**: http://www.homeinmists.com

### 相关文档

- `BOOK_SEARCH_INTEGRATION_STATUS.md` - 书籍搜索功能集成状态
- `BOOK_SEARCH_MVP_COMPLETED.md` - MVP完成报告
- `backend/models/source.py` - 数据源模型定义
- `backend/models/book.py` - 书籍模型定义

---

**更新完成**: 2026-04-01
**文档版本**: v1.0
**更新者**: Claude (AI Assistant)
