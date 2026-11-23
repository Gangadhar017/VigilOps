"""Allowlist of automated remediation actions.

This catalog is the *only* place where executable actions are declared.  A
request can never name a command, script or file path - it can only reference
one of the codes below, and the worker has exactly one hard-coded handler per
code (``app/workers/actions.py``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.models.models import (
    ACTIVE_INCIDENT_STATUSES,
    FindingStatus,
    Incident,
    SecurityFinding,
)


@dataclass(frozen=True)
class ActionDefinition:
    code: str
    name: str
    description: str
    source_type: str  # "incident" | "finding"
    risk: str
    steps: Tuple[str, ...]
    verification: Tuple[str, ...]

    def as_dict(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type,
            "risk": self.risk,
            "steps": list(self.steps),
            "verification": list(self.verification),
        }


ACTION_RECOVER_APP = "ACTION-001"
ACTION_FIX_PUBLIC_STORAGE = "ACTION-002"

ACTIONS: Dict[str, ActionDefinition] = {
    ACTION_RECOVER_APP: ActionDefinition(
        code=ACTION_RECOVER_APP,
        name="Recover monitored demonstration application",
        description=(
            "Calls the demo application's token-protected internal recovery endpoint, which "
            "re-initialises its service component and clears any active fault condition."
        ),
        source_type="incident",
        risk="Low - affects only the demonstration application; no host or Docker access.",
        steps=(
            "Record the application's health before the action.",
            "Call POST /internal/recover on the demo application with the worker's recovery token.",
        ),
        verification=(
            "Three consecutive successful readiness checks against the application.",
            "Prometheus reports the scrape target as up with a sample newer than the action.",
            "The alert that opened the incident is no longer firing in Prometheus.",
        ),
    ),
    ACTION_FIX_PUBLIC_STORAGE: ActionDefinition(
        code=ACTION_FIX_PUBLIC_STORAGE,
        name="Correct public storage configuration",
        description=(
            "Updates the allowlisted YAML configuration so the affected storage bucket no "
            "longer permits public access (public_access: false, acl: private)."
        ),
        source_type="finding",
        risk="Low - edits one allowlisted sample configuration file inside the scan workspace.",
        steps=(
            "Confirm the target file is on the remediation allowlist.",
            "Set public_access to false and a public ACL to private for the affected bucket.",
            "Write the file atomically and record a before/after diff.",
        ),
        verification=(
            "Run the security scanner again on the corrected file.",
            "Confirm SEC-001 is no longer detected for the corrected resource.",
        ),
    ),
}


def list_actions() -> List[Dict[str, object]]:
    return [action.as_dict() for action in ACTIONS.values()]


def get_action(code: str) -> Optional[ActionDefinition]:
    return ACTIONS.get(code)


def action_for_incident(incident: Incident) -> Tuple[Optional[str], Optional[str]]:
    """Return (action_code, reason_if_unavailable) for an incident."""
    resource_job = incident.resource.monitoring_identifier if incident.resource else None
    if resource_job != settings.DEMO_APP_JOB:
        return None, "No automated action exists for this resource; follow the manual steps."
    if incident.status not in ACTIVE_INCIDENT_STATUSES:
        return None, f"The incident is already {incident.status}."
    return ACTION_RECOVER_APP, None


def action_for_finding(finding: SecurityFinding) -> Tuple[Optional[str], Optional[str]]:
    """Return (action_code, reason_if_unavailable) for a finding."""
    if finding.rule_id != "SEC-001":
        return None, (
            f"Automated correction is not implemented for {finding.rule_id}; "
            "apply the recommended change manually and run the scan again."
        )
    if finding.target_file not in settings.writable_target_names:
        return None, "This configuration file is not on the remediation allowlist."
    if finding.status != FindingStatus.OPEN.value:
        return None, f"The finding is {finding.status}; only OPEN findings can be remediated."
    return ACTION_FIX_PUBLIC_STORAGE, None
