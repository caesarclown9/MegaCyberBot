from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    title_ru = Column(String(500), nullable=True)
    title_original = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    description_ru = Column(Text, nullable=True)
    description_original = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    parsed_at = Column(DateTime, server_default=func.now(), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    is_sent = Column(Boolean, default=False, nullable=False, index=True)
    source = Column(String(50), nullable=True, index=True)
    category = Column(String(50), nullable=True, index=True, default="general")
    
    __table_args__ = (
        Index("idx_is_sent_published", "is_sent", "published_at"),
        Index("idx_category_sent", "category", "is_sent"),
    )
    
    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title={self.title[:50]}...)>"

