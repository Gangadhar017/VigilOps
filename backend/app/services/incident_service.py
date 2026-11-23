"""Incident engine: alert ingestion, deduplication and the incident lifecycle."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.metrics import ALERT_WEBHOOK_EVENTS, OPEN_INCIDENTS
from app.core.permissions import has_permission
from app.models.models import (
    ACTIVE_INCIDENT_STATUSES,
    AuditOutcome,
    Incident,
    IncidentEvent,
    IncidentStatus,
    MonitoredResource,
    RemediationRequest,
    RemediationStatus,
    Severity,
    User,
)
from app.services import demo_service, monitoring_service
from app.services.audit_service import record_audit
from app.services.remediation_catalog import action_for_incident
from app.services.scan_service import severity_order
from app.services.settings_service import get_setting

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    "critical": Severity.CRITICAL.value,
    "high": Severity.HIGH.value,
    "error": Severity.HIGH.value,
    "warning": Severity.MEDIUM.value,
    "medium": Severity.MEDIUM.value,
    "low": Severity.LOW.value,
    "info": Severity.LOW.value,
}

# status -> statuses it may move to
TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    IncidentStatus.OPEN.value: (
        IncidentStatus.ACKNOWLEDGED.value,
        IncidentStatus.IN_PROGRESS.value,
        IncidentStatus.RESOLVED.value,
    ),
    IncidentStatus.ACKNOWLEDGED.value: (
        IncidentStatus.IN_PROGRESS.value,
        IncidentStatus.RESOLVED.value,
    ),
    IncidentStatus.IN_PROGRESS.value: (IncidentStatus.RESOLVED.value,),
    IncidentStatus.RESOLVED.value: (IncidentStatus.CLOSED.value, IncidentStatus.OPEN.value),
    IncidentStatus.CLOSED.value: (),
}

MIN_RESOLUTION_NOTE = 10
_MAX_LABELS = 40
_MAX_LABEL_VALUE = 500


class IncidentError(ValueError):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean_map(values: Dict[str, Any]) -> Dict[str, str]:
    cleaned: Dict[str, str] = {}
    for index, (key, value) in enumerate(sorted(values.items())):
        if index >= _MAX_LABELS:
            break
        cleaned[str(key)[:120]] = str(value)[:_MAX_LABEL_VALUE]
    return cleaned


def compute_fingerprint(labels: Dict[str, str]) -> str:
    """Stable identity of an alert: hash of its sorted label set."""
    canonical = "\n".join(f"{key}={labels[key]}" for key in sorted(labels))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        import re

        cleaned = re.sub(r"(\.\d{6})\d+", r"\1", value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed.year < 2000:
        return None
    return parsed.astimezone(timezone.utc)


def add_event(
    db: Session,
    incident: Incident,
    event_type: str,
    *,
    actor: Optional[User] = None,
    actor_label: Optional[str] = None,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    details: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> IncidentEvent:
    event = IncidentEvent(
        incident=incident,
        actor_id=actor.id if actor else None,
        actor_label=actor_label or (actor.email if actor else "system"),
        event_type=event_type,
        previous_state=previous_state,
        new_state=new_state,
        details=details,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event


def _refresh_gauge(db: Session) -> None:
    OPEN_INCIDENTS.set(
        db.query(func.count(Incident.id))
        .filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES))
        .scalar()
        or 0
    )


def signal_is_stale(incident: Incident, now: Optional[datetime] = None) -> bool:
    """True when an active alert has not been re-notified for unusually long.

    Alertmanager repeats notifications for firing alerts; prolonged silence
    means the monitoring pipeline itself may be unhealthy, so the incident's
    'still firing' flag should not be trusted blindly.
    """
    if not incident.alert_active or incident.status not in ACTIVE_INCIDENT_STATUSES:
        return False
    limit = timedelta(seconds=settings_stale_after())
    return ((now or utcnow()) - incident.last_occurrence_at) > limit


def settings_stale_after() -> int:
    """Three missed repeat notifications (plus slack) mean the signal is stale."""
    return settings.ALERT_REPEAT_INTERVAL_SECONDS * 3 + 60


# ---------------------------------------------------------------------------
# Resolution (shared by alert-cleared, remediation verification and humans)
# ---------------------------------------------------------------------------
def resolve_incident(
    db: Session,
    incident: Incident,
    *,
    summary: str,
    evidence: Dict[str, Any],
    actor: Optional[User] = None,
    actor_label: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Move an active incident to RESOLVED with recorded verification evidence."""
    if incident.status not in ACTIVE_INCIDENT_STATUSES:
        return False
    previous = incident.status
    now = utcnow()
    incident.status = IncidentStatus.RESOLVED.value
    incident.resolved_at = now
    incident.resolution_summary = summary
    add_event(
        db,
        incident,
        "RESOLVED",
        actor=actor,
        actor_label=actor_label,
        previous_state=previous,
        new_state=IncidentStatus.RESOLVED.value,
        details=summary,
        metadata={"evidence": evidence},
    )
    record_audit(
        db,
        action="INCIDENT_RESOLVED",
        entity_type="incident",
        entity_id=incident.id,
        actor=actor,
        actor_label=actor_label,
        metadata={"previous_status": previous, "summary": summary, "evidence": evidence},
        correlation_id=correlation_id,
    )
    return True


def _cancel_unstarted_remediation(db: Session, incident: Incident, reason: str) -> None:
    """Requests that were never dispatched are pointless once the incident is resolved."""
    pending = (
        db.query(RemediationRequest)
        .filter(
            RemediationRequest.incident_id == incident.id,
            RemediationRequest.status.in_(
                [RemediationStatus.PENDING_APPROVAL.value, RemediationStatus.APPROVED.value]
            ),
        )
        .all()
    )
    for request in pending:
        previous = request.status
        request.status = RemediationStatus.CANCELLED.value
        request.completed_at = utcnow()
        request.failure_reason = reason
        add_event(
            db,
            incident,
            "REMEDIATION_CANCELLED",
            actor_label="system",
            details=f"Remediation request #{request.id} cancelled: {reason}",
        )
        record_audit(
            db,
            action="REMEDIATION_CANCELLED",
            entity_type="remediation_request",
            entity_id=request.id,
            actor_label="system",
            metadata={"previous_status": previous, "reason": reason},
            correlation_id=request.correlation_id,
        )


# ---------------------------------------------------------------------------
# Alert ingestion
# ---------------------------------------------------------------------------
def _lookup_resource(db: Session, labels: Dict[str, str]) -> Optional[MonitoredResource]:
    for candidate in (labels.get("resource"), labels.get("job")):
        if candidate:
            resource = (
                db.query(MonitoredResource)
                .filter(MonitoredResource.monitoring_identifier == candidate)
                .first()
            )
            if resource:
                return resource
    return None


def _handle_firing(db: Session, alert: Dict[str, Any], fingerprint: str) -> str:
    now = utcnow()
    labels = _clean_map(alert.get("labels") or {})
    annotations = _clean_map(alert.get("annotations") or {})
    alert_name = labels.get("alertname", "UnknownAlert")[:120]

    active = (
        db.query(Incident)
        .filter(
            Incident.alert_fingerprint == fingerprint,
            Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
        )
        .first()
    )
    if active is not None:
        # Repeated notification for a problem we already track: update, never duplicate.
        active.occurrence_count += 1
        active.last_occurrence_at = now
        active.alert_active = True
        last = active.events[-1] if active.events else None
        text = f"Alert notification repeated ({active.occurrence_count} notifications received)."
        if last is not None and last.event_type == "ALERT_REPEATED":
            last.details = text
            last.updated_at = now
            last.event_metadata = {"occurrences": active.occurrence_count}
        else:
            add_event(
                db,
                active,
                "ALERT_REPEATED",
                actor_label="alertmanager",
                details=text,
                metadata={"occurrences": active.occurrence_count},
            )
        return "deduplicated"

    reopen_window = int(get_setting(db, "incidents.reopen_window_minutes"))
    if reopen_window > 0:
        recent = (
            db.query(Incident)
            .filter(
                Incident.alert_fingerprint == fingerprint,
                Incident.status == IncidentStatus.RESOLVED.value,
                Incident.resolved_at >= now - timedelta(minutes=reopen_window),
            )
            .order_by(Incident.resolved_at.desc())
            .first()
        )
        if recent is not None:
            recent.status = IncidentStatus.OPEN.value
            recent.resolved_at = None
            recent.resolution_summary = None
            recent.alert_active = True
            recent.occurrence_count += 1
            recent.last_occurrence_at = now
            details = (
                f"The same alert fired again within {reopen_window} minutes of resolution; "
                "incident reopened."
            )
            add_event(
                db,
                recent,
                "REOPENED",
                actor_label="alertmanager",
                previous_state=IncidentStatus.RESOLVED.value,
                new_state=IncidentStatus.OPEN.value,
                details=details,
            )
            record_audit(
                db,
                action="INCIDENT_REOPENED",
                entity_type="incident",
                entity_id=recent.id,
                actor_label="alertmanager",
                metadata={"reason": details, "alert": alert_name},
            )
            return "reopened"

    resource = _lookup_resource(db, labels)
    severity = SEVERITY_MAP.get(labels.get("severity", "").lower(), Severity.MEDIUM.value)
    simulation_note = None
    if resource is not None and resource.monitoring_identifier == settings.DEMO_APP_JOB:
        simulation_note = demo_service.active_fault_marker()

    incident = Incident(
        title=(annotations.get("summary") or f"{alert_name} on {labels.get('instance', 'unknown')}")[:255],
        description=annotations.get("description", ""),
        severity=severity,
        status=IncidentStatus.OPEN.value,
        source="alertmanager",
        alert_name=alert_name,
        alert_fingerprint=fingerprint,
        resource_id=resource.id if resource else None,
        affected_resource=(
            resource.name if resource else labels.get("instance") or labels.get("job") or "unknown"
        )[:255],
        labels=labels,
        annotations=annotations,
        is_simulated=simulation_note is not None,
        simulation_note=simulation_note,
        alert_active=True,
        occurrence_count=1,
        detected_at=_parse_time(alert.get("startsAt")) or now,
        last_occurrence_at=now,
    )
    if incident.detected_at > now:
        incident.detected_at = now
    db.add(incident)
    db.flush()
    incident.action_code = action_for_incident(incident)[0]
    add_event(
        db,
        incident,
        "ALERT_RECEIVED",
        actor_label="alertmanager",
        new_state=IncidentStatus.OPEN.value,
        details=f"Incident opened from alert {alert_name}.",
        metadata={"fingerprint": fingerprint, "simulated": incident.is_simulated},
    )
    record_audit(
        db,
        action="INCIDENT_CREATED",
        entity_type="incident",
        entity_id=incident.id,
        actor_label="alertmanager",
        metadata={
            "alert": alert_name,
            "severity": severity,
            "resource": incident.affected_resource,
            "fingerprint": fingerprint,
            "simulated": incident.is_simulated,
        },
    )
    return "created"


def _handle_resolved(db: Session, alert: Dict[str, Any], fingerprint: str) -> str:
    ends_at = _parse_time(alert.get("endsAt"))
    active = (
        db.query(Incident)
        .filter(
            Incident.alert_fingerprint == fingerprint,
            Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
        )
        .first()
    )
    if active is None:
        # Already resolved (for example by a verified remediation): just note the signal.
        latest = (
            db.query(Incident)
            .filter(Incident.alert_fingerprint == fingerprint, Incident.alert_active.is_(True))
            .order_by(Incident.id.desc())
            .first()
        )
        if latest is not None:
            latest.alert_active = False
            add_event(
                db,
                latest,
                "ALERT_CLEARED",
                actor_label="alertmanager",
                details="Alertmanager confirmed the alert is no longer firing.",
            )
            return "cleared"
        return "ignored"

    active.alert_active = False
    evidence = {
        "source": "alertmanager",
        "signal": "alert resolved",
        "alert": active.alert_name,
        "ended_at": ends_at.isoformat() if ends_at else None,
    }
    add_event(
        db,
        active,
        "ALERT_CLEARED",
        actor_label="alertmanager",
        details="Alertmanager reported the alert as resolved.",
        metadata=evidence,
    )
    resolve_incident(
        db,
        active,
        summary="Resolved automatically: monitoring reported that the alert condition cleared.",
        evidence=evidence,
        actor_label="alertmanager",
    )
    _cancel_unstarted_remediation(
        db, active, "The incident was resolved by the monitoring signal before execution."
    )
    return "resolved"


def process_alerts(db: Session, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
    """Apply a validated Alertmanager webhook batch.  Each alert is atomic."""
    results = {"created": 0, "deduplicated": 0, "reopened": 0, "resolved": 0, "cleared": 0, "ignored": 0}
    for alert in alerts:
        labels = _clean_map(alert.get("labels") or {})
        fingerprint = (alert.get("fingerprint") or "").strip().lower() or compute_fingerprint(labels)
        fingerprint = fingerprint[:64]
        firing = alert.get("status") == "firing"
        handler = _handle_firing if firing else _handle_resolved
        try:
            with db.begin_nested():
                outcome = handler(db, alert, fingerprint)
        except IntegrityError:
            if not firing:
                raise
            # Lost a race with a concurrent delivery of the same alert: the partial
            # unique index kept the data consistent, so treat this one as a repeat.
            with db.begin_nested():
                outcome = _handle_firing(db, alert, fingerprint)
        results[outcome] += 1
        ALERT_WEBHOOK_EVENTS.labels(result=outcome).inc()
    db.commit()
    _refresh_gauge(db)
    return results


# ---------------------------------------------------------------------------
# Human-driven lifecycle
# ---------------------------------------------------------------------------
def transition_incident(
    db: Session,
    actor: User,
    incident: Incident,
    new_status: str,
    note: Optional[str] = None,
    override_monitoring: bool = False,
) -> Incident:
    current = incident.status
    note = (note or "").strip()
    if new_status not in TRANSITIONS.get(current, ()):
        allowed = ", ".join(TRANSITIONS.get(current, ())) or "none (terminal state)"
        raise IncidentError(
            f"Invalid transition {current} -> {new_status}. Allowed from {current}: {allowed}."
        )

    reopening = current == IncidentStatus.RESOLVED.value and new_status == IncidentStatus.OPEN.value
    if new_status == IncidentStatus.CLOSED.value or reopening:
        if not has_permission(actor, "incidents:close"):
            raise IncidentError("Only an Administrator can close or reopen an incident.", 403)
    if reopening and len(note) < MIN_RESOLUTION_NOTE:
        raise IncidentError("A reason is required to reopen an incident.", 422)

    metadata: Dict[str, Any] = {}
    now = utcnow()

    if new_status == IncidentStatus.RESOLVED.value:
        if len(note) < MIN_RESOLUTION_NOTE:
            raise IncidentError(
                "Resolution evidence is required: describe how recovery was verified "
                f"(at least {MIN_RESOLUTION_NOTE} characters).",
                422,
            )
        if incident.alert_active:
            job = incident.resource.monitoring_identifier if incident.resource else None
            firing, reason = monitoring_service.get_client().alert_is_firing(incident.alert_name, job)
            metadata["prometheus_alert_firing"] = firing
            if firing is False:
                incident.alert_active = False
            elif firing is True:
                # Positive evidence that the problem persists: nobody may resolve it.
                raise IncidentError(
                    "Monitoring still reports this alert as firing. The incident can only be "
                    "resolved once the condition has cleared."
                )
            elif override_monitoring and has_permission(actor, "incidents:close"):
                # Monitoring cannot answer either way: an Administrator may vouch for recovery.
                metadata["monitoring_override"] = True
                metadata["override_reason"] = reason or "monitoring unavailable"
            else:
                raise IncidentError(
                    "Recovery cannot be verified because Prometheus is unavailable "
                    f"({reason}). An Administrator may override with a documented reason."
                )
        resolve_incident(
            db,
            incident,
            summary=note,
            evidence={"source": "operator", "note": note, **metadata},
            actor=actor,
        )
        _cancel_unstarted_remediation(db, incident, "The incident was resolved manually.")
        db.commit()
        _refresh_gauge(db)
        return incident

    incident.status = new_status
    if new_status == IncidentStatus.ACKNOWLEDGED.value:
        incident.acknowledged_at = now
    elif new_status == IncidentStatus.IN_PROGRESS.value and incident.acknowledged_at is None:
        incident.acknowledged_at = now
    elif new_status == IncidentStatus.CLOSED.value:
        incident.closed_at = now
    elif reopening:
        incident.resolved_at = None
        incident.resolution_summary = None

    add_event(
        db,
        incident,
        "REOPENED" if reopening else "STATUS_CHANGED",
        actor=actor,
        previous_state=current,
        new_state=new_status,
        details=note,
    )
    record_audit(
        db,
        action="INCIDENT_REOPENED" if reopening else "INCIDENT_STATUS_CHANGED",
        entity_type="incident",
        entity_id=incident.id,
        actor=actor,
        metadata={"previous_status": current, "new_status": new_status, "note": note},
    )
    db.commit()
    _refresh_gauge(db)
    return incident


def add_comment(db: Session, actor: User, incident: Incident, note: str) -> IncidentEvent:
    event = add_event(db, incident, "COMMENT", actor=actor, details=note.strip())
    record_audit(
        db,
        action="INCIDENT_COMMENT_ADDED",
        entity_type="incident",
        entity_id=incident.id,
        actor=actor,
        metadata={"length": len(note)},
    )
    db.commit()
    return event


def record_denied_transition(db: Session, actor: User, incident: Incident, new_status: str, reason: str) -> None:
    record_audit(
        db,
        action="INCIDENT_STATUS_CHANGE_DENIED",
        entity_type="incident",
        entity_id=incident.id,
        actor=actor,
        outcome=AuditOutcome.DENIED,
        metadata={"requested_status": new_status, "current_status": incident.status, "reason": reason},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
_SORT = {
    "id": Incident.id,
    "detected_at": Incident.detected_at,
    "last_occurrence_at": Incident.last_occurrence_at,
    "status": Incident.status,
    "title": Incident.title,
    "occurrence_count": Incident.occurrence_count,
}


def list_incidents(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    q: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    active_only: bool = False,
    sort: str = "detected_at",
    order: str = "desc",
) -> Tuple[List[Incident], int]:
    query = db.query(Incident)
    if active_only:
        query = query.filter(Incident.status.in_(ACTIVE_INCIDENT_STATUSES))
    if status:
        query = query.filter(Incident.status.in_([s.strip().upper() for s in status.split(",")]))
    if severity:
        query = query.filter(Incident.severity.in_([s.strip().upper() for s in severity.split(",")]))
    if q:
        text = q.strip().lower()
        pattern = f"%{text}%"
        conditions = [
            func.lower(Incident.title).like(pattern),
            func.lower(Incident.description).like(pattern),
            func.lower(Incident.alert_name).like(pattern),
            func.lower(Incident.affected_resource).like(pattern),
        ]
        digits = text.lstrip("#").replace("inc-", "")
        if digits.isdigit():
            conditions.append(Incident.id == int(digits))
        query = query.filter(or_(*conditions))
    total = query.count()
    primary = severity_order(Incident.severity) if sort == "severity" else _SORT.get(sort, Incident.detected_at)
    ordering = primary.asc() if order == "asc" else primary.desc()
    items = (
        query.order_by(ordering, Incident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def allowed_transitions(actor: User, incident: Incident) -> List[str]:
    options = []
    for target in TRANSITIONS.get(incident.status, ()):
        admin_only = target == IncidentStatus.CLOSED.value or (
            incident.status == IncidentStatus.RESOLVED.value and target == IncidentStatus.OPEN.value
        )
        if admin_only and not has_permission(actor, "incidents:close"):
            continue
        options.append(target)
    return options
