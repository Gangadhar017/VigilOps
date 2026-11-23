"""Authorised, read-only live-data functions for VigilAI (safeguard layers 3-5).

VigilAI never receives database credentials and never builds SQL.  The only
platform data it can see is what the fixed functions below return.  Each one

* checks the *current user's* permission before reading anything,
* goes through the same service layer as the REST API (so RBAC scoping such as
  the Operator's audit view applies identically),
* returns a minimal, size-bounded summary (context minimisation), and
* only ever reads - there is no function here that changes state.

Which functions run for a question is decided by deterministic keyword routing
in ``select_tools`` - the language model does not choose or parameterise them.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.permissions import has_permission
from app.models.models import (
    ACTIVE_REMEDIATION_STATUSES,
    FindingStatus,
    Incident,
    RemediationRequest,
    SecurityFinding,
    User,
)
from app.services import (
    audit_service,
    incident_service,
    monitoring_service,
    remediation_service,
    scan_service,
)
from app.services.recommendations import finding_recommendation, incident_recommendation

MAX_ITEMS = 10
_MAX_TEXT = 300


def _clip(value: Optional[str], limit: int = _MAX_TEXT) -> str:
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _iso(value) -> Optional[str]:
    return value.isoformat(timespec="seconds") if value is not None else None


def _result(tool: str, data: Any) -> Dict[str, Any]:
    return {"tool": tool, "retrieved_at": _iso(utcnow()), "data": data}


def _denied(tool: str) -> Dict[str, Any]:
    return {
        "tool": tool,
        "retrieved_at": _iso(utcnow()),
        "denied": True,
        "data": "The current user's role is not permitted to view this information.",
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def get_monitoring_summary(db: Session, user: User) -> Dict[str, Any]:
    tool = "get_monitoring_summary"
    if not has_permission(user, "monitoring:view"):
        return _denied(tool)
    overview = monitoring_service.overview(db)
    resources = []
    for resource in overview["resources"]:
        metrics = {}
        for key, metric in (resource.get("metrics") or {}).items():
            metrics[key] = (
                {"value": round(metric["value"], 4), "unit": metric["unit"]}
                if metric.get("available")
                else {"value": None, "unavailable_reason": metric.get("reason")}
            )
        resources.append(
            {
                "name": resource["name"],
                "type": resource["resource_type"],
                "status": resource["status"],
                "metrics": metrics,
            }
        )
    return _result(
        tool,
        {
            "prometheus_available": overview["prometheus"]["available"],
            "prometheus_error": overview["prometheus"].get("error"),
            "alertmanager_available": overview["alertmanager"]["available"],
            "scrape_targets": [
                {
                    "job": t["job"],
                    "health": t["health"],
                    "last_error": _clip(t["last_error"], 160) if t["last_error"] else None,
                    "stale": t["stale"],
                }
                for t in overview["targets"]["targets"]
            ],
            "firing_alerts": [
                {"name": a["name"], "state": a["state"], "severity": a["severity"], "resource": a["resource"]}
                for a in overview["alerts"]["alerts"]
            ],
            "monitored_resources": resources,
        },
    )


def _incident_brief(incident: Incident) -> Dict[str, Any]:
    return {
        "id": incident.id,
        "title": _clip(incident.title, 160),
        "severity": incident.severity,
        "status": incident.status,
        "resource": incident.affected_resource,
        "alert": incident.alert_name,
        "alert_still_firing": incident.alert_active,
        "detected_at": _iso(incident.detected_at),
        "notifications_received": incident.occurrence_count,
        "triggered_by_demo_fault": incident.is_simulated,
    }


def get_authorized_open_incidents(db: Session, user: User) -> Dict[str, Any]:
    tool = "get_authorized_open_incidents"
    if not has_permission(user, "incidents:view"):
        return _denied(tool)
    items, total = incident_service.list_incidents(
        db, active_only=True, page_size=MAX_ITEMS, sort="severity", order="asc"
    )
    return _result(tool, {"open_incident_count": total, "incidents": [_incident_brief(i) for i in items]})


def get_authorized_incident_details(db: Session, user: User, incident_id: int) -> Dict[str, Any]:
    tool = "get_authorized_incident_details"
    if not has_permission(user, "incidents:view"):
        return _denied(tool)
    incident = db.get(Incident, incident_id)
    if incident is None:
        return _result(tool, {"error": f"Incident #{incident_id} does not exist."})
    recommendation = incident_recommendation(incident)
    return _result(
        tool,
        {
            **_incident_brief(incident),
            "description": _clip(incident.description),
            "resolved_at": _iso(incident.resolved_at),
            "resolution_summary": _clip(incident.resolution_summary),
            "timeline": [
                {"at": _iso(e.created_at), "type": e.event_type, "by": e.actor_label, "details": _clip(e.details, 200)}
                for e in incident.events[-8:]
            ],
            "remediation_requests": [
                {"id": r.id, "action": r.action_code, "status": r.status} for r in incident.remediation_requests
            ],
            "possible_causes": recommendation["possible_causes"],
            "recommended_steps": recommendation["recommended_steps"],
            "automated_action": recommendation["automation"]["action_code"],
        },
    )


def _finding_brief(finding: SecurityFinding) -> Dict[str, Any]:
    return {
        "id": finding.id,
        "rule": finding.rule_id,
        "rule_name": finding.rule_name,
        "severity": finding.severity,
        "status": finding.status,
        "resource": finding.resource_identifier,
        "file": finding.target_file,
        "evidence": _clip(str((finding.evidence or {}).get("summary", "")), 200),
    }


def get_authorized_security_findings(db: Session, user: User) -> Dict[str, Any]:
    tool = "get_authorized_security_findings"
    if not has_permission(user, "findings:view"):
        return _denied(tool)
    active = ",".join(
        [FindingStatus.OPEN.value, FindingStatus.REMEDIATION_PENDING.value, FindingStatus.ACCEPTED_RISK.value]
    )
    items, total = scan_service.list_findings(db, status=active, page_size=15)
    findings = []
    for finding in items:
        brief = _finding_brief(finding)
        brief["automated_action"] = finding_recommendation(finding)["automation"]["action_code"]
        findings.append(brief)
    return _result(tool, {"unresolved_finding_count": total, "findings": findings})


def get_latest_security_scan(db: Session, user: User) -> Dict[str, Any]:
    tool = "get_latest_security_scan"
    if not has_permission(user, "findings:view"):
        return _denied(tool)
    scan = scan_service.latest_scan(db)
    if scan is None:
        return _result(tool, {"message": "No security scan has been run yet."})
    summary = scan.result_summary or {}
    return _result(
        tool,
        {
            "scan_id": scan.id,
            "status": scan.status,
            "trigger": scan.trigger,
            "requested_by": scan.requested_by_label,
            "completed_at": _iso(scan.completed_at),
            "files_scanned": summary.get("files_scanned"),
            "violations_detected": summary.get("violations_detected"),
            "new_findings": summary.get("new_findings"),
            "resolved_findings": summary.get("resolved_findings"),
            "by_rule": summary.get("by_rule"),
            "error": _clip(scan.error),
        },
    )


def _remediation_brief(request: RemediationRequest) -> Dict[str, Any]:
    return {
        "id": request.id,
        "action": request.action_code,
        "status": request.status,
        "target": _clip(request.target, 160),
        "source": f"{request.source_type} #{request.source_id}",
        "requested_by": request.requester.email if request.requester else None,
        "approved_by": request.approver.email if request.approver else None,
        "requested_at": _iso(request.created_at),
        "attempts": request.attempt_count,
        "failure_reason": _clip(request.failure_reason, 200) or None,
    }


def get_authorized_remediation_requests(
    db: Session, user: User, *, mine: bool = False, pending_only: bool = False
) -> Dict[str, Any]:
    tool = "get_authorized_remediation_requests"
    if not has_permission(user, "remediation:view"):
        return _denied(tool)
    items, total = remediation_service.list_requests(
        db,
        status=",".join(ACTIVE_REMEDIATION_STATUSES) if pending_only else None,
        requested_by=user.id if mine else None,
        page_size=MAX_ITEMS,
    )
    return _result(
        tool,
        {
            "filter": {"only_my_requests": mine, "only_in_progress": pending_only},
            "matching_request_count": total,
            "requests": [_remediation_brief(r) for r in items],
        },
    )


def get_authorized_remediation_status(db: Session, user: User, request_id: int) -> Dict[str, Any]:
    tool = "get_authorized_remediation_status"
    if not has_permission(user, "remediation:view"):
        return _denied(tool)
    request = db.get(RemediationRequest, request_id)
    if request is None:
        return _result(tool, {"error": f"Remediation request #{request_id} does not exist."})
    latest = request.executions[-1] if request.executions else None
    return _result(
        tool,
        {
            **_remediation_brief(request),
            "justification": _clip(request.justification, 200),
            "decision_comment": _clip(request.decision_comment, 200) or None,
            "latest_execution": (
                {
                    "attempt": latest.attempt,
                    "status": latest.status,
                    "verification_passed": (latest.verification_result or {}).get("passed"),
                    "verification_summary": _clip((latest.verification_result or {}).get("summary"), 240),
                }
                if latest
                else None
            ),
        },
    )


def get_recent_audit_events(db: Session, user: User) -> Dict[str, Any]:
    tool = "get_recent_audit_events"
    if not has_permission(user, "audit:view"):
        return _denied(tool)
    # list_audit_events applies the viewer's visibility rules (operators: operational events).
    items, _total = audit_service.list_audit_events(db, user, page_size=8)
    return _result(
        tool,
        {
            "events": [
                {
                    "at": _iso(e.created_at),
                    "actor": e.actor_label,
                    "action": e.action,
                    "entity": f"{e.entity_type} {e.entity_id or ''}".strip(),
                    "outcome": e.outcome,
                }
                for e in items
            ]
        },
    )


# ---------------------------------------------------------------------------
# Deterministic routing
# ---------------------------------------------------------------------------
_RE_INCIDENT_ID = re.compile(r"\b(?:incident|inc)[\s#\-:]*(\d{1,9})\b", re.IGNORECASE)
# "request #7" or "remediation (request) 7" - but not "HTTP request 500 errors".
_RE_REMEDIATION_ID = re.compile(
    r"\b(?:remediation(?:\s+request)?|rem)[\s#\-:]*(\d{1,9})\b|\brequest\s*#\s*(\d{1,9})\b", re.IGNORECASE
)
_RE_INCIDENTS = re.compile(r"\b(incidents?|outage|alerts?\s+(fired|firing|open)|what\s+caused)\b", re.IGNORECASE)
_RE_HEALTH = re.compile(
    r"\b(unhealthy|healthy|health|down|unavailable|outage|slow|latency|error\s+rate|[45]xx|http\s*[45]\d\d|[45]\d\d\s+errors?|"
    r"cpu|memory|uptime|metrics?|monitor\w*|prometheus|alertmanager|targets?|scrap\w*|"
    r"(?:platform|system|service|application|app|server)\s+status|"
    r"request\s+rate|telemetry|firing)\b",
    re.IGNORECASE,
)
_RE_FINDINGS = re.compile(
    r"\b(findings?|misconfigur\w*|vulnerab\w*|sec-?00[1-5]|security\s+(issue|problem|posture|status)\w*|"
    r"public\s+(storage|access|bucket)|encrypt\w*|wildcard|iam|inbound|ingress|privileged)\b",
    re.IGNORECASE,
)
_RE_SCAN = re.compile(r"\b(scan\w*)\b", re.IGNORECASE)
_RE_REMEDIATION = re.compile(r"\b(remediat\w*|approv\w*|pending\s+(request|approval)s?)\b", re.IGNORECASE)
_RE_AUDIT = re.compile(r"\b(audit\w*|who\s+(approved|did|changed|ran|requested|rejected)|history|recent\s+(activity|events?))\b", re.IGNORECASE)
_RE_MINE = re.compile(r"\b(my|mine|i\s+(submitted|requested|created|raised))\b", re.IGNORECASE)
_RE_PENDING = re.compile(r"\b(pending|waiting|awaiting|in\s+progress|open|queued|running|current)\b", re.IGNORECASE)
# "What does SEC-001 mean?" is a documentation question - no live data needed.
_RE_DEFINITION = re.compile(r"^\s*(what\s+(does|is|are)|explain|define|describe)\b.*\b(mean|means|is|are|rule)\b", re.IGNORECASE)

ToolCall = Callable[[Session, User], Dict[str, Any]]


def select_tools(message: str) -> List[Tuple[str, ToolCall]]:
    """Choose which read-only functions provide context for this question."""
    calls: List[Tuple[str, ToolCall]] = []
    names: set = set()

    def add(name: str, call: ToolCall) -> None:
        if name not in names:
            names.add(name)
            calls.append((name, call))

    incident_id = _RE_INCIDENT_ID.search(message)
    remediation_id = _RE_REMEDIATION_ID.search(message)
    definition = bool(_RE_DEFINITION.match(message)) and not _RE_MINE.search(message)

    if incident_id:
        value = int(incident_id.group(1))
        add("incident_details", lambda db, user, v=value: get_authorized_incident_details(db, user, v))
    if remediation_id and not incident_id:
        value = int(remediation_id.group(1) or remediation_id.group(2))
        add("remediation_status", lambda db, user, v=value: get_authorized_remediation_status(db, user, v))

    if not definition:
        if _RE_HEALTH.search(message):
            add("monitoring", get_monitoring_summary)
            add("open_incidents", get_authorized_open_incidents)
        if _RE_INCIDENTS.search(message) and not incident_id:
            add("open_incidents", get_authorized_open_incidents)
        if _RE_FINDINGS.search(message):
            add("findings", get_authorized_security_findings)
        if _RE_SCAN.search(message):
            add("latest_scan", get_latest_security_scan)
            add("findings", get_authorized_security_findings)
        if _RE_REMEDIATION.search(message) and not remediation_id:
            mine = bool(_RE_MINE.search(message))
            pending = bool(_RE_PENDING.search(message))
            add(
                "remediation_requests",
                lambda db, user, m=mine, p=pending: get_authorized_remediation_requests(
                    db, user, mine=m, pending_only=p
                ),
            )
        if _RE_AUDIT.search(message):
            add("audit", get_recent_audit_events)
    return calls[:4]


def run_tools(db: Session, user: User, calls: List[Tuple[str, ToolCall]]) -> List[Dict[str, Any]]:
    results = []
    for name, call in calls:
        try:
            results.append(call(db, user))
        except Exception as exc:  # noqa: BLE001 - a failing tool must not break the chat
            results.append(
                {
                    "tool": name,
                    "retrieved_at": _iso(utcnow()),
                    "error": f"Live data could not be retrieved ({exc.__class__.__name__}).",
                }
            )
    return results
