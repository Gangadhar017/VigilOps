"""Incident management APIs."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, paged
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.models import Incident, User
from app.schemas.schemas import (
    IncidentComment,
    IncidentDetail,
    IncidentEventOut,
    IncidentOut,
    IncidentTransition,
    Page,
)
from app.services import incident_service
from app.services.recommendations import incident_recommendation

router = APIRouter(prefix="/incidents", tags=["Incidents"])


def _summary(incident: Incident) -> IncidentOut:
    return IncidentOut.model_validate(incident).model_copy(
        update={"signal_stale": incident_service.signal_is_stale(incident)}
    )


def _detail(incident: Incident, user: User) -> IncidentDetail:
    return IncidentDetail.model_validate(incident).model_copy(
        update={
            "signal_stale": incident_service.signal_is_stale(incident),
            "recommendation": incident_recommendation(incident),
            "allowed_transitions": incident_service.allowed_transitions(user, incident),
        }
    )


def _get_or_404(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    return incident


@router.get("", response_model=Page[IncidentOut])
def list_incidents(
    params: PageParams = Depends(page_params),
    status_filter: Optional[str] = Query(None, alias="status", max_length=80, description="Comma-separated statuses"),
    severity: Optional[str] = Query(None, max_length=60, description="Comma-separated severities"),
    active_only: bool = Query(False, description="Only OPEN / ACKNOWLEDGED / IN_PROGRESS"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("incidents:view")),
) -> Dict[str, Any]:
    items, total = incident_service.list_incidents(
        db,
        page=params.page,
        page_size=params.page_size,
        q=params.q,
        status=status_filter,
        severity=severity,
        active_only=active_only,
        sort=params.sort or "detected_at",
        order=params.order,
    )
    return paged([_summary(item) for item in items], total, params)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:view")),
) -> IncidentDetail:
    return _detail(_get_or_404(db, incident_id), user)


@router.post("/{incident_id}/transition", response_model=IncidentDetail)
def transition_incident(
    incident_id: int,
    payload: IncidentTransition,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:update")),
) -> IncidentDetail:
    """Move an incident through its lifecycle.  Invalid transitions return HTTP 409."""
    incident = _get_or_404(db, incident_id)
    try:
        incident = incident_service.transition_incident(
            db, user, incident, payload.status, payload.note, payload.override_monitoring
        )
    except incident_service.IncidentError as exc:
        db.rollback()
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            incident_service.record_denied_transition(db, user, _get_or_404(db, incident_id), payload.status, str(exc))
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return _detail(incident, user)


@router.post("/{incident_id}/comments", response_model=IncidentEventOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    incident_id: int,
    payload: IncidentComment,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("incidents:update")),
):
    incident = _get_or_404(db, incident_id)
    return incident_service.add_comment(db, user, incident, payload.note)
