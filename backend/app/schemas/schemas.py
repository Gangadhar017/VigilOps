"""Pydantic request and response models (input validation + OpenAPI contract)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class Message(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Authentication and users
# ---------------------------------------------------------------------------
_EMAIL_PATTERN = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=_EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value


class UserOut(ORMModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class SessionUser(UserOut):
    permissions: List[str] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: SessionUser


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    email: str = Field(max_length=255, pattern=_EMAIL_PATTERN)
    full_name: str = Field(default="", max_length=120)
    password: str = Field(min_length=1, max_length=128)
    role: Literal["admin", "operator"] = "operator"

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=120)
    role: Optional[Literal["admin", "operator"]] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SettingUpdate(BaseModel):
    value: Any


# ---------------------------------------------------------------------------
# Alertmanager webhook (https://prometheus.io/docs/alerting/latest/configuration/#webhook_config)
# ---------------------------------------------------------------------------
class AlertmanagerAlert(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["firing", "resolved"]
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    startsAt: Optional[str] = Field(default=None, max_length=64)
    endsAt: Optional[str] = Field(default=None, max_length=64)
    fingerprint: Optional[str] = Field(default=None, max_length=64, pattern=r"^[A-Fa-f0-9]{8,64}$")

    @field_validator("labels")
    @classmethod
    def _require_alertname(cls, value: Dict[str, str]) -> Dict[str, str]:
        if not value.get("alertname"):
            raise ValueError("labels.alertname is required")
        if len(value) > 60:
            raise ValueError("too many labels")
        return value


class AlertmanagerWebhook(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: Optional[str] = None
    status: Optional[str] = None
    receiver: Optional[str] = None
    alerts: List[AlertmanagerAlert] = Field(min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------
class IncidentEventOut(ORMModel):
    id: int
    event_type: str
    actor_label: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    details: str
    event_metadata: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class RemediationBrief(ORMModel):
    id: int
    action_code: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class IncidentOut(ORMModel):
    id: int
    title: str
    description: str
    severity: str
    status: str
    source: str
    alert_name: str
    alert_fingerprint: str
    resource_id: Optional[int] = None
    affected_resource: str
    action_code: Optional[str] = None
    is_simulated: bool
    simulation_note: Optional[str] = None
    alert_active: bool
    occurrence_count: int
    detected_at: datetime
    last_occurrence_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None
    signal_stale: bool = False


class IncidentDetail(IncidentOut):
    labels: Dict[str, Any] = {}
    annotations: Dict[str, Any] = {}
    events: List[IncidentEventOut] = []
    remediation_requests: List[RemediationBrief] = []
    recommendation: Dict[str, Any] = {}
    allowed_transitions: List[str] = []


class IncidentTransition(BaseModel):
    status: Literal["ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "CLOSED", "OPEN"]
    note: Optional[str] = Field(default=None, max_length=2000)
    override_monitoring: bool = False


class IncidentComment(BaseModel):
    note: str = Field(min_length=2, max_length=2000)


# ---------------------------------------------------------------------------
# Security scanning
# ---------------------------------------------------------------------------
class ScanRequest(BaseModel):
    target: Optional[str] = Field(default=None, max_length=130)


class ScanOut(ORMModel):
    id: int
    requested_by: Optional[int] = None
    requested_by_label: str
    trigger: str
    target: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    result_summary: Dict[str, Any] = {}
    error: Optional[str] = None


class FindingOut(ORMModel):
    id: int
    scan_id: Optional[int] = None
    last_scan_id: Optional[int] = None
    stable_finding_key: str
    rule_id: str
    rule_name: str
    severity: str
    target_file: str
    resource_type: str
    resource_name: str
    resource_identifier: str
    evidence: Dict[str, Any] = {}
    recommendation: str
    status: str
    detection_count: int
    first_detected_at: datetime
    last_seen_at: datetime
    resolved_at: Optional[datetime] = None
    accepted_risk_reason: Optional[str] = None
    accepted_risk_at: Optional[datetime] = None


class FindingDetail(FindingOut):
    rule: Optional[Dict[str, Any]] = None
    guidance: Dict[str, Any] = {}
    remediation_requests: List[RemediationBrief] = []
    history: List[Dict[str, Any]] = []


class AcceptRiskRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


# ---------------------------------------------------------------------------
# Remediation
# ---------------------------------------------------------------------------
class RemediationCreate(BaseModel):
    source_type: Literal["incident", "finding"]
    source_id: int = Field(gt=0)
    action_code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Z]+-\d{3}$")
    justification: str = Field(min_length=10, max_length=2000)


class RemediationDecision(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=2000)


class ExecutionOut(ORMModel):
    id: int
    attempt: int
    worker_identifier: str
    status: str
    execution_details: Dict[str, Any] = {}
    verification_result: Dict[str, Any] = {}
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class RemediationOut(ORMModel):
    id: int
    correlation_id: str
    source_type: str
    source_id: int
    incident_id: Optional[int] = None
    finding_id: Optional[int] = None
    action_code: str
    action_name: Optional[str] = None
    target: str
    status: str
    justification: str
    decision_comment: Optional[str] = None
    requested_by: int
    requested_by_email: Optional[str] = None
    approved_by: Optional[int] = None
    approved_by_email: Optional[str] = None
    attempt_count: int
    max_attempts: int
    failure_reason: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    allowed_operations: List[str] = []


class RemediationDetail(RemediationOut):
    executions: List[ExecutionOut] = []
    action: Optional[Dict[str, Any]] = None
    source_summary: Dict[str, Any] = {}
    timeline: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditEventOut(ORMModel):
    id: int
    event_id: str
    actor_id: Optional[int] = None
    actor_label: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    outcome: str
    event_metadata: Dict[str, Any] = Field(default_factory=dict, serialization_alias="metadata")
    correlation_id: Optional[str] = None
    source_ip: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# VigilAI
# ---------------------------------------------------------------------------
class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class ChatResponse(BaseModel):
    reply: str
    mode: Literal["ai", "fallback", "refusal"]
    scope: str
    notice: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    sources: List[Dict[str, Any]] = []
    live_data: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Demo controls
# ---------------------------------------------------------------------------
class FaultRequest(BaseModel):
    mode: Literal["none", "outage", "errors", "latency", "cpu", "memory"]
