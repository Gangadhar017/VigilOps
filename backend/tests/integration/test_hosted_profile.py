"""The hosted-demonstration profile: settings used by the single-container image
(deploy/render) where the API port is public and the host is small."""
import logging

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.api import auth as auth_api
from app.core.config import Settings, settings
from app.main import app, apply_migrations
from app.services import demo_service
from tests.conftest import ADMIN_PASSWORD

BASE_ENV = {"SECRET_KEY": "k" * 40, "DATABASE_URL": "postgresql://u:strongpassword@db/x", "ALERT_WEBHOOK_TOKEN": "t" * 24}
PRODUCTION = dict(_env_file=None, ENVIRONMENT="production", **BASE_ENV)


# --- demo controls ---------------------------------------------------------------
def test_demo_controls_in_production_need_the_explicit_opt_in():
    assert Settings(**PRODUCTION, DEMO_CONTROLS_ENABLED=True).demo_controls_active is False
    assert Settings(**PRODUCTION, DEMO_CONTROLS_ENABLED=True, ALLOW_DEMO_CONTROLS_IN_PRODUCTION=True).demo_controls_active is True
    # The opt-in alone never switches them on.
    assert Settings(**PRODUCTION, DEMO_CONTROLS_ENABLED=False, ALLOW_DEMO_CONTROLS_IN_PRODUCTION=True).demo_controls_active is False


def test_hosted_demo_controls_stay_administrator_only(client, monkeypatch, admin_headers, operator_headers):
    monkeypatch.setattr(demo_service, "demo_app_state", lambda timeout=2.0: None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert client.get("/api/demo/status", headers=admin_headers).json()["enabled"] is False
    monkeypatch.setattr(settings, "ALLOW_DEMO_CONTROLS_IN_PRODUCTION", True)
    assert client.get("/api/demo/status", headers=admin_headers).json()["enabled"] is True
    assert client.post("/api/demo/faults", json={"mode": "outage"}, headers=operator_headers).status_code == 403


def test_disabled_faults_are_neither_offered_nor_passed_on(client, monkeypatch, admin_headers):
    sent = []

    def fake_post(url, **kwargs):
        sent.append(kwargs["json"]["mode"])
        return httpx.Response(200, json={"fault_mode": kwargs["json"]["mode"]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(demo_service.httpx, "post", fake_post)
    monkeypatch.setattr(demo_service, "demo_app_state", lambda timeout=2.0: None)
    monkeypatch.setattr(settings, "DEMO_DISABLED_FAULTS", "cpu, Memory ,none")

    status = client.get("/api/demo/status", headers=admin_headers).json()
    assert sorted(status["fault_modes"]) == ["errors", "latency", "none", "outage"]
    assert status["disabled_fault_modes"] == ["cpu", "memory"]

    refused = client.post("/api/demo/faults", json={"mode": "memory"}, headers=admin_headers)
    assert refused.status_code == 422 and "switched off" in refused.json()["detail"]
    assert sent == []  # the demo application was never contacted
    assert client.post("/api/demo/faults", json={"mode": "outage"}, headers=admin_headers).status_code == 200
    # Clearing a fault can never be disabled.
    assert client.post("/api/demo/faults", json={"mode": "none"}, headers=admin_headers).status_code == 200
    assert sent == ["outage", "none"]


# --- public API port ---------------------------------------------------------------
def test_internal_endpoints_answer_only_local_callers_when_the_api_port_is_public(client, monkeypatch):
    outside = TestClient(app)                              # peer address "testclient"
    local = TestClient(app, client=("127.0.0.1", 50000))   # the bundled Prometheus

    # Default: reachable.  In the Compose stack the reverse proxy withholds them.
    assert outside.get("/metrics").status_code == 200

    monkeypatch.setattr(settings, "INTERNAL_ENDPOINTS_LOCAL_ONLY", True)
    for path in ("/metrics", "/health/ready"):
        assert outside.get(path).status_code == 404
        assert local.get(path).status_code == 200
        # A request that came through a proxy is never local, whatever address it claims.
        assert local.get(path, headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 404
        assert local.get(path, headers={"Forwarded": "for=127.0.0.1"}).status_code == 404
    # What the platform and the frontend need stays public.
    assert outside.get("/health/live").status_code == 200
    assert outside.get("/api/health").status_code == 200
    # An uptime monitor that keeps a sleeping host awake may send HEAD instead of GET.
    for path in ("/health/live", "/api/health"):
        answer = outside.head(path)
        assert answer.status_code == 200 and answer.content == b""


def test_liveness_discloses_nothing_in_production(client, monkeypatch):
    assert "version" in client.get("/health/live").json()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert client.get("/health/live").json() == {"status": "alive"}


def test_login_failures_are_limited_per_account_whatever_the_client_address(client, admin, monkeypatch):
    """The client address comes from a forwarding header and can be forged when
    no trusted proxy is in front, so rotating it must not allow unlimited guesses."""
    monkeypatch.setattr(auth_api, "verify_password", lambda password, password_hash: password == ADMIN_PASSWORD)
    limit = settings.LOGIN_RATE_LIMIT_ATTEMPTS * 4

    def attempt(index, email="admin@test.local", password="wrong-Password-1"):
        caller = TestClient(app, client=(f"10.0.{index // 250}.{index % 250 + 1}", 40000))  # a new address every time
        return caller.post("/api/auth/login", json={"email": email, "password": password}).status_code

    assert [attempt(index) for index in range(limit)] == [401] * limit
    assert attempt(limit) == 429
    assert attempt(limit + 1, password=ADMIN_PASSWORD) == 429          # even the right password, from a fresh address
    assert attempt(limit + 2, email="someone-else@test.local") == 401  # other accounts are unaffected


# --- start-up ----------------------------------------------------------------------
def test_production_refuses_a_bootstrap_password_that_fails_the_policy():
    good = {"BOOTSTRAP_ADMIN_PASSWORD": "Good-Passw0rd-x", "BOOTSTRAP_OPERATOR_PASSWORD": "Other-Passw0rd-y"}
    Settings(**PRODUCTION, **good)
    with pytest.raises(Exception, match="BOOTSTRAP_ADMIN_PASSWORD does not meet the password policy"):
        Settings(**PRODUCTION, **{**good, "BOOTSTRAP_ADMIN_PASSWORD": "short"})
    with pytest.raises(Exception, match="BOOTSTRAP_OPERATOR_PASSWORD does not meet the password policy"):
        Settings(**PRODUCTION, **{**good, "BOOTSTRAP_OPERATOR_PASSWORD": "alllowercase123"})
    # Outside production a weak value does not stop the start-up (the account is skipped and logged).
    Settings(_env_file=None, ENVIRONMENT="development", BOOTSTRAP_ADMIN_PASSWORD="short", **BASE_ENV)
    # The worker holds no bootstrap passwords, so it has nothing to check.
    Settings(_env_file=None, ENVIRONMENT="production", PROCESS_ROLE="worker", BOOTSTRAP_ADMIN_PASSWORD="short", **BASE_ENV)


def test_migrations_can_run_inside_the_api_process(tmp_path):
    url = f"sqlite:///{(tmp_path / 'hosted.db').as_posix()}"
    handlers_before = list(logging.getLogger().handlers)
    apply_migrations(attempts=1, database_url=url)
    assert logging.getLogger().handlers == handlers_before  # this process's logging was left alone
    assert {"users", "incidents", "audit_events", "alembic_version"} <= set(inspect(create_engine(url)).get_table_names())
    apply_migrations(attempts=1, database_url=url)  # already at head: nothing to do


def test_migration_is_retried_while_the_database_is_not_ready(monkeypatch):
    from alembic import command

    calls = []

    def flaky_upgrade(config, revision):
        calls.append(revision)
        if len(calls) < 3:
            raise RuntimeError("database is starting up")

    monkeypatch.setattr(command, "upgrade", flaky_upgrade)
    apply_migrations(attempts=5, delay_seconds=0)
    assert calls == ["head"] * 3

    calls.clear()
    monkeypatch.setattr(command, "upgrade", lambda config, revision: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        apply_migrations(attempts=2, delay_seconds=0)
