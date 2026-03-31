"""书籍搜索服务

提供书籍的多维度搜索功能：
- 元数据搜索（标题、作者）
- 全文搜索（章节内容）
- 向量搜索（语义相似度）
"""
from typing import List, Dict, Any, Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, update
from sqlalchemy.sql import text

from models.book import Book, BookChapter
from models.source import DataSource
from services.retrieval.vector import VectorRetriever

logger = logging.getLogger(__name__)


class BookSearchService:
    """书籍搜索服务"""

    def __init__(self, db_session: AsyncSession, db_pool):
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
    ) -> Dict[str, Any]:
        """元数据搜索（标题、作者、描述）

        Args:
            query: 搜索关键词
            category: 分类筛选
            dynasty: 朝代筛选
            author: 作者筛选
            page: 页码
            size: 每页数量

        Returns:
            搜索结果字典
        """
        # 构建基础查询
        stmt = select(Book)

        # 构建搜索条件
        conditions = []

        if query and query.strip():
            query_str = query.strip()
            # 使用ILIKE进行模糊匹配（利用pg_trgm索引）
            conditions.append(
                or_(
                    Book.title.ilike(f'%{query_str}%'),
                    Book.author.ilike(f'%{query_str}%'),
                    Book.description.ilike(f'%{query_str}%')
                )
            )

        if category:
            conditions.append(Book.category == category)

        if dynasty:
            conditions.append(Book.dynasty == dynasty)

        if author:
            conditions.append(Book.author.ilike(f'%{author}%'))

        # 应用所有条件
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # 排序：有标题匹配的优先
        if query and query.strip():
            stmt = stmt.order_by(
                text("CASE WHEN title ILIKE :query_start THEN 1 ELSE 2 END"),
                Book.view_count.desc(),
                Book.created_at.desc()
            ).params(query_start=f"{query.strip()}%")
        else:
            stmt = stmt.order_by(Book.view_count.desc(), Book.created_at.desc())

        # 获取总数
        count_stmt = select(func.count(Book.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar()

        # 分页
        stmt = stmt.limit(size).offset((page - 1) * size)
        result = await self.db.execute(stmt)
        books = result.scalars().all()

        return {
            "total": total or 0,
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
    ) -> Dict[str, Any]:
        """全文内容搜索

        Args:
            query: 搜索关键词
            category: 分类筛选
            page: 页码
            size: 每页数量

        Returns:
            搜索结果字典
        """
        if not query or not query.strip():
            return {"total": 0, "page": page, "size": size, "results": []}

        # 构建查询
        stmt = select(BookChapter).join(Book)

        conditions = [
            BookChapter.content.ilike(f'%{query.strip()}%')
        ]

        if category:
            conditions.append(Book.category == category)

        stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(BookChapter.char_count.desc())

        # 分页
        stmt = stmt.limit(size).offset((page - 1) * size)
        result = await self.db.execute(stmt)
        chapters = result.scalars().all()

        return {
            "total": len(chapters),  # 简化：不计算总数
            "page": page,
            "size": size,
            "results": [self._chapter_to_dict(ch, query) for ch in chapters]
        }

    async def search_similar(
        self,
        book_id: int,
        top_k: int = 10,
        threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """基于向量的相似书籍推荐

        Args:
            book_id: 目标书籍ID
            top_k: 返回数量
            threshold: 相似度阈值

        Returns:
            相似书籍列表
        """
        # 获取目标书籍
        book = await self.db.get(Book, book_id)
        if not book or not book.embedding:
            logger.warning(f"Book {book_id} not found or has no embedding")
            return []

        # 使用VectorRetriever进行向量搜索
        try:
            async with VectorRetriever(self.pool) as retriever:
                # 获取书籍的嵌入向量
                query_vector = book.embedding

                # 构建向量搜索SQL
                vector_str = "[" + ",".join(map(str, query_vector)) + "]"

                sql = """
                    SELECT id, title, author, category, dynasty,
                           1 - (embedding <=> $1::vector) as similarity
                    FROM books
                    WHERE id != $2 AND embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                """

                rows = await self.pool.fetch(sql, vector_str, book_id, top_k)

                # 过滤低于阈值的结果
                results = []
                for row in rows:
                    if row['similarity'] >= threshold:
                        results.append({
                            'id': row['id'],
                            'title': row['title'],
                            'author': row['author'],
                            'category': row['category'],
                            'dynasty': row['dynasty'],
                            'similarity': float(row['similarity'])
                        })

                logger.info(f"Found {len(results)} similar books for book {book_id}")
                return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def get_book_detail(self, book_id: int) -> Optional[Dict[str, Any]]:
        """获取书籍详情

        Args:
            book_id: 书籍ID

        Returns:
            书籍详情字典，如果不存在返回None
        """
        book = await self.db.get(Book, book_id)
        if not book:
            return None

        # 增加浏览计数 - 使用UPDATE语句避免async错误
        await self.db.execute(
            update(Book)
            .where(Book.id == book_id)
            .values(view_count=Book.view_count + 1)
        )
        await self.db.commit()

        # 刷新以获取更新后的值
        await self.db.refresh(book)

        return self._book_to_dict(book, include_chapters=True)

    async def get_chapter_content(self, book_id: int, chapter_id: int) -> Optional[Dict[str, Any]]:
        """获取章节内容

        Args:
            book_id: 书籍ID
            chapter_id: 章节ID

        Returns:
            章节内容字典
        """
        chapter = await self.db.get(BookChapter, chapter_id)
        if not chapter or chapter.book_id != book_id:
            return None

        return {
            'id': chapter.id,
            'book_id': chapter.book_id,
            'chapter_num': chapter.chapter_num,
            'title': chapter.title,
            'content': chapter.content,
            'char_count': chapter.char_count
        }

    def _book_to_dict(self, book: Book, include_chapters: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'category': book.category,
            'dynasty': book.dynasty,
            'year': book.year,
            'language': book.language,
            'description': book.description,
            'has_content': book.has_content,
            'total_pages': book.total_pages,
            'total_chars': book.total_chars,
            'view_count': book.view_count,
            'source_id': book.source_id,
            'created_at': book.created_at.isoformat() if book.created_at else None
        }

        if include_chapters:
            result['chapters'] = [
                {
                    'id': ch.id,
                    'chapter_num': ch.chapter_num,
                    'title': ch.title,
                    'level': ch.level,
                    'char_count': ch.char_count
                }
                for ch in sorted(book.chapters, key=lambda x: x.order_position or 0)
            ]

        return result

    def _chapter_to_dict(self, chapter: BookChapter, query: str = None) -> Dict[str, Any]:
        """转换为字典（带高亮）"""
        # 生成高亮预览
        preview = chapter.content or ""
        if query and query.strip():
            # 简单高亮：截取包含关键词的部分
            query_lower = query.strip().lower()
            content_lower = preview.lower()
            pos = content_lower.find(query_lower)

            if pos != -1:
                # 截取关键词前后200字符
                start = max(0, pos - 200)
                end = min(len(preview), pos + 200)
                preview = preview[start:end]

                # 添加高亮标记
                if len(preview) > 0:
                    preview = preview.replace(
                        query.strip(),
                        f"**{query.strip()}**",
                        1  # 只替换第一个
                    )
            else:
                # 如果没找到，取前400字符
                preview = preview[:400] + "..."

        return {
            'id': chapter.id,
            'book_id': chapter.book_id,
            'book_title': chapter.book.title if chapter.book else '',
            'chapter_num': chapter.chapter_num,
            'title': chapter.title,
            'preview': preview,
            'char_count': chapter.char_count
        }
