"""Demonstration controls.

These routes exist only to drive the demo (controlled outage, sample
configuration reset).  They return HTTP 404 unless demo controls are active -
which in production mode needs the explicit hosted-demonstration opt-in - and
they require Administrator rights.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import has_permission, require_permission
from app.models.models import User
from app.schemas.schemas import FaultRequest, ScanOut
from app.services import demo_service, scan_service

router = APIRouter(prefix="/demo", tags=["Demo controls"])


def _guard() -> None:
    try:
        demo_service.ensure_enabled()
    except demo_service.DemoError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("/status")
def demo_status(user: User = Depends(require_permission("settings:view"))) -> Dict[str, Any]:
    """Whether demo controls are available and (for Administrators) the demo app's fault state."""
    enabled = settings.demo_controls_active
    state = demo_service.demo_app_state() if enabled and has_permission(user, "demo:control") else None
    return {
        "enabled": enabled,
        "environment": settings.ENVIRONMENT,
        "fault_modes": demo_service.available_fault_modes() if enabled else {},
        "disabled_fault_modes": settings.disabled_fault_modes if enabled else [],
        "demo_app": state,
        "demo_app_reachable": state is not None if enabled else None,
    }


@router.post("/faults")
def inject_fault(
    payload: FaultRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("demo:control")),
) -> Dict[str, Any]:
    """Inject (or clear) a controlled fault on the demonstration application."""
    _guard()
    try:
        state = demo_service.inject_fault(db, user, payload.mode)
    except demo_service.DemoError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {"status": "applied", "simulated": True, "demo_app": state}


@router.post("/reset-config")
def reset_sample_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("demo:control")),
) -> Dict[str, Any]:
    """Restore the insecure sample configuration (done by the worker) and re-scan it."""
    _guard()
    task = demo_service.reset_sample_config(db, user)
    if task is None or task.status != "SUCCEEDED":
        detail = (
            task.error
            if task is not None and task.status == "FAILED"
            else "The remediation worker did not complete the reset in time. Is the worker running?"
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    scan = scan_service.run_scan(db, actor=user, target=None, trigger="DEMO_RESET")
    return {
        "status": "reset",
        "simulated": True,
        "restored_files": task.details.get("restored_files", []),
        "scan": ScanOut.model_validate(scan).model_dump(mode="json"),
    }
