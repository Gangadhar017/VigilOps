"""Audit trail APIs (read-only: there is no endpoint that edits or deletes audit history)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, paged
from app.core.database import get_db
from app.core.permissions import has_permission, require_permission
from app.models.models import AuditEvent, User
from app.schemas.schemas import AuditEventOut, Page
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])

CATEGORIES = [
    {"key": "AUTH", "label": "Authentication"},
    {"key": "INCIDENT", "label": "Incidents"},
    {"key": "SECURITY_SCAN", "label": "Security scans"},
    {"key": "FINDING", "label": "Findings"},
    {"key": "REMEDIATION", "label": "Remediation"},
    {"key": "USER", "label": "User administration"},
    {"key": "SETTINGS", "label": "Settings"},
    {"key": "ACCESS", "label": "Access denied"},
    {"key": "ASSISTANT", "label": "VigilAI"},
    {"key": "DEMO", "label": "Demo controls"},
]


@router.get("/events", response_model=Page[AuditEventOut])
def list_events(
    params: PageParams = Depends(page_params),
    action: Optional[str] = Query(None, max_length=80),
    category: Optional[str] = Query(None, max_length=40, description="Action prefix, e.g. REMEDIATION"),
    outcome: Optional[str] = Query(None, max_length=20),
    entity_type: Optional[str] = Query(None, max_length=50),
    entity_id: Optional[str] = Query(None, max_length=64),
    correlation_id: Optional[str] = Query(None, max_length=64),
    actor: Optional[str] = Query(None, max_length=120),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit:view")),
) -> Dict[str, Any]:
    items, total = audit_service.list_audit_events(
        db,
        user,
        page=params.page,
        page_size=params.page_size,
        q=params.q,
        action=action,
        category=category,
        outcome=outcome,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=correlation_id,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
        sort=params.sort or "created_at",
        order=params.order,
    )
    return paged(items, total, params)


@router.get("/meta")
def audit_meta(user: User = Depends(require_permission("audit:view"))) -> Dict[str, Any]:
    full = has_permission(user, "audit:view_all")
    return {
        "categories": CATEGORIES,
        "outcomes": ["SUCCESS", "FAILURE", "DENIED"],
        "visibility": "all" if full else "operational",
        "visibility_note": (
            "You can see every audit event."
            if full
            else "Your role shows operational events (incidents, scans, findings, remediation) "
            "and your own activity (such as sign-ins)."
        ),
    }


@router.get("/events/{event_pk}", response_model=AuditEventOut)
def get_event(
    event_pk: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("audit:view")),
) -> AuditEvent:
    event = audit_service.get_audit_event(db, user, event_pk)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit event not found.")
    return event
