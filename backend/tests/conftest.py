"""Shared test fixtures.

The suite runs against SQLite by default (fast, no services needed).  Set
``TEST_DATABASE_URL`` to a PostgreSQL URL to run the same tests against the
production database engine (CI does both).

Environment variables are set *before* the application is imported because
configuration is read at import time.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_TMP = Path(tempfile.mkdtemp(prefix="vigilops-tests-"))
_REPO_ROOT = Path(__file__).resolve().parents[2]

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "SECRET_KEY": "unit-test-signing-key-0123456789abcdef-not-for-real-use",
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}",
        "ALERT_WEBHOOK_TOKEN": "unit-test-webhook-token-123456",
        "DEMO_CONTROLS_ENABLED": "true",
        "DEMO_APP_CONTROL_TOKEN": "unit-test-control-token",
        "DEMO_APP_RECOVERY_TOKEN": "unit-test-recovery-token",
        "DEMO_APP_URL": "http://demo-app.invalid:8001",
        "PROMETHEUS_URL": "http://prometheus.invalid:9090",
        "ALERTMANAGER_URL": "http://alertmanager.invalid:9093",
        "SCAN_WORKSPACE_DIR": str(_TMP / "workspace"),
        "SECURITY_RULES_DIR": str(_REPO_ROOT / "security-rules"),
        "KNOWLEDGE_BASE_DIR": str(_REPO_ROOT / "knowledge_base"),
        "AI_PROVIDER": "none",
        "GEMINI_API_KEY": "",
        "BOOTSTRAP_ADMIN_EMAIL": "",
        "BOOTSTRAP_ADMIN_PASSWORD": "",
        "BOOTSTRAP_OPERATOR_EMAIL": "",
        "BOOTSTRAP_OPERATOR_PASSWORD": "",
        # INFO on purpose: log calls are part of the code under test (a bad log call
        # must fail a test, not surface for the first time in a running stack).
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "text",
        "AI_RATE_LIMIT_PER_MINUTE": "8",
        "VERIFY_TIMEOUT_SECONDS": "6",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.auth import reset_login_limits  # noqa: E402
from app.assistant import providers as ai_providers  # noqa: E402
from app.assistant import service as assistant_service  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine, utcnow  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import MonitoredResource, User  # noqa: E402
from app.services import monitoring_service  # noqa: E402

ADMIN_PASSWORD = "Admin-Test-Pass-1"
OPERATOR_PASSWORD = "Operator-Test-Pass-1"
BASELINE = _REPO_ROOT / "security-rules" / "samples" / "baseline" / "cloud-infrastructure.yaml"
TARGET = "cloud-infrastructure.yaml"

# bcrypt is deliberately slow; hash the fixture passwords once per session.
_HASHES = {
    "admin": hash_password(ADMIN_PASSWORD),
    "operator": hash_password(OPERATOR_PASSWORD),
}


class FakePrometheus:
    """Stand-in for PrometheusClient with controllable observations."""

    def __init__(self) -> None:
        self.available = True
        self.demo_health = "up"
        self.firing: set = set()
        self.last_error: Optional[str] = None

    def prometheus_ready(self) -> Dict[str, Any]:
        return {"available": self.available, "error": None if self.available else "unreachable (ConnectError)"}

    def alertmanager_ready(self) -> Dict[str, Any]:
        return {"available": self.available, "error": None if self.available else "unreachable (ConnectError)"}

    def targets(self) -> Dict[str, Any]:
        if not self.available:
            return {"available": False, "reason": "unreachable (ConnectError)", "targets": []}
        now = utcnow().isoformat()
        return {
            "available": True,
            "reason": None,
            "targets": [
                {
                    "job": settings.DEMO_APP_JOB,
                    "instance": "test-app:8001",
                    "health": self.demo_health,
                    "last_scrape": now,
                    "last_scrape_age_seconds": 0.1,
                    "last_error": self.last_error,
                    "scrape_url": "http://test-app:8001/metrics",
                    "stale": False,
                },
                {
                    "job": settings.BACKEND_JOB,
                    "instance": "backend:8000",
                    "health": "up",
                    "last_scrape": now,
                    "last_scrape_age_seconds": 0.1,
                    "last_error": None,
                    "scrape_url": "http://backend:8000/metrics",
                    "stale": False,
                },
            ],
        }

    def firing_alerts(self) -> Dict[str, Any]:
        if not self.available:
            return {"available": False, "reason": "unreachable (ConnectError)", "alerts": []}
        return {
            "available": True,
            "reason": None,
            "alerts": [
                {"name": name, "state": "firing", "severity": "CRITICAL", "resource": "demo-app",
                 "instance": "test-app:8001", "summary": name, "active_at": None}
                for name in sorted(self.firing)
            ],
        }

    def alert_is_firing(self, alert_name: str, job: Optional[str] = None) -> Tuple[Optional[bool], Optional[str]]:
        if not self.available:
            return None, "unreachable (ConnectError)"
        return alert_name in self.firing, None

    def instant(self, promql: str) -> Dict[str, Any]:
        if not self.available:
            return {"available": False, "value": None, "reason": "unreachable (ConnectError)", "sampled_at": None}
        if promql.startswith("up{"):
            up = 1.0 if (settings.DEMO_APP_JOB not in promql or self.demo_health == "up") else 0.0
            return {"available": True, "value": up, "reason": None, "sampled_at": utcnow().isoformat()}
        return {"available": False, "value": None, "reason": "no data", "sampled_at": None}

    def range(self, promql: str, window_seconds: int, step_seconds: int) -> Dict[str, Any]:
        if not self.available:
            return {"available": False, "reason": "unreachable (ConnectError)", "points": []}
        return {"available": True, "reason": None, "points": [{"t": utcnow().isoformat(), "v": 1.5}]}


@pytest.fixture(autouse=True)
def _clean_state():
    """Fresh schema, limiter state, workspace and fake monitoring for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_login_limits()
    assistant_service.reset_limits()
    ai_providers.set_provider(None)

    workspace = Path(settings.SCAN_WORKSPACE_DIR)
    shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)

    fake = FakePrometheus()
    monitoring_service.set_client(fake)  # type: ignore[arg-type]
    yield
    monitoring_service.set_client(None)
    ai_providers.reset_provider()


@pytest.fixture
def prometheus() -> FakePrometheus:
    return monitoring_service.get_client()  # type: ignore[return-value]


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_user(db, email: str, role: str, kind: str, name: str) -> User:
    user = User(email=email, full_name=name, password_hash=_HASHES[kind], role=role)
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def admin(db) -> User:
    return _make_user(db, "admin@test.local", "admin", "admin", "Test Admin")


@pytest.fixture
def second_admin(db) -> User:
    return _make_user(db, "admin2@test.local", "admin", "admin", "Second Admin")


@pytest.fixture
def operator(db) -> User:
    return _make_user(db, "operator@test.local", "operator", "operator", "Test Operator")


def auth_headers(user: User) -> Dict[str, str]:
    token, _expires, _jti = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin) -> Dict[str, str]:
    return auth_headers(admin)


@pytest.fixture
def second_admin_headers(second_admin) -> Dict[str, str]:
    return auth_headers(second_admin)


@pytest.fixture
def operator_headers(operator) -> Dict[str, str]:
    return auth_headers(operator)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def workspace() -> Path:
    """Scan workspace containing the insecure demo baseline."""
    path = Path(settings.SCAN_WORKSPACE_DIR)
    shutil.copyfile(BASELINE, path / TARGET)
    return path


@pytest.fixture
def demo_resource(db, client) -> MonitoredResource:
    """The demo-app monitored resource (registered by application bootstrap)."""
    return (
        db.query(MonitoredResource)
        .filter(MonitoredResource.monitoring_identifier == settings.DEMO_APP_JOB)
        .one()
    )


WEBHOOK_HEADERS = {"Authorization": f"Bearer {os.environ['ALERT_WEBHOOK_TOKEN']}"}


def alert_payload(
    status: str = "firing",
    alertname: str = "ApplicationUnavailable",
    fingerprint: str = "a1b2c3d4e5f60718",
    severity: str = "critical",
    **extra_labels: str,
) -> Dict[str, Any]:
    labels = {
        "alertname": alertname,
        "severity": severity,
        "job": "demo-app",
        "resource": "demo-app",
        "instance": "test-app:8001",
        **extra_labels,
    }
    return {
        "version": "4",
        "status": status,
        "receiver": "vigilops-webhook",
        "alerts": [
            {
                "status": status,
                "labels": labels,
                "annotations": {
                    "summary": "Demo application is unavailable",
                    "description": "Prometheus cannot scrape the demo application.",
                },
                "startsAt": "2026-11-23T10:00:00.000000000Z",
                "endsAt": "0001-01-01T00:00:00Z" if status == "firing" else "2026-11-23T10:05:00Z",
                "fingerprint": fingerprint,
            }
        ],
    }


def fire_alert(client, **kwargs) -> Dict[str, Any]:
    response = client.post("/api/alerts/webhook", json=alert_payload(**kwargs), headers=WEBHOOK_HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def audit_actions(db) -> List[str]:
    from app.models.models import AuditEvent

    db.expire_all()
    return [event.action for event in db.query(AuditEvent).order_by(AuditEvent.id).all()]
