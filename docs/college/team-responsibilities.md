# VigilOps: Secure Cloud Operations - Team Responsibilities

Four-member ownership for the B.Tech major project, mapped to the modules and files of this repository. The division follows the one in the project synopsis (frontend; backend, database and access control; monitoring, test application and security scanner; Docker Compose, remediation, CI/CD and hardening) and adds the parts that were built beyond the synopsis: the VigilAI assistant, the product page, the OrbitCrate storefront and the hosted deployment.

> **To be filled in by the team**
>
> | Member | Name | Roll number | Signature |
> |---|---|---|---|
> | Member 1 | __________________ | ____________ | ____________ |
> | Member 2 | __________________ | ____________ | ____________ |
> | Member 3 | __________________ | ____________ | ____________ |
> | Member 4 | __________________ | ____________ | ____________ |
>
> Institution: ____________________  Guide: ____________________

## Principle: every member understands the complete project

Ownership decides who maintains a module, who writes the corresponding part of the report and who answers first in the viva. It does not limit what a member must know. An examiner may ask any member about any part of the system, so **all four members must understand the complete project**: the architecture, the demonstrations, the security model, the limitations and what was not verified. The section "What every member must be able to do" at the end is a minimum that applies to everyone.

## Ownership at a glance

| Member | Area | Main directories |
|---|---|---|
| Member 1 | Frontend and user interface | `frontend/src/` (pages, components, contexts, hooks, API wrappers, the VigilAI widget, the product page), `tests/e2e/` |
| Member 2 | Backend, database, access control and the assistant backend | `backend/app/main.py`, `backend/app/core/`, `backend/app/models/`, `backend/app/schemas/`, `backend/alembic/`, authentication, users, settings and audit APIs, `backend/app/assistant/`, `knowledge_base/` |
| Member 3 | Monitoring, the demonstration application, incidents and the security scanner | `test-app/`, `monitoring/`, monitoring and incident services and APIs, `backend/app/security_scanner/`, `security-rules/`, the scan service and API |
| Member 4 | Remediation, deployment, CI/CD and verification | `backend/app/workers/`, remediation services and API, `compose.yaml`, `compose.prod.yaml`, `reverse-proxy/`, `deploy/render/`, `.github/workflows/`, `scripts/` |

Documentation is shared: each member writes and maintains the documents of their own area, and Member 4 keeps `README.md`, `docs/verification-report.md` and `docs/evaluation.md` consistent with them.

---

## Member 1 - Frontend and user interface

**Owns**

| Part | Files |
|---|---|
| Application shell and routing | `frontend/src/main.jsx`, `App.jsx`, `layouts/AppLayout.jsx`, `index.css`, `config/links.js` |
| Pages | `pages/Landing.jsx` (product page), `Login.jsx`, `Dashboard.jsx` (Overview), `Monitoring.jsx`, `Incidents.jsx`, `IncidentDetail.jsx`, `Findings.jsx`, `FindingDetail.jsx`, `Remediation.jsx`, `RemediationDetail.jsx`, `AuditLogs.jsx`, `Help.jsx`, `Settings.jsx` |
| Shared components | `components/Sidebar.jsx`, `Header.jsx`, `PageHeader.jsx`, `DataTable.jsx`, `Filters.jsx`, `StatusBadge.jsx`, `States.jsx`, `MetricCard.jsx`, `TimeSeriesChart.jsx`, `Timeline.jsx`, `DataSourceTag.jsx`, `Modal.jsx` (with `ConfirmDialog`), `RequestRemediation.jsx` |
| Assistant in the browser | `features/vigilai/VigilAIWidget.jsx`, `VigilAIChat.jsx`, `SafeText.jsx`, `SuggestedQuestions.jsx`, `api/vigilai.js` |
| State and data access | `context/AuthContext.jsx`, `ThemeContext.jsx`, `ToastContext.jsx`, `hooks/useApi.js`, `hooks/useServerStatus.js`, `utils/format.js`, `api/client.js` and the other files in `api/` |
| Build | `frontend/package.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `index.html`, the build stage of `frontend/Dockerfile` |
| Tests | `frontend/src/test/app.test.jsx`, `landing.test.jsx`, `vigilai.test.jsx`, `setup.js`; the browser tests `tests/e2e/specs/platform.spec.js` and `public.spec.js`; the screenshot and recording tools `tests/e2e/screenshots.js` and `record-demo.js` |

**Deliverables**

- Every page works against the real API with loading, empty and error states, in both the light and the dark theme, and on a phone-sized screen.
- The product page states only what the implementation does, and offers sign-in only.
- Screenshots of every page for the report and the slides, and the recorded walkthrough.
- Frontend tests pass (`npm test` in `frontend/`), the production build succeeds (`npm run build`) and the browser tests pass against the running stack.
- Report: user-interface parts of Chapters 5 and 7, the user-guide appendix. Presentation: slides 1, 2, 8 and 15.

**Must be able to explain**

- How routing decides between the product page, the sign-in page and the console, and what happens on an HTTP 401 (the interceptor in `api/client.js`).
- Why the token is kept in `sessionStorage` and sent in a header, and what that means for CSRF and XSS.
- Why hiding a button is not access control: `can(permission)` is a hint; the backend enforces.
- How `useApi` polls, why polling stops in a hidden tab, and why a metric card shows "Unavailable" instead of a number.
- How the remediation detail page shows the workflow stepper, the configuration diff and the verification checks.
- Why the assistant's answers are rendered as text only (`SafeText.jsx`), and how the Content-Security-Policy limits what a page may load.

**Must be able to demonstrate**

- The opening: the product page, and an order placed in OrbitCrate.
- Sign-in as both roles and the differences in the interface (no "Users" tab, no "Approve" button, disabled demo controls for the Operator).
- The Operator window during the demonstrations.

---

## Member 2 - Backend, database, access control and the assistant backend

**Owns**

| Part | Files |
|---|---|
| Application and cross-cutting code | `backend/app/main.py`, `core/config.py`, `core/database.py`, `core/logging.py`, `core/request_context.py`, `core/metrics.py`, `core/rate_limit.py` |
| Authentication and access control | `core/security.py`, `core/permissions.py`, `api/auth.py`, `api/users.py` |
| Data model | `models/models.py`, `schemas/schemas.py`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic.ini` |
| Audit and settings | `services/audit_service.py`, `api/audit.py`, `services/settings_service.py`, `api/settings.py`, `services/bootstrap.py`, `api/router.py`, `api/deps.py` |
| Assistant backend | `backend/app/assistant/service.py`, `scope.py`, `retrieval.py`, `context_tools.py`, `prompts.py`, `providers.py`, `gemini_provider.py`, `sanitize.py`, `api/assistant.py` |
| Knowledge base | every file in `knowledge_base/` |
| Packaging and operations | `backend/Dockerfile`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pytest.ini`, `backend/ruff.toml`, `scripts/generate_env.py`, `scripts/backup_db.sh`, `scripts/restore_db.sh` |
| Tests | `backend/tests/conftest.py`, `tests/unit/test_core.py`, `tests/integration/test_auth_rbac.py`, `tests/integration/test_postgres.py`, the audit tests in `tests/integration/test_audit_monitoring.py`, `tests/unit/test_assistant_guards.py`, `tests/integration/test_assistant.py`, `scripts/verify_gemini_live.py` |

**Deliverables**

- The API starts only with valid configuration, applies its migrations, and exposes separate liveness and readiness probes.
- An assistant that answers only platform questions, is read-only, respects the caller's role and falls back to documentation answers; a knowledge base that matches the code.
- The database chapter of the report (Chapter 6) with the data dictionary and the constraint table; the authentication, RBAC and VigilAI parts of Chapter 7; the permission matrix.
- Backend tests pass on SQLite and on PostgreSQL. Presentation: slides 5, 6, 7 and 12.

**Must be able to explain**

- The sign-in flow, the JWT claims, token revocation by `jti` and session invalidation by `token_version`.
- The permission matrix and `require_permission`, including the audited HTTP 403.
- Sign-in rate limiting and why it is in process; the password policy and the bcrypt 72-byte limit.
- The thirteen tables, the partial unique indexes, the CHECK constraints and the append-only audit trigger.
- Why an audit record is written in the same transaction as the change, and what the correlation ID is.
- The start-up checks: required secrets, refusal of placeholder values in production mode.
- The assistant pipeline and its safeguards, in order, and which of them run before any model is called: scope classification, BM25 retrieval, permission-checked read-only context, prompt construction, output validation, the documentation fallback.
- How live Gemini generation was verified with a real API key (`docs/evidence/gemini-live.json`) and, plainly, that real quota exhaustion was never observed and that answer quality was not evaluated systematically.

**Must be able to demonstrate**

- The Administrator window during the demonstrations (approve, execute, close, demo controls).
- User management under Settings, tab "Users", and the audit trail filtered by category, outcome and correlation ID.
- DEMO 3 as narrator: documentation question, live-data question, guidance, refusal of unrelated, privileged, secret and injection messages, and the fallback.

---

## Member 3 - Monitoring, the demonstration application, incidents and the security scanner

**Owns**

| Part | Files |
|---|---|
| Monitored application (OrbitCrate) | `test-app/app.py`, `test-app/static/` (page, script, styles), `test-app/Dockerfile`, `test-app/requirements.txt` |
| Monitoring configuration | `monitoring/prometheus.yml`, `monitoring/alert_rules.yml`, `monitoring/alertmanager.yml` |
| Monitoring services | `backend/app/services/monitoring_service.py`, `services/dashboard_service.py`, `api/monitoring.py` (including the alert webhook) |
| Incident engine | `services/incident_service.py`, `api/incidents.py`, the alert runbooks in `services/recommendations.py` |
| Demo controls | `services/demo_service.py`, `api/demo.py` |
| Scanner | `backend/app/security_scanner/engine.py`, `security_scanner/rules.py` |
| Rule catalog and fixtures | `security-rules/policies.yaml`, `security-rules/samples/baseline/`, `samples/insecure/`, `samples/secure/` |
| Scan service | `services/scan_service.py`, `api/security.py`, the rule fix steps in `services/recommendations.py` |
| Tests | `test-app/tests/test_store.py`, `backend/tests/integration/test_incidents.py`, the monitoring and demo-control tests in `tests/integration/test_audit_monitoring.py`, `backend/tests/unit/test_scanner.py`, `tests/integration/test_scanning.py`, `scripts/verify_alert_rules.py`, `scripts/evaluate_scanner.py` |

**Deliverables**

- Real instrumentation of the demonstration application and a working chain from scrape to alert to incident.
- Five rules with fixtures that prove detection and absence of false positives; a finding lifecycle that never deletes.
- The monitoring, incident and scanner parts of Chapter 7 and the existing-systems chapter (Chapter 3) of the report; the incident lifecycle and scanning-flow diagrams.
- The alert-to-incident, deduplication, alert-rule and scanner measurements for the evaluation. Presentation: slides 3, 4, 9 and 10.

**Must be able to explain**

- Why the telemetry is real although the store's orders are not, and how each fault mode changes the measurements and what a visitor sees.
- What of the store is public (`/orbitcrate/`: the page, its static files, its store API) and what is not (`/internal/*`, `/metrics`, `/health/*`), and how visitors' orders are kept apart and bounded.
- The scrape configuration, each of the five alert rules and its PromQL, `for`, `group_wait`, `group_interval` and `repeat_interval`.
- Webhook protection, payload validation, and the handling of firing, repeated and resolved alerts.
- Deduplication by fingerprint with the partial unique index, including the concurrent case.
- The incident lifecycle, evidence-based resolution, the reopen window, "Simulated fault" and "Signal stale".
- Why the backend accepts only catalog metrics and never raw PromQL.
- The scope of the scanner (local YAML, `vigilops/v1`) and each rule's detection logic, severity and impact.
- Scanner input safety: file-name pattern, path confinement, size limit, anchors and aliases, safe loading; the stable finding key and the transitions OPEN, REMEDIATION_PENDING, RESOLVED, ACCEPTED_RISK.

**Must be able to demonstrate**

- DEMO 1 as narrator: healthy state, outage, the store answering HTTP 503, monitoring signal, alert, incident, and the refusal to resolve while the alert is firing.
- The scan part of DEMO 2: reset, scan, the five findings, SEC-001 detail with its evidence.
- The Prometheus and Alertmanager user interfaces on the local ports, if the examiner asks.

---

## Member 4 - Remediation, deployment, CI/CD and verification

**Owns**

| Part | Files |
|---|---|
| Remediation workflow | `backend/app/services/remediation_service.py`, `services/remediation_catalog.py`, `api/remediation.py` |
| Restricted worker and action registry | `workers/remediation_worker.py`, `workers/actions.py`, `workers/verification.py`, `workers/healthcheck.py` |
| Integration and deployment | `compose.yaml`, `compose.prod.yaml`, `reverse-proxy/Caddyfile`, `.env.example`, the final stage of `frontend/Dockerfile` |
| Hosted profile | `render.yaml`, `deploy/render/Dockerfile`, `deploy/render/launcher.py`, `frontend/vercel.json`, `backend/app/api/store.py` (the storefront pass-through) |
| CI/CD | `.github/workflows/ci.yml` |
| Verification | `scripts/run_e2e_demos.py`, `scripts/run_failed_remediation_demo.py`, `scripts/verify_stack.sh`, and coordination of `backend/tests/integration/test_hardening.py` (cross-module regression tests; each member maintains the cases for their own module) |
| Tests | `backend/tests/integration/test_remediation.py`, `test_hosted_profile.py`, `test_store_proxy.py`, the row-locking test in `tests/integration/test_postgres.py` |
| Documents kept consistent | `README.md`, `docs/verification-report.md`, `docs/evaluation.md`, `docs/evidence/` |

**Deliverables**

- Two automated actions that succeed only after verification, executed by the worker, and a failed run that is reported as failed.
- One-command deployment, a passing CI workflow, the single-container image for the hosted profile, and the evidence files in `docs/evidence/`.
- The remediation part of Chapter 7, the testing and evaluation chapters (Chapters 8 and 9) and the limitations and future scope of Chapter 10, with every value taken from [`../evaluation.md`](../evaluation.md) and [`../verification-report.md`](../verification-report.md); the remediation-sequence and deployment diagrams. Presentation: slides 11, 13 and 14.

**Must be able to explain**

- The remediation state machine, the self-approval rule, and why approval and dispatch are separate.
- The worker's isolation, `FOR UPDATE SKIP LOCKED`, the refusal of unapproved requests and the recovery of interrupted executions.
- Exactly how each action is verified, and why ACTION-001 cannot start a stopped container.
- The Compose services, the network exposure and the container hardening (unprivileged users, read-only file systems, dropped capabilities), and what the reverse proxy routes.
- The production overlay and, plainly, that the HTTPS deployment was not tested on a real domain; the hosted profile on Render and Vercel and what is and is not verified about it.
- The jobs of the CI workflow, the test levels, what the fakes leave unproven, and how each evaluation metric is measured.

**Must be able to demonstrate**

- The remediation part of DEMO 2 as narrator: request, approval, execution, diff, verification scan, resolved finding.
- DEMO 4: a failed remediation and the retry path (`python scripts/run_failed_remediation_demo.py`, or by hand).
- `python scripts/run_e2e_demos.py` and `sh scripts/verify_stack.sh` in a terminal, and how to read their output; the recorded fallback if the live demonstration cannot continue.

---

## Shared responsibilities

1. **Accuracy.** No member writes a number, a test count or a citation that was not measured or read. Values come from the evaluation and verification documents; statements about behaviour come from the code.
2. **Review.** Every change is read by at least one other member before it is accepted; a change to a module is reviewed by a member who does not own it, which also spreads knowledge.
3. **Documentation follows code.** A change in behaviour updates the knowledge base, the relevant document in `docs/` and, if needed, this folder in the same change.
4. **Security hygiene.** The `.env` file is never committed, shown on a projector or pasted into a document; passwords and tokens are never printed.
5. **Verification before submission.** The whole team runs the backend tests, the frontend tests, `scripts/verify_stack.sh` and the end-to-end demonstrations together, and records the result with its date.
6. **Honest reporting.** Limitations and unverified items (real Gemini quota exhaustion, public HTTPS deployment) appear in the report, the slides and the viva answers of every member.
7. **Report and presentation.** Each member drafts the sections listed under their deliverables; all members read the full report before submission.
8. **Integration, testing and documentation are everybody's work**, as the synopsis states: owning an area does not excuse a member from testing and documenting the others' parts.

## Demonstration and presentation roles

| Activity | Member 1 | Member 2 | Member 3 | Member 4 |
|---|---|---|---|---|
| Slides ([`presentation-outline.md`](presentation-outline.md)) | 1, 2, 8, 15 | 5, 6, 7, 12 | 3, 4, 9, 10 | 11, 13, 14 |
| Live demonstration ([`demo-script.md`](demo-script.md)) | Presents the opening; operates the Operator window | Operates the Administrator window; narrates DEMO 3 | Narrates DEMO 1 and the scan part of DEMO 2 | Narrates the remediation part of DEMO 2 and DEMO 4; runs the fallback if needed |
| Viva ([`viva-questions.md`](viva-questions.md)) - answers first on | React, API security (browser side), the product page | FastAPI, PostgreSQL, Authentication, RBAC, Audit logs, Gemini API, RAG, Prompt injection | Cloud computing, Monitoring, Prometheus, Alertmanager, Incident management, IAM, Security scanning, the demonstration application | Remediation, Docker, Deployment, Testing |

The roles should be rotated at least once during rehearsal, so that each member has operated both windows and narrated a demonstration other than their own.

## What every member must be able to do

Each member, alone and without notes:

- Start the stack with Docker Compose, check that it is healthy, and sign in as Administrator and as Operator.
- Perform the demonstrations from [`demo-script.md`](demo-script.md), including the reset between runs.
- Draw the architecture from memory: the seven services, which one is exposed, what the worker may and may not do, and the alert flow.
- Explain the permission matrix and show an Operator being refused.
- Explain how duplicate incidents are prevented and how a remediation is verified, and what happens when it fails.
- Explain why the assistant cannot act and what happens when the model provider is unavailable.
- State the limitations and the two unverified items without being prompted.
- Run the backend tests (`pytest` in `backend/`) and the frontend tests (`npm test` in `frontend/`) and explain what a failing test would mean.
- Answer the questions marked **(hard)** in [`viva-questions.md`](viva-questions.md).

## Suggested working routine

- Short planning meeting at the start of each week: what each member will finish and what they need from the others.
- Work on separate branches; merge only after review and a passing CI run.
- One integration session each week with the full stack running, in which a member other than the owner demonstrates each new feature.
- Before each review with the guide: run the end-to-end script and update the documents that changed.
