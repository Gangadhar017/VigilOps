# Phase 0 – Repository Audit and Gap Analysis

**Repository audited:** `github.com/Gangadhar017/CloudShield`, branch `main`, commit `a433fc7`
**Audit date:** 2026-11-23
**Method:** every tracked file (92 files, about 10,700 lines excluding the npm lock file) was read; the existing
test suite was run unmodified as a baseline. No file was changed during the audit.

Statuses: `IMPLEMENTED` · `PARTIAL` · `MISSING` · `BROKEN` · `UNVERIFIED`

## 1. Baseline test result

```
cd <repo> && PYTHONPATH=. pytest backend/tests -q
15 passed, 1 warning in 5.56s
```

The 15 tests passed, but they run against in-memory SQLite and never start Prometheus, the demo
application, a worker or the Docker stack, so they did not reveal the defects listed below.

## 2. What the repository contained

| Area | Files | Summary |
|---|---|---|
| Backend | `backend/app/**` (FastAPI, SQLAlchemy, Pydantic) | 7 routers, 4 services, 7 tables, JWT + bcrypt auth |
| Scanner | `backend/app/services/scanner_service.py` | Five hard-coded checks SEC-001…005 over a single-resource YAML schema |
| Remediation | `remediation/actions.py` | `ACTION_REGISTRY` allowlist dictionary, executed inline by the API process |
| Demo app | `test-app/app.py` | FastAPI app exposing Prometheus gauges |
| Monitoring | `monitoring/prometheus.yml`, `alert_rules.yml` | Scrape config and 5 alert rules |
| Frontend | `frontend/src/**` (React 18, Vite, Tailwind, Recharts) | 11 pages, about 5,600 lines |
| Deployment | `compose.yaml`, Dockerfiles, `render.yaml`, `vercel.json` | 5 Compose services |
| Docs / CI | `docs/*.md`, `.github/workflows/ci.yml` | Report material, pytest + build workflow |

## 3. Gap matrix

| # | Feature | Status | Evidence | Required action |
|---|---|---|---|---|
| 1 | Backend container starts | **BROKEN** | `backend/Dockerfile` uses build context `./backend` and runs `app.main:app`, but every module imports `backend.app...` and `remediation.actions`, and the scanner reads `../../../security-rules`. Neither `backend/` (as a package), `remediation/` nor `security-rules/` exists inside the image. | Make the backend a self-contained package (`app.*`), build from the repository root, copy the rule catalog and knowledge base into the image. |
| 2 | Frontend container reachable | **BROKEN** | `frontend/Dockerfile` serves nginx on port 80; `compose.yaml` publishes `5173:5173`. Nothing listens on 5173 in the container. | Serve the build through a reverse proxy on a correct port. |
| 3 | PostgreSQL persistence | **PARTIAL** | `core/database.py` silently falls back to SQLite when PostgreSQL is unreachable; schema made with `create_all`; Alembic is listed as a dependency but there are no migrations. | Remove the silent fallback; add Alembic migrations; preserve any legacy data. |
| 4 | Secure authentication | **BROKEN** | `POST /api/auth/register` is unauthenticated and accepts `"role": "admin"`: anyone can create an Administrator. `SECRET_KEY` and the database password are hard-coded in `config.py`, `compose.yaml` and `.env.example`. Tokens last 24 h; no logout, no rate limiting, no `is_active`. | Remove public registration; admin-only user management; secrets only from the environment; token revocation, expiry, login rate limiting. |
| 5 | Frontend login | **BROKEN** | `LoginPage.jsx` shows a fake "FIDO2 hardware key" dialog (`handleSimulateKeyTouch`) and, when the real login fails, signs in as `admin@cloudshield.local / Admin@123` instead. | Real login form with real error handling. |
| 6 | RBAC | **PARTIAL** | `require_admin` protects approve/execute; but simulation, scan, sample-reset and resource creation are open to any user, and Operators can inject faults. Operator approval returns 403 (kept). | Central permission matrix enforced on every endpoint; denied attempts audited. |
| 7 | Dashboard shows real data | **BROKEN** | `DashboardPage.jsx` contains hard-coded series (`cpuTelemetryData` "with 84% spike at 10:30"), `IncidentsPage.jsx` a hard-coded `incidentsList` (INC-8041 …), `SecurityPosturePage.jsx` `defaultMockFindings`, `Sidebar.jsx` a fixed incident badge "4", "99.8% OK" and the name "Alex Rivera". | Rebuild pages on real APIs with loading, empty and error states. |
| 8 | Genuine telemetry | **BROKEN** | `test-app/app.py` produces CPU, memory and latency with `random.uniform(...)`. `monitoring_service.py` substitutes defaults (`cpu_val = 24.5`, `mem_val = 45.2`) when the app is unreachable. `seed.py` inserts 30 minutes of invented metric history. | Real instrumentation (request counters, latency histogram, process CPU/memory); never substitute values; no seeded metrics. |
| 9 | Prometheus integration | **PARTIAL** | Prometheus scrapes the demo app, but the backend never queries Prometheus: it scrapes the app itself with a 0.3 s timeout and stores rows in a `metrics` table. Scrape targets include `localhost` entries that are always down. | Backend reads all telemetry from the Prometheus HTTP API. |
| 10 | Alertmanager | **MISSING** | No Alertmanager service or configuration. Alert rules exist but are routed nowhere. | Add Alertmanager and route alerts to a webhook. |
| 11 | Alert → incident | **PARTIAL** | `POST /api/monitoring/webhook` exists but is unauthenticated, unvalidated (`payload: dict`), ignores `resolved` alerts, and nothing calls it. Incidents are actually created by the backend's own threshold checks. | Protected, validated webhook; handle firing, repeated and resolved alerts. |
| 12 | Incident deduplication | **PARTIAL** | `_upsert_incident` reuses an open incident with the same fingerprint (application-level only; no database constraint; no occurrence tracking). | Keep the idea; enforce with a partial unique index; count notifications. |
| 13 | Incident lifecycle | **PARTIAL** | Only `open`, `acknowledged`, `resolved`; no transition validation, no timeline, acknowledging is unaudited. | Five statuses, validated transitions, event timeline, evidence-based resolution. |
| 14 | Security rules SEC-001…005 | **PARTIAL** | Detection logic exists and is deterministic (reused as the basis of the new rules). One resource per type, so findings cannot identify a resource; `policies.yaml` is never read. | Multi-resource schema, rule catalog loaded from `policies.yaml`, evidence per resource. |
| 15 | Scanner input safety | **BROKEN** | `POST /api/findings/scan?target_file=<any path>` opens any path on the server (directory traversal / arbitrary file read attempt); no size limit. `yaml.safe_load` is used (kept). | Authorised workspace only; name validation; size limit; reject anchors. |
| 16 | Scan history / finding lifecycle | **PARTIAL** | No scan table. Findings keyed by `rule_id` per file; statuses `open`/`resolved` only. | Scan history, stable finding key, four finding states. |
| 17 | Remediation approval | **PARTIAL** | `execute` accepts a job that is still `pending`, so approval can be skipped; no self-approval rule; rejection is stored as `failed`. | Full state machine; approval and dispatch as separate, enforced steps. |
| 18 | Restricted worker | **MISSING** | Actions run inside the API process, which therefore has write access to the configuration files. | Separate worker process with the only write access. |
| 19 | Remediation verification | **BROKEN** | Every `FIX_SEC_*` action returns `"verification_passed": ok` where `ok` only means "the file was written", and the service then sets `finding.status = "resolved"` directly. A `SIMULATE_FAILED_ACTION` entry fabricates a failure. | Verify with an independent re-scan / monitoring evidence; never set the result by hand. |
| 20 | ACTION-001 application recovery | **PARTIAL** | Calls the unauthenticated `POST /simulate/recover` and polls `/health` for 5 s. Any client can inject or clear faults. | Token-protected recovery endpoint; verification against Prometheus. |
| 21 | Audit logging | **PARTIAL** | `audit_logs` table and `log_audit` exist (kept as a concept) but logins, incident changes and denied actions are not audited; no event id, outcome vocabulary or correlation id; each entry commits separately from the change it describes. | Complete coverage, same-transaction writes, append-only guarantee. |
| 22 | VigilAI assistant | **MISSING** | No AI code, knowledge base or chat widget. | Implement per specification. |
| 23 | Demo controls gated | **BROKEN** | `/api/monitoring/simulate` and `/api/findings/reset-sample` are always enabled for every user; the simulate endpoint reports success even when the demo app is unreachable. | Admin-only, disabled in production, truthful results. |
| 24 | Health endpoints | **PARTIAL** | Single `/api/health` returning a constant; no liveness/readiness split; backend exposes no `/metrics`. | `/health/live`, `/health/ready`, `/metrics`. |
| 25 | CORS / headers | **BROKEN** | `allow_origins=["*"]` together with `allow_credentials=True`. | Same-origin through the reverse proxy; explicit origins only. |
| 26 | Reverse proxy / HTTPS | **MISSING** | nginx config proxies `/api` only; no production overlay. | Caddy reverse proxy and production Compose overlay. |
| 27 | Tests | **PARTIAL** | 15 tests; several assert the insecure behaviour (open registration). No frontend or end-to-end tests. | New unit, integration, frontend and end-to-end suites. |
| 28 | CI | **PARTIAL** | Workflow runs pytest, an "evaluation benchmark" and a frontend build. | Test both databases, lint, validate configuration, run the stack. |
| 29 | Documentation | **PARTIAL** | `docs/evaluation-results.md` reports benchmark figures produced by `scripts/run_evaluation.py` against the simulated system. | Rewrite; measured values only. |
| 30 | Unrelated files | — | `optimize_disk.bat` disables Windows hibernation and edits the page-file registry key; unrelated to the project. `render.yaml` / `vercel.json` deploy the backend alone on SQLite and the mock frontend. | Remove from the working tree (they remain in Git history). |

## 4. What was preserved

* Technology choices and versions: React 18 + Vite 5 + Tailwind 3.4 + React Router 6 + Axios + Recharts +
  Lucide; FastAPI + Pydantic 2 + SQLAlchemy 2 + bcrypt + python-jose; PostgreSQL 16; Prometheus v2.51.0.
* Repository layout: `backend/app/{api,core,models,schemas,services}`, `frontend/`, `monitoring/`,
  `security-rules/`, `test-app/`, `scripts/`, `docs/`, `compose.yaml`.
* The five rule identifiers, their names, severities and the essence of each detection condition.
* The idea of an allowlisted action registry, of fingerprint-based incident deduplication, of the
  audit service, and the Operator → HTTP 403 behaviour on approval.
* The demo application's role as the monitored workload (its metrics are now real).
* The light/dark theme toggle and the JWT-in-Axios-interceptor pattern.
* Complete Git history: nothing was rewritten. The work is in the working tree of branch
  `vigilops-upgrade`, created from the original `main` (commit `a433fc7`); committing it is left to
  the repository owner.

## 5. Decisions recorded

1. **The audit, not a rebuild, drove the scope.** Items marked BROKEN in §3 could not be repaired in
   place because the behaviour itself was simulated (rows 5, 7, 8, 19); those parts were rewritten.
2. **Configuration schema changed** from one resource per type to a `resources:` list
   (`schema_version: vigilops/v1`) so that a finding can name the affected resource and remediation
   can be verified per resource. The three old sample files were replaced by fixtures in the new schema.
3. **Legacy data is not deleted.** If the initial migration finds CloudShield tables in PostgreSQL it
   moves them, with their data, into the `legacy_cloudshield` schema.
4. **Development sequence.** The specification asks for one phase at a time with an explicit "NEXT".
   The project owner instead gave full authority to complete the build in one pass, so phases 1–11
   were carried out consecutively; each phase's verification is recorded in
   [`verification-report.md`](verification-report.md).
