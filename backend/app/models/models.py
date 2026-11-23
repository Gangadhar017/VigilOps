"""SQLAlchemy models for the VigilOps operational database.

Conventions
-----------
* Every timestamp is timezone-aware UTC (``UTCDateTime``).
* Status / severity columns hold upper-case string constants that are also
  enforced with CHECK constraints.
* Deduplication keys are enforced by the database (partial unique indexes),
  not only by application code.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UTCDateTime, utcnow


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class Role(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"


class Severity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


ACTIVE_INCIDENT_STATUSES = (
    IncidentStatus.OPEN.value,
    IncidentStatus.ACKNOWLEDGED.value,
    IncidentStatus.IN_PROGRESS.value,
)


class FindingStatus(str, enum.Enum):
    OPEN = "OPEN"
    REMEDIATION_PENDING = "REMEDIATION_PENDING"
    RESOLVED = "RESOLVED"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class ScanStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RemediationStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# A source (incident / finding) may have at most one request in these states.
ACTIVE_REMEDIATION_STATUSES = (
    RemediationStatus.PENDING_APPROVAL.value,
    RemediationStatus.APPROVED.value,
    RemediationStatus.QUEUED.value,
    RemediationStatus.RUNNING.value,
    RemediationStatus.VERIFYING.value,
)


class AuditOutcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


def _in_list(column: str, values) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def _enum_values(enum_cls) -> list[str]:
    return [member.value for member in enum_cls]


# ---------------------------------------------------------------------------
# Users and sessions
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in_list("role", _enum_values(Role)), name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=Role.OPERATOR.value)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Incremented on password / role change or deactivation: invalidates all tokens.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class RevokedToken(Base):
    """JWT identifiers revoked by an explicit logout (until natural expiry)."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
class MonitoredResource(Base):
    __tablename__ = "monitored_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    # Prometheus ``job`` label that identifies this resource.
    monitoring_identifier: Mapped[Optional[str]] = mapped_column(
        String(120), unique=True, nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Last status observed from Prometheus: UP | DOWN | UNKNOWN
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    status_checked_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------
class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            _in_list("status", _enum_values(IncidentStatus)), name="ck_incidents_status"
        ),
        CheckConstraint(
            _in_list("severity", _enum_values(Severity)), name="ck_incidents_severity"
        ),
        # Deterministic deduplication: one *active* incident per alert fingerprint.
        Index(
            "uq_incidents_active_fingerprint",
            "alert_fingerprint",
            unique=True,
            postgresql_where=text(_in_list("status", ACTIVE_INCIDENT_STATUSES)),
            sqlite_where=text(_in_list("status", ACTIVE_INCIDENT_STATUSES)),
        ),
        Index("ix_incidents_status_severity", "status", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentStatus.OPEN.value, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="alertmanager")
    alert_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    alert_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitored_resources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    affected_resource: Mapped[str] = mapped_column(String(255), nullable=False, default="unknown")
    labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    annotations: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Allowlisted automated action suggested for this incident (may be NULL).
    action_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # True when the incident was triggered while a controlled demo fault was active.
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    simulation_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Does monitoring still report the alert as firing?
    alert_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, index=True)
    last_occurrence_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    resource: Mapped[Optional[MonitoredResource]] = relationship(lazy="joined")
    events: Mapped[List["IncidentEvent"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentEvent.id",
    )
    remediation_requests: Mapped[List["RemediationRequest"]] = relationship(
        back_populates="incident", order_by="RemediationRequest.id"
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    incident: Mapped[Incident] = relationship(back_populates="events")


# ---------------------------------------------------------------------------
# Security scanning
# ---------------------------------------------------------------------------
class SecurityScan(Base):
    __tablename__ = "security_scans"
    __table_args__ = (
        CheckConstraint(_in_list("status", _enum_values(ScanStatus)), name="ck_scans_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_by_label: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    # MANUAL | REMEDIATION_VERIFICATION | DEMO_RESET
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="MANUAL")
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ScanStatus.RUNNING.value)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SecurityFinding(Base):
    __tablename__ = "security_findings"
    __table_args__ = (
        CheckConstraint(
            _in_list("status", _enum_values(FindingStatus)), name="ck_findings_status"
        ),
        CheckConstraint(
            _in_list("severity", _enum_values(Severity)), name="ck_findings_severity"
        ),
        Index("ix_findings_status_severity", "status", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Scan that first detected the finding / scan that most recently evaluated it.
    scan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("security_scans.id", ondelete="SET NULL"), nullable=True
    )
    last_scan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("security_scans.id", ondelete="SET NULL"), nullable=True
    )
    # sha256(target file | rule | resource type | resource name) - the dedup key.
    stable_finding_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    rule_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    target_file: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(160), nullable=False)
    resource_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=FindingStatus.OPEN.value, index=True
    )
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_detected_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    accepted_risk_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_risk_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accepted_risk_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    remediation_requests: Mapped[List["RemediationRequest"]] = relationship(
        back_populates="finding", order_by="RemediationRequest.id"
    )


# ---------------------------------------------------------------------------
# Remediation
# ---------------------------------------------------------------------------
class RemediationRequest(Base):
    __tablename__ = "remediation_requests"
    __table_args__ = (
        CheckConstraint(
            _in_list("status", _enum_values(RemediationStatus)), name="ck_remediation_status"
        ),
        CheckConstraint(
            _in_list("source_type", ("incident", "finding")), name="ck_remediation_source_type"
        ),
        # Exactly one source must be referenced.
        CheckConstraint(
            "(incident_id IS NOT NULL AND finding_id IS NULL) OR "
            "(incident_id IS NULL AND finding_id IS NOT NULL)",
            name="ck_remediation_single_source",
        ),
        # Idempotency: at most one in-flight request per source.
        Index(
            "uq_remediation_active_incident",
            "incident_id",
            unique=True,
            postgresql_where=text(
                "incident_id IS NOT NULL AND " + _in_list("status", ACTIVE_REMEDIATION_STATUSES)
            ),
            sqlite_where=text(
                "incident_id IS NOT NULL AND " + _in_list("status", ACTIVE_REMEDIATION_STATUSES)
            ),
        ),
        Index(
            "uq_remediation_active_finding",
            "finding_id",
            unique=True,
            postgresql_where=text(
                "finding_id IS NOT NULL AND " + _in_list("status", ACTIVE_REMEDIATION_STATUSES)
            ),
            sqlite_where=text(
                "finding_id IS NOT NULL AND " + _in_list("status", ACTIVE_REMEDIATION_STATUSES)
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    correlation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True, default=lambda: str(uuid.uuid4())
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    incident_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    finding_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("security_findings.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    action_code: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # Administrator who approved or rejected the request.
    approved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RemediationStatus.PENDING_APPROVAL.value, index=True
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    decision_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    incident: Mapped[Optional[Incident]] = relationship(back_populates="remediation_requests")
    finding: Mapped[Optional[SecurityFinding]] = relationship(back_populates="remediation_requests")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by], lazy="joined")
    approver: Mapped[Optional[User]] = relationship(foreign_keys=[approved_by], lazy="joined")
    executions: Mapped[List["RemediationExecution"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="RemediationExecution.id",
    )

    @property
    def source_id(self) -> int:
        return self.incident_id if self.source_type == "incident" else self.finding_id  # type: ignore[return-value]


class RemediationExecution(Base):
    __tablename__ = "remediation_executions"
    __table_args__ = (
        UniqueConstraint("request_id", "attempt", name="uq_execution_request_attempt"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("remediation_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_identifier: Mapped[str] = mapped_column(String(120), nullable=False)
    # RUNNING | VERIFYING | SUCCEEDED | FAILED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    execution_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    verification_result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    request: Mapped[RemediationRequest] = relationship(back_populates="executions")


# ---------------------------------------------------------------------------
# Audit trail (append-only)
# ---------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(_in_list("outcome", _enum_values(AuditOutcome)), name="ck_audit_outcome"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    # RESTRICT: audit rows are immutable, so a user with audit history is
    # deactivated, never deleted.
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # E-mail of the user, or a service identity such as "alertmanager" / "worker".
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, index=True)


# ---------------------------------------------------------------------------
# Runtime settings, worker liveness and demo tasks
# ---------------------------------------------------------------------------
class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    jobs_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DemoTask(Base):
    """Demo-environment maintenance performed by the restricted worker.

    The API container mounts the scan workspace read-only, so resetting the
    sample configuration to its insecure baseline is queued here and executed
    by the worker (the only component with write access).
    """

    __tablename__ = "demo_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # QUEUED | RUNNING | SUCCEEDED | FAILED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED", index=True)
    requested_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
