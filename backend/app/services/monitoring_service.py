"""Read-only access to Prometheus and Alertmanager.

Every number shown in the UI comes from a Prometheus query made here.  When a
value cannot be obtained the result says so (``available: False`` plus a
reason) - nothing is ever substituted with a made-up default.

Clients may only request metrics by *key* from ``METRIC_CATALOG``; arbitrary
PromQL is never accepted from a browser.
"""
from __future__ import annotations

import math
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.models.models import MonitoredResource

_JOB_NAME = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")

# key -> definition.  %(job)s is replaced with a validated Prometheus job name.
METRIC_CATALOG: Dict[str, Dict[str, str]] = {
    "availability": {
        "label": "Availability",
        "unit": "state",
        "description": "Prometheus scrape success (1 = target reachable, 0 = down).",
        "query": 'up{job="%(job)s"}',
    },
    "request_rate": {
        "label": "HTTP request rate",
        "unit": "req/s",
        "description": "Requests per second over the last minute.",
        "query": 'sum(rate(http_requests_total{job="%(job)s"}[1m]))',
    },
    "error_rate_5xx": {
        "label": "HTTP 5xx error rate",
        "unit": "ratio",
        "description": "Share of requests answered with a 5xx status over the last minute.",
        "query": (
            '(sum(rate(http_requests_total{job="%(job)s",status=~"5.."}[1m])) or vector(0))'
            ' / sum(rate(http_requests_total{job="%(job)s"}[1m]))'
        ),
    },
    "error_rate_4xx": {
        "label": "HTTP 4xx error rate",
        "unit": "ratio",
        "description": "Share of requests answered with a 4xx status over the last minute.",
        "query": (
            '(sum(rate(http_requests_total{job="%(job)s",status=~"4.."}[1m])) or vector(0))'
            ' / sum(rate(http_requests_total{job="%(job)s"}[1m]))'
        ),
    },
    "latency_p95": {
        "label": "Response latency (p95)",
        "unit": "seconds",
        "description": "95th percentile request duration over the last minute.",
        "query": (
            "histogram_quantile(0.95, sum by (le) "
            '(rate(http_request_duration_seconds_bucket{job="%(job)s"}[1m])))'
        ),
    },
    "cpu_usage": {
        "label": "CPU usage",
        "unit": "cores",
        "description": "Process CPU time consumed per second (1.0 = one full core).",
        "query": 'sum(rate(process_cpu_seconds_total{job="%(job)s"}[1m]))',
    },
    "memory_rss": {
        "label": "Memory (resident)",
        "unit": "bytes",
        "description": "Resident memory of the process.",
        "query": 'sum(process_resident_memory_bytes{job="%(job)s"})',
    },
    "uptime": {
        "label": "Uptime",
        "unit": "seconds",
        "description": "Time since the process started.",
        "query": 'time() - max(process_start_time_seconds{job="%(job)s"})',
    },
}

RANGE_PRESETS: Dict[str, Tuple[int, int]] = {
    # name: (window seconds, step seconds)
    "5m": (300, 5),
    "15m": (900, 15),
    "1h": (3600, 30),
    "6h": (21600, 180),
}


class MetricRequestError(ValueError):
    pass


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _parse_number(raw: Any) -> Optional[float]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


class PrometheusClient:
    """Minimal Prometheus / Alertmanager HTTP client with strict timeouts."""

    def __init__(
        self,
        prometheus_url: Optional[str] = None,
        alertmanager_url: Optional[str] = None,
        timeout: Optional[float] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.prometheus_url = (prometheus_url or settings.PROMETHEUS_URL).rstrip("/")
        self.alertmanager_url = (alertmanager_url or settings.ALERTMANAGER_URL).rstrip("/")
        self._client = httpx.Client(
            timeout=timeout or settings.MONITORING_HTTP_TIMEOUT_SECONDS, transport=transport
        )

    # -- low level -----------------------------------------------------
    def _get_json(self, url: str, params: Optional[dict] = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            response = self._client.get(url, params=params)
        except httpx.TimeoutException:
            return None, "timeout"
        except httpx.HTTPError as exc:
            return None, f"unreachable ({exc.__class__.__name__})"
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        try:
            body = response.json()
        except ValueError:
            return None, "invalid response"
        if isinstance(body, dict) and body.get("status") not in (None, "success"):
            return None, str(body.get("error") or "query failed")[:200]
        return body, None

    def _ready(self, base_url: str) -> Dict[str, Any]:
        try:
            response = self._client.get(f"{base_url}/-/ready")
        except httpx.TimeoutException:
            return {"available": False, "error": "timeout"}
        except httpx.HTTPError as exc:
            return {"available": False, "error": f"unreachable ({exc.__class__.__name__})"}
        if response.status_code == 200:
            return {"available": True, "error": None}
        return {"available": False, "error": f"HTTP {response.status_code}"}

    # -- public API ----------------------------------------------------
    def prometheus_ready(self) -> Dict[str, Any]:
        return self._ready(self.prometheus_url)

    def alertmanager_ready(self) -> Dict[str, Any]:
        return self._ready(self.alertmanager_url)

    def instant(self, promql: str) -> Dict[str, Any]:
        """Evaluate an instant query that is expected to return a single value."""
        body, error = self._get_json(f"{self.prometheus_url}/api/v1/query", {"query": promql})
        if error:
            return {"available": False, "value": None, "reason": error, "sampled_at": None}
        result = (body or {}).get("data", {}).get("result", [])
        if not result:
            return {"available": False, "value": None, "reason": "no data", "sampled_at": None}
        timestamp, raw = result[0].get("value", [None, None])
        value = _parse_number(raw)
        if value is None:
            return {"available": False, "value": None, "reason": "no data", "sampled_at": None}
        return {
            "available": True,
            "value": value,
            "reason": None,
            "sampled_at": _iso(float(timestamp)) if timestamp is not None else None,
        }

    def vector(self, promql: str) -> Tuple[Optional[List[dict]], Optional[str]]:
        """Evaluate an instant query and return every series."""
        body, error = self._get_json(f"{self.prometheus_url}/api/v1/query", {"query": promql})
        if error:
            return None, error
        return (body or {}).get("data", {}).get("result", []), None

    def range(self, promql: str, window_seconds: int, step_seconds: int) -> Dict[str, Any]:
        end = time.time()
        start = end - window_seconds
        body, error = self._get_json(
            f"{self.prometheus_url}/api/v1/query_range",
            {"query": promql, "start": f"{start:.3f}", "end": f"{end:.3f}", "step": str(step_seconds)},
        )
        if error:
            return {"available": False, "reason": error, "points": []}
        result = (body or {}).get("data", {}).get("result", [])
        points: List[Dict[str, Any]] = []
        if result:
            previous: Optional[float] = None
            for timestamp, raw in result[0].get("values", []):
                current = float(timestamp)
                # Prometheus omits steps that have no sample (for example while a
                # target is down).  Mark the hole explicitly so charts draw a gap
                # instead of a line that suggests data existed.
                if previous is not None and current - previous > step_seconds * 1.5:
                    points.append({"t": _iso(previous + step_seconds), "v": None})
                points.append({"t": _iso(current), "v": _parse_number(raw)})
                previous = current
        return {
            "available": True,
            "reason": None if points else "no data in the selected range",
            "points": points,
        }

    def targets(self) -> Dict[str, Any]:
        body, error = self._get_json(f"{self.prometheus_url}/api/v1/targets", {"state": "active"})
        if error:
            return {"available": False, "reason": error, "targets": []}
        now = utcnow()
        stale_after = settings.PROMETHEUS_SCRAPE_INTERVAL_SECONDS * 4
        targets = []
        for item in (body or {}).get("data", {}).get("activeTargets", []):
            last_scrape_raw = item.get("lastScrape") or ""
            age: Optional[float] = None
            last_scrape: Optional[str] = None
            try:
                # Prometheus emits RFC3339 with nanoseconds; trim to microseconds.
                cleaned = re.sub(r"(\.\d{6})\d+", r"\1", last_scrape_raw).replace("Z", "+00:00")
                parsed = datetime.fromisoformat(cleaned)
                if parsed.year > 1:
                    last_scrape = parsed.astimezone(timezone.utc).isoformat()
                    age = max((now - parsed.astimezone(timezone.utc)).total_seconds(), 0.0)
            except ValueError:
                pass
            targets.append(
                {
                    "job": item.get("labels", {}).get("job", ""),
                    "instance": item.get("labels", {}).get("instance", ""),
                    "health": item.get("health", "unknown"),
                    "last_scrape": last_scrape,
                    "last_scrape_age_seconds": round(age, 1) if age is not None else None,
                    "last_error": (item.get("lastError") or "")[:300] or None,
                    "scrape_url": item.get("scrapeUrl", ""),
                    # No fresh observation recently: the health value may be outdated.
                    "stale": age is None or age > stale_after,
                }
            )
        targets.sort(key=lambda t: (t["job"], t["instance"]))
        return {"available": True, "reason": None, "targets": targets}

    def firing_alerts(self) -> Dict[str, Any]:
        body, error = self._get_json(f"{self.prometheus_url}/api/v1/alerts")
        if error:
            return {"available": False, "reason": error, "alerts": []}
        alerts = []
        for item in (body or {}).get("data", {}).get("alerts", []):
            labels = item.get("labels", {})
            alerts.append(
                {
                    "name": labels.get("alertname", ""),
                    "state": item.get("state", ""),
                    "severity": str(labels.get("severity", "")).upper(),
                    "resource": labels.get("resource") or labels.get("job", ""),
                    "instance": labels.get("instance", ""),
                    "summary": item.get("annotations", {}).get("summary", ""),
                    "active_at": item.get("activeAt"),
                }
            )
        alerts.sort(key=lambda a: (a["state"] != "firing", a["name"]))
        return {"available": True, "reason": None, "alerts": alerts}

    def alert_is_firing(self, alert_name: str, job: Optional[str] = None) -> Tuple[Optional[bool], Optional[str]]:
        """Is the named alert currently firing?  Returns (None, reason) if unknown."""
        if not re.match(r"^[A-Za-z0-9_]{1,120}$", alert_name):
            return None, "invalid alert name"
        selector = f'alertname="{alert_name}",alertstate="firing"'
        if job and _JOB_NAME.match(job):
            selector += f',job="{job}"'
        series, error = self.vector(f"ALERTS{{{selector}}}")
        if error:
            return None, error
        return bool(series), None

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Shared client + small cache (several dashboard widgets poll together)
# ---------------------------------------------------------------------------
_client_lock = threading.Lock()
_client: Optional[PrometheusClient] = None


def get_client() -> PrometheusClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = PrometheusClient()
        return _client


def set_client(client: Optional[PrometheusClient]) -> None:
    """Replace the shared client (used by tests)."""
    global _client
    with _client_lock:
        _client = client
    _cache.clear()


_cache: Dict[str, Tuple[float, Any]] = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 3.0


def _cached(key: str, producer: Callable[[], Any]) -> Any:
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    value = producer()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def validate_job(db: Session, job: str) -> str:
    """Only jobs registered as monitored resources may be queried."""
    if not _JOB_NAME.match(job or ""):
        raise MetricRequestError("Unknown monitored resource.")
    exists = (
        db.query(MonitoredResource.id)
        .filter(MonitoredResource.monitoring_identifier == job)
        .first()
    )
    if not exists:
        raise MetricRequestError("Unknown monitored resource.")
    return job


def current_metrics(job: str) -> Dict[str, Any]:
    """Latest value of every catalog metric for one job."""
    client = get_client()
    metrics = {}
    timed_out = False
    for key, definition in METRIC_CATALOG.items():
        if timed_out:
            # Prometheus is not answering: do not stack further timeouts on this request.
            sample = {"available": False, "value": None, "reason": "timeout", "sampled_at": None}
        else:
            sample = client.instant(definition["query"] % {"job": job})
            timed_out = sample.get("reason") == "timeout"
        metrics[key] = {
            "label": definition["label"],
            "unit": definition["unit"],
            "description": definition["description"],
            **sample,
        }
    return metrics


def timeseries(db: Session, job: str, metric: str, range_name: str) -> Dict[str, Any]:
    validate_job(db, job)
    definition = METRIC_CATALOG.get(metric)
    if definition is None:
        raise MetricRequestError("Unknown metric.")
    preset = RANGE_PRESETS.get(range_name)
    if preset is None:
        raise MetricRequestError("Unknown time range.")
    window, step = preset

    def produce() -> Dict[str, Any]:
        data = get_client().range(definition["query"] % {"job": job}, window, step)
        return {
            "job": job,
            "metric": metric,
            "label": definition["label"],
            "unit": definition["unit"],
            "range": range_name,
            "step_seconds": step,
            "source": "prometheus",
            "generated_at": utcnow().isoformat(),
            **data,
        }

    return _cached(f"ts:{job}:{metric}:{range_name}", produce)


def _status_from_target(job: str, targets: List[dict]) -> str:
    matching = [t for t in targets if t["job"] == job]
    if not matching:
        return "UNKNOWN"
    if all(t["health"] == "up" for t in matching):
        return "UP"
    if any(t["health"] == "down" for t in matching):
        return "DOWN"
    return "UNKNOWN"


def overview(db: Session) -> Dict[str, Any]:
    """Platform-wide monitoring snapshot for the dashboard and monitoring page."""

    def produce() -> Dict[str, Any]:
        client = get_client()
        prometheus = client.prometheus_ready()
        alertmanager = client.alertmanager_ready()
        targets = client.targets() if prometheus["available"] else {
            "available": False,
            "reason": prometheus["error"],
            "targets": [],
        }
        alerts = client.firing_alerts() if prometheus["available"] else {
            "available": False,
            "reason": prometheus["error"],
            "alerts": [],
        }
        return {
            "prometheus": prometheus,
            "alertmanager": alertmanager,
            "targets": targets,
            "alerts": alerts,
        }

    base = _cached("overview", produce)
    now = utcnow()
    resources = []
    for resource in db.query(MonitoredResource).order_by(MonitoredResource.id).all():
        job = resource.monitoring_identifier
        status = "UNKNOWN"
        metrics: Dict[str, Any] = {}
        if job and base["targets"]["available"]:
            status = _status_from_target(job, base["targets"]["targets"])
            metrics = _cached(f"metrics:{job}", lambda j=job: current_metrics(j))
            # Remember the last status actually observed (never invented).
            if resource.status != status or resource.status_checked_at is None:
                resource.status = status
            resource.status_checked_at = now
        resources.append(
            {
                "id": resource.id,
                "name": resource.name,
                "resource_type": resource.resource_type,
                "environment": resource.environment,
                "job": job,
                "description": resource.description,
                "status": status,
                "last_known_status": resource.status,
                "status_checked_at": resource.status_checked_at,
                "metrics": metrics,
            }
        )
    db.commit()
    return {
        "generated_at": now,
        "source": "prometheus",
        "scrape_interval_seconds": settings.PROMETHEUS_SCRAPE_INTERVAL_SECONDS,
        "prometheus": base["prometheus"],
        "alertmanager": base["alertmanager"],
        "targets": base["targets"],
        "alerts": base["alerts"],
        "resources": resources,
    }


def metric_catalog() -> List[Dict[str, str]]:
    return [
        {"key": key, "label": d["label"], "unit": d["unit"], "description": d["description"]}
        for key, d in METRIC_CATALOG.items()
    ]
