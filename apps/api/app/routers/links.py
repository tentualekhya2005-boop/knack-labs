from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_principal
from app.core.rate_limit import rate_limit_create_link, rate_limit_analytics
from app.db.session import get_db
from app.schemas.link import (
    LinkCreate,
    LinkResponse,
    LinkUpdate,
    LinkAnalyticsResponse,
    PaginatedLinksResponse,
)
from app.services import links_service

router = APIRouter(prefix="/links", tags=["links"])


@router.post(
    "",
    response_model=LinkResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_create_link)],
)
def create_link(
    link_in: LinkCreate,
    request: Request,
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    base_url = str(request.base_url)
    return links_service.create_link(
        db=db,
        link_in=link_in,
        base_url=base_url,
        principal_id=principal_id,
    )


@router.get("", response_model=List[LinkResponse])
def list_links(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    base_url = str(request.base_url)
    return links_service.list_links(
        db=db,
        base_url=base_url,
        principal_id=principal_id,
        skip=skip,
        limit=limit,
    )


ALLOWED_SORT_FIELDS = {"created_at", "code", "long_url"}
ALLOWED_SORT_ORDERS = {"asc", "desc"}


@router.get("/search", response_model=PaginatedLinksResponse)
def search_links(
    request: Request,
    q: Optional[str] = Query(None, description="Search term for URL, code, or tags"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, description="Page size (capped at 100)"),
    sort_by: str = Query("created_at", description="Sort field: created_at, code, long_url"),
    order: str = Query("desc", description="Sort direction: asc or desc"),
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    if sort_by not in ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sort_by field: '{sort_by}'. Must be one of: {', '.join(sorted(ALLOWED_SORT_FIELDS))}.",
        )
    if order.lower() not in ALLOWED_SORT_ORDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid order: '{order}'. Must be 'asc' or 'desc'.",
        )

    # Hard cap on page_size to prevent DoS memory exhaustion
    capped_page_size = min(page_size, 100)

    base_url = str(request.base_url)
    return links_service.search_links(
        db=db,
        base_url=base_url,
        principal_id=principal_id,
        q=q,
        tag=tag,
        sort_by=sort_by,
        order=order.lower(),
        page=page,
        page_size=capped_page_size,
    )


@router.get("/{id}", response_model=LinkResponse)
def get_link_by_id(
    id: int,
    request: Request,
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    base_url = str(request.base_url)
    link = links_service.get_link_by_id(
        db=db,
        link_id=id,
        base_url=base_url,
        principal_id=principal_id,
    )
    if not link:
        # Chosen strategy: 404 to hide existence and prevent IDOR enumeration
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link with ID {id} not found",
        )
    return link


@router.patch("/{id}", response_model=LinkResponse)
def update_link(
    id: int,
    link_update: LinkUpdate,
    request: Request,
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    base_url = str(request.base_url)
    updated = links_service.update_link(
        db=db,
        link_id=id,
        link_update=link_update,
        base_url=base_url,
        principal_id=principal_id,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link with ID {id} not found",
        )
    return updated


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    id: int,
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    success = links_service.delete_link(
        db=db,
        link_id=id,
        principal_id=principal_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link with ID {id} not found",
        )
    return None


@router.get(
    "/{id}/analytics",
    response_model=LinkAnalyticsResponse,
    dependencies=[Depends(rate_limit_analytics)],
)
def get_link_analytics(
    id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    analytics = links_service.get_link_analytics(
        db=db,
        link_id=id,
        principal_id=principal_id,
        from_date=from_date,
        to_date=to_date,
    )
    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link with ID {id} not found",
        )
    return analytics


@router.post("/maintenance/purge-clicks")
def purge_clicks_endpoint(
    retention_days: int = Query(30, ge=0),
    principal_id: str = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    deleted_count = links_service.purge_old_clicks(db=db, retention_days=retention_days)
    return {"status": "success", "retention_days": retention_days, "deleted_clicks": deleted_count}

