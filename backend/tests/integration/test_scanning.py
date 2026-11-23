"""Scan API, authorised targets, scan history and the finding lifecycle."""
from pathlib import Path

from app.models.models import SecurityFinding, SecurityScan
from tests.conftest import BASELINE, TARGET, audit_actions

SECURE_STORAGE = Path(__file__).resolve().parents[3] / "security-rules" / "samples" / "secure" / "sec-001-private-storage.yaml"


def _scan(client, headers, target=None):
    return client.post("/api/security/scans", json={"target": target} if target else {}, headers=headers)


def _findings(client, headers, **params):
    return client.get("/api/security/findings", params=params, headers=headers).json()


def test_scan_persists_five_findings_and_history(client, db, workspace, operator_headers):
    response = _scan(client, operator_headers)
    assert response.status_code == 201
    scan = response.json()
    assert scan["status"] == "COMPLETED" and scan["trigger"] == "MANUAL"
    assert scan["requested_by_label"] == "operator@test.local"
    summary = scan["result_summary"]
    assert summary["files_scanned"] == [TARGET]
    assert summary["violations_detected"] == 5 and summary["new_findings"] == 5
    assert summary["by_rule"] == {f"SEC-00{n}": 1 for n in range(1, 6)}

    listing = _findings(client, operator_headers)
    assert listing["total"] == 5
    assert {f["status"] for f in listing["items"]} == {"OPEN"}
    assert listing["items"][0]["severity"] == "CRITICAL"  # default sort: most severe first
    first = listing["items"][0]
    for field in ("rule_id", "rule_name", "severity", "resource_identifier", "evidence", "recommendation", "stable_finding_key"):
        assert first[field]

    history = client.get("/api/security/scans", headers=operator_headers).json()
    assert history["total"] == 1 and history["items"][0]["id"] == scan["id"]
    actions = audit_actions(db)
    assert actions.count("FINDING_DETECTED") == 5 and "SECURITY_SCAN_COMPLETED" in actions


def test_repeated_scans_do_not_duplicate_findings(client, db, workspace, operator_headers):
    _scan(client, operator_headers)
    second = _scan(client, operator_headers).json()["result_summary"]
    assert second["new_findings"] == 0 and second["unchanged_findings"] == 5
    assert db.query(SecurityFinding).count() == 5
    assert {f.detection_count for f in db.query(SecurityFinding)} == {2}
    assert db.query(SecurityScan).count() == 2


def test_finding_detail_explains_rule_and_guidance(client, workspace, operator_headers):
    _scan(client, operator_headers)
    sec001 = _findings(client, operator_headers, rule_id="SEC-001")["items"][0]
    detail = client.get(f"/api/security/findings/{sec001['id']}", headers=operator_headers).json()
    assert detail["rule"]["detection_logic"] and detail["rule"]["impact"]
    assert detail["guidance"]["automation"] == {
        "supported": True,
        "action_code": "ACTION-002",
        "action": detail["guidance"]["automation"]["action"],
        "reason": None,
    }
    assert detail["evidence"]["matches"] and detail["history"][0]["action"] == "FINDING_DETECTED"

    sec003 = _findings(client, operator_headers, rule_id="SEC-003")["items"][0]
    guidance = client.get(f"/api/security/findings/{sec003['id']}", headers=operator_headers).json()["guidance"]
    assert guidance["automation"]["supported"] is False and "not implemented" in guidance["automation"]["reason"]
    assert guidance["recommended_steps"], "manual steps must still be provided"


def test_fixed_configuration_resolves_and_regression_reopens(client, db, workspace, operator_headers):
    _scan(client, operator_headers)
    target = workspace / TARGET
    insecure = target.read_text(encoding="utf-8")
    target.write_text(
        insecure.replace("public_access: true", "public_access: false").replace("acl: public-read", "acl: private"),
        encoding="utf-8",
    )
    summary = _scan(client, operator_headers).json()["result_summary"]
    assert summary["resolved_findings"] == 1 and summary["violations_detected"] == 4
    sec001 = db.query(SecurityFinding).filter(SecurityFinding.rule_id == "SEC-001").one()
    assert sec001.status == "RESOLVED" and sec001.resolved_at is not None
    assert db.query(SecurityFinding).count() == 5  # resolved findings are kept, not deleted

    target.write_text(insecure, encoding="utf-8")
    summary = _scan(client, operator_headers).json()["result_summary"]
    assert summary["reopened_findings"] == 1 and summary["new_findings"] == 0
    db.refresh(sec001)
    assert sec001.status == "OPEN" and sec001.resolved_at is None
    actions = audit_actions(db)
    assert "FINDING_RESOLVED" in actions and "FINDING_REOPENED" in actions


def test_secure_file_in_workspace_produces_no_findings(client, db, workspace, operator_headers):
    (workspace / TARGET).unlink()
    (workspace / "hardened.yaml").write_text(SECURE_STORAGE.read_text(encoding="utf-8"), encoding="utf-8")
    summary = _scan(client, operator_headers).json()["result_summary"]
    assert summary["files_scanned"] == ["hardened.yaml"] and summary["violations_detected"] == 0
    assert db.query(SecurityFinding).count() == 0


def test_only_authorised_targets_can_be_scanned(client, db, workspace, operator_headers, tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text(BASELINE.read_text(encoding="utf-8"), encoding="utf-8")
    for target in (
        "../outside.yaml",
        "..\\outside.yaml",
        str(outside),
        "/etc/passwd",
        "sub/dir.yaml",
        "cloud-infrastructure.yaml/../../x.yaml",
        ".hidden.yaml",
        "notes.txt",
        "%2e%2e%2fsecret.yaml",
    ):
        response = _scan(client, operator_headers, target)
        assert response.status_code == 400, f"{target!r} -> {response.status_code}"
    assert _scan(client, operator_headers, "missing.yaml").status_code == 404
    assert client.get("/api/security/targets/..%2F..%2Fetc%2Fpasswd", headers=operator_headers).status_code in (400, 404)
    assert db.query(SecurityScan).count() == 0 and db.query(SecurityFinding).count() == 0

    targets = client.get("/api/security/targets", headers=operator_headers).json()["targets"]
    assert [(t["name"], t["remediation_allowed"]) for t in targets] == [(TARGET, True)]
    content = client.get(f"/api/security/targets/{TARGET}", headers=operator_headers).json()
    assert "customer-records" in content["content"]


def test_symlink_escape_is_blocked(client, workspace, operator_headers, tmp_path):
    outside = tmp_path / "secret.yaml"
    outside.write_text(BASELINE.read_text(encoding="utf-8"), encoding="utf-8")
    link = workspace / "link.yaml"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        import pytest

        pytest.skip("symlinks are not available on this platform")
    assert _scan(client, operator_headers, "link.yaml").status_code == 400
    assert "link.yaml" not in [t["name"] for t in client.get("/api/security/targets", headers=operator_headers).json()["targets"]]


def test_malformed_file_fails_scan_and_keeps_existing_findings(client, db, workspace, operator_headers):
    _scan(client, operator_headers)
    (workspace / TARGET).write_text("schema_version: vigilops/v1\nresources: [\n", encoding="utf-8")
    failed = _scan(client, operator_headers, TARGET).json()
    assert failed["status"] == "FAILED" and "malformed YAML" in failed["error"]
    # Nothing is resolved or hidden just because the file could not be read.
    assert {f.status for f in db.query(SecurityFinding)} == {"OPEN"}
    assert "SECURITY_SCAN_FAILED" in audit_actions(db)


def test_empty_workspace_scan_completes_with_note(client, operator_headers):
    summary = _scan(client, operator_headers).json()["result_summary"]
    assert summary["files_scanned"] == [] and "No configuration files" in summary["note"]


def test_accepted_risk_requires_admin_and_justification(client, db, workspace, operator_headers, admin_headers):
    _scan(client, operator_headers)
    finding = _findings(client, operator_headers, rule_id="SEC-005")["items"][0]
    url = f"/api/security/findings/{finding['id']}/accept-risk"
    assert client.post(url, json={"reason": "Vendor agent requires privileged mode."}, headers=operator_headers).status_code == 403
    assert client.post(url, json={"reason": "short"}, headers=admin_headers).status_code == 422
    accepted = client.post(url, json={"reason": "Vendor agent requires privileged mode."}, headers=admin_headers)
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACCEPTED_RISK"
    assert client.post(url, json={"reason": "Vendor agent requires privileged mode."}, headers=admin_headers).status_code == 409

    # Still detected on the next scan: it stays ACCEPTED_RISK rather than silently re-opening.
    _scan(client, operator_headers)
    assert db.get(SecurityFinding, finding["id"]).status == "ACCEPTED_RISK"
    assert _findings(client, operator_headers, status="ACCEPTED_RISK")["total"] == 1

    revoked = client.post(f"/api/security/findings/{finding['id']}/revoke-risk-acceptance", headers=admin_headers)
    assert revoked.json()["status"] == "OPEN"
    assert "FINDING_RISK_ACCEPTED" in audit_actions(db)


def test_findings_search_filter_and_rules_catalog(client, workspace, operator_headers):
    _scan(client, operator_headers)
    assert _findings(client, operator_headers, q="web-sg")["items"][0]["rule_id"] == "SEC-004"
    assert _findings(client, operator_headers, severity="HIGH")["total"] == 3
    assert _findings(client, operator_headers, page_size=2)["total"] == 5
    rules = client.get("/api/security/rules", headers=operator_headers).json()
    assert len(rules["rules"]) == 5 and "does not assess a live cloud account" in rules["scope"]
