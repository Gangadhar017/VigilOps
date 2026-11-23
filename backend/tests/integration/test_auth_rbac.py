"""Authentication, session handling and backend-enforced RBAC."""
from app.models.models import AuditEvent, RemediationRequest, User
from tests.conftest import ADMIN_PASSWORD, OPERATOR_PASSWORD, audit_actions, auth_headers


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_valid_administrator_login_grants_dashboard_access(client, admin):
    response = _login(client, "admin@test.local", ADMIN_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["user"]["role"] == "admin"
    assert "remediation:approve" in body["user"]["permissions"]
    assert "password_hash" not in str(body)
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get("/api/dashboard/summary", headers=headers).status_code == 200


def test_invalid_credentials_fail_with_generic_message(client, admin, db):
    wrong = _login(client, "admin@test.local", "not-the-password")
    unknown = _login(client, "nobody@test.local", "whatever-Pass1")
    assert wrong.status_code == 401 and unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]  # no user enumeration
    assert audit_actions(db).count("AUTH_LOGIN_FAILED") == 2


def test_login_is_case_insensitive_on_email(client, admin):
    assert _login(client, "  ADMIN@Test.Local ", ADMIN_PASSWORD).status_code == 200


def test_login_rate_limiting_blocks_after_repeated_failures(client, admin, db):
    for _ in range(5):
        assert _login(client, "admin@test.local", "bad-password").status_code == 401
    blocked = _login(client, "admin@test.local", ADMIN_PASSWORD)  # even the right password is refused
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert "AUTH_LOGIN_RATE_LIMITED" in audit_actions(db)
    # A different account from the same address is not locked out.
    assert _login(client, "someone-else@test.local", "x").status_code == 401


def test_requests_without_or_with_invalid_token_are_rejected(client):
    for path in ("/api/auth/me", "/api/incidents", "/api/security/findings", "/api/remediation/requests",
                 "/api/audit/events", "/api/monitoring/overview", "/api/settings", "/api/users",
                 "/api/assistant/status", "/api/dashboard/summary"):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers={"Authorization": "Bearer not.a.token"}).status_code == 401, path
    assert client.post("/api/assistant/chat", json={"message": "hello"}).status_code == 401


def test_logout_revokes_the_token_server_side(client, admin):
    token = _login(client, "admin@test.local", ADMIN_PASSWORD).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_password_change_invalidates_existing_sessions(client, operator, operator_headers):
    weak = client.post(
        "/api/auth/change-password",
        json={"current_password": OPERATOR_PASSWORD, "new_password": "weak"},
        headers=operator_headers,
    )
    assert weak.status_code == 422
    wrong = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong", "new_password": "Brand-New-Pass-9"},
        headers=operator_headers,
    )
    assert wrong.status_code == 400
    ok = client.post(
        "/api/auth/change-password",
        json={"current_password": OPERATOR_PASSWORD, "new_password": "Brand-New-Pass-9"},
        headers=operator_headers,
    )
    assert ok.status_code == 204
    assert client.get("/api/auth/me", headers=operator_headers).status_code == 401  # old token dead
    assert _login(client, "operator@test.local", "Brand-New-Pass-9").status_code == 200


def test_deactivated_user_cannot_sign_in_or_use_old_token(client, db, admin_headers, operator, operator_headers):
    response = client.patch(f"/api/users/{operator.id}", json={"is_active": False}, headers=admin_headers)
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=operator_headers).status_code == 401
    assert _login(client, "operator@test.local", OPERATOR_PASSWORD).status_code == 401


def test_there_is_no_public_registration(client):
    assert client.post("/api/auth/register", json={"email": "x@y.zz", "password": "Abcdefgh12", "role": "admin"}).status_code in (404, 405)
    assert client.post("/api/users", json={"email": "x@y.zz", "password": "Abcdefgh12", "role": "admin"}).status_code == 401


def test_operator_cannot_use_administrator_endpoints(client, db, operator_headers, admin):
    denied = [
        ("get", "/api/users", None),
        ("post", "/api/users", {"email": "n@test.local", "password": "Abcdefgh12", "role": "admin"}),
        ("patch", f"/api/users/{admin.id}", {"role": "operator"}),
        ("put", "/api/settings/remediation.allow_self_approval", {"value": True}),
        ("post", "/api/demo/faults", {"mode": "outage"}),
        ("post", "/api/demo/reset-config", None),
        ("post", "/api/security/findings/1/accept-risk", {"reason": "because I say so"}),
        ("post", "/api/remediation/requests/1/approve", {}),
        ("post", "/api/remediation/requests/1/reject", {"comment": "no thanks"}),
        ("post", "/api/remediation/requests/1/execute", None),
        ("post", "/api/remediation/requests/1/retry", None),
    ]
    for method, path, body in denied:
        response = client.request(method, path, json=body, headers=operator_headers)
        assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
    assert db.query(User).count() == 2
    assert db.query(AuditEvent).filter(AuditEvent.action == "ACCESS_DENIED").count() == len(denied)
    db.refresh(admin)
    assert admin.role == "admin"


def test_operator_approval_attempt_returns_403_and_changes_nothing(client, db, workspace, operator, operator_headers):
    client.post("/api/security/scans", json={}, headers=operator_headers)
    finding = next(f for f in client.get("/api/security/findings", headers=operator_headers).json()["items"] if f["rule_id"] == "SEC-001")
    created = client.post(
        "/api/remediation/requests",
        json={"source_type": "finding", "source_id": finding["id"], "action_code": "ACTION-002",
              "justification": "Bucket must not be public."},
        headers=operator_headers,
    )
    assert created.status_code == 201 and created.json()["status"] == "PENDING_APPROVAL"
    request_id = created.json()["id"]

    response = client.post(f"/api/remediation/requests/{request_id}/approve", json={}, headers=operator_headers)
    assert response.status_code == 403
    db.expire_all()
    request = db.get(RemediationRequest, request_id)
    assert request.status == "PENDING_APPROVAL" and request.approved_by is None
    assert "approve" not in client.get(f"/api/remediation/requests/{request_id}", headers=operator_headers).json()["allowed_operations"]


def test_administrator_manages_users(client, db, admin, admin_headers):
    weak = client.post("/api/users", json={"email": "new@test.local", "password": "weak", "role": "operator"}, headers=admin_headers)
    assert weak.status_code == 422
    created = client.post(
        "/api/users",
        json={"email": "New.User@Test.Local", "full_name": "New User", "password": "Strong-Pass-123", "role": "operator"},
        headers=admin_headers,
    )
    assert created.status_code == 201 and created.json()["email"] == "new.user@test.local"
    duplicate = client.post("/api/users", json={"email": "new.user@test.local", "password": "Strong-Pass-123"}, headers=admin_headers)
    assert duplicate.status_code == 409
    user_id = created.json()["id"]

    assert _login(client, "new.user@test.local", "Strong-Pass-123").status_code == 200
    assert client.post(f"/api/users/{user_id}/reset-password", json={"new_password": "Another-Pass-456"}, headers=admin_headers).status_code == 204
    assert _login(client, "new.user@test.local", "Strong-Pass-123").status_code == 401
    assert _login(client, "new.user@test.local", "Another-Pass-456").status_code == 200

    listed = client.get("/api/users?q=new.user", headers=admin_headers).json()
    assert listed["total"] == 1
    for action in ("USER_CREATED", "USER_PASSWORD_RESET"):
        assert action in audit_actions(db)


def test_last_administrator_cannot_be_removed(client, admin, admin_headers):
    demote = client.patch(f"/api/users/{admin.id}", json={"role": "operator"}, headers=admin_headers)
    deactivate = client.patch(f"/api/users/{admin.id}", json={"is_active": False}, headers=admin_headers)
    assert demote.status_code == 409 and deactivate.status_code == 409


def test_role_change_invalidates_old_token(client, db, admin_headers, operator, operator_headers):
    assert client.patch(f"/api/users/{operator.id}", json={"role": "admin"}, headers=admin_headers).status_code == 200
    assert client.get("/api/auth/me", headers=operator_headers).status_code == 401
    db.refresh(operator)
    assert client.get("/api/users", headers=auth_headers(operator)).status_code == 200


def test_runtime_settings_are_admin_only_validated_and_audited(client, db, admin_headers, operator_headers):
    view = client.get("/api/settings", headers=operator_headers)
    assert view.status_code == 200 and view.json()["can_manage"] is False
    text = str(view.json())
    for secret in ("unit-test-signing-key", "unit-test-webhook-token", "unit-test-recovery-token"):
        assert secret not in text  # configuration view never returns secret values

    assert client.put("/api/settings/incidents.reopen_window_minutes", json={"value": 99999}, headers=admin_headers).status_code == 422
    assert client.put("/api/settings/incidents.reopen_window_minutes", json={"value": "ten"}, headers=admin_headers).status_code == 422
    assert client.put("/api/settings/not.a.setting", json={"value": 1}, headers=admin_headers).status_code == 404
    ok = client.put("/api/settings/incidents.reopen_window_minutes", json={"value": 45}, headers=admin_headers)
    assert ok.status_code == 200 and ok.json()["value"] == 45
    assert "SETTINGS_UPDATED" in audit_actions(db)


def test_health_endpoints_and_metrics(client):
    assert client.get("/health/live").json()["status"] == "alive"
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["checks"]["database"]["ok"] is True
    assert client.get("/api/health").json()["status"] == "healthy"
    client.get("/api/version")
    metrics = client.get("/metrics").text
    assert 'http_requests_total{method="GET",path="/api/version",status="200"}' in metrics
    assert "http_request_duration_seconds_bucket" in metrics
    assert "X-Request-ID" in client.get("/api/version").headers
