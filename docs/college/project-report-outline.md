# VigilOps: Secure Cloud Operations - Project Report Outline

B.Tech Computer Science and Engineering (Cloud Computing and Virtualization) - Major Project

> **To be filled in by the team before submission**
>
> | Field | Value |
> |---|---|
> | Institution and department | ______________________________ |
> | Academic year / semester | ______________________________ |
> | Project guide | ______________________________ |
> | Member 1 (name, roll number) | ______________________________ |
> | Member 2 (name, roll number) | ______________________________ |
> | Member 3 (name, roll number) | ______________________________ |
> | Member 4 (name, roll number) | ______________________________ |
> | Member 5 (name, roll number) | ______________________________ |

## How to use this outline

This file is a report skeleton with real content for each of the ten chapters. Every technical statement in it was written from the code in this repository; expand the paragraphs, add screenshots and figures, and keep the statements consistent with the code.

Rules the team must follow while expanding it:

1. **No invented numbers.** Timings, test counts, percentages and any other measured value are taken only from [`../evaluation.md`](../evaluation.md) and [`../verification-report.md`](../verification-report.md), which are produced from real runs. Where this outline says "value: see evaluation", copy the value from there together with the date and machine it was measured on.
2. **No unverified citations.** Cite only sources that a team member has opened and read (official documentation of Prometheus, Alertmanager, FastAPI, React, PostgreSQL, Docker, Caddy, the Google Gen AI SDK, and any textbook or paper the guide approves). Do not copy statistics from memory.
3. **Do not reuse the prototype's figures.** The evaluation figures and report material written for the earlier CloudShield prototype came from a system whose telemetry and verification were simulated. Those documents have been removed from the repository, and none of their numbers may appear in this report.
4. **State what was not verified.** Live Google Gemini generation was verified with a real API key on 2026-11-23 (`scripts/verify_gemini_live.py`, `docs/evidence/gemini-live.json`), but real quota exhaustion (HTTP 429 from the provider) was never observed; that path and provider timeouts are covered only by automated tests with a stubbed SDK client. Answer quality was checked with keyword grounding checks and by reading the replies of a small question set with one model, not by a systematic human evaluation. Deployment with public HTTPS on a real domain was not tested.

Suggested front matter (college format): title page, certificate, declaration, acknowledgement, abstract, table of contents, list of figures, list of tables, list of abbreviations.

### Abstract (draft, about 200 words)

Operating a cloud application requires several activities that are usually carried out with separate tools: monitoring, alert handling, security configuration review, corrective action and record keeping. VigilOps: Secure Cloud Operations is a centralized, local-first web platform that brings these activities into one application. Prometheus scrapes real metrics from a monitored demonstration application and from the platform's own backend; Alertmanager delivers alerts to a protected webhook, from which an incident engine creates deduplicated incidents. A deterministic Python scanner evaluates local YAML configuration files against five rules (SEC-001 to SEC-005) and maintains a finding lifecycle. Corrective action follows a controlled workflow: an Operator requests one of two allowlisted actions, an Administrator approves and dispatches it, a restricted worker executes it, and the result is accepted only after independent verification. Every important event is written to an append-only audit trail. A read-only assistant, VigilAI, answers platform questions using BM25 retrieval over a Markdown knowledge base and authorised live data, with Google Gemini as an optional generator and a documentation fallback. The system is built with React, FastAPI and PostgreSQL and is deployed with Docker Compose. It needs no cloud account or paid service. Measured results are reported in the evaluation chapter.

---

## Chapter 1 - Introduction

### 1.1 Background

- Applications deployed on cloud infrastructure must be observed continuously (availability, request rate, error rate, latency, CPU, memory), and their configuration must be reviewed for security weaknesses such as public storage, missing encryption, wildcard permissions, open network ports and privileged containers.
- In practice these tasks are spread across tools: a metrics system, an alert router, a configuration scanner, a ticketing or on-call tool and, increasingly, an AI assistant. The operator has to move between them and manually connect "what was detected" with "what was done about it" and "whether it worked".
- Automation of corrective actions shortens response time but is risky if an automated component can run arbitrary commands, or if an action is reported as successful merely because it was executed.

### 1.2 Overview of the project

VigilOps is one web application with one login, one navigation menu, one backend and one database. Its modules are:

| Module | What it does in this implementation |
|---|---|
| Monitoring | Shows live Prometheus telemetry for two monitored resources (the demonstration application, job `demo-app`, and the backend, job `vigilops-backend`): availability, request rate, 4xx and 5xx error rate, p95 latency, CPU, resident memory and uptime; lists scrape targets and active alert rules. |
| Incident management | Creates incidents from Alertmanager notifications, deduplicates repeated notifications by alert fingerprint, records a timeline and enforces a five-state lifecycle. |
| Security scanning | Deterministic Python scanner for YAML files in the `vigilops/v1` schema, five rules SEC-001 to SEC-005, scan history and a four-state finding lifecycle. |
| Controlled remediation | Request, approval, dispatch, execution by a restricted worker, verification. Two automated actions: ACTION-001 (recover the demonstration application) and ACTION-002 (correct public storage configuration). |
| Audit logging | Append-only record of sign-ins, incident changes, scans, findings, remediation steps, administration and refused actions. |
| Access control | Two roles, Administrator and Operator, enforced by the backend through a permission matrix. |
| VigilAI | Read-only assistant in a floating chat widget; answers only platform questions from the knowledge base and authorised live data; Google Gemini is optional; a documentation fallback is always available. |

### 1.3 Nature of the system: local-first

The whole platform runs on one machine with `docker compose up --build -d`. No AWS account, paid service, Ollama installation or model training is required. The scanner evaluates local YAML files that describe sample cloud resources; it does not assess a live cloud account. This is a deliberate scope decision and is listed as a limitation in Chapter 10.

### 1.4 Origin of the project

VigilOps was produced by auditing and upgrading an earlier prototype named CloudShield. The audit ([`../phase-0-audit.md`](../phase-0-audit.md)) read every tracked file and recorded thirty gaps. The most important changes are worth one paragraph each in the report:

- The prototype generated CPU, memory and latency with random numbers and substituted default values when the application was unreachable. VigilOps measures real requests with middleware and reads all telemetry from the Prometheus HTTP API; a missing value is shown as "Unavailable".
- The prototype had no Alertmanager; alert rules were routed nowhere. VigilOps adds Alertmanager and a token-protected webhook.
- Remediation actions ran inside the API process and reported `verification_passed` when the file had merely been written. VigilOps moves execution into a separate restricted worker and verifies with a fresh scan or fresh monitoring evidence.
- Public registration accepted `"role": "admin"`. VigilOps has no self-registration; users are managed by an Administrator.
- The prototype's frontend contained hard-coded data and a fallback sign-in. The pages were rebuilt on real APIs with loading, empty and error states.

### 1.5 Organisation of the report

One sentence per chapter (2 to 10), as in the table of contents.

**Figures / tables to include**

- Context diagram: [`../diagrams/context.md`](../diagrams/context.md).
- Screenshot of the Overview page after sign-in.
- Table 1.1: modules of VigilOps (the table above).
- Table 1.2: prototype defect versus VigilOps change (five to eight rows selected from the audit).

---

## Chapter 2 - Problem Statement and Objectives

### 2.1 Problem statement

Small teams that operate cloud applications face four connected problems:

1. **Fragmented tooling.** Metrics, alerts, configuration findings, corrective actions and their history live in different systems, so the link between detection and resolution is maintained by hand.
2. **Alert noise.** An alerting system repeats notifications while a problem persists. Without deduplication each repeat can become a separate ticket, which hides the real number of problems.
3. **Unverified manual response.** A person identifies the fault, applies a fix and decides informally that it worked. There is often no recorded evidence that the condition actually cleared.
4. **Uncontrolled automation and weak accountability.** Automation that can run arbitrary commands is dangerous, and automation without an approval step and an audit trail cannot be reviewed afterwards. The same concern applies to AI assistants that are given the ability to act.

**Statement.** To design and implement a single, local-first platform that detects operational and configuration problems from real signals, turns them into deduplicated, traceable records, permits only allowlisted corrective actions under role-based approval, accepts a correction only after independent verification, records every step in an append-only audit trail, and offers a read-only assistant that explains the platform without being able to change it.

### 2.2 Objectives

| No. | Objective | Realised by | Evaluated by (Chapter 9) |
|---|---|---|---|
| O1 | Collect genuine telemetry and present it without invented values | `test-app/app.py`, `monitoring/prometheus.yml`, `backend/app/services/monitoring_service.py` | Demonstration 1, steps 2 and 4 |
| O2 | Convert alerts into incidents automatically | `monitoring/alert_rules.yml`, `monitoring/alertmanager.yml`, `POST /api/alerts/webhook`, `incident_service.py` | M1 alert-to-incident time |
| O3 | Guarantee one active incident per alert | fingerprint + partial unique index `uq_incidents_active_fingerprint` | M2 incident deduplication |
| O4 | Detect five classes of misconfiguration deterministically | `backend/app/security_scanner/`, `security-rules/policies.yaml` | M3 detection, M4 false positives |
| O5 | Allow only approved, allowlisted, verified remediation | `remediation_service.py`, `remediation_catalog.py`, `backend/app/workers/` | M5, M6, M7 |
| O6 | Enforce role-based access on the server | `backend/app/core/permissions.py` | M10 RBAC enforcement |
| O7 | Keep a complete, append-only audit trail | `audit_service.py`, trigger in `alembic/versions/0001_initial_schema.py` | Audit checks in the demonstrations |
| O8 | Provide a read-only, platform-only assistant with graceful degradation | `backend/app/assistant/`, `knowledge_base/` | M8, M9 |
| O9 | Deploy the whole system reproducibly with one command | `compose.yaml`, `compose.prod.yaml`, `reverse-proxy/Caddyfile` | `scripts/verify_stack.sh` |

### 2.3 Scope

In scope: one monitored demonstration application, five alert rules, five scanner rules, two automated remediation actions, two roles, one assistant, deployment with Docker Compose.

Out of scope (state these plainly): live cloud account assessment, AWS integration, more than two automated actions, starting or stopping containers, horizontal scaling of the backend, multi-factor authentication, notification channels other than the platform itself.

### 2.4 Assumptions

- The platform is operated on a trusted host; only the web entry point is exposed to users.
- Configuration files to be scanned are placed in the scan workspace by an authorised person.
- The demonstration application's traffic comes from its built-in synthetic load generator; the measurements of that traffic are real.

**Figures / tables to include**

- Table 2.1: objective - module - metric traceability (the table above).
- Figure 2.1: the closed loop "detect, record, request, approve, execute, verify, audit" drawn as a cycle.

---

## Chapter 3 - Existing Systems and Identified Gap

Describe each category in general terms and cite its official documentation. Do not quote market statistics.

### 3.1 Categories of existing systems

| Category | Well-known examples | What the category provides (general) | What it does not provide on its own |
|---|---|---|---|
| Metrics collection and alert rules | Prometheus | Pull-based scraping of metrics, a time-series database, the PromQL query language and alert rule evaluation | Incident records, approval workflows, corrective action |
| Alert routing | Alertmanager | Grouping, repetition control, silencing and routing of alerts to receivers such as e-mail, chat or webhooks | Persistent incident lifecycle, evidence of resolution |
| Dashboards | Grafana | Visualisation of time series from several data sources, with its own alerting features | Security configuration review, controlled remediation |
| Cloud-provider configuration assessment | AWS Config | Recording of resource configurations inside an AWS account and evaluation against rules | Works only inside that provider's account; not available without a cloud account |
| Infrastructure-as-code scanners | Checkov, tfsec | Static analysis of infrastructure definitions for misconfigurations before deployment, with large rule libraries | A finding lifecycle tied to incidents, approval and verification inside one operations console |
| Incident response and on-call | PagerDuty | Event intake, on-call schedules, escalation and notification | Metrics, configuration scanning, execution of the fix |
| Log analytics and SIEM | Splunk | Search and correlation over machine data and logs | Lightweight local deployment for a student project; controlled remediation |
| General AI chat assistants | (various) | Natural-language explanations | Grounding in this platform's live records; guaranteed read-only behaviour |

Write one paragraph per row. For each product, check the current feature list in its official documentation before making a claim about what it lacks; several of these products have optional extensions that overlap with other rows.

### 3.2 The earlier prototype (CloudShield)

The prototype attempted the same integration but, as the audit shows, several parts were simulated or unsafe: random telemetry, no Alertmanager, remediation executed in the API process, verification that only checked that a file was written, open registration, and a frontend with hard-coded data. Its automated tests passed because they did not start Prometheus, the demonstration application, a worker or the Docker stack. This is itself a useful finding for the report: passing tests do not prove a working system unless the tests exercise the real integration.

### 3.3 Identified gap

1. The established tools are strong inside their own category, but the chain from detection to verified correction to audit record crosses several of them.
2. Corrective automation is commonly either absent (humans act outside the tool) or unrestricted (scripts with broad privileges). A middle path - a small allowlist, mandatory approval by a second role, an isolated executor and evidence-based success - is not provided by the monitoring or scanning tools themselves.
3. AI assistance is commonly general-purpose. An assistant embedded in an operations tool must be restricted to the platform's subject, must respect the caller's role, must not be able to act, and must keep working (in a reduced form) when the model provider is unavailable.

### 3.4 Position of VigilOps

VigilOps does not replace these tools. It **uses** Prometheus and Alertmanager unchanged and adds the incident, remediation, audit and assistant layers on top. Its scanner is deliberately small (five rules, its own YAML schema) and must not be presented as an alternative to Checkov or tfsec; its contribution is the lifecycle around a finding (stable identity, automatic resolution and reopening, approval-gated correction, verification by re-scan).

**Figures / tables to include**

- Table 3.1: capability comparison (the table in 3.1, extended with a VigilOps column: monitoring - uses Prometheus; alert routing - uses Alertmanager; incident lifecycle - yes; configuration scanning - five rules on local YAML; approval-gated remediation - two actions; verification - yes; audit - yes; assistant - read-only).
- Table 3.2: gaps found in the prototype (selected rows of the audit's gap matrix).

---

## Chapter 4 - Requirements Analysis

### 4.1 Actors

| Actor | Kind | Description |
|---|---|---|
| Administrator | Human user (role `admin`) | Everything an Operator can do, plus approval, dispatch, closing incidents, accepted risk, user management, settings and demo controls |
| Operator | Human user (role `operator`) | Views data, works on incidents, runs scans, requests remediation, uses VigilAI |
| Alertmanager | Service identity | Delivers firing and resolved alerts to the webhook with a shared bearer token |
| Remediation worker | Service identity (`remediation-worker-1`) | Executes approved, dispatched requests and verifies them |
| Prometheus | External system | Scrapes metrics, evaluates alert rules, answers the backend's queries |
| Google Gemini | Optional external system | Generates assistant answers when an API key is configured |

### 4.2 Functional requirements

Group the requirements by module. Each row below is implemented; the "where" column lets an examiner trace it to code.

**Authentication and users**

| ID | Requirement | Where |
|---|---|---|
| FR-01 | Sign in with e-mail and password; receive a signed JWT access token | `POST /api/auth/login`, `core/security.py` |
| FR-02 | Sign out revokes the token on the server | `POST /api/auth/logout`, table `revoked_tokens` |
| FR-03 | Password policy: at least 10 characters, upper and lower case and a digit, at most 72 bytes | `validate_password_strength` |
| FR-04 | Failed sign-ins are rate limited and audited; the error message does not reveal whether the e-mail exists | `api/auth.py` |
| FR-05 | No public registration; an Administrator creates users, changes roles, deactivates or reactivates accounts and resets passwords | `api/users.py` |
| FR-06 | The last active Administrator cannot be demoted or deactivated | `api/users.py` |
| FR-07 | Changing a password or role, or deactivating a user, invalidates that user's existing tokens | `token_version` column |

**Monitoring and alerting**

| ID | Requirement | Where |
|---|---|---|
| FR-08 | Show the state of Prometheus, Alertmanager, scrape targets and active alert rules | `GET /api/monitoring/overview` |
| FR-09 | Show eight catalog metrics per monitored resource; show "Unavailable" with a reason when no sample exists | `METRIC_CATALOG` in `monitoring_service.py` |
| FR-10 | Show time series for the ranges 5 minutes, 15 minutes, 1 hour and 6 hours; accept only catalog metric keys and registered jobs, never raw PromQL | `GET /api/monitoring/timeseries` |
| FR-11 | Accept Alertmanager webhooks only with the shared token; reject malformed payloads | `POST /api/alerts/webhook` |

**Incidents**

| ID | Requirement | Where |
|---|---|---|
| FR-12 | A firing alert opens an incident with severity, affected resource, fingerprint and labels | `incident_service._handle_firing` |
| FR-13 | Repeated notifications update the same incident (notification counter, last occurrence) | same |
| FR-14 | A resolved alert resolves the incident with monitoring evidence | `_handle_resolved` |
| FR-15 | The same alert firing again within the reopen window reopens the resolved incident; closed incidents are never reopened automatically | setting `incidents.reopen_window_minutes` |
| FR-16 | Lifecycle OPEN, ACKNOWLEDGED, IN_PROGRESS, RESOLVED, CLOSED with validated transitions | `TRANSITIONS` |
| FR-17 | Manual resolution requires written evidence and is refused while Prometheus still reports the alert as firing; when Prometheus cannot be queried, an Administrator may override with a recorded reason | `transition_incident` |
| FR-18 | Only an Administrator can close or reopen an incident | permission `incidents:close` |
| FR-19 | Incidents opened during a controlled demo fault are labelled "Simulated fault" | `is_simulated`, `simulation_note` |

**Security scanning**

| ID | Requirement | Where |
|---|---|---|
| FR-20 | Evaluate rules SEC-001 to SEC-005 on YAML files in the scan workspace | `security_scanner/rules.py`, `engine.py` |
| FR-21 | Scan one named target or every file; keep a scan history | `POST /api/security/scans`, table `security_scans` |
| FR-22 | Identify each finding by a stable key so repeated scans do not create duplicates | `stable_finding_key` |
| FR-23 | Finding states OPEN, REMEDIATION_PENDING, RESOLVED, ACCEPTED_RISK; a finding is resolved only by a scan and reopens if the violation returns | `scan_service._apply_file_results` |
| FR-24 | An Administrator may record or revoke an accepted risk with a justification | `accept-risk`, `revoke-risk-acceptance` |
| FR-25 | Reject unsafe input: path traversal, non-YAML names, oversized files, anchors and aliases, unsupported schema | `resolve_target`, `parse_yaml_document` |

**Remediation**

| ID | Requirement | Where |
|---|---|---|
| FR-26 | Only allowlisted action codes can be requested; a justification is required | `remediation_catalog.py`, `create_request` |
| FR-27 | At most one in-flight request per incident or finding | partial unique indexes |
| FR-28 | Only an Administrator can approve, reject, dispatch or retry; by default not their own request | `approve`, setting `remediation.allow_self_approval` |
| FR-29 | Execution happens only in the restricted worker, only for requests that are QUEUED and have a recorded approval | `remediation_worker.claim_next` |
| FR-30 | A request succeeds only if verification passes; otherwise it is FAILED and the source stays open | `workers/verification.py` |
| FR-31 | A failed request can be retried up to the attempt limit | `retry`, `max_attempts` |

**Audit, assistant, settings**

| ID | Requirement | Where |
|---|---|---|
| FR-32 | Record actor, action, entity, outcome, metadata, correlation ID and time for every important event | `record_audit` |
| FR-33 | Search, filter, sort and page audit events; Operators see operational events and their own events, Administrators see all | `list_audit_events`, `_apply_visibility` |
| FR-34 | Audit history cannot be changed through the application or by SQL UPDATE/DELETE in PostgreSQL | no API; trigger `trg_audit_events_immutable` |
| FR-35 | VigilAI answers only platform questions, read-only, using retrieved documentation and authorised live data | `assistant/service.py` |
| FR-36 | VigilAI falls back to documentation answers when the provider is missing or fails | `compose_fallback` |
| FR-37 | Administrators can change three runtime settings and switch the assistant off | `settings_service.py` |
| FR-38 | Demo controls (fault injection, sample reset) exist only when enabled; in production mode they are off unless the explicit hosted-demonstration opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION` is also set (default off) | `demo_controls_active` |

### 4.3 Non-functional requirements

| Area | Requirement as implemented |
|---|---|
| Security | Secrets come only from the environment; production mode refuses placeholder values; bcrypt password hashes; server-side permission checks; security headers and Content-Security-Policy at the reverse proxy; credentials redacted from logs and audit metadata |
| Data integrity | CHECK constraints on every status and severity column; partial unique indexes for deduplication; a state change and its audit record are committed in the same transaction |
| Reliability | The worker marks executions interrupted by a restart as FAILED; the assistant never blocks the rest of the platform; liveness and readiness probes are separate |
| Observability | The backend exposes its own Prometheus metrics and structured JSON logs with a request ID |
| Usability | Consistent loading, empty and error states; light and dark theme; responsive layout; accessible dialogs |
| Portability | The complete stack is defined in `compose.yaml`; no host dependencies other than Docker |
| Maintainability | Business logic in `services/`, routing in `api/`; one permission matrix; rule metadata in a YAML catalog; automated tests and a CI workflow |
| Performance | Not load tested. State this honestly; the only timing values are those in [`../evaluation.md`](../evaluation.md) |

### 4.4 Hardware and software requirements

**Software (from the repository)**

| Layer | Technology and version source |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS 3.4, React Router 6, Axios, Recharts, lucide-react (`frontend/package.json`) |
| Frontend tests | Vitest, Testing Library, jsdom |
| Backend | Python 3.11 (image `python:3.11-slim`), FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, python-jose, bcrypt, httpx, PyYAML, prometheus-client, google-genai (`backend/requirements.txt`) |
| Backend tests | pytest, ruff (`backend/requirements-dev.txt`) |
| Database | PostgreSQL 16 (image `postgres:16-alpine`) |
| Monitoring | Prometheus v2.51.0, Alertmanager v0.27.0 |
| Reverse proxy | Caddy 2 (image `caddy:2-alpine`) |
| Deployment | Docker with the Compose plugin (Docker Desktop with WSL2 on Windows) |
| Optional | A Google AI Studio API key for live Gemini answers |

**Hardware.** Any development machine that can run Docker with seven long-running containers. In `compose.yaml` the demonstration application is limited to 512 MB of memory and one CPU. No cloud resources are needed. Internet access is needed only to pull images, install packages during the build, and for optional Gemini calls. A minimum specification was not benchmarked: record the processor, memory and operating system of the machine actually used for the evaluation in [`../evaluation.md`](../evaluation.md) and quote that.

### 4.5 Use cases

| ID | Use case | Administrator | Operator |
|---|---|---|---|
| UC-01 | Sign in, sign out, change own password | Yes | Yes |
| UC-02 | View the Overview page | Yes | Yes |
| UC-03 | View monitoring data, targets and active alerts | Yes | Yes |
| UC-04 | View and search incidents; open an incident | Yes | Yes |
| UC-05 | Acknowledge, start work, comment | Yes | Yes |
| UC-06 | Resolve an incident with evidence | Yes (may override when monitoring is unavailable) | Yes |
| UC-07 | Close or reopen an incident | Yes | No |
| UC-08 | Run a security scan; view findings, rules, scan history and configuration files | Yes | Yes |
| UC-09 | Mark a finding as accepted risk; revoke it | Yes | No |
| UC-10 | Request remediation for an incident or finding | Yes | Yes |
| UC-11 | Approve or reject a remediation request | Yes (not own request by default) | No |
| UC-12 | Dispatch (execute) or retry a request | Yes | No |
| UC-13 | Cancel a request before dispatch | Yes | Own requests only |
| UC-14 | View audit events | All events | Operational events and own events |
| UC-15 | Ask VigilAI | Yes | Yes |
| UC-16 | Manage users | Yes | No |
| UC-17 | Change runtime settings | Yes | View only |
| UC-18 | Use demo controls | Yes | No |

Write three or four use cases in full (actor, precondition, main flow, alternative flows, postcondition). Recommended: UC-06, UC-10 to UC-12 as one workflow, UC-08, UC-15. Example for the workflow:

- **Precondition:** an OPEN SEC-001 finding exists in a file on the remediation allowlist.
- **Main flow:** the Operator opens the finding and submits ACTION-002 with a justification (status PENDING_APPROVAL, finding REMEDIATION_PENDING); an Administrator approves (APPROVED) and dispatches (QUEUED); the worker claims the request (RUNNING), edits the file, re-scans (VERIFYING) and the request becomes SUCCEEDED; the scan sets the finding to RESOLVED.
- **Alternative flows:** the Operator tries to approve - HTTP 403, no state change, audited; the Administrator rejects with a reason - REJECTED, finding back to OPEN; verification fails - FAILED, finding back to OPEN, retry possible up to the limit.

### 4.6 Permission matrix

Reproduce the matrix from `backend/app/core/permissions.py` (also visible in the application under Settings, tab Permissions).

| Permission | Administrator | Operator |
|---|---|---|
| `dashboard:view`, `monitoring:view`, `incidents:view`, `findings:view`, `remediation:view` | Yes | Yes |
| `incidents:update` (acknowledge, start work, resolve, comment) | Yes | Yes |
| `incidents:close` (close and reopen) | Yes | No |
| `scans:run` | Yes | Yes |
| `findings:accept_risk` | Yes | No |
| `remediation:request` | Yes | Yes |
| `remediation:approve` (approve, reject) | Yes | No |
| `remediation:execute` (dispatch, retry) | Yes | No |
| `remediation:cancel` | Yes | Own requests |
| `audit:view` | Yes | Operational events |
| `audit:view_all` | Yes | No |
| `assistant:use` | Yes | Yes |
| `users:manage`, `settings:manage`, `demo:control` | Yes | No |
| `settings:view` | Yes | Yes |

**Figures / tables to include**

- Use-case diagram: [`../diagrams/use-case.md`](../diagrams/use-case.md).
- Tables 4.1 to 4.6 as above.
- Screenshot: Settings, tab Permissions.

---

## Chapter 5 - System Architecture and Design

### 5.1 Architectural style

A modular monolith plus one restricted worker. The backend is a single FastAPI application whose modules (authentication, monitoring, incidents, scanning, remediation workflow, audit, assistant) share one database session and one permission system. The only code that changes the outside world - editing a configuration file or calling the recovery endpoint - runs in a second process, the remediation worker, built from the same image but started with a different command and different privileges.

### 5.2 Services

| Compose service | Image | Role | Exposure and privileges |
|---|---|---|---|
| `web` | `caddy:2-alpine` with the React build | Serves the frontend; reverse-proxies `/api/*` to the backend | The only user-facing port: 8080 locally, bound to 127.0.0.1 by default (`VIGILOPS_BIND_ADDRESS`); 80 and 443 in the production overlay |
| `backend` | `python:3.11-slim` | REST API, incident engine, scanner, VigilAI; runs `alembic upgrade head` on start | Port 8000 bound to 127.0.0.1 in the local stack only; scan workspace mounted read-only; non-root user; read-only root filesystem and no Linux capabilities |
| `worker` | same image | `python -m app.workers.remediation_worker` | No port; read-only root filesystem; all Linux capabilities dropped; `no-new-privileges`; the only writer of the scan workspace; holds the recovery token |
| `postgres` | `postgres:16-alpine` | Operational database | Internal network only |
| `prometheus` | `prom/prometheus:v2.51.0` | Scraping and alert rules | UI on 127.0.0.1:9090 locally |
| `alertmanager` | `prom/alertmanager:v0.27.0` | Routing alerts to the webhook | UI on 127.0.0.1:9093 locally; webhook token delivered as a Docker secret file |
| `test-app` | `python:3.11-slim` | Monitored demonstration application ("order service") | Internal network only; read-only root filesystem; memory and CPU limits |
| `workspace-init` | backend image | One-shot job that gives the scan workspace volume to the unprivileged user | Runs once with no network |

### 5.3 Main flows

- **Request flow:** browser - Caddy - React application and `/api` - FastAPI - PostgreSQL. The backend reads monitoring data from Prometheus over the internal network. The browser never contacts Prometheus, Alertmanager, PostgreSQL or the worker.
- **Alert flow:** demonstration application - Prometheus scrape - alert rule - Alertmanager - `POST /api/alerts/webhook` - incident engine - PostgreSQL - user interface.
- **Remediation flow:** request (PENDING_APPROVAL) - approve (APPROVED) - dispatch (QUEUED) - worker claims (RUNNING) - action handler - verification (VERIFYING) - SUCCEEDED or FAILED - audit record.
- **Assistant flow:** message - rate limit - scope classification - BM25 retrieval - read-only live-data functions - Gemini if configured - response validation - reply; on any provider problem the retrieved documentation and live data are returned directly.

### 5.4 Security design (trust boundaries)

1. **Single entry point.** Caddy routes only `/api/*` to the backend. The backend's `/metrics`, `/docs` and `/health/*` paths, Prometheus, Alertmanager and PostgreSQL are not reachable through it (`scripts/verify_stack.sh` checks this).
2. **Split privileges between API and worker.** The API container can read the scan workspace but cannot write it. The worker can write it but has no network port. The worker is not given `SECRET_KEY` or `ALERT_WEBHOOK_TOKEN` (`PROCESS_ROLE=worker`), and the API is not given the recovery token.
3. **Separate tokens for separate purposes.** `ALERT_WEBHOOK_TOKEN` (Alertmanager to backend), `DEMO_APP_CONTROL_TOKEN` (backend to demonstration application, fault injection) and `DEMO_APP_RECOVERY_TOKEN` (worker to demonstration application, recovery).
4. **No arbitrary execution.** A remediation request carries only an action code; parameters for the handler are built from database records.
5. **Assistant isolation.** The model is called only from the backend, receives a minimised context, cannot call functions, and its output is validated.

### 5.5 Design decisions and their reasons

| Decision | Reason |
|---|---|
| Telemetry is read from Prometheus on demand; there is no metrics table | One source of truth for time series; no stale copies; a missing value is visible as missing |
| The remediation queue is a database table, not a message broker | The request, its state and its audit trail are in one transactional store; row locking gives safe claiming without another service |
| Approval and dispatch are two separate Administrator steps | Approval records a decision; nothing changes until an explicit dispatch |
| Runbook text is static, version-controlled content (`services/recommendations.py`) | Guidance shown next to an incident is deterministic and reviewable, not generated |
| BM25 keyword retrieval instead of a vector database | The corpus is small, queries contain exact domain terms such as SEC-001, ranking is deterministic and explainable, and no extra service is operated |
| The assistant's live-data functions are selected by keyword routing, not by the model | The model cannot choose or parameterise a function; all functions are read-only and permission-checked |
| The access token is kept in `sessionStorage`, not a cookie | No cross-site request forgery surface; the token disappears when the tab closes |
| A single Uvicorn worker process | The in-process rate limiters and caches assume one process (documented limitation) |

### 5.6 Frontend design

- Routes (`frontend/src/App.jsx`): `/login`, `/` (Overview), `/monitoring`, `/incidents`, `/incidents/:id`, `/findings`, `/findings/:id`, `/remediation`, `/remediation/:id`, `/audit`, `/help`, `/settings`. All routes except `/login` are wrapped in `RequireAuth`.
- Shared layout (`layouts/AppLayout.jsx`): sidebar, header (environment tag, "Demo controls enabled" badge, role badge, theme toggle) and the floating VigilAI widget on every page.
- `context/AuthContext.jsx` holds the user and a `can(permission)` helper used only to hide or disable controls; the backend enforces every permission again.
- `hooks/useApi.js` provides loading, error and polling behaviour; polling pauses while the browser tab is hidden.

### 5.7 Deployment design

- **Local:** `compose.yaml`. Tool ports (API documentation, Prometheus, Alertmanager) are bound to 127.0.0.1.
- **Production overlay:** `compose.prod.yaml` sets `ENVIRONMENT=production`, forces demo controls off, removes all published ports except 80 and 443 on `web`, and gives Caddy a domain name so that it obtains a TLS certificate automatically. **This overlay was validated as configuration but not deployed on a real domain; say so.**
- **Free hosting (second option):** `render.yaml` (Render Blueprint: one free web service running `deploy/render/Dockerfile` - API, worker, demo application, Prometheus and Alertmanager as separate processes in one container, each under its own user where the host lets the container switch users, supervised by `deploy/render/launcher.py` - plus one free PostgreSQL) and `frontend/vercel.json` (frontend on Vercel, `/api/*` proxied to the Render service). Described in [`../deployment-render-vercel.md`](../deployment-render-vercel.md). The Compose stack remains the reference deployment.

**Figures / tables to include** (reference the Mermaid diagrams by file name)

- [`../diagrams/system-architecture.md`](../diagrams/system-architecture.md) - component view.
- [`../diagrams/context.md`](../diagrams/context.md) - context diagram.
- [`../diagrams/data-flow.md`](../diagrams/data-flow.md) - data-flow diagram.
- [`../diagrams/incident-lifecycle.md`](../diagrams/incident-lifecycle.md) - incident state diagram.
- [`../diagrams/security-scanning-flow.md`](../diagrams/security-scanning-flow.md) - scan and finding lifecycle.
- [`../diagrams/remediation-sequence.md`](../diagrams/remediation-sequence.md) - sequence diagram of a remediation request.
- [`../diagrams/vigilai-architecture.md`](../diagrams/vigilai-architecture.md) - assistant pipeline.
- [`../diagrams/deployment.md`](../diagrams/deployment.md) - deployment diagram.
- Table 5.1 (services) and Table 5.2 (design decisions).
- Further detail: [`../architecture.md`](../architecture.md), [`../security.md`](../security.md).

---

## Chapter 6 - Database Design

### 6.1 Overview

The operational database is PostgreSQL 16, accessed through SQLAlchemy 2 models in `backend/app/models/models.py`. The schema is created by the Alembic migration `backend/alembic/versions/0001_initial_schema.py`, which the backend applies on start. There are thirteen tables. Time series are not stored here (they stay in Prometheus), and neither are chat messages (kept only in the browser for the session).

Conventions: every timestamp is timezone-aware UTC (`UTCDateTime`); status and severity columns hold upper-case strings that are also enforced by CHECK constraints; deduplication keys are enforced by the database, not only by application code.

### 6.2 Tables

| Table | Primary key | Purpose | Important columns |
|---|---|---|---|
| `users` | `id` | Accounts | `email` (unique), `password_hash`, `role`, `is_active`, `token_version`, `last_login_at` |
| `revoked_tokens` | `jti` | Tokens revoked by sign-out | `user_id`, `expires_at` |
| `monitored_resources` | `id` | Resources shown on the Monitoring page | `name` (unique), `resource_type`, `monitoring_identifier` (unique; the Prometheus job), `status` |
| `incidents` | `id` | Incidents created from alerts | `alert_name`, `alert_fingerprint`, `severity`, `status`, `resource_id`, `labels`, `annotations`, `action_code`, `is_simulated`, `alert_active`, `occurrence_count`, `detected_at`, `last_occurrence_at`, `resolved_at`, `resolution_summary` |
| `incident_events` | `id` | Incident timeline | `incident_id`, `actor_id`, `actor_label`, `event_type`, `previous_state`, `new_state`, `details`, `metadata` |
| `security_scans` | `id` | Scan history | `requested_by`, `trigger` (MANUAL, REMEDIATION_VERIFICATION, DEMO_RESET), `target`, `status`, `result_summary`, `error` |
| `security_findings` | `id` | Findings | `stable_finding_key` (unique), `rule_id`, `severity`, `target_file`, `resource_type`, `resource_name`, `evidence`, `status`, `detection_count`, `first_detected_at`, `last_seen_at`, `resolved_at`, accepted-risk columns |
| `remediation_requests` | `id` | Remediation workflow | `correlation_id`, `source_type`, `incident_id`, `finding_id`, `action_code`, `target`, `requested_by`, `approved_by`, `status`, `justification`, `decision_comment`, `attempt_count`, `max_attempts`, `failure_reason`, timestamps per stage |
| `remediation_executions` | `id` | One row per execution attempt | `request_id`, `attempt`, `worker_identifier`, `status`, `execution_details`, `verification_result`, `error` |
| `audit_events` | `id` | Audit trail | `event_id` (unique UUID), `actor_id`, `actor_label`, `action`, `entity_type`, `entity_id`, `outcome`, `metadata`, `correlation_id`, `source_ip`, `created_at` |
| `system_settings` | `key` | Runtime settings | `value` (JSON), `updated_by` |
| `worker_heartbeats` | `worker_id` | Worker liveness | `last_seen_at`, `jobs_processed` |
| `demo_tasks` | `id` | Demo maintenance queued for the worker | `task_type`, `status`, `details` |

### 6.3 Relationships and foreign keys

| Child column | Parent | On delete | Meaning |
|---|---|---|---|
| `revoked_tokens.user_id` | `users.id` | CASCADE | Revocations disappear with the user |
| `incidents.resource_id` | `monitored_resources.id` | SET NULL | An incident survives removal of the resource record |
| `incident_events.incident_id` | `incidents.id` | CASCADE | The timeline belongs to its incident |
| `incident_events.actor_id`, `audit_events.actor_id` | `users.id` | SET NULL | History is kept; `actor_label` preserves who acted |
| `security_findings.scan_id`, `last_scan_id` | `security_scans.id` | SET NULL | First and most recent scan of the finding |
| `remediation_requests.incident_id`, `finding_id` | `incidents.id`, `security_findings.id` | RESTRICT | A source with remediation history cannot be deleted |
| `remediation_requests.requested_by`, `approved_by` | `users.id` | RESTRICT | Requester and approver cannot be deleted |
| `remediation_executions.request_id` | `remediation_requests.id` | CASCADE | Attempts belong to their request |

### 6.4 Constraints that carry business rules

| Constraint | Rule enforced |
|---|---|
| `ck_users_role`, `ck_incidents_status`, `ck_incidents_severity`, `ck_scans_status`, `ck_findings_status`, `ck_findings_severity`, `ck_remediation_status`, `ck_audit_outcome` | Only the defined enumeration values can be stored |
| `uq_incidents_active_fingerprint` (partial unique index on `alert_fingerprint` where status is OPEN, ACKNOWLEDGED or IN_PROGRESS) | At most one active incident per alert fingerprint |
| `security_findings.stable_finding_key` unique | One finding per file, rule and resource |
| `ck_remediation_single_source` | A request refers to exactly one of incident or finding |
| `uq_remediation_active_incident`, `uq_remediation_active_finding` (partial unique indexes over the in-flight statuses) | At most one in-flight request per source |
| `uq_execution_request_attempt` | Attempt numbers are unique per request |
| Trigger `trg_audit_events_immutable` (PostgreSQL) | UPDATE and DELETE on `audit_events` raise an error |

Explain what a partial unique index is: a unique index that applies only to rows satisfying a predicate. It allows many resolved or closed incidents with the same fingerprint, but only one active one.

### 6.5 Migration and legacy data

- The schema is versioned with Alembic; a test compares the migrated schema with the models so they cannot drift apart.
- If the migration finds tables of the CloudShield prototype in PostgreSQL, it moves them, with their data, into the schema `legacy_cloudshield` instead of dropping them.
- Normal forms: discuss that the tables are in third normal form except for deliberate denormalisation - `actor_label` and `requested_by_label` copy a name so that history remains readable after a user is removed, and JSON columns hold evidence and metadata whose shape varies by rule or action.

**Figures / tables to include**

- ER diagram: [`../diagrams/er-diagram.md`](../diagrams/er-diagram.md).
- Tables 6.1 to 6.3 as above; a data dictionary per table (column, type, null, default, description) copied from `models.py`.
- Listing: the definition of `uq_incidents_active_fingerprint`.

---

## Chapter 7 - Implementation

Present the implementation module by module. For each module give the files, the responsibility and the important algorithm.

### 7.1 Backend application (`backend/app/main.py`, `core/`)

- A middleware assigns a fresh request ID to every request (a caller-supplied `X-Request-ID` is deliberately not adopted, because the request ID becomes the default audit correlation ID), writes a structured access log, and records `http_requests_total` and `http_request_duration_seconds` using the route template as the label so that label cardinality stays bounded.
- Exception handlers return consistent JSON (`detail`, `request_id`) and never a stack trace.
- `/health/live` reports that the process runs; `/health/ready` returns HTTP 503 unless the database is reachable and migrated; `/metrics` is the Prometheus exposition endpoint.
- `core/config.py` reads all configuration from the environment. The API refuses to start without a `SECRET_KEY` of at least 32 characters and an `ALERT_WEBHOOK_TOKEN` of at least 16; in production mode it also refuses placeholder values, SQLite and bootstrap passwords that do not meet the password policy.

### 7.2 Authentication and RBAC (`core/security.py`, `core/permissions.py`, `api/auth.py`)

- Passwords are hashed with bcrypt. `verify_password` always performs one bcrypt comparison, using a dummy hash when the e-mail is unknown, so that response time does not reveal whether an account exists.
- The JWT (HS256) carries `sub`, `role`, `ver`, `jti`, `iat` and `exp`. On every request `get_current_user` checks the signature and expiry, that the user exists and is active, that `ver` equals the user's current `token_version`, and that `jti` is not in `revoked_tokens`.
- `require_permission("...")` is a FastAPI dependency factory. A refused request is audited as `ACCESS_DENIED` and answered with HTTP 403. An unknown permission name raises an error at import time, so a typing mistake cannot silently disable a check.
- Sign-in rate limiting uses an in-process sliding window keyed by client address and e-mail, plus a coarser per-address limit and a limit per e-mail regardless of the address (20 failures by default lock sign-in for that e-mail from every address until the window passes). Wrong current-password attempts on the change-password form are limited per user in the same way, and the limiter's memory is bounded by periodic sweeps.

### 7.3 Monitoring (`test-app/app.py`, `monitoring/`, `services/monitoring_service.py`)

- The demonstration application is a small order service. Middleware counts and times every HTTP request; CPU and memory come from the process collector of `prometheus_client`. A background thread sends real HTTP requests to the service's own endpoints (the synthetic load generator).
- Controlled faults (only when demo controls are enabled, token protected): `outage` (every service endpoint and `/metrics` answer HTTP 503), `errors`, `latency`, `cpu`, `memory`.
- The backend's `PrometheusClient` uses the HTTP API (`/api/v1/query`, `/api/v1/query_range`, `/api/v1/targets`, `/api/v1/alerts`) with a strict timeout and a short cache. Every result carries `available` and a reason; no default value is substituted.
- Five alert rules in `monitoring/alert_rules.yml`: `ApplicationUnavailable`, `HighHttp5xxErrorRate`, `HighApiLatency`, `HighCpuUsage`, `HighMemoryUsage`.
- The alert webhook checks its bearer token in a dependency that runs before the request body is parsed, so a caller without the token always receives HTTP 401 and learns nothing about the expected payload; with the token, a malformed payload receives HTTP 422.

### 7.4 Algorithm: incident deduplication by fingerprint

Files: `services/incident_service.py`, index in `models/models.py`.

```
for each alert in the validated webhook batch:
    fingerprint = alert.fingerprint (lower case)  or  sha256(sorted labels)[:32]
    begin SAVEPOINT
        if alert is firing:
            active = incident with this fingerprint and status in (OPEN, ACKNOWLEDGED, IN_PROGRESS)
            if active exists:
                occurrence_count += 1; last_occurrence_at = now          -> "deduplicated"
            else if a RESOLVED incident with this fingerprint was resolved
                    within incidents.reopen_window_minutes:
                reopen it                                                -> "reopened"
            else:
                insert a new OPEN incident + timeline event + audit      -> "created"
        else (resolved):
            resolve the active incident with monitoring evidence         -> "resolved"
    if the insert violates uq_incidents_active_fingerprint (two deliveries raced):
        roll back the savepoint and run the firing branch again; it now
        finds the incident the other transaction created                 -> "deduplicated"
commit the batch
```

Points to explain: (a) application code alone is not sufficient under concurrency, because two transactions can both see "no active incident"; (b) the partial unique index makes the second insert fail; (c) the savepoint (`begin_nested`) confines the failure to one alert; (d) the repeated-notification event on the timeline is updated in place rather than appended, so a long outage does not flood the timeline.

### 7.5 Incident lifecycle and evidence-based resolution

- Allowed transitions are a table (`TRANSITIONS`); anything else returns HTTP 409.
- An incident reaches RESOLVED in three ways only: Alertmanager reports the alert resolved; a remediation request succeeds after verification; or a person resolves it with a note of at least ten characters, in which case the service asks Prometheus whether the alert is still firing and refuses if it is, or if Prometheus cannot answer. Only in the second case (monitoring unavailable) may an Administrator override, and the override and reason are stored with the evidence.
- When an incident is resolved by monitoring or manually, remediation requests that were not yet dispatched are cancelled automatically.
- `signal_is_stale` flags an active incident whose alert has not been re-notified for much longer than Alertmanager's repeat interval.

### 7.6 Algorithm: scanner, stable key and finding lifecycle

Files: `security_scanner/engine.py`, `security_scanner/rules.py`, `services/scan_service.py`, `security-rules/policies.yaml`.

- **Input validation.** Only a plain `*.yaml` file name is accepted; the resolved path must lie directly inside the workspace (this blocks `../`, absolute paths and symbolic links). The file must be UTF-8, below the size limit, contain no YAML anchors or aliases, declare `schema_version: vigilops/v1` and contain a list of resources with unique type and name. `yaml.safe_load` is used.
- **Rules.** Each rule is a pure function from a resource to a list of matches; rule metadata (name, severity, description, impact, recommendation) is loaded from `policies.yaml`, and loading the rule set raises an error if the catalog and the code do not describe exactly the same rule identifiers.

| Rule | Severity | Detected when |
|---|---|---|
| SEC-001 Public Storage Access | HIGH | a storage bucket has `public_access: true` or an ACL of `public-read` or `public-read-write` |
| SEC-002 Missing Encryption | MEDIUM | a storage bucket, disk volume or database has no encryption block, `enabled` is not true, or the algorithm is empty or NONE |
| SEC-003 Wildcard IAM Permissions | CRITICAL | an Allow statement has action `*` or `service:*`, or resource `*` |
| SEC-004 Unrestricted Inbound Network Access | HIGH | an ingress rule open to `0.0.0.0/0` or `::/0` covers a sensitive port (22, 23, 3389, 1433, 3306, 5432, 6379, 9200, 27017), including port ranges |
| SEC-005 Privileged Container Execution | HIGH | a container has `privileged: true` or `security_context.privileged: true` |

- **Stable key.** `stable_finding_key = sha256(target_file | rule_id | resource_type | resource_name)`. There is one finding per rule and resource; individual matches (for example two open ports) are stored as evidence.
- **Lifecycle on each successfully scanned file:**

```
existing = findings of this file, indexed by stable key
for each violation:
    not in existing            -> insert OPEN                     (audit FINDING_DETECTED)
    existing and RESOLVED      -> back to OPEN                    (audit FINDING_REOPENED)
    existing, any other state  -> update last_seen, evidence, detection_count
for each existing finding not detected and not RESOLVED:
    -> RESOLVED, resolved_at = now                               (audit FINDING_RESOLVED)
```

A malformed file is reported and skipped; its existing findings are left unchanged. Findings are never deleted. When a scan of the whole workspace finds unresolved findings whose file is no longer present, it reports their number in the scan summary and leaves their status unchanged, because a deleted file is not a verified fix.

### 7.7 Algorithm: remediation state machine

Files: `services/remediation_service.py` (API side), `services/remediation_catalog.py` (allowlist).

| From | Operation | By | To |
|---|---|---|---|
| (new) | request | Operator or Administrator | PENDING_APPROVAL |
| PENDING_APPROVAL | approve | Administrator (not the requester unless self-approval is enabled) | APPROVED |
| PENDING_APPROVAL | reject (reason required) | Administrator | REJECTED |
| PENDING_APPROVAL, APPROVED | cancel | requester or Administrator | CANCELLED |
| APPROVED | execute (dispatch) | Administrator | QUEUED |
| QUEUED | claim | worker | RUNNING |
| RUNNING | handler finished | worker | VERIFYING |
| VERIFYING | verification passed / failed | worker | SUCCEEDED / FAILED |
| FAILED | retry (while attempts remain) | Administrator | QUEUED |

Every operation checks the current status first (`_require_status`), so executing a request that is still PENDING_APPROVAL returns HTTP 409. The API never performs the corrective action; it only moves the request to QUEUED.

### 7.8 Algorithm: worker queue with `FOR UPDATE SKIP LOCKED`

File: `workers/remediation_worker.py`.

```
SELECT * FROM remediation_requests
 WHERE status = 'QUEUED'
 ORDER BY queued_at, id
 LIMIT 1
 FOR UPDATE OF remediation_requests SKIP LOCKED;

if no row: nothing to do
if approved_by IS NULL: mark FAILED ("no recorded approval"), audit as DENIED, stop
status = RUNNING; attempt_count += 1; insert remediation_executions row; commit
run the handler for action_code with a timeout
status = VERIFYING; commit
run the verifier for action_code
SUCCEEDED or FAILED; commit
```

`FOR UPDATE` locks the selected row for the transaction; `SKIP LOCKED` makes a second worker skip a locked row instead of waiting, so two workers can never claim the same request. On start the worker marks requests left in RUNNING or VERIFYING by an earlier crash as FAILED with the reason "outcome unknown". A separate heartbeat thread writes a heartbeat row on a timer, independently of the job loop, so the user interface and the container health check can tell that the worker is alive even during a long verification. A queued request without a recorded approval is refused, can never be retried, and releases its finding back to OPEN.

### 7.9 Action handlers and verification (`workers/actions.py`, `workers/verification.py`)

- **ACTION-001.** The handler records readiness before the action and calls `POST /internal/recover` on the demonstration application with the recovery token, with a small number of retries for transient errors. Verification requires three consecutive successful readiness checks, then a Prometheus scrape of the target that is healthy and newer than the action, then that the alert which opened the incident is no longer firing. Only then is the incident resolved with these checks as evidence. The handler cannot start a stopped container; in that case the recovery call fails and the request ends as FAILED.
- **ACTION-002.** The handler accepts only a storage bucket finding whose file is on the remediation allowlist, sets `public_access: false` and a public ACL to `private`, writes the file atomically (temporary file, then rename) and records before and after values, hashes and a diff. Verification runs a real, persisted scan of the file, independently re-evaluates that the rule no longer matches the resource, and checks that the scan itself moved the finding to RESOLVED. The handler is idempotent: if the bucket is already private it changes nothing.
- The set of handlers must equal the catalog (an assertion at import time).

### 7.10 Audit trail (`services/audit_service.py`)

`record_audit` adds the event to the caller's transaction, so a state change and its audit record are committed together or not at all. Metadata is sanitised: keys that look like credentials are replaced with `[REDACTED]`, and long values are truncated. All events of one remediation workflow share the request's correlation ID, which the user interface uses to show the complete workflow.

### 7.11 VigilAI (`backend/app/assistant/`)

Pipeline in `service.py`: input limit and per-user rate limit, scope classification, retrieval, live-data functions, provider call, validation, reply. A message longer than the configured limit is rejected with HTTP 422 rather than truncated. Conversation history sent by the browser is treated as untrusted: it is bounded, and turns that look like an attempt to override the assistant's rules are dropped before the prompt is built.

**Scope classification (`scope.py`).** Decided in the backend before any retrieval or model call, in this order:

1. empty message - out of scope;
2. instruction-override pattern (for example "ignore previous instructions", "system prompt") - PROMPT_INJECTION;
3. request to reveal a credential, unless phrased as "how do I configure ..." - SECRET_REQUEST;
4. off-topic task type (poem, joke, weather, stock prediction ...) - OUT_OF_SCOPE;
5. relevance score from domain vocabulary: 2 points per strong term (incident, Prometheus, SEC-001 ...), 1 per weak term (application, CPU, status ...);
6. an instruction to act (an imperative verb such as approve, execute or delete at the start, or "... for me / right now") that uses platform vocabulary, or any shell-command pattern - PRIVILEGED_ACTION;
7. score of at least 2 - IN_SCOPE;
8. a short follow-up ("how do I fix it?") inherits the scope of the user's previous in-scope question, which the server remembers per user for a limited time - it is never taken from the history the browser sends, which could be fabricated;
9. otherwise OUT_OF_SCOPE.

**BM25 retrieval (`retrieval.py`).** The Markdown files in `knowledge_base/` are split into chunks at second- and third-level headings (long sections are split at paragraph boundaries). Tokens are lower-cased, stop words are removed, identifiers such as `sec-001` are kept whole and simple plurals are normalised; the tokens of a chunk's section heading are counted three times and the document title once, so headings weigh more than body text. For a query with distinct terms t:

```
score(chunk) = sum over t of  idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len / avg_len))
idf(t)       = ln(1 + (N - df + 0.5) / (df + 0.5))        with k1 = 1.5, b = 0.75
```

Up to four chunks are returned, and only if the best score reaches a minimum and each chunk reaches a fraction of the best score; otherwise nothing is returned.

**Live data (`context_tools.py`).** Fixed read-only functions (monitoring summary, open incidents, incident details, findings, latest scan, remediation requests, remediation status, recent audit events). Each checks the caller's permission and goes through the same service layer as the REST API. Which functions run is decided by keyword routing, never by the model.

**Prompt and provider (`prompts.py`, `gemini_provider.py`).** Documentation, live data, conversation and question are placed in separate delimiter tags, with angle brackets in untrusted text replaced so that it cannot close a tag. The system instruction states the scope, read-only, grounding, untrusted-data and secrets rules. The provider is behind a small interface; quota errors are never retried.

**Validation (`sanitize.py`).** The out-of-scope sentinel becomes the standard refusal; markup is stripped; configured secrets and key-shaped strings are redacted; a sentence in which the model claims to have performed an action is replaced by the read-only message; long replies are truncated. The frontend renders replies as text (`SafeText.jsx`), never as HTML.

**Fallback.** If no provider is configured, the daily budget is used up, or the provider fails, times out or returns nothing, the retrieved documentation and live data are returned directly with a notice. **Verification status:** this fallback path was exercised, and live Gemini generation was verified with a real API key and the default model `gemini-3.5-flash-lite` (9 of 9 platform questions answered in `ai` mode; `scripts/verify_gemini_live.py`, `docs/evidence/gemini-live.json`). On the running stack, a model name that does not exist (HTTP 404 from the provider) and an invalid API key (HTTP 400, reason `API_KEY_INVALID`) each produced the fallback with the matching notice. Real quota exhaustion (HTTP 429) and provider timeouts are covered only by tests with a stubbed SDK client.

### 7.12 Frontend (`frontend/src/`)

Describe the pages (Overview, Monitoring, Incidents, Incident detail, Security Findings with its four tabs, Finding detail, Remediation, Remediation detail with stepper and verification checks, Audit Logs, VigilAI / Help, Settings with its tabs) and the shared components (`DataTable`, `StatusBadge`, `MetricCard`, `TimeSeriesChart`, `Timeline`, `Modal` and `ConfirmDialog`, `RequestRemediation`). Note that a metric card renders "Unavailable" rather than a number when the value is missing.

### 7.13 Deployment and configuration

`compose.yaml`, `compose.prod.yaml`, `reverse-proxy/Caddyfile`, Dockerfiles, `.env.example`, `scripts/generate_env.py`, `scripts/verify_stack.sh`, `scripts/backup_db.sh`, `scripts/restore_db.sh`. See [`../setup.md`](../setup.md), [`../configuration.md`](../configuration.md) and [`../deployment.md`](../deployment.md). For the free-hosting option: `render.yaml`, `deploy/render/Dockerfile`, `deploy/render/launcher.py` and `frontend/vercel.json`; see [`../deployment-render-vercel.md`](../deployment-render-vercel.md).

**Figures / tables to include**

- Listings: `require_permission`, `process_alerts`, `claim_next`, `verify_storage_correction`, `classify`, `KnowledgeBase.search` (short excerpts with file names).
- Table 7.1: rules; Table 7.2: remediation transitions; Table 7.3: assistant safeguards (scope validation, restricted retrieval, authorised live-data functions, role-aware checks, context minimisation, prompt-injection resistance, response validation, output sanitisation, rate limiting).
- Screenshots: each page; the remediation detail page showing the verification checks and the configuration diff; the VigilAI widget.
- API reference: [`../api.md`](../api.md).

---

## Chapter 8 - Testing and Validation

Do not state the number of tests or a pass rate here. Take them from [`../verification-report.md`](../verification-report.md) with the date of the run.

### 8.1 Strategy and levels

| Level | Tooling | What it proves |
|---|---|---|
| Unit | pytest | Pure logic: rules, parsing, hashing, tokens, limiter, redaction, scope classification, retrieval, output validation |
| Integration (API) | pytest with FastAPI `TestClient` | Endpoints, permissions, state machines and database effects together, with monitoring and the AI provider replaced by controllable fakes |
| Database-specific | pytest on PostgreSQL | Migration equals models, audit trigger, legacy-table preservation, row locking |
| Frontend component | Vitest, Testing Library, jsdom | Sign-in flow, formatting, remediation request dialog, VigilAI widget behaviour |
| Configuration | `docker compose config`, `promtool`, `amtool` | Compose files, Prometheus rules and Alertmanager configuration are valid |
| Stack verification | `scripts/verify_stack.sh` | Containers run and are healthy; internal endpoints are not exposed through the proxy; security headers are present |
| End-to-end | `scripts/run_e2e_demos.py` | The three demonstrations work against the real running stack |

The backend suite runs on SQLite by default and on PostgreSQL when `TEST_DATABASE_URL` is set; the CI workflow (`.github/workflows/ci.yml`) runs both, then the frontend tests and build, the configuration checks, and finally starts the stack and runs the demonstrations.

### 8.2 What each suite covers

| File | Coverage |
|---|---|
| `backend/tests/unit/test_core.py` | bcrypt hashing, password policy, token round trip and tamper detection, sliding-window limiter, audit metadata sanitising, log redaction, permission matrix, settings validation, production safeguards |
| `backend/tests/unit/test_scanner.py` | each insecure fixture triggers exactly its rule; secure fixtures produce no findings; baseline has one finding per rule; determinism; stable key; edge cases of SEC-001, SEC-003 and SEC-004; rejection of invalid, oversized and unsafe YAML |
| `backend/tests/unit/test_assistant_guards.py` | scope classification of allowed, unrelated, privileged, secret and injection messages; follow-up handling; tokenizer and chunking; retrieval of the right section; sentinel, markup stripping, secret redaction, action-claim replacement, truncation; delimiter escaping |
| `backend/tests/integration/test_auth_rbac.py` | sign-in, generic failure message, rate limiting, missing or invalid tokens, sign-out revocation, session invalidation, no public registration, Operator refused on Administrator endpoints, user management, last-Administrator rule, settings, health endpoints |
| `backend/tests/integration/test_incidents.py` | webhook token and payload validation, incident creation, repeated notifications, separate alerts, resolution by monitoring, reopen inside the window and new incident outside it, lifecycle validation, refusal to resolve without confirmation, comments and listing, stale signal |
| `backend/tests/integration/test_scanning.py` | persisted findings and history, no duplicates, finding detail, resolve and reopen by scan, secure file, authorised targets only, symbolic-link escape, malformed file, empty workspace, accepted risk |
| `backend/tests/integration/test_remediation.py` | both actions end to end, failed verification, retry and attempt limit, idempotency, allowlist validation, self-approval rule, reject and cancel, worker refusing an unapproved request, write allowlist, interrupted executions, recovery not successful until monitoring confirms, unreachable application |
| `backend/tests/integration/test_assistant.py` | documentation mode, live-data answers, standard refusal, privileged instruction changes nothing, secret and injection refusals, grounding context passed to a stub provider, validation of model output, provider failure kinds, rate limit, disabling the assistant, embedded instructions treated as data, Gemini error classification with a stub client |
| `backend/tests/integration/test_audit_monitoring.py` | audit fields, Operator visibility, search and filters, no modification through the API, real target state, unavailable Prometheus, metric catalog restriction, Prometheus client parsing, demo controls gating, simulated label, baseline restore, migration matches models, gaps in range data |
| `backend/tests/integration/test_postgres.py` | (PostgreSQL only) migration, append-only trigger, legacy tables preserved, two workers cannot claim the same request |
| `backend/tests/integration/test_hardening.py` | regression tests for defects found in review and in runs against the live stack: webhook returns 401 before validating the body, reopen clears the old resolution, verification results are not redacted in audit metadata, a caller cannot choose the audit correlation ID, a forged queued request is refused and cannot be retried, retry respects accepted risk, refused cancel is audited, heartbeat thread, findings of a removed file are reported, change-password rate limit, bounded limiter memory, production configuration checks, fabricated chat history cannot widen the scope, over-long message rejected |
| `frontend/src/test/app.test.jsx` | formatting, unavailable metric shows no number, status tones, redirect to sign-in, failed sign-in shows the backend error, invalid stored token dropped, remediation request dialog |
| `frontend/src/test/vigilai.test.jsx` | model markup shown as literal text, widget closed by default, welcome and suggestions, sending and sources, history without the welcome message, error with retry, Escape to close, opening from another page, no blank messages |
| `tests/e2e/specs/platform.spec.js` | (Playwright, Chromium, against the running stack) redirect of signed-out visitors, failed and successful sign-in, sign-out, every section reachable from one menu, live Prometheus telemetry on the Monitoring page, Operator restrictions in the interface, the VigilAI widget, the complete security remediation workflow with two users, phone-sized layout |
| `scripts/verify_alert_rules.py` | (running stack) each of the four other alert rules opens an incident under its controlled fault and is resolved by the monitoring signal |
| `scripts/verify_gemini_live.py` | (running stack, real API key) generated answers are grounded, refusals never reach the model, no secret or rule text in replies |

### 8.3 Test doubles and their consequence

- `FakePrometheus` (in `backend/tests/conftest.py`) replaces the Prometheus client so that target health and firing alerts can be controlled.
- A fake demonstration application and a fake AI provider replace the corresponding HTTP calls; a stub client replaces the Google SDK client to test error classification.
- Consequence to state in the report: integration tests prove the platform's logic against controlled inputs; the end-to-end demonstrations prove the real integration with Prometheus, Alertmanager, PostgreSQL, the worker and the demonstration application. Neither proves the integration with the real Gemini API; that is verified separately by `scripts/verify_gemini_live.py`, which needs a real API key.

### 8.4 The three end-to-end demonstrations

`python scripts/run_e2e_demos.py` signs in as the bootstrap Administrator and Operator from `.env`, drives the public entry point like a browser, records each check as PASS or FAIL and writes measured values to `docs/evidence/e2e-results.json`.

1. **Application failure and recovery.** Healthy state from live Prometheus data; controlled outage; scrape target DOWN; alert reaches the webhook and one incident is created, labelled simulated, CRITICAL, OPEN with ACTION-001; resolving while the alert fires is refused; a repeated notification updates the same incident; Operator requests, Administrator approves and dispatches; the worker recovers the application; verification by health checks and Prometheus; incident RESOLVED with evidence; audit trail under one correlation ID; Administrator closes the incident.
2. **Security misconfiguration.** Reset of the insecure sample by the worker; scan; all five rules detected without duplicates; SEC-001 detail with evidence and ACTION-002; Operator approval attempt returns HTTP 403 with no change; execution before approval is refused; approval alone changes nothing; dispatch; file corrected; verification re-ran the scanner; SEC-001 RESOLVED while the other four stay OPEN; audit trail complete.
3. **VigilAI.** Status and welcome message; documentation question answered from the knowledge base; live-incident and incident-specific questions use authorised live data; remediation guidance; allowed examples answered; unrelated questions receive the exact refusal; privileged instruction refused with nothing changed; secret request and prompt injection refused; documentation fallback when Gemini is not configured; the platform keeps working; per-user rate limit.

### 8.5 What was not tested

- Real quota exhaustion of the Gemini API (HTTP 429 from the provider) and real provider timeouts; these paths are covered only by tests with a stubbed SDK client. Live generation itself was verified with a real API key.
- Systematic human evaluation of the quality of generated answers; they were checked with keyword grounding checks and by reading the replies of a small question set with one model.
- Deployment with public HTTPS on a real domain.
- Load, stress and long-duration behaviour.
- Browsers other than Chromium. The nine Playwright tests in `tests/e2e/` run in Chromium only, and Demo 1 (application failure and recovery) is automated at the API level, not through the pages.

**Figures / tables to include**

- Table 8.1 (levels) and Table 8.2 (suites).
- Figure: CI pipeline with its four jobs.
- Screenshot or listing: output of `scripts/run_e2e_demos.py` and of `scripts/verify_stack.sh` from the verification report.
- Table of results: copied from [`../verification-report.md`](../verification-report.md).

---

## Chapter 9 - Results and Evaluation

This chapter defines each metric and exactly how it is measured. **All values are deferred to [`../evaluation.md`](../evaluation.md).** Report each value with the date, the machine, the number of repetitions and, where there is more than one run, the minimum, median and maximum.

### 9.1 Experimental setup

- The full stack from `compose.yaml` on one machine, demo controls enabled, default intervals: Prometheus scrape and rule evaluation every 5 seconds; `ApplicationUnavailable` has `for: 15s`; Alertmanager `group_wait` 5 seconds, `group_interval` 15 seconds, `repeat_interval` 2 minutes.
- Measurements are taken by `scripts/run_e2e_demos.py` through the public entry point and written to `docs/evidence/e2e-results.json`; correctness metrics come from that script and from the automated test suites.
- Record: hardware, operating system, Docker version, commit identifier, whether a Gemini key was configured (`assistant_mode` in the evidence file).

### 9.2 Metrics and measurement procedure

| ID | Metric | Definition | How it is measured | Value |
|---|---|---|---|---|
| M1 | Alert-to-incident time | Seconds from injecting the outage to the incident being visible through the API | Timestamp before `POST /api/demo/faults` (mode `outage`); poll `GET /api/incidents?active_only=true&q=ApplicationUnavailable` every second until an item appears; recorded as `alert_to_incident_seconds`. The script also records `outage_to_target_down_seconds` (injection to scrape target DOWN). | see evaluation |
| M2 | Incident deduplication | Number of active incidents per alert fingerprint after repeated notifications (expected: one) and the notification count on that incident | After creation check `occurrence_count` is 1; wait for Alertmanager's repeat; check `occurrence_count` is at least 2 and that the listing for this alert has exactly one active incident. Supported by the integration test for repeated notifications and by the database index. | see evaluation |
| M3 | Scanner detection on insecure fixtures | For each file in `security-rules/samples/insecure/`, expected violating resources detected divided by expected | Unit test that scans each fixture and compares the set of (rule, resource) with the expected set; the demo baseline must yield one finding per rule | see evaluation |
| M4 | False positives on secure fixtures | Number of findings produced for files in `security-rules/samples/secure/` (expected: none) | Unit test scanning every secure fixture; integration test with a secure file in the workspace | see evaluation |
| M5 | Remediation execution time | Seconds from dispatch to a terminal status, per action | Timestamp before `POST /api/remediation/requests/{id}/execute`; poll the request until SUCCEEDED or FAILED; recorded as `remediation_execution_seconds_ACTION_001` and `..._ACTION_002`. For ACTION-001 this includes waiting for the alert to clear. | see evaluation |
| M6 | Verification success | Proportion of dispatched requests that reach SUCCEEDED with every verification check passed; and correct FAILED outcome when verification cannot pass | Inspect `verification_result.checks` of the last execution (`application_health`, `prometheus_target_up`, `alert_cleared`; or `security_rescan`, `rule_not_detected`, `finding_resolved_by_scan`). Negative cases come from the integration tests for failed verification. | see evaluation |
| M7 | Application recovery time | Seconds from the worker starting the execution to completion of the recovery call | `execution_details.recovered_at` minus the execution's `started_at`; recorded as `application_recovery_seconds` | see evaluation |
| M8 | AI in-scope correctness | Proportion of the specification's allowed example questions that receive an answer (mode `ai` or `fallback`), with content checks on selected answers | The script asks each allowed question and counts answered ones (`assistant_in_scope_answered`); it checks that the SEC-001 answer cites `security_rules.md` and that the remediation-guidance answer mentions the fix. Retrieval of the right section is tested per query in the unit tests. | see evaluation |
| M9 | AI out-of-scope refusal | Proportion of the specification's disallowed examples answered with the exact refusal text; classification of secret requests and prompt injection | The script compares each reply with the fixed refusal string (`assistant_out_of_scope_refused`) and checks the `scope` field for the secret and injection cases | see evaluation |
| M10 | RBAC enforcement | Proportion of unauthorised attempts that are refused with HTTP 403 without a state change | Operator calls approve on a pending request: expect 403 and status unchanged; Administrator calls execute before approval: expect 409; an integration test calls a list of Administrator-only endpoints (user management, settings, demo controls, accepted risk, approve, reject, execute, retry) as an Operator and checks that each returns 403 and writes one `ACCESS_DENIED` audit record | see evaluation |

### 9.3 Interpretation guidance

- **M1** has a structural lower bound that follows from configuration, not from the platform's speed: the rule's `for` duration, plus Alertmanager's `group_wait`, plus up to one scrape interval and one evaluation interval. Discuss the measured value against that bound.
- **M5 for ACTION-001** is dominated by verification (waiting for a fresh scrape and for the alert to stop firing), which is deliberate: the platform trades speed for evidence.
- **M8 in documentation-fallback mode** measures whether the right documentation and live data were returned, not the quality of generated language. If the evaluation was run without a Gemini key, state that the generated-answer quality of live mode was not evaluated.
- **M3 and M4** are measured on the project's own fixtures. They show that the rules behave as specified on those files; they are not a claim about detection in arbitrary real-world configurations.

### 9.4 Threats to validity

- Single machine, single monitored application, synthetic workload.
- Timings depend on the configured intervals and on polling granularity of the measuring script (one or two seconds).
- Fixtures were written by the same team that wrote the rules.
- Live AI mode was verified in one run with one model on a small question set, without a systematic human evaluation of answer quality; rate limits and caches are per process.

**Figures / tables to include**

- Table 9.1: metric definitions (above) with the measured values filled in from the evaluation document.
- Chart: time line of one outage run (fault injected, target DOWN, incident created, request dispatched, recovery, verified) using the recorded timestamps.
- Screenshots: Monitoring page during the outage (gap in the charts), remediation detail with verification checks, Security Findings before and after, audit trail filtered by correlation ID.
- Table: PASS/FAIL list of the end-to-end checks from the verification report.

---

## Chapter 10 - Conclusion and Future Scope

### 10.1 Conclusion

- The project delivers one application in which a problem detected from a real monitoring signal or by a deterministic scan becomes a traceable record, can be corrected only through an approved, allowlisted action executed by an isolated worker, is accepted as fixed only on independent evidence, and leaves a complete audit trail.
- The audit of the prototype showed how a system can appear complete while its core behaviour is simulated; the upgrade replaced simulation with real instrumentation and real verification, and added tests that exercise the running stack.
- The assistant demonstrates a conservative way to add a language model to an operations tool: scope decided by the backend, read-only data functions, validated output and a non-AI fallback.
- Relate the conclusion to objectives O1 to O9 and to the measured values in Chapter 9.

### 10.2 Limitations (state them plainly)

1. The scanner evaluates local YAML files in the `vigilops/v1` schema; it is not a live cloud account assessment, and there is no AWS integration.
2. Only two automated remediation actions exist; findings for SEC-002 to SEC-005 are corrected manually.
3. ACTION-001 cannot start a stopped container, because the platform has no Docker or host access by design.
4. ACTION-002 rewrites the YAML document when it corrects a bucket; leading comments are kept, but formatting and comments inside the body are normalised.
5. Rate limiting, the monitoring cache and the assistant's daily budget are held in process memory; the backend therefore runs as a single process and the limits reset on restart.
6. The demonstration application's traffic is produced by a built-in synthetic load generator. The measurements are real; the workload is not production traffic.
7. Live Gemini generation was verified with a real API key, but only on a small question set with one model; answer quality was checked with keyword grounding checks and by reading the replies, not by a systematic human evaluation. Real quota exhaustion (HTTP 429 from the provider) was never observed; that path and provider timeouts are covered only by tests with a stubbed SDK client.
8. The production overlay with automatic HTTPS was not deployed on a real domain.
9. The assistant's scope classification is based on keyword patterns; it can misclassify unusual phrasing. Because the assistant has no ability to act, a misclassification can at worst produce an unhelpful answer.
10. No load testing, no multi-factor authentication, no external notification channel.
11. The worker processes one job at a time, and an action that exceeds its timeout is abandoned rather than stopped, because a Python thread cannot be killed; handlers therefore perform only bounded input and output.
12. The API and the worker connect to PostgreSQL with the same database role; the approval check in the worker and the audit trigger protect against application faults and misuse through the API, not against someone who holds the database password.

The complete lists, with reasons, are in [`../architecture.md`](../architecture.md#known-limitations) and [`../security.md`](../security.md#residual-risks-and-limitations). Use them as the source for this section and do not omit items because they are unflattering.

### 10.3 Future scope

Summarise the themes of [`future-scope.md`](future-scope.md): optional read-only AWS integration, more rules and actions, node and container exporters, notification channels, multi-factor authentication and single sign-on, a shared rate-limit store and multi-instance backend, vector retrieval if the knowledge base grows, Kubernetes deployment.

**Figures / tables to include**

- Table 10.1: objective - achieved - evidence.
- Table 10.2: limitation - consequence - proposed future work.

---

## Suggested appendices

| Appendix | Content | Source |
|---|---|---|
| A | Installation and configuration | [`../setup.md`](../setup.md), [`../configuration.md`](../configuration.md) |
| B | API reference | [`../api.md`](../api.md) |
| C | Rule catalog | `security-rules/policies.yaml` |
| D | Alert rules and Alertmanager configuration | `monitoring/alert_rules.yml`, `monitoring/alertmanager.yml` |
| E | User guide with screenshots | [`../user-guide.md`](../user-guide.md) |
| F | Demonstration script | [`demo-script.md`](demo-script.md) |
| G | Verification report and evidence file | [`../verification-report.md`](../verification-report.md), `docs/evidence/e2e-results.json` |
| H | Team responsibilities | [`team-responsibilities.md`](team-responsibilities.md) |

## References (guidance)

List only sources that were actually consulted, in the format required by the college. Expected entries: official documentation of Prometheus, Alertmanager, PromQL, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL (partial indexes, `SELECT ... FOR UPDATE SKIP LOCKED`, triggers), React, Vite, Docker Compose, Caddy, the Google Gen AI SDK; the OWASP guidance on prompt injection and on access control if used; the original description of the BM25 ranking function if the guide requires a primary source. Add the access date for every web source.
