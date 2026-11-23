"""Security scanning: authorised targets, scan history and finding lifecycle."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.metrics import OPEN_FINDINGS, SECURITY_SCANS
from app.models.models import (
    AuditOutcome,
    FindingStatus,
    ScanStatus,
    SecurityFinding,
    SecurityScan,
    User,
)
from app.security_scanner.engine import ScanInputError, Violation, scan_file
from app.services.audit_service import record_audit

# Only plain file names are accepted - never a path.
_TARGET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,120}\.ya?ml$")


class ScanTargetError(ValueError):
    """The requested target is not an authorised, existing configuration file."""

    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


class FindingStateError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Authorised targets
# ---------------------------------------------------------------------------
def workspace_dir() -> Path:
    return settings.scan_workspace_path


def resolve_target(name: str) -> Path:
    """Map a target name to a file inside the scan workspace.

    Rejects anything that is not a simple ``*.yaml`` file name, and verifies the
    fully resolved path still sits directly inside the workspace so that
    ``../`` sequences, absolute paths and symlinks cannot escape it.
    """
    if not isinstance(name, str) or not _TARGET_NAME.match(name):
        raise ScanTargetError(
            "Target must be the name of a .yaml or .yml file in the authorised scan workspace."
        )
    workspace = workspace_dir()
    candidate = workspace / name
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise ScanTargetError("Target cannot be resolved.") from exc
    if resolved.parent != workspace:
        raise ScanTargetError("Target is outside the authorised scan workspace.")
    if not resolved.is_file():
        raise ScanTargetError(f"Target '{name}' does not exist in the scan workspace.", not_found=True)
    return resolved


def list_targets() -> List[Dict[str, Any]]:
    workspace = workspace_dir()
    if not workspace.is_dir():
        return []
    targets = []
    for path in sorted(workspace.iterdir(), key=lambda p: p.name):
        if not _TARGET_NAME.match(path.name):
            continue
        try:
            resolved = path.resolve()
            if resolved.parent != workspace or not resolved.is_file():
                continue
            stat = resolved.stat()
        except OSError:
            continue
        targets.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                "remediation_allowed": path.name in settings.writable_target_names,
            }
        )
    return targets


def read_target(name: str) -> Dict[str, Any]:
    path = resolve_target(name)
    size = path.stat().st_size
    if size > settings.SCAN_MAX_FILE_BYTES:
        raise ScanTargetError("Target file is too large to display.")
    return {
        "name": name,
        "size_bytes": size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------
def _apply_file_results(
    db: Session,
    scan: SecurityScan,
    target_file: str,
    violations: List[Violation],
    actor: Optional[User],
    actor_label: str,
    counters: Dict[str, int],
) -> None:
    """Upsert findings for one successfully scanned file and resolve the rest."""
    now = utcnow()
    existing = {
        finding.stable_finding_key: finding
        for finding in db.query(SecurityFinding).filter(SecurityFinding.target_file == target_file)
    }
    detected_keys = set()

    for violation in violations:
        key = violation.stable_key
        detected_keys.add(key)
        evidence = {"summary": violation.summary, **violation.evidence}
        finding = existing.get(key)
        if finding is None:
            finding = SecurityFinding(
                scan_id=scan.id,
                last_scan_id=scan.id,
                stable_finding_key=key,
                rule_id=violation.rule.id,
                rule_name=violation.rule.name,
                severity=violation.rule.severity,
                target_file=target_file,
                resource_type=violation.resource_type,
                resource_name=violation.resource_name,
                resource_identifier=violation.resource_identifier,
                evidence=evidence,
                recommendation=violation.rule.recommendation,
                status=FindingStatus.OPEN.value,
                first_detected_at=now,
                last_seen_at=now,
            )
            db.add(finding)
            db.flush()
            counters["new"] += 1
            record_audit(
                db,
                action="FINDING_DETECTED",
                entity_type="finding",
                entity_id=finding.id,
                actor=actor,
                actor_label=actor_label,
                metadata={
                    "rule_id": finding.rule_id,
                    "resource": finding.resource_identifier,
                    "target_file": target_file,
                    "severity": finding.severity,
                    "scan_id": scan.id,
                },
            )
            continue

        finding.last_seen_at = now
        finding.last_scan_id = scan.id
        finding.evidence = evidence
        finding.rule_name = violation.rule.name
        finding.severity = violation.rule.severity
        finding.recommendation = violation.rule.recommendation
        finding.detection_count += 1
        if finding.status == FindingStatus.RESOLVED.value:
            finding.status = FindingStatus.OPEN.value
            finding.resolved_at = None
            counters["reopened"] += 1
            record_audit(
                db,
                action="FINDING_REOPENED",
                entity_type="finding",
                entity_id=finding.id,
                actor=actor,
                actor_label=actor_label,
                metadata={
                    "rule_id": finding.rule_id,
                    "resource": finding.resource_identifier,
                    "reason": "Rule violation detected again by a later scan",
                    "scan_id": scan.id,
                },
            )
        else:
            counters["unchanged"] += 1

    for key, finding in existing.items():
        if key in detected_keys or finding.status == FindingStatus.RESOLVED.value:
            continue
        previous = finding.status
        finding.status = FindingStatus.RESOLVED.value
        finding.resolved_at = now
        finding.last_scan_id = scan.id
        counters["resolved"] += 1
        record_audit(
            db,
            action="FINDING_RESOLVED",
            entity_type="finding",
            entity_id=finding.id,
            actor=actor,
            actor_label=actor_label,
            metadata={
                "rule_id": finding.rule_id,
                "resource": finding.resource_identifier,
                "previous_status": previous,
                "verification": "Rule no longer violated in scan",
                "scan_id": scan.id,
            },
        )


def run_scan(
    db: Session,
    *,
    actor: Optional[User] = None,
    actor_label: Optional[str] = None,
    target: Optional[str] = None,
    trigger: str = "MANUAL",
    correlation_id: Optional[str] = None,
) -> SecurityScan:
    """Scan one target (or every file in the workspace) and persist the result."""
    label = actor_label or (actor.email if actor else "system")
    scan = SecurityScan(
        requested_by=actor.id if actor else None,
        requested_by_label=label,
        trigger=trigger,
        target=target or "*",
        status=ScanStatus.RUNNING.value,
        started_at=utcnow(),
    )
    db.add(scan)
    db.flush()

    counters = {"new": 0, "reopened": 0, "unchanged": 0, "resolved": 0}
    file_errors: Dict[str, str] = {}
    files_scanned: List[str] = []
    by_rule: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    detected_total = 0

    try:
        if target is not None:
            paths = [(target, resolve_target(target))]
        else:
            paths = [(entry["name"], workspace_dir() / entry["name"]) for entry in list_targets()]
    except ScanTargetError as exc:
        paths = []
        file_errors[str(target)] = str(exc)

    for name, path in paths:
        try:
            violations = scan_file(path, name, max_bytes=settings.SCAN_MAX_FILE_BYTES)
        except ScanInputError as exc:
            # A malformed file is rejected; its existing findings are left untouched.
            file_errors[name] = str(exc)
            continue
        files_scanned.append(name)
        detected_total += len(violations)
        for violation in violations:
            by_rule[violation.rule.id] = by_rule.get(violation.rule.id, 0) + 1
            by_severity[violation.rule.severity] = by_severity.get(violation.rule.severity, 0) + 1
        _apply_file_results(db, scan, name, violations, actor, label, counters)

    # Findings are only re-evaluated for files that exist.  When a file has been
    # removed its findings are left untouched (a deleted file is not a verified
    # fix) and the scan reports them so they are not silently forgotten.
    orphaned = 0
    if target is None:
        present = {name for name, _path in paths}
        orphaned = (
            db.query(func.count(SecurityFinding.id))
            .filter(
                SecurityFinding.status != FindingStatus.RESOLVED.value,
                SecurityFinding.target_file.notin_(present) if present else True,
            )
            .scalar()
            or 0
        )
    notes = []
    if not paths and not file_errors:
        notes.append("No configuration files are present in the scan workspace.")
    if orphaned:
        notes.append(
            f"{orphaned} unresolved finding(s) refer to configuration files that are no longer in the "
            "scan workspace; they were not re-evaluated."
        )

    failed = bool(file_errors) and not files_scanned
    scan.status = ScanStatus.FAILED.value if failed else ScanStatus.COMPLETED.value
    scan.completed_at = utcnow()
    scan.error = "; ".join(file_errors.values()) if failed else None
    scan.result_summary = {
        "files_scanned": files_scanned,
        "files_failed": file_errors,
        "violations_detected": detected_total,
        "new_findings": counters["new"],
        "reopened_findings": counters["reopened"],
        "unchanged_findings": counters["unchanged"],
        "resolved_findings": counters["resolved"],
        "by_rule": by_rule,
        "by_severity": by_severity,
        "orphaned_findings": orphaned,
        "note": " ".join(notes) or None,
    }
    record_audit(
        db,
        action="SECURITY_SCAN_FAILED" if failed else "SECURITY_SCAN_COMPLETED",
        entity_type="security_scan",
        entity_id=scan.id,
        actor=actor,
        actor_label=label,
        outcome=AuditOutcome.FAILURE if failed else AuditOutcome.SUCCESS,
        metadata={"trigger": trigger, "target": scan.target, **scan.result_summary},
        correlation_id=correlation_id,
    )
    db.commit()
    SECURITY_SCANS.labels(status=scan.status).inc()
    OPEN_FINDINGS.set(
        db.query(func.count(SecurityFinding.id))
        .filter(SecurityFinding.status == FindingStatus.OPEN.value)
        .scalar()
        or 0
    )
    return scan


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
_FINDING_SORT = {
    "id": SecurityFinding.id,
    "severity": SecurityFinding.severity,
    "status": SecurityFinding.status,
    "rule_id": SecurityFinding.rule_id,
    "resource": SecurityFinding.resource_identifier,
    "first_detected_at": SecurityFinding.first_detected_at,
    "last_seen_at": SecurityFinding.last_seen_at,
}
_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def severity_order(column):
    """SQL expression ordering severities CRITICAL > HIGH > MEDIUM > LOW."""
    from sqlalchemy import case

    return case(_SEVERITY_RANK, value=column, else_=9)


def list_findings(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    q: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    rule_id: Optional[str] = None,
    target_file: Optional[str] = None,
    sort: str = "severity",
    order: str = "asc",
) -> Tuple[List[SecurityFinding], int]:
    query = db.query(SecurityFinding)
    if status:
        query = query.filter(SecurityFinding.status.in_([s.strip().upper() for s in status.split(",")]))
    if severity:
        query = query.filter(
            SecurityFinding.severity.in_([s.strip().upper() for s in severity.split(",")])
        )
    if rule_id:
        query = query.filter(SecurityFinding.rule_id == rule_id.upper())
    if target_file:
        query = query.filter(SecurityFinding.target_file == target_file)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(SecurityFinding.rule_id).like(pattern),
                func.lower(SecurityFinding.rule_name).like(pattern),
                func.lower(SecurityFinding.resource_identifier).like(pattern),
                func.lower(SecurityFinding.target_file).like(pattern),
            )
        )
    total = query.count()
    if sort == "severity":
        primary = severity_order(SecurityFinding.severity)
    else:
        primary = _FINDING_SORT.get(sort, SecurityFinding.id)
    ordering = primary.desc() if order == "desc" else primary.asc()
    items = (
        query.order_by(ordering, SecurityFinding.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def list_scans(db: Session, *, page: int = 1, page_size: int = 20) -> Tuple[List[SecurityScan], int]:
    query = db.query(SecurityScan)
    total = query.count()
    items = (
        query.order_by(SecurityScan.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return items, total


def latest_scan(db: Session) -> Optional[SecurityScan]:
    return db.query(SecurityScan).order_by(SecurityScan.id.desc()).first()


# ---------------------------------------------------------------------------
# Accepted risk
# ---------------------------------------------------------------------------
def accept_risk(db: Session, actor: User, finding: SecurityFinding, reason: str) -> SecurityFinding:
    if finding.status != FindingStatus.OPEN.value:
        raise FindingStateError(
            f"Only OPEN findings can be marked as accepted risk (current: {finding.status})."
        )
    finding.status = FindingStatus.ACCEPTED_RISK.value
    finding.accepted_risk_by = actor.id
    finding.accepted_risk_reason = reason
    finding.accepted_risk_at = utcnow()
    record_audit(
        db,
        action="FINDING_RISK_ACCEPTED",
        entity_type="finding",
        entity_id=finding.id,
        actor=actor,
        metadata={"rule_id": finding.rule_id, "resource": finding.resource_identifier, "reason": reason},
    )
    db.commit()
    return finding


def revoke_risk_acceptance(db: Session, actor: User, finding: SecurityFinding) -> SecurityFinding:
    if finding.status != FindingStatus.ACCEPTED_RISK.value:
        raise FindingStateError("Finding is not in ACCEPTED_RISK state.")
    finding.status = FindingStatus.OPEN.value
    finding.accepted_risk_by = None
    finding.accepted_risk_reason = None
    finding.accepted_risk_at = None
    record_audit(
        db,
        action="FINDING_RISK_ACCEPTANCE_REVOKED",
        entity_type="finding",
        entity_id=finding.id,
        actor=actor,
        metadata={"rule_id": finding.rule_id, "resource": finding.resource_identifier},
    )
    db.commit()
    return finding
