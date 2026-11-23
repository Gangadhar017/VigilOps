"""Scanner engine and rules SEC-001..SEC-005 against the version-controlled fixtures."""
from pathlib import Path

import pytest

from app.security_scanner.engine import (
    ScanInputError,
    evaluate_document,
    parse_yaml_document,
    scan_file,
    stable_finding_key,
)
from app.security_scanner.rules import get_rules

SAMPLES = Path(__file__).resolve().parents[3] / "security-rules" / "samples"
MAX = 262_144

INSECURE = {
    "sec-001-public-storage.yaml": ("SEC-001", {"storage_bucket/public-assets-bucket"}),
    "sec-002-missing-encryption.yaml": (
        "SEC-002",
        {
            "storage_bucket/unencrypted-bucket",
            "disk_volume/data-volume-without-encryption-block",
            "database/orders-db-no-algorithm",
        },
    ),
    "sec-003-wildcard-iam.yaml": (
        "SEC-003",
        {
            "iam_policy/full-admin-policy",
            "iam_policy/service-wide-wildcard-policy",
            "iam_policy/wildcard-resource-policy",
        },
    ),
    "sec-004-open-ingress.yaml": (
        "SEC-004",
        {
            "security_group/ssh-open-to-world",
            "security_group/wide-port-range-open",
            "security_group/rdp-open-ipv6",
        },
    ),
    "sec-005-privileged-container.yaml": (
        "SEC-005",
        {"container/privileged-agent", "container/privileged-via-security-context"},
    ),
}


def _scan(path: Path):
    return scan_file(path, path.name, max_bytes=MAX)


def test_five_rules_are_defined_with_complete_metadata():
    rules = get_rules()
    assert [rule.id for rule in rules] == ["SEC-001", "SEC-002", "SEC-003", "SEC-004", "SEC-005"]
    for rule in rules:
        data = rule.as_dict()
        for field in ("name", "severity", "description", "detection_logic", "impact", "recommendation"):
            assert data[field], f"{rule.id} is missing {field}"
        assert data["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert {rule.id: rule.automated_action for rule in rules}["SEC-001"] == "ACTION-002"


@pytest.mark.parametrize("filename", sorted(INSECURE))
def test_insecure_fixture_triggers_exactly_its_rule(filename):
    expected_rule, expected_resources = INSECURE[filename]
    violations = _scan(SAMPLES / "insecure" / filename)
    assert {v.rule.id for v in violations} == {expected_rule}
    assert {v.resource_identifier for v in violations} == expected_resources
    for violation in violations:
        assert violation.evidence["matches"], "every finding must carry evidence"
        assert violation.summary


@pytest.mark.parametrize("path", sorted((SAMPLES / "secure").glob("*.yaml")), ids=lambda p: p.name)
def test_secure_fixtures_produce_no_findings(path):
    assert _scan(path) == []


def test_there_is_a_secure_counterpart_for_every_rule():
    names = sorted(p.name[:7] for p in (SAMPLES / "secure").glob("*.yaml"))
    assert names == ["sec-001", "sec-002", "sec-003", "sec-004", "sec-005"]


def test_demo_baseline_has_one_finding_per_rule_and_no_false_positives():
    violations = _scan(SAMPLES / "baseline" / "cloud-infrastructure.yaml")
    assert {(v.rule.id, v.resource_identifier) for v in violations} == {
        ("SEC-001", "storage_bucket/customer-records"),
        ("SEC-002", "storage_bucket/customer-records"),
        ("SEC-003", "iam_policy/app-deployer-role"),
        ("SEC-004", "security_group/web-sg"),
        ("SEC-005", "container/worker-agent"),
    }


def test_scanning_is_deterministic():
    path = SAMPLES / "baseline" / "cloud-infrastructure.yaml"
    first = [(v.stable_key, v.summary, v.evidence) for v in _scan(path)]
    second = [(v.stable_key, v.summary, v.evidence) for v in _scan(path)]
    assert first == second


def test_stable_key_depends_on_file_rule_and_resource():
    base = stable_finding_key("a.yaml", "SEC-001", "storage_bucket", "x")
    assert base == stable_finding_key("a.yaml", "SEC-001", "storage_bucket", "x")
    assert base != stable_finding_key("b.yaml", "SEC-001", "storage_bucket", "x")
    assert base != stable_finding_key("a.yaml", "SEC-002", "storage_bucket", "x")
    assert base != stable_finding_key("a.yaml", "SEC-001", "storage_bucket", "y")


def _doc(resources_yaml: str) -> str:
    return "schema_version: vigilops/v1\nresources:\n" + resources_yaml


def test_sec_004_ignores_web_ports_and_private_ranges():
    document = parse_yaml_document(
        _doc(
            "- type: security_group\n  name: sg\n  ingress:\n"
            "  - {protocol: tcp, port: 443, cidr: 0.0.0.0/0}\n"
            "  - {protocol: tcp, port: 22, cidr: 192.168.0.0/16}\n"
            "  - {protocol: tcp, port_range: 8000-8100, cidr: 0.0.0.0/0}\n"
        )
    )
    assert evaluate_document(document, "x.yaml") == []


def test_sec_004_all_protocols_open_to_world_is_flagged():
    document = parse_yaml_document(
        _doc("- type: security_group\n  name: sg\n  ingress:\n  - {protocol: all, cidr: 0.0.0.0/0}\n")
    )
    violations = evaluate_document(document, "x.yaml")
    assert [v.rule.id for v in violations] == ["SEC-004"]
    assert 22 in violations[0].evidence["matches"][0]["ports"]


def test_sec_003_ignores_deny_statements():
    document = parse_yaml_document(
        _doc("- type: iam_policy\n  name: p\n  statements:\n  - {effect: Deny, actions: ['*'], resources: ['*']}\n")
    )
    assert evaluate_document(document, "x.yaml") == []


def test_sec_001_public_acl_without_flag_is_flagged():
    document = parse_yaml_document(
        _doc(
            "- type: storage_bucket\n  name: b\n  acl: public-read-write\n"
            "  encryption: {enabled: true, algorithm: AES-256}\n"
        )
    )
    assert [v.rule.id for v in evaluate_document(document, "x.yaml")] == ["SEC-001"]


@pytest.mark.parametrize(
    "text, message",
    [
        ("schema_version: vigilops/v1\nresources: [", "malformed YAML"),
        ("- just\n- a list\n", "top level must be a mapping"),
        ("schema_version: other/v9\nresources: []\n", "unsupported schema_version"),
        ("schema_version: vigilops/v1\nresources: nope\n", "'resources' must be a list"),
        (_doc("- type: spaceship\n  name: x\n"), "type must be one of"),
        (_doc("- type: container\n"), "name must be a non-empty string"),
        (_doc("- type: container\n  name: a\n- type: container\n  name: a\n"), "duplicate resource"),
        ("schema_version: vigilops/v1\nbase: &a {x: 1}\nresources: []\ncopy: *a\n", "anchors and aliases"),
    ],
)
def test_invalid_documents_are_rejected(text, message):
    with pytest.raises(ScanInputError, match=message):
        parse_yaml_document(text, source="bad.yaml")


def test_yaml_object_constructors_are_not_executed():
    with pytest.raises(ScanInputError):
        parse_yaml_document("!!python/object/apply:os.system ['echo unsafe']\n", source="evil.yaml")


def test_oversized_file_is_rejected(tmp_path):
    big = tmp_path / "big.yaml"
    big.write_text("schema_version: vigilops/v1\nresources: []\n# " + "x" * 5000, encoding="utf-8")
    with pytest.raises(ScanInputError, match="larger than"):
        scan_file(big, big.name, max_bytes=1000)


@pytest.mark.parametrize(
    "resource_yaml, message",
    [
        ('- type: storage_bucket\n  name: b\n  public_access: "true"\n', "public_access must be true or false"),
        ("- type: storage_bucket\n  name: b\n  encryption: yes-please\n", "encryption must be a mapping"),
        ('- type: database\n  name: d\n  encryption: {enabled: "false"}\n', "encryption.enabled must be true or false"),
        ('- type: container\n  name: c\n  privileged: "true"\n', "privileged must be true or false"),
        ("- type: container\n  name: c\n  security_context: {privileged: 1}\n", "security_context.privileged must be true or false"),
        ('- type: security_group\n  name: s\n  ingress:\n  - {port: "22", cidr: 0.0.0.0/0}\n', "port must be an integer"),
        ("- type: security_group\n  name: s\n  ingress:\n  - {port_range: all, cidr: 0.0.0.0/0}\n", "port_range must look like"),
        ("- type: security_group\n  name: s\n  ingress: open\n", "ingress must be a list"),
        ("- type: iam_policy\n  name: p\n  statements:\n  - {effect: Allow, actions: {a: 1}}\n", "actions must be a string or a list of strings"),
        ("- type: iam_policy\n  name: p\n  statements: everything\n", "statements must be a list"),
    ],
)
def test_wrongly_typed_security_fields_are_rejected_not_ignored(resource_yaml, message):
    """A misconfiguration must never slip through because a value has the wrong type."""
    with pytest.raises(ScanInputError, match=message):
        parse_yaml_document(_doc(resource_yaml), source="typed.yaml")


def test_all_shipped_sample_files_satisfy_the_type_checks():
    for path in sorted(SAMPLES.rglob("*.yaml")):
        parse_yaml_document(path.read_text(encoding="utf-8"), source=path.name)
