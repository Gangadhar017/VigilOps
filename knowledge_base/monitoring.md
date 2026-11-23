# Monitoring and Observability

## What is monitored
VigilOps monitors two resources through Prometheus: the demonstration application (job demo-app) and the VigilOps backend itself (job vigilops-backend). For each it shows availability, HTTP request rate, 4xx and 5xx error rate, p95 response latency, CPU usage, resident memory and uptime.

## Where the numbers come from
Every value on the Monitoring page is the result of a Prometheus query made by the backend. CPU and memory come from the process's own counters (process_cpu_seconds_total and process_resident_memory_bytes). Request metrics come from http_requests_total and the http_request_duration_seconds histogram, recorded by middleware in each service. If Prometheus has no sample, the card shows "Unavailable" with the reason; values are never estimated or invented.

## Health endpoints
Each service exposes separate liveness and readiness probes:
- GET /health/live: the process is running. It does not check dependencies.
- GET /health/ready: the service can do useful work. For the backend this means the database is reachable and migrations are applied; it returns HTTP 503 otherwise.
- GET /metrics: Prometheus exposition format. It is reachable only on the internal network.

## Prometheus configuration
The configuration is version controlled in monitoring/prometheus.yml. Prometheus scrapes test-app:8001 and backend:8000 every 5 seconds and evaluates the rules in monitoring/alert_rules.yml every 5 seconds. In the local setup the Prometheus UI is published on http://localhost:9090 for demonstrations, bound to the local machine only.

## Scrape targets and stale data
The Monitoring page lists each scrape target with its health (up or down), the time of the last scrape and the last scrape error. If a target has not been scraped recently it is marked "stale", which means its displayed health may be outdated.

## Why Prometheus is not receiving metrics
Check these in order: 1) Monitoring page: is Prometheus itself shown as available? If not, run docker compose ps prometheus. 2) Scrape target list: a target that is down shows the scrape error. "connection refused" means the container is not running; "HTTP status 503" means the application is in a failed state. 3) The service's /metrics endpoint must be reachable from the Prometheus container on the internal network. 4) After fixing the cause, the next scrape (within 5 seconds) updates the status.

## Time ranges and charts
Charts support 5 minute, 15 minute, 1 hour and 6 hour ranges. Only metrics from the built-in catalog can be requested; the API does not accept arbitrary PromQL from the browser.
