"""Aggregated figures for the Overview page (all computed from stored records)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import check_database, utcnow
from app.models.models import (
    ACTIVE_INCIDENT_STATUSES,
    FindingStatus,
    Incident,
    IncidentStatus,
    RemediationRequest,
    RemediationStatus,
    SecurityFinding,
    Severity,
    User,
    WorkerHeartbeat,
)
from app.services import audit_service, scan_service

WORKER_ONLINE_WITHIN_SECONDS = 45


def _counts(db: Session, column, *filters) -> Dict[str, int]:
    query = db.query(column, func.count()).group_by(column)
    for condition in filters:
        query = query.filter(condition)
    return {str(key): int(count) for key, count in query.all()}


def refresh_gauges(db: Session) -> None:
    """Set the open-incident / open-finding gauges from the database (called at start-up)."""
    from app.core.metrics import OPEN_FINDINGS, OPEN_INCIDENTS

    OPEN_INCIDENTS.set(
        db.query(func.count(Incident.id)).filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES)).scalar() or 0
    )
    OPEN_FINDINGS.set(
        db.query(func.count(SecurityFinding.id)).filter(SecurityFinding.status == FindingStatus.OPEN.value).scalar() or 0
    )


def worker_status(db: Session) -> Dict[str, Any]:
    row = db.query(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()).first()
    if row is None:
        return {"online": False, "worker_id": None, "last_seen_at": None, "detail": "No worker has reported yet."}
    age = (utcnow() - row.last_seen_at).total_seconds()
    return {
        "online": age <= WORKER_ONLINE_WITHIN_SECONDS,
        "worker_id": row.worker_id,
        "last_seen_at": row.last_seen_at,
        "last_seen_age_seconds": round(age, 1),
        "started_at": row.started_at,
        "jobs_processed": row.jobs_processed,
    }


def summary(db: Session, viewer: User) -> Dict[str, Any]:
    severities = [s.value for s in Severity]

    incident_by_status = _counts(db, Incident.status)
    active_by_severity = _counts(db, Incident.severity, Incident.status.in_(ACTIVE_INCIDENT_STATUSES))
    finding_by_status = _counts(db, SecurityFinding.status)
    open_finding_by_severity = _counts(
        db,
        SecurityFinding.severity,
        SecurityFinding.status.in_(
            [FindingStatus.OPEN.value, FindingStatus.REMEDIATION_PENDING.value]
        ),
    )
    remediation_by_status = _counts(db, RemediationRequest.status)

    since = utcnow() - timedelta(hours=24)
    resolved_last_24h = (
        db.query(func.count(Incident.id))
        .filter(Incident.resolved_at.is_not(None), Incident.resolved_at >= since)
        .scalar()
        or 0
    )

    latest = scan_service.latest_scan(db)
    recent_events, _ = audit_service.list_audit_events(db, viewer, page_size=8)
    database_ok, database_error = check_database()

    return {
        "generated_at": utcnow(),
        "incidents": {
            "active": sum(incident_by_status.get(s, 0) for s in ACTIVE_INCIDENT_STATUSES),
            "by_status": {s.value: incident_by_status.get(s.value, 0) for s in IncidentStatus},
            "active_by_severity": {s: active_by_severity.get(s, 0) for s in severities},
            "resolved_last_24h": int(resolved_last_24h),
            "simulated_active": int(
                db.query(func.count(Incident.id))
                .filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES), Incident.is_simulated.is_(True))
                .scalar()
                or 0
            ),
        },
        "findings": {
            "open": finding_by_status.get(FindingStatus.OPEN.value, 0),
            "by_status": {s.value: finding_by_status.get(s.value, 0) for s in FindingStatus},
            "unresolved_by_severity": {s: open_finding_by_severity.get(s, 0) for s in severities},
        },
        "remediation": {
            "pending_approval": remediation_by_status.get(RemediationStatus.PENDING_APPROVAL.value, 0),
            "in_progress": sum(
                remediation_by_status.get(s, 0)
                for s in (
                    RemediationStatus.APPROVED.value,
                    RemediationStatus.QUEUED.value,
                    RemediationStatus.RUNNING.value,
                    RemediationStatus.VERIFYING.value,
                )
            ),
            "succeeded": remediation_by_status.get(RemediationStatus.SUCCEEDED.value, 0),
            "failed": remediation_by_status.get(RemediationStatus.FAILED.value, 0),
            "by_status": {s.value: remediation_by_status.get(s.value, 0) for s in RemediationStatus},
        },
        "latest_scan": (
            {
                "id": latest.id,
                "status": latest.status,
                "trigger": latest.trigger,
                "target": latest.target,
                "requested_by": latest.requested_by_label,
                "started_at": latest.started_at,
                "completed_at": latest.completed_at,
                "summary": latest.result_summary,
            }
            if latest
            else None
        ),
        "recent_audit_events": [
            {
                "id": event.id,
                "created_at": event.created_at,
                "actor": event.actor_label,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "outcome": event.outcome,
            }
            for event in recent_events
        ],
        "platform": {
            "backend": {"healthy": True, "version": settings.VERSION, "environment": settings.ENVIRONMENT},
            "database": {"healthy": database_ok, "error": database_error},
            "worker": worker_status(db),
            "demo_controls_enabled": settings.demo_controls_active,
        },
    }
