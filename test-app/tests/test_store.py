"""Tests of OrbitCrate, the demonstration application.

Run from the repository root:  python -m pytest test-app/tests -q
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.update(
    {
        "LOAD_GENERATOR_ENABLED": "false",
        "DEMO_CONTROLS_ENABLED": "true",
        "DEMO_APP_CONTROL_TOKEN": "test-control-token",
        "DEMO_APP_RECOVERY_TOKEN": "test-recovery-token",
        "DEMO_DISABLED_FAULTS": "memory",
    }
)

_spec = importlib.util.spec_from_file_location("orbitcrate_app", Path(__file__).resolve().parents[1] / "app.py")
store_app = importlib.util.module_from_spec(_spec)
sys.modules["orbitcrate_app"] = store_app
_spec.loader.exec_module(store_app)

VISITOR = {"X-Session-Id": "visitor-0001"}
OTHER = {"X-Session-Id": "visitor-0002"}
CONTROL = {"Authorization": "Bearer test-control-token"}
RECOVERY = {"Authorization": "Bearer test-recovery-token"}
SELECTION = {"plan": "crate-m", "region": "sin-1", "quantity": 2, "addons": ["backups", "ipv4"], "term": "yearly"}


@pytest.fixture
def client():
    store_app.state.set_fault("none")
    store_app.store.clear()
    with TestClient(store_app.app) as test_client:
        yield test_client
    store_app.state.set_fault("none")


def metric(client, name):
    for line in client.get("/metrics").text.splitlines():
        if line.startswith(name + " ") or line.startswith(name + "{"):
            yield line


# --- pages ------------------------------------------------------------------------
def test_the_storefront_and_its_files_are_served(client):
    page = client.get("/")
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert "OrbitCrate" in page.text and "Demonstration store" in page.text
    # Relative addresses only: the page must work behind a path prefix.
    assert 'src="static/app.js"' in page.text and 'href="static/styles.css"' in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert "<script>" not in page.text  # no inline script: it would be blocked

    assert client.get("/static/app.js").headers["content-type"].startswith(("text/javascript", "application/javascript"))
    assert client.get("/static/styles.css").headers["content-type"].startswith("text/css")
    font = client.get("/static/fonts/manrope-latin-wght-normal.woff2")
    assert font.status_code == 200 and font.headers["content-type"] == "font/woff2"
    assert client.get("/static/../app.py").status_code == 404


def test_the_page_script_never_writes_server_text_as_html():
    script = (Path(store_app.STATIC_DIR) / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script and "document.write" not in script


# --- catalogue and prices ----------------------------------------------------------
def test_catalogue_lists_plans_regions_addons_and_terms(client):
    catalog = client.get("/api/catalog").json()
    assert [plan["id"] for plan in catalog["plans"]] == ["crate-s", "crate-m", "crate-l", "crate-xl"]
    assert {region["id"] for region in catalog["regions"]} == {"bom-1", "sin-1", "fra-1"}
    assert catalog["currency"] == "INR" and len(catalog["addons"]) == 4 and len(catalog["terms"]) == 2


def test_estimate_is_calculated_line_by_line(client):
    price = client.post("/api/estimate", json=SELECTION).json()
    # 2 x 1199 x 1.08 = 2589.84; backups 20% = 517.97; IPv4 2 x 150 = 300.00
    assert [line["amount"] for line in price["lines"]] == [2589.84, 517.97, 300.0, -511.17]
    assert price["net"] == 2896.64            # 3407.81 less 15%
    assert price["tax"] == 521.4              # GST 18% (521.395 rounded)
    assert price["monthly_total"] == 3418.04
    assert price["selection"]["plan_name"] == "Crate M" and price["selection"]["region_name"] == "Singapore"

    simple = client.post("/api/estimate", json={"plan": "crate-s", "region": "bom-1"}).json()
    assert simple["lines"] == [{"label": "1 x Crate S in Mumbai", "amount": 349.0}]
    assert simple["monthly_total"] == 411.82


@pytest.mark.parametrize(
    "change",
    [{"plan": "crate-xxl"}, {"region": "mars-1"}, {"addons": ["teleport"]}, {"term": "weekly"}, {"quantity": 0}, {"quantity": 11}],
)
def test_estimate_refuses_unknown_or_out_of_range_values(client, change):
    assert client.post("/api/estimate", json={**SELECTION, **change}).status_code == 422


# --- orders -------------------------------------------------------------------------
def test_an_order_belongs_to_its_visitor_and_moves_through_its_statuses(client, monkeypatch):
    assert client.get("/api/orders").status_code == 400            # no visitor session
    assert client.get("/api/orders", headers={"X-Session-Id": "bad id!"}).status_code == 400
    assert client.get("/api/orders", headers=VISITOR).json() == {"orders": [], "count": 0, "limit": 20}

    placed = client.post("/api/orders", json={**SELECTION, "project": "campus-portal"}, headers=VISITOR)
    assert placed.status_code == 201
    order = placed.json()
    assert order["id"].startswith("OC-") and order["status"] == "received" and order["monthly_total"] == 3418.04
    assert order["project"] == "campus-portal" and order["ready_in_seconds"] == 20

    # Another visitor neither sees nor reaches it.
    assert client.get("/api/orders", headers=OTHER).json()["count"] == 0
    assert client.get(f"/api/orders/{order['id']}", headers=OTHER).status_code == 404
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=OTHER).status_code == 404

    # The status follows from the order's age.
    real_time = store_app.time.time
    monkeypatch.setattr(store_app.time, "time", lambda: real_time() + 10)
    assert client.get(f"/api/orders/{order['id']}", headers=VISITOR).json()["status"] == "provisioning"
    monkeypatch.setattr(store_app.time, "time", lambda: real_time() + 30)
    active = client.get(f"/api/orders/{order['id']}", headers=VISITOR).json()
    assert active["status"] == "active" and active["ready_in_seconds"] == 0

    cancelled = client.post(f"/api/orders/{order['id']}/cancel", headers=VISITOR).json()
    assert cancelled["status"] == "cancelled" and cancelled["cancelled_at"]
    assert client.get("/api/orders", headers=VISITOR).json()["orders"][0]["status"] == "cancelled"


@pytest.mark.parametrize("project", ["", "x", "<script>alert(1)</script>", "a" * 41, " leading-space", "name;drop"])
def test_project_names_are_restricted(client, project):
    response = client.post("/api/orders", json={**SELECTION, "project": project}, headers=VISITOR)
    assert response.status_code == 422


def test_order_storage_is_bounded(client, monkeypatch):
    monkeypatch.setattr(store_app, "MAX_ORDER_WRITES_PER_MINUTE", 1000)
    monkeypatch.setattr(store_app, "MAX_ORDERS_PER_SESSION", 3)
    codes = [
        client.post("/api/orders", json={**SELECTION, "project": f"project-{n}"}, headers=VISITOR).status_code
        for n in range(4)
    ]
    assert codes == [201, 201, 201, 409]

    # Only the most recently seen visitors are kept.
    monkeypatch.setattr(store_app, "MAX_SESSIONS", 2)
    for n in range(4):
        client.post("/api/orders", json={**SELECTION, "project": "site"}, headers={"X-Session-Id": f"visitor-10{n}0"})
    assert len(store_app.store.sessions) == 2
    # Reading with an unknown session does not create one.
    client.get("/api/orders", headers={"X-Session-Id": "never-ordered-1"})
    assert len(store_app.store.sessions) == 2


def test_orders_per_minute_are_limited(client, monkeypatch):
    monkeypatch.setattr(store_app, "MAX_ORDER_WRITES_PER_MINUTE", 2)
    codes = [
        client.post("/api/orders", json={**SELECTION, "project": "site"}, headers=VISITOR).status_code for _ in range(3)
    ]
    assert codes == [201, 201, 429]


# --- telemetry -----------------------------------------------------------------------
def test_requests_are_counted_under_bounded_labels(client):
    client.get("/api/catalog")
    client.get("/api/orders/OC-NOSUCH", headers=VISITOR)
    client.get("/static/app.js")
    client.get("/no/such/page/123456")
    lines = "\n".join(metric(client, "http_requests_total"))
    assert 'path="/api/catalog",status="200"' in lines
    assert 'path="/api/orders/{order_id}",status="404"' in lines   # the route, not the raw address
    assert 'path="/static",status="200"' in lines
    assert 'path="other",status="404"' in lines
    assert "OC-NOSUCH" not in lines and "123456" not in lines
    assert "/metrics" not in lines and "/internal" not in lines


def test_store_counters_follow_what_visitors_do(client):
    def value(name):
        return float(next(metric(client, name)).split()[-1])

    before = value("demo_app_estimates_total"), value("demo_app_orders_placed_total"), value("demo_app_orders_cancelled_total")
    client.post("/api/estimate", json=SELECTION)
    order = client.post("/api/orders", json={**SELECTION, "project": "site"}, headers=VISITOR).json()
    client.post(f"/api/orders/{order['id']}/cancel", headers=VISITOR)
    client.post(f"/api/orders/{order['id']}/cancel", headers=VISITOR)  # cancelling twice counts once
    after = value("demo_app_estimates_total"), value("demo_app_orders_placed_total"), value("demo_app_orders_cancelled_total")
    assert [b - a for a, b in zip(before, after, strict=True)] == [1.0, 1.0, 1.0]


# --- controlled faults and recovery -------------------------------------------------
def test_control_endpoints_need_their_tokens(client):
    assert client.get("/internal/state").status_code == 401
    assert client.post("/internal/fault", json={"mode": "outage"}).status_code == 401
    assert client.post("/internal/fault", json={"mode": "outage"}, headers=RECOVERY).status_code == 401
    assert client.post("/internal/recover", headers=CONTROL).status_code == 401
    assert client.post("/internal/fault", json={"mode": "meltdown"}, headers=CONTROL).status_code == 422
    assert client.post("/internal/fault", json={"mode": "memory"}, headers=CONTROL).status_code == 422  # switched off
    assert client.get("/internal/state", headers=CONTROL).json()["fault_mode"] == "none"


def test_outage_stops_the_store_but_not_liveness_or_recovery(client):
    assert client.post("/internal/fault", json={"mode": "outage"}, headers=CONTROL).status_code == 200
    page = client.get("/", headers={"Accept": "text/html"})
    assert page.status_code == 503 and "temporarily unavailable" in page.text
    assert client.get("/api/catalog").status_code == 503
    assert client.get("/metrics").status_code == 503
    assert client.get("/health/ready").status_code == 503
    assert client.get("/health/live").status_code == 200

    recovered = client.post("/internal/recover", headers=RECOVERY).json()
    assert recovered["status"] == "recovered" and recovered["previous_fault_mode"] == "outage"
    assert recovered["service_restarts"] >= 1
    assert client.get("/api/catalog").status_code == 200


def test_error_fault_fails_most_store_requests_and_leaves_the_page_up(client):
    client.post("/internal/fault", json={"mode": "errors"}, headers=CONTROL)
    codes = [client.get("/api/catalog").status_code for _ in range(20)]
    assert codes.count(500) == 18 and codes.count(200) == 2
    assert client.get("/").status_code == 200
    assert client.post("/api/estimate", json=SELECTION).status_code in (200, 500)
    client.post("/internal/fault", json={"mode": "none"}, headers=CONTROL)
    assert client.get("/api/catalog").status_code == 200


def test_latency_fault_slows_the_store_api(client, monkeypatch):
    slept = []
    monkeypatch.setattr(store_app.time, "sleep", slept.append)
    client.post("/internal/fault", json={"mode": "latency"}, headers=CONTROL)
    assert client.get("/api/catalog").status_code == 200
    assert client.get("/api/orders", headers=VISITOR).status_code == 200
    assert slept == [store_app.LATENCY_SECONDS, store_app.LATENCY_SECONDS]
    assert client.get("/").status_code == 200 and len(slept) == 2  # the page itself is not slowed


def test_synthetic_load_is_a_visitor_like_mix():
    requests = [store_app._load_request("http://127.0.0.1:8001", n) for n in range(1, 101)]
    paths = [request.full_url.replace("http://127.0.0.1:8001", "") for request in requests]
    assert paths.count("/api/orders/OC-NOSUCH") == 4          # a genuine 404, 4 in 100
    assert {"/api/catalog", "/api/estimate", "/api/orders"} <= set(paths)
    assert all(request.get_header("X-session-id") for request in requests)
