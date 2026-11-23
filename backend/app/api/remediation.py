"""Remediation workflow APIs.

Requesting is open to Operators and Administrators.  Approving, rejecting,
dispatching and retrying require Administrator permissions, enforced here by
``require_permission`` (HTTP 403 otherwise, with no state change).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, paged
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.models import RemediationRequest, User
from app.schemas.schemas import (
    ExecutionOut,
    Page,
    RemediationCreate,
    RemediationDecision,
    RemediationDetail,
    RemediationOut,
)
from app.services import audit_service, remediation_service
from app.services.dashboard_service import worker_status
from app.services.remediation_catalog import get_action, list_actions

router = APIRouter(prefix="/remediation", tags=["Remediation"])


def _base_fields(db: Session, request: RemediationRequest, user: User) -> Dict[str, Any]:
    action = get_action(request.action_code)
    return {
        "source_id": request.source_id,
        "action_name": action.name if action else None,
        "requested_by_email": request.requester.email if request.requester else None,
        "approved_by_email": request.approver.email if request.approver else None,
        "allowed_operations": remediation_service.allowed_operations(db, user, request),
    }


def _summary(db: Session, request: RemediationRequest, user: User) -> RemediationOut:
    return RemediationOut.model_validate(request).model_copy(update=_base_fields(db, request, user))


def _detail(db: Session, request: RemediationRequest, user: User) -> RemediationDetail:
    action = get_action(request.action_code)
    if request.incident is not None:
        source = {
            "type": "incident",
            "id": request.incident.id,
            "title": request.incident.title,
            "status": request.incident.status,
            "severity": request.incident.severity,
        }
    elif request.finding is not None:
        source = {
            "type": "finding",
            "id": request.finding.id,
            "title": f"{request.finding.rule_id} {request.finding.rule_name}",
            "status": request.finding.status,
            "severity": request.finding.severity,
            "resource": request.finding.resource_identifier,
            "target_file": request.finding.target_file,
        }
    else:
        source = {}
    timeline = [
        {
            "at": event.created_at,
            "action": event.action,
            "actor": event.actor_label,
            "outcome": event.outcome,
            "metadata": event.event_metadata,
        }
        for event in audit_service.correlation_history(db, request.correlation_id)
    ]
    return RemediationDetail.model_validate(request).model_copy(
        update={
            **_base_fields(db, request, user),
            "executions": [ExecutionOut.model_validate(e) for e in request.executions],
            "action": action.as_dict() if action else None,
            "source_summary": source,
            "timeline": timeline,
        }
    )


def _get_or_404(db: Session, request_id: int) -> RemediationRequest:
    request = db.get(RemediationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remediation request not found.")
    return request


def _run(operation, db: Session):
    try:
        return operation()
    except remediation_service.RemediationError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/actions")
def action_catalog(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("remediation:view")),
) -> Dict[str, Any]:
    """The complete allowlist of automated actions and the worker's liveness."""
    return {"actions": list_actions(), "worker": worker_status(db)}


@router.get("/requests", response_model=Page[RemediationOut])
def list_requests(
    params: PageParams = Depends(page_params),
    status_filter: Optional[str] = Query(None, alias="status", max_length=160),
    action_code: Optional[str] = Query(None, max_length=20),
    source_type: Optional[str] = Query(None, max_length=20),
    mine: bool = Query(False, description="Only requests submitted by the current user"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:view")),
) -> Dict[str, Any]:
    items, total = remediation_service.list_requests(
        db,
        page=params.page,
        page_size=params.page_size,
        q=params.q,
        status=status_filter,
        action_code=action_code,
        source_type=source_type,
        requested_by=user.id if mine else None,
        sort=params.sort or "created_at",
        order=params.order,
    )
    return paged([_summary(db, item, user) for item in items], total, params)


@router.post("/requests", response_model=RemediationDetail, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RemediationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:request")),
) -> RemediationDetail:
    """Submit a remediation request.  It always starts in PENDING_APPROVAL."""
    request = _run(
        lambda: remediation_service.create_request(
            db,
            user,
            source_type=payload.source_type,
            source_id=payload.source_id,
            action_code=payload.action_code,
            justification=payload.justification,
        ),
        db,
    )
    return _detail(db, request, user)


@router.get("/requests/{request_id}", response_model=RemediationDetail)
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:view")),
) -> RemediationDetail:
    return _detail(db, _get_or_404(db, request_id), user)


@router.post("/requests/{request_id}/approve", response_model=RemediationDetail)
def approve_request(
    request_id: int,
    payload: RemediationDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:approve")),
) -> RemediationDetail:
    request = _get_or_404(db, request_id)
    _run(lambda: remediation_service.approve(db, user, request, payload.comment), db)
    return _detail(db, request, user)


@router.post("/requests/{request_id}/reject", response_model=RemediationDetail)
def reject_request(
    request_id: int,
    payload: RemediationDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:approve")),
) -> RemediationDetail:
    request = _get_or_404(db, request_id)
    _run(lambda: remediation_service.reject(db, user, request, payload.comment or ""), db)
    return _detail(db, request, user)


@router.post("/requests/{request_id}/execute", response_model=RemediationDetail)
def execute_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:execute")),
) -> RemediationDetail:
    """Dispatch an APPROVED request to the restricted worker (status becomes QUEUED)."""
    request = _get_or_404(db, request_id)
    _run(lambda: remediation_service.execute(db, user, request), db)
    return _detail(db, request, user)


@router.post("/requests/{request_id}/retry", response_model=RemediationDetail)
def retry_request(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:execute")),
) -> RemediationDetail:
    request = _get_or_404(db, request_id)
    _run(lambda: remediation_service.retry(db, user, request), db)
    return _detail(db, request, user)


@router.post("/requests/{request_id}/cancel", response_model=RemediationDetail)
def cancel_request(
    request_id: int,
    payload: RemediationDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("remediation:cancel")),
) -> RemediationDetail:
    request = _get_or_404(db, request_id)
    _run(lambda: remediation_service.cancel(db, user, request, payload.comment), db)
    return _detail(db, request, user)
