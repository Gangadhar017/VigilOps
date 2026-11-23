"""Prometheus instrumentation for the VigilOps backend itself."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled, by method, route template and status code.",
    ["method", "path", "status"],
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds, by method and route template.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
ALERT_WEBHOOK_EVENTS = Counter(
    "vigilops_alert_webhook_events_total",
    "Alertmanager webhook alerts processed, by resulting action.",
    ["result"],
)
ALERT_WEBHOOK_REJECTED = Counter(
    "vigilops_alert_webhook_rejected_total",
    "Alertmanager webhook calls rejected, by reason.",
    ["reason"],
)
SECURITY_SCANS = Counter(
    "vigilops_security_scans_total", "Security scans executed, by status.", ["status"]
)
REMEDIATION_TRANSITIONS = Counter(
    "vigilops_remediation_transitions_total",
    "Remediation request state transitions, by new status.",
    ["status"],
)
ASSISTANT_REQUESTS = Counter(
    "vigilops_assistant_requests_total",
    "VigilAI requests, by outcome (ai, fallback, refusal, rate_limited).",
    ["outcome"],
)
ASSISTANT_PROVIDER_LATENCY = Histogram(
    "vigilops_assistant_provider_seconds",
    "Latency of calls to the AI provider.",
    buckets=(0.25, 0.5, 1, 2, 4, 8, 15, 30),
)
OPEN_INCIDENTS = Gauge("vigilops_open_incidents", "Incidents that are not resolved or closed.")
OPEN_FINDINGS = Gauge("vigilops_open_findings", "Security findings in OPEN state.")
