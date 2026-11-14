from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class ClickEvent(Base):
    __tablename__ = "click_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, index=True, nullable=True)  # Idempotency key
    link_id = Column(
        Integer, ForeignKey("links.id", ondelete="CASCADE"), nullable=False
    )
    clicked_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    user_agent = Column(String(512), nullable=True)
    referrer = Column(String(512), nullable=True)
    ip_hash = Column(String(64), nullable=True)  # SHA-256 hash, never store raw IP

    link = relationship("Link", back_populates="clicks")

    __table_args__ = (
        Index("idx_clicks_link_id_clicked_at", "link_id", "clicked_at"),
    )

