"""Request models and validation for the EMEIA dashboard."""

from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

MAX_URL_LENGTH = 2000


def validate_http_url(value: str) -> str:
    """Accept only absolute http(s) URLs without control characters."""
    if len(value) > MAX_URL_LENGTH or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("URL is too long or contains control characters")
    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("Only absolute http and https URLs are allowed")
    return parts.geturl()


def current_period(today: Optional[date] = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    return f"{today.year}-Q{(today.month - 1) // 3 + 1}"


def period_bounds(period: str) -> tuple[str, str]:
    """Inclusive ISO date bounds for a period such as 2026-Q4."""
    year, quarter = int(period[:4]), int(period[-1])
    first_month = 3 * (quarter - 1) + 1
    start = date(year, first_month, 1)
    next_start = date(year + (first_month + 3 > 12), (first_month + 2) % 12 + 1, 1)
    return start.isoformat(), (next_start - timedelta(days=1)).isoformat()


class TargetCreate(BaseModel):
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    objective: str = Field(min_length=1, max_length=200)
    key_result: str = Field(min_length=1, max_length=200)
    target_value: float = Field(gt=0)
    current_value: float = Field(default=0, ge=0)
    unit: str = Field(default="", max_length=40)
    owner: str = Field(default="", max_length=120)


class TargetUpdate(BaseModel):
    current_value: float = Field(ge=0)


class WinCreate(BaseModel):
    customer: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    value: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="", pattern=r"^([A-Z]{3})?$")
    won_on: date

    @field_validator("won_on")
    @classmethod
    def not_far_in_future(cls, value: date) -> date:
        if value > datetime.now(timezone.utc).date() + timedelta(days=1):
            raise ValueError("won_on cannot be more than one day in the future")
        return value


class MarketItemCreate(BaseModel):
    kind: Literal["market", "competitor"]
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=2000)
    source_url: Optional[str] = None

    @field_validator("source_url")
    @classmethod
    def http_only(cls, value: Optional[str]) -> Optional[str]:
        return validate_http_url(value) if value else None


class MarketItemReview(BaseModel):
    reviewed: Literal[True]


class ToolLinkCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    url: str

    @field_validator("url")
    @classmethod
    def http_only(cls, value: str) -> str:
        return validate_http_url(value)
