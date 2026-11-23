# VigilOps: Secure Cloud Operations - Presentation Outline

B.Tech Computer Science and Engineering (Cloud Computing and Virtualization) - Major Project presentation, 15 slides.

> **To be filled in by the team:** institution, department, guide name, and the name and roll number of Member 1 to Member 5 (slide 1).

## Before building the slides

- Every figure on a slide must come from [`../evaluation.md`](../evaluation.md) or [`../verification-report.md`](../verification-report.md). Where this outline says "measured value", copy it from there with its date. Do not use numbers from the old CloudShield documents.
- Diagrams are the Mermaid sources in [`../diagrams/`](../diagrams/); export them as images.
- Screens are taken from the running application (`http://localhost:8080`). Use the light theme for projection (theme button in the header).
- Say plainly where something was not verified: real exhaustion of the Gemini quota (live Gemini answers themselves were verified with a real API key, on a small question set with one model and without a systematic human evaluation) and public HTTPS deployment.
- Suggested length: about 15 minutes of slides, followed by the live demonstration in [`demo-script.md`](demo-script.md).

## Who presents what

| Member | Area of ownership | Slides |
|---|---|---|
| Member 1 | Frontend and user interface | 1, 2, 8 |
| Member 2 | Backend and authentication | 5, 6, 7 |
| Member 3 | Monitoring and incident management | 3, 4, 9 |
| Member 4 | Security scanner and remediation | 10, 11, 14 |
| Member 5 | VigilAI, integration, testing and documentation | 12, 13, 15 |

All members must be able to answer questions on every slide; see [`team-responsibilities.md`](team-responsibilities.md).

---

## Slide 1 - Title and Team

**Presenter:** Member 1

- VigilOps: Secure Cloud Operations
- B.Tech CSE (Cloud Computing and Virtualization) - Major Project
- Team: Member 1 to Member 5 (names and roll numbers), guide, institution
- One line: a centralized, local-first platform for monitoring, incidents, security scanning, controlled remediation, audit and a read-only assistant

**Visual:** project title with the application's sign-in screen or the Overview page as a background image.

**Speaker notes:** Introduce the team and the guide. State in one sentence what the project is: one web application that connects detection, corrective action and its record. Mention that the whole system runs on a laptop with Docker Compose and needs no cloud account.

---

## Slide 2 - Problem Statement

**Presenter:** Member 1

- Monitoring, alert handling, configuration review and corrective action are usually done in separate tools
- Repeated alerts for one problem create noise and duplicate tickets
- A fix is often declared successful without recorded evidence
- Automation and AI assistants that can act freely are a risk; actions must be approved and auditable

**Visual:** a simple diagram of four disconnected boxes (metrics, alerts, scanner, tickets) with a person in the middle, next to the closed loop of VigilOps (detect, record, request, approve, execute, verify, audit).

**Speaker notes:** Explain that the difficulty is not any single task but the links between them. Read the formal problem statement from Chapter 2 of the report. Stress the last point: the project is as much about controlling action as about detecting problems.

---

## Slide 3 - Motivation

**Presenter:** Member 3

- Cloud operations and security are core topics of the specialization; the project practises them end to end
- A small team should be able to see the health and the security posture of its application in one place
- "Fixed" should mean "verified by a fresh signal", not "a command was run"
- The earlier prototype looked complete but simulated its telemetry and its verification; this motivated a rebuild on real signals

**Visual:** two short quotations from [`../phase-0-audit.md`](../phase-0-audit.md) (random telemetry; verification that only checked the file was written) beside a screenshot of the Monitoring page with its "Live · Prometheus" tag.

**Speaker notes:** Describe the audit of the prototype honestly: its tests passed although Prometheus, the worker and the stack were never started. Explain that this finding shaped the project's rule that nothing shown to the user may be invented. Keep this slide short and move to existing systems.

---

## Slide 4 - Existing System Limitations

**Presenter:** Member 3

- Prometheus, Alertmanager, Grafana: strong for metrics, alert routing and dashboards; no incident lifecycle or corrective workflow of their own
- AWS Config, Checkov, tfsec: configuration assessment; either tied to a cloud account or limited to scanning, without approval-gated correction in one console
- PagerDuty, Splunk: incident response and log analytics; commercial platforms that do not execute and verify the fix
- General AI assistants: not grounded in the platform's live records and not guaranteed read-only
- Gap: the chain from detection to verified correction to audit record crosses several tools

**Visual:** comparison table from Chapter 3 of the report (rows: capabilities; columns: tool categories and VigilOps).

**Speaker notes:** Be fair to these tools: VigilOps uses Prometheus and Alertmanager and does not compete with large scanners. The claim is narrow - a small, integrated chain with approval and verification. Say that each statement about a product was checked against its official documentation.

---

## Slide 5 - Proposed Solution

**Presenter:** Member 2

- One React + FastAPI + PostgreSQL application, deployed with Docker Compose
- Real telemetry from Prometheus; alerts become deduplicated incidents through Alertmanager
- Deterministic scanner with five rules (SEC-001 to SEC-005) on local YAML configuration files
- Controlled remediation: Operator requests, Administrator approves and dispatches, restricted worker executes, result is verified
- Append-only audit trail and a read-only assistant (VigilAI)

**Visual:** the Overview page of the application (active incidents, open findings, pending approvals, remediation results, platform health).

**Speaker notes:** Walk through the Overview page from left to right, since each tile corresponds to one module. Explain "local-first": no AWS account, no paid service, no model training. Mention that the scanner works on sample configuration files, not on a live cloud account.

---

## Slide 6 - Objectives

**Presenter:** Member 2

- Show genuine telemetry; never substitute a value
- One active incident per alert; evidence-based resolution
- Detect five classes of misconfiguration deterministically, with a finding lifecycle
- Only allowlisted, approved, verified remediation by an isolated worker
- Server-enforced roles, complete audit trail, and an assistant that cannot act

**Visual:** the objective - module - metric table from Chapter 2 of the report (O1 to O9).

**Speaker notes:** For each objective name the metric that evaluates it, so the examiner sees that objectives and results are connected. Do not quote values yet; they come on slide 13.

---

## Slide 7 - Architecture

**Presenter:** Member 2

- Seven services on one private network: web (Caddy), backend, worker, PostgreSQL, Prometheus, Alertmanager, demonstration application
- Only the web service is exposed to users; it serves the frontend and forwards `/api` to the backend
- The backend reads the scan workspace read-only; the worker is the only writer and has no network port
- Alert flow: application - Prometheus - Alertmanager - protected webhook - incident engine
- Modular monolith with one restricted worker instead of many microservices

**Visual:** [`../diagrams/system-architecture.md`](../diagrams/system-architecture.md); keep [`../diagrams/deployment.md`](../diagrams/deployment.md) as a backup slide.

**Speaker notes:** Trace one request and one alert across the diagram. Explain why the worker is a separate container: a fault in the public API can only queue a request, and the worker runs it only if an Administrator approved it. Mention the container hardening of the worker (read-only root filesystem, no capabilities), which the backend and the demonstration application share.

---

## Slide 8 - Technology Stack

**Presenter:** Member 1

- Frontend: React 18, Vite, Tailwind CSS, React Router, Axios, Recharts
- Backend: Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, bcrypt, JWT
- Data and monitoring: PostgreSQL 16, Prometheus, Alertmanager
- Deployment: Docker Compose, Caddy reverse proxy
- Assistant: BM25 retrieval in plain Python; Google Gemini through the official SDK (optional); tests with pytest and Vitest

**Visual:** layered stack diagram (browser, reverse proxy, API, worker, database, monitoring) with the technology names on each layer.

**Speaker notes:** Give one reason for each main choice: FastAPI for typed validation and automatic API documentation, PostgreSQL for partial unique indexes and row locking, Prometheus because it is a widely used open-source, pull-based metrics system with its own alert rules. Point out that no extra infrastructure such as a message broker or a vector database is used, and say why in one sentence.

---

## Slide 9 - Monitoring and Incidents

**Presenter:** Member 3

- Metrics are measured, not generated: request counters, a latency histogram, process CPU and memory; a synthetic load generator provides traffic
- Five alert rules: unavailable, 5xx error rate, p95 latency, CPU, memory
- Webhook protected by a shared token; firing, repeated and resolved alerts are handled
- Deduplication by alert fingerprint, enforced by a partial unique index in PostgreSQL
- Lifecycle OPEN - ACKNOWLEDGED - IN_PROGRESS - RESOLVED - CLOSED; resolution needs evidence

**Visual:** the Monitoring page during a controlled outage (gap in the charts, target Down) and the incident detail page with its timeline; [`../diagrams/incident-lifecycle.md`](../diagrams/incident-lifecycle.md) as the diagram.

**Speaker notes:** Explain honestly that the traffic is synthetic but every measurement is real, and that a missing value is displayed as "Unavailable". Describe what happens when Alertmanager repeats a notification: the counter on the same incident increases. Explain that a person cannot resolve an incident while Prometheus still reports the alert as firing.

---

## Slide 10 - Security Scanning

**Presenter:** Member 4

- Scope: local YAML files in the `vigilops/v1` schema inside an authorised workspace - not a live cloud account
- SEC-001 public storage, SEC-002 missing encryption, SEC-003 wildcard IAM, SEC-004 open sensitive ports, SEC-005 privileged container
- Rules are pure functions; the same file always gives the same findings
- Stable finding key: file + rule + resource; repeated scans update, never duplicate
- Finding states: OPEN, REMEDIATION_PENDING, RESOLVED (only by a scan), ACCEPTED_RISK

**Visual:** the Security Findings page (Findings tab) after a scan of the sample configuration, and the detail page of the SEC-001 finding; [`../diagrams/security-scanning-flow.md`](../diagrams/security-scanning-flow.md).

**Speaker notes:** State the scope limitation first so that it is not discovered by the examiner. Explain the input safety measures: plain file names only, path checks against traversal and symbolic links, size limit, no YAML anchors, safe loading. Mention that a finding is never deleted and reopens automatically if the violation returns.

---

## Slide 11 - Remediation

**Presenter:** Member 4

- Two allowlisted actions: ACTION-001 recover the demonstration application; ACTION-002 correct public storage configuration
- Workflow: PENDING_APPROVAL - APPROVED - QUEUED - RUNNING - VERIFYING - SUCCEEDED or FAILED
- Operator cannot approve (HTTP 403); an Administrator cannot approve their own request by default
- Worker claims work with `SELECT ... FOR UPDATE SKIP LOCKED` and refuses any request without a recorded approval
- Success only after verification: health checks plus Prometheus for ACTION-001; a fresh scan for ACTION-002

**Visual:** [`../diagrams/remediation-sequence.md`](../diagrams/remediation-sequence.md) and the remediation detail page showing the workflow stepper, the configuration diff and the verification checks.

**Speaker notes:** Emphasise that a request contains only an action code and a justification; there is no field for a command. Explain why approval and dispatch are separate steps. State the limit of ACTION-001: it cannot start a stopped container because the platform has no Docker or host access by design.

---

## Slide 12 - VigilAI

**Presenter:** Member 5

- Floating chat widget on every page; read-only; answers only questions about the platform
- Backend decides the scope before any model call: in scope, out of scope, privileged action, secret request, prompt injection
- Retrieval-augmented: BM25 over the Markdown knowledge base plus fixed, permission-checked live-data functions
- Model output is validated and sanitised; the browser renders it as text
- If Gemini is not configured or fails, the same documentation and live data are returned directly (documentation fallback)

**Visual:** [`../diagrams/vigilai-architecture.md`](../diagrams/vigilai-architecture.md) and a screenshot of the widget answering "What does SEC-001 mean?" with its source tags.

**Speaker notes:** Explain why the assistant is not allowed to execute remediation: a language model is not deterministic and can be manipulated by text, so all changes go through the approval workflow. Explain why BM25 was chosen over a vector database for a small corpus with exact identifiers. State clearly what was verified for live Gemini generation: with a real API key and the default model, 9 of 9 platform questions were answered by the model and passed a grounding check, six refusal messages were refused by the backend without a call to the model, and a model name that does not exist and an invalid API key each produced the documentation fallback (`scripts/verify_gemini_live.py`, `docs/evidence/gemini-live.json`). State equally clearly what was not: real quota exhaustion was never observed and is covered only by tests with a stubbed SDK client, and answer quality was checked on a small question set with one model, not by a systematic human evaluation.

---

## Slide 13 - Testing and Results

**Presenter:** Member 5

- Levels: unit, API integration (SQLite and PostgreSQL), PostgreSQL-specific, frontend component, configuration validation, stack verification, end-to-end
- Three end-to-end demonstrations run against the real stack by `scripts/run_e2e_demos.py`
- Results table (measured values from the evaluation document): alert-to-incident time, deduplication, scanner detection and false positives, remediation execution and recovery time, verification success, assistant in-scope and out-of-scope behaviour, RBAC enforcement
- Not verified: real Gemini quota exhaustion; public HTTPS deployment; load

**Visual:** the metric table from Chapter 9 of the report with values filled in from [`../evaluation.md`](../evaluation.md), and a screenshot of the end-to-end script output from [`../verification-report.md`](../verification-report.md).

**Speaker notes:** For each value say how it was measured, for example that alert-to-incident time runs from fault injection to the incident appearing through the API. Explain that this time has a lower bound set by the alert rule's `for` duration and Alertmanager's group wait. Do not round or improve any value; show the date and machine of the run.

---

## Slide 14 - Limitations and Future Scope

**Presenter:** Member 4

- Scanner reads local YAML in its own schema; no AWS integration; only two automated actions
- ACTION-001 cannot start a stopped container; rate limiting is in process, so the backend is a single instance
- Synthetic workload; live AI answers checked on a small question set with one model, real quota exhaustion not observed; HTTPS overlay not deployed
- Future: optional read-only AWS integration (EC2, S3, IAM, CloudWatch) - any real change to a cloud account would need a separately reviewed security design and explicit authorization
- Future: more rules and actions, exporters, notifications, multi-factor authentication, shared rate-limit store, vector retrieval, Kubernetes

**Visual:** two-column table "limitation today" and "planned enhancement" from [`future-scope.md`](future-scope.md).

**Speaker notes:** Present the limitations as design boundaries with reasons, not as apologies. For each future item give the reason it is out of scope today. Keep the AWS point precise: read-only first, and no mutation without a separate security review.

---

## Slide 15 - Conclusion

**Presenter:** Member 5

- One platform connects real detection, deduplicated incidents, deterministic findings, controlled and verified remediation, and an audit trail
- Safety by design: allowlist, two-person approval, isolated worker, evidence-based success, server-side roles
- An assistant can be useful without being able to act, and keeps working without the model provider
- Lesson from the prototype audit: test the running system, and never display a value that was not measured
- Thank you - questions and live demonstration

**Visual:** the closed-loop diagram from slide 2 with each stage ticked, and the repository structure as a small inset.

**Speaker notes:** Return to the problem statement and show that each of its four points was addressed. Repeat the two unverified items once more so the conclusion is honest. Invite questions and hand over to the live demonstration.

---

## Backup slides (optional, not counted in the 15)

| Backup slide | Content | Source |
|---|---|---|
| B1 | Entity-relationship diagram and key constraints | [`../diagrams/er-diagram.md`](../diagrams/er-diagram.md), report Chapter 6 |
| B2 | Permission matrix | Settings, tab Permissions; `backend/app/core/permissions.py` |
| B3 | BM25 formula and scope classification order | report Chapter 7 |
| B4 | Deployment: local stack and production overlay | [`../diagrams/deployment.md`](../diagrams/deployment.md), [`../deployment.md`](../deployment.md) |
| B5 | Use-case and data-flow diagrams | [`../diagrams/use-case.md`](../diagrams/use-case.md), [`../diagrams/data-flow.md`](../diagrams/data-flow.md) |
