"""Deterministic security rules SEC-001 … SEC-005.

Each rule is a pure function ``(resource: dict) -> list[RuleMatch]``.  Rules do
no I/O and have no randomness, so scanning the same document always yields the
same findings.  Rule *metadata* is loaded from ``security-rules/policies.yaml``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from app.core.config import settings

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

# Ports whose exposure to the whole internet is treated as a violation.
SENSITIVE_PORTS: Dict[int, str] = {
    22: "SSH",
    23: "Telnet",
    3389: "RDP",
    1433: "MSSQL",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    9200: "Elasticsearch",
    27017: "MongoDB",
}
OPEN_CIDRS = {"0.0.0.0/0", "::/0"}
PUBLIC_ACLS = {"public-read", "public-read-write"}


@dataclass(frozen=True)
class RuleMatch:
    """One violation of a rule on one resource."""

    evidence: Dict[str, Any]
    summary: str


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: str
    description: str
    detection_logic: str
    impact: str
    recommendation: str
    resource_types: tuple
    automated_action: Optional[str]
    evaluate: Callable[[Dict[str, Any]], List[RuleMatch]] = field(compare=False, repr=False)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "severity": self.severity,
            "description": self.description,
            "detection_logic": self.detection_logic,
            "impact": self.impact,
            "recommendation": self.recommendation,
            "resource_types": list(self.resource_types),
            "automated_action": self.automated_action,
        }


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------
def _sec_001_public_storage(resource: Dict[str, Any]) -> List[RuleMatch]:
    public_flag = resource.get("public_access")
    acl = resource.get("acl")
    acl_text = str(acl).strip().lower() if acl is not None else None

    reasons: Dict[str, Any] = {}
    if public_flag is True:
        reasons["public_access"] = True
    if acl_text in PUBLIC_ACLS:
        reasons["acl"] = acl_text
    if not reasons:
        return []
    described = ", ".join(f"{key} = {str(value).lower()}" for key, value in reasons.items())
    return [RuleMatch(evidence=reasons, summary=f"Bucket allows public access ({described}).")]


def _sec_002_missing_encryption(resource: Dict[str, Any]) -> List[RuleMatch]:
    encryption = resource.get("encryption")
    if not isinstance(encryption, dict):
        return [
            RuleMatch(
                evidence={"encryption": None},
                summary="No encryption block is defined for this resource.",
            )
        ]
    enabled = encryption.get("enabled")
    algorithm = encryption.get("algorithm")
    algorithm_text = str(algorithm).strip().upper() if algorithm is not None else ""
    if enabled is not True:
        return [
            RuleMatch(
                evidence={"encryption.enabled": enabled, "encryption.algorithm": algorithm},
                summary="Encryption at rest is disabled.",
            )
        ]
    if algorithm_text in ("", "NONE"):
        return [
            RuleMatch(
                evidence={"encryption.enabled": True, "encryption.algorithm": algorithm},
                summary="Encryption is enabled but no algorithm is configured.",
            )
        ]
    return []


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _sec_003_wildcard_iam(resource: Dict[str, Any]) -> List[RuleMatch]:
    matches: List[RuleMatch] = []
    for index, statement in enumerate(_as_list(resource.get("statements"))):
        if not isinstance(statement, dict):
            continue
        if str(statement.get("effect", "Allow")).strip().lower() != "allow":
            continue
        actions = [str(a) for a in _as_list(statement.get("actions"))]
        resources = [str(r) for r in _as_list(statement.get("resources"))]
        wildcard_actions = sorted(a for a in actions if a == "*" or a.endswith(":*"))
        wildcard_resources = sorted(r for r in resources if r == "*")
        if not wildcard_actions and not wildcard_resources:
            continue
        parts = []
        if wildcard_actions:
            parts.append("actions " + ", ".join(wildcard_actions))
        if wildcard_resources:
            parts.append("resources *")
        matches.append(
            RuleMatch(
                evidence={
                    "statement_index": index,
                    "wildcard_actions": wildcard_actions,
                    "wildcard_resources": wildcard_resources,
                },
                summary=f"Allow statement #{index} grants wildcard " + " and ".join(parts) + ".",
            )
        )
    return matches


def _port_span(rule: Dict[str, Any]) -> Optional[tuple]:
    """Return (low, high) for an ingress rule, or None when it cannot be read."""
    protocol = str(rule.get("protocol", "tcp")).strip().lower()
    if protocol in ("all", "-1", "any"):
        return 0, 65535
    if "port_range" in rule and rule.get("port_range") is not None:
        text = str(rule["port_range"]).strip()
        low_text, _, high_text = text.partition("-")
        try:
            low, high = int(low_text), int(high_text or low_text)
        except ValueError:
            return None
        return (low, high) if low <= high else (high, low)
    port = rule.get("port")
    if isinstance(port, bool) or not isinstance(port, int):
        return None
    return port, port


def _sec_004_open_ingress(resource: Dict[str, Any]) -> List[RuleMatch]:
    matches: List[RuleMatch] = []
    for index, rule in enumerate(_as_list(resource.get("ingress"))):
        if not isinstance(rule, dict):
            continue
        cidr = str(rule.get("cidr", "")).strip()
        if cidr not in OPEN_CIDRS:
            continue
        span = _port_span(rule)
        if span is None:
            continue
        low, high = span
        exposed = sorted(port for port in SENSITIVE_PORTS if low <= port <= high)
        if not exposed:
            continue
        labels = [f"{port} ({SENSITIVE_PORTS[port]})" for port in exposed]
        matches.append(
            RuleMatch(
                evidence={
                    "ingress_index": index,
                    "cidr": cidr,
                    "ports": exposed,
                    "protocol": str(rule.get("protocol", "tcp")),
                },
                summary=f"Ingress rule #{index} opens {', '.join(labels)} to {cidr}.",
            )
        )
    return matches


def _sec_005_privileged_container(resource: Dict[str, Any]) -> List[RuleMatch]:
    reasons: Dict[str, Any] = {}
    if resource.get("privileged") is True:
        reasons["privileged"] = True
    security_context = resource.get("security_context")
    if isinstance(security_context, dict) and security_context.get("privileged") is True:
        reasons["security_context.privileged"] = True
    if not reasons:
        return []
    return [RuleMatch(evidence=reasons, summary="Container runs in privileged mode.")]


EVALUATORS: Dict[str, Callable[[Dict[str, Any]], List[RuleMatch]]] = {
    "SEC-001": _sec_001_public_storage,
    "SEC-002": _sec_002_missing_encryption,
    "SEC-003": _sec_003_wildcard_iam,
    "SEC-004": _sec_004_open_ingress,
    "SEC-005": _sec_005_privileged_container,
}

SUPPORTED_RESOURCE_TYPES = (
    "storage_bucket",
    "disk_volume",
    "database",
    "iam_policy",
    "security_group",
    "container",
)


class RuleCatalogError(RuntimeError):
    pass


def load_rules(catalog_path: Optional[Path] = None) -> List[Rule]:
    """Build the rule set from the YAML catalog and the evaluators above."""
    path = catalog_path or (settings.security_rules_path / "policies.yaml")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuleCatalogError(f"Cannot read rule catalog {path}: {exc}") from exc

    entries = (document or {}).get("policies")
    if not isinstance(entries, list):
        raise RuleCatalogError("Rule catalog must contain a 'policies' list")

    rules: List[Rule] = []
    for entry in entries:
        rule_id = str(entry.get("id", "")).strip()
        if rule_id not in EVALUATORS:
            raise RuleCatalogError(f"Rule catalog references unknown rule id '{rule_id}'")
        severity = str(entry.get("severity", "")).upper()
        if severity not in SEVERITIES:
            raise RuleCatalogError(f"{rule_id}: invalid severity '{severity}'")
        resource_types = tuple(entry.get("resource_types") or ())
        unknown = [t for t in resource_types if t not in SUPPORTED_RESOURCE_TYPES]
        if not resource_types or unknown:
            raise RuleCatalogError(f"{rule_id}: invalid resource_types {unknown or '(empty)'}")
        for required in ("name", "description", "detection_logic", "impact", "recommendation"):
            if not str(entry.get(required, "")).strip():
                raise RuleCatalogError(f"{rule_id}: missing '{required}'")
        rules.append(
            Rule(
                id=rule_id,
                name=str(entry["name"]).strip(),
                severity=severity,
                description=str(entry["description"]).strip(),
                detection_logic=str(entry["detection_logic"]).strip(),
                impact=str(entry["impact"]).strip(),
                recommendation=str(entry["recommendation"]).strip(),
                resource_types=resource_types,
                automated_action=entry.get("automated_action") or None,
                evaluate=EVALUATORS[rule_id],
            )
        )

    declared = {rule.id for rule in rules}
    if declared != set(EVALUATORS):
        missing = sorted(set(EVALUATORS) - declared)
        raise RuleCatalogError(f"Rule catalog is missing metadata for: {', '.join(missing)}")
    if len(declared) != len(rules):
        raise RuleCatalogError("Rule catalog contains duplicate rule ids")
    return sorted(rules, key=lambda rule: rule.id)


@lru_cache
def get_rules() -> tuple:
    return tuple(load_rules())


def get_rule(rule_id: str) -> Optional[Rule]:
    for rule in get_rules():
        if rule.id == rule_id:
            return rule
    return None
