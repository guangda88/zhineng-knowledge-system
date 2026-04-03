"""数据源模型

数据源的配置和管理
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.core.database import Base


class DataSource(Base):
    """数据源模型"""

    __tablename__ = "data_sources"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name_zh = Column(String(200), nullable=False)
    name_en = Column(String(200))
    base_url = Column(String(500))
    api_url = Column(String(500))
    description = Column(Text)
    access_type = Column(String(20), default="external")  # local/external/api
    region = Column(String(50))
    languages = Column(String(200))  # 逗号分隔的ISO 639代码
    category = Column(String(50))  # 气功/中医/儒家/其他

    # 能力标记
    supports_search = Column(Boolean, default=False)
    supports_fulltext = Column(Boolean, default=False)
    has_local_fulltext = Column(Boolean, default=False)
    has_remote_fulltext = Column(Boolean, default=False)
    supports_api = Column(Boolean, default=False)

    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default="now()")
    updated_at = Column(DateTime, server_default="now()", onupdate="now()")

    # 关系
    books = relationship("Book", back_populates="source")

    def __repr__(self):
        return (
            f"<DataSource(code='{self.code}', name_zh='{self.name_zh}', active={self.is_active})>"
        )
