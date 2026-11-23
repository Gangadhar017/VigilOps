"""VigilOps demonstration application - a small "order service".

Purpose
-------
A monitored workload for the local VigilOps environment.  Its telemetry is
genuine: request counts and durations are measured by middleware for every
real HTTP request, and CPU / memory come from the process's own counters
(prometheus_client's ProcessCollector).  Nothing is generated with random
numbers.

Because a demo needs traffic, a built-in *synthetic load generator* sends real
HTTP requests to the service's own endpoints.  The workload is synthetic; the
measurements of it are real.

Controlled faults (demo only)
-----------------------------
When ``DEMO_CONTROLS_ENABLED=true`` a token-protected control API can put the
service into a fault mode:

  outage   every service endpoint (and /metrics) answers HTTP 503
  errors   the business endpoint answers HTTP 500 for most requests
  latency  the business endpoint takes ~1.5 s
  cpu      a bounded background thread keeps one core busy
  memory   a bounded block of memory is allocated

Recovery
--------
``POST /internal/recover`` (separate recovery token, held only by the VigilOps
remediation worker) re-initialises the service component and clears any fault.
This is the narrowly scoped mechanism behind remediation ACTION-001: no shell,
no Docker daemon, no host access.
"""
from __future__ import annotations

import gc
import hmac
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel

SERVICE_NAME = "vigilops-demo-app"
PORT = int(os.environ.get("PORT", "8001"))
DEMO_CONTROLS_ENABLED = os.environ.get("DEMO_CONTROLS_ENABLED", "false").lower() == "true"
CONTROL_TOKEN = os.environ.get("DEMO_APP_CONTROL_TOKEN", "")
RECOVERY_TOKEN = os.environ.get("DEMO_APP_RECOVERY_TOKEN", "")
LOAD_GENERATOR_ENABLED = os.environ.get("LOAD_GENERATOR_ENABLED", "true").lower() == "true"
LOAD_INTERVAL_SECONDS = float(os.environ.get("LOAD_INTERVAL_SECONDS", "0.5"))

FAULT_MODES = ("none", "outage", "errors", "latency", "cpu", "memory")
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
        self.orders_served = 0
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

ORDERS = [
    {"id": 1001, "customer": "acme-retail", "items": 3, "total": 148.50, "status": "shipped"},
    {"id": 1002, "customer": "globex", "items": 1, "total": 39.99, "status": "processing"},
    {"id": 1003, "customer": "initech", "items": 7, "total": 512.00, "status": "delivered"},
]

app = FastAPI(
    title="VigilOps Demo Application",
    version="2.0.0",
    description="Monitored demonstration order service for the VigilOps local environment.",
    docs_url=None,
    redoc_url=None,
)

# Paths that stay reachable during a simulated outage: the process is alive
# (liveness) and the control plane must be able to recover it.
_ALWAYS_AVAILABLE = ("/health/live", "/internal/")


@app.middleware("http")
async def instrument(request: Request, call_next):
    started = time.perf_counter()
    path = request.url.path
    state.expire_if_needed()

    if not state.serving and not path.startswith(_ALWAYS_AVAILABLE):
        response: Response = JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "Service component is not running."},
        )
        template = path if path in ("/", "/metrics", "/health", "/health/ready", "/api/orders") else "other"
    else:
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - count unexpected failures as 500s
            response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
        route = request.scope.get("route")
        template = getattr(route, "path", None) or "other"

    if template != "/metrics" and not template.startswith("/internal"):
        HTTP_REQUESTS.labels(method=request.method, path=template, status=str(response.status_code)).inc()
        HTTP_DURATION.labels(method=request.method, path=template).observe(time.perf_counter() - started)
    return response


# ---------------------------------------------------------------------------
# Service endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root() -> Dict[str, Any]:
    return {"service": SERVICE_NAME, "status": "running", "endpoints": ["/api/orders", "/health/live", "/health/ready", "/metrics"]}


@app.get("/health/live")
def health_live() -> Dict[str, Any]:
    """Liveness: the process is running (true even during a service outage)."""
    return {"status": "alive", "service": SERVICE_NAME}


@app.get("/health/ready")
@app.get("/health")
def health_ready() -> Dict[str, Any]:
    """Readiness: the service component is able to handle requests."""
    return {"status": "ready", **state.snapshot()}


@app.get("/api/orders")
def list_orders() -> Dict[str, Any]:
    mode = state.fault_mode
    if mode == "latency":
        time.sleep(LATENCY_SECONDS)
    if mode == "errors":
        state.orders_served += 1
        if state.orders_served % 10 != 0:  # 9 of 10 requests fail
            raise HTTPException(status_code=500, detail="Order backend failure.")
    return {"orders": ORDERS, "count": len(ORDERS)}


@app.get("/api/orders/{order_id}")
def get_order(order_id: int) -> Dict[str, Any]:
    for order in ORDERS:
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found.")


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
def _load_loop() -> None:
    base = f"http://127.0.0.1:{PORT}"
    counter = 0
    time.sleep(2.0)
    while True:
        counter += 1
        # Roughly 1 request in 25 asks for an order that does not exist (a genuine 404).
        path = "/api/orders/9999" if counter % 25 == 0 else ("/api/orders/1001" if counter % 5 == 0 else "/api/orders")
        try:
            with urllib.request.urlopen(base + path, timeout=5) as response:
                response.read()
        except (urllib.error.URLError, OSError, TimeoutError):
            pass  # failures are recorded by the service's own metrics
        time.sleep(LOAD_INTERVAL_SECONDS)


@app.on_event("startup")
def _start_load_generator() -> None:
    if LOAD_GENERATOR_ENABLED:
        threading.Thread(target=_load_loop, daemon=True, name="synthetic-load").start()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
