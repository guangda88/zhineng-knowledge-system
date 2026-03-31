# 找书查书功能 - 实现指南

<div align="center">

⚠️ **归档文档 — 数据已过时**

本报告为历史快照存档。当前版本 **v1.3.0-dev**，232 测试通过。

👉 最新工程状态请参阅 **[ENGINEERING_ALIGNMENT.md](ENGINEERING_ALIGNMENT.md)**

</div>

---

**实施阶段**: 阶段1 - 基础功能
**预计时间**: 1-2周

---

## 📁 文件结构

```
backend/
├── api/v2/
│   ├── __init__.py
│   ├── books.py              # 书籍API
│   ├── search.py             # 搜索API
│   └── sources.py            # 数据源API
├── models/
│   ├── book.py               # 书籍模型
│   └── source.py             # 数据源模型
├── services/
│   ├── book_search.py        # 搜索服务
│   └── source_manager.py     # 数据源管理
└── schemas/
    ├── book.py               # 书籍Schema
    └── search.py             # 搜索Schema

frontend/
├── src/
│   ├── pages/
│   │   ├── Books.tsx         # 书籍列表
│   │   ├── BookDetail.tsx    # 书籍详情
│   │   └── BookReader.tsx    # 阅读器
│   └── components/
│       ├── SearchBox.tsx     # 搜索框
│       └── BookCard.tsx      # 书籍卡片
```

---

## 🔧 实现步骤

### 步骤 1: 数据库初始化

```bash
# 执行SQL脚本
docker exec -i zhineng-postgres psql -U zhineng -d zhineng_kb < scripts/init_book_search_db.sql

# 验证表创建
docker exec zhineng-postgres psql -U zhineng -d zhineng_kb -c "\dt books"
```

### 步骤 2: 创建数据模型

```python
# backend/models/book.py
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, VECTOR
from datetime import datetime

from backend.core.database import Base

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    title_alternative = Column(String(500))
    subtitle = Column(String(500))
    author = Column(String(200))
    author_alt = Column(String(200))
    translator = Column(String(200))
    category = Column(String(50))  # 气功/中医/儒家
    dynasty = Column(String(50))
    year = Column(String(50))
    language = Column(String(10), default='zh')

    source_id = Column(Integer, ForeignKey('data_sources.id'))
    source_uid = Column(String(200))
    source_url = Column(String(500))

    description = Column(Text)
    toc = Column(JSONB)
    has_content = Column(Boolean, default=False)
    total_pages = Column(Integer, default=0)
    total_chars = Column(Integer, default=0)
    embedding = Column(VECTOR(1024))

    view_count = Column(Integer, default=0)
    bookmark_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    chapters = relationship("BookChapter", back_populates="book", cascade="all, delete-orphan")
    source = relationship("DataSource", back_populates="books")


class BookChapter(Base):
    __tablename__ = "book_chapters"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'))
    chapter_num = Column(Integer, nullable=False)
    title = Column(String(500))
    level = Column(Integer, default=1)
    parent_id = Column(Integer, ForeignKey('book_chapters.id'))

    content = Column(Text)
    char_count = Column(Integer, default=0)
    order_position = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    book = relationship("Book", back_populates="chapters")
    parent = relationship("BookChapter", remote_side=[id])
```

### 步骤 3: 创建搜索服务

```python
# backend/services/book_search.py
from typing import List, Optional
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.sql import text

from backend.models.book import Book, BookChapter
from backend.services.retrieval.vector import VectorRetriever

class BookSearchService:
    """书籍搜索服务"""

    def __init__(self, db_session: AsyncSession, db_pool: asyncpg.Pool):
        self.db = db_session
        self.pool = db_pool

    async def search_metadata(
        self,
        query: str,
        category: Optional[str] = None,
        dynasty: Optional[str] = None,
        author: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> dict:
        """元数据搜索（标题、作者、描述）"""

        # 构建查询
        stmt = select(Book).where(Book.has_content == True)

        # 全文搜索
        if query:
            search_condition = text(
                "textsearchable_index_col @@ to_tsquery('chinese', :query)"
            )
            stmt = stmt.where(search_condition).order_by(
                text("ts_rank(textsearchable_index_col, to_tsquery('chinese', :query)) DESC")
            ).params(query=query)

        # 筛选条件
        if category:
            stmt = stmt.where(Book.category == category)
        if dynasty:
            stmt = stmt.where(Book.dynasty == dynasty)
        if author:
            stmt = stmt.where(Book.author.ilike(f"%{author}%"))

        # 分页
        stmt = stmt.limit(size).offset((page - 1) * size)

        result = await self.db.execute(stmt)
        books = result.scalars().all()

        # 获取总数
        count_stmt = select(func.count(Book.id))
        if query:
            count_stmt = count_stmt.where(search_condition).params(query=query)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar()

        return {
            "total": total,
            "page": page,
            "size": size,
            "results": [self._book_to_dict(book) for book in books]
        }

    async def search_content(
        self,
        query: str,
        category: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> dict:
        """全文内容搜索"""

        stmt = select(BookChapter).join(Book).where(
            BookChapter.content.ilike(f"%{query}%")
        )

        if category:
            stmt = stmt.where(Book.category == category)

        stmt = stmt.limit(size).offset((page - 1) * size)

        result = await self.db.execute(stmt)
        chapters = result.scalars().all()

        return {
            "total": len(chapters),
            "page": page,
            "size": size,
            "results": [self._chapter_to_dict(ch) for ch in chapters]
        }

    async def search_similar(
        self,
        book_id: int,
        top_k: int = 10
    ) -> List[dict]:
        """基于向量的相似书籍推荐"""

        async with VectorRetriever(self.pool) as retriever:
            # 获取目标书籍的向量
            book = await self.db.get(Book, book_id)
            if not book or not book.embedding:
                return []

            # 向量搜索
            results = await retriever.search_by_vector(
                book.embedding,
                top_k=top_k + 1  # +1 因为会包含自己
            )

            # 过滤掉自己
            return [r for r in results if r['id'] != book_id][:top_k]

    def _book_to_dict(self, book: Book) -> dict:
        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "category": book.category,
            "dynasty": book.dynasty,
            "description": book.description,
            "has_content": book.has_content,
            "view_count": book.view_count
        }

    def _chapter_to_dict(self, chapter: BookChapter) -> dict:
        return {
            "id": chapter.id,
            "book_id": chapter.book_id,
            "book_title": chapter.book.title,
            "title": chapter.title,
            "content": chapter.content[:200] + "...",  # 预览
        }
```

### 步骤 4: 创建API端点

```python
# backend/api/v2/books.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.services.book_search import BookSearchService
from backend.schemas.book import BookResponse, BookListResponse

router = APIRouter(prefix="/books", tags=["books"])

@router.get("/search", response_model=BookListResponse)
async def search_books(
    q: str = Query("", max_length=200),
    category: str = Query(None),
    dynasty: str = Query(None),
    author: str = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """搜索书籍"""
    service = BookSearchService(db, get_db_pool())
    return await service.search_metadata(q, category, dynasty, author, page, size)

@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取书籍详情"""
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # 增加浏览计数
    book.view_count += 1
    await db.commit()

    return book

@router.get("/{book_id}/related")
async def get_related_books(
    book_id: int,
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """获取相关书籍"""
    service = BookSearchService(db, get_db_pool())
    return await service.search_similar(book_id, top_k)
```

### 步骤 5: 前端实现

```typescript
// frontend/src/pages/Books.tsx
import React, { useState } from 'react';
import { SearchBox } from '../components/SearchBox';
import { BookCard } from '../components/BookCard';
import { searchBooks } from '../api/books';

export const Books: React.FC = () => {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    category: '',
    dynasty: '',
    author: ''
  });

  const handleSearch = async (query: string) => {
    setLoading(true);
    try {
      const results = await searchBooks({
        q: query,
        ...filters,
        page: 1,
        size: 20
      });
      setBooks(results.data);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="books-page">
      <SearchBox
        placeholder="搜索书名、作者、关键词..."
        onSearch={handleSearch}
        filters={filters}
        onFilterChange={setFilters}
      />

      <div className="books-grid">
        {books.map(book => (
          <BookCard
            key={book.id}
            book={book}
            onClick={() => window.location.href = `/books/${book.id}`}
          />
        ))}
      </div>

      {loading && <div className="loading">搜索中...</div>}
    </div>
  );
};
```

---

## 📝 TODO 任务列表

### 后端任务

- [ ] 创建数据模型（`models/book.py`, `models/source.py`）
- [ ] 实现搜索服务（`services/book_search.py`）
- [ ] 创建API路由（`api/v2/books.py`）
- [ ] 添加Pydantic schemas（`schemas/book.py`）
- [ ] 编写单元测试
- [ ] 添加API文档

### 前端任务

- [ ] 创建搜索页面（`pages/Books.tsx`）
- [ ] 创建书籍详情页（`pages/BookDetail.tsx`）
- [ ] 创建搜索框组件（`components/SearchBox.tsx`）
- [ ] 创建书籍卡片组件（`components/BookCard.tsx`）
- [ ] 添加筛选器UI
- [ ] 实现无限滚动分页

### 数据任务

- [ ] 导入现有教材数据
- [ ] 配置Elasticsearch索引
- [ ] 生成书籍向量嵌入
- [ ] 创建示例数据

---

## 🧪 测试

### API测试

```bash
# 搜索书籍
curl "http://localhost:8000/api/v2/books/search?q=周易&category=儒家"

# 获取书籍详情
curl "http://localhost:8000/api/v2/books/1"

# 获取相关书籍
curl "http://localhost:8000/api/v2/books/1/related?top_k=10"
```

### 性能测试

```bash
# 使用 ab (Apache Bench)
ab -n 1000 -c 10 "http://localhost:8000/api/v2/books/search?q=周易"

# 目标: >100 req/s
```

---

## 📊 验收标准

### 功能验收

- [ ] 可以按标题、作者搜索书籍
- [ ] 可以按分类、朝代筛选
- [ ] 全文搜索返回正确的高亮结果
- [ ] 相关推荐书籍有语义相关性
- [ ] 前端UI响应式设计

### 性能验收

- [ ] 搜索响应时间 < 200ms
- [ ] 支持100+并发请求
- [ ] 全文搜索响应时间 < 500ms

---

**下一步**: 开始实施步骤1，创建数据模型和数据库表
