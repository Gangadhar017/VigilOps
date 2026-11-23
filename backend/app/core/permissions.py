"""Role-based access control.

The permission matrix below is the single source of truth.  Every privileged
endpoint depends on ``require_permission(...)`` so the check is enforced by the
backend, never only by hiding a button in the UI.  Refused attempts are written
to the audit trail.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import AuditOutcome, Role, User

ADMIN = Role.ADMIN.value
OPERATOR = Role.OPERATOR.value

PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "dashboard:view": frozenset({ADMIN, OPERATOR}),
    "monitoring:view": frozenset({ADMIN, OPERATOR}),
    "incidents:view": frozenset({ADMIN, OPERATOR}),
    # acknowledge, start work, resolve with evidence, comment
    "incidents:update": frozenset({ADMIN, OPERATOR}),
    # close and reopen
    "incidents:close": frozenset({ADMIN}),
    "findings:view": frozenset({ADMIN, OPERATOR}),
    "scans:run": frozenset({ADMIN, OPERATOR}),
    "findings:accept_risk": frozenset({ADMIN}),
    "remediation:view": frozenset({ADMIN, OPERATOR}),
    "remediation:request": frozenset({ADMIN, OPERATOR}),
    "remediation:approve": frozenset({ADMIN}),   # approve / reject
    "remediation:execute": frozenset({ADMIN}),   # dispatch / retry
    "remediation:cancel": frozenset({ADMIN, OPERATOR}),  # operators: own requests only
    "audit:view": frozenset({ADMIN, OPERATOR}),   # operators: operational events only
    "audit:view_all": frozenset({ADMIN}),
    "assistant:use": frozenset({ADMIN, OPERATOR}),
    "users:manage": frozenset({ADMIN}),
    "settings:view": frozenset({ADMIN, OPERATOR}),
    "settings:manage": frozenset({ADMIN}),
    "demo:control": frozenset({ADMIN}),
}

PERMISSION_DESCRIPTIONS: Dict[str, str] = {
    "dashboard:view": "View the operations overview",
    "monitoring:view": "View monitoring data and targets",
    "incidents:view": "View and investigate incidents",
    "incidents:update": "Acknowledge, work on, comment on and resolve incidents",
    "incidents:close": "Close or reopen incidents",
    "findings:view": "View security findings and scan history",
    "scans:run": "Run security scans",
    "findings:accept_risk": "Mark a finding as accepted risk",
    "remediation:view": "View remediation requests and results",
    "remediation:request": "Request remediation",
    "remediation:approve": "Approve or reject remediation requests",
    "remediation:execute": "Dispatch approved remediation to the worker and retry failures",
    "remediation:cancel": "Cancel remediation requests (operators: their own)",
    "audit:view": "View operational audit events",
    "audit:view_all": "View all audit events, including sign-ins and administration",
    "assistant:use": "Use the VigilAI assistant",
    "users:manage": "Create, update and deactivate users",
    "settings:view": "View platform configuration",
    "settings:manage": "Change platform settings",
    "demo:control": "Use demonstration controls (demonstration environments only)",
}


def has_permission(user: User, permission: str) -> bool:
    return user.role in PERMISSIONS.get(permission, frozenset())


def permissions_for(role: str) -> List[str]:
    return sorted(name for name, roles in PERMISSIONS.items() if role in roles)


def permission_matrix() -> List[Dict[str, object]]:
    return [
        {
            "permission": name,
            "description": PERMISSION_DESCRIPTIONS.get(name, ""),
            "admin": ADMIN in roles,
            "operator": OPERATOR in roles,
        }
        for name, roles in PERMISSIONS.items()
    ]


def require_permission(permission: str):
    """FastAPI dependency factory enforcing one permission."""
    if permission not in PERMISSIONS:  # fail fast on typos at import time
        raise KeyError(f"Unknown permission '{permission}'")

    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if has_permission(current_user, permission):
            return current_user

        from app.services.audit_service import record_audit

        record_audit(
            db,
            action="ACCESS_DENIED",
            entity_type="permission",
            entity_id=permission,
            actor=current_user,
            outcome=AuditOutcome.DENIED,
            metadata={
                "role": current_user.role,
                "method": request.method,
                "path": request.url.path,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your role ({current_user.role}) is not permitted to perform this action "
            f"({permission}).",
        )

    return dependency
