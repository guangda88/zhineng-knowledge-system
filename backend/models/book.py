"""书籍数据模型

书籍和章节的数据模型定义
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.core.database import Base


class Book(Base):
    """书籍模型"""

    __tablename__ = "books"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)

    # 标题信息
    title = Column(String(500), nullable=False)
    title_alternative = Column(String(500))
    subtitle = Column(String(500))

    # 作者信息
    author = Column(String(200))
    author_alt = Column(String(200))
    translator = Column(String(200))

    # 元数据
    category = Column(String(50))  # 气功/中医/儒家
    dynasty = Column(String(50))
    year = Column(String(50))
    language = Column(String(10), default="zh")

    # 数据源关联
    source_id = Column(Integer, ForeignKey("data_sources.id"))
    source_uid = Column(String(200))
    source_url = Column(String(500))

    # 内容
    description = Column(Text)
    toc = Column(JSONB)  # 目录结构
    has_content = Column(Boolean, default=False)
    total_pages = Column(Integer, default=0)
    total_chars = Column(Integer, default=0)

    # 向量搜索（512维，匹配bge-small-zh-v1.5）
    embedding = Column(Vector(512))

    # 统计
    view_count = Column(Integer, default=0)
    bookmark_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    chapters = relationship("BookChapter", back_populates="book", cascade="all, delete-orphan")
    source = relationship("DataSource", back_populates="books")

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}', category='{self.category}')>"


class BookChapter(Base):
    """书籍章节模型"""

    __tablename__ = "book_chapters"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"))

    chapter_num = Column(Integer, nullable=False)
    title = Column(String(500))
    level = Column(Integer, default=1)  # 1=章, 2=节, 3=小节
    parent_id = Column(Integer, ForeignKey("book_chapters.id"))

    content = Column(Text)
    char_count = Column(Integer, default=0)
    order_position = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    book = relationship("Book", back_populates="chapters")
    parent = relationship("BookChapter", remote_side=[id])

    def __repr__(self):
        return f"<BookChapter(id={self.id}, book_id={self.book_id}, title='{self.title}')>"
