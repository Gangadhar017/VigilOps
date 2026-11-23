"""Scanner engine: safe YAML loading, input validation and rule execution.

The engine is pure (no database access).  ``scan_service`` wraps it with
authorised-path handling, scan history and the finding lifecycle.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.security_scanner.rules import SUPPORTED_RESOURCE_TYPES, Rule, get_rules

SCHEMA_VERSION = "vigilops/v1"
MAX_RESOURCES = 500


class ScanInputError(ValueError):
    """The file is not a valid, supported configuration document."""


@dataclass(frozen=True)
class Violation:
    rule: Rule
    target_file: str
    resource_type: str
    resource_name: str
    summary: str
    evidence: Dict[str, Any]

    @property
    def resource_identifier(self) -> str:
        return f"{self.resource_type}/{self.resource_name}"

    @property
    def stable_key(self) -> str:
        """Deterministic identity of a finding across repeated scans."""
        return stable_finding_key(
            self.target_file, self.rule.id, self.resource_type, self.resource_name
        )


def stable_finding_key(target_file: str, rule_id: str, resource_type: str, resource_name: str) -> str:
    raw = "|".join([target_file, rule_id, resource_type, resource_name])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require(condition: bool, where: str, message: str) -> None:
    if not condition:
        raise ScanInputError(f"{where}: {message}")


def _is_string_list(value: Any) -> bool:
    return isinstance(value, str) or (isinstance(value, list) and all(isinstance(item, str) for item in value))


def _validate_field_types(resource: Dict[str, Any], where: str) -> None:
    """Reject wrongly typed security-relevant fields instead of silently ignoring them.

    The rules compare booleans and integers strictly.  Without this check a
    value such as ``public_access: "true"`` (a string) or ``port: "22"`` would
    simply not match and the misconfiguration would go unreported; a document
    like that is malformed and is refused, which is the safe failure mode.
    """
    rtype = resource["type"]

    if rtype == "storage_bucket":
        if "public_access" in resource:
            _require(isinstance(resource["public_access"], bool), where, "public_access must be true or false")
        if resource.get("acl") is not None:
            _require(isinstance(resource["acl"], str), where, "acl must be a string")

    if rtype in ("storage_bucket", "disk_volume", "database") and resource.get("encryption") is not None:
        encryption = resource["encryption"]
        _require(isinstance(encryption, dict), where, "encryption must be a mapping")
        if "enabled" in encryption:
            _require(isinstance(encryption["enabled"], bool), where, "encryption.enabled must be true or false")
        if encryption.get("algorithm") is not None:
            _require(isinstance(encryption["algorithm"], str), where, "encryption.algorithm must be a string")

    if rtype == "iam_policy":
        statements = resource.get("statements", [])
        _require(isinstance(statements, list), where, "statements must be a list")
        for position, statement in enumerate(statements):
            _require(isinstance(statement, dict), where, f"statements[{position}] must be a mapping")
            _require(isinstance(statement.get("effect", "Allow"), str), where, f"statements[{position}].effect must be a string")
            for key in ("actions", "resources"):
                if statement.get(key) is not None:
                    _require(_is_string_list(statement[key]), where, f"statements[{position}].{key} must be a string or a list of strings")

    if rtype == "security_group":
        ingress = resource.get("ingress", [])
        _require(isinstance(ingress, list), where, "ingress must be a list")
        for position, rule in enumerate(ingress):
            _require(isinstance(rule, dict), where, f"ingress[{position}] must be a mapping")
            _require(isinstance(rule.get("cidr", ""), str), where, f"ingress[{position}].cidr must be a string")
            if rule.get("port") is not None:
                port = rule["port"]
                _require(
                    isinstance(port, int) and not isinstance(port, bool) and 0 <= port <= 65535,
                    where,
                    f"ingress[{position}].port must be an integer between 0 and 65535",
                )
            if rule.get("port_range") is not None:
                text = str(rule["port_range"])
                low, _, high = text.partition("-")
                _require(
                    low.strip().isdigit() and (not high or high.strip().isdigit()),
                    where,
                    f"ingress[{position}].port_range must look like '1000-2000'",
                )

    if rtype == "container":
        if "privileged" in resource:
            _require(isinstance(resource["privileged"], bool), where, "privileged must be true or false")
        if resource.get("security_context") is not None:
            context = resource["security_context"]
            _require(isinstance(context, dict), where, "security_context must be a mapping")
            if "privileged" in context:
                _require(isinstance(context["privileged"], bool), where, "security_context.privileged must be true or false")


def parse_yaml_document(text: str, *, source: str = "<input>") -> Dict[str, Any]:
    """Parse and validate one configuration document.

    Uses ``yaml.safe_load`` (no arbitrary object construction) and rejects YAML
    anchors/aliases up front, which prevents alias-expansion ("billion laughs")
    memory attacks.
    """
    try:
        for token in yaml.scan(text):
            if isinstance(token, (yaml.AliasToken, yaml.AnchorToken)):
                raise ScanInputError(f"{source}: YAML anchors and aliases are not allowed")
        document = yaml.safe_load(text)
    except ScanInputError:
        raise
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or "invalid YAML syntax"
        mark = getattr(exc, "problem_mark", None)
        location = f" (line {mark.line + 1})" if mark is not None else ""
        raise ScanInputError(f"{source}: malformed YAML - {problem}{location}") from exc

    if not isinstance(document, dict):
        raise ScanInputError(f"{source}: top level must be a mapping")
    schema = document.get("schema_version")
    if schema != SCHEMA_VERSION:
        raise ScanInputError(
            f"{source}: unsupported schema_version {schema!r}; expected '{SCHEMA_VERSION}'"
        )
    resources = document.get("resources")
    if not isinstance(resources, list):
        raise ScanInputError(f"{source}: 'resources' must be a list")
    if len(resources) > MAX_RESOURCES:
        raise ScanInputError(f"{source}: too many resources (limit {MAX_RESOURCES})")

    seen = set()
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise ScanInputError(f"{source}: resources[{index}] must be a mapping")
        rtype, name = resource.get("type"), resource.get("name")
        if not isinstance(rtype, str) or rtype not in SUPPORTED_RESOURCE_TYPES:
            raise ScanInputError(
                f"{source}: resources[{index}].type must be one of "
                + ", ".join(SUPPORTED_RESOURCE_TYPES)
            )
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ScanInputError(f"{source}: resources[{index}].name must be a non-empty string")
        _validate_field_types(resource, f"{source}: resources[{index}] ({rtype}/{name})")
        key = (rtype, name)
        if key in seen:
            raise ScanInputError(f"{source}: duplicate resource {rtype}/{name}")
        seen.add(key)
    return document


def load_document(path: Path, *, max_bytes: int) -> Dict[str, Any]:
    """Read a configuration file with a size limit and parse it safely."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ScanInputError(f"{path.name}: file cannot be read") from exc
    if size > max_bytes:
        raise ScanInputError(f"{path.name}: file is larger than {max_bytes} bytes")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ScanInputError(f"{path.name}: file is not readable UTF-8 text") from exc
    return parse_yaml_document(text, source=path.name)


def evaluate_document(document: Dict[str, Any], target_file: str) -> List[Violation]:
    """Run every applicable rule against every resource (deterministic order)."""
    violations: List[Violation] = []
    for resource in document.get("resources", []):
        for rule in get_rules():
            if resource["type"] not in rule.resource_types:
                continue
            matches = rule.evaluate(resource)
            if not matches:
                continue
            # One finding per (rule, resource); individual matches become evidence.
            evidence = {
                "matches": [match.evidence for match in matches],
                "details": [match.summary for match in matches],
            }
            violations.append(
                Violation(
                    rule=rule,
                    target_file=target_file,
                    resource_type=resource["type"],
                    resource_name=resource["name"],
                    summary=" ".join(match.summary for match in matches),
                    evidence=evidence,
                )
            )
    violations.sort(key=lambda v: (v.target_file, v.rule.id, v.resource_type, v.resource_name))
    return violations


def scan_file(path: Path, target_file: str, *, max_bytes: int) -> List[Violation]:
    return evaluate_document(load_document(path, max_bytes=max_bytes), target_file)
