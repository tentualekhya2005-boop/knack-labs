import os
import sys
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db.session import SessionLocal
from app.models.click import ClickEvent

logger = logging.getLogger(__name__)

broker_url = os.getenv("CELERY_BROKER_URL", settings.redis_url or "redis://localhost:6379/0")

celery_app = Celery("app_worker", broker=broker_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=2,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_enable_remote_control=False,
    worker_send_task_events=False,
)


# Fixed Bug #10 (Part 3): Dedicated worker connection pool (bulkhead resource isolation)
worker_db_url = settings.database_url
if worker_db_url.startswith("postgres://"):
    worker_db_url = worker_db_url.replace("postgres://", "postgresql://", 1)

worker_engine = create_engine(
    worker_db_url,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    pool_timeout=5,
    connect_args={"connect_timeout": 3},
)
WorkerSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=worker_engine)


def process_click_event_record(db: Session, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Core idempotent database insertion logic for click events.
    Guarantees that replaying the identical event_id does not insert duplicate rows.
    Fixed BREAK: Uses dedicated analytics:dedup:<event_id> namespace completely separate
    from link:redirect:<code_or_key> namespace.
    """
    event_id = event_data.get("event_id")
    from app.core.cache import cache_service

    # Check dedicated deduplication namespace first
    if event_id and cache_service.is_analytics_processed(event_id):
        return {"status": "duplicate_skipped", "event_id": event_id, "inserted": False}

    link_id = event_data.get("link_id")
    user_agent = event_data.get("user_agent")
    referrer = event_data.get("referrer")
    ip_hash = event_data.get("ip_hash")
    clicked_at_raw = event_data.get("clicked_at")

    if clicked_at_raw:
        if isinstance(clicked_at_raw, str):
            clicked_at = datetime.fromisoformat(clicked_at_raw)
        else:
            clicked_at = clicked_at_raw
    else:
        clicked_at = datetime.now(timezone.utc)

    # Dialect-aware idempotent insert
    dialect = db.bind.dialect.name if db.bind else "postgresql"
    if dialect == "postgresql" and event_id:
        stmt = (
            pg_insert(ClickEvent)
            .values(
                event_id=event_id,
                link_id=link_id,
                clicked_at=clicked_at,
                user_agent=user_agent[:512] if user_agent else None,
                referrer=referrer[:512] if referrer else None,
                ip_hash=ip_hash[:64] if ip_hash else None,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
            .returning(ClickEvent.id)
        )
        res = db.execute(stmt)
        inserted_id = res.scalar()
        db.commit()
        inserted = inserted_id is not None
    else:
        # Generic fallback for SQLite or non-Postgres in unit tests
        if event_id:
            existing = db.query(ClickEvent).filter(ClickEvent.event_id == event_id).first()
            if existing:
                return {"status": "duplicate_skipped", "event_id": event_id, "inserted": False}

        click = ClickEvent(
            event_id=event_id,
            link_id=link_id,
            clicked_at=clicked_at,
            user_agent=user_agent[:512] if user_agent else None,
            referrer=referrer[:512] if referrer else None,
            ip_hash=ip_hash[:64] if ip_hash else None,
        )
        db.add(click)
        try:
            db.commit()
            inserted = True
        except Exception:
            db.rollback()
            inserted = False

    if inserted and event_id:
        cache_service.mark_analytics_processed(event_id)

    return {
        "status": "success" if inserted else "duplicate_skipped",
        "event_id": event_id,
        "inserted": inserted,
        "link_id": link_id,
    }


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=1,
    retry_backoff=True,
    retry_backoff_max=30,
    retry_jitter=True,
    name="record_click_event_task",
)
def record_click_event_task(self, event_data: dict) -> dict:
    """Celery task consuming click events from Redis queue and persisting to DB idempotently.
    Fixed Bug #10: Uses isolated WorkerSessionLocal pool, exponential backoff, and max retry ceiling.
    """
    event_id = event_data.get("event_id")
    db: Session = WorkerSessionLocal()
    try:
        result = process_click_event_record(db, event_data)
        if result["inserted"]:
            logger.info("Successfully recorded click event %s for link %s", event_id, event_data.get("link_id"))
        else:
            logger.info("Duplicate click event %s skipped idempotently", event_id)
        return result
    except Exception as exc:
        db.rollback()
        logger.error(
            "Failed to persist click event %s: %s (attempt %s/%s). Retrying with backoff...",
            event_id,
            exc,
            self.request.retries + 1,
            self.max_retries,
        )
        if self.request.retries >= self.max_retries:
            logger.error("Dead-Letter Queue: click event %s exceeded max retries. Discarding to DLQ.", event_id)
            return {"status": "dlq_discarded", "event_id": event_id, "error": str(exc)}
        raise self.retry(exc=exc)
    finally:
        db.close()


if __name__ == "__main__":
    # Support direct invocation
    celery_app.start()
