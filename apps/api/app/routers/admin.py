from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.link import Link
from app.schemas.link import LinkResponse

router = APIRouter(prefix="/api/admin/links", tags=["admin"])


@router.get("", response_model=List[LinkResponse])
def get_admin_links(
    request: Request,
    page: int = Query(1, ge=1, description="1-based page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Admin link listing endpoint.
    NOTE: Currently has Bug #2 injected:
    1. Incorrect offset calculation: page * limit (skips first page items and duplicates boundary)
    2. Missing deterministic ORDER BY clause.
    """
    # Fixed Bug #2: Deterministic ordering and zero-indexed offset calculation
    offset = (page - 1) * limit
    links = db.query(Link).order_by(Link.id.asc()).offset(offset).limit(limit).all()

    base_url = str(request.base_url)
    return [
        LinkResponse(
            id=link.id,
            code=link.code,
            short_url=f"{base_url.rstrip('/')}/r/{link.code}",
            long_url=link.long_url,
            tags=link.tags,
            created_by=link.created_by,
            created_at=link.created_at,
            expires_at=link.expires_at,
        )
        for link in links
    ]


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_link(
    link_id: int,
    db: Session = Depends(get_db),
):
    link = db.query(Link).filter(Link.id == link_id).first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link with id {link_id} not found",
        )
    db.delete(link)
    db.commit()
    return None
