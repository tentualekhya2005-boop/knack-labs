from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    long_url = Column(Text, nullable=False)
    tags = Column(String(256), nullable=True)
    created_by = Column(String(128), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)

    clicks = relationship(
        "ClickEvent", back_populates="link", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_links_created_by", "created_by"),
        Index("idx_links_code_unique", "code", unique=True),
    )

