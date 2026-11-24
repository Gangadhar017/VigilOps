# VigilOps: Secure Cloud Operations - Synopsis Traceability

This document compares the approved project synopsis with what was built. For every commitment in the synopsis it gives a status, what exists in the repository, and where to look.

## 1. Introduction

The approved synopsis was written under the project's earlier name, CloudShield (file "CloudShield Project Synopsis", 16 pages). The project is now called VigilOps: Secure Cloud Operations. `README.md` says the project "was upgraded from an earlier prototype called CloudShield", and `docs/phase-0-audit.md` records what that prototype contained and what was rebuilt.

The tables in section 3 follow the synopsis in its own order and use its own wording. Each row gives the page of the synopsis. The repository was checked on 2026-11-25.

| Status | Meaning |
|---|---|
| Met | The code or the documents show the item as the synopsis describes it. |
| Partly met | Part of the item exists. The missing part is named in the row. |
| Changed | The item exists in a different form: a different design, name or value. |
| Not done | The item does not exist in the repository. |
| Not verified | The repository cannot confirm the item either way, for example team process. |

How to read the tables:

- Each row has a label (for example **O3** or **M4.2**). Section 4 uses these labels.
- All paths are relative to the repository root. Page names are the names shown in the application's sidebar.
- Test results and measurements are quoted from the recorded documents, with their dates. No test was run again for this document.
- The synopsis repeats some commitments in several sections. Each repetition has its own row with the same status, so section 2 counts rows, not distinct features.
- `[TO FILL]` marks a fact that only the team can supply. All of them are listed again in section 6.

## 2. Summary of statuses

| Status | Rows |
|---|---|
| Met | 188 |
| Partly met | 25 |
| Changed | 23 |
| Not done | 5 |
| Not verified | 7 |
| **Total** | **248** |

Rows per table:

| Table | Met | Partly met | Changed | Not done | Not verified | Rows |
|---|---|---|---|---|---|---|
| 3.1 Title line | 3 | 0 | 1 | 0 | 1 | 5 |
| 3.2 Abstract | 6 | 0 | 0 | 0 | 0 | 6 |
| 3.3 Introduction and problem statement | 3 | 0 | 0 | 0 | 0 | 3 |
| 3.4 Objectives | 8 | 0 | 0 | 0 | 0 | 8 |
| 3.5 Scope | 11 | 1 | 0 | 3 | 0 | 15 |
| 3.6 Existing systems and contribution | 1 | 1 | 0 | 0 | 0 | 2 |
| 3.7 Users and roles | 2 | 1 | 0 | 0 | 0 | 3 |
| 3.8 Use cases and acceptance criteria | 13 | 1 | 0 | 0 | 0 | 14 |
| 3.9 Non-functional requirements | 7 | 0 | 0 | 0 | 0 | 7 |
| 3.10 System architecture | 21 | 2 | 1 | 0 | 0 | 24 |
| 3.11 Technology stack | 11 | 4 | 2 | 1 | 0 | 18 |
| 3.12 Module design | 37 | 3 | 7 | 0 | 0 | 47 |
| 3.13 Database design | 4 | 0 | 4 | 0 | 0 | 8 |
| 3.14 API design | 6 | 0 | 7 | 0 | 0 | 13 |
| 3.15 Security and safety considerations | 8 | 0 | 0 | 0 | 0 | 8 |
| 3.16 Testing and evaluation plan | 17 | 2 | 0 | 0 | 0 | 19 |
| 3.17 Implementation plan | 9 | 2 | 0 | 0 | 2 | 13 |
| 3.18 Team division | 1 | 0 | 0 | 0 | 2 | 3 |
| 3.19 Deliverables | 4 | 2 | 0 | 0 | 0 | 6 |
| 3.20 Risks and mitigation | 3 | 2 | 0 | 0 | 2 | 7 |
| 3.21 Limitations, future scope and expected outcomes | 6 | 0 | 0 | 1 | 0 | 7 |
| 3.22 Likely questions from the guide | 7 | 2 | 1 | 0 | 0 | 10 |
| 3.23 Tools and documentation to reference | 0 | 2 | 0 | 0 | 0 | 2 |
| **Total** | **188** | **25** | **23** | **5** | **7** | **248** |

Reading the numbers:

- All eight objectives (O1 to O8) and all seven mandatory scope items (SM1 to SM7) are Met.
- Of the four optional scope items, three are Not done and one is Partly met.
- 19 of the 23 Changed rows come from three groups: API paths and database tables that differ from the proposed ones (11 rows), the worker having no Docker access, so that recovery replaced restart and two check actions became verification steps (6 rows), and incident handling (2 rows).
- The 7 Not verified rows are about the team and its process (duration, reviews, weekly routine), which a repository cannot prove.

## 3. Traceability tables

### 3.1 Title line (page 1)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **T1.** Title: "CloudShield: Design and Development of an Integrated Cloud Security, Monitoring and Auto-Remediation Platform" (p. 1) | Changed | The project is now named "VigilOps: Secure Cloud Operations". Monitoring, security scanning and approval-based remediation are still its subject. | `README.md` (title, "Project introduction"); `PROJECT_TITLE` in `backend/app/core/config.py`; `docs/phase-0-audit.md` |
| **T2.** "Domain: Cloud Computing, Cloud Security and DevOps" (p. 1) | Met | A containerised stack, Prometheus monitoring, configuration security rules and a CI workflow. | `compose.yaml`; `monitoring/`; `security-rules/`; `.github/workflows/ci.yml` |
| **T3.** "Team: 4 students" (p. 1) | Met | The team has four members; the team confirmed this on 2026-11-25. `README.md` says "built by a team of four students" and `docs/college/team-responsibilities.md` describes a four-member ownership. (Earlier versions of both documents said five; that was corrected.) | `README.md` line 5; `docs/college/team-responsibilities.md` |
| **T4.** "Duration: 24 weeks" (p. 1) | Not verified | The repository does not record the project's duration. Its own records of the VigilOps build are dated 2026-11-23 and 2026-11-24. [TO FILL: state the actual duration and dates of the work] | `docs/phase-0-audit.md`; `docs/verification-report.md`; `docs/evidence/` |
| **T5.** "Mandatory cloud spend: ₹0" (p. 1) | Met | The stack runs on one machine with Docker Compose. No cloud account or paid service is needed. The Gemini key and the free hosting plans are optional. | `README.md` ("Prerequisites", "Gemini API setup"); `docs/verification-report.md` criterion 30 |

### 3.2 Abstract (Section 1, page 1)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **A1.** "monitors application health and resource usage, detects selected security misconfigurations, manages incidents, and supports controlled, approval-based automated remediation" (p. 1) | Met | All four functions exist in one web application. Details are in tables 3.4 and 3.11. | `README.md` ("Features"); pages Overview, Monitoring, Incidents, Security Findings, Remediation |
| **A2.** "Metrics are collected with Prometheus, security policies are evaluated by a rule-based Python engine" (p. 1) | Met | Prometheus scrapes the application every 5 seconds. The scanner is Python code with five fixed rules. | `monitoring/prometheus.yml`; `backend/app/security_scanner/` |
| **A3.** "presented through a React dashboard backed by a FastAPI service and a PostgreSQL database" (p. 1) | Met | React 18 frontend, FastAPI backend, PostgreSQL 16. | `frontend/src/`; `backend/app/main.py`; `compose.yaml` (service `postgres`) |
| **A4.** "Corrective actions are limited to a fixed allowlist, require authorization, are verified after execution and are recorded in an audit log" (p. 1) | Met | Two allowlisted actions. An Administrator approves and dispatches. The worker verifies before it reports success. Each step writes an audit event. | `backend/app/services/remediation_catalog.py`; `backend/app/workers/verification.py`; `backend/app/services/audit_service.py` |
| **A5.** "The core system runs in a local Docker Compose test environment, so no paid cloud infrastructure is required" (p. 1) | Met | One command starts eight Compose services (seven long-running, one that runs once). | `compose.yaml`; `README.md` ("Local execution") |
| **A6.** "evaluated through controlled application failures, deliberately insecure configurations, access-control tests and measured remediation outcomes" (p. 1) | Met | All four kinds of evaluation are recorded with measured values. | `docs/evaluation.md` sections 2.1 to 2.7; `docs/evidence/` |

### 3.3 Introduction and problem statement (Sections 2 and 3, pages 1 and 2)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **I1.** One closed loop: "detect, create an incident, propose an action, approve, execute, verify and audit" (p. 1) | Met | For alerts the whole loop exists: alert, incident, recommended action, request, approval, dispatch, execution, verification, audit. For a security finding the same loop starts from the finding and no incident is created (see M3.3). | `docs/diagrams/remediation-sequence.md`; `docs/evidence/e2e-results.json` |
| **I2.** "built with free and open-source tools and demonstrated in a safe local test environment" (p. 1) | Met | The core stack is open source and local. One later addition is optional and is not open source: VigilAI can call the hosted Google Gemini API when a key is set (section 5). | `README.md` ("Technology stack"); `.env.example` (`GEMINI_API_KEY=` is empty) |
| **P1.** "a unified platform for monitoring, security checks, incident management and controlled remediation in a local test environment" (p. 2) | Met | One web application, one API and one database cover the four areas. | `README.md` ("Project introduction"); `docs/architecture.md` |

### 3.4 Objectives (Section 4, page 2)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **O1.** "Build a web dashboard that shows application health, resource usage, incidents and security findings." (p. 2) | Met | The Overview page shows counts of active incidents and open findings, live health and metrics of the monitored resources, and charts. Separate pages show details. | Page Overview (`frontend/src/pages/Dashboard.jsx`); `Monitoring.jsx`, `Incidents.jsx`, `Findings.jsx` |
| **O2.** "Collect real metrics (CPU, memory, health, request count, errors, latency) from a test application using Prometheus." (p. 2) | Met | The application counts every request, measures its duration in a histogram, and exposes the process's own CPU and memory counters. Health is Prometheus's scrape result (`up`). No value is generated or substituted. | `test-app/app.py`; `monitoring/prometheus.yml`; `backend/app/services/monitoring_service.py` |
| **O3.** "Generate alerts from configurable threshold rules and convert them into deduplicated incidents." (p. 2) | Met | Five alert rules. Alertmanager posts to a token-protected webhook. One active incident per alert fingerprint, enforced by a partial unique index. | `monitoring/alert_rules.yml`; `backend/app/services/incident_service.py`; `backend/app/models/models.py` (`uq_incidents_active_fingerprint`) |
| **O4.** "Implement a rule-based security scanner with at least five predefined checks for test configuration files." (p. 2) | Met | Rules SEC-001 to SEC-005 on YAML files in the scan workspace. | `backend/app/security_scanner/rules.py`; `security-rules/policies.yaml` |
| **O5.** "Implement an approval-based remediation workflow with an allowlist of actions, timeouts and verification." (p. 2) | Met | Allowlist of two actions. Request, approval and dispatch are separate steps. Action timeout 30 seconds, verification timeout 150 seconds (defaults). Success only after verification. | `backend/app/services/remediation_service.py`; `backend/app/workers/remediation_worker.py`; `backend/app/core/config.py` |
| **O6.** "Demonstrate two end-to-end scenarios: application recovery and configuration correction." (p. 2) | Met | Demo 1 (application failure and recovery) and Demo 2 (public storage correction). A scripted run on 2026-11-23 passed 55 of 55 checks. Recovery is done through a recovery endpoint, not a restart (see DA6). | `README.md` ("Demonstration instructions"); `scripts/run_e2e_demos.py`; `docs/evidence/e2e-results.json` |
| **O7.** "Provide role-based access control and a complete audit trail of remediation attempts." (p. 2) | Met | Two roles with a permission matrix checked in the backend. Every remediation step is an audit event with one correlation ID per request. | `backend/app/core/permissions.py`; `backend/app/services/audit_service.py`; page Audit Logs |
| **O8.** "Deliver automated tests, a CI pipeline, reproducible setup instructions and a measured evaluation." (p. 2) | Met | Backend, frontend and browser test suites, a GitHub Actions workflow, a setup guide and an evaluation document with measured values. | `backend/tests/`; `frontend/src/test/`; `tests/e2e/`; `.github/workflows/ci.yml`; `docs/setup.md`; `docs/evaluation.md` |

### 3.5 Scope (Section 5, pages 2 and 3)

Mandatory ("must be completed"):

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **SM1.** "Login with two roles (Administrator and Operator)." (p. 2) | Met | Sign-in with e-mail and password. Roles `admin` and `operator`. No self-registration. | Page Sign in (`frontend/src/pages/Login.jsx`); `backend/app/api/auth.py`; `Role` in `backend/app/models/models.py` |
| **SM2.** "Prometheus metrics collection and configurable alert rules." (p. 2) | Met | Four scrape jobs and five alert rules in version-controlled files. | `monitoring/prometheus.yml`; `monitoring/alert_rules.yml` |
| **SM3.** "Alert-to-incident creation with deduplication." (p. 2) | Met | A real repeated notification after 122 seconds updated the same incident and raised its counter from 1 to 2. | `docs/evaluation.md` section 2.3; `backend/tests/integration/test_incidents.py` |
| **SM4.** "Five security rules with persistent findings and repeat-scan comparison." (p. 2) | Met | Findings are stored with a stable key. A later scan marks a finding RESOLVED when the rule no longer matches, reopens it when it matches again, and never duplicates it. | `backend/app/services/scan_service.py`; `backend/tests/integration/test_scanning.py` |
| **SM5.** "Incident workflow with remediation request, approval, execution and verification." (p. 2) | Met | From the incident page: Request remediation, then Approve and Execute by an Administrator, then worker execution and three verification checks. | Pages Incidents and Remediation; `backend/app/api/remediation.py`; `backend/app/workers/verification.py` |
| **SM6.** "Two verified remediation scenarios, including a deliberately failed run." (p. 2) | Met | Both scenarios succeed with verification (O6). A deliberately failed run is recorded: the application container was stopped, ACTION-001 ended FAILED after three unanswered recovery calls, the incident stayed OPEN, and after the container was started again outside the platform the retry SUCCEEDED. 24 checks passed, 0 failed. Measured: stop to incident 36.3 s, dispatch to FAILED 22.6 s, retry to verified result 12.4 s. The failed run covers the application scenario. For the configuration scenario a failed verification is covered by an automated test only. | `scripts/run_failed_remediation_demo.py`; `docs/evidence/failed-remediation.json` (run of 2026-11-24); `backend/tests/integration/test_remediation.py` |
| **SM7.** "Audit log, automated tests and GitHub Actions CI." (p. 2) | Met | Append-only audit table, test suites, and a workflow with five job definitions (the backend job runs twice, on SQLite and on PostgreSQL). | `backend/app/models/models.py` (`AuditEvent`); `backend/tests/`; `.github/workflows/ci.yml` |

Optional ("only if time remains"):

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **SO1.** "Read-only AWS integration with Boto3, tested first against the moto mocking library." (p. 2) | Not done | No AWS code, no Boto3 and no moto in the dependencies. The scanner reads local YAML files only. | `backend/requirements.txt`; `README.md` ("Limitations"); `docs/college/future-scope.md` section 1 |
| **SO2.** "Anomaly detection on CPU and latency data (rolling z-score or Isolation Forest)." (p. 3) | Not done | Detection uses fixed thresholds in Prometheus alert rules only. No anomaly detection code exists. | `monitoring/alert_rules.yml` |
| **SO3.** "Automatic execution of explicitly configured low-risk actions after the approval flow is stable." (p. 3) | Not done | Every execution needs an approval and a separate dispatch by an Administrator. The three runtime settings contain no automatic-execution option. | `backend/app/services/remediation_service.py`; `backend/app/services/settings_service.py` |
| **SO4.** "Deployment of the same Compose stack to a single cloud VM." (p. 3) | Partly met | A production overlay for the same Compose file and a deployment guide for a Linux VM exist. The overlay was started only on the development machine with `VIGILOPS_DOMAIN=localhost`. It was not run on a cloud VM or a public domain. A second, different deployment (one container on Render plus Vercel) was verified locally and in CI. The owner created the Render and Vercel deployment on 2026-11-24. On 2026-11-25 its health endpoint answered through both addresses and its public pages (the product page and the storefront) worked in a browser; the demonstrations were not run against it. [TO FILL: the public address, if the team wants to state it] | `compose.prod.yaml`; `docs/deployment.md` ("What was and was not verified"); `docs/deployment-render-vercel.md`; `render.yaml`; `frontend/vercel.json`; `docs/verification-report.md` sections 4, 6 and 8 |

Out of scope (the row is Met when the limit was kept):

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **SX1.** "Scanning production systems or any resource without explicit authorization." (p. 3) | Met | The scanner reads only plain `.yaml` or `.yml` files directly inside the scan workspace. Other paths and symbolic links are refused. | `resolve_target` in `backend/app/services/scan_service.py` |
| **SX2.** "A complete cloud security audit or compliance certification." (p. 3) | Met | Five rules. The API and the documents state that this is not a live cloud assessment. | `security-rules/policies.yaml` (header); `README.md` ("Limitations") |
| **SX3.** "Arbitrary command execution, or LLM-generated commands." (p. 3) | Met | A request carries only an action code. No handler runs a shell command. VigilAI is read-only and refuses instructions to act before any model is called. | `backend/app/workers/actions.py`; `backend/app/assistant/scope.py` |
| **SX4.** "Enterprise-grade multi-tenancy and fine-grained permissions." (p. 3) | Met | Two fixed roles and one tenant. | `backend/app/core/permissions.py`; `docs/architecture.md` ("Known limitations") |

### 3.6 Existing systems and contribution (Section 6, page 3)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **G1.** Contribution: "the integrated closed loop of detection, incident, approval, action, verification and audit in one application, with safety controls that are visible and testable" (p. 3) | Met | The loop runs in one application. The controls are covered by tests (approval enforced, worker refuses unapproved requests, operator refused with HTTP 403). | `docs/verification-report.md` criteria 16 to 22; `backend/tests/integration/test_remediation.py` |
| **G2.** Comparison with "Prometheus + Alertmanager", "AWS CloudWatch", "Prowler, Checkov", "Rundeck, StackStorm" (p. 3) | Partly met | The report (Chapter 3) and its outline compare VigilOps with Prometheus, Alertmanager, Grafana, AWS Config, Checkov, tfsec, PagerDuty and Splunk. AWS CloudWatch, Prowler, Rundeck and StackStorm are not named there (text search on 2026-11-25). | `docs/college/project-report.md` Chapter 3; `docs/college/project-report-outline.md` section 3.1 |

### 3.7 Users and roles (Section 7, page 4)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **R1.** Administrator: "Manages users, policies and monitoring configuration; approves remediation; views all audit logs" (p. 4) | Partly met | The Administrator manages users, changes three runtime settings, approves, rejects and dispatches remediation, and sees all audit events. Security policies and monitoring configuration cannot be managed in the application: they are version-controlled files. | Page Settings (tabs Users and Platform); `backend/app/api/users.py`; `backend/app/services/settings_service.py`; `security-rules/policies.yaml`; `monitoring/` |
| **R2.** Operator: "Views metrics, findings and incidents; acknowledges incidents; requests permitted remediation actions" (p. 4) | Met | All of these, and also: run a scan, comment on and resolve an incident, cancel own request. | `README.md` ("User roles"); `backend/app/core/permissions.py` |
| **R3.** "Only two roles are used in version one. Role checks are enforced on the backend, not just hidden in the UI." (p. 4) | Met | Every protected endpoint has a permission check. A refused call returns HTTP 403 and is audited. An automated test sends an Operator to 11 Administrator-only endpoints and gets 403 each time. | `require_permission` in `backend/app/core/permissions.py`; `backend/tests/integration/test_auth_rbac.py`; `docs/evaluation.md` section 2.7 |

### 3.8 Use cases and acceptance criteria (Section 8, pages 4 and 5)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **U1.** "Log in and view the dashboard. Authenticated users see resource counts, open incidents, recent findings and metric charts." (p. 4) | Met | The Overview page shows each monitored resource with its status and live metrics, the number of active incidents, open findings by severity with the latest scan, and two time-series charts. It shows the resources themselves, not a single resource count, and finding counts, not a list of recent findings. | Page Overview (`frontend/src/pages/Dashboard.jsx`); `GET /api/dashboard/summary` |
| **U2.** "Monitor a test application. CPU, memory, health, request and latency data are collected and displayed." (p. 4) | Met | The Monitoring page shows availability, request rate, 4xx and 5xx error rate, p95 latency, CPU, memory and uptime, with charts from 5 minutes to 6 hours. | Page Monitoring; `backend/app/api/monitoring.py` |
| **U3.** "Alert on threshold violation. A configured rule fires and an alert reaches CloudShield." (p. 4) | Met | Alertmanager delivers firing and resolved alerts to `POST /api/alerts/webhook`. | `monitoring/alertmanager.yml`; `backend/app/api/monitoring.py` |
| **U4.** "Scan configuration files. The scanner evaluates test configurations and stores findings with evidence." (p. 4) | Met | Each finding stores the matched values as evidence, the resource and the file. | Page Security Findings; `SecurityFinding.evidence` in `backend/app/models/models.py` |
| **U5.** "Manage incidents. Users list incidents, open details, see evidence and acknowledge them." (p. 4) | Met | List with filters, detail page with alert labels, timeline and runbook, and the Acknowledge button. | Pages Incidents and incident detail; `backend/app/api/incidents.py` |
| **U6.** "Approve and execute remediation. An authorized user approves an allowlisted action, which then runs and is verified." (p. 4) | Met | Approve and Execute are two buttons for the Administrator. The worker runs the action and verifies it. | Page Remediation (request detail); `backend/app/api/remediation.py` |
| **U7.** "Review audit records. Users confirm who requested, approved and executed each action and what the result was." (p. 4) | Met | The Audit Logs page filters by correlation ID and shows actor, action and outcome for each step. | Page Audit Logs; `backend/app/api/audit.py` |
| **AC1.** Monitoring: "CPU, memory and application health are displayed from real data" (p. 4) | Met | Values come from Prometheus queries at request time. A missing value is shown as "Unavailable". | `backend/app/services/monitoring_service.py`; `docs/verification-report.md` criterion 8 |
| **AC2.** Alerting: "A deliberately triggered threshold violation creates an incident" (p. 4) | Met | The outage rule and the four other rules each opened an incident on the running stack. | `docs/evidence/alert-rules.json`; `docs/evaluation.md` sections 2.1 and 2.2 |
| **AC3.** Security: "At least five predefined rules are implemented, each with positive and negative tests" (p. 5) | Met | One insecure and one secure fixture per rule, checked by parametrised tests. | `security-rules/samples/insecure/`; `security-rules/samples/secure/`; `backend/tests/unit/test_scanner.py` |
| **AC4.** Remediation: "Two distinct workflows work end to end" (p. 5) | Met | ACTION-001 for an incident and ACTION-002 for a finding. | `docs/evidence/e2e-results.json`; `tests/e2e/specs/platform.spec.js` (Demo 2 through the browser) |
| **AC5.** Authorization: "Unauthorized users cannot execute remediation" (p. 5) | Met | Operator approval returns 403. Execute before approval returns 409. The worker refuses a queued request without a recorded approval. | `docs/evaluation.md` section 2.7; `claim_next` in `backend/app/workers/remediation_worker.py` |
| **AC6.** Audit: "Every remediation attempt records actor, action and result" (p. 5) | Met | Audit events have actor, action and outcome (SUCCESS, FAILURE or DENIED). | `AuditEvent` in `backend/app/models/models.py`; `docs/evidence/failed-remediation.json` checks 10 and 15 |
| **AC7.** Deployment: "A teammate can start the system using only the README" (p. 5) | Partly met | A fresh installation was done on the development machine, and the CI workflow builds and starts the stack from a clean checkout on a GitHub Ubuntu runner. A start by a second team member on their own machine is not recorded. [TO FILL: record one clean start by another member, with date and machine] | `README.md` ("Local execution"); `docs/verification-report.md` sections 1, 4 and 6 |

### 3.9 Non-functional requirements (Section 9, page 5)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **N1.** Security: "Hashed passwords, backend role checks, restricted CORS, no secrets in the repository, safe error responses." (p. 5) | Met | bcrypt hashes, a backend permission matrix, CORS off unless origins are listed, secrets read from `.env` (ignored by Git), errors as JSON without stack traces. The Git history was not inspected for this document. | `backend/app/core/security.py`; `backend/app/main.py`; `.gitignore`; `.env.example` |
| **N2.** Reliability: "Duplicate alerts do not create duplicate incidents; failed actions leave the incident open." (p. 5) | Met | Both are tested and were observed on the running stack. | `backend/tests/integration/test_incidents.py`; `docs/evidence/failed-remediation.json` check 9 |
| **N3.** Safety: "Remediation is restricted to a named test environment and an allowlist of actions." (p. 5) | Met | ACTION-001 applies only to incidents on the demonstration application. ACTION-002 applies only to files named in `REMEDIATION_WRITABLE_TARGETS`. | `backend/app/services/remediation_catalog.py`; `backend/app/workers/actions.py` |
| **N4.** Reproducibility: "The full stack starts from documented steps using Docker Compose." (p. 5) | Met | `docker compose up --build -d` after copying `.env.example`. | `README.md`; `docs/setup.md`; `compose.yaml` |
| **N5.** Maintainability: "Separate frontend, backend, monitoring, security-rule and remediation modules; configurable thresholds and rules." (p. 5) | Met | Separate directories for each module. Thresholds are in `monitoring/alert_rules.yml`. Rule text and severities are in `security-rules/policies.yaml`. The detection logic itself is Python code (see M2.6). | `frontend/`; `backend/app/`; `monitoring/`; `security-rules/`; `backend/app/workers/` |
| **N6.** Usability: "Clear status, severity and evidence on every page; understandable error messages." (p. 5) | Met | Status and severity badges, evidence sections, and loading, empty and error states on each page. | `frontend/src/components/StatusBadge.jsx`; `frontend/src/components/States.jsx`; `docs/screenshots/` |
| **N7.** Honesty of data: "Development fixtures are labelled, and demo values are never presented as live measurements." (p. 5) | Met | An incident opened during an injected fault carries the badge "Simulated fault". No metrics, incidents or findings are seeded. The documents say that the application's traffic is synthetic and its measurements are real. | `Incident.is_simulated` in `backend/app/models/models.py`; `frontend/src/components/DataSourceTag.jsx`; `README.md` ("Limitations") |

### 3.10 System architecture (Section 10, pages 5 to 7)

Components:

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **C1.** React dashboard: "Login, dashboard, resources, findings, incident details, approvals" (p. 6) | Met | Pages Sign in, Overview, Monitoring, Incidents, Security Findings, Remediation, Audit Logs, VigilAI / Help and Settings. There is no separate Resources page: the monitored resources are on Overview and Monitoring. | `frontend/src/App.jsx`; `frontend/src/pages/` |
| **C2.** FastAPI backend: "Authentication, RBAC, REST APIs, incident logic, orchestration" (p. 6) | Met | One backend package with routers, services and the permission matrix. | `backend/app/api/`; `backend/app/services/` |
| **C3.** PostgreSQL: "Users, resources, findings, incidents, remediation jobs, audit logs" (p. 6) | Met | PostgreSQL 16 holds all of these. Some table names differ (table 3.12). | `backend/app/models/models.py`; `backend/alembic/versions/0001_initial_schema.py` |
| **C4.** Prometheus: "Scrapes metrics, evaluates alert rules" (p. 6) | Met | Prometheus v2.51.0, scrape and evaluation interval 5 seconds. | `compose.yaml`; `monitoring/prometheus.yml` |
| **C5.** Alertmanager: "Routes fired alerts to the CloudShield webhook" (p. 6) | Met | One receiver: the backend webhook, with a bearer token read from a Docker secret. | `monitoring/alertmanager.yml` |
| **C6.** Security engine: "Loads YAML rules, parses test configs, produces findings" (p. 6) | Met | The catalog is loaded from YAML, files are parsed with `yaml.safe_load`, and violations become findings. | `backend/app/security_scanner/engine.py`; `backend/app/security_scanner/rules.py` |
| **C7.** Remediation worker: "Executes approved allowlisted actions, then verifies the result" (p. 6) | Met | A separate container with no network port, a read-only root file system and no Linux capabilities. | `compose.yaml` (service `worker`); `backend/app/workers/remediation_worker.py` |
| **C8.** Test application: "Small Python service with health and metrics endpoints and a failure-simulation mode" (p. 6) | Met | The monitored application is now OrbitCrate, a small storefront. It has `/health`, `/metrics` and five fault modes (outage, errors, latency, cpu, memory). Its storefront can be opened without an account at `/orbitcrate/`. | `test-app/app.py`; `test-app/static/`; `reverse-proxy/Caddyfile` |
| **C9.** Docker Compose: "Runs all services together as the local test environment" (p. 6) | Met | Services `postgres`, `workspace-init`, `backend`, `worker`, `test-app`, `prometheus`, `alertmanager`, `web`. | `compose.yaml` |
| **C10.** Diagram: "Prometheus <-- test app + exporters" (p. 5) | Partly met | Prometheus scrapes the test application, the backend, itself and Alertmanager. There are no exporters (see TS9). | `monitoring/prometheus.yml` |
| **C11.** Diagram: dashboard to backend over "HTTPS / JSON" (p. 5) | Partly met | JSON everywhere. The local stack uses plain HTTP on 127.0.0.1. HTTPS is provided by the production overlay through Caddy and was verified only on `localhost` with Caddy's internal certificate. | `reverse-proxy/Caddyfile`; `compose.prod.yaml`; `docs/verification-report.md` sections 4 and 6 |

Data flow, Scenario A (application recovery):

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **DA1.** "The test application is stopped or made unhealthy." (p. 6) | Met | An Administrator injects the `outage` fault: every endpoint answers HTTP 503. A real container stop is used in the failed-run demonstration. | Page Settings (tab Demo controls); `backend/app/api/demo.py`; `scripts/run_failed_remediation_demo.py` |
| **DA2.** "Prometheus detects repeated health-check failure and fires an alert." (p. 6) | Met | Rule `ApplicationUnavailable`: `up{job="demo-app"} == 0` for 15 seconds. The signal is a failed scrape of `/metrics`. | `monitoring/alert_rules.yml` |
| **DA3.** "Alertmanager sends the alert to the backend webhook." (p. 6) | Met | `POST /api/alerts/webhook`, protected by a shared token. | `monitoring/alertmanager.yml`; `backend/app/api/monitoring.py` |
| **DA4.** "The backend validates it, matches it to a resource, and creates or updates an incident (deduplicated by rule and resource)." (p. 6) | Met | The payload is validated by a schema. The resource is found from the `resource` or `job` label. The fingerprint is Alertmanager's, or a hash of the sorted labels, which include the rule name and the resource. | `_handle_firing` and `compute_fingerprint` in `backend/app/services/incident_service.py` |
| **DA5.** "An operator requests the restart action; an administrator approves it." (p. 6) | Met | The Operator requests ACTION-001 ("Recover monitored demonstration application"). The Administrator approves and then presses Execute. By default an Administrator cannot approve their own request. The action is not a restart (DA6). | `backend/app/services/remediation_service.py`; `docs/evidence/e2e-results.json` |
| **DA6.** "The worker restarts only the designated test service." (p. 6) | Changed | The worker does not restart a container or a process. ACTION-001 calls the application's token-protected endpoint `POST /internal/recover`, which re-initialises the service component and clears the fault. It cannot start a stopped container. | `recover_demo_application` in `backend/app/workers/actions.py`; `ServiceState.recover` in `test-app/app.py` |
| **DA7.** "The health endpoint is polled until recovery or timeout." (p. 6) | Met | Three consecutive successful readiness checks are required within 30 seconds. Then Prometheus must show a newer successful scrape and the alert must stop firing, within 150 seconds in total. | `verify_application_recovery` in `backend/app/workers/verification.py` |
| **DA8.** "The incident closes only if verification succeeds; the audit log records the outcome either way." (p. 6) | Met | After verification the incident becomes RESOLVED. After a failure it stays active. Both outcomes are audited. CLOSED is a later step by an Administrator. Other ways to resolve an incident are in M3.4. | `run_execution` in `backend/app/workers/remediation_worker.py`; `docs/evidence/failed-remediation.json` |

Data flow, Scenario B (configuration remediation):

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **DB1.** "The scanner evaluates an intentionally insecure test configuration and stores a finding with evidence." (p. 6) | Met | The sample file violates each of the five rules once. | `security-rules/samples/baseline/cloud-infrastructure.yaml`; page Security Findings |
| **DB2.** "A user requests the predefined correction; an administrator approves it." (p. 6) | Met | ACTION-002 can be requested for a SEC-001 finding only. | `action_for_finding` in `backend/app/services/remediation_catalog.py` |
| **DB3.** "The worker applies the correction to the approved test file only." (p. 7) | Met | The worker sets `public_access: false` and `acl: private` for one bucket in an allowlisted file and writes the file atomically. The backend container mounts the workspace read-only. | `fix_public_storage` in `backend/app/workers/actions.py`; `compose.yaml` |
| **DB4.** "The scanner runs again; the finding must be resolved for the action to count as successful." (p. 7) | Met | Three checks: a new scan completed, the rule no longer matches the resource, and the scan set the finding to RESOLVED. | `verify_storage_correction` in `backend/app/workers/verification.py` |
| **DB5.** "Before-and-after evidence and audit records are stored." (p. 7) | Met | The execution record stores the values before and after, both file hashes and a diff. | `RemediationExecution.execution_details` in `backend/app/models/models.py`; page Remediation (request detail) |

### 3.11 Technology stack (Section 11, pages 7 and 8)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **TS1.** Frontend: "React + Vite" (p. 7) | Met | React 18, Vite 5. | `frontend/package.json` |
| **TS2.** Styling: "CSS or Tailwind CSS" (p. 7) | Met | Tailwind CSS 3.4. | `frontend/package.json`; `frontend/tailwind.config.js` |
| **TS3.** Charts: "Recharts or Chart.js" (p. 7) | Met | Recharts. | `frontend/package.json`; `frontend/src/components/TimeSeriesChart.jsx` |
| **TS4.** Backend: "Python + FastAPI", with Pydantic validation and "interactive API docs at /docs" (p. 7) | Met | Python 3.11, FastAPI, Pydantic 2. `/docs` is on in development mode and off in production mode. | `backend/requirements.txt`; `api_docs_enabled` in `backend/app/core/config.py` |
| **TS5.** Database: "PostgreSQL" (p. 7) | Met | PostgreSQL 16. The test suite uses SQLite by default and also runs on PostgreSQL in CI. | `compose.yaml`; `.github/workflows/ci.yml` |
| **TS6.** ORM and migrations: "SQLAlchemy + Alembic" (p. 7) | Met | SQLAlchemy 2 models and one Alembic migration, applied when the backend starts. | `backend/app/models/models.py`; `backend/alembic/versions/0001_initial_schema.py` |
| **TS7.** Authentication: "Password hashing (bcrypt or Argon2) with JWT or secure session cookies" (p. 7) | Met | bcrypt and a signed JWT (HS256, 60 minutes by default) sent in the `Authorization` header. | `backend/app/core/security.py` |
| **TS8.** Monitoring: "Prometheus + Alertmanager" (p. 7) | Met | Prometheus v2.51.0 and Alertmanager v0.27.0. | `compose.yaml`; `monitoring/` |
| **TS9.** Metrics sources: "prometheus_client (Python), node_exporter or cAdvisor" (p. 7) | Partly met | `prometheus_client` is used in the application and in the backend. Neither node_exporter nor cAdvisor is used. CPU and memory are the application process's own counters, not host or container metrics. | `test-app/app.py`; `backend/app/core/metrics.py`; `compose.yaml` |
| **TS10.** Security engine: "Python, YAML rules (PyYAML safe loading), JSON parsing" (p. 7) | Partly met | Python, a YAML rule catalog and `yaml.safe_load`. JSON configuration files are not accepted: a scan target must be a `.yaml` or `.yml` file in the `vigilops/v1` schema. | `backend/app/security_scanner/engine.py`; `resolve_target` in `backend/app/services/scan_service.py` |
| **TS11.** Remediation: "Python worker using a fixed action registry; Docker SDK or a restricted wrapper" (p. 7) | Changed | A Python worker with a fixed registry of two handlers. It uses neither the Docker SDK nor a wrapper around Docker. It has no access to the Docker daemon. | `HANDLERS` in `backend/app/workers/actions.py`; `backend/requirements.txt` |
| **TS12.** Environment: "Docker + Docker Compose", "One command starts the whole stack" (p. 8) | Met | `docker compose up --build -d`. | `compose.yaml`; `README.md` |
| **TS13.** Testing: "Pytest, httpx test client, Vitest, React Testing Library, Playwright (optional)" (p. 8) | Met | pytest with FastAPI's test client (built on httpx), Vitest with Testing Library, and Playwright browser tests. | `backend/tests/conftest.py`; `frontend/package.json`; `tests/e2e/package.json` |
| **TS14.** Code quality: "Ruff or Flake8, ESLint" (p. 8) | Partly met | Ruff is configured and runs in CI. ESLint is not configured: there is no ESLint dependency, script or configuration file in `frontend/`. | `backend/ruff.toml`; `.github/workflows/ci.yml`; `frontend/package.json` |
| **TS15.** CI/CD: "GitHub Actions", "runs lint, tests and build on every pull request" (p. 8) | Met | The workflow runs on every pull request and on pushes to `main`, `develop` and `vigilops-upgrade`: backend lint and tests, frontend tests and build, configuration checks, image build and the demonstration scripts. The frontend has no lint step (TS14). | `.github/workflows/ci.yml` |
| **TS16.** Version control: "Git + GitHub with main, develop and feature branches" (p. 8) | Changed | Git and GitHub are used. The local record of the GitHub remote lists one branch, `main`. There is no `develop` branch and there are no feature branches. The local clone also holds `vigilops-upgrade` and a backup branch. | `.git/refs/remotes/origin/`; `.git/refs/heads/`; `.git/config` |
| **TS17.** Optional cloud: "Boto3 with moto" (p. 8) | Not done | Neither library is installed or used (see SO1). | `backend/requirements.txt`; `backend/requirements-dev.txt` |
| **TS18.** "The stack is frozen at the start of the project and not changed afterwards." (p. 8) | Partly met | The listed core technologies are all still in use. Not used: node_exporter or cAdvisor, the Docker SDK, ESLint, Boto3 and moto. Added: Caddy as reverse proxy, the Google Gen AI SDK for VigilAI, React Router and Axios. | `README.md` ("Technology stack"); `docs/phase-0-audit.md` section 4 |

### 3.12 Module design (Section 12, pages 8 to 10)

12.1 Monitoring and alert engine:

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **M1.1.** The test application "exposes a health endpoint, a Prometheus metrics endpoint, a request counter, a latency histogram and a controlled failure mode" (p. 8) | Met | `/health` and `/health/ready`, `/metrics`, `http_requests_total`, `http_request_duration_seconds`, and five fault modes behind a control token. | `test-app/app.py` |
| **M1.2.** "Prometheus scrapes it and, where practical, system exporters." (p. 8) | Partly met | Prometheus scrapes the application. No system exporter is used (TS9). | `monitoring/prometheus.yml` |
| **M1.3.** "Collected: CPU utilization, memory usage, application health, request count, error count and latency." (p. 8) | Met | Metric catalog: availability, request rate, 4xx and 5xx error rate, p95 latency, CPU usage, resident memory, uptime. | `METRIC_CATALOG` in `backend/app/services/monitoring_service.py` |
| **M1.4.** Rule "Application unavailable": "Health check fails repeatedly" (p. 8) | Met | `ApplicationUnavailable`: `up == 0` for 15 s, severity critical. | `monitoring/alert_rules.yml` |
| **M1.5.** Rule "High CPU": "CPU above 80% for a sustained interval" (p. 8) | Met | `HighCpuUsage`: more than 0.80 of one core for 30 s, severity high. | `monitoring/alert_rules.yml` |
| **M1.6.** Rule "High memory": "Memory above a configured threshold" (p. 8) | Met | `HighMemoryUsage`: resident memory above 250 MiB for 30 s, severity high. | `monitoring/alert_rules.yml` |
| **M1.7.** Rule "High error rate": "Error rate above a defined limit" (p. 8) | Met | `HighHttp5xxErrorRate`: 5xx share above 20% for 30 s, severity high. | `monitoring/alert_rules.yml` |
| **M1.8.** Rule "High latency": "Response latency above a configured limit" (p. 8) | Met | `HighApiLatency`: p95 above 1 second for 30 s, severity medium. | `monitoring/alert_rules.yml` |
| **M1.9.** "all thresholds configurable, not universal values" (p. 8) | Met | Thresholds are values in a version-controlled rule file. They are not editable from the web interface. | `monitoring/alert_rules.yml`; `docs/configuration.md` |
| **M1.10.** "On receiving an alert, the backend validates the payload, matches it to a resource, and creates or updates an incident." (p. 9) | Met | Same as DA4. Resolved notifications resolve the incident with the monitoring signal as evidence. | `backend/app/services/incident_service.py`; `docs/api.md` ("Alertmanager webhook") |
| **M1.11.** "A stable fingerprint built from the rule and resource prevents duplicate incidents for the same active problem." (p. 9) | Met | A partial unique index allows one active incident per fingerprint. A repeat raises a counter. An alert that fires again within the reopen window (10 minutes by default) reopens the incident. | `backend/app/models/models.py`; `backend/tests/integration/test_incidents.py` |
| **M1.12.** "Prometheus holds the time-series data; PostgreSQL stores only incident snapshots and summaries." (p. 9) | Met | The backend stores no metric samples. Every monitoring value is read from Prometheus at request time. | `backend/app/services/monitoring_service.py`; `docs/architecture.md` ("Key architectural decisions") |

12.2 Security assessment engine:

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **M2.1.** "SEC-001 Public access enabled in a test storage policy", severity High (p. 9) | Met | SEC-001 Public Storage Access, HIGH. | `security-rules/policies.yaml` |
| **M2.2.** "SEC-002 Encryption requirement missing from a storage configuration", severity Medium (p. 9) | Met | SEC-002 Missing Encryption, MEDIUM. It also covers disk volumes and databases. | `security-rules/policies.yaml` |
| **M2.3.** "SEC-003 Wildcard permissions in a sample IAM policy", severity High (p. 9) | Changed | SEC-003 Wildcard IAM Permissions exists, but its severity is CRITICAL. The synopsis calls its column "Severity (initial)". | `security-rules/policies.yaml` |
| **M2.4.** "SEC-004 Unrestricted inbound access in a sample network rule", severity High (p. 9) | Met | SEC-004, HIGH. It flags an open source range (0.0.0.0/0 or ::/0) on a sensitive port such as 22, 3389 or 5432. | `security-rules/policies.yaml`; `backend/app/security_scanner/rules.py` |
| **M2.5.** "SEC-005 Privileged execution enabled in a test container configuration", severity High (p. 9) | Met | SEC-005 Privileged Container Execution, HIGH. | `security-rules/policies.yaml` |
| **M2.6.** "Rules are defined in a YAML policy file with an id, name, severity, target type, check name and recommendation." (p. 9) | Partly met | The YAML file holds id, name, severity, resource types, description, detection logic as text, impact, recommendation and the automated action. There is no "check name" field. The check itself is a Python function selected by the rule id. The scanner refuses to load if the file and the code do not list the same rule ids. | `security-rules/policies.yaml`; `load_rules` and `EVALUATORS` in `backend/app/security_scanner/rules.py` |
| **M2.7.** Scanner step 1: "Loads a test configuration and parses it safely." (p. 9) | Met | `yaml.safe_load`, anchors and aliases refused, size limit 262,144 bytes, type checks on security fields. | `parse_yaml_document` in `backend/app/security_scanner/engine.py` |
| **M2.8.** Step 2: "Evaluates the applicable rules." (p. 9) | Met | Every rule that applies to a resource type is run on every resource, in a fixed order. | `evaluate_document` in `backend/app/security_scanner/engine.py` |
| **M2.9.** Step 3: "Creates a finding for each violation, with the affected field and evidence." (p. 9) | Met | One finding per rule and resource. The matched fields and values are stored as evidence. | `backend/app/services/scan_service.py`; `docs/api.md` (finding object) |
| **M2.10.** Step 4: "Stores findings in PostgreSQL." (p. 9) | Met | Table `security_findings`, with scan history in `security_scans`. | `backend/app/models/models.py` |
| **M2.11.** Step 5: "Compares repeat scans to mark findings as resolved or persistent." (p. 9) | Met | A scan counts new, unchanged, reopened and resolved findings and updates their status. | `_apply_file_results` in `backend/app/services/scan_service.py` |
| **M2.12.** "For every rule there is one positive test ... and one negative test" (p. 9) | Met | Same as AC3. Recorded result of 2026-11-23: 17 of 17 expected violations detected, 0 findings on the secure fixtures. | `backend/tests/unit/test_scanner.py`; `scripts/evaluate_scanner.py`; `docs/evaluation.md` section 2.4 |
| **M2.13.** "Malformed files and missing fields must produce a clear error, not a crash." (p. 9) | Met | A malformed file fails the scan with a message that names the file and the problem. Existing findings are kept. | `ScanInputError` in `backend/app/security_scanner/engine.py`; `backend/tests/integration/test_scanning.py` |
| **M2.14.** "The scanner checks controlled test artifacts. It is a rule-based demonstration of misconfiguration detection, not a complete cloud audit." (p. 9) | Met | Stated in the catalog header, the API responses and the README. | `security-rules/policies.yaml`; `backend/app/api/security.py`; `README.md` ("Limitations") |

12.3 Incident management:

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **M3.1.** "An incident has a title, severity, status, affected resource, evidence, timestamps and remediation history." (p. 9) | Met | All of these, and also a timeline of events, a notification counter and a "simulated" flag. | `Incident` and `IncidentEvent` in `backend/app/models/models.py`; incident detail page |
| **M3.2.** "Statuses: open, acknowledged, remediation requested, remediation in progress, resolved, failed." (p. 10) | Changed | Incident statuses are OPEN, ACKNOWLEDGED, IN_PROGRESS, RESOLVED and CLOSED. There is no "remediation requested", "remediation in progress" or "failed" incident status. Remediation progress is on the remediation request (nine statuses) and on the incident's timeline. | `IncidentStatus` and `RemediationStatus` in `backend/app/models/models.py`; `docs/diagrams/incident-lifecycle.md` |
| **M3.3.** "Incidents come from either an alert or a security finding." (p. 10) | Changed | Incidents are created only by the Alertmanager webhook. A security finding does not open an incident. It has its own lifecycle (OPEN, REMEDIATION_PENDING, RESOLVED, ACCEPTED_RISK) and a remediation request is attached to the finding directly. | `docs/api.md` ("Incidents"); `backend/app/services/incident_service.py`; `FindingStatus` in `backend/app/models/models.py` |
| **M3.4.** "An incident is closed only after a successful verification step." (p. 10) | Partly met | An incident becomes RESOLVED in three ways: a verified remediation, a "resolved" notification from Alertmanager, or a person with a written note when Prometheus confirms that the alert is no longer firing. One exception: when Prometheus cannot be queried, an Administrator may resolve with a recorded override. CLOSED is set by an Administrator after RESOLVED. | `resolve_incident` and `transition_incident` in `backend/app/services/incident_service.py` |

12.4 Remediation engine:

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **M4.1.** "Lifecycle: finding detected, action proposed, authorization, execution, verification, audit and closure." (p. 10) | Met | Request statuses: PENDING_APPROVAL, APPROVED, REJECTED, QUEUED, RUNNING, VERIFYING, SUCCEEDED, FAILED, CANCELLED. | `RemediationStatus` in `backend/app/models/models.py`; `docs/diagrams/remediation-sequence.md` |
| **M4.2.** Action registry: "Restart the dedicated test application." (p. 10) | Changed | ACTION-001 "Recover monitored demonstration application" calls a recovery endpoint. It is not a restart (DA6). | `backend/app/services/remediation_catalog.py`; `backend/app/workers/actions.py` |
| **M4.3.** Action registry: "Recheck an application's health endpoint." (p. 10) | Changed | Not a registered action. The health recheck is the first verification step of ACTION-001. | `_verify_health` in `backend/app/workers/verification.py` |
| **M4.4.** Action registry: "Apply a predefined correction to an approved test configuration file." (p. 10) | Met | ACTION-002 "Correct public storage configuration", for SEC-001 only. | `backend/app/services/remediation_catalog.py`; `fix_public_storage` in `backend/app/workers/actions.py` |
| **M4.5.** Action registry: "Re-run the security scanner." (p. 10) | Changed | Not a registered action. The rescan is the verification step of ACTION-002. A user can also start a scan at any time with the Run scan button. | `verify_storage_correction` in `backend/app/workers/verification.py`; `POST /api/security/scans` |
| **M4.6.** "Each action has a validated target, explicit permissions, an execution timeout, a recorded result and a verification step." (p. 10) | Met | Targets come from database records, not from free text. Permissions `remediation:request`, `remediation:approve`, `remediation:execute`. Timeouts as in O5. The result and the verification checks are stored per attempt. | `_build_params` and `_run_with_timeout` in `backend/app/workers/remediation_worker.py`; `RemediationExecution` in `backend/app/models/models.py` |
| **M4.7.** "No user input, API request or language model can supply a raw shell command." (p. 10) | Met | No handler starts a process. A request carries an action code only. An assertion requires the handler registry and the published catalog to list the same codes. | `backend/app/workers/actions.py` (last lines) |
| **M4.8.** Safeguard: "approval required for every state-changing action in version one" (p. 10) | Met | Every remediation needs an approval by an Administrator, and the worker checks again that an approval is recorded. | `approve` in `backend/app/services/remediation_service.py`; `claim_next` in `backend/app/workers/remediation_worker.py` |
| **M4.9.** Safeguard: "duplicate-request protection" (p. 10) | Met | At most one request in progress per incident or finding, enforced by partial unique indexes. A duplicate returns HTTP 409. | `backend/app/models/models.py`; `backend/tests/integration/test_remediation.py` |
| **M4.10.** Safeguard: "timeouts" (p. 10) | Met | Action timeout, verification timeout, three bounded recovery calls, at most three attempts per request. A timeout ends as FAILED with the reason in the text. | `backend/app/core/config.py`; `backend/app/workers/remediation_worker.py` |
| **M4.11.** Safeguard: "least-privilege execution" (p. 10) | Met | The worker runs as a non-root user with a read-only root file system and no capabilities. It holds no API secrets. | `compose.yaml` (service `worker`); `docs/verification-report.md` section 4 |
| **M4.12.** Safeguard: "an explicit test-environment boundary" (p. 10) | Met | Same as N3. | `backend/app/services/remediation_catalog.py` |
| **M4.13.** "the worker uses a fixed wrapper that can restart only the designated service" (Docker socket) (p. 10) | Changed | The worker has no access to the Docker socket at all, so there is no wrapper. It calls one token-protected HTTP endpoint and edits one allowlisted file. | `compose.yaml` (no socket mount); `backend/app/workers/actions.py` |

12.5 Authentication and authorization, and 12.6 Audit logging:

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **M5.1.** "Login, hashed passwords, token or session expiry, logout, input validation and role checks on every protected endpoint." (p. 10) | Met | Sign-in with rate limiting, bcrypt, a 60-minute token, logout that revokes the token on the server, Pydantic validation and permission checks. | `backend/app/api/auth.py`; `backend/app/core/security.py`; `backend/tests/integration/test_auth_rbac.py` |
| **M5.2.** "Passwords and secrets are never returned in responses or committed to the repository." (p. 10) | Met | Responses contain no password hash. The settings API only reports whether the Gemini key is set. `.env` is ignored by Git. The Git history was not inspected for this document. | `backend/app/schemas/schemas.py`; `.gitignore`; `README.md` ("Gemini API setup") |
| **M6.1.** "Every remediation attempt records the requesting user, approving user, target resource, action type, request and execution timestamps, result, error details and verification outcome." (p. 10) | Met | The request row holds requester, approver, target, action code and timestamps. Each attempt holds its details, error and verification result. Audit events link them by correlation ID. | `RemediationRequest` and `RemediationExecution` in `backend/app/models/models.py`; request detail page |
| **M6.2.** "Audit records are not editable through normal application endpoints." (p. 10) | Met | The audit API has read endpoints only. In PostgreSQL a trigger rejects UPDATE and DELETE on `audit_events`. | `backend/app/api/audit.py`; `backend/alembic/versions/0001_initial_schema.py` |

### 3.13 Database design (Section 13, pages 10 and 11)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **DT1.** `users`: "id, email, password_hash, role, created_at" (p. 10) | Met | Table `users` with these columns and more (`is_active`, `token_version`, `last_login_at`). | `User` in `backend/app/models/models.py` |
| **DT2.** `resources`: "id, name, resource_type, status, last_seen" (p. 11) | Changed | The table is named `monitored_resources`. `last_seen` is `status_checked_at`. | `MonitoredResource` in `backend/app/models/models.py` |
| **DT3.** `metrics`: "id, resource_id, metric_name, value, timestamp (snapshots only)" (p. 11) | Changed | There is no `metrics` table. Metric values stay in Prometheus and are read when needed. | `backend/app/models/models.py`; `docs/architecture.md` ("Key architectural decisions") |
| **DT4.** `security_findings`: "id, rule_id, severity, evidence, status, first_detected, last_observed" (p. 11) | Met | Table `security_findings`. The time columns are `first_detected_at` and `last_seen_at`. | `SecurityFinding` in `backend/app/models/models.py` |
| **DT5.** `incidents`: "id, title, severity, status, resource_id, fingerprint, created_at, resolved_at" (p. 11) | Met | Table `incidents`. The fingerprint column is `alert_fingerprint`. | `Incident` in `backend/app/models/models.py` |
| **DT6.** `remediation_jobs`: "id, incident_id, action_type, status, requested_by, approved_by, timestamps" (p. 11) | Changed | The table is named `remediation_requests`, with `action_code` and either `incident_id` or `finding_id`. Each attempt is a row in `remediation_executions`. | `RemediationRequest` and `RemediationExecution` in `backend/app/models/models.py` |
| **DT7.** `audit_logs`: "id, actor_id, action, target, result, timestamp" (p. 11) | Changed | The table is named `audit_events`. Target is `entity_type` and `entity_id`. Result is `outcome`. | `AuditEvent` in `backend/app/models/models.py` |
| **DT8.** "Foreign keys link incidents to resources and remediation jobs to incidents. Indexes are added on timestamps, status and resource identifiers. Alembic manages all schema changes." (p. 11) | Met | These foreign keys and indexes exist. The schema is created by one Alembic migration. The schema has thirteen tables in total. | `backend/alembic/versions/0001_initial_schema.py`; `docs/diagrams/er-diagram.md` |

### 3.14 API design (Section 14, pages 11 and 12)

The synopsis says: "These are proposed routes."

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **AP1.** "GET /api/health, GET /api/version" (p. 11) | Met | Both exist. In production mode they return only a status or the project title. | `backend/app/main.py` |
| **AP2.** "POST /api/auth/login" (p. 11) | Met | Exists, with rate limiting. | `backend/app/api/auth.py` |
| **AP3.** "GET /api/auth/me" (p. 11) | Met | Exists. | `backend/app/api/auth.py` |
| **AP4.** "GET /api/resources" (p. 11) | Changed | No such path. Monitored resources are returned in `GET /api/monitoring/overview`. | `backend/app/api/monitoring.py`; `docs/api.md` |
| **AP5.** "GET /api/incidents" (paginated) (p. 11) | Met | Exists, with pages, filters, search and sorting. | `backend/app/api/incidents.py` |
| **AP6.** "GET /api/findings" (p. 11) | Changed | `GET /api/security/findings`. | `backend/app/api/security.py` |
| **AP7.** "GET /api/audit-logs" (p. 11) | Changed | `GET /api/audit/events`. | `backend/app/api/audit.py` |
| **AP8.** "POST /api/incidents/{id}/remediation-requests" (p. 11) | Changed | `POST /api/remediation/requests` with `source_type`, `source_id`, `action_code` and `justification` in the body. The source can be an incident or a finding. | `backend/app/api/remediation.py` |
| **AP9.** "POST /api/remediation/{id}/approve" (p. 11) | Changed | `POST /api/remediation/requests/{id}/approve`. There are also `reject`, `retry` and `cancel`. | `backend/app/api/remediation.py` |
| **AP10.** "POST /api/remediation/{id}/execute" (p. 11) | Changed | `POST /api/remediation/requests/{id}/execute`. It puts the approved request in the worker's queue. The worker executes it. | `backend/app/api/remediation.py` |
| **AP11.** "GET /api/remediation/{id}" (p. 11) | Changed | `GET /api/remediation/requests/{id}`. | `backend/app/api/remediation.py` |
| **AP12.** "FastAPI's interactive documentation at /docs will serve as the living API reference." (p. 12) | Met | `/docs` is served on the backend port (`http://localhost:8000/docs`) in development mode. It is off in production mode and is not routed by the reverse proxy. A written reference also exists. | `backend/app/main.py`; `docs/api.md` |
| **AP13.** "Lists are paginated and errors use one consistent format." (p. 12) | Met | Lists return `items`, `total`, `page`, `page_size`. Errors return `detail` and `request_id`. | `backend/app/api/deps.py`; exception handlers in `backend/app/main.py` |

### 3.15 Security and safety considerations (Section 15, page 12)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **S1.** "Secrets are kept in environment variables; only a .env.example file is committed." (p. 12) | Met | All secrets are read from the environment. `.env` is in `.gitignore`. `.env.example` holds placeholders that are refused in production mode. | `backend/app/core/config.py`; `.gitignore`; `.env.example` |
| **S2.** "Role checks are enforced on the backend for every protected route." (p. 12) | Met | Same as R3. | `require_permission` in `backend/app/core/permissions.py` |
| **S3.** "CORS allows only the intended frontend origin." (p. 12) | Met | By default no CORS is enabled: the frontend and the API share one origin behind the proxy. Otherwise only the origins listed in `CORS_ORIGINS` are allowed. | `backend/app/main.py`; `reverse-proxy/Caddyfile` |
| **S4.** "All database access goes through the ORM with parameterized queries." (p. 12) | Met | Application code uses SQLAlchemy. The few literal SQL texts are constants (a `SELECT 1` health check, index conditions, the audit trigger in the migration) and take no user input. | `backend/app/services/`; `backend/app/core/database.py` |
| **S5.** "Error responses never expose stack traces or credentials." (p. 12) | Met | Unhandled errors return "Internal server error." with a request id. Audit metadata and logs redact secret-like keys. | `backend/app/main.py`; `sanitize_metadata` in `backend/app/services/audit_service.py` |
| **S6.** "YAML is loaded with safe loaders, and the scanner reads only designated test files." (p. 12) | Met | Same as M2.7 and SX1. | `backend/app/security_scanner/engine.py`; `backend/app/services/scan_service.py` |
| **S7.** "Remediation targets are restricted to the test environment." (p. 12) | Met | Same as N3. | `backend/app/services/remediation_catalog.py` |
| **S8.** "Scans and actions are never run against production or unauthorized resources." (p. 12) | Met | The platform has no cloud credentials, no Docker access and no host access. | `docs/architecture.md` (line starting "What VigilOps deliberately is not") |

### 3.16 Testing and evaluation plan (Section 16, page 12)

Test results below are the recorded results of 2026-11-25: backend 280 passed and 5 skipped on SQLite, demonstration application 26 passed, frontend 32 passed, browser tests 16 passed (`docs/verification-report.md` sections 1 and 10).

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **TE1.** "unit tests (rule evaluation, severity, business logic)" (p. 12) | Met | Unit tests for the scanner rules, core functions and the assistant's guards. | `backend/tests/unit/` |
| **TE2.** "API tests (authentication, validation, endpoints)" (p. 12) | Met | Tests call the API through the test client. | `backend/tests/integration/test_auth_rbac.py` and the other files in that folder |
| **TE3.** "integration tests (alert-to-incident, finding-to-remediation)" (p. 12) | Met | Webhook to incident, and finding to request to worker to verification. | `backend/tests/integration/test_incidents.py`; `backend/tests/integration/test_remediation.py` |
| **TE4.** "end-to-end tests through the UI" (p. 12) | Met | Playwright tests in Chromium, including Demo 2 through the pages with two users. Demo 1 is automated at the API level only. | `tests/e2e/specs/platform.spec.js`; `scripts/run_e2e_demos.py` |
| **NG1.** Negative case: "invalid credentials" (p. 12) | Met | Wrong password, unknown e-mail and deactivated account give the same message. | `backend/tests/integration/test_auth_rbac.py` |
| **NG2.** Negative case: "unauthorized approvals" (p. 12) | Met | Operator approval returns 403 and changes nothing. | `backend/tests/integration/test_auth_rbac.py` |
| **NG3.** Negative case: "duplicate requests" (p. 12) | Met | A second request for the same source returns 409. | `backend/tests/integration/test_remediation.py` |
| **NG4.** Negative case: "malformed configurations" (p. 12) | Met | Invalid YAML, wrong types, oversized files and anchors are rejected. | `backend/tests/unit/test_scanner.py`; `backend/tests/integration/test_scanning.py` |
| **NG5.** Negative case: "restart failures" (p. 12) | Met | The recovery endpoint is unreachable: three bounded attempts, then FAILED, incident stays open. Also shown on the running stack. | `backend/tests/integration/test_remediation.py`; `docs/evidence/failed-remediation.json` |
| **NG6.** Negative case: "timeouts" (p. 12) | Partly met | Tested: verification that does not pass within its timeout, Prometheus timeouts and assistant provider timeouts. No test was found for the branch where an action handler itself exceeds its 30-second execution timeout. | `backend/tests/integration/test_remediation.py`; `backend/tests/integration/test_audit_monitoring.py`; `_run_with_timeout` in `backend/app/workers/remediation_worker.py` |
| **EX0.** "Experiments (each repeated several times, with actual results reported)" (p. 12) | Partly met | Actual results are reported. Outage and remediation timings come from two or three runs. Each of the four other alert rules was run once, and the failed-remediation run is recorded once. The evaluation states these sample sizes. | `docs/evaluation.md` (opening paragraph and section 3) |
| **EX1.** "Application outage: Detection rate and alert latency" (p. 12) | Met | Three runs, an incident in each: 30.2 s, 27.9 s and 37.5 s from outage to incident. A fourth observation with a real container stop: 36.3 s. | `docs/evaluation.md` section 2.1; `docs/evidence/failed-remediation.json` |
| **EX2.** "High CPU load: Threshold and alert behavior" (p. 12) | Met | One run: 0.97 core observed against the 0.80 threshold, incident after 97.6 s, automatic resolution 24.4 s after the fault was cleared. | `docs/evaluation.md` section 2.2; `docs/evidence/alert-rules.json` |
| **EX3.** "Insecure configuration scan: Correct detections and false positives" (p. 12) | Met | 17 of 17 expected violations detected, 0 false positives, same result in 20 repeated scans. | `docs/evaluation.md` section 2.4; `scripts/evaluate_scanner.py` |
| **EX4.** "Approved restart: Recovery success rate and recovery time" (p. 12) | Met | Measured for the recovery action (not a restart, DA6): 3 of 3 runs SUCCEEDED, 12.2 s, 12.2 s and 20.4 s from dispatch to verified result. | `docs/evaluation.md` section 2.5 |
| **EX5.** "Configuration correction and rescan: Whether the original finding is resolved" (p. 12) | Met | The SEC-001 finding was RESOLVED by the verification scan in each recorded run (2.1 s and 4.4 s). | `docs/evaluation.md` section 2.5 |
| **EX6.** "Unauthorized operations: Rejected requests and audit evidence" (p. 12) | Met | 11 Administrator-only endpoints returned 403 to an Operator and wrote 11 `ACCESS_DENIED` audit events. | `docs/evaluation.md` section 2.7 |
| **EX7.** "Forced action failure or timeout: Correct failure status and incident retention" (p. 12) | Met | Automated tests for failed verification and an unreachable application, and the recorded failed run: FAILED, incident OPEN, manual resolution refused while the alert fires. | `docs/evaluation.md` section 2.5; `docs/evidence/failed-remediation.json` checks 8 to 10 |
| **RP1.** "The report states the number of trials, the environment and any failed runs, without selecting favorable numbers in advance." (p. 12) | Met | Chapter 9 of the report states the environment, the three runs and their sample sizes, a defect found in the first run, and the failed-remediation run with its measurements. `docs/evaluation.md` itself does not yet include the failed-remediation run of 2026-11-24. | `docs/college/project-report.md` sections 9.1 and 9.4; `docs/evaluation.md` sections 1 and 3 |

### 3.17 Implementation plan (Section 17, page 13)

The repository does not record in which weeks each phase was done (see T4). The status of each row below is about the work and the exit check, not about the weeks.

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **PL1.** Phase 1, weeks 1 to 2: "Problem statement, roles, use cases, acceptance criteria, initial docs". Exit: "Guide-approved scope; everyone agrees on minimum features" (p. 13) | Not verified | The documents exist. The guide's approval and the team's agreement are outside the repository. | `README.md` ("Problem statement"); `docs/diagrams/use-case.md`; `docs/verification-report.md` section 3 |
| **PL2.** Phase 2, weeks 3 to 4: "Tools, GitHub repo, project structure, health endpoint, landing page". Exit: "A second member runs the app from the README" (p. 13) | Partly met | Repository, structure, health endpoints and a public product page exist. The exit check is not recorded (AC7). | `backend/app/main.py`; `frontend/src/pages/Landing.jsx` |
| **PL3.** Phase 3, weeks 5 to 7: "Models, migrations, login, roles, initial endpoints, tests". Exit: "Login works; unauthorized requests are rejected" (p. 13) | Met | All exist and are tested. | `backend/tests/integration/test_auth_rbac.py` |
| **PL4.** Phase 4, weeks 8 to 9: "Dashboard, resources, findings and incident pages, API client". Exit: "No core page uses hard-coded data" (p. 13) | Met | Every page reads from the API. The audit of the prototype found hard-coded page data, and those pages were rebuilt. | `frontend/src/api/`; `docs/phase-0-audit.md` row 7 |
| **PL5.** Phase 5, weeks 10 to 12: "Test app, Prometheus, alert rules, webhook, deduplication". Exit: "A real failure produces a traceable incident" (p. 13) | Met | A real container stop opened an incident that was not labelled as simulated. | `docs/evidence/failed-remediation.json` checks 2 to 4b |
| **PL6.** Phase 6, weeks 13 to 15: "Five rules, YAML policies, scanner, findings view, tests". Exit: "Detect, fix and rescan shows the finding resolved" (p. 13) | Met | Shown in Demo 2 and in a test that fixes a file and scans again. | `docs/evidence/e2e-results.json`; `backend/tests/integration/test_scanning.py` |
| **PL7.** Phase 7, weeks 16 to 18: "Action registry, approval flow, both scenarios, audit logs". Exit: "One successful and one deliberately failed run, both audited" (p. 13) | Met | Successful runs and the failed run are recorded, each with its audit events. | `docs/evidence/e2e-results.json`; `docs/evidence/failed-remediation.json` |
| **PL8.** Phase 8, weeks 19 to 21: "Full integration, test suites, GitHub Actions, hardening, clean-install test". Exit: "Clean checkout passes checks; both demos work" (p. 13) | Met | Two CI runs on 2026-11-23 are recorded as fully successful (5 of 5 and 6 of 6 jobs), including the stack check and the demonstrations from a clean checkout. CI results for later commits are Not verified here. | `docs/verification-report.md` section 1; `.github/workflows/ci.yml` |
| **PL9.** Phase 9, weeks 22 to 24: "Experiments, report, diagrams, demo, viva preparation". Exit: "Final software, report and rehearsed demo" (p. 13) | Partly met | Experiments, diagrams, a demonstration script, viva questions and a full draft of the report exist. The report still has blanks to fill (DL5). A rehearsal is not recorded. | `docs/evaluation.md`; `docs/diagrams/`; `docs/college/` |
| **PL10.** "Documentation, testing and Git commits happen continuously, not only at the end." (p. 13) | Not verified | The commit history was not examined for this document. The repository's own records are dated 2026-11-23 and 2026-11-24. [TO FILL: describe from the GitHub history how the work was spread over time] | `docs/phase-0-audit.md`; `docs/verification-report.md` |
| **MS1.** Milestone 1: "React frontend talking to the FastAPI backend" (p. 13) | Met | The frontend calls `/api` through the reverse proxy. | `frontend/src/api/client.js`; `reverse-proxy/Caddyfile` |
| **MS2.** Milestone 2: "real metrics and alert-generated incidents" (p. 13) | Met | Same as O2 and O3. | `docs/evaluation.md` sections 2.1 and 2.2 |
| **MS3.** Milestone 3: "end-to-end verified remediation" (p. 13) | Met | Same as O6. | `docs/evidence/e2e-results.json` |

### 3.18 Team division (Section 18, page 14)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **TM1.** Four members: Member 1 "React dashboard, UI pages, charts, API client"; Member 2 "FastAPI backend, database models and migrations, authentication, RBAC"; Member 3 "Prometheus and alert rules, test application, security scanner and rule tests"; Member 4 "Docker Compose, remediation worker and action registry, CI/CD, hardening" (p. 14) | Met | The repository document divides the work among four members along the same lines. It also assigns the parts built beyond the synopsis: the assistant's front end and the product page to Member 1, the assistant's backend and the knowledge base to Member 2, the incident engine to Member 3, and the hosted deployment and the verification scripts to Member 4. Names and roll numbers are blank. | `docs/college/team-responsibilities.md` |
| **TM2.** "All four members take part in integration, testing, documentation and cross-review of each other's pull requests" (p. 14) | Not verified | The repository states review as a rule for the team but holds no record of pull requests or reviews. [TO FILL: say how changes were reviewed] | `docs/college/team-responsibilities.md` ("Shared responsibilities") |
| **TM3.** "Working routine: Monday plan; Tuesday to Thursday implement in feature branches; Friday integrate and review; end of week run the full system" (p. 14) | Not verified | A weekly routine is suggested in a document. No record shows that it was followed. There are no feature branches (TS16). [TO FILL: describe the routine the team actually followed] | `docs/college/team-responsibilities.md` ("Suggested working routine") |

### 3.19 Deliverables (Section 19, page 14)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **DL1.** "Working application: frontend, backend, database, monitoring, scanner and remediation worker." (p. 14) | Met | All six parts run in the Compose stack. | `compose.yaml`; `docs/verification-report.md` section 3 |
| **DL2.** "GitHub repository with README, setup instructions and .env.example." (p. 14) | Met | All three files exist. The configured remote is `github.com/Gangadhar017/VigilOps`. The GitHub site was not opened for this document. | `README.md`; `docs/setup.md`; `.env.example`; `.git/config` |
| **DL3.** "Automated test suites and a passing CI pipeline." (p. 14) | Met | Recorded on 2026-11-23: all suites passed and two CI runs succeeded. Later CI runs are Not verified here. | `docs/verification-report.md` section 1 |
| **DL4.** "Documentation: problem statement, requirements, use cases, architecture, ER diagram, API docs." (p. 14) | Met | Problem statement in the README. Requirements and use cases in the report (Chapter 4) and its outline. Architecture, ER diagram and API reference as separate documents. | `README.md`; `docs/college/project-report.md`; `docs/architecture.md`; `docs/diagrams/er-diagram.md`; `docs/diagrams/use-case.md`; `docs/api.md` |
| **DL5.** "Evaluation results and final project report." (p. 14) | Partly met | Evaluation results exist. The report exists as a full draft: when checked on 2026-11-25 it had Chapters 1 to 10, a reference list and Appendices A to H. It is not final: it still has `[TO FILL]` blanks for the college, the guide, the team members' names and roll numbers, page numbers and the reference format. | `docs/evaluation.md`; `docs/college/project-report.md`; `docs/college/project-report-outline.md` |
| **DL6.** "Demo (10 to 15 minutes) plus a recorded fallback." (p. 14) | Partly met | A timed demonstration script exists; its plan adds up to about 15 minutes without the optional part. A script records the walkthrough as a video, and one recording was made with it on 2026-11-25 (3 min 20 s, WebM; verification report section 10). The video is not stored in the repository (the `recordings/` folder is ignored by Git), and the demonstration itself has not been given yet. [TO FILL: where the team keeps the video for the demonstration day] | `docs/college/demo-script.md`; `tests/e2e/record-demo.js`; `.gitignore` |

### 3.20 Risks and mitigation (Section 20, pages 14 and 15)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **RK1.** Docker unavailable: "Start with local backend and database; do not block on containers" (p. 14) | Met | The setup guide has a section for development without Docker. The backend tests need no running services. | `docs/setup.md` ("Development without Docker") |
| **RK2.** Integration left too late: "Weekly integration on Friday; a running end-to-end skeleton early" (p. 14) | Not verified | No record of weekly integration exists in the repository (see TM3). | `docs/college/team-responsibilities.md` |
| **RK3.** Scope creep: "Freeze the stack and the mandatory list; optional items only after core works" (p. 15) | Partly met | The mandatory list is complete. Items that were not in the synopsis were added: the VigilAI assistant, a public product page, the OrbitCrate storefront and a free-hosting profile. The stack also grew (TS18). | `README.md` ("Features"); `docs/phase-0-audit.md` rows 22 and 26 |
| **RK4.** Live demo failure: "Rehearse; keep screenshots and a recorded fallback" (p. 15) | Partly met | Eight screenshots are stored. A recording script and scripted demonstrations exist, and one recording was made on 2026-11-25 (DL6). The video is not in the repository and a rehearsal is not recorded. | `docs/screenshots/`; `tests/e2e/record-demo.js`; `scripts/run_e2e_demos.py` |
| **RK5.** Remediation causing damage: "Allowlist, approval, test-only targets, timeouts, audit trail" (p. 15) | Met | All five controls exist (M4.6 to M4.12). | `backend/app/workers/`; `docs/security.md` |
| **RK6.** One member becomes a bottleneck: "Pull request reviews and shared ownership of each module" (p. 15) | Not verified | Shared understanding is stated as a principle. No pull request records exist in the repository (TM2). | `docs/college/team-responsibilities.md` |
| **RK7.** Alert flapping or duplicates: "Sustained-interval rules and fingerprint-based deduplication" (p. 15) | Met | Each rule has a `for` duration of 15 or 30 seconds. Deduplication and the reopen window are in M1.11. | `monitoring/alert_rules.yml`; `backend/app/services/incident_service.py` |

### 3.21 Limitations, future scope and expected outcomes (Sections 21 and 22, page 15)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **L1.** "The core runs in a local test environment, not a real multi-account cloud." (p. 15) | Met | Still true, and stated openly. | `README.md` ("Limitations") |
| **L2.** "The scanner covers five rules on test artifacts." (p. 15) | Met | Still true. | `security-rules/policies.yaml` |
| **L3.** "Detection is rule-based, with no machine learning in version one." (p. 15) | Met | Alert rules and scanner rules are fixed rules. The VigilAI assistant uses a language model but takes no part in detection (section 5). | `monitoring/alert_rules.yml`; `backend/app/security_scanner/rules.py` |
| **L4.** "Thresholds are starting values that need tuning." (p. 15) | Met | The evaluation says the thresholds were chosen for a clear demonstration. | `docs/evaluation.md` section 3 |
| **F1.** Future scope: "Read-only AWS integration; additional rules and providers; anomaly detection on metrics; automatic execution of approved low-risk actions; notifications by email or chat; Kubernetes support; deployment to a cloud VM." (p. 15) | Not done | As the synopsis planned, none of these is built, except that the deployment to a VM is prepared but not run (SO4). AWS, more rules, notifications and Kubernetes are listed again as future work. Anomaly detection and automatic execution are not mentioned in the repository's future-scope document. | `docs/college/future-scope.md`; `README.md` ("Future scope") |
| **X1.** Expected outcome: "A functional web platform that collects real monitoring metrics, identifies selected security misconfigurations, creates deduplicated incidents, executes two controlled corrective workflows with approval, verifies their outcomes and maintains an audit trail" (p. 15) | Met | Each part is Met in the tables above (O2, O4, O3, O6, O5, O7). | `docs/verification-report.md` section 3 |
| **X2.** "together with measured evaluation results and complete documentation" (p. 15) | Met | The evaluation and the technical documents exist. The status of the final report is in DL5. | `docs/evaluation.md`; `README.md` ("Documentation index") |

### 3.22 Likely questions from the guide (Section 23, pages 15 and 16)

Each answer in the synopsis is a statement about the project, so each is traced.

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **Q1.** "Why Prometheus instead of collecting metrics manually?" (p. 15) | Met | Prometheus is used unchanged for scraping, storage and alert rules. | `monitoring/`; `docs/architecture.md` |
| **Q2.** "Why PostgreSQL as well as Prometheus?" Prometheus for time series, PostgreSQL for relational records (p. 15) | Met | Exactly this split (M1.12). | `backend/app/models/models.py` |
| **Q3.** "Why FastAPI?" Validation is built in and "the automatic /docs page helps testing and demonstration" (p. 15) | Met | Same as TS4 and AP12. | `backend/app/main.py` |
| **Q4.** "How does the scanner detect a misconfiguration?" It "evaluates it against YAML-defined rules, then records the field and evidence" (p. 16) | Partly met | Field and evidence are recorded. The rules are described in YAML, but the checks are Python functions (M2.6). | `backend/app/security_scanner/rules.py` |
| **Q5.** "How do you prevent unauthorized remediation?" Role checks, mandatory approval, an allowlist, a test-only boundary and an audit log (p. 16) | Met | All five exist (R3, M4.8, M4.7, M4.12, M6.1). | `docs/security.md` |
| **Q6.** "What happens if an action fails? The job is marked failed or timed out, the incident stays open and the failure is audited." (p. 16) | Met | The request becomes FAILED, the incident stays active, and the failure is audited with outcome FAILURE. There is no separate "timed out" status: a timeout ends as FAILED with the reason in the text. | `_finish_failed` in `backend/app/workers/remediation_worker.py`; `docs/evidence/failed-remediation.json` |
| **Q7.** "Is it really cloud computing?" The "same Compose file can run on a single VM. AWS-style checks can be tested against moto without a paid account." (p. 16) | Partly met | The stack is containerised and a production overlay for a VM exists, but it was not run on a VM (SO4). The rules are AWS-style checks on local YAML files. moto is not used (SO1). | `compose.prod.yaml`; `docs/deployment.md`; `security-rules/` |
| **Q8.** "How is it different from CloudWatch or Prowler?" It "joins detection, incident handling, approved action, verification and audit in one workflow" (p. 16) | Met | Same as G1. | `docs/diagrams/remediation-sequence.md` |
| **Q9.** "Are you using AI? Version one is rule-based for reliability and explainability. Anomaly detection is an optional extension, and no capability will be claimed that is not implemented." (p. 16) | Changed | Detection and remediation are still rule-based. Anomaly detection was not built. An optional AI assistant, VigilAI, was added. Section 5 gives the accurate answer. | `backend/app/assistant/`; `knowledge_base/` |
| **Q10.** "What are the limitations? See Section 21; we state them openly." (p. 16) | Met | Limitations and unverified items are listed in several documents. | `README.md` ("Limitations"); `docs/architecture.md` ("Known limitations"); `docs/verification-report.md` section 6 |

### 3.23 Tools and documentation to reference (Section 24, page 16)

| Synopsis item | Status | What exists in VigilOps | Where to see it |
|---|---|---|---|
| **RF1.** Cite the official documentation of Prometheus, Alertmanager, FastAPI, SQLAlchemy, Alembic, PostgreSQL, React, Vite, Docker, Docker Compose, GitHub Actions and Pytest, "and, for rule definitions, the relevant cloud provider's security documentation" (p. 16) | Partly met | The report's reference list (21 entries when checked on 2026-11-25) cites the official documentation of all the named tools except GitHub Actions. It has no cloud provider security documentation for the rule definitions; the AWS Config entry belongs to the comparison of existing systems. The list carries a `[TO FILL]` note: keep only the sources the team has read, and add access dates. | `docs/college/project-report.md` ("References") |
| **RF2.** "For related work, review Prowler, Checkov, Rundeck, StackStorm and AWS CloudWatch." (p. 16) | Partly met | Same as G2: Checkov is covered. The other four are not named. | `docs/college/project-report.md` Chapter 3 |

## 4. Differences to explain in the viva

Each paragraph names the rows it covers. Where the repository records a reason, the document is named. Where it does not, the line "Reason to be stated by the team: [TO FILL]" is used.

### 4.1 Changed

**Project name (T1).** The synopsis is titled CloudShield. The project is now VigilOps: Secure Cloud Operations. The README says it was upgraded from an earlier prototype called CloudShield, and `docs/phase-0-audit.md` lists what was kept and what was rebuilt. The repository does not say why the name was changed. Reason to be stated by the team: [TO FILL].

**Recovery instead of restart (DA6, M4.2, M4.13, TS11).** The synopsis said the worker would restart the test service through the Docker SDK or a restricted wrapper around the Docker socket. In VigilOps the worker has no Docker access at all. ACTION-001 calls a token-protected recovery endpoint of the application, which re-initialises its service component and clears the fault. The documented reason is safety: `docs/architecture.md` (worker table, row "No shell, no Docker") and `README.md` ("Limitations") say the platform deliberately has no access to the Docker daemon or the host. The stated consequence is that ACTION-001 cannot start a stopped container. `docs/evidence/failed-remediation.json` shows exactly that case ending as FAILED.

**Two registered actions instead of four (M4.3, M4.5).** The synopsis listed four actions: restart, health recheck, configuration correction and rescan. VigilOps registers two: ACTION-001 and ACTION-002. The health recheck and the rescan are not separate actions. They are the mandatory verification steps of the two actions, so a request cannot succeed without them. The repository records this design in `backend/app/workers/verification.py` and in `docs/architecture.md` ("Evidence-based resolution"). `docs/college/future-scope.md` section 3 adds that each further action needs a handler, an independent verifier and failure tests. A scan can still be started by hand at any time.

**Incidents come from alerts only (M3.3).** The synopsis said an incident comes from an alert or from a security finding. In VigilOps only the Alertmanager webhook creates incidents; `docs/api.md` says so directly. A finding is tracked by its own four statuses, and a remediation request is attached to the finding itself. The repository does not give the reason for this choice. Reason to be stated by the team: [TO FILL].

**Incident statuses (M3.2).** The synopsis listed open, acknowledged, remediation requested, remediation in progress, resolved and failed. VigilOps uses OPEN, ACKNOWLEDGED, IN_PROGRESS, RESOLVED and CLOSED. Remediation progress is shown on the remediation request, which has nine statuses, and on the incident's timeline. A failed remediation leaves the incident active instead of moving it to a "failed" status. `docs/phase-0-audit.md` row 13 lists the five statuses as the required change but gives no reason for the exact set. Reason to be stated by the team: [TO FILL].

**Severity of SEC-003 (M2.3).** The synopsis gave SEC-003 the initial severity High. The rule catalog sets it to CRITICAL. The other four severities match. `docs/phase-0-audit.md` section 4 says the rule severities were kept from the prototype. The repository does not say why this rule is Critical. Reason to be stated by the team: [TO FILL].

**No metrics table (DT3).** The synopsis planned a `metrics` table for snapshots. VigilOps has none. The documented reason is in `docs/architecture.md` ("Prometheus is the only source of telemetry"): every number shown comes from a Prometheus query, and nothing is copied or substituted. `docs/phase-0-audit.md` rows 8 and 9 record that the prototype's stored metrics contained invented values, which this design removed. The cost is that history is limited to Prometheus's retention of 7 days.

**Table names (DT2, DT6, DT7).** The synopsis named the tables `resources`, `remediation_jobs` and `audit_logs`. They are `monitored_resources`, `remediation_requests` (with `remediation_executions` for each attempt) and `audit_events`. The planned fields exist under these names. The repository does not record why the names differ. Reason to be stated by the team: [TO FILL].

**API paths (AP4, AP6 to AP11).** The synopsis itself called its routes "proposed". Seven of them have different paths now: resources are inside `GET /api/monitoring/overview`, findings are under `/api/security/findings`, audit history is under `/api/audit/events`, and all remediation endpoints are under `/api/remediation/requests`. A request is created with one endpoint for both incidents and findings, because a finding can also be the source. The full list is in `docs/api.md`. The repository does not give a reason for each new path. Reason to be stated by the team: [TO FILL].

**Branch strategy (TS16).** The synopsis planned `main`, `develop` and feature branches. The local record of the GitHub remote lists only `main`. There is no `develop` branch and no feature branch; the local clone also has `vigilops-upgrade` and a backup branch. The CI workflow still names `develop` as a trigger. Reason to be stated by the team: [TO FILL].

**"Are you using AI?" (Q9).** See section 5.

### 4.2 Partly met

**Administrator manages policies and monitoring configuration (R1).** The synopsis gave the Administrator the management of users, policies and monitoring configuration. In VigilOps the Administrator manages users and three runtime settings in the application. Security policies and Prometheus configuration are files in the repository and are changed there. For monitoring, `docs/college/future-scope.md` section 4 explains that registering resources from the interface would need generated scrape and rule configuration and a reload mechanism. For policy editing no reason is recorded. Reason to be stated by the team: [TO FILL].

**Incident closure rule (M3.4).** The synopsis said an incident is closed only after a successful verification step. In VigilOps an incident is resolved only with evidence: a verified remediation, a "resolved" signal from monitoring, or a person's note that Prometheus confirms. The one exception is an Administrator override when Prometheus cannot be queried, and it is recorded in the evidence. `docs/verification-report.md` section 5 records that this override was narrowed so that it never works while the alert is firing.

**Rule file and rule logic (M2.6, Q4).** The synopsis said rules are defined in a YAML file that includes a check name. The YAML catalog holds the description, severity and guidance of each rule, but the check is a Python function chosen by the rule id. Changing a threshold inside a rule therefore needs a code change, not only an edit of the YAML file. `docs/phase-0-audit.md` row 14 records that the prototype never read `policies.yaml` at all; loading the catalog from it was the fix. Why the checks stayed in code is not recorded. Reason to be stated by the team: [TO FILL].

**YAML only, no JSON parsing (TS10).** The synopsis listed JSON parsing for the security engine. The scanner accepts only `.yaml` and `.yml` files in its own `vigilops/v1` schema. `docs/college/future-scope.md` section 2 says other formats each need their own parser and that the project concentrated on the lifecycle around a finding. It does not mention JSON by name. Reason to be stated by the team: [TO FILL].

**No node_exporter or cAdvisor (TS9, M1.2, C10).** The synopsis listed one of these exporters for system and container metrics, "where practical". Neither is used. CPU and memory are measured from the application process's own counters, which are real values but not host or container metrics. The documented reason is in `docs/college/future-scope.md` section 4: exporters need host mounts and privileges that were avoided in the hardened local stack.

**ESLint (TS14).** The synopsis listed ESLint for the frontend. Ruff checks the Python code in CI, but the frontend has no ESLint configuration and no lint step. Reason to be stated by the team: [TO FILL].

**Frozen stack (TS18, RK3).** The synopsis said the stack would be frozen and that optional items would come only after the core. The core technologies were kept. Caddy and the Google Gen AI SDK were added, and several features that the synopsis does not mention were built: VigilAI, the product page, the OrbitCrate storefront and the free-hosting profile. `docs/phase-0-audit.md` lists the reverse proxy (row 26) and the assistant (row 22) as required parts of the upgrade. Why the scope was extended beyond the synopsis is not recorded. Reason to be stated by the team: [TO FILL].

**HTTPS (C11).** The synopsis diagram labels the link between the dashboard and the backend as HTTPS. The local stack uses plain HTTP on the loopback address. HTTPS is provided by the production overlay and was verified only on `localhost` with an internal certificate. `docs/verification-report.md` section 6 gives the reason: no server or domain was available.

**Deployment to a single cloud VM (SO4, Q7).** This was an optional item. The overlay `compose.prod.yaml` and the guide `docs/deployment.md` prepare it, and the merged configuration is validated in CI. It was never run on a VM, so certificate issuance and public access are untested; the deployment guide says so. The Render and Vercel profile is a different deployment (one container, not the Compose stack). It was created by the owner on 2026-11-24 and its health endpoint answered on 2026-11-25; the demonstrations were not run against it (verification report, section 8). [TO FILL: the public address, if the team wants to state it]

**Start by a teammate from the README (AC7, PL2).** The synopsis asked that a second member can start the system using only the README. The repository shows a fresh installation on the development machine and a clean build in CI. It does not show a start by another member on another machine, and `docs/verification-report.md` section 6 lists an own Ubuntu machine as not verified. [TO FILL: record one clean start by another member, with date and machine]

**Timeout tests (NG6).** The synopsis listed timeouts among the negative test cases. Timeouts of verification, of Prometheus and of the AI provider are tested. No test was found for an action handler that runs longer than its 30-second limit. `docs/architecture.md` ("Known limitations") explains that this timeout stops waiting but cannot kill the handler's thread.

**Repetition of experiments (EX0).** The synopsis said each experiment would be repeated several times. The main timings come from two or three runs. Each of the four other alert rules was run once, and the failed-remediation run is recorded once. `docs/evaluation.md` and Chapter 9 of the report state these sample sizes openly and say that the figures are not a statistical benchmark. The repository gives no reason for the small number of runs. Reason to be stated by the team: [TO FILL].

**Final report, demonstration and recorded fallback (DL5, DL6, PL9, RK4).** The evaluation, the diagrams, the demonstration script and the viva questions exist. The report exists as a full draft with blanks for the college, the guide and the team members, so it is not yet final. The recorded fallback exists as a script, `tests/e2e/record-demo.js`, and as one recording made with it on 2026-11-25; the video itself is deliberately not stored in the repository. A rehearsal cannot be shown from the repository. [TO FILL: where the team keeps the video for the demonstration day]

**Related work and references (G2, RF1, RF2).** The synopsis named Prowler, Checkov, Rundeck, StackStorm and AWS CloudWatch for the comparison. The report's Chapter 3 covers Checkov and other tools (Grafana, AWS Config, tfsec, PagerDuty, Splunk) but does not name the other four. The reference list has no entry for GitHub Actions and none for a cloud provider's security documentation, both of which the synopsis asked for. Either add them or be ready to say why the set changed. Reason to be stated by the team: [TO FILL].

### 4.3 Not done

**AWS integration with Boto3 and moto (SO1, TS17, and the moto sentence in Q7).** This was optional. Nothing of it exists: the scanner reads local YAML files and no AWS library is installed. `docs/college/future-scope.md` section 1 gives the reason for real AWS access: it needs an account and credentials, and the project was to run without any cloud account or cost. It does not say why the moto-based mock was not built. Reason to be stated by the team: [TO FILL].

**Anomaly detection (SO2).** This was optional. Only fixed thresholds are used. The repository contains no statement about it. Reason to be stated by the team: [TO FILL].

**Automatic execution of low-risk actions (SO3).** This was optional. Every execution needs an approval and a separate dispatch. `docs/architecture.md` ("Approve and execute are separate steps") records why the two steps were made impossible to skip, and `docs/college/future-scope.md` lists approval by a second person as a principle to keep. No document says that automatic execution was considered and dropped. Reason to be stated by the team: [TO FILL].

**Future scope list (F1).** The synopsis already placed these items outside version one, so this is not a failure to deliver. Say which are still planned (`docs/college/future-scope.md`) and note that anomaly detection and automatic execution no longer appear there.

## 5. Answer to "Are you using AI?"

**What the synopsis answered (p. 16):** "Version one is rule-based for reliability and explainability. Anomaly detection is an optional extension, and no capability will be claimed that is not implemented."

**What the implementation does today:**

| Area | Uses AI? | Facts | Where to see it |
|---|---|---|---|
| Alerting and incidents | No | Five fixed Prometheus alert rules with thresholds. Incidents are created and deduplicated by fixed logic. | `monitoring/alert_rules.yml`; `backend/app/services/incident_service.py` |
| Security scanning | No | Five fixed rules, SEC-001 to SEC-005. Each is a Python function without randomness. The same file always gives the same findings. | `backend/app/security_scanner/rules.py`; `security-rules/policies.yaml` |
| Remediation | No | A closed registry of two actions, ACTION-001 and ACTION-002. A request carries only an action code and needs an Administrator's approval. | `backend/app/services/remediation_catalog.py`; `backend/app/workers/actions.py` |
| Guidance shown next to an incident or finding | No | Static runbooks stored in the code, selected by alert name or rule id. | `backend/app/services/recommendations.py` |
| Anomaly detection | Not built | The optional extension named in the synopsis does not exist. | Row SO2 |
| VigilAI assistant | Yes, optionally | A chat assistant that answers questions about the platform. It was added after the synopsis. | `backend/app/assistant/`; `frontend/src/features/vigilai/` |

How VigilAI works, in the order of `backend/app/assistant/service.py`:

1. **Limits.** A message longer than 1,000 characters is rejected, and each user is limited to 10 questions per minute by default.
2. **Scope classifier.** Before any retrieval or model call, fixed patterns sort the message into one of five classes: in scope, out of scope, privileged action, secret request or prompt injection (`backend/app/assistant/scope.py`). This step uses no model. Only an in-scope message continues. The other four get a fixed refusal text, and the last three are also written to the audit trail.
3. **Retrieval.** The backend searches the project's own documentation, the 13 Markdown files in `knowledge_base/`, with BM25 keyword ranking written in plain Python (`backend/app/assistant/retrieval.py`). There is no vector database.
4. **Read-only context tools.** Keywords in the question select fixed read-only functions, for example open incidents or the monitoring summary (`backend/app/assistant/context_tools.py`). The model does not choose them. Each function checks the user's permission first.
5. **Model call, only with a key.** If `GEMINI_API_KEY` is set, the backend sends the question, recent turns, the retrieved documentation and the selected live data to the Google Gemini API through the `google-genai` SDK (`backend/app/assistant/gemini_provider.py`). The default model name is `gemini-3.5-flash-lite`. The key stays on the server.
6. **Output check.** The reply is validated and cleaned before it is shown (`backend/app/assistant/sanitize.py`).
7. **Fallback.** If no key is set, or the daily limit is reached, or the provider fails, times out or returns nothing, VigilAI answers from the same retrieved documentation and live data without a model, with a notice that live AI generation is not available.

VigilAI cannot change anything. An instruction such as "Approve all remediation requests." is classified as a privileged action and refused before any model is called; the request stays in its status (`docs/evaluation.md` section 2.6). The assistant logs usage metadata but not the text of questions or answers.

What was verified, and its limits: on 2026-11-23, with a real key, 9 of 9 platform questions were answered by the model and 6 of 6 disallowed messages were refused without a model call; the script's 19 checks passed (`docs/evidence/gemini-live.json`, `docs/verification-report.md` section 7). This used one model and a small question set. Answer quality was not evaluated systematically, and a real quota error (HTTP 429) was never observed.

**Suggested spoken answer:**

> "Detection and remediation are rule-based, as the synopsis said: Prometheus alert rules raise the incidents, five fixed rules, SEC-001 to SEC-005, find the misconfigurations, and remediation is a closed list of two actions that need an Administrator's approval. Since the synopsis we added one optional AI feature, VigilAI, a read-only assistant that answers questions about the platform. With a Google Gemini API key it sends the question, the matching parts of our own documentation and the permitted live data to Gemini; without a key it answers from the same documentation and data directly, and in both cases it cannot approve, execute or change anything. We did not build the anomaly detection that the synopsis listed as an optional extension."

Do not claim machine learning in detection, and do not claim that answer quality was evaluated beyond the small recorded check.

## 6. Open items to fill in before the viva

Facts that only the team can supply:

1. [TO FILL: state the actual duration and dates of the work] The synopsis says 24 weeks. (Row T4.)
2. [TO FILL: describe from the GitHub history how the work was spread over time] (Row PL10.)
3. [TO FILL: say how changes were reviewed] (Rows TM2, RK6.)
4. [TO FILL: describe the routine the team actually followed] (Rows TM3, RK2.)
5. [TO FILL: record one clean start by another member, with date and machine] (Rows AC7, PL2.)
6. [TO FILL: the public address of the hosted deployment, if the team wants to state it] (Rows SO4, Q7.)
7. [TO FILL: where the team keeps the video for the demonstration day] (Rows DL6, RK4.)

Reasons that the repository does not record ("Reason to be stated by the team: [TO FILL]" in section 4):

9. Why the project was renamed (T1).
10. Why incidents are not created from security findings (M3.3).
11. Why the incident statuses differ from the synopsis (M3.2).
12. Why SEC-003 is Critical and not High (M2.3).
13. Why the table names differ (DT2, DT6, DT7).
14. Why the API paths differ from the proposed ones (AP4, AP6 to AP11).
15. Why the GitHub remote has only a `main` branch and no `develop` or feature branches (TS16).
16. Why policies cannot be managed in the application (R1).
17. Why the rule checks are Python code and not data in the YAML file (M2.6, Q4).
18. Why JSON input was left out (TS10).
19. Why ESLint was not set up (TS14).
20. Why the scope was extended beyond the synopsis, in particular with VigilAI (TS18, RK3).
21. Why the related-work comparison and the reference list use a different set (G2, RF1, RF2).
22. Why most experiments were run only once to three times (EX0).
23. Why the moto-based AWS mock was not built (SO1).
24. Why anomaly detection was not built (SO2).
25. Why automatic execution was not built (SO3).

Things to bring up to date in the repository (not blanks in this document, but useful before submission):

- Add the failed-remediation run of 2026-11-24 to `docs/evaluation.md`. The report's Chapter 9 already has it (row RP1).
- Fill the `[TO FILL]` blanks in `docs/college/project-report.md` and settle its reference list (rows DL5, RF1).
- Run the test suites and the CI workflow once more and record the current totals, because test files were added after the recorded results of 2026-11-23 (table 3.16, rows PL8 and DL3).
- The CI workflow lists `develop` as a trigger branch although no such branch exists (row TS16).
- The demonstration script's heading says "about 12 to 15 minutes" but its plan table adds up to about 16 minutes (row DL6).
