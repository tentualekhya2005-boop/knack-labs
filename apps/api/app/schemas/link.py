from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.parse import urlsplit
import re
from pydantic import BaseModel, Field, field_validator, ConfigDict


def validate_long_url(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError("URL must be a string")

    # Reject control characters (ASCII 0-31 and 127, including \n, \r, \t)
    if any(ord(c) < 32 or ord(c) == 127 for c in v):
        raise ValueError("URL contains illegal control characters")

    stripped = v.strip()
    if not stripped:
        raise ValueError("URL cannot be empty")

    # Reject backslashes
    if "\\" in stripped:
        raise ValueError("URL cannot contain backslashes")

    try:
        parsed = urlsplit(stripped)
    except Exception as e:
        raise ValueError(f"Invalid URL structure: {e}")

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{scheme}'. Only 'http' and 'https' are allowed.")

    if not parsed.netloc:
        raise ValueError("URL must have a valid host / netloc")

    # Reject userinfo (user@host) trick
    if "@" in parsed.netloc or parsed.username or parsed.password:
        raise ValueError("URLs with userinfo (credentials or '@') are not allowed")

    if not parsed.hostname:
        raise ValueError("URL host cannot be empty")

    return stripped


class LinkCreate(BaseModel):
    long_url: str
    code: Optional[str] = Field(None, min_length=3, max_length=32)
    created_by: Optional[str] = Field("default", max_length=128)
    expires_at: Optional[datetime] = None
    tags: Optional[List[str]] = Field(None)

    @field_validator("long_url")
    @classmethod
    def check_long_url(cls, v: str) -> str:
        return validate_long_url(v)

    @field_validator("code")
    @classmethod
    def check_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not re.match(r"^[a-zA-Z0-9_-]+$", v):
                raise ValueError("Short code must only contain letters, numbers, underscores, or hyphens")
            return v
        return v

    @field_validator("expires_at")
    @classmethod
    def check_expires_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            now = datetime.now(timezone.utc)
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v <= now:
                raise ValueError("expires_at must be in the future")
        return v

    @field_validator("tags")
    @classmethod
    def check_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if len(v) > 10:
                raise ValueError("A maximum of 10 tags is allowed")
            for tag in v:
                if len(tag) > 32:
                    raise ValueError("Tag length cannot exceed 32 characters")
        return v


class LinkUpdate(BaseModel):
    long_url: Optional[str] = None
    expires_at: Optional[datetime] = None

    @field_validator("long_url")
    @classmethod
    def check_long_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_long_url(v)
        return v


class LinkResponse(BaseModel):
    id: int
    code: str
    short_url: str
    long_url: str
    tags: Optional[List[str]] = None
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v


class PaginatedLinksResponse(BaseModel):
    items: List[LinkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int



class ClickEventResponse(BaseModel):
    id: int
    event_id: Optional[str] = None
    clicked_at: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    ip_hash: Optional[str] = None


class LinkAnalyticsResponse(BaseModel):
    link_id: int
    code: str
    total_clicks: int
    from_date: Optional[str] = Field(None, alias="from")
    to_date: Optional[str] = Field(None, alias="to")
    last_clicked_at: Optional[str] = None
    clicks: List[ClickEventResponse] = []

    model_config = ConfigDict(populate_by_name=True)


