# System Architecture

## Components
VigilOps runs as a set of Docker Compose services on one private network:
- web: Caddy reverse proxy that serves the React frontend and forwards /api to the backend. It is the only public entry point.
- backend: FastAPI application (REST API, incident engine, scanner, VigilAI). Runs database migrations on start.
- worker: the restricted remediation worker. It has no network port and polls the database for approved, queued work.
- postgres: PostgreSQL 16, the operational database (users, incidents, findings, scans, remediation, audit).
- prometheus: scrapes metrics and evaluates alert rules.
- alertmanager: groups alerts and sends them to the backend webhook.
- test-app: the monitored demonstration application, OrbitCrate, a demonstration storefront. Its page is public at /orbitcrate/; its control endpoints, /metrics and /health are not routed.

## Request flow
Browser -> Caddy (web) -> React frontend and /api -> FastAPI backend -> PostgreSQL. The backend reads monitoring data from Prometheus over the internal network. The browser never talks to Prometheus, Alertmanager, PostgreSQL or the worker directly.

## Alert flow
Demo application -> Prometheus scrape -> alert rules -> Alertmanager -> protected backend webhook (/api/alerts/webhook) -> incident engine -> PostgreSQL -> dashboard.

## Remediation flow
Problem detected -> recommendation shown -> Operator requests remediation -> PENDING_APPROVAL -> Administrator approves or rejects -> Administrator dispatches (QUEUED) -> restricted worker executes the allowlisted action -> verification -> SUCCEEDED or FAILED -> audit record.

## Design principles
A modular monolith instead of many microservices; business logic in services, separate from API routing; PostgreSQL for operational records and Prometheus for time series; privileged remediation isolated in the worker; the Gemini API is called only from the backend; role-based access control is enforced by the backend on every sensitive operation.

## Why the worker is separate
The worker is the only component that can write to the scan workspace and the only one that holds the demo application's recovery token. The backend container mounts the workspace read-only. A bug or compromise of the public API therefore cannot directly change configuration files or trigger recovery: it can only queue a request, which the worker executes only if it was approved by an Administrator.
