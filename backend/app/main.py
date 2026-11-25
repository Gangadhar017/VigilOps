"""VigilOps API application."""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import inspect
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.store import router as store_router
from app.core.config import settings
from app.core.database import SessionLocal, check_database, engine
from app.core.logging import configure_logging
from app.core.metrics import HTTP_DURATION, HTTP_REQUESTS
from app.core.request_context import get_request_id, new_request_id, set_request_context
from app.services.bootstrap import run_bootstrap
from app.services.dashboard_service import refresh_gauges

configure_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)
logger = logging.getLogger("vigilops.api")
access_logger = logging.getLogger("vigilops.access")

_started_at = time.time()
_state: Dict[str, Any] = {"bootstrapped": False}


def schema_ready() -> bool:
    """Have the database migrations been applied?"""
    try:
        return inspect(engine).has_table("users")
    except Exception:  # noqa: BLE001
        return False


def apply_migrations(attempts: int = 12, delay_seconds: float = 10.0, database_url: str = "") -> None:
    """Run "alembic upgrade head" in this process (RUN_MIGRATIONS_ON_START).

    A database created moments ago may not accept connections yet, so a failure
    is retried for about two minutes before the start-up is abandoned.
    ``database_url`` overrides the configured database (used by tests).
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.attributes["configure_logger"] = False  # keep this process's logging setup
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    for attempt in range(1, attempts + 1):
        try:
            command.upgrade(config, "head")
            logger.info("database migrations applied")
            return
        except Exception as exc:  # noqa: BLE001 - reported, retried, then re-raised
            logger.warning(
                "database migration failed",
                extra={"attempt": attempt, "of": attempts, "error": exc.__class__.__name__},
            )
            if attempt == attempts:
                raise
            time.sleep(delay_seconds)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.RUN_MIGRATIONS_ON_START:
        apply_migrations()
    if settings.uses_placeholder_secrets():
        logger.warning(
            "placeholder secrets from .env.example are in use; acceptable for local "
            "development only - generate real values before any shared deployment"
        )
    if schema_ready():
        with SessionLocal() as db:
            run_bootstrap(db)
            refresh_gauges(db)
        _state["bootstrapped"] = True
    else:
        logger.error("database schema missing: run 'alembic upgrade head' before starting the API")
    if settings.ai_configured:
        # Load the AI client in the background now, so that the first question
        # does not pay for importing the SDK (seconds on a small CPU share).
        # No request is sent to the provider.
        from app.assistant.providers import get_provider

        threading.Thread(target=get_provider, name="ai-client-warmup", daemon=True).start()
    logger.info(
        "vigilops api started",
        extra={
            "environment": settings.ENVIRONMENT,
            "version": settings.VERSION,
            "demo_controls": settings.demo_controls_active,
            "ai_provider": settings.AI_PROVIDER,
            "ai_configured": settings.ai_configured,
        },
    )
    yield


app = FastAPI(
    title="VigilOps API",
    description=(
        "VigilOps: Secure Cloud Operations - monitoring, incident management, security "
        "configuration scanning, controlled remediation, audit logging and the VigilAI assistant."
    ),
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )


# Paths meant for the internal network only.  Behind the Compose reverse proxy
# they are never routed; when the API port itself is public they are refused
# here unless the caller is on the loopback interface (the bundled Prometheus).
_INTERNAL_PATHS = ("/metrics", "/health/ready")


def _is_local_caller(request: Request) -> bool:
    # Anything that arrived through a proxy carries a forwarding header that the
    # outside caller cannot remove, so its presence alone rules the request out.
    if request.headers.get("x-forwarded-for") or request.headers.get("forwarded"):
        return False
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Correlation id, structured access log and Prometheus instrumentation."""
    request_id = new_request_id(request.headers.get("x-request-id"))
    client_ip = request.client.host if request.client else None
    set_request_context(request_id, client_ip)
    started = time.perf_counter()
    status_code = 500
    try:
        if (
            settings.INTERNAL_ENDPOINTS_LOCAL_ONLY
            and request.url.path in _INTERNAL_PATHS
            and not _is_local_caller(request)
        ):
            response = JSONResponse(status_code=404, content={"detail": "Not Found", "request_id": request_id})
        else:
            response = await call_next(request)
        status_code = response.status_code
    finally:
        duration = time.perf_counter() - started
        route = request.scope.get("route")
        # Use the route template (never the raw URL) to keep label cardinality bounded.
        path = getattr(route, "path", None) or "unmatched"
        if path != "/metrics":
            HTTP_REQUESTS.labels(method=request.method, path=path, status=str(status_code)).inc()
            HTTP_DURATION.labels(method=request.method, path=path).observe(duration)
            if not path.startswith("/health"):
                access_logger.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "duration_ms": round(duration * 1000, 1),
                        "client_ip": client_ip,
                    },
                )
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


# ---------------------------------------------------------------------------
# Error handling: consistent JSON, no stack traces to clients
# ---------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": get_request_id()},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    errors = [
        {
            "field": ".".join(str(part) for part in error.get("loc", []) if part != "body"),
            "message": error.get("msg", "invalid value"),
        }
        for error in exc.errors()
    ]
    summary = "; ".join(f"{e['field']}: {e['message']}" if e["field"] else e["message"] for e in errors[:3])
    return JSONResponse(
        status_code=422,
        content={"detail": summary or "Invalid request.", "errors": errors, "request_id": get_request_id()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("unhandled error", extra={"error": exc.__class__.__name__})
    # This handler runs outside the request middleware, so set its headers here.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "request_id": get_request_id()},
        headers={"X-Request-ID": get_request_id() or "", "Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# Health and metrics (not under /api; /metrics is never routed by the reverse proxy)
#
# The two public probes also answer HEAD: uptime monitors and some platform
# checks send HEAD, and a 405 would be reported as "down".
# ---------------------------------------------------------------------------
@app.get("/health/live", tags=["Health"], summary="Liveness probe")
@app.head("/health/live", include_in_schema=False)
def health_live() -> Dict[str, Any]:
    """The process is running.  Does not check dependencies."""
    if settings.is_production:
        # May be reachable without authentication (platform health checks).
        return {"status": "alive"}
    return {"status": "alive", "service": settings.PROJECT_NAME, "version": settings.VERSION}


@app.get("/health/ready", tags=["Health"], summary="Readiness probe")
def health_ready(response: Response) -> Dict[str, Any]:
    """Ready to serve traffic: database reachable and migrations applied."""
    database_ok, database_error = check_database()
    schema_ok = database_ok and schema_ready()
    if schema_ok and not _state["bootstrapped"]:
        with SessionLocal() as db:
            run_bootstrap(db)
        _state["bootstrapped"] = True
    ready = database_ok and schema_ok
    if not ready:
        response.status_code = 503
    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": {"ok": database_ok, "error": database_error},
            "schema": {"ok": schema_ok},
        },
    }


@app.get("/api/health", tags=["Health"], summary="Combined health summary")
@app.head("/api/health", include_in_schema=False)
def api_health(response: Response) -> Dict[str, Any]:
    result = health_ready(response)
    if settings.is_production:
        # Reachable without authentication: disclose nothing but the status.
        return {"status": "healthy" if result["status"] == "ready" else "unhealthy"}
    return {
        "status": "healthy" if result["status"] == "ready" else "unhealthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - _started_at, 1),
        "checks": result["checks"],
    }


@app.get("/api/version", tags=["Health"])
def api_version() -> Dict[str, Any]:
    if settings.is_production:
        return {"project": settings.PROJECT_TITLE}
    return {"project": settings.PROJECT_TITLE, "version": settings.VERSION, "environment": settings.ENVIRONMENT}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus exposition endpoint (scraped over the internal network only)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(api_router)
# The demonstration application's public address on this port.  It answers 404
# unless SERVE_DEMO_APP is set (hosts without a reverse proxy in front).
app.include_router(store_router)
