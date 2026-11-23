"""Remediation workflow: request, approval, restricted worker, verification, audit."""
import httpx
import pytest

from app.core.config import settings
from app.core.database import utcnow
from app.models.models import (
    Incident,
    RemediationExecution,
    RemediationRequest,
    SecurityFinding,
    SecurityScan,
    WorkerHeartbeat,
)
from app.workers import actions, remediation_worker, verification
from tests.conftest import TARGET, audit_actions, fire_alert


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    """Verification polls with sleeps; tests do not need to wait."""
    monkeypatch.setattr(verification.time, "sleep", lambda _s: None)
    monkeypatch.setattr(actions.time, "sleep", lambda _s: None)


def _scan(client, headers):
    assert client.post("/api/security/scans", json={}, headers=headers).status_code == 201


def _finding(client, headers, rule="SEC-001"):
    return client.get("/api/security/findings", params={"rule_id": rule}, headers=headers).json()["items"][0]


def _request(client, headers, source_type, source_id, action="ACTION-002", justification="Required by security policy."):
    return client.post(
        "/api/remediation/requests",
        json={"source_type": source_type, "source_id": source_id, "action_code": action, "justification": justification},
        headers=headers,
    )


def _op(client, headers, request_id, operation, body=None):
    return client.post(f"/api/remediation/requests/{request_id}/{operation}", json=body if body is not None else {}, headers=headers)


def _approve_and_dispatch(client, admin_headers, request_id):
    assert _op(client, admin_headers, request_id, "approve", {"comment": "Reviewed."}).json()["status"] == "APPROVED"
    assert _op(client, admin_headers, request_id, "execute").json()["status"] == "QUEUED"


# ---------------------------------------------------------------------------
# ACTION-002  (real file edit + real rescan)
# ---------------------------------------------------------------------------
def test_storage_correction_end_to_end(client, db, workspace, operator_headers, admin_headers):
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)
    before_text = (workspace / TARGET).read_text(encoding="utf-8")

    created = _request(client, operator_headers, "finding", finding["id"])
    assert created.status_code == 201
    request = created.json()
    assert request["status"] == "PENDING_APPROVAL" and request["action_name"]
    assert request["target"] == f"{TARGET}#storage_bucket/customer-records"
    assert db.get(SecurityFinding, finding["id"]).status == "REMEDIATION_PENDING"
    request_id = request["id"]

    # Nothing runs before approval, and the worker ignores un-dispatched requests.
    assert remediation_worker.process_next(db) is False
    assert (workspace / TARGET).read_text(encoding="utf-8") == before_text

    approved = _op(client, admin_headers, request_id, "approve", {"comment": "Reviewed."}).json()
    assert approved["status"] == "APPROVED" and approved["approved_by_email"] == "admin@test.local"
    assert remediation_worker.process_next(db) is False  # APPROVED is still not QUEUED
    assert _op(client, admin_headers, request_id, "execute").json()["status"] == "QUEUED"

    assert remediation_worker.process_next(db) is True
    detail = client.get(f"/api/remediation/requests/{request_id}", headers=operator_headers).json()
    assert detail["status"] == "SUCCEEDED" and detail["attempt_count"] == 1

    execution = detail["executions"][0]
    assert execution["status"] == "SUCCEEDED" and execution["worker_identifier"] == settings.WORKER_ID
    assert execution["execution_details"]["changed"] is True
    assert execution["execution_details"]["before"] == {"public_access": True, "acl": "public-read"}
    assert execution["execution_details"]["after"] == {"public_access": False, "acl": "private"}
    assert "-  public_access: true" in execution["execution_details"]["diff"]
    assert "+  public_access: false" in execution["execution_details"]["diff"]
    assert execution["verification_result"]["passed"] is True
    assert [c["name"] for c in execution["verification_result"]["checks"]] == [
        "security_rescan", "rule_not_detected", "finding_resolved_by_scan",
    ]

    # The file really changed, only for the affected bucket, and stays valid YAML.
    after_text = (workspace / TARGET).read_text(encoding="utf-8")
    assert after_text != before_text and after_text.startswith("# VigilOps demonstration environment")
    changed = [(a, b) for a, b in zip(before_text.splitlines(), after_text.splitlines(), strict=True) if a != b]
    assert changed == [("  public_access: true", "  public_access: false"), ("  acl: public-read", "  acl: private")]

    # The finding was resolved by a verification scan - not deleted, not set by hand.
    resolved = db.get(SecurityFinding, finding["id"])
    db.refresh(resolved)
    assert resolved.status == "RESOLVED"
    verification_scan = db.query(SecurityScan).order_by(SecurityScan.id.desc()).first()
    assert verification_scan.trigger == "REMEDIATION_VERIFICATION"
    assert db.query(SecurityFinding).count() == 5
    assert db.query(SecurityFinding).filter(SecurityFinding.status == "OPEN").count() == 4

    timeline = [entry["action"] for entry in detail["timeline"]]
    for action in ("REMEDIATION_REQUESTED", "REMEDIATION_APPROVED", "REMEDIATION_QUEUED",
                   "REMEDIATION_EXECUTION_STARTED", "REMEDIATION_EXECUTED",
                   "REMEDIATION_VERIFICATION_PASSED", "REMEDIATION_SUCCEEDED", "SECURITY_SCAN_COMPLETED"):
        assert action in timeline, action
    assert timeline.index("REMEDIATION_APPROVED") < timeline.index("REMEDIATION_EXECUTED")


def test_failed_verification_marks_request_failed_and_reopens_finding(client, db, workspace, monkeypatch, operator_headers, admin_headers):
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)
    request_id = _request(client, operator_headers, "finding", finding["id"]).json()["id"]
    _approve_and_dispatch(client, admin_headers, request_id)

    # The handler claims success without changing anything: verification must catch it.
    monkeypatch.setitem(
        remediation_worker.HANDLERS,
        "ACTION-002",
        lambda params: {"action": "ACTION-002", "operation": "noop", "changed": False, "target_file": TARGET},
    )
    assert remediation_worker.process_next(db) is True

    detail = client.get(f"/api/remediation/requests/{request_id}", headers=admin_headers).json()
    assert detail["status"] == "FAILED" and "still detected" in detail["failure_reason"]
    assert detail["executions"][0]["verification_result"]["passed"] is False
    assert db.get(SecurityFinding, finding["id"]).status == "OPEN"
    actions_logged = audit_actions(db)
    assert "REMEDIATION_VERIFICATION_FAILED" in actions_logged and "REMEDIATION_FAILED" in actions_logged
    assert "REMEDIATION_SUCCEEDED" not in actions_logged


def test_retry_after_failure_and_attempt_limit(client, db, workspace, monkeypatch, operator_headers, admin_headers):
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)
    request_id = _request(client, operator_headers, "finding", finding["id"]).json()["id"]
    _approve_and_dispatch(client, admin_headers, request_id)

    def broken(_params):
        raise actions.ActionError("The configuration file could not be written: PermissionError")

    real_handler = remediation_worker.HANDLERS["ACTION-002"]
    monkeypatch.setitem(remediation_worker.HANDLERS, "ACTION-002", broken)
    remediation_worker.process_next(db)
    failed = client.get(f"/api/remediation/requests/{request_id}", headers=admin_headers).json()
    assert failed["status"] == "FAILED" and "could not be written" in failed["failure_reason"]
    assert failed["allowed_operations"] == ["retry"]
    assert _op(client, operator_headers, request_id, "retry").status_code == 403

    monkeypatch.setitem(remediation_worker.HANDLERS, "ACTION-002", real_handler)
    assert _op(client, admin_headers, request_id, "retry").json()["status"] == "QUEUED"
    assert db.get(SecurityFinding, finding["id"]).status == "REMEDIATION_PENDING"
    remediation_worker.process_next(db)
    done = client.get(f"/api/remediation/requests/{request_id}", headers=admin_headers).json()
    assert done["status"] == "SUCCEEDED" and done["attempt_count"] == 2 and len(done["executions"]) == 2
    assert _op(client, admin_headers, request_id, "retry").status_code == 409  # only FAILED can be retried

    exhausted = db.get(RemediationRequest, request_id)
    exhausted.status, exhausted.attempt_count = "FAILED", exhausted.max_attempts
    db.commit()
    assert "used all" in _op(client, admin_headers, request_id, "retry").json()["detail"]


def test_action_is_idempotent_when_already_compliant(client, db, workspace, operator_headers, admin_headers):
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)
    request_id = _request(client, operator_headers, "finding", finding["id"]).json()["id"]
    _approve_and_dispatch(client, admin_headers, request_id)
    target = workspace / TARGET
    target.write_text(
        target.read_text(encoding="utf-8").replace("public_access: true", "public_access: false").replace("acl: public-read", "acl: private"),
        encoding="utf-8",
    )
    stamp = target.stat().st_mtime_ns
    remediation_worker.process_next(db)
    detail = client.get(f"/api/remediation/requests/{request_id}", headers=admin_headers).json()
    assert detail["status"] == "SUCCEEDED"
    assert detail["executions"][0]["execution_details"]["changed"] is False
    assert target.stat().st_mtime_ns == stamp  # nothing was rewritten


def test_request_validation_and_allowlist(client, db, workspace, demo_resource, operator_headers):
    _scan(client, operator_headers)
    sec001 = _finding(client, operator_headers)
    sec003 = _finding(client, operator_headers, "SEC-003")

    assert _request(client, operator_headers, "finding", sec001["id"], action="ACTION-999").status_code == 422
    assert _request(client, operator_headers, "finding", sec001["id"], action="rm -rf /").status_code == 422
    assert _request(client, operator_headers, "finding", sec001["id"], action="ACTION-001").status_code == 422
    assert _request(client, operator_headers, "finding", sec001["id"], justification="too short").status_code == 422
    assert _request(client, operator_headers, "finding", 99999).status_code == 404
    unsupported = _request(client, operator_headers, "finding", sec003["id"])
    assert unsupported.status_code == 409 and "not implemented for SEC-003" in unsupported.json()["detail"]
    extra = client.post(
        "/api/remediation/requests",
        json={"source_type": "finding", "source_id": sec001["id"], "action_code": "ACTION-002",
              "justification": "valid justification", "command": "cat /etc/shadow", "target": "/etc/passwd"},
        headers=operator_headers,
    )
    assert extra.status_code == 201
    assert extra.json()["target"] == f"{TARGET}#storage_bucket/customer-records"  # caller cannot choose the target

    duplicate = _request(client, operator_headers, "finding", sec001["id"])
    assert duplicate.status_code == 409 and "already in progress" in duplicate.json()["detail"]
    assert db.query(RemediationRequest).count() == 1

    catalog = client.get("/api/remediation/actions", headers=operator_headers).json()
    assert [a["code"] for a in catalog["actions"]] == ["ACTION-001", "ACTION-002"]


def test_self_approval_is_blocked_unless_enabled(client, db, workspace, admin_headers, second_admin_headers):
    _scan(client, admin_headers)
    finding = _finding(client, admin_headers)
    request_id = _request(client, admin_headers, "finding", finding["id"]).json()["id"]

    own = _op(client, admin_headers, request_id, "approve")
    assert own.status_code == 403 and "submitted yourself" in own.json()["detail"]
    assert db.get(RemediationRequest, request_id).status == "PENDING_APPROVAL"
    assert "REMEDIATION_APPROVAL_DENIED" in audit_actions(db)
    detail = client.get(f"/api/remediation/requests/{request_id}", headers=admin_headers).json()
    assert "approve" not in detail["allowed_operations"]

    assert _op(client, second_admin_headers, request_id, "approve").json()["status"] == "APPROVED"

    # With the policy relaxed by an administrator, self-approval is permitted.
    client.put("/api/settings/remediation.allow_self_approval", json={"value": True}, headers=admin_headers)
    sec001 = db.get(SecurityFinding, finding["id"])
    _op(client, admin_headers, request_id, "cancel", {"comment": "start again"})
    db.refresh(sec001)
    assert sec001.status == "OPEN"
    again = _request(client, admin_headers, "finding", finding["id"]).json()["id"]
    assert _op(client, admin_headers, again, "approve").status_code == 200


def test_reject_and_cancel_release_the_finding(client, db, workspace, operator_headers, admin_headers, second_admin, second_admin_headers):
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)

    first = _request(client, operator_headers, "finding", finding["id"]).json()["id"]
    assert _op(client, admin_headers, first, "reject", {"comment": ""}).status_code == 422
    rejected = _op(client, admin_headers, first, "reject", {"comment": "Bucket is intentionally public."}).json()
    assert rejected["status"] == "REJECTED" and rejected["decision_comment"] == "Bucket is intentionally public."
    assert db.get(SecurityFinding, finding["id"]).status == "OPEN"
    assert _op(client, admin_headers, first, "approve").status_code == 409
    assert _op(client, admin_headers, first, "execute").status_code == 409

    second = _request(client, operator_headers, "finding", finding["id"]).json()["id"]
    db.expire_all()
    assert db.get(SecurityFinding, finding["id"]).status == "REMEDIATION_PENDING"
    cancelled = _op(client, operator_headers, second, "cancel", {"comment": "No longer needed."}).json()
    assert cancelled["status"] == "CANCELLED"
    db.expire_all()
    assert db.get(SecurityFinding, finding["id"]).status == "OPEN"

    third = _request(client, admin_headers, "finding", finding["id"]).json()["id"]
    assert _op(client, operator_headers, third, "cancel").status_code == 403  # not the operator's request
    assert remediation_worker.process_next(db) is False
    actions_logged = audit_actions(db)
    assert "REMEDIATION_REJECTED" in actions_logged and "REMEDIATION_CANCELLED" in actions_logged


def test_worker_refuses_a_queued_request_without_approval(client, db, workspace, operator, operator_headers):
    """Defence in depth: even if a row were forced to QUEUED, nothing executes."""
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)
    request_id = _request(client, operator_headers, "finding", finding["id"]).json()["id"]
    forged = db.get(RemediationRequest, request_id)
    forged.status, forged.queued_at = "QUEUED", utcnow()
    db.commit()
    before = (workspace / TARGET).read_text(encoding="utf-8")

    assert remediation_worker.process_next(db) is False
    db.expire_all()
    assert db.get(RemediationRequest, request_id).status == "FAILED"
    assert db.query(RemediationExecution).count() == 0
    assert (workspace / TARGET).read_text(encoding="utf-8") == before
    assert "REMEDIATION_EXECUTION_REFUSED" in audit_actions(db)


def test_action_cannot_write_outside_the_allowlist(workspace, tmp_path):
    with pytest.raises(actions.ActionError, match="allowlist"):
        actions.resolve_writable_target("other.yaml")
    with pytest.raises(actions.ActionError):
        actions.resolve_writable_target("../cloud-infrastructure.yaml")
    params = actions.ActionParams(request_id=1, action_code="ACTION-002", target_file=TARGET,
                                  resource_type="storage_bucket", resource_name="does-not-exist")
    with pytest.raises(actions.ActionError, match="no longer exists"):
        actions.fix_public_storage(params)


def test_interrupted_executions_are_failed_on_worker_start(client, db, workspace, operator_headers, admin_headers):
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)
    request_id = _request(client, operator_headers, "finding", finding["id"]).json()["id"]
    _approve_and_dispatch(client, admin_headers, request_id)
    assert remediation_worker.claim_next(db) is not None  # RUNNING, then the worker "crashes"
    assert remediation_worker.recover_interrupted(db) == 1
    db.expire_all()
    request = db.get(RemediationRequest, request_id)
    assert request.status == "FAILED" and "stopped before" in request.failure_reason
    assert db.get(SecurityFinding, finding["id"]).status == "OPEN"


# ---------------------------------------------------------------------------
# ACTION-001  (demo application HTTP calls are simulated; monitoring is the fake client)
# ---------------------------------------------------------------------------
class DemoApp:
    """Simulates the demo application's HTTP surface for the worker."""

    def __init__(self, recover_works=True):
        self.healthy = False
        self.recover_works = recover_works
        self.recover_calls = []

    def get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        if not self.recover_works and not self.healthy and url.endswith("/health/ready") and self.unreachable:
            raise httpx.ConnectError("connection refused", request=request)
        status = 200 if self.healthy else 503
        return httpx.Response(status, json={"status": "ready" if self.healthy else "unavailable"}, request=request)

    unreachable = False

    def post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        self.recover_calls.append(kwargs.get("headers", {}).get("Authorization"))
        if self.unreachable:
            raise httpx.ConnectError("connection refused", request=request)
        if kwargs.get("headers", {}).get("Authorization") != f"Bearer {settings.DEMO_APP_RECOVERY_TOKEN}":
            return httpx.Response(401, request=request)
        if self.recover_works:
            self.healthy = True
        return httpx.Response(200, json={"status": "recovered", "fault_mode": "none"}, request=request)


@pytest.fixture
def demo_app(monkeypatch):
    app = DemoApp()
    monkeypatch.setattr(actions.httpx, "get", app.get)
    monkeypatch.setattr(actions.httpx, "post", app.post)
    return app


def _open_incident(client, db, prometheus):
    prometheus.demo_health = "down"
    prometheus.firing.add("ApplicationUnavailable")
    fire_alert(client)
    return db.query(Incident).one()


def test_application_recovery_end_to_end(client, db, demo_resource, prometheus, demo_app, operator_headers, admin_headers):
    incident = _open_incident(client, db, prometheus)
    created = _request(client, operator_headers, "incident", incident.id, action="ACTION-001",
                       justification="Application is down; recover the service.")
    assert created.status_code == 201 and created.json()["status"] == "PENDING_APPROVAL"
    request_id = created.json()["id"]
    db.refresh(incident)
    assert incident.status == "OPEN", "requesting remediation must not resolve the incident"
    _approve_and_dispatch(client, admin_headers, request_id)
    db.refresh(incident)
    assert incident.status == "OPEN", "approval must not resolve the incident either"

    # Recovery makes the app healthy; monitoring then observes it.
    original_post = demo_app.post

    def post_and_recover(url, **kwargs):
        response = original_post(url, **kwargs)
        prometheus.demo_health = "up"
        prometheus.firing.discard("ApplicationUnavailable")
        return response

    actions.httpx.post = post_and_recover
    assert remediation_worker.process_next(db) is True

    detail = client.get(f"/api/remediation/requests/{request_id}", headers=operator_headers).json()
    assert detail["status"] == "SUCCEEDED"
    execution = detail["executions"][0]
    assert execution["execution_details"]["before"]["ready"] is False
    assert [c["name"] for c in execution["verification_result"]["checks"]] == [
        "application_health", "prometheus_target_up", "alert_cleared",
    ]
    assert all(c["passed"] for c in execution["verification_result"]["checks"])
    assert demo_app.recover_calls == [f"Bearer {settings.DEMO_APP_RECOVERY_TOKEN}"]

    db.refresh(incident)
    assert incident.status == "RESOLVED" and f"request #{request_id}" in incident.resolution_summary
    events = [e.event_type for e in incident.events]
    for expected in ("REMEDIATION_REQUESTED", "REMEDIATION_APPROVED", "REMEDIATION_QUEUED",
                     "REMEDIATION_STARTED", "REMEDIATION_EXECUTED", "RESOLVED"):
        assert expected in events
    linked = client.get(f"/api/incidents/{incident.id}", headers=operator_headers).json()["remediation_requests"]
    assert linked[0]["id"] == request_id and linked[0]["status"] == "SUCCEEDED"


def test_recovery_is_not_successful_until_monitoring_confirms(client, db, demo_resource, prometheus, demo_app, operator_headers, admin_headers):
    incident = _open_incident(client, db, prometheus)
    request_id = _request(client, operator_headers, "incident", incident.id, action="ACTION-001",
                          justification="Application is down; recover the service.").json()["id"]
    _approve_and_dispatch(client, admin_headers, request_id)
    # The app answers its health check, but Prometheus still sees the target down.
    remediation_worker.process_next(db)
    detail = client.get(f"/api/remediation/requests/{request_id}", headers=admin_headers).json()
    assert detail["status"] == "FAILED" and "prometheus_target_up" in detail["failure_reason"]
    db.refresh(incident)
    assert incident.status == "OPEN", "a failed remediation must leave the incident open"
    assert "REMEDIATION_FAILED" in [e.event_type for e in incident.events]


def test_recovery_fails_when_application_is_unreachable(client, db, demo_resource, prometheus, demo_app, operator_headers, admin_headers):
    incident = _open_incident(client, db, prometheus)
    demo_app.unreachable = True
    request_id = _request(client, operator_headers, "incident", incident.id, action="ACTION-001",
                          justification="Application is down; recover the service.").json()["id"]
    _approve_and_dispatch(client, admin_headers, request_id)
    remediation_worker.process_next(db)
    detail = client.get(f"/api/remediation/requests/{request_id}", headers=admin_headers).json()
    assert detail["status"] == "FAILED"
    assert "could not be reached after 3 attempts" in detail["failure_reason"]
    assert len(demo_app.recover_calls) == 3  # bounded automatic retries
    assert detail["executions"][0]["execution_details"]["retryable"] is True
    assert db.get(Incident, incident.id).status == "OPEN"


def test_incident_resolved_by_monitoring_cancels_unstarted_requests(client, db, demo_resource, prometheus, operator_headers):
    incident = _open_incident(client, db, prometheus)
    request_id = _request(client, operator_headers, "incident", incident.id, action="ACTION-001",
                          justification="Application is down; recover the service.").json()["id"]
    fire_alert(client, status="resolved")
    db.expire_all()
    assert db.get(RemediationRequest, request_id).status == "CANCELLED"
    assert db.get(Incident, incident.id).status == "RESOLVED"
    again = _request(client, operator_headers, "incident", incident.id, action="ACTION-001",
                     justification="Application is down; recover the service.")
    assert again.status_code == 409 and "already RESOLVED" in again.json()["detail"]


def test_list_filters_and_worker_heartbeat(client, db, workspace, operator, operator_headers, admin_headers):
    _scan(client, operator_headers)
    finding = _finding(client, operator_headers)
    _request(client, operator_headers, "finding", finding["id"])
    listing = client.get("/api/remediation/requests", params={"status": "PENDING_APPROVAL", "mine": True}, headers=operator_headers).json()
    assert listing["total"] == 1 and listing["items"][0]["requested_by_email"] == "operator@test.local"
    assert client.get("/api/remediation/requests", params={"mine": True}, headers=admin_headers).json()["total"] == 0
    assert client.get("/api/remediation/requests", params={"q": "customer-records"}, headers=admin_headers).json()["total"] == 1

    assert client.get("/api/remediation/actions", headers=admin_headers).json()["worker"]["online"] is False
    remediation_worker.heartbeat(db, utcnow(), 0)
    assert db.query(WorkerHeartbeat).count() == 1
    assert client.get("/api/remediation/actions", headers=admin_headers).json()["worker"]["online"] is True
