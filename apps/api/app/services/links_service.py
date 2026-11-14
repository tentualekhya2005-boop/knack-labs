import hashlib
import math
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.click import ClickEvent
from app.models.link import Link
from app.schemas.link import LinkCreate, LinkResponse, LinkUpdate, PaginatedLinksResponse


def generate_random_code(length: int = 8) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_link(
    db: Session,
    link_in: LinkCreate,
    base_url: str,
    principal_id: str = "default",
) -> LinkResponse:
    if link_in.code:
        # Check if code already exists
        existing = db.query(Link).filter(Link.code == link_in.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Short code '{link_in.code}' already exists.",
            )
        code = link_in.code
    else:
        # Generate a unique code with retries
        for _ in range(5):
            candidate = generate_random_code(8)
            if not db.query(Link).filter(Link.code == candidate).first():
                code = candidate
                break
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate a unique short code. Please try again.",
            )

    tags_str = ",".join(link_in.tags) if link_in.tags else None
    new_link = Link(
        code=code,
        long_url=link_in.long_url,
        tags=tags_str,
        created_by=principal_id,
        expires_at=link_in.expires_at,
    )
    db.add(new_link)
    db.commit()
    db.refresh(new_link)

    short_url = f"{base_url.rstrip('/')}/r/{new_link.code}"
    return LinkResponse(
        id=new_link.id,
        code=new_link.code,
        short_url=short_url,
        long_url=new_link.long_url,
        tags=new_link.tags,
        created_by=new_link.created_by,
        created_at=new_link.created_at,
        expires_at=new_link.expires_at,
    )


def get_link_by_id(
    db: Session,
    link_id: int,
    base_url: str,
    principal_id: Optional[str] = None,
) -> Optional[LinkResponse]:
    query = db.query(Link).filter(Link.id == link_id)
    if principal_id:
        query = query.filter(Link.created_by == principal_id)
    link = query.first()
    if not link:
        return None
    short_url = f"{base_url.rstrip('/')}/r/{link.code}"
    return LinkResponse(
        id=link.id,
        code=link.code,
        short_url=short_url,
        long_url=link.long_url,
        created_by=link.created_by,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


def update_link(
    db: Session,
    link_id: int,
    link_update: LinkUpdate,
    base_url: str,
    principal_id: str,
) -> Optional[LinkResponse]:
    query = db.query(Link).filter(Link.id == link_id, Link.created_by == principal_id)
    link = query.first()
    if not link:
        return None

    if link_update.long_url is not None:
        link.long_url = link_update.long_url
    if link_update.expires_at is not None:
        link.expires_at = link_update.expires_at

    db.commit()
    db.refresh(link)

    # Invalidate cache for this short code
    from app.core.cache import cache_service
    cache_service.invalidate_redirect_target(link.code)

    short_url = f"{base_url.rstrip('/')}/r/{link.code}"
    return LinkResponse(
        id=link.id,
        code=link.code,
        short_url=short_url,
        long_url=link.long_url,
        created_by=link.created_by,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


def delete_link(
    db: Session,
    link_id: int,
    principal_id: str,
) -> bool:
    query = db.query(Link).filter(Link.id == link_id, Link.created_by == principal_id)
    link = query.first()
    if not link:
        return False

    code = link.code
    db.delete(link)
    db.commit()

    # Invalidate cache
    from app.core.cache import cache_service
    cache_service.invalidate_redirect_target(code)

    return True


def get_link_by_code(db: Session, code: str) -> Optional[Link]:
    return db.query(Link).filter(Link.code == code).first()


def list_links(
    db: Session,
    base_url: str,
    principal_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> List[LinkResponse]:
    query = db.query(Link)
    if principal_id:
        query = query.filter(Link.created_by == principal_id)
    links = query.order_by(Link.created_at.desc()).offset(skip).limit(limit).all()

    return [
        LinkResponse(
            id=l.id,
            code=l.code,
            short_url=f"{base_url.rstrip('/')}/r/{l.code}",
            long_url=l.long_url,
            tags=l.tags,
            created_by=l.created_by,
            created_at=l.created_at,
            expires_at=l.expires_at,
        )
        for l in links
    ]


def search_links(
    db: Session,
    base_url: str,
    principal_id: str,
    q: Optional[str] = None,
    tag: Optional[str] = None,
    sort_by: str = "created_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> PaginatedLinksResponse:
    """Safe, tenant-scoped search and pagination across links."""
    # Enforce page and page_size bounds (cap at 100)
    if page < 1:
        page = 1
    page_size = min(max(1, page_size), 100)

    # Base query strictly scoped to tenant (defeats IDOR / cross-tenant leakage)
    query = db.query(Link).filter(Link.created_by == principal_id)

    # Search keyword filter across long_url, code, tags
    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Link.long_url.ilike(search_pattern),
                Link.code.ilike(search_pattern),
                Link.tags.ilike(search_pattern),
            )
        )

    # Tag filter
    if tag and tag.strip():
        tag_pattern = f"%{tag.strip()}%"
        query = query.filter(Link.tags.ilike(tag_pattern))

    total = query.count()

    # Allowlisted sorting
    sort_column = Link.created_at
    if sort_by == "created_at":
        sort_column = Link.created_at
    elif sort_by == "code":
        sort_column = Link.code
    elif sort_by == "long_url":
        sort_column = Link.long_url

    if order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # 1-based page to 0-based offset calculation: OFFSET = (page - 1) * page_size
    offset = (page - 1) * page_size
    links = query.offset(offset).limit(page_size).all()

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    items = [
        LinkResponse(
            id=l.id,
            code=l.code,
            short_url=f"{base_url.rstrip('/')}/r/{l.code}",
            long_url=l.long_url,
            tags=l.tags,
            created_by=l.created_by,
            created_at=l.created_at,
            expires_at=l.expires_at,
        )
        for l in links
    ]

    return PaginatedLinksResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )



def record_click(
    db: Session,
    link_id: int,
    user_agent: Optional[str] = None,
    referrer: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> None:
    ip_hash = None
    if client_ip:
        ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()

    click = ClickEvent(
        link_id=link_id,
        user_agent=user_agent[:512] if user_agent else None,
        referrer=referrer[:512] if referrer else None,
        ip_hash=ip_hash,
    )
    db.add(click)
    db.commit()


def get_link_analytics(
    db: Session,
    link_id: int,
    principal_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve click analytics scoped strictly to the link owner.
    Returns None if link does not exist or belongs to another tenant/user.
    """
    link = db.query(Link).filter(Link.id == link_id, Link.created_by == principal_id).first()
    if not link:
        return None

    query = db.query(ClickEvent).filter(ClickEvent.link_id == link_id)
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            if from_dt.tzinfo is None:
                from_dt = from_dt.replace(tzinfo=timezone.utc)
            query = query.filter(ClickEvent.clicked_at >= from_dt)
        except ValueError:
            pass

    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            if to_dt.tzinfo is None:
                to_dt = to_dt.replace(tzinfo=timezone.utc)
            query = query.filter(ClickEvent.clicked_at <= to_dt)
        except ValueError:
            pass

    clicks = query.order_by(ClickEvent.clicked_at.desc()).all()
    total_clicks = len(clicks)
    last_clicked = clicks[0].clicked_at.isoformat() if clicks else None

    return {
        "link_id": link_id,
        "code": link.code,
        "total_clicks": total_clicks,
        "from": from_date,
        "to": to_date,
        "last_clicked_at": last_clicked,
        "clicks": [
            {
                "id": c.id,
                "event_id": c.event_id,
                "clicked_at": c.clicked_at.isoformat() if c.clicked_at else None,
                "user_agent": c.user_agent,
                "referrer": c.referrer,
                "ip_hash": c.ip_hash,
            }
            for c in clicks
        ],
    }


def purge_old_clicks(db: Session, retention_days: int = 30) -> int:
    """Purge click events older than the configured retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted_count = db.query(ClickEvent).filter(ClickEvent.clicked_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return deleted_count

