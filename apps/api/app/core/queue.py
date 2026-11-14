import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def hash_ip(ip_address: Optional[str]) -> Optional[str]:
    """Privacy guard: SHA-256 hash of raw IP address. Raw IP is never persisted or queued."""
    if not ip_address:
        return None
    return hashlib.sha256(ip_address.strip().encode("utf-8")).hexdigest()


def enqueue_click_event(
    link_id: int,
    user_agent: Optional[str] = None,
    referrer: Optional[str] = None,
    client_ip: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Optional[str]:
    """Enqueue click analytics task onto Celery message queue.
    
    Resilience guarantees:
    - Privacy: client_ip is immediately hashed; raw IP never leaves the request context.
    - Idempotency: generates a unique event_id if not provided.
    - Graceful degradation: if Redis/Celery is down, the error is caught and logged.
      The redirect is NEVER blocked or failed.
    """
    if not event_id:
        event_id = str(uuid.uuid4())

    ip_hash = hash_ip(client_ip)
    now_iso = datetime.now(timezone.utc).isoformat()

    event_payload: Dict[str, Any] = {
        "event_id": event_id,
        "link_id": link_id,
        "clicked_at": now_iso,
        "user_agent": user_agent[:512] if user_agent else None,
        "referrer": referrer[:512] if referrer else None,
        "ip_hash": ip_hash,
    }

    try:
        from app.worker import record_click_event_task
        record_click_event_task.apply_async(args=[event_payload], retry=False)
        logger.debug("Successfully enqueued click event %s for link %s", event_id, link_id)
        return event_id
    except Exception as exc:
        logger.warning(
            "Async queue broker unavailable (%s); gracefully bypassing click event %s to preserve redirect SLA.",
            exc,
            event_id,
        )
        return None

