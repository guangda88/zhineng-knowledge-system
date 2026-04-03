# 灵知系统 - 找书查书功能集成方案

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**设计日期**: 2026-03-31
**参考系统**: 典津、FoJin、SimpleBookFinder

---

## 📋 功能需求分析

### 核心功能（参考 FoJin）

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **数据源管理** | 管理多个古籍/教材数据源 | P0 |
| **多维度搜索** | 标题、作者、朝代、分类、标签、关键词 | P0 |
| **全文搜索** | 书籍内容全文检索 | P0 |
| **高级筛选** | 按分类、数据源、语言等筛选 | P1 |
| **书籍详情** | 元数据、目录、相关推荐 | P0 |
| **在线阅读** | 分章节阅读教材内容 | P1 |
| **对照阅读** | 多版本/多语言对照 | P2 |
| **词典集成** | 术语解释、生词查询 | P2 |
| **知识图谱** | 书籍、概念、人物关系 | P2 |
| **AI问答** | 基于书籍内容的RAG问答 | P0 |
| **书签笔记** | 用户个人标注、高亮、笔记 | P2 |
| **引用导出** | BibTeX、RIS、APA格式 | P2 |
| **推荐系统** | 基于阅读历史的智能推荐 | P3 |

---

## 🏗️ 架构设计

### 1. 整体架构（参考 FoJin）

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (React 18)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ 搜索界面  │  │ 阅读器   │  │ 知识图谱  │  │ AI问答  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────────┐
│                   Nginx (反向代理)                        │
│              静态文件 + API路由 + 缓存                    │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                 FastAPI 后端服务                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ 搜索API   │  │ 书籍API   │  │ 阅读API   │  │ 推理API  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
│ PostgreSQL   │ │Elasticsearch│ │  Redis     │
│ + pgvector   │ │  (搜索)   │ │  (缓存)    │
└──────────────┘ └───────────┘ └─────────────┘
```

### 2. 数据库设计

#### 2.1 数据源表 (data_sources)

```sql
CREATE TABLE data_sources (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,           -- 数据源代码
    name_zh VARCHAR(200) NOT NULL,              -- 中文名称
    name_en VARCHAR(200),                       -- 英文名称
    base_url VARCHAR(500),                      -- 基础URL
    api_url VARCHAR(500),                       -- API URL
    description TEXT,                           -- 描述
    access_type VARCHAR(20) DEFAULT 'external', -- local/external/api
    region VARCHAR(50),                         -- 地区
    languages VARCHAR(200),                     -- 语言（逗号分隔）
    category VARCHAR(50),                       -- 类别（气功/中医/儒家/其他）

    -- 能力标记
    supports_search BOOLEAN DEFAULT false,      -- 支持搜索
    supports_fulltext BOOLEAN DEFAULT false,    -- 支持全文
    has_local_fulltext BOOLEAN DEFAULT false,   -- 有本地全文
    has_remote_fulltext BOOLEAN DEFAULT false,  -- 有远程全文
    supports_api BOOLEAN DEFAULT false,         -- 支持API

    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 2.2 书籍表 (books)

```sql
CREATE TABLE books (
    id SERIAL PRIMARY KEY,

    -- 标题信息
    title VARCHAR(500) NOT NULL,
    title_alternative VARCHAR(500),            -- 别名
    subtitle VARCHAR(500),

    -- 作者信息
    author VARCHAR(200),
    author_alt VARCHAR(200),                   -- 其他作者
    translator VARCHAR(200),                   -- 译者/注疏者

    -- 元数据
    category VARCHAR(50),                      -- 分类（气功/中医/儒家）
    dynasty VARCHAR(50),                       -- 朝代
    year VARCHAR(50),                          -- 年代
    language VARCHAR(10) DEFAULT 'zh',         -- 语言

    -- 数据源关联
    source_id INTEGER REFERENCES data_sources(id),
    source_uid VARCHAR(200),                   -- 数据源中的ID
    source_url VARCHAR(500),                   -- 数据源链接

    -- 内容
    description TEXT,                          -- 简介
    toc JSONB,                                 -- 目录结构
    has_content BOOLEAN DEFAULT false,         -- 是否有全文
    total_pages INTEGER DEFAULT 0,
    total_chars INTEGER DEFAULT 0,

    -- 向量搜索
    embedding vector(1024),                    -- BGE-M3向量

    -- 统计
    view_count INTEGER DEFAULT 0,
    bookmark_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 全文搜索
    FULLTEXT(title, author, description)
);

CREATE INDEX idx_books_category ON books(category);
CREATE INDEX idx_books_dynasty ON books(dynasty);
CREATE INDEX idx_books_source ON books(source_id);
CREATE INDEX idx_books_embedding ON books USING ivfflat(embedding vector_cosine_ops);
```

#### 2.3 章节表 (book_chapters)

```sql
CREATE TABLE book_chapters (
    id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,

    chapter_num INTEGER NOT NULL,              -- 章节号
    title VARCHAR(500),                        -- 章节标题
    level INTEGER DEFAULT 1,                   -- 层级（章/节/小节）
    parent_id INTEGER REFERENCES book_chapters(id),

    content TEXT,                              -- 章节内容
    char_count INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chapters_book ON book_chapters(book_id);
CREATE INDEX idx_chapters_parent ON book_chapters(parent_id);
```

#### 2.4 词典表 (dictionary)

```sql
CREATE TABLE dictionary (
    id SERIAL PRIMARY KEY,
    term VARCHAR(200) NOT NULL,                -- 术语
    pinyin VARCHAR(200),                       -- 拼音
    definition TEXT,                           -- 定义
    category VARCHAR(50),                      -- 分类
    source VARCHAR(200),                       -- 来源
    related_terms TEXT[],                      -- 相关术语

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_dict_term ON dictionary(term);
CREATE INDEX idx_dict_category ON dictionary(category);
```

#### 2.5 书签表 (user_bookmarks)

```sql
CREATE TABLE user_bookmarks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    chapter_id INTEGER REFERENCES book_chapters(id),

    note TEXT,                                 -- 笔记
    highlight_text TEXT,                       -- 高亮文本
    position INTEGER,                          -- 位置

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bookmarks_user ON user_bookmarks(user_id);
CREATE INDEX idx_bookmarks_book ON user_bookmarks(book_id);
```

#### 2.6 Elasticsearch 索引配置

```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "ik_max_word": {
          "type": "custom",
          "tokenizer": "ik_max_word"
        },
        "cjk_content": {
          "type": "custom",
          "tokenizer": "ik_max_word",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "id": {"type": "integer"},
      "title": {
        "type": "text",
        "analyzer": "ik_max_word",
        "fields": {
          "keyword": {"type": "keyword"}
        }
      },
      "author": {
        "type": "text",
        "analyzer": "ik_max_word"
      },
      "category": {"type": "keyword"},
      "dynasty": {"type": "keyword"},
      "content": {
        "type": "text",
        "analyzer": "cjk_content"
      },
      "source_code": {"type": "keyword"},
      "language": {"type": "keyword"}
    }
  }
}
```

---

## 🔌 API 设计

### 1. 搜索 API

#### 1.1 书籍搜索（元数据）

```python
GET /api/v2/books/search

查询参数:
- q: 搜索关键词
- page: 页码（默认1）
- size: 每页数量（默认20，最大100）
- category: 分类筛选（气功/中医/儒家）
- dynasty: 朝代筛选
- author: 作者筛选
- source: 数据源筛选
- sort: 排序方式（relevance/title/dynasty/year）

响应:
{
  "total": 150,
  "page": 1,
  "size": 20,
  "results": [
    {
      "id": 123,
      "title": "周易注疏",
      "author": "王弼",
      "dynasty": "魏晋",
      "category": "儒家",
      "description": "...",
      "source": "本地教材",
      "has_content": true,
      "score": 0.95
    }
  ]
}
```

#### 1.2 全文搜索

```python
GET /api/v2/books/search/content

查询参数:
- q: 搜索关键词
- page: 页码
- size: 每页数量
- source: 数据源筛选
- category: 分类筛选

响应:
{
  "total": 50,
  "page": 1,
  "size": 20,
  "results": [
    {
      "book_id": 123,
      "book_title": "周易注疏",
      "chapter_id": 456,
      "chapter_title": "乾卦",
      "highlight": "<em>天行健</em>，君子以<em>自强不息</em>",
      "score": 0.92
    }
  ]
}
```

#### 1.3 联合搜索

```python
GET /api/v2/books/search/federated

同时搜索本地数据库 + 外部数据源

响应:
{
  "local_total": 100,
  "local_results": [...],
  "external_total": 250,
  "external_results": [...],
  "combined_total": 350
}
```

### 2. 书籍 API

```python
# 获取书籍详情
GET /api/v2/books/{book_id}

# 获取书籍目录
GET /api/v2/books/{book_id}/toc

# 获取章节内容
GET /api/v2/books/{book_id}/chapters/{chapter_id}

# 获取相关书籍（基于向量相似度）
GET /api/v2/books/{book_id}/related

# 书签/笔记操作
POST /api/v2/books/{book_id}/bookmarks
GET /api/v2/users/me/bookmarks
DELETE /api/v2/bookmarks/{bookmark_id}
```

### 3. 数据源 API

```python
# 列出所有数据源
GET /api/v2/sources

# 获取数据源统计
GET /api/v2/sources/stats

# 获取筛选选项
GET /api/v2/filters
{
  "categories": ["气功", "中医", "儒家"],
  "dynasties": ["先秦", "两汉", "魏晋", ...],
  "languages": ["zh", "lzh", "en"],
  "sources": ["local", "cbeta", "guji"]
}
```

### 4. 词典 API

```python
# 术语查询
GET /api/v2/dictionary/lookup?term={term}

# 术语建议
GET /api/v2/dictionary/suggest?q={q}
```

---

## 🎨 前端设计

### 1. 搜索界面

```typescript
// 搜索框组件
<SearchBox
  placeholder="搜索书名、作者、关键词..."
  filters={{
    category: '分类',
    dynasty: '朝代',
    source: '数据源'
  }}
  onSearch={handleSearch}
/>

// 搜索结果卡片
<BookCard
  title={book.title}
  author={book.author}
  description={book.description}
  category={book.category}
  onClick={openBook}
/>
```

### 2. 阅读器界面

```typescript
// 书籍阅读器
<BookReader
  bookId={bookId}
  chapters={toc}
  content={content}
  onChapterChange={handleChapterChange}
  onAddBookmark={handleBookmark}
  onHighlight={handleHighlight}
/>

// 对照阅读模式
<ParallelReader
  versions={[version1, version2]}
  layout="side-by-side"
/>
```

### 3. 知识图谱

```typescript
// 使用 D3.js 或 Cytoscape.js
<KnowledgeGraph
  nodes={entities}
  edges={relations}
  onNodeClick={showDetails}
/>
```

---

## 📚 数据源集成策略

### 1. 本地数据源

```python
# 本地教材数据
class LocalBookSource(BaseDataSource):
    async def search(self, query: str) -> List[Book]:
        # 搜索本地数据库
        pass

    async def get_content(self, book_id: int) -> str:
        # 获取本地内容
        pass
```

### 2. 外部API集成

```python
# 典津 API 集成
class DianjinSource(BaseDataSource):
    BASE_URL = "https://guji.cckb.cn/api"

    async def search(self, query: str) -> List[Book]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/search",
                params={"q": query}
            )
            return self._parse_response(response.json())

    async def get_content(self, book_id: str) -> str:
        # 实现内容获取
        pass
```

### 3. 爬虫集成（可选）

```python
# 对于没有API的数据源
class WebScraperSource(BaseDataSource):
    async def scrape_catalog(self, url: str) -> List[Book]:
        # 使用 BeautifulSoup/Scrapy
        pass
```

---

## 🚀 实施计划

### 阶段 1: 基础功能（1-2周）

- [ ] 数据库表结构创建
- [ ] 数据源模型实现
- [ ] 基础书籍搜索API
- [ ] 简单搜索UI
- [ ] 本地数据导入脚本

### 阶段 2: 高级搜索（1-2周）

- [ ] Elasticsearch集成
- [ ] 全文搜索实现
- [ ] 高级筛选功能
- [ ] 向量搜索集成（使用BGE-M3）
- [ ] 相关推荐

### 阶段 3: 阅读功能（1-2周）

- [ ] 章节内容API
- [ ] 在线阅读器UI
- [ ] 书签/笔记功能
- [ ] 高亮标注

### 阶段 4: 外部集成（1周）

- [ ] 典津API集成
- [ ] 其他数据源适配器
- [ ] 联合搜索
- [ ] 数据源管理界面

### 阶段 5: 高级功能（2-3周）

- [ ] 词典集成
- [ ] 知识图谱
- [ ] AI问答增强
- [ ] 对照阅读
- [ ] 引用导出

---

## 💡 技术要点

### 1. 搜索性能优化

```python
# 多级缓存
@cached(ttl=300)  # Redis缓存5分钟
async def search_with_cache(query: str):
    # ES搜索
    pass

# 数据库查询优化
# 使用 materialized view 预计算聚合
CREATE MATERIALIZED VIEW book_stats AS
SELECT category, COUNT(*) as count
FROM books
GROUP BY category;
```

### 2. 向量搜索

```python
# 使用已有的BGE-M3嵌入服务
async def find_similar_books(book_id: int, top_k: int = 10):
    embedding = await get_book_embedding(book_id)
    async with VectorRetriever(pool) as retriever:
        return await retriever.search_by_vector(embedding, top_k)
```

### 3. AI问答增强

```python
# 扩展现有的RAG系统，增加书籍上下文
async def answer_about_book(question: str, book_id: int):
    # 1. 获取书籍内容
    book_content = await get_book_content(book_id)

    # 2. 检索相关段落
    relevant = await search_in_book(question, book_id)

    # 3. 使用DeepSeek生成答案
    answer = await deepseek_rag(question, relevant)

    return answer
```

---

## 📊 预期效果

### 搜索质量

| 指标 | 当前 | 目标 |
|------|------|------|
| 搜索准确率 | 60% | 85% |
| 全文覆盖率 | 0% | 80% |
| 相关性排序 | 0.5 | 0.8 |

### 功能完整性

| 功能 | 完成度 |
|------|--------|
| 多维度搜索 | 100% |
| 全文搜索 | 100% |
| 在线阅读 | 100% |
| 书签笔记 | 80% |
| 词典集成 | 60% |
| 知识图谱 | 40% |

---

**下一步**: 开始实施阶段1，创建数据库表和基础API
