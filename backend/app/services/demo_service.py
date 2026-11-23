"""Controls for the local demonstration environment.

Everything here is refused unless ``settings.demo_controls_active`` is true.
In production mode that requires the explicit opt-in for a hosted demonstration
instance (``ALLOW_DEMO_CONTROLS_IN_PRODUCTION``); otherwise it is never the case.

* Fault injection talks to the demo application's token-protected control API.
* Resetting the sample configuration is queued for the restricted worker,
  because the API container only has read access to the scan workspace.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import AuditOutcome, DemoTask, User
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)

FAULT_MODES = {
    "none": "No fault - normal operation.",
    "outage": "Service outage: every service endpoint and /metrics answer HTTP 503.",
    "errors": "Error burst: the business endpoint answers HTTP 500 for most requests.",
    "latency": "Slow responses: the business endpoint takes about 1.5 seconds.",
    "cpu": "CPU saturation: a bounded background thread keeps one core busy.",
    "memory": "Memory pressure: the service allocates a bounded block of memory.",
}
RESET_TASK = "RESET_SAMPLE_CONFIG"


class DemoError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def ensure_enabled() -> None:
    if not settings.demo_controls_active:
        raise DemoError("Demonstration controls are disabled in this environment.", status_code=404)


def available_fault_modes() -> Dict[str, str]:
    """Fault modes offered by this deployment (DEMO_DISABLED_FAULTS removes some)."""
    disabled = settings.disabled_fault_modes
    return {mode: text for mode, text in FAULT_MODES.items() if mode not in disabled}


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {settings.DEMO_APP_CONTROL_TOKEN}"}


def demo_app_state(timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """Current fault state reported by the demo app, or None if it cannot be read."""
    if not settings.demo_controls_active or not settings.DEMO_APP_CONTROL_TOKEN:
        return None
    try:
        response = httpx.get(
            f"{settings.DEMO_APP_URL}/internal/state", headers=_headers(), timeout=timeout
        )
        if response.status_code == 200:
            return response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return None


def active_fault_marker() -> Optional[str]:
    """Describe the controlled fault currently active on the demo app, if any."""
    state = demo_app_state()
    if not state:
        return None
    mode = state.get("fault_mode")
    if mode and mode != "none":
        return f"Controlled demo fault '{mode}' was active when this alert fired."
    return None


def inject_fault(db: Session, actor: User, mode: str) -> Dict[str, Any]:
    ensure_enabled()
    if mode not in FAULT_MODES:
        raise DemoError("Unknown fault mode.", status_code=422)
    if mode in settings.disabled_fault_modes:
        raise DemoError(
            f"The '{mode}' fault is switched off in this deployment because the host "
            "does not have the resources to run it.",
            status_code=422,
        )
    try:
        response = httpx.post(
            f"{settings.DEMO_APP_URL}/internal/fault",
            json={"mode": mode},
            headers=_headers(),
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        record_audit(
            db,
            action="DEMO_FAULT_INJECTED",
            entity_type="demo_app",
            entity_id=settings.DEMO_APP_JOB,
            actor=actor,
            outcome=AuditOutcome.FAILURE,
            metadata={"mode": mode, "error": exc.__class__.__name__},
        )
        db.commit()
        raise DemoError("The demonstration application could not be reached.") from exc

    ok = response.status_code == 200
    record_audit(
        db,
        action="DEMO_FAULT_CLEARED" if mode == "none" else "DEMO_FAULT_INJECTED",
        entity_type="demo_app",
        entity_id=settings.DEMO_APP_JOB,
        actor=actor,
        outcome=AuditOutcome.SUCCESS if ok else AuditOutcome.FAILURE,
        metadata={"mode": mode, "simulated": True, "http_status": response.status_code},
    )
    db.commit()
    if not ok:
        raise DemoError(f"The demonstration application rejected the request (HTTP {response.status_code}).")
    return response.json()


def reset_sample_config(db: Session, actor: User, wait_seconds: float = 20.0) -> DemoTask:
    """Queue a reset of the sample configuration and wait for the worker to do it."""
    ensure_enabled()
    task = DemoTask(task_type=RESET_TASK, requested_by=actor.id, status="QUEUED")
    db.add(task)
    record_audit(
        db,
        action="DEMO_CONFIG_RESET_REQUESTED",
        entity_type="demo_task",
        entity_id=None,
        actor=actor,
        metadata={"simulated": True},
    )
    db.commit()
    task_id = task.id

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        time.sleep(0.5)
        with SessionLocal() as poll:
            current = poll.get(DemoTask, task_id)
            if current is not None and current.status in ("SUCCEEDED", "FAILED"):
                break
    db.expire_all()
    task = db.get(DemoTask, task_id)
    return task
