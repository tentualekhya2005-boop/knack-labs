from datetime import datetime, timezone
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import cache_service
from app.core.queue import enqueue_click_event
from app.core.rate_limit import rate_limit_redirect
from app.db.session import get_db
from app.services import links_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["redirect"])


def record_analytics_bucket(db: Session, link_id: int, accessed_at: datetime = None):
    """Hourly bucketed analytics aggregation.
    Bug #5 & Silent Drift Fix: Atomic PostgreSQL upsert with GREATEST() monotonic ratchet.
    """
    now = accessed_at or datetime.now(timezone.utc)
    now_bucket = now.replace(minute=0, second=0, microsecond=0)

    stmt = text("""
        INSERT INTO analytics (link_id, timestamp_bucket, count, last_accessed_at)
        VALUES (:link_id, :bucket, 1, :accessed_at)
        ON CONFLICT (link_id, timestamp_bucket)
        DO UPDATE SET
            count = analytics.count + 1,
            last_accessed_at = GREATEST(analytics.last_accessed_at, EXCLUDED.last_accessed_at)
    """)
    db.execute(stmt, {"link_id": link_id, "bucket": now_bucket, "accessed_at": now})
    db.commit()


@router.get("/{code}", dependencies=[Depends(rate_limit_redirect)])
@router.get("/r/{code}", dependencies=[Depends(rate_limit_redirect)])
def redirect_to_long_url(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    # Ignore reserved system routes if matched by /{code}
    if code in ("health", "ready", "docs", "redoc", "openapi.json"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        cached = None
        # 1. Check cache (Graceful path: if cache check fails, continue to DB fallback)
        try:
            cached = cache_service.get_redirect_target(code)
        except Exception as exc:
            logger.warning(f"Cache check failed ({exc}), gracefully falling back to DB.")
            cached = None

        if cached:
            # Check expiration if stored
            expires_at_str = cached.get("expires_at")
            if expires_at_str:
                try:
                    exp_dt = datetime.fromisoformat(expires_at_str)
                    if exp_dt < datetime.now(timezone.utc):
                        try:
                            cache_service.invalidate_redirect_target(code)
                        except Exception:
                            pass
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Short link has expired",
                        )
                except ValueError:
                    pass

            link_id = cached.get("link_id")
            if link_id:
                # Record aggregated hourly analytics
                record_analytics_bucket(db, link_id)
                try:
                    client_ip = request.client.host if request.client else None
                    user_agent = request.headers.get("user-agent")
                    referrer = request.headers.get("referer")
                    enqueue_click_event(
                        link_id=link_id,
                        user_agent=user_agent,
                        referrer=referrer,
                        client_ip=client_ip,
                    )
                except Exception as e:
                    logger.error(f"Failed to enqueue click analytics: {e}")

            resp = RedirectResponse(
                url=cached["long_url"],
                status_code=status.HTTP_302_FOUND,
            )
            resp.headers["X-Cache"] = "HIT"
            return resp

        # 2. Cache Miss: Fall back to PostgreSQL database
        link = links_service.get_link_by_code(db, code)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short link not found",
            )

        # Check expiration
        if link.expires_at:
            now = datetime.now(timezone.utc)
            if link.expires_at.tzinfo is None:
                link_expires = link.expires_at.replace(tzinfo=timezone.utc)
            else:
                link_expires = link.expires_at
            if link_expires < now:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Short link has expired",
                )

        # Populate cache with TTL (Cache-Aside write on miss; catch error gracefully)
        cache_data = {
            "long_url": link.long_url,
            "link_id": link.id,
            "tenant_id": link.created_by,
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        }
        try:
            cache_service.set_redirect_target(code, cache_data)
        except Exception as exc:
            logger.warning(f"Cache populate failed ({exc}), continuing redirect.")

        # Record aggregated hourly analytics directly (Bug #5 surface)
        record_analytics_bucket(db, link.id)

        # Record analytics via async queue
        try:
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            referrer = request.headers.get("referer")
            enqueue_click_event(
                link_id=link.id,
                user_agent=user_agent,
                referrer=referrer,
                client_ip=client_ip,
            )
        except Exception as e:
            logger.error(f"Failed to enqueue click analytics: {e}")

        resp = RedirectResponse(
            url=link.long_url,
            status_code=status.HTTP_302_FOUND,
        )
        resp.headers["X-Cache"] = "MISS"
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during redirect: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process redirect request",
        )
