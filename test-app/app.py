"""OrbitCrate - the demonstration application monitored by VigilOps.

Purpose
-------
A small but real web application: the storefront of a fictional cloud-hosting
provider.  Visitors browse server plans, estimate a monthly price, place an
order and watch it move through provisioning.  Nothing is provisioned or
charged - the application says so on every page - but every request is a real
HTTP request handled by this service.

It is the workload VigilOps watches.  Its telemetry is genuine: request counts
and durations are measured by middleware for every request, and CPU / memory
come from the process's own counters (prometheus_client's ProcessCollector).
Nothing is generated with random numbers.

Because a demo needs traffic even when nobody is browsing, a built-in
*synthetic load generator* sends real HTTP requests to the service's own
endpoints.  The workload is synthetic; the measurements of it are real.

Controlled faults (demo only)
-----------------------------
When ``DEMO_CONTROLS_ENABLED=true`` a token-protected control API can put the
service into a fault mode:

  outage   every page, API endpoint and /metrics answer HTTP 503
  errors   the store's API answers HTTP 500 for most requests
  latency  the store's API takes ~1.5 s
  cpu      a bounded background thread keeps one core busy
  memory   a bounded block of memory is allocated

Recovery
--------
``POST /internal/recover`` (separate recovery token, held only by the VigilOps
remediation worker) re-initialises the service component and clears any fault.
This is the narrowly scoped mechanism behind remediation ACTION-001: no shell,
no Docker daemon, no host access.

What is public
--------------
The pages, ``/static`` and ``/api`` are meant for visitors.  ``/internal``,
``/metrics`` and ``/health`` are for the platform and are never routed by the
reverse proxy.
"""
from __future__ import annotations

import gc
import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

mimetypes.add_type("font/woff2", ".woff2")  # not known to every platform's type table

SERVICE_NAME = "vigilops-demo-app"
PRODUCT_NAME = "OrbitCrate"
STATIC_DIR = Path(__file__).resolve().parent / "static"
PORT = int(os.environ.get("PORT", "8001"))
# 0.0.0.0 inside its own container; 127.0.0.1 when it shares a container with the platform.
HOST = os.environ.get("HOST", "0.0.0.0")
DEMO_CONTROLS_ENABLED = os.environ.get("DEMO_CONTROLS_ENABLED", "false").lower() == "true"
CONTROL_TOKEN = os.environ.get("DEMO_APP_CONTROL_TOKEN", "")
RECOVERY_TOKEN = os.environ.get("DEMO_APP_RECOVERY_TOKEN", "")
LOAD_GENERATOR_ENABLED = os.environ.get("LOAD_GENERATOR_ENABLED", "true").lower() == "true"
LOAD_INTERVAL_SECONDS = float(os.environ.get("LOAD_INTERVAL_SECONDS", "0.5"))

FAULT_MODES = ("none", "outage", "errors", "latency", "cpu", "memory")
# Faults a small host cannot survive can be switched off (e.g. "cpu,memory").
DISABLED_FAULTS = {
    mode.strip().lower() for mode in os.environ.get("DEMO_DISABLED_FAULTS", "").split(",") if mode.strip()
} - {"none"}
FAULT_TTL_SECONDS = 600           # cpu / memory faults clear themselves after 10 minutes
MEMORY_BALLAST_BYTES = 220 * 1024 * 1024
LATENCY_SECONDS = 1.5

# ---------------------------------------------------------------------------
# Metrics (process_* CPU and memory metrics are registered by default)
# ---------------------------------------------------------------------------
HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests handled.", ["method", "path", "status"]
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
SERVICE_RESTARTS = Counter("demo_app_service_restarts_total", "Service re-initialisations.")
FAULT_ACTIVE = Gauge(
    "demo_app_fault_active",
    "1 while a controlled demo fault is active (marks simulated conditions).",
    ["mode"],
)
for _mode in FAULT_MODES[1:]:
    FAULT_ACTIVE.labels(mode=_mode).set(0)
ESTIMATES = Counter("demo_app_estimates_total", "Price estimates calculated.")
ORDERS_PLACED = Counter("demo_app_orders_placed_total", "Orders placed in the store.")
ORDERS_CANCELLED = Counter("demo_app_orders_cancelled_total", "Orders cancelled in the store.")
SESSIONS = Gauge("demo_app_sessions", "Visitor sessions currently held in memory.")


# ---------------------------------------------------------------------------
# Service state
# ---------------------------------------------------------------------------
class ServiceState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.fault_mode = "none"
        self.fault_since: Optional[float] = None
        self.service_started_at = time.time()
        self.restarts = 0
        self.business_calls = 0
        self._ballast: Optional[bytearray] = None
        self._burner_stop = threading.Event()
        self._burner: Optional[threading.Thread] = None

    # -- fault helpers ---------------------------------------------------
    def _burn_cpu(self, stop: threading.Event, deadline: float) -> None:
        value = 0
        while not stop.is_set() and time.time() < deadline:
            for index in range(20000):
                value = (value + index * index) % 1000003
        if not stop.is_set():
            self.set_fault("none")  # TTL reached

    def _clear_resources(self) -> None:
        self._burner_stop.set()
        self._burner = None
        self._ballast = None
        gc.collect()

    def set_fault(self, mode: str) -> None:
        with self.lock:
            self._clear_resources()
            self.fault_mode = mode
            self.fault_since = time.time() if mode != "none" else None
            for name in FAULT_MODES[1:]:
                FAULT_ACTIVE.labels(mode=name).set(1 if name == mode else 0)
            if mode == "cpu":
                self._burner_stop = threading.Event()
                self._burner = threading.Thread(
                    target=self._burn_cpu,
                    args=(self._burner_stop, time.time() + FAULT_TTL_SECONDS),
                    daemon=True,
                    name="cpu-fault",
                )
                self._burner.start()
            elif mode == "memory":
                ballast = bytearray(MEMORY_BALLAST_BYTES)
                for offset in range(0, MEMORY_BALLAST_BYTES, 4096):
                    ballast[offset] = 1  # touch every page so the memory is really resident
                self._ballast = ballast

    def recover(self) -> None:
        """Re-initialise the service component: the genuine recovery operation."""
        self.set_fault("none")
        with self.lock:
            self.service_started_at = time.time()
            self.restarts += 1
        SERVICE_RESTARTS.inc()

    def expire_if_needed(self) -> None:
        if self.fault_mode == "memory" and self.fault_since and time.time() - self.fault_since > FAULT_TTL_SECONDS:
            self.set_fault("none")

    @property
    def serving(self) -> bool:
        return self.fault_mode != "outage"

    def snapshot(self) -> Dict[str, Any]:
        return {
            "service": SERVICE_NAME,
            "fault_mode": self.fault_mode,
            "fault_since": _iso(self.fault_since),
            "serving": self.serving,
            "service_started_at": _iso(self.service_started_at),
            "service_restarts": self.restarts,
            "demo_controls_enabled": DEMO_CONTROLS_ENABLED,
        }


def _iso(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


state = ServiceState()


def business_call() -> None:
    """Apply the active fault to one request of the store's API."""
    mode = state.fault_mode
    if mode == "latency":
        time.sleep(LATENCY_SECONDS)
    if mode == "errors":
        state.business_calls += 1
        if state.business_calls % 10 != 0:  # 9 of 10 requests fail
            raise HTTPException(status_code=500, detail="The store backend failed to answer.")


# ---------------------------------------------------------------------------
# Store: catalogue, price calculation and per-visitor orders
# ---------------------------------------------------------------------------
CURRENCY = "INR"
TAX_RATE = 0.18  # GST shown as a separate line
PLANS = [
    {"id": "crate-s", "name": "Crate S", "vcpu": 1, "ram_gb": 1, "disk_gb": 25, "transfer_tb": 1, "price": 349,
     "summary": "Small sites and test environments"},
    {"id": "crate-m", "name": "Crate M", "vcpu": 2, "ram_gb": 4, "disk_gb": 80, "transfer_tb": 3, "price": 1199,
     "summary": "Web applications and APIs", "featured": True},
    {"id": "crate-l", "name": "Crate L", "vcpu": 4, "ram_gb": 8, "disk_gb": 160, "transfer_tb": 5, "price": 2399,
     "summary": "Busy applications and databases"},
    {"id": "crate-xl", "name": "Crate XL", "vcpu": 8, "ram_gb": 16, "disk_gb": 320, "transfer_tb": 8, "price": 4799,
     "summary": "High-traffic services"},
]
REGIONS = [
    {"id": "bom-1", "name": "Mumbai", "multiplier": 1.0},
    {"id": "sin-1", "name": "Singapore", "multiplier": 1.08},
    {"id": "fra-1", "name": "Frankfurt", "multiplier": 1.12},
]
ADDONS = [
    {"id": "backups", "name": "Daily backups", "kind": "percent", "value": 20,
     "description": "A copy of every server each night, kept for seven days."},
    {"id": "storage-100", "name": "Extra 100 GB block storage", "kind": "flat", "value": 400,
     "description": "Attachable volume, per server."},
    {"id": "ipv4", "name": "Dedicated IPv4 address", "kind": "flat", "value": 150,
     "description": "One public address per server."},
    {"id": "support", "name": "Priority support", "kind": "flat", "value": 500,
     "description": "Answers within one hour, per server."},
]
TERMS = [
    {"id": "monthly", "name": "Monthly", "discount_percent": 0},
    {"id": "yearly", "name": "Yearly commitment", "discount_percent": 15},
]
_PLANS = {plan["id"]: plan for plan in PLANS}
_REGIONS = {region["id"]: region for region in REGIONS}
_ADDONS = {addon["id"]: addon for addon in ADDONS}
_TERMS = {term["id"]: term for term in TERMS}

MAX_SESSIONS = 300
MAX_ORDERS_PER_SESSION = 20
MAX_ORDER_WRITES_PER_MINUTE = 12
RECEIVED_SECONDS = 6       # an order is "received", then
PROVISIONING_SECONDS = 20  # "provisioning" until this age, then "active"
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_ORDER_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class Selection(BaseModel):
    plan: str = Field(min_length=1, max_length=20)
    region: str = Field(min_length=1, max_length=20)
    quantity: int = Field(default=1, ge=1, le=10)
    addons: List[str] = Field(default_factory=list, max_length=len(ADDONS))
    term: str = Field(default="monthly", max_length=20)


class OrderRequest(Selection):
    project: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._-]{1,39}$")


def money(value: float) -> float:
    return round(value + 1e-9, 2)


def calculate(selection: Selection) -> Dict[str, Any]:
    """Price of a selection, as line items.  Raises 422 for unknown identifiers."""
    plan = _PLANS.get(selection.plan)
    region = _REGIONS.get(selection.region)
    term = _TERMS.get(selection.term)
    addon_ids = list(dict.fromkeys(selection.addons))  # keep order, drop duplicates
    unknown = [addon for addon in addon_ids if addon not in _ADDONS]
    if plan is None or region is None or term is None or unknown:
        raise HTTPException(status_code=422, detail="Unknown plan, region, add-on or term.")

    quantity = selection.quantity
    base = plan["price"] * region["multiplier"] * quantity
    lines = [{
        "label": f"{quantity} x {plan['name']} in {region['name']}",
        "amount": money(base),
    }]
    for addon_id in addon_ids:
        addon = _ADDONS[addon_id]
        amount = base * addon["value"] / 100 if addon["kind"] == "percent" else addon["value"] * quantity
        lines.append({"label": addon["name"], "amount": money(amount)})
    # Each amount is rounded where it is shown, so the lines add up to the total exactly.
    subtotal = money(sum(line["amount"] for line in lines))
    discount = money(subtotal * term["discount_percent"] / 100)
    if discount:
        lines.append({"label": f"{term['name']} (-{term['discount_percent']}%)", "amount": -discount})
    net = money(subtotal - discount)
    tax = money(net * TAX_RATE)
    return {
        "currency": CURRENCY,
        "lines": lines,
        "net": net,
        "tax_label": "GST 18%",
        "tax": tax,
        "monthly_total": money(net + tax),
        "selection": {
            "plan": plan["id"], "plan_name": plan["name"], "region": region["id"], "region_name": region["name"],
            "quantity": quantity, "addons": addon_ids, "term": term["id"],
        },
    }


class Store:
    """Orders per visitor session, in memory and bounded.  No personal data is kept."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sessions: "OrderedDict[str, Dict[str, Dict[str, Any]]]" = OrderedDict()
        self.writes: Dict[str, Deque[float]] = {}

    def _orders(self, session: str, create: bool = False) -> Dict[str, Dict[str, Any]]:
        """The visitor's orders.  Reading never creates a session; placing an order does."""
        orders = self.sessions.get(session)
        if orders is None:
            if not create:
                return {}
            orders = {}
            self.sessions[session] = orders
            while len(self.sessions) > MAX_SESSIONS:  # forget the least recently used visitor
                forgotten, _ = self.sessions.popitem(last=False)
                self.writes.pop(forgotten, None)
        self.sessions.move_to_end(session)
        SESSIONS.set(len(self.sessions))
        return orders

    def allow_write(self, session: str) -> bool:
        now = time.monotonic()
        if session not in self.writes and len(self.writes) >= MAX_SESSIONS * 2:
            self.writes.clear()  # bounded even when many visitors only ever try once
        window = self.writes.setdefault(session, deque())
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= MAX_ORDER_WRITES_PER_MINUTE:
            return False
        window.append(now)
        return True

    def list(self, session: str) -> List[Dict[str, Any]]:
        with self.lock:
            return sorted((present(order) for order in self._orders(session).values()), key=lambda o: o["created_at"], reverse=True)

    def get(self, session: str, order_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            order = self._orders(session).get(order_id)
            return present(order) if order else None

    def place(self, session: str, request: OrderRequest, price: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if not self.allow_write(session):
                raise HTTPException(status_code=429, detail="Too many orders in a short time. Please wait a minute.")
            orders = self._orders(session, create=True)
            if len(orders) >= MAX_ORDERS_PER_SESSION:
                raise HTTPException(status_code=409, detail=f"This demonstration keeps at most {MAX_ORDERS_PER_SESSION} orders per visitor. Cancel one first.")
            order_id = "OC-" + "".join(secrets.choice(_ORDER_ID_ALPHABET) for _ in range(6))
            order = {
                "id": order_id, "project": request.project.strip(), "created": time.time(), "cancelled": None,
                "selection": price["selection"], "currency": price["currency"], "monthly_total": price["monthly_total"],
            }
            orders[order_id] = order
            ORDERS_PLACED.inc()
            return present(order)

    def cancel(self, session: str, order_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            order = self._orders(session).get(order_id)
            if order is None:
                return None
            if order["cancelled"] is None:
                order["cancelled"] = time.time()
                ORDERS_CANCELLED.inc()
            return present(order)

    def clear(self) -> None:
        with self.lock:
            self.sessions.clear()
            self.writes.clear()
            SESSIONS.set(0)


def present(order: Dict[str, Any]) -> Dict[str, Any]:
    """Public view of an order.  Its status follows from its age: the store's own
    fulfilment pipeline is part of the demonstration and creates nothing real."""
    age = time.time() - order["created"]
    if order["cancelled"] is not None:
        status = "cancelled"
    elif age < RECEIVED_SECONDS:
        status = "received"
    elif age < PROVISIONING_SECONDS:
        status = "provisioning"
    else:
        status = "active"
    return {
        "id": order["id"], "project": order["project"], "status": status,
        "created_at": _iso(order["created"]), "cancelled_at": _iso(order["cancelled"]),
        "ready_in_seconds": max(0, round(PROVISIONING_SECONDS - age)) if status in ("received", "provisioning") else 0,
        "selection": order["selection"], "currency": order["currency"], "monthly_total": order["monthly_total"],
    }


store = Store()


def session_id(value: Optional[str]) -> str:
    if not value or not _SESSION_RE.match(value):
        raise HTTPException(status_code=400, detail="A visitor session is required (X-Session-Id header).")
    return value


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if LOAD_GENERATOR_ENABLED:
        threading.Thread(target=_load_loop, daemon=True, name="synthetic-load").start()
    yield


app = FastAPI(
    title="OrbitCrate - VigilOps demonstration application",
    version="3.0.0",
    description="Monitored demonstration storefront for the VigilOps environment.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# Paths that stay reachable during a simulated outage: the process is alive
# (liveness) and the control plane must be able to recover it.
_ALWAYS_AVAILABLE = ("/health/live", "/internal/")
# Metric labels must stay bounded, so only these raw paths are ever used as a label.
_KNOWN_PATHS = (
    "/", "/metrics", "/health", "/health/ready", "/api/status", "/api/info", "/api/catalog",
    "/api/estimate", "/api/orders",
)

# The page loads only its own files; the outage page carries its few styles inline.
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)

_OUTAGE_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>OrbitCrate is unavailable</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b1b3a;color:#f4f6fb;
font-family:system-ui,-apple-system,"Segoe UI",sans-serif;text-align:center;padding:24px}
h1{font-size:28px;margin:0 0 8px}p{margin:6px 0;color:#b7c2da;max-width:34rem;line-height:1.5}
code{display:inline-block;margin-top:18px;padding:6px 10px;border:1px solid #2a3c66;border-radius:8px;color:#ffb199}
</style></head><body><main><h1>OrbitCrate is temporarily unavailable</h1>
<p>The store is not answering requests right now. Please try again in a moment.</p>
<code>HTTP 503 &middot; Service Unavailable</code></main></body></html>"""


@app.middleware("http")
async def instrument(request: Request, call_next):
    started = time.perf_counter()
    path = request.url.path
    state.expire_if_needed()

    if not state.serving and not path.startswith(_ALWAYS_AVAILABLE):
        wants_page = request.method == "GET" and not path.startswith(("/api/", "/metrics", "/health", "/static/"))
        if wants_page and "text/html" in request.headers.get("accept", ""):
            response: Response = HTMLResponse(_OUTAGE_PAGE, status_code=503, headers={"Cache-Control": "no-store", "Retry-After": "30"})
        else:
            response = JSONResponse(
                status_code=503,
                content={"status": "unavailable", "detail": "Service component is not running."},
            )
        template = path if path in _KNOWN_PATHS else "/static" if path.startswith("/static/") else "other"
    else:
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - count unexpected failures as 500s
            response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
        route = request.scope.get("route")
        template = "/static" if path.startswith("/static/") else getattr(route, "path", None) or "other"

    if template != "/metrics" and not template.startswith("/internal"):
        HTTP_REQUESTS.labels(method=request.method, path=template, status=str(response.status_code)).inc()
        HTTP_DURATION.labels(method=request.method, path=template).observe(time.perf_counter() - started)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Content-Security-Policy", _CONTENT_SECURITY_POLICY)
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def storefront() -> Response:
    """The single-page storefront.  Its assets use relative addresses, so it works
    behind a path prefix of the reverse proxy as well as at the root."""
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Platform endpoints
# ---------------------------------------------------------------------------
@app.get("/health/live")
def health_live() -> Dict[str, Any]:
    """Liveness: the process is running (true even during a service outage)."""
    return {"status": "alive", "service": SERVICE_NAME}


@app.get("/health/ready")
@app.get("/health")
def health_ready() -> Dict[str, Any]:
    """Readiness: the service component is able to handle requests."""
    return {"status": "ready", **state.snapshot()}


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Store API (public)
# ---------------------------------------------------------------------------
@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    """What a visitor may know: whether the store is answering."""
    return {"status": "operational", "product": PRODUCT_NAME, "time": _iso(time.time())}


@app.get("/api/info")
def api_info() -> Dict[str, Any]:
    return {
        "product": PRODUCT_NAME,
        "service": SERVICE_NAME,
        "demonstration": True,
        "notice": "Demonstration application. Orders are not real; nothing is provisioned or charged.",
    }


@app.get("/api/catalog")
def catalog() -> Dict[str, Any]:
    business_call()
    return {"currency": CURRENCY, "plans": PLANS, "regions": REGIONS, "addons": ADDONS, "terms": TERMS}


@app.post("/api/estimate")
def estimate(selection: Selection) -> Dict[str, Any]:
    business_call()
    price = calculate(selection)
    ESTIMATES.inc()
    return price


@app.get("/api/orders")
def list_orders(x_session_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    session = session_id(x_session_id)
    business_call()
    orders = store.list(session)
    return {"orders": orders, "count": len(orders), "limit": MAX_ORDERS_PER_SESSION}


@app.post("/api/orders", status_code=201)
def place_order(request: OrderRequest, x_session_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    session = session_id(x_session_id)
    business_call()
    return store.place(session, request, calculate(request))


@app.get("/api/orders/{order_id}")
def get_order(order_id: str, x_session_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    session = session_id(x_session_id)
    business_call()
    order = store.get(session, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@app.post("/api/orders/{order_id}/cancel")
def cancel_order(order_id: str, x_session_id: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    session = session_id(x_session_id)
    business_call()
    order = store.cancel(session, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


# ---------------------------------------------------------------------------
# Internal control API (token protected, internal network only)
# ---------------------------------------------------------------------------
def _bearer(authorization: Optional[str]) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def _matches(provided: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest(provided.encode(), expected.encode())


class FaultRequest(BaseModel):
    mode: str


@app.get("/internal/state")
def internal_state(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _bearer(authorization)
    if not (_matches(token, CONTROL_TOKEN) or _matches(token, RECOVERY_TOKEN)):
        raise HTTPException(status_code=401, detail="Invalid control token.")
    return state.snapshot()


@app.post("/internal/fault")
def internal_fault(payload: FaultRequest, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Inject or clear a controlled fault.  Exists only when demo controls are enabled."""
    if not DEMO_CONTROLS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found.")
    if not _matches(_bearer(authorization), CONTROL_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid control token.")
    if payload.mode not in FAULT_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {', '.join(FAULT_MODES)}")
    if payload.mode in DISABLED_FAULTS:
        raise HTTPException(status_code=422, detail=f"The '{payload.mode}' fault is switched off in this deployment.")
    state.set_fault(payload.mode)
    return {"status": "applied", "simulated": payload.mode != "none", **state.snapshot()}


@app.post("/internal/recover")
def internal_recover(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Re-initialise the service component (used by remediation ACTION-001)."""
    if not RECOVERY_TOKEN:
        raise HTTPException(status_code=503, detail="Recovery is not configured.")
    if not _matches(_bearer(authorization), RECOVERY_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid recovery token.")
    previous = state.fault_mode
    state.recover()
    return {"status": "recovered", "previous_fault_mode": previous, **state.snapshot()}


# ---------------------------------------------------------------------------
# Synthetic load generator (real HTTP requests against this service)
# ---------------------------------------------------------------------------
_LOAD_SESSION = "synthetic-load-generator"
_LOAD_ESTIMATE = json.dumps({"plan": "crate-m", "region": "bom-1", "quantity": 2, "addons": ["backups"], "term": "monthly"}).encode()


def _load_request(base: str, counter: int) -> urllib.request.Request:
    """The mix a browsing visitor produces: catalogue, estimates, order list - and,
    roughly once in 25 requests, an order that does not exist (a genuine 404)."""
    headers = {"X-Session-Id": _LOAD_SESSION}
    if counter % 25 == 0:
        return urllib.request.Request(base + "/api/orders/OC-NOSUCH", headers=headers)
    step = counter % 4
    if step == 0:
        return urllib.request.Request(base + "/api/catalog", headers=headers)
    if step == 1:
        return urllib.request.Request(
            base + "/api/estimate", data=_LOAD_ESTIMATE, method="POST", headers={**headers, "Content-Type": "application/json"}
        )
    return urllib.request.Request(base + "/api/orders", headers=headers)


def _load_loop() -> None:
    base = f"http://127.0.0.1:{PORT}"
    counter = 0
    time.sleep(2.0)
    while True:
        counter += 1
        try:
            with urllib.request.urlopen(_load_request(base, counter), timeout=5) as response:
                response.read()
        except (urllib.error.URLError, OSError, TimeoutError):
            pass  # failures are recorded by the service's own metrics
        time.sleep(LOAD_INTERVAL_SECONDS)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
