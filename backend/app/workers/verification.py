"""Post-action verification.

A remediation request is only marked SUCCEEDED when *independent, fresh
evidence* shows that the problem is gone.  The action handler reporting
"done" is never enough.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import FindingStatus, RemediationRequest, ScanStatus
from app.security_scanner.engine import ScanInputError, scan_file
from app.services import monitoring_service, scan_service
from app.services.remediation_catalog import ACTION_FIX_PUBLIC_STORAGE, ACTION_RECOVER_APP
from app.workers.actions import probe_readiness

REQUIRED_CONSECUTIVE_HEALTH_CHECKS = 3


@dataclass
class VerificationResult:
    passed: bool
    summary: str
    checks: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "checks": self.checks,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }


def _check(name: str, passed: bool, detail: str, **extra: Any) -> Dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "detail": detail,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# ACTION-001
# ---------------------------------------------------------------------------
def _verify_health(deadline: float) -> Dict[str, Any]:
    consecutive = 0
    attempts = 0
    last: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        attempts += 1
        last = probe_readiness()
        consecutive = consecutive + 1 if last.get("ready") else 0
        if consecutive >= REQUIRED_CONSECUTIVE_HEALTH_CHECKS:
            return _check(
                "application_health",
                True,
                f"{consecutive} consecutive readiness checks returned HTTP 200.",
                attempts=attempts,
                last_probe=last,
            )
        time.sleep(1.0)
    return _check(
        "application_health",
        False,
        f"Readiness did not stabilise: only {consecutive} consecutive successful checks "
        f"after {attempts} attempts.",
        attempts=attempts,
        last_probe=last,
    )


def _verify_scrape_target(recovered_at: datetime, deadline: float) -> Dict[str, Any]:
    """Prometheus must have scraped the target successfully *after* the action."""
    client = monitoring_service.get_client()
    reason = "no observation"
    while time.monotonic() < deadline:
        result = client.targets()
        if not result["available"]:
            reason = f"Prometheus unavailable ({result['reason']})"
        else:
            matching = [t for t in result["targets"] if t["job"] == settings.DEMO_APP_JOB]
            if not matching:
                reason = "Prometheus has no scrape target for the application"
            else:
                target = matching[0]
                fresh = bool(target["last_scrape"]) and _parse_iso(target["last_scrape"]) >= recovered_at
                if target["health"] == "up" and fresh:
                    return _check(
                        "prometheus_target_up",
                        True,
                        "Prometheus scraped the application successfully after the recovery action.",
                        last_scrape=target["last_scrape"],
                    )
                reason = (
                    f"target health is '{target['health']}'"
                    + ("" if fresh else " and no scrape newer than the action yet")
                )
        time.sleep(2.0)
    return _check("prometheus_target_up", False, f"Monitoring did not confirm recovery: {reason}.")


def _verify_alert_cleared(alert_name: str, deadline: float) -> Dict[str, Any]:
    client = monitoring_service.get_client()
    reason = "no observation"
    while time.monotonic() < deadline:
        firing, error = client.alert_is_firing(alert_name, settings.DEMO_APP_JOB)
        if firing is False:
            return _check(
                "alert_cleared", True, f"Prometheus no longer reports {alert_name} as firing."
            )
        reason = "the alert is still firing" if firing else f"Prometheus unavailable ({error})"
        time.sleep(3.0)
    return _check("alert_cleared", False, f"{alert_name} was not confirmed as cleared: {reason}.")


def verify_application_recovery(db: Session, request: RemediationRequest, details: Dict[str, Any]) -> VerificationResult:
    started = time.monotonic()
    total = settings.VERIFY_TIMEOUT_SECONDS
    recovered_at = _parse_iso(details["recovered_at"])
    checks: List[Dict[str, Any]] = []

    checks.append(_verify_health(started + min(30.0, total)))
    if checks[-1]["passed"]:
        checks.append(_verify_scrape_target(recovered_at, started + min(75.0, total)))
    if all(c["passed"] for c in checks) and request.incident is not None:
        checks.append(_verify_alert_cleared(request.incident.alert_name, started + total))

    required = 3 if request.incident is not None else 2
    passed = len(checks) == required and all(c["passed"] for c in checks)
    if passed:
        summary = "Recovery verified by fresh health checks and Prometheus observations."
    else:
        failed = next(c for c in checks if not c["passed"])
        summary = f"Verification failed at '{failed['name']}': {failed['detail']}"
    return VerificationResult(passed=passed, summary=summary, checks=checks)


# ---------------------------------------------------------------------------
# ACTION-002
# ---------------------------------------------------------------------------
def verify_storage_correction(db: Session, request: RemediationRequest, details: Dict[str, Any]) -> VerificationResult:
    finding = request.finding
    checks: List[Dict[str, Any]] = []
    if finding is None:
        return VerificationResult(False, "The source finding no longer exists.", checks)

    # 1. A real, persisted scan of the corrected file.
    scan = scan_service.run_scan(
        db,
        actor=None,
        actor_label=settings.WORKER_ID,
        target=finding.target_file,
        trigger="REMEDIATION_VERIFICATION",
        correlation_id=request.correlation_id,
    )
    scan_ok = scan.status == ScanStatus.COMPLETED.value and finding.target_file in (
        scan.result_summary.get("files_scanned") or []
    )
    checks.append(
        _check(
            "security_rescan",
            scan_ok,
            f"Verification scan #{scan.id} finished with status {scan.status}.",
            scan_id=scan.id,
        )
    )
    if not scan_ok:
        return VerificationResult(False, "The verification scan did not complete.", checks)

    # 2. Independent re-evaluation: the rule must no longer match this resource.
    try:
        violations = scan_file(
            scan_service.resolve_target(finding.target_file),
            finding.target_file,
            max_bytes=settings.SCAN_MAX_FILE_BYTES,
        )
    except (ScanInputError, scan_service.ScanTargetError) as exc:
        checks.append(_check("rule_not_detected", False, f"The file could not be evaluated: {exc}"))
        return VerificationResult(False, "The corrected file could not be evaluated.", checks)
    still_detected = any(v.stable_key == finding.stable_finding_key for v in violations)
    checks.append(
        _check(
            "rule_not_detected",
            not still_detected,
            f"{finding.rule_id} is {'still' if still_detected else 'no longer'} detected for "
            f"{finding.resource_identifier}.",
        )
    )

    # 3. The finding's own lifecycle state, as set by the scan (never set by hand here).
    db.refresh(finding)
    resolved = finding.status == FindingStatus.RESOLVED.value
    checks.append(
        _check("finding_resolved_by_scan", resolved, f"Finding #{finding.id} status is {finding.status}.")
    )

    passed = all(c["passed"] for c in checks)
    summary = (
        f"{finding.rule_id} is no longer detected for {finding.resource_identifier}; "
        f"confirmed by verification scan #{scan.id}."
        if passed
        else f"Verification failed: {finding.rule_id} is still detected for {finding.resource_identifier}."
    )
    return VerificationResult(passed=passed, summary=summary, checks=checks)


VERIFIERS: Dict[str, Callable[[Session, RemediationRequest, Dict[str, Any]], VerificationResult]] = {
    ACTION_RECOVER_APP: verify_application_recovery,
    ACTION_FIX_PUBLIC_STORAGE: verify_storage_correction,
}
