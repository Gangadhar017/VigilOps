"""Restricted remediation worker.

Runs as its own process/container:

    python -m app.workers.remediation_worker

Isolation properties
--------------------
* No inbound network port - it only polls the database queue.
* It is the only component with write access to the scan workspace and the
  only one that holds the demo application's recovery token.
* It executes nothing but the hard-coded handlers in ``actions.py``, and only
  for requests that an Administrator approved and dispatched (status QUEUED).
"""
from __future__ import annotations

import concurrent.futures
import logging
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.core.logging import configure_logging
from app.core.metrics import REMEDIATION_TRANSITIONS
from app.models.models import (
    AuditOutcome,
    DemoTask,
    FindingStatus,
    RemediationExecution,
    RemediationRequest,
    RemediationStatus,
    WorkerHeartbeat,
)
from app.services import incident_service
from app.services.audit_service import record_audit
from app.services.demo_service import RESET_TASK
from app.workers.actions import HANDLERS, ActionError, ActionParams, atomic_write
from app.workers.verification import VERIFIERS, VerificationResult

logger = logging.getLogger("vigilops.worker")

_stop = False


def _request_stop(*_args) -> None:  # pragma: no cover - signal handler
    global _stop
    _stop = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _audit(db: Session, request: RemediationRequest, action: str, outcome=AuditOutcome.SUCCESS, **metadata) -> None:
    record_audit(
        db,
        action=action,
        entity_type="remediation_request",
        entity_id=request.id,
        actor_label=settings.WORKER_ID,
        outcome=outcome,
        metadata={
            "action_code": request.action_code,
            "target": request.target,
            "attempt": request.attempt_count,
            **metadata,
        },
        correlation_id=request.correlation_id,
    )


def _set_status(request: RemediationRequest, status: RemediationStatus) -> None:
    request.status = status.value
    REMEDIATION_TRANSITIONS.labels(status=status.value).inc()


def _incident_event(db: Session, request: RemediationRequest, event_type: str, details: str, metadata: Optional[dict] = None) -> None:
    if request.incident is not None:
        incident_service.add_event(
            db,
            request.incident,
            event_type,
            actor_label=settings.WORKER_ID,
            details=details,
            metadata={"remediation_request_id": request.id, **(metadata or {})},
        )


def _release_finding(request: RemediationRequest) -> None:
    """The problem is not fixed: a finding waiting on this request returns to OPEN."""
    if request.finding is not None and request.finding.status == FindingStatus.REMEDIATION_PENDING.value:
        request.finding.status = FindingStatus.OPEN.value


def _build_params(request: RemediationRequest) -> ActionParams:
    """Parameters come exclusively from trusted database records."""
    if request.finding is not None:
        return ActionParams(
            request_id=request.id,
            action_code=request.action_code,
            target_file=request.finding.target_file,
            resource_type=request.finding.resource_type,
            resource_name=request.finding.resource_name,
        )
    return ActionParams(
        request_id=request.id,
        action_code=request.action_code,
        alert_name=request.incident.alert_name if request.incident else None,
    )


def _run_with_timeout(handler, params: ActionParams, timeout: float) -> Dict[str, Any]:
    # A Python thread cannot be killed, so on timeout the handler is abandoned,
    # not stopped.  Handlers therefore only do bounded I/O (every HTTP call has a
    # timeout and retries are capped), which keeps their worst case below
    # ACTION_TIMEOUT_SECONDS.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="action")
    future = executor.submit(handler, params)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError as exc:
        raise ActionError(f"The action exceeded its {timeout:.0f}s execution timeout.", retryable=True) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# ---------------------------------------------------------------------------
# Queue handling
# ---------------------------------------------------------------------------
def claim_next(db: Session) -> Optional[int]:
    """Atomically claim the oldest QUEUED request.  Returns the execution id."""
    statement = (
        select(RemediationRequest)
        .where(RemediationRequest.status == RemediationStatus.QUEUED.value)
        .order_by(RemediationRequest.queued_at, RemediationRequest.id)
        .limit(1)
        # Lock only the request row: the eagerly joined user rows sit on the
        # nullable side of an outer join, which PostgreSQL cannot lock.
        .with_for_update(skip_locked=True, of=RemediationRequest)
    )
    request = db.execute(statement).scalars().first()
    if request is None:
        db.rollback()
        return None

    # State validation: only dispatched requests with a recorded approval may run.
    if request.approved_by is None:
        _set_status(request, RemediationStatus.FAILED)
        request.failure_reason = "Refused: the request has no recorded approval."
        request.completed_at = utcnow()
        request.attempt_count = request.max_attempts  # a refused request can never be retried
        _release_finding(request)
        _incident_event(db, request, "REMEDIATION_REFUSED", f"Remediation request #{request.id} was refused: no recorded approval.")
        _audit(db, request, "REMEDIATION_EXECUTION_REFUSED", AuditOutcome.DENIED, reason=request.failure_reason)
        db.commit()
        return None

    _set_status(request, RemediationStatus.RUNNING)
    request.started_at = utcnow()
    request.attempt_count += 1
    execution = RemediationExecution(
        request_id=request.id,
        attempt=request.attempt_count,
        worker_identifier=settings.WORKER_ID,
        status="RUNNING",
    )
    db.add(execution)
    _incident_event(db, request, "REMEDIATION_STARTED", f"Worker started {request.action_code} (attempt {request.attempt_count}).")
    _audit(db, request, "REMEDIATION_EXECUTION_STARTED", worker=settings.WORKER_ID)
    db.commit()
    return execution.id


def _finish_failed(db: Session, request: RemediationRequest, execution: RemediationExecution, reason: str, verification: Optional[VerificationResult] = None) -> None:
    execution.status = "FAILED"
    execution.error = reason
    execution.completed_at = utcnow()
    if verification is not None:
        execution.verification_result = verification.as_dict()
    _set_status(request, RemediationStatus.FAILED)
    request.failure_reason = reason
    request.completed_at = execution.completed_at
    # The problem is NOT fixed: the finding returns to OPEN and the incident stays open.
    _release_finding(request)
    _incident_event(db, request, "REMEDIATION_FAILED", f"Remediation request #{request.id} failed: {reason}")
    _audit(db, request, "REMEDIATION_FAILED", AuditOutcome.FAILURE, reason=reason)
    db.commit()
    logger.warning("remediation failed", extra={"request_id": request.id, "reason": reason})


def run_execution(db: Session, execution_id: int) -> None:
    execution = db.get(RemediationExecution, execution_id)
    request = execution.request
    handler = HANDLERS.get(request.action_code)
    verifier = VERIFIERS.get(request.action_code)
    if handler is None or verifier is None:
        _finish_failed(db, request, execution, f"Unsupported action '{request.action_code}' - nothing was executed.")
        return

    # ---- execute -------------------------------------------------------
    try:
        details = _run_with_timeout(handler, _build_params(request), settings.ACTION_TIMEOUT_SECONDS)
    except ActionError as exc:
        execution.execution_details = {"error": str(exc), "retryable": exc.retryable, **exc.details}
        _audit(db, request, "REMEDIATION_EXECUTION_ERROR", AuditOutcome.FAILURE, error=str(exc))
        _finish_failed(db, request, execution, str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - any handler bug must end as a recorded failure
        logger.exception("unexpected action error", extra={"request_id": request.id})
        execution.execution_details = {"error": exc.__class__.__name__}
        _finish_failed(db, request, execution, f"Unexpected error during execution: {exc.__class__.__name__}")
        return

    execution.execution_details = details
    execution.status = "VERIFYING"
    _set_status(request, RemediationStatus.VERIFYING)
    _incident_event(db, request, "REMEDIATION_EXECUTED", f"{request.action_code} executed; verifying the result.")
    _audit(db, request, "REMEDIATION_EXECUTED", operation=details.get("operation"), changed=details.get("changed"))
    db.commit()

    # ---- verify --------------------------------------------------------
    try:
        verification = verifier(db, request, details)
    except Exception as exc:  # noqa: BLE001
        logger.exception("verification error", extra={"request_id": request.id})
        db.rollback()
        verification = VerificationResult(False, f"Verification could not be completed: {exc.__class__.__name__}")

    execution = db.get(RemediationExecution, execution_id)
    request = execution.request
    _audit(
        db,
        request,
        "REMEDIATION_VERIFICATION_PASSED" if verification.passed else "REMEDIATION_VERIFICATION_FAILED",
        AuditOutcome.SUCCESS if verification.passed else AuditOutcome.FAILURE,
        summary=verification.summary,
        checks=[{"name": c["name"], "passed": c["passed"]} for c in verification.checks],
    )
    if not verification.passed:
        _finish_failed(db, request, execution, verification.summary, verification)
        return

    execution.verification_result = verification.as_dict()
    execution.status = "SUCCEEDED"
    execution.completed_at = utcnow()
    _set_status(request, RemediationStatus.SUCCEEDED)
    request.completed_at = execution.completed_at
    request.failure_reason = None
    if request.incident is not None:
        resolved = incident_service.resolve_incident(
            db,
            request.incident,
            summary=(
                f"Resolved by remediation request #{request.id} ({request.action_code}). "
                + verification.summary
            ),
            evidence={"source": "remediation-verification", "checks": verification.checks},
            actor_label=settings.WORKER_ID,
            correlation_id=request.correlation_id,
        )
        if not resolved:
            _incident_event(db, request, "REMEDIATION_SUCCEEDED", f"Remediation request #{request.id} verified successfully.")
    _audit(db, request, "REMEDIATION_SUCCEEDED", summary=verification.summary)
    db.commit()
    logger.info("remediation succeeded", extra={"request_id": request.id})


def process_next(db: Session) -> bool:
    """Claim and fully process one queued request.  Returns True if work was done."""
    execution_id = claim_next(db)
    if execution_id is None:
        return False
    run_execution(db, execution_id)
    return True


def recover_interrupted(db: Session) -> int:
    """Fail requests left RUNNING/VERIFYING by a worker that stopped mid-flight."""
    stuck = (
        db.query(RemediationRequest)
        .filter(
            RemediationRequest.status.in_(
                [RemediationStatus.RUNNING.value, RemediationStatus.VERIFYING.value]
            )
        )
        .all()
    )
    for request in stuck:
        execution = request.executions[-1] if request.executions else None
        reason = "The worker stopped before this execution finished; the outcome is unknown."
        if execution is not None and execution.status in ("RUNNING", "VERIFYING"):
            _finish_failed(db, request, execution, reason)
        else:
            _set_status(request, RemediationStatus.FAILED)
            request.failure_reason = reason
            request.completed_at = utcnow()
            _release_finding(request)
            _incident_event(db, request, "REMEDIATION_FAILED", f"Remediation request #{request.id} failed: {reason}")
            _audit(db, request, "REMEDIATION_FAILED", AuditOutcome.FAILURE, reason=reason)
            db.commit()
    return len(stuck)


# ---------------------------------------------------------------------------
# Demo environment maintenance (only when demo controls are active)
# ---------------------------------------------------------------------------
def _baseline_dir() -> Path:
    return settings.security_rules_path / "samples" / "baseline"


def restore_baseline() -> list[str]:
    """Copy the insecure sample configuration into the scan workspace."""
    workspace = settings.scan_workspace_path
    workspace.mkdir(parents=True, exist_ok=True)
    restored = []
    for source in sorted(_baseline_dir().glob("*.yaml")):
        atomic_write(workspace / source.name, source.read_text(encoding="utf-8"))
        restored.append(source.name)
    return restored


def initialise_workspace(db: Session) -> None:
    workspace = settings.scan_workspace_path
    workspace.mkdir(parents=True, exist_ok=True)
    if not settings.demo_controls_active:
        return
    if any(workspace.glob("*.yaml")) or any(workspace.glob("*.yml")):
        return
    restored = restore_baseline()
    record_audit(
        db,
        action="DEMO_WORKSPACE_INITIALISED",
        entity_type="scan_workspace",
        actor_label=settings.WORKER_ID,
        metadata={"files": restored, "simulated": True},
    )
    db.commit()
    logger.info("scan workspace initialised from the demo baseline", extra={"files": restored})


def process_demo_task(db: Session) -> bool:
    statement = (
        select(DemoTask)
        .where(DemoTask.status == "QUEUED")
        .order_by(DemoTask.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    task = db.execute(statement).scalars().first()
    if task is None:
        db.rollback()
        return False
    task.status = "RUNNING"
    task.started_at = utcnow()
    db.commit()

    try:
        if not settings.demo_controls_active:
            raise RuntimeError("Demonstration controls are disabled in this environment.")
        if task.task_type != RESET_TASK:
            raise RuntimeError(f"Unsupported demo task '{task.task_type}'.")
        restored = restore_baseline()
        task.status = "SUCCEEDED"
        task.details = {"restored_files": restored}
        outcome = AuditOutcome.SUCCESS
    except Exception as exc:  # noqa: BLE001
        task.status = "FAILED"
        task.error = str(exc)[:500]
        outcome = AuditOutcome.FAILURE
    task.completed_at = utcnow()
    record_audit(
        db,
        action="DEMO_CONFIG_RESET",
        entity_type="demo_task",
        entity_id=task.id,
        actor_label=settings.WORKER_ID,
        outcome=outcome,
        metadata={"simulated": True, **(task.details or {}), "error": task.error},
    )
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------
def heartbeat(db: Session, started_at, processed: int) -> None:
    row = db.get(WorkerHeartbeat, settings.WORKER_ID)
    if row is None:
        row = WorkerHeartbeat(worker_id=settings.WORKER_ID, started_at=started_at)
        db.add(row)
    row.hostname = socket.gethostname()
    row.version = settings.VERSION
    row.started_at = started_at
    row.last_seen_at = utcnow()
    row.jobs_processed = processed
    db.commit()


class HeartbeatThread(threading.Thread):
    """Reports liveness on a timer, independently of the job loop.

    A verification can legitimately take minutes; without a separate thread
    the worker would look offline (and its container unhealthy) meanwhile.
    """

    def __init__(self, started_at) -> None:
        super().__init__(daemon=True, name="heartbeat")
        self.started_at = started_at
        self.processed = 0
        self._stopped = threading.Event()

    def beat(self) -> None:
        try:
            with SessionLocal() as db:
                heartbeat(db, self.started_at, self.processed)
        except Exception:  # noqa: BLE001 - a missed beat must never stop the worker
            logger.exception("heartbeat failed")

    def run(self) -> None:
        while not self._stopped.wait(settings.WORKER_HEARTBEAT_SECONDS):
            self.beat()

    def stop(self) -> None:
        self._stopped.set()


def wait_for_schema(max_wait: float = 180.0) -> None:
    """Block until the API container has applied the database migrations."""
    deadline = time.monotonic() + max_wait
    while True:
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1 FROM worker_heartbeats LIMIT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            if time.monotonic() > deadline:
                raise RuntimeError("Database schema is not available") from exc
            logger.info("waiting for database schema", extra={"error": exc.__class__.__name__})
            time.sleep(3)


def main() -> None:  # pragma: no cover - exercised by the running stack
    configure_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    logger.info("remediation worker starting", extra={"worker": settings.WORKER_ID, "actions": sorted(HANDLERS)})
    wait_for_schema()

    with SessionLocal() as db:
        interrupted = recover_interrupted(db)
        if interrupted:
            logger.warning("marked interrupted executions as failed", extra={"count": interrupted})
        initialise_workspace(db)

    beats = HeartbeatThread(utcnow())
    beats.beat()
    beats.start()

    while not _stop:
        worked = False
        try:
            with SessionLocal() as db:
                worked = process_demo_task(db) or process_next(db)
            if worked:
                beats.processed += 1
                beats.beat()
        except Exception:  # noqa: BLE001 - the loop must survive transient database errors
            logger.exception("worker loop error")
            time.sleep(5)
        if not worked:
            time.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
    beats.stop()
    logger.info("remediation worker stopped")


if __name__ == "__main__":  # pragma: no cover
    main()
