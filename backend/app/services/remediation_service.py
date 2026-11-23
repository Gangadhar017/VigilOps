"""Remediation request workflow (API side).

    PENDING_APPROVAL --approve--> APPROVED --execute--> QUEUED --worker--> RUNNING
          |    \\--reject--> REJECTED                                         |
          \\--cancel--> CANCELLED                              VERIFYING <----/
                                                               /        \\
                                                        SUCCEEDED      FAILED --retry--> QUEUED

The API never performs the corrective action itself: it only moves a request to
QUEUED.  Execution and verification happen in the restricted worker process.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.metrics import REMEDIATION_TRANSITIONS
from app.core.permissions import has_permission
from app.models.models import (
    ACTIVE_INCIDENT_STATUSES,
    ACTIVE_REMEDIATION_STATUSES,
    AuditOutcome,
    FindingStatus,
    Incident,
    RemediationRequest,
    RemediationStatus,
    SecurityFinding,
    User,
)
from app.services import incident_service
from app.services.audit_service import record_audit
from app.services.remediation_catalog import (
    action_for_finding,
    action_for_incident,
    get_action,
)
from app.services.settings_service import get_setting
from app.core.config import settings

MIN_JUSTIFICATION = 10


class RemediationError(ValueError):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


def _set_status(request: RemediationRequest, status: RemediationStatus) -> str:
    previous = request.status
    request.status = status.value
    REMEDIATION_TRANSITIONS.labels(status=status.value).inc()
    return previous


def _audit(db: Session, request: RemediationRequest, action: str, actor: Optional[User], **kwargs) -> None:
    metadata = {
        "action_code": request.action_code,
        "target": request.target,
        "source_type": request.source_type,
        "source_id": request.source_id,
        "status": request.status,
    }
    metadata.update(kwargs.pop("metadata", {}) or {})
    record_audit(
        db,
        action=action,
        entity_type="remediation_request",
        entity_id=request.id,
        actor=actor,
        metadata=metadata,
        correlation_id=request.correlation_id,
        **kwargs,
    )


def _incident_event(db: Session, request: RemediationRequest, event_type: str, details: str, actor=None, actor_label=None):
    if request.incident is not None:
        incident_service.add_event(
            db,
            request.incident,
            event_type,
            actor=actor,
            actor_label=actor_label,
            details=details,
            metadata={"remediation_request_id": request.id, "action_code": request.action_code},
        )


def _release_finding(request: RemediationRequest) -> None:
    """A finding whose remediation did not complete goes back to OPEN."""
    finding = request.finding
    if finding is not None and finding.status == FindingStatus.REMEDIATION_PENDING.value:
        finding.status = FindingStatus.OPEN.value


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create_request(
    db: Session,
    actor: User,
    *,
    source_type: str,
    source_id: int,
    action_code: str,
    justification: str,
) -> RemediationRequest:
    action = get_action(action_code)
    if action is None:
        raise RemediationError(
            f"'{action_code}' is not a supported remediation action. Only allowlisted actions "
            "can be requested.",
            422,
        )
    if action.source_type != source_type:
        raise RemediationError(
            f"{action_code} applies to a {action.source_type}, not to a {source_type}.", 422
        )
    justification = justification.strip()
    if len(justification) < MIN_JUSTIFICATION:
        raise RemediationError(
            f"A justification of at least {MIN_JUSTIFICATION} characters is required.", 422
        )

    incident: Optional[Incident] = None
    finding: Optional[SecurityFinding] = None
    if source_type == "incident":
        incident = db.get(Incident, source_id)
        if incident is None:
            raise RemediationError("Incident not found.", 404)
        applicable, reason = action_for_incident(incident)
        target = incident.affected_resource
    else:
        finding = db.get(SecurityFinding, source_id)
        if finding is None:
            raise RemediationError("Security finding not found.", 404)
        applicable, reason = action_for_finding(finding)
        target = f"{finding.target_file}#{finding.resource_identifier}"

    column = RemediationRequest.incident_id if incident else RemediationRequest.finding_id
    existing = (
        db.query(RemediationRequest)
        .filter(column == source_id, RemediationRequest.status.in_(ACTIVE_REMEDIATION_STATUSES))
        .first()
    )
    if existing is not None:
        raise RemediationError(
            f"Remediation request #{existing.id} is already in progress for this {source_type} "
            f"({existing.status})."
        )

    if applicable != action_code:
        raise RemediationError(reason or f"{action_code} cannot be applied to this {source_type}.")

    request = RemediationRequest(
        source_type=source_type,
        incident_id=incident.id if incident else None,
        finding_id=finding.id if finding else None,
        action_code=action_code,
        target=target[:255],
        requested_by=actor.id,
        status=RemediationStatus.PENDING_APPROVAL.value,
        justification=justification,
        max_attempts=settings.REMEDIATION_MAX_ATTEMPTS,
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise RemediationError(f"A remediation request is already in progress for this {source_type}.")

    REMEDIATION_TRANSITIONS.labels(status=request.status).inc()
    if finding is not None:
        finding.status = FindingStatus.REMEDIATION_PENDING.value
        record_audit(
            db,
            action="FINDING_REMEDIATION_PENDING",
            entity_type="finding",
            entity_id=finding.id,
            actor=actor,
            metadata={"remediation_request_id": request.id, "rule_id": finding.rule_id},
            correlation_id=request.correlation_id,
        )
    _incident_event(
        db,
        request,
        "REMEDIATION_REQUESTED",
        f"Remediation request #{request.id} ({action_code}) submitted; awaiting Administrator approval.",
        actor=actor,
    )
    _audit(db, request, "REMEDIATION_REQUESTED", actor, metadata={"justification": justification})
    db.commit()
    return request


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
def _require_status(request: RemediationRequest, *allowed: RemediationStatus) -> None:
    if request.status not in [s.value for s in allowed]:
        expected = " or ".join(s.value for s in allowed)
        raise RemediationError(
            f"Request #{request.id} is {request.status}; this operation requires {expected}."
        )


def approve(db: Session, actor: User, request: RemediationRequest, comment: Optional[str]) -> RemediationRequest:
    _require_status(request, RemediationStatus.PENDING_APPROVAL)
    if request.requested_by == actor.id and not get_setting(db, "remediation.allow_self_approval"):
        _audit(
            db,
            request,
            "REMEDIATION_APPROVAL_DENIED",
            actor,
            outcome=AuditOutcome.DENIED,
            metadata={"reason": "self-approval is not permitted"},
        )
        db.commit()
        raise RemediationError(
            "You cannot approve a remediation request that you submitted yourself. "
            "Another Administrator must review it.",
            403,
        )
    _set_status(request, RemediationStatus.APPROVED)
    request.approver = actor
    request.decided_at = utcnow()
    request.decision_comment = (comment or "").strip() or None
    _incident_event(db, request, "REMEDIATION_APPROVED", f"Remediation request #{request.id} approved.", actor=actor)
    _audit(db, request, "REMEDIATION_APPROVED", actor, metadata={"comment": request.decision_comment})
    db.commit()
    return request


def reject(db: Session, actor: User, request: RemediationRequest, comment: str) -> RemediationRequest:
    _require_status(request, RemediationStatus.PENDING_APPROVAL)
    comment = (comment or "").strip()
    if len(comment) < 5:
        raise RemediationError("A reason is required when rejecting a remediation request.", 422)
    _set_status(request, RemediationStatus.REJECTED)
    request.approver = actor
    request.decided_at = utcnow()
    request.completed_at = request.decided_at
    request.decision_comment = comment
    _release_finding(request)
    _incident_event(db, request, "REMEDIATION_REJECTED", f"Remediation request #{request.id} rejected: {comment}", actor=actor)
    _audit(db, request, "REMEDIATION_REJECTED", actor, metadata={"comment": comment})
    db.commit()
    return request


def execute(db: Session, actor: User, request: RemediationRequest) -> RemediationRequest:
    """Dispatch an approved request to the restricted worker."""
    _require_status(request, RemediationStatus.APPROVED)
    _set_status(request, RemediationStatus.QUEUED)
    request.queued_at = utcnow()
    _incident_event(db, request, "REMEDIATION_QUEUED", f"Remediation request #{request.id} queued for the worker.", actor=actor)
    _audit(db, request, "REMEDIATION_QUEUED", actor)
    db.commit()
    return request


def cancel(db: Session, actor: User, request: RemediationRequest, reason: Optional[str]) -> RemediationRequest:
    _require_status(request, RemediationStatus.PENDING_APPROVAL, RemediationStatus.APPROVED)
    if request.requested_by != actor.id and not has_permission(actor, "remediation:approve"):
        record_denied(db, actor, request.id, "cancel")
        raise RemediationError("Operators can only cancel their own remediation requests.", 403)
    _set_status(request, RemediationStatus.CANCELLED)
    request.completed_at = utcnow()
    request.failure_reason = (reason or "").strip() or "Cancelled by user."
    _release_finding(request)
    _incident_event(db, request, "REMEDIATION_CANCELLED", f"Remediation request #{request.id} cancelled.", actor=actor)
    _audit(db, request, "REMEDIATION_CANCELLED", actor, metadata={"reason": request.failure_reason})
    db.commit()
    return request


def retry(db: Session, actor: User, request: RemediationRequest) -> RemediationRequest:
    """Re-queue a FAILED request (bounded number of attempts)."""
    _require_status(request, RemediationStatus.FAILED)
    if request.attempt_count >= request.max_attempts:
        raise RemediationError(
            f"Request #{request.id} has used all {request.max_attempts} attempts. "
            "Submit a new request after investigating the failure."
        )
    if request.incident is not None and request.incident.status not in ACTIVE_INCIDENT_STATUSES:
        raise RemediationError(f"The incident is already {request.incident.status}.")
    if request.finding is not None:
        if request.finding.status != FindingStatus.OPEN.value:
            raise RemediationError(
                f"The finding is {request.finding.status}; only OPEN findings can be remediated."
            )
        request.finding.status = FindingStatus.REMEDIATION_PENDING.value
    _set_status(request, RemediationStatus.QUEUED)
    request.queued_at = utcnow()
    request.completed_at = None
    request.failure_reason = None
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise RemediationError("Another remediation request is already in progress for this source.")
    _incident_event(db, request, "REMEDIATION_RETRY", f"Remediation request #{request.id} re-queued (attempt {request.attempt_count + 1}).", actor=actor)
    _audit(db, request, "REMEDIATION_RETRY_QUEUED", actor, metadata={"next_attempt": request.attempt_count + 1})
    db.commit()
    return request


def record_denied(db: Session, actor: User, request_id: int, operation: str) -> None:
    """Audit a privileged operation that RBAC refused."""
    record_audit(
        db,
        action="REMEDIATION_OPERATION_DENIED",
        entity_type="remediation_request",
        entity_id=request_id,
        actor=actor,
        outcome=AuditOutcome.DENIED,
        metadata={"operation": operation, "role": actor.role},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
_SORT = {
    "id": RemediationRequest.id,
    "created_at": RemediationRequest.created_at,
    "status": RemediationRequest.status,
    "action_code": RemediationRequest.action_code,
    "completed_at": RemediationRequest.completed_at,
}


def list_requests(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    q: Optional[str] = None,
    status: Optional[str] = None,
    action_code: Optional[str] = None,
    source_type: Optional[str] = None,
    requested_by: Optional[int] = None,
    sort: str = "created_at",
    order: str = "desc",
) -> Tuple[List[RemediationRequest], int]:
    query = db.query(RemediationRequest)
    if status:
        query = query.filter(
            RemediationRequest.status.in_([s.strip().upper() for s in status.split(",")])
        )
    if action_code:
        query = query.filter(RemediationRequest.action_code == action_code.upper())
    if source_type:
        query = query.filter(RemediationRequest.source_type == source_type.lower())
    if requested_by:
        query = query.filter(RemediationRequest.requested_by == requested_by)
    if q:
        text = q.strip().lower()
        pattern = f"%{text}%"
        conditions = [
            func.lower(RemediationRequest.target).like(pattern),
            func.lower(RemediationRequest.justification).like(pattern),
            func.lower(RemediationRequest.action_code).like(pattern),
        ]
        if text.lstrip("#").isdigit():
            conditions.append(RemediationRequest.id == int(text.lstrip("#")))
        query = query.filter(or_(*conditions))
    total = query.count()
    column = _SORT.get(sort, RemediationRequest.created_at)
    ordering = column.asc() if order == "asc" else column.desc()
    items = (
        query.order_by(ordering, RemediationRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def allowed_operations(db: Session, actor: User, request: RemediationRequest) -> List[str]:
    """Which workflow buttons the current user may use (the API re-checks each one)."""
    operations: List[str] = []
    is_admin = has_permission(actor, "remediation:approve")
    status = request.status
    if status == RemediationStatus.PENDING_APPROVAL.value:
        if is_admin:
            self_blocked = request.requested_by == actor.id and not get_setting(
                db, "remediation.allow_self_approval"
            )
            if not self_blocked:
                operations.append("approve")
            operations.append("reject")
        if is_admin or request.requested_by == actor.id:
            operations.append("cancel")
    elif status == RemediationStatus.APPROVED.value:
        if is_admin:
            operations.append("execute")
        if is_admin or request.requested_by == actor.id:
            operations.append("cancel")
    elif status == RemediationStatus.FAILED.value:
        if is_admin and request.attempt_count < request.max_attempts:
            operations.append("retry")
    return operations
