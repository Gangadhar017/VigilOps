"""Audit trail.

``record_audit`` adds an event to the *caller's* transaction so that a state
change and its audit record are committed atomically.  There is deliberately no
update or delete function: audit history is append-only (PostgreSQL also
enforces this with a trigger, see the initial migration).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.core.request_context import get_client_ip, get_request_id
from app.models.models import AuditEvent, AuditOutcome, Role, User

_SENSITIVE_KEY = re.compile(r"(?i)(password|passwd|passphrase|secret|token|api[_-]?key|authorization|credential)")
_MAX_STRING = 600
_MAX_ITEMS = 40

# Actions an Operator may see: operational history, plus any event they performed themselves.
OPERATOR_VISIBLE_PREFIXES = (
    "INCIDENT_",
    "SECURITY_SCAN_",
    "FINDING_",
    "REMEDIATION_",
    "DEMO_",
)


def sanitize_metadata(value: Any, depth: int = 0) -> Any:
    """Recursively strip credentials and bound the size of audit metadata."""
    if depth > 5:
        return "[truncated]"
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                cleaned["_truncated"] = True
                break
            key_text = str(key)
            if _SENSITIVE_KEY.search(key_text):
                cleaned[key_text] = "[REDACTED]"
            else:
                cleaned[key_text] = sanitize_metadata(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple, set)):
        return [sanitize_metadata(item, depth + 1) for item in list(value)[:_MAX_ITEMS]]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value if len(value) <= _MAX_STRING else value[:_MAX_STRING] + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:_MAX_STRING]


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: Optional[Any] = None,
    actor: Optional[User] = None,
    actor_label: Optional[str] = None,
    outcome: AuditOutcome | str = AuditOutcome.SUCCESS,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> AuditEvent:
    """Append an audit event to the current transaction (the caller commits)."""
    outcome_value = outcome.value if isinstance(outcome, AuditOutcome) else str(outcome)
    event = AuditEvent(
        actor_id=actor.id if actor is not None else None,
        actor_label=actor_label or (actor.email if actor is not None else "system"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        outcome=outcome_value,
        event_metadata=sanitize_metadata(metadata or {}),
        correlation_id=correlation_id or get_request_id(),
        source_ip=get_client_ip(),
    )
    db.add(event)
    return event


_SORTABLE = {
    "created_at": AuditEvent.created_at,
    "action": AuditEvent.action,
    "outcome": AuditEvent.outcome,
    "actor": AuditEvent.actor_label,
    "entity_type": AuditEvent.entity_type,
}


def _apply_visibility(query, viewer: User):
    """Operators see operational events and their own authentication events."""
    if viewer.role == Role.ADMIN.value:
        return query
    operational = or_(*[AuditEvent.action.like(prefix + "%") for prefix in OPERATOR_VISIBLE_PREFIXES])
    return query.filter(or_(operational, AuditEvent.actor_id == viewer.id))


def list_audit_events(
    db: Session,
    viewer: User,
    *,
    page: int = 1,
    page_size: int = 25,
    q: Optional[str] = None,
    action: Optional[str] = None,
    category: Optional[str] = None,
    outcome: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    actor: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort: str = "created_at",
    order: str = "desc",
) -> Tuple[list[AuditEvent], int]:
    query = _apply_visibility(db.query(AuditEvent), viewer)

    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(AuditEvent.action).like(pattern),
                func.lower(AuditEvent.actor_label).like(pattern),
                func.lower(AuditEvent.entity_type).like(pattern),
                func.lower(func.coalesce(AuditEvent.entity_id, "")).like(pattern),
                func.lower(func.coalesce(AuditEvent.correlation_id, "")).like(pattern),
                func.lower(cast(AuditEvent.event_metadata, String)).like(pattern),
            )
        )
    if action:
        query = query.filter(AuditEvent.action == action.upper())
    if category:
        query = query.filter(AuditEvent.action.like(category.upper() + "_%"))
    if outcome:
        query = query.filter(AuditEvent.outcome == outcome.upper())
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditEvent.entity_id == str(entity_id))
    if correlation_id:
        query = query.filter(AuditEvent.correlation_id == correlation_id)
    if actor:
        query = query.filter(func.lower(AuditEvent.actor_label).like(f"%{actor.strip().lower()}%"))
    if date_from:
        query = query.filter(AuditEvent.created_at >= date_from)
    if date_to:
        query = query.filter(AuditEvent.created_at <= date_to)

    total = query.count()
    column = _SORTABLE.get(sort, AuditEvent.created_at)
    ordering = column.asc() if order == "asc" else column.desc()
    items = (
        query.order_by(ordering, AuditEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_audit_event(db: Session, viewer: User, event_pk: int) -> Optional[AuditEvent]:
    return _apply_visibility(db.query(AuditEvent), viewer).filter(AuditEvent.id == event_pk).first()


def entity_history(db: Session, entity_type: str, entity_id: Any, limit: int = 100) -> list[AuditEvent]:
    """Chronological audit history of one entity (used for detail timelines)."""
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == str(entity_id))
        .order_by(AuditEvent.id.asc())
        .limit(limit)
        .all()
    )


def correlation_history(db: Session, correlation_id: str, limit: int = 200) -> list[AuditEvent]:
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.correlation_id == correlation_id)
        .order_by(AuditEvent.id.asc())
        .limit(limit)
        .all()
    )
