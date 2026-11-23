"""Shared API dependencies and helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import Query


@dataclass
class PageParams:
    page: int
    page_size: int
    sort: Optional[str]
    order: str
    q: Optional[str]


def page_params(
    page: int = Query(1, ge=1, le=100000, description="Page number (1-based)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    sort: Optional[str] = Query(None, max_length=40, description="Field to sort by"),
    order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    q: Optional[str] = Query(None, max_length=120, description="Free-text search"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size, sort=sort, order=order, q=(q or None))


def paged(items, total: int, params: PageParams) -> dict:
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size}
