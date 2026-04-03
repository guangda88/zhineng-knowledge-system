# 数据资产分析与利用策略

> 生成日期: 2026-03-31
> 状态: 战略分析文档

---

## 一、现状：三个数据孤岛，零内容

### 1.1 数据资产全景

| 数据源 | 规模 | 结构化程度 | 内容深度 | 当前利用率 |
|--------|------|-----------|---------|-----------|
| `Sys_books.db` | 302 万条 | ⭐⭐⭐⭐⭐ | 文件名+路径+分类 | **0%** |
| `data.db` (Openlist) | 90.7 万条 | ⭐⭐ | 文件路径+大小 | **12%** (仅路径导入) |
| `PostgreSQL documents` | ~13,875 条 | ⭐⭐⭐ | 实际文本(85条新导入) | **~15%** (85条有真实内容) |
| 本地教科书 | 168 个文件 | ⭐⭐⭐ | 实际文本 | **100%** (已全部导入) |
| `guoxue.db` | 13万+ 书籍 | ⭐⭐⭐⭐ | — | **已清理** (文件不存在，配置已移除) |

### 1.2 核心问题 (更新)

**Phase 0 实施后进展**: documents 表已有 ~85 条真实文本内容 (来自本地TXT和textbooks.db)。sys_books 表已导入 3,024,428 条结构化书目记录。

**但仍有 ~13,790 条 documents 记录仅含元数据/路径，缺少实际文本内容。** 内容提取 (Phase 2) 是下一阶段重点。

| 类别 | 总数 | 来源:路径 | IMA来源 | 文件名列表 | 书名索引 | 实际内容(>500字) |
|------|------|----------|---------|-----------|---------|-----------------|
| 中医 | 68,749 | 0 | 3,607 | 62,168 | 2,973 | **0** |
| 儒家 | 20,610 | 0 | 1,039 | 5,172 | 14,398 | **0** |
| 气功 | 13,564 | 11,055 | 144 | 2,361 | 0 | **0** |

系统本质上是一个**空壳搜索引擎** — 拥有文件目录索引，但没有任何可检索的文本内容。

---

## 二、Sys_books.db — 被忽视的金矿

### 2.1 数据概览

这是价值最高的数据资产，目前完全未被使用。

```
文件大小: 2.4 GB
总记录:   3,024,428 条 (2,906,851 文件 + 117,577 目录)
数据来源: 4 个人收集 (Z-disk: 242万, Ammiao: 52万, sunbo: 5.6万, yangxl: 2.1万)
```

### 2.2 丰富的分类体系

| 分类 | 数量 | 说明 |
|------|------|------|
| 古籍 | 335,437 | 历代古籍扫描件 |
| 百度云9080\电脑备份 | 465,637 | 个人资料备份 |
| 115\国学大师 | 165,456 | 国学大师离线版资源 |
| 哲社 | 125,849 | 哲学社会科学图书 |
| 中医学习与工作 | 63,995 | 中医专业资料 |
| 书画学习 | 50,056 | 书法绘画 |
| ZNQG (智能气功) | 51,823 | 仅顶级分类，含子类共 102,005 |
| 科学研究 | 32,523 | 科研文献 |
| 传统文化学习 | 26,508 | 传统文化 |
| 智能 (智能气功) | 25,946 | 仅顶级分类，含子类共 26,000 |
| 辞书 | 24,399 | 工具书/字典 |
| 115\Zhineng | 21,954 | 智能气功专题 |
| 115\国学大师 | 165,456 | 国学大师离线版 |
| 古籍 | 335,437 | 历代古籍 |
| 四库全书 | 9,232 | 四库系列 |
| 哲学 | 9,636 | 含儒道佛医各派 |
| 历史 | 16,890 | 含山海经等 |
| 中医 (全部) | 82,473 | 含子分类中医 |

### 2.3 文件类型分布

| 类型 | 数量 | 说明 |
|------|------|------|
| (无扩展名) | 1,239,326 | 可能是古籍扫描页面或目录 |
| jpg | 301,650 | 古籍页面扫描 |
| **pdf** | **214,200** | **可提取文本的PDF** |
| djvu | 170,797 | 古籍常用格式 |
| **txt** | **133,403** | **直接可用的文本** |
| mp3 | 50,185 | 音频(可ASR转录) |
| png | 36,864 | 古籍页面扫描 |
| doc | 32,633 | Word文档(可提取) |
| mp4 | 23,341 | 视频(可ASR转录) |

### 2.4 深层分类结构

Sys_books.db 的 path 字段包含了极丰富的层级分类信息：

```
01哲学\1.中国哲学\4.医家\1.黄帝内经\灵枢\...
01哲学\1.中国哲学\5.道家\0.单行本道经\1.先秦\1.老子\...
01哲学\1.中国哲学\6.佛家\1.乾隆大藏经\...
01哲学\1.中国哲学\7.儒家\9.元朝\吴澄\...
05文学\1.中华文学\10.宋朝\太平御览\...
06历史学\1.中华历史\1.先秦\山海经\...
四库全书\景印文渊阁四库全书pdf\1.经部\...
古籍\...
115\国学大师\...
115\Zhineng\...
百度云2362\ZNQG新整理20251212\...
```

这不仅仅是一个文件列表 — **它是一个完整的中国传统文化知识分类体系**。

---

## 三、data.db (Openlist) — 云端文件索引

### 3.1 数据概览

```
文件大小:   296 MB
**总大小:   ~17.4 TB** (报告初版误报为 19TB，实际可统计总量 17,433 GB，少数文件 size=0 未计入)
**总条目:   907,539**
**实际文件:  825,290** (报告初版误报为 ~730,000)
**目录:      82,249**
```

### 3.2 连接的云盘

| 云盘 | 挂载路径 | 说明 |
|------|---------|------|
| 百度云9080 | /百度云9080 | 主要资料盘 |
| 百度云2362 | /百度云2362 | 第二资料盘 |
| 阿里云盘 | /阿里云盘 | 补充资源 |
| 115网盘 | /115 | 国学大师/Zhineng |
| 夸克 | /夸克 | 补充资源 |
| 豆包 | /豆包 | 补充资源 |
| 一刻相册 | /一刻相册 | 图片 |

### 3.3 关键内容区域

| 区域 | 文件数 | 数据量 | 价值 |
|------|--------|--------|------|
| ZNQG (智能气功) | 48,795 | **3.3 TB** | 核心气功资料 |
| 中医学习与工作 | 61,651 | **2.0 TB** | 中医专业文献 |
| 传统文化 | 25,719 | 1.5 TB | 传统文化资源 |
| 其他 | 663,295 | 9.9 TB | 混合内容 |

### 3.4 文件类型与数据量

| 类型 | 数量 | 数据量 | 可提取性 |
|------|------|--------|---------|
| pdf | 41,383 | **1,181 GB** | 文本可提取 |
| mp3 | 26,642 | 418 GB | ASR可转录 |
| mp4 | 19,937 | **4,928 GB** | ASR可转录 |
| doc/docx | 27,314 | 8.7 GB | 文本可提取 |
| txt | 26,925 | 1.8 GB | **直接可用** |
| image | 191,268 | 387 GB | 需OCR |
| wav | 1,870 | 428 GB | ASR可转录 |

---

## 四、数据关系分析

### 4.1 三个数据源的关系

```
Sys_books.db (302万)           data.db (91万)          PostgreSQL (10万)
┌───────────────┐          ┌───────────────┐        ┌───────────────┐
│ 本地磁盘索引    │          │ 云端文件索引    │        │ 已导入元数据    │
│ Z: K: E: G:盘  │          │ 百度/阿里/115  │        │ 气功/中医/儒家  │
│               │          │               │        │               │
│ category字段   │◄──重叠──►│ x_search_nodes │◄─已导入─►│ documents表   │
│ 01哲学\...     │          │ parent/name   │        │ title/content │
│ 古籍/中医/...  │          │               │        │               │
│               │          │               │        │               │
│ 214K PDFs     │          │ 41K PDFs      │        │ 0 实际内容     │
│ 133K TXTs     │          │ 27K TXTs      │        │               │
│ 50K MP3s      │          │ 27K MP3s      │        │               │
└───────────────┘          └───────────────┘        └───────────────┘
      │                          │                         │
      │    都指向云盘/本地上的实际文件  │                         │
      └──────────────┬────────────┘                         │
                     ▼                                      │
              实际文件内容                                    │
              (PDF/TXT/MP3/MP4/DJVU...)                     │
              目前完全未被提取                                 │
```

### 4.2 数据重叠与互补

| 维度 | Sys_books.db | data.db | PostgreSQL |
|------|-------------|---------|-----------|
| 智能气功 | ZNQG=102K + 智能=26K + 115/Zhineng=22K = **~128K** (去重后) | 49K(ZNQG) | 14K |
| 中医 | 82K(全部含子类) | 62K | 69K |
| 古籍 | 335K + 165K(115/国学大师) | — | 14K(书名索引) |
| 分类体系 | **完整学科分类** | 路径层级 | 扁平3类 |
| 元数据质量 | category/author/year | parent/size | title/path |
| 内容深度 | 文件名级别 | 文件名级别 | 路径级别 |

**关键发现**：Sys_books.db 和 data.db 有大量重叠文件（同一文件在不同索引中），但 Sys_books.db 有更好的分类信息，data.db 有更准确的云端路径。

---

## 五、分阶段利用策略

### Phase 0: 数据对账 (1-2天)

**目标**：建立三源数据映射，明确去重策略

```sql
-- 新建 books 表 (从 Sys_books.db 导入)
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,          -- 'Z-disk', 'Ammiao', 'sunbo', 'yangxl'
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    category TEXT,
    author TEXT,
    year TEXT,
    extension TEXT,
    file_type TEXT,                -- 'file' or 'directory'
    size BIGINT,
    created_date TIMESTAMP,
    publisher TEXT,
    book_number TEXT,
    
    -- 增强字段 (后续填充)
    domain TEXT,                   -- '气功', '中医', '儒家', '古籍', '其他'
    subcategory TEXT,              -- 从 path 层级提取
    content_extracted BOOLEAN DEFAULT FALSE,
    content_id INTEGER,            -- 关联到 documents 表
    cloud_path TEXT,               -- 对应的云盘路径
    
    -- 全文搜索
    tsv_search TSVECTOR
);

CREATE INDEX idx_books_domain ON books(domain);
CREATE INDEX idx_books_category ON books(category);
CREATE INDEX idx_books_extension ON books(extension);
```

**关键任务**：
1. 导入 Sys_books.db → PostgreSQL `books` 表
2. 从 path 层级提取学科分类 (domain/subcategory)
3. 与 data.db 进行路径匹配，关联云端路径
4. 与现有 documents 表进行 title 去重

### Phase 1: 结构化书目服务 (3-5天)

**目标**：立即提供价值 — 书目搜索引擎

Sys_books.db 即使不提取文件内容，其 302 万条结构化记录本身就是一个巨大的价值：

**1.1 丰富的分类 API**
```
GET /api/v1/books/search?q=黄帝内经&domain=中医
GET /api/v1/books/categories                    -- 返回完整分类树
GET /api/v1/books/stats                         -- 统计信息
GET /api/v1/books/{id}                          -- 书目详情
GET /api/v1/books/recommend?domain=气功          -- 推荐
```

**1.2 从 path 提取的知识分类**

Sys_books.db 的 category + path 组合天然形成一个知识分类体系：

```
01哲学/
  ├── 1.中国哲学/
  │   ├── 4.医家/          → 中医
  │   ├── 5.道家/          → 道家
  │   ├── 6.佛家/          → 佛家
  │   └── 7.儒家/          → 儒家
  ├── 2.西方哲学/
  └── ...
05文学/
06历史学/
四库全书/                      → 古籍(经/史/子/集)
115\国学大师\                  → 国学
115\Zhineng\                   → 智能气功
ZNQG音频\                      → 智能气功(音频)
ZNQG视频\                      → 智能气功(视频)
古籍\                          → 古籍
辞书\                          → 工具书
中医\                          → 中医
```

**1.3 价值**：
- 302 万册中国传统文化图书的结构化索引
- 哲学、医学、文学、历史、佛学、道学的完整学科覆盖
- 这是任何单一数据库都无法比拟的广度

### Phase 2: 内容提取管道 (2-4周)

**目标**：从文件中提取实际文本内容

按优先级排序的提取策略：

**P0: 本地已有内容 (立即可用)**
- 189 个 .txt 教科书文件 → 直接导入
- 10 个已处理的 JSON → 导入到 documents
- `textbooks.db` (496MB) → 解析结构化数据

**P1: 可直接提取的文本 (1周)**
- 133K TXT 文件 → 直接读取导入
- 214K PDF → PyMuPDF/pdfplumber 提取
- 32K DOC/DOCX → python-docx 提取
- 170K DJVU → djvuLibre 提取

**P2: 需要转录的多媒体 (2-3周)**
- 50K MP3 + 1,870 WAV → FunASR/SenseVoice 批量转录
- 23K MP4 → 提取音轨 + ASR 转录

**P3: 需要 OCR 的扫描件 (长期)**
- 301K JPG + 37K PNG → PaddleOCR/Tesseract
- 90K PDG → 转换后 OCR
- 1.2M 无扩展名文件 → 需要逐个识别

### Phase 3: 知识融合与图谱 (4-8周)

**目标**：构建统一的知识图谱

```
书目元数据 (Sys_books.db)
    │
    ├── 内容全文 (Phase 2 提取)
    │     └── 向量化 → RAG 检索
    │
    ├── 分类体系 (path 层级)
    │     └── 知识图谱节点
    │
    ├── 维度标注 (V4 系统)
    │     └── qigong_dims JSONB
    │
    └── 跨域关联
          ├── 气功 ↔ 中医 (经络/气血理论)
          ├── 中医 ↔ 儒家 (身体哲学)
          └── 古籍 ↔ 现代研究 (注释/引用)
```

### Phase 4: 智能问答增强 (持续)

**目标**：基于真实内容提供高质量问答

当前系统的 RAG 管道是完整的 (BGE embedding + pgvector + DeepSeek LLM)，
缺的只是**真实内容**。一旦 Phase 2 完成：

1. 对提取的文本进行 BGE embedding
2. 导入 documents 表的 content 字段
3. 现有的 HybridRetriever (向量 + BM25) 立即可用
4. 维度标注系统提供精准过滤
5. DeepSeek 生成高质量回答

---

## 六、优先级排序与投入产出比

| 优先级 | 任务 | 投入 | 产出 | ROI |
|--------|------|------|------|-----|
| **P0** | Sys_books.db → books 表导入 | 1天 | 302万条书目立即可用 | ⭐⭐⭐⭐⭐ |
| **P0** | 本地189个TXT导入 | 0.5天 | 首批真实内容 | ⭐⭐⭐⭐⭐ |
| **P1** | 书目搜索API | 2天 | 完整书目搜索引擎 | ⭐⭐⭐⭐ |
| **P1** | data.db ↔ Sys_books.db 对账 | 2天 | 去重 + 云端路径关联 | ⭐⭐⭐⭐ |
| **P2** | PDF批量提取 | 3天 | 214K文档内容 | ⭐⭐⭐ |
| **P2** | 音频ASR批量转录 | 1周 | 50K音频转录 | ⭐⭐⭐ |
| **P3** | DJVU/PDG古籍OCR | 2周 | 古籍数字化 | ⭐⭐ |
| **P3** | 知识图谱构建 | 4周 | 跨域知识关联 | ⭐⭐ |

---

## 七、技术架构建议

### 7.1 数据模型

```sql
-- 书目主表 (从 Sys_books.db 导入)
books (302万条)
├── id, source, path, filename, category
├── author, year, extension, size
├── domain, subcategory           -- 增强字段
└── cloud_path, content_extracted -- 关联字段

-- 文档内容表 (提取后)
documents (保留现有, 逐步填充真实内容)
├── id, title, content            -- content 从空路径→真实文本
├── category, tags
├── embedding                     -- BGE 向量
├── qigong_dims                   -- 维度标注 JSONB
└── book_id                       -- 关联到 books 表

-- 知识图谱 (Phase 3)
knowledge_graph
├── concepts (概念节点)
├── relations (关系边)
└── book_concepts (书目-概念关联)
```

### 7.2 关键设计决策

| 决策点 | 建议 | 理由 |
|--------|------|------|
| books 与 documents 的关系 | 1:1 (通过 book_id) | 一本书对应一条文档 |
| 先导入哪个 | **Sys_books.db 优先** | 元数据价值立即可用 |
| 内容提取顺序 | TXT > PDF > DOC > MP3 > JPG | 投入产出比递减 |
| 维度标注时机 | 在内容提取之后 | 需要内容才能做NLP标注 |
| guoxue.db | 放弃，清理残留代码 | 文件不存在，服务已删 |

---

## 八、实施进度

> 最后更新: 2026-04-02

### Phase 0: 数据对账 — ✅ 基本完成

| 任务 | 状态 | 结果 |
|------|------|------|
| P0-1: Sys_books.db → PostgreSQL `sys_books` 表 | ✅ 完成 | 3,024,428 行，5 B-tree + 2 GIN trigram 全部就绪 |
| P0-2: 从 path 提取 domain 分类 | ✅ 完成 | 中医/道家/佛家/儒家/气功/古籍等分类自动提取 |
| P0-3: 本地 TXT 导入 documents.content | ✅ 完成 | 168个文件(159已有 + 3新增 + 6空文件)，82条textbooks.db记录 |
| P0-4: guoxue.db 残留配置清理 | ✅ 完成 | 移除 LingZhiConfig 中 guoxue.db 引用 |

### Phase 1: 结构化书目服务 — ✅ 完成

| 任务 | 状态 | 结果 |
|------|------|------|
| P1-1: `/api/v1/sysbooks/` REST API | ✅ 完成 | search/stats/domains/{id} 四个端点，prefix 已修正 |
| P1-2: API 功能测试 | ✅ 通过 | 8/8 unit + GIN trigram 模糊搜索验证通过 |
| P1-3: data.db ↔ Sys_books.db 对账 | ✅ 完成 | 1,116,600/3,024,428 匹配 (36.9%)，1,907,828 未匹配，cloud_path 已填充 |

### Phase 2: 内容提取管道 — ✅ 基础设施完成

| 任务 | 状态 | 结果 |
|------|------|------|
| P2-1: DB 迁移 (新增表 + 列) | ✅ 完成 | `sys_book_contents`, `extraction_tasks`, `kg_entities`, `kg_relations` 表 + `qigong_dims`, `cloud_path`, `cross_ref_status`, `extraction_status` 列 |
| P2-2: 内容提取服务 | ✅ 完成 | `BatchExtractionService` — 支持 TXT/PDF/DOC/DJVU/EPUB 批量提取，跟踪进度 |
| P2-3: 维度标注服务 (sys_books) | ✅ 完成 | `SysBooksDimensionTagger` — V4.0 17维度系统，使用 `QigongPathParser` + `QigongContentParser` |
| P2-4: 管道 API | ✅ 完成 | `/api/v1/pipeline/` — stats/extract/tag/kg-build/cross-ref/tasks 端点 |
| P2-5: API 测试 | ✅ 通过 | 12/12 pipeline API tests passed |
| P2-6: 批量维度标注执行 | 🔄 部分完成 | 5,000/3,024,428 已标注 (0.2%)，首次50万批量因 guji 导入竞争超时，待重试 |

### Phase 3: 知识图谱 — ✅ 基础设施完成

| 任务 | 状态 | 结果 |
|------|------|------|
| P3-1: 知识图谱构建器 | ✅ 完成 | `KnowledgeGraphBuilder` — 实体提取 (功法/理论/人物/文献/地点/术语) + 共现关系 + 路径层级 + 领域关联 |
| P3-2: 知识图谱查询 API | ✅ 完成 | `/api/v1/pipeline/kg/` — stats/entities/graph 端点 |
| P3-3: 批量 KG 构建 | 🔄 待执行 | 游标分页优化已部署，待批量运行 |

### 关键技术决策 (Phase 2/3)

1. **asyncpg JSONB 序列化**: asyncpg 要求 JSONB 列使用 `json.dumps()` 而非直接传 Python dict
2. **游标分页**: 3M 行表使用 `WHERE id > last_id ORDER BY id LIMIT N` 替代 OFFSET，避免后期分页 O(N²) 性能问题
3. **pg_class 估算**: `SELECT reltuples::bigint FROM pg_class WHERE relname = 'sys_books'` 替代 `COUNT(*)` 实现秒级统计
4. **后台任务模式**: 长 running 操作 (标注/KG构建/对账) 通过 FastAPI BackgroundTasks 异步执行，进度记录在 `extraction_tasks` 表
5. **部分 GIN 索引**: `idx_sys_books_qigong_dims` 使用 `WHERE qigong_dims <> '{}'::jsonb` 减少索引体积

### 测试状态

```
pytest tests/ — 471 passed, 34 failed (all pre-existing), 1 skipped
sysbooks API: 8/8 passed (test_sysbooks_api.py)
pipeline API: 12/12 passed (test_pipeline_api.py)
零新回归 (Zero new regressions from all changes)
```

### 关键技术发现

1. `tsv_content` 是 GENERATED ALWAYS 列 (`to_tsvector('simple', title || ' ' || content)`)，不能 INSERT/UPDATE
2. 内容超过 ~1MB 的 tsvector 会失败，workaround: 截断 content 到 300K 字符
3. PostgreSQL 索引在 TRUNCATE 后保留，重新导入前需显式 DROP
4. 3M 行无索引导入速度: 平均 4,947 行/秒，峰值 8,589 行/秒
5. GIN trigram 索引构建时间: filename_trgm=127s, path_trgm=620s; 模糊搜索性能: filename~144ms, path~394ms
6. sysbooks router prefix 必须包含 `/api/v1` 前缀（与 documents 等路由一致），否则 TestClient 返回 404

### 数据库当前状态

| 表 | 行数 | 说明 |
|----|------|------|
| `sys_books` | 3,024,428 | 11 索引; cross_ref: 1,116,600 matched (36.9%), cloud_path 已填充 |
| `sys_book_contents` | 0 | Phase 2 内容提取目标表 |
| `kg_entities` | 0 | Phase 3 知识图谱实体 |
| `kg_relations` | 0 | Phase 3 知识图谱关系 |
| `extraction_tasks` | 1+ | 后台任务跟踪 |
| `documents` | 103,234 | 含139条有内容的记录 + V4.0 维度标注 (13,875条, 100%覆盖) |

---

## 九、审计记录

> 审计日期: 2026-03-31

| 审计项 | 报告原文 | 实际值 | 状态 |
|--------|---------|--------|------|
| Sys_books.db 总记录 | 3,024,428 | 3,024,428 | ✅ |
| 文件数/目录数 | 2,906,851 / 117,577 | 2,906,851 / 117,577 | ✅ |
| PDF 数量 | 214,200 | 214,200 | ✅ |
| TXT 数量 | 133,403 | 133,403 | ✅ |
| Author 覆盖 | 1,190 (0.0%) | 1,190 (0.04%) | ⚠️ 四舍五入偏差，已修正 |
| data.db 总记录 | 907,539 | 907,539 | ✅ |
| data.db 文件数 | ~730,000 | **825,290** | ❌ 已修正 |
| data.db 总大小 | ~19 TB | **17,433 GB** | ⚠️ 已修正 |
| PostgreSQL 总文档 | 102,923 | 102,923 | ✅ |
| "0条>500字" | 0 | **1** (仍是文件列表) | ⚠️ 已修正 |
| 气功 IMA来源 | 未区分 | 144 | ✅ 新增细分 |
| 中医 IMA来源 | 未区分 | 3,607 | ✅ 新增细分 |
| 儒家 IMA来源 | 未区分 | 1,039 | ✅ 新增细分 |
| 智能气功总量 | ~7.8万 | **~12.8万** (去重) | ❌ 已修正 |
| 本地 TXT 文件 | 189 | 189 | ✅ |
| 已处理 JSON | 10 | **11** | ⚠️ 次要偏差 |
