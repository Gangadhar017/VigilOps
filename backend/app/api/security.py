"""Security scanner APIs: rules, authorised targets, scans and findings."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, paged
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.models import SecurityFinding, SecurityScan, User
from app.schemas.schemas import (
    AcceptRiskRequest,
    FindingDetail,
    FindingOut,
    Page,
    RemediationBrief,
    ScanOut,
    ScanRequest,
)
from app.security_scanner.rules import get_rule, get_rules
from app.services import audit_service, scan_service
from app.services.recommendations import finding_recommendation

router = APIRouter(prefix="/security", tags=["Security"])

SCOPE_NOTICE = (
    "The scanner evaluates authorised local YAML configuration files in the scan workspace "
    "against rules SEC-001 to SEC-005. It does not assess a live cloud account."
)


def _finding_detail(db: Session, finding: SecurityFinding) -> FindingDetail:
    rule = get_rule(finding.rule_id)
    history = [
        {
            "at": event.created_at,
            "action": event.action,
            "actor": event.actor_label,
            "outcome": event.outcome,
            "metadata": event.event_metadata,
        }
        for event in audit_service.entity_history(db, "finding", finding.id)
    ]
    return FindingDetail.model_validate(finding).model_copy(
        update={
            "rule": rule.as_dict() if rule else None,
            "guidance": finding_recommendation(finding),
            "remediation_requests": [
                RemediationBrief.model_validate(request) for request in finding.remediation_requests
            ],
            "history": history,
        }
    )


def _finding_or_404(db: Session, finding_id: int) -> SecurityFinding:
    finding = db.get(SecurityFinding, finding_id)
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Security finding not found.")
    return finding


@router.get("/rules")
def list_rules(_user: User = Depends(require_permission("findings:view"))) -> Dict[str, Any]:
    return {"scope": SCOPE_NOTICE, "rules": [rule.as_dict() for rule in get_rules()]}


@router.get("/targets")
def list_targets(_user: User = Depends(require_permission("findings:view"))) -> Dict[str, Any]:
    """Configuration files that may be scanned (the authorised scan workspace)."""
    return {"scope": SCOPE_NOTICE, "targets": scan_service.list_targets()}


@router.get("/targets/{name}")
def read_target(name: str, _user: User = Depends(require_permission("findings:view"))) -> Dict[str, Any]:
    try:
        return scan_service.read_target(name)
    except scan_service.ScanTargetError as exc:
        code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc))


@router.post("/scans", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
def run_scan(
    payload: ScanRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("scans:run")),
) -> SecurityScan:
    """Scan one authorised target, or every file in the workspace when no target is given."""
    if payload.target is not None:
        try:
            scan_service.resolve_target(payload.target)
        except scan_service.ScanTargetError as exc:
            code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=code, detail=str(exc))
    return scan_service.run_scan(db, actor=user, target=payload.target, trigger="MANUAL")


@router.get("/scans", response_model=Page[ScanOut])
def list_scans(
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("findings:view")),
) -> Dict[str, Any]:
    items, total = scan_service.list_scans(db, page=params.page, page_size=params.page_size)
    return paged(items, total, params)


@router.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("findings:view")),
) -> SecurityScan:
    scan = db.get(SecurityScan, scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return scan


@router.get("/findings", response_model=Page[FindingOut])
def list_findings(
    params: PageParams = Depends(page_params),
    status_filter: Optional[str] = Query(None, alias="status", max_length=120),
    severity: Optional[str] = Query(None, max_length=60),
    rule_id: Optional[str] = Query(None, max_length=20),
    target_file: Optional[str] = Query(None, max_length=130),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("findings:view")),
) -> Dict[str, Any]:
    items, total = scan_service.list_findings(
        db,
        page=params.page,
        page_size=params.page_size,
        q=params.q,
        status=status_filter,
        severity=severity,
        rule_id=rule_id,
        target_file=target_file,
        sort=params.sort or "severity",
        order=params.order if params.sort else "asc",
    )
    return paged(items, total, params)


@router.get("/findings/{finding_id}", response_model=FindingDetail)
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("findings:view")),
) -> FindingDetail:
    return _finding_detail(db, _finding_or_404(db, finding_id))


@router.post("/findings/{finding_id}/accept-risk", response_model=FindingDetail)
def accept_risk(
    finding_id: int,
    payload: AcceptRiskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("findings:accept_risk")),
) -> FindingDetail:
    finding = _finding_or_404(db, finding_id)
    try:
        scan_service.accept_risk(db, user, finding, payload.reason.strip())
    except scan_service.FindingStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _finding_detail(db, finding)


@router.post("/findings/{finding_id}/revoke-risk-acceptance", response_model=FindingDetail)
def revoke_risk_acceptance(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("findings:accept_risk")),
) -> FindingDetail:
    finding = _finding_or_404(db, finding_id)
    try:
        scan_service.revoke_risk_acceptance(db, user, finding)
    except scan_service.FindingStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _finding_detail(db, finding)
