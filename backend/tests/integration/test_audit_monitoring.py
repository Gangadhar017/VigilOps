"""Audit trail, monitoring APIs, demo controls and database migrations."""
import httpx
from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.core.database import Base
from app.models.models import AuditEvent, DemoTask
from app.services import demo_service, monitoring_service
from app.services.monitoring_service import PrometheusClient
from app.workers import remediation_worker
from tests.conftest import ADMIN_PASSWORD, TARGET, audit_actions, fire_alert


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def _events(client, headers, **params):
    return client.get("/api/audit/events", params=params, headers=headers).json()


def test_audit_records_have_required_fields(client, db, admin, admin_headers):
    client.post("/api/auth/login", json={"email": "admin@test.local", "password": ADMIN_PASSWORD})
    event = _events(client, admin_headers, action="AUTH_LOGIN_SUCCESS")["items"][0]
    assert event["event_id"] and event["actor_label"] == "admin@test.local"
    assert event["entity_type"] == "user" and event["outcome"] == "SUCCESS"
    assert event["created_at"].endswith("Z") or "+00:00" in event["created_at"]  # UTC
    assert event["correlation_id"] and "metadata" in event
    assert ADMIN_PASSWORD not in str(_events(client, admin_headers, page_size=100))


def test_operator_sees_operational_events_and_only_own_sign_ins(client, db, demo_resource, admin, operator, admin_headers, operator_headers):
    client.post("/api/auth/login", json={"email": "admin@test.local", "password": ADMIN_PASSWORD})
    client.post("/api/auth/login", json={"email": "operator@test.local", "password": "wrong"})
    client.post("/api/users", json={"email": "x@test.local", "password": "Strong-Pass-123"}, headers=admin_headers)
    fire_alert(client)

    admin_view = {e["action"] for e in _events(client, admin_headers, page_size=100)["items"]}
    assert {"AUTH_LOGIN_SUCCESS", "AUTH_LOGIN_FAILED", "USER_CREATED", "INCIDENT_CREATED"} <= admin_view

    operator_items = _events(client, operator_headers, page_size=100)["items"]
    operator_view = {e["action"] for e in operator_items}
    assert "INCIDENT_CREATED" in operator_view
    assert "USER_CREATED" not in operator_view and "AUTH_LOGIN_SUCCESS" not in operator_view
    assert all(e["actor_label"] != "admin@test.local" for e in operator_items)
    assert client.get("/api/audit/meta", headers=operator_headers).json()["visibility"] == "operational"

    hidden = db.query(AuditEvent).filter(AuditEvent.action == "USER_CREATED").one()
    assert client.get(f"/api/audit/events/{hidden.id}", headers=operator_headers).status_code == 404
    assert client.get(f"/api/audit/events/{hidden.id}", headers=admin_headers).status_code == 200


def test_audit_search_filters_and_pagination(client, db, demo_resource, admin_headers):
    for index in range(6):
        fire_alert(client, fingerprint=f"{index:016x}", alertname=f"Alert{index}")
    assert _events(client, admin_headers, category="INCIDENT")["total"] == 6
    assert _events(client, admin_headers, q="alert3")["total"] == 1
    assert _events(client, admin_headers, outcome="DENIED")["total"] == 0
    assert _events(client, admin_headers, actor="alertmanager")["total"] == 6
    page = _events(client, admin_headers, category="INCIDENT", page=2, page_size=4, sort="created_at", order="asc")
    assert len(page["items"]) == 2 and page["total"] == 6
    assert _events(client, admin_headers, date_from="2999-01-01T00:00:00Z")["total"] == 0


def test_audit_history_cannot_be_modified_through_the_api(client, db, demo_resource, admin_headers):
    fire_alert(client)
    event_id = db.query(AuditEvent).first().id
    for method in ("put", "patch", "delete", "post"):
        response = client.request(method, f"/api/audit/events/{event_id}", json={"action": "TAMPERED"}, headers=admin_headers)
        assert response.status_code == 405, method
    assert client.delete("/api/audit/events", headers=admin_headers).status_code == 405
    assert "TAMPERED" not in audit_actions(db)


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
def test_overview_reports_real_target_state(client, prometheus, operator_headers):
    overview = client.get("/api/monitoring/overview", headers=operator_headers).json()
    assert overview["source"] == "prometheus" and overview["prometheus"]["available"] is True
    demo = next(r for r in overview["resources"] if r["job"] == settings.DEMO_APP_JOB)
    assert demo["status"] == "UP"
    assert demo["metrics"]["availability"]["value"] == 1.0
    # Metrics without samples are reported as unavailable, never given a default number.
    assert demo["metrics"]["cpu_usage"] == {**demo["metrics"]["cpu_usage"], "available": False, "value": None, "reason": "no data"}

    prometheus.demo_health = "down"
    monitoring_service._cache.clear()
    demo = next(r for r in client.get("/api/monitoring/overview", headers=operator_headers).json()["resources"] if r["job"] == settings.DEMO_APP_JOB)
    assert demo["status"] == "DOWN"


def test_unavailable_prometheus_yields_unavailable_state_not_fake_values(client, prometheus, operator_headers):
    prometheus.available = False
    overview = client.get("/api/monitoring/overview", headers=operator_headers).json()
    assert overview["prometheus"]["available"] is False and overview["targets"]["available"] is False
    for resource in overview["resources"]:
        assert resource["status"] == "UNKNOWN" and resource["metrics"] == {}
    series = client.get("/api/monitoring/timeseries", params={"job": settings.DEMO_APP_JOB, "metric": "request_rate"}, headers=operator_headers).json()
    assert series["available"] is False and series["points"] == []
    summary = client.get("/api/dashboard/summary", headers=operator_headers)
    assert summary.status_code == 200 and summary.json()["platform"]["database"]["healthy"] is True


def test_timeseries_only_accepts_catalog_metrics_and_registered_jobs(client, operator_headers):
    ok = client.get("/api/monitoring/timeseries", params={"job": settings.DEMO_APP_JOB, "metric": "request_rate", "range": "5m"}, headers=operator_headers)
    assert ok.status_code == 200 and ok.json()["points"] and ok.json()["unit"] == "req/s"
    for params in (
        {"job": settings.DEMO_APP_JOB, "metric": "up{job=~'.+'}"},
        {"job": 'demo-app"} or vector(1) #', "metric": "request_rate"},
        {"job": "unregistered-job", "metric": "request_rate"},
        {"job": settings.DEMO_APP_JOB, "metric": "request_rate", "range": "10y"},
    ):
        assert client.get("/api/monitoring/timeseries", params=params, headers=operator_headers).status_code == 400, params
    catalog = client.get("/api/monitoring/metrics", headers=operator_headers).json()
    assert {"availability", "request_rate", "error_rate_5xx", "error_rate_4xx", "latency_p95", "cpu_usage", "memory_rss", "uptime"} == {m["key"] for m in catalog["metrics"]}


def _prom_client(handler):
    return PrometheusClient("http://prom.test", "http://am.test", timeout=1, transport=httpx.MockTransport(handler))


def test_prometheus_client_parses_responses_and_handles_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/-/ready":
            return httpx.Response(200, text="ok")
        if request.url.path == "/api/v1/query":
            query = request.url.params["query"]
            if "nan_metric" in query:
                return httpx.Response(200, json={"status": "success", "data": {"result": [{"metric": {}, "value": [1700000000, "NaN"]}]}})
            if "empty" in query:
                return httpx.Response(200, json={"status": "success", "data": {"result": []}})
            if "ALERTS" in query:
                return httpx.Response(200, json={"status": "success", "data": {"result": [{"metric": {"alertname": "X"}, "value": [1700000000, "1"]}]}})
            return httpx.Response(200, json={"status": "success", "data": {"result": [{"metric": {}, "value": [1700000000, "0.25"]}]}})
        if request.url.path == "/api/v1/query_range":
            return httpx.Response(200, json={"status": "success", "data": {"result": [{"values": [[1700000000, "1"], [1700000005, "NaN"]]}]}})
        if request.url.path == "/api/v1/targets":
            return httpx.Response(200, json={"status": "success", "data": {"activeTargets": [
                {"labels": {"job": "demo-app", "instance": "test-app:8001"}, "health": "down",
                 "lastScrape": "2024-01-15T10:00:00.123456789Z", "lastError": "server returned HTTP status 503", "scrapeUrl": "http://test-app:8001/metrics"}]}})
        return httpx.Response(500)

    client = _prom_client(handler)
    assert client.prometheus_ready() == {"available": True, "error": None}
    assert client.instant("some_metric")["value"] == 0.25
    assert client.instant("nan_metric") == {"available": False, "value": None, "reason": "no data", "sampled_at": None}
    assert client.instant("empty")["available"] is False
    assert client.range("x", 60, 5)["points"][1]["v"] is None  # NaN is never turned into a number
    target = client.targets()["targets"][0]
    assert target["health"] == "down" and target["stale"] is True and "503" in target["last_error"]
    assert client.alert_is_firing("X") == (True, None)
    assert client.alert_is_firing('X"} or up{job="') == (None, "invalid alert name")
    assert client.firing_alerts()["available"] is False  # /api/v1/alerts answered 500


def test_prometheus_client_reports_timeouts_and_connection_errors():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request):
        raise httpx.ConnectError("refused", request=request)

    assert _prom_client(timeout).instant("up")["reason"] == "timeout"
    assert _prom_client(timeout).prometheus_ready() == {"available": False, "error": "timeout"}
    assert "unreachable" in _prom_client(refused).targets()["reason"]
    assert _prom_client(refused).alert_is_firing("X")[0] is None


# ---------------------------------------------------------------------------
# Demo controls
# ---------------------------------------------------------------------------
def test_demo_controls_are_unavailable_when_disabled(client, monkeypatch, admin_headers):
    monkeypatch.setattr(settings, "DEMO_CONTROLS_ENABLED", False)
    assert client.get("/api/demo/status", headers=admin_headers).json()["enabled"] is False
    assert client.post("/api/demo/faults", json={"mode": "outage"}, headers=admin_headers).status_code == 404
    assert client.post("/api/demo/reset-config", headers=admin_headers).status_code == 404


def test_demo_controls_are_forced_off_in_production(client, monkeypatch, admin_headers):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert settings.DEMO_CONTROLS_ENABLED is True and settings.demo_controls_active is False
    assert client.post("/api/demo/faults", json={"mode": "outage"}, headers=admin_headers).status_code == 404


def test_fault_injection_calls_demo_app_with_control_token(client, db, monkeypatch, admin_headers):
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(200, json={"fault_mode": kwargs["json"]["mode"]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(demo_service.httpx, "post", fake_post)
    assert client.post("/api/demo/faults", json={"mode": "meteor"}, headers=admin_headers).status_code == 422
    response = client.post("/api/demo/faults", json={"mode": "outage"}, headers=admin_headers)
    assert response.status_code == 200 and response.json()["simulated"] is True
    assert seen["url"].endswith("/internal/fault") and seen["json"] == {"mode": "outage"}
    assert seen["headers"]["Authorization"] == f"Bearer {settings.DEMO_APP_CONTROL_TOKEN}"
    assert "DEMO_FAULT_INJECTED" in audit_actions(db)


def test_incident_during_demo_fault_is_labelled_simulated(client, db, demo_resource, monkeypatch, operator_headers):
    monkeypatch.setattr(demo_service, "demo_app_state", lambda timeout=2.0: {"fault_mode": "outage"})
    fire_alert(client)
    incident = client.get("/api/incidents", headers=operator_headers).json()["items"][0]
    assert incident["is_simulated"] is True and "outage" in incident["simulation_note"]

    monkeypatch.setattr(demo_service, "demo_app_state", lambda timeout=2.0: None)  # app unreachable: a real outage
    fire_alert(client, fingerprint="ffffffffffffffff", alertname="HighCpuUsage")
    newest = client.get("/api/incidents", params={"q": "HighCpuUsage"}, headers=operator_headers).json()["items"][0]
    assert newest["is_simulated"] is False


def test_worker_restores_sample_configuration(db, workspace, admin):
    (workspace / TARGET).write_text("schema_version: vigilops/v1\nresources: []\n", encoding="utf-8")
    db.add(DemoTask(task_type=demo_service.RESET_TASK, requested_by=admin.id))
    db.add(DemoTask(task_type="FORMAT_DISK", requested_by=admin.id))
    db.commit()
    assert remediation_worker.process_demo_task(db) is True
    assert "customer-records" in (workspace / TARGET).read_text(encoding="utf-8")
    assert remediation_worker.process_demo_task(db) is True  # unsupported task types are failed, not run
    statuses = [task.status for task in db.query(DemoTask).order_by(DemoTask.id)]
    assert statuses == ["SUCCEEDED", "FAILED"]
    assert remediation_worker.process_demo_task(db) is False


def test_workspace_is_initialised_only_in_demo_mode(db, monkeypatch):
    from pathlib import Path

    workspace = Path(settings.SCAN_WORKSPACE_DIR)
    monkeypatch.setattr(settings, "DEMO_CONTROLS_ENABLED", False)
    remediation_worker.initialise_workspace(db)
    assert list(workspace.glob("*.yaml")) == []
    monkeypatch.setattr(settings, "DEMO_CONTROLS_ENABLED", True)
    remediation_worker.initialise_workspace(db)
    assert [p.name for p in workspace.glob("*.yaml")] == [TARGET]


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------
def test_alembic_migration_matches_the_models(tmp_path):
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[2]
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        assert set(Base.metadata.tables) <= tables and "alembic_version" in tables
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == [], f"models and migration differ: {differences}"

    command.downgrade(config, "base")
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
    engine.dispose()


def test_range_query_marks_missing_samples_as_gaps():
    def handler(request: httpx.Request) -> httpx.Response:
        # Samples every 5 s, with a 30 s hole in the middle (target was down).
        values = [[1700000000, "2"], [1700000005, "2"], [1700000035, "1"], [1700000040, "2"]]
        return httpx.Response(200, json={"status": "success", "data": {"result": [{"values": values}]}})

    points = _prom_client(handler).range("x", 60, 5)["points"]
    assert [p["v"] for p in points] == [2.0, 2.0, None, 1.0, 2.0]
