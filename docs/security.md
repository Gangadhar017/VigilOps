# VigilOps Security

This document describes the security design of VigilOps as it is implemented: what is protected, from whom, by which mechanism, and what is not protected. Each control names the module or function that implements it so that it can be checked against the code. The last section lists the residual risks and limitations of the current build.

Statements about containers, mounts, the internal network and published ports describe the Docker Compose stack, which is the reference deployment. The free-hosting variant that runs the components in one container is described in [deployment-render-vercel.md](deployment-render-vercel.md).

Related documents: [Architecture](architecture.md) · [API reference](api.md) · [Configuration](configuration.md) · [Deployment](deployment.md) · [Verification report](verification-report.md) · [Evaluation](evaluation.md)

## Contents

- [Threat model](#threat-model)
- [Authentication](#authentication)
- [Role-based access control](#role-based-access-control)
- [Secrets handling and start-up checks](#secrets-handling-and-start-up-checks)
- [Network exposure and reverse-proxy headers](#network-exposure-and-reverse-proxy-headers)
- [Input validation](#input-validation)
- [Scanner safety](#scanner-safety)
- [Remediation safety model](#remediation-safety-model)
- [Audit integrity](#audit-integrity)
- [VigilAI safeguards](#vigilai-safeguards)
- [Logging and redaction](#logging-and-redaction)
- [Demo-control gating](#demo-control-gating)
- [Container hardening](#container-hardening)
- [Residual risks and limitations](#residual-risks-and-limitations)

## Threat model

### Assets

| Asset | Why it matters |
|---|---|
| User credentials and sessions | An Administrator session can approve and dispatch remediation and manage users |
| The remediation capability | It is the only part of the platform that changes something outside the database: a configuration file or the state of the demo application |
| Configuration files in the scan workspace | They are both the scanner's input and the target of ACTION-002 |
| The audit trail | It is the evidence of who did what; it is only useful if it cannot be rewritten |
| Secrets | JWT signing key, database password, Alertmanager webhook token, demo control and recovery tokens, Gemini API key, bootstrap passwords |
| Operational records | Incidents, findings, remediation history |
| The Gemini quota | A free-tier key can be exhausted by abuse |

### Actors

| Actor | Assumed capability |
|---|---|
| Anonymous network client | Can reach the published web port; may guess passwords or send crafted requests |
| Operator | Authenticated, honest but may make mistakes; may be curious about actions reserved for Administrators |
| Administrator | Authenticated and trusted with approvals; may still make mistakes, which is why self-approval is refused by default |
| Compromised or buggy API process | Can run code with the backend's privileges and credentials |
| Malicious content | Text inside alerts, YAML files, chat messages or model output that tries to change behaviour (injection) |
| Other containers on the internal network | Can reach the unauthenticated internal endpoints |

Out of scope: an attacker with root on the Docker host, physical access, or a compromised PostgreSQL superuser.

### Trust boundaries

| Boundary | Control at the boundary |
|---|---|
| Internet or LAN to `web` (Caddy) | Only `/api/*` is proxied; security headers; TLS in production |
| `web` to `backend` | JWT on every `/api` route except login, health, version and the webhook |
| Alertmanager to `backend` | Dedicated bearer token compared in constant time; user JWTs are not accepted on the webhook |
| `backend` to PostgreSQL | Parameterised queries through SQLAlchemy; CHECK constraints, unique indexes, append-only trigger |
| `backend` to the scan workspace | Read-only mount |
| `backend` to `worker` | No direct channel. The only link is the `remediation_requests` queue, and the worker re-checks the recorded approval |
| `worker` to the demo application | Separate recovery token, held by the worker and not by the backend |
| `backend` to Google Gemini | Outbound HTTPS only; scope check before, validation after; the key never leaves the backend |
| Model output to the browser | Validation, sanitisation, and rendering as text nodes |

### Main threats and mitigations

| Threat | Mitigation | Where |
|---|---|---|
| Password guessing | bcrypt, login rate limiting, generic error message, timing equalisation | `core/security.py`, `api/auth.py` |
| Stolen or stale token | 60-minute expiry, server-side revocation on logout, `token_version` invalidation | `core/security.py` |
| Privilege escalation by an Operator | Central permission matrix enforced by a dependency on every privileged route; refusals audited | `core/permissions.py` |
| Self-registration as Administrator (present in the prototype) | No registration endpoint; users are created by Administrators only | `api/users.py` |
| Remediation without approval (present in the prototype) | Separate approve and execute transitions; worker refuses rows without an approver | `services/remediation_service.py`, `workers/remediation_worker.py` |
| Arbitrary command or file access through remediation | Allowlisted action codes only; hard-coded handlers; path confinement | `services/remediation_catalog.py`, `workers/actions.py` |
| Reading arbitrary server files through the scanner (present in the prototype) | Target must be a plain file name inside the workspace; resolved path re-checked | `services/scan_service.py` |
| Malicious YAML | `yaml.safe_load`, anchors and aliases rejected, size and resource-count limits | `security_scanner/engine.py` |
| Forged alerts | Webhook token; strict payload schema and limits | `api/monitoring.py`, `schemas/schemas.py` |
| PromQL injection | Metric catalog, validated job names, range presets | `services/monitoring_service.py` |
| Tampering with audit history | No update or delete code path; PostgreSQL trigger | `services/audit_service.py`, migration `0001` |
| Prompt injection, data exfiltration through the assistant | Nine safeguards, read-only tools, role checks | `assistant/*.py` |
| Cross-site scripting | React escaping, no HTML rendering of data, Content-Security-Policy | `frontend/src`, `reverse-proxy/Caddyfile` |
| Cross-site request forgery | No cookies: the token is sent in the `Authorization` header | `frontend/src/api/client.js` |
| Clickjacking | `X-Frame-Options: DENY`, `frame-ancestors 'none'` | `reverse-proxy/Caddyfile` |

## Authentication

Implemented in `backend/app/core/security.py` and `backend/app/api/auth.py`.

**Passwords**

- Stored as bcrypt hashes with cost factor 12 (`hash_password`). Plain passwords are never stored or logged.
- bcrypt considers only the first 72 bytes of its input. Instead of truncating silently, the policy rejects longer passwords and `verify_password` never reports a match for an over-long input.
- Password policy (`validate_password_strength`): at least 10 characters, at most 72 bytes, both upper-case and lower-case letters, and at least one digit. It is applied when a user is created, when an Administrator resets a password, when a user changes their own password, and to the bootstrap accounts (in production mode the API refuses to start when a bootstrap password fails the policy; outside production the account is skipped with an error in the log).
- A password change must supply the current password and a different new one.

**Login**

- `POST /api/auth/login` answers every failure - unknown e-mail, wrong password, deactivated account - with the same HTTP 401 and the same text, "Incorrect e-mail or password.", so the response does not reveal whether an account exists.
- `verify_password` always performs one bcrypt comparison, using a dummy hash when the e-mail is unknown, so the response time does not reveal it either.
- Rate limiting (`core/rate_limit.SlidingWindowLimiter`):
  - failed attempts per (client address, e-mail): `LOGIN_RATE_LIMIT_ATTEMPTS` (5) within `LOGIN_RATE_LIMIT_WINDOW_SECONDS` (300);
  - all login requests per client address: 30 per 60 seconds;
  - failed attempts per e-mail, whatever the client address: four times `LOGIN_RATE_LIMIT_ATTEMPTS` (20 by default) within `LOGIN_RATE_LIMIT_WINDOW_SECONDS`. The client address is taken from a forwarding header and can be forged when the API is reachable without a trusted proxy in front of it, so the per-address limits alone would not stop password guessing against one account. Reaching this limit locks sign-in for that e-mail from every address until the window passes;
  - exceeding any of them returns HTTP 429 with a `Retry-After` header. A lock-out is audited once per window (`AUTH_LOGIN_RATE_LIMITED`) so that a flood cannot bloat the audit trail. A successful login clears the failure counter for that (client address, e-mail) key; the per-e-mail counter is not cleared and empties as the window passes.
- Successful and failed logins are audited (`AUTH_LOGIN_SUCCESS`, `AUTH_LOGIN_FAILED`).

**Tokens**

- A login returns a JWT signed with HS256 and `SECRET_KEY` (`create_access_token`). Claims:

  | Claim | Content |
  |---|---|
  | `sub` | User id |
  | `role` | Role at issue time (informational; authorisation always uses the role stored in the database) |
  | `ver` | The user's `token_version` at issue time |
  | `jti` | Random token id (UUID) |
  | `iat`, `exp` | Issue and expiry time; lifetime `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60) |

- Every request is checked by `get_token_claims` and `get_current_user`: valid signature and expiry, `sub` and `jti` present, the user exists and is active, `ver` equals the user's current `token_version`, and `jti` is not in `revoked_tokens`.
- **Logout** (`revoke_token`) stores the token's `jti` in `revoked_tokens` until its natural expiry, so a copied token cannot be used after the user signed out. Expired rows are removed opportunistically on each logout.
- **Invalidation of all sessions.** `token_version` is incremented when a user changes their password, when an Administrator resets it, when the role changes and when the account is deactivated or reactivated. Every token issued before then fails the `ver` check.
- The browser keeps the token in `sessionStorage` and sends it in the `Authorization` header. There is no refresh token: after expiry the user signs in again.

**Accounts**

- There is no public registration. Accounts are created by an Administrator (`POST /api/users`) or by the bootstrap configuration on first start (`services/bootstrap.py`), which never overwrites an existing account.
- The last active Administrator cannot be demoted or deactivated, and an Administrator cannot deactivate their own account (`api/users.py`).

## Role-based access control

Two roles exist: `admin` (Administrator) and `operator` (Operator). The permission matrix in `backend/app/core/permissions.py` is the single source of truth; the complete table is in the [API reference](api.md#permission-matrix).

- Every privileged endpoint declares `Depends(require_permission("..."))`. An unknown permission name raises an error when the module is imported, so a typo cannot silently create an unprotected route.
- A refusal returns HTTP 403 and writes an `ACCESS_DENIED` audit event with the role, the method and the path.
- The user interface hides or disables controls using the permission list returned at login, but this is a convenience only; the backend check is what counts.

Rules that depend on the object, enforced in the services:

| Rule | Where |
|---|---|
| Closing and reopening an incident requires `incidents:close` even though the transition endpoint itself needs only `incidents:update`; a refusal is audited as `INCIDENT_STATUS_CHANGE_DENIED` | `incident_service.transition_incident` |
| Overriding the monitoring check when resolving an incident requires `incidents:close` | `incident_service.transition_incident` |
| An Operator may cancel only their own remediation request | `remediation_service.cancel` |
| An Administrator may not approve their own request unless `remediation.allow_self_approval` is enabled; a refusal is audited as `REMEDIATION_APPROVAL_DENIED` | `remediation_service.approve` |
| Operators see only operational audit events and events in which they are the actor | `audit_service._apply_visibility` |

## Secrets handling and start-up checks

- **No secret has a default in source code.** `backend/app/core/config.py` reads everything from the environment. With `PROCESS_ROLE=api` the process refuses to start unless `SECRET_KEY` has at least 32 characters and `ALERT_WEBHOOK_TOKEN` at least 16; `DATABASE_URL` is always required.
- **Production checks.** With `ENVIRONMENT=production` the process refuses to start if `SECRET_KEY`, `ALERT_WEBHOOK_TOKEN`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_OPERATOR_PASSWORD`, `DEMO_APP_RECOVERY_TOKEN`, `DEMO_APP_CONTROL_TOKEN` or the database password inside `DATABASE_URL` contains a placeholder marker (`change-me`, `changeme`, `replace-me`, `example`, `dev-only`), or if `DATABASE_URL` points at SQLite. The API also refuses to start in production if `BOOTSTRAP_ADMIN_PASSWORD` or `BOOTSTRAP_OPERATOR_PASSWORD` is set and does not meet the password policy. In development the same placeholders produce a warning in the log and a flag in `GET /api/settings`.
- **Least distribution.** Compose passes each secret only to the services that need it:

  | Secret | backend | worker | test-app | alertmanager |
  |---|---|---|---|---|
  | `SECRET_KEY` | yes | no | no | no |
  | `ALERT_WEBHOOK_TOKEN` | yes | no | no | as a secret file |
  | `GEMINI_API_KEY` | yes | no | no | no |
  | Bootstrap passwords | yes | no | no | no |
  | `DEMO_APP_CONTROL_TOKEN` | yes | no | yes | no |
  | `DEMO_APP_RECOVERY_TOKEN` | no | yes | yes | no |
  | Database password | yes | yes | no | no |

- **Alertmanager's token** is delivered as a Compose secret mounted at `/run/secrets/alert_webhook_token` and referenced by `credentials_file`, so it is not written into `monitoring/alertmanager.yml`.
- **Not in images or Git.** `.dockerignore` excludes `.env` from build contexts and `.gitignore` excludes it from the repository. `.env.example` contains only public placeholders; `scripts/generate_env.py` writes a `.env` with random secrets.
- **Never returned by the API.** `GET /api/settings` reports only whether the Gemini key is configured and whether placeholder secrets are in use.
- **Never sent to the browser or the model.** The Gemini key is used only by `assistant/gemini_provider.py`; it is not placed in prompts, and the frontend contains no provider code.

## Network exposure and reverse-proxy headers

| Service | Local stack (`compose.yaml`) | Production overlay (`compose.prod.yaml`) |
|---|---|---|
| `web` | Host port 8080 to container port 80 (HTTP) | Host ports 80 and 443 (TCP) and 443 (UDP); Caddy obtains the certificate for `VIGILOPS_DOMAIN` |
| `backend` | 127.0.0.1:8000 only (API docs for development) | Not published |
| `prometheus` | 127.0.0.1:9090 only | Not published |
| `alertmanager` | 127.0.0.1:9093 only | Not published |
| `postgres`, `worker`, `test-app` | Not published | Not published |

Caddy (`reverse-proxy/Caddyfile`) forwards only `/api/*` to the backend. The backend's `/metrics`, `/health/live`, `/health/ready`, `/docs` and `/openapi.json` are therefore not reachable through the proxy, and neither are Prometheus, Alertmanager, PostgreSQL or the worker. The interactive API documentation is also switched off in production (`ENABLE_API_DOCS` defaults to off there). Caddy's admin API is disabled (`admin off`). `/api/health` and `/api/version` are intentionally reachable without authentication.

Caddy also routes `/orbitcrate/*` to the demonstration application, because its storefront (OrbitCrate) is meant to be visited. Only three kinds of path are routed after the prefix is removed: `/`, `/static/*` and `/api/*` (the store's own API: catalogue, price estimate and the visitor's orders). Everything else under `/orbitcrate/` answers HTTP 404 at the proxy, including the application's token-protected control endpoints (`/internal/*`), its `/metrics` and its `/health/*`. A request body may be at most 4 KB. The store holds no accounts and no personal data: a visitor is identified by a random value kept in that browser, orders exist in memory only, and the number of visitors, orders per visitor and orders per minute is bounded.

Where the API port itself is the public port and no reverse proxy withholds those paths (the single-container image of the [Render and Vercel deployment](deployment-render-vercel.md)), the backend setting `INTERNAL_ENDPOINTS_LOCAL_ONLY=true` makes `/metrics` and `/health/ready` answer HTTP 404 unless the caller is on the loopback interface and the request carries no `X-Forwarded-For` or `Forwarded` header. It is `false` by default and is not used by the Compose stack. `/health/live` stays reachable; in production mode it returns only `{"status": "alive"}`. In the same image the storefront is passed through by the API itself (`SERVE_DEMO_APP=true`, `backend/app/api/store.py`) with the same restriction to the page, `static/*` and `api/*`, a fixed list of forwarded headers (`Accept`, `Content-Type`, `X-Session-Id`), a 4096-byte body limit and 300 requests per minute per client address.

Response headers set by Caddy on every response:

| Header | Value |
|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |
| `Server` | removed |

What the policy means: scripts, fonts and network connections are limited to the application's own origin, so an injected script from another host does not load and a script cannot send data to another host with `fetch`; the page cannot be framed; inline styles are allowed because the charting and styling libraries use them.

On the [Render and Vercel deployment](deployment-render-vercel.md) the same headers are set by `frontend/vercel.json`, with one difference: `connect-src` also names the address of the Render service. The pages send one request there, without credentials and without reading the answer, because a sleeping service is started only by a request to its own address. A script on the page can therefore also send requests to that one address, which is the project's own API.

The backend adds `Cache-Control: no-store` to every `/api` response, `X-Content-Type-Options: nosniff`, and `X-Request-ID`. The backend generates that id itself for every request and ignores any `X-Request-ID` a client sends.

CORS is disabled unless `CORS_ORIGINS` lists explicit origins (needed only when the frontend runs on the Vite development server); credentials are never allowed in CORS mode because the token is not a cookie.

## Input validation

| Input | Validation | Where |
|---|---|---|
| All JSON bodies | Pydantic models with types, length limits, patterns and literals; validation errors return HTTP 422 with a field list and no stack trace | `schemas/schemas.py`, `main.py` |
| Pagination | `page` 1..100000, `page_size` 1..100, `sort` at most 40 characters and mapped through a fixed dictionary of sortable columns, `order` `asc` or `desc`, `q` at most 120 characters | `api/deps.py`, services |
| E-mail on user creation | Pattern and maximum length; normalised to lower case | `schemas.UserCreate` |
| Incident transition | Status literal; note at most 2000 characters; transition table | `schemas.IncidentTransition`, `incident_service` |
| Alertmanager webhook | 1..100 alerts; status `firing` or `resolved`; `labels.alertname` required; at most 60 labels; fingerprint 8..64 hexadecimal characters; unknown fields ignored. The engine then keeps at most 40 labels and truncates keys to 120 and values to 500 characters | `schemas.AlertmanagerWebhook`, `incident_service._clean_map` |
| Monitoring queries | Metric by key from `METRIC_CATALOG`; job must match `^[A-Za-z0-9_\-]{1,80}$` and be a registered monitored resource; range from `RANGE_PRESETS`. PromQL is never accepted from a client | `monitoring_service.timeseries`, `validate_job` |
| Alert name used in a PromQL selector | Must match `^[A-Za-z0-9_]{1,120}$` before it is interpolated | `PrometheusClient.alert_is_firing` |
| Scan target | Plain file name matching `^[A-Za-z0-9][A-Za-z0-9._\-]{0,120}\.ya?ml$`, then path confinement | `scan_service.resolve_target` |
| Remediation request | `source_type` literal, positive `source_id`, action code pattern `^[A-Z]+-\d{3}$` and membership in the catalog, justification 10..2000 characters | `schemas.RemediationCreate`, `remediation_service.create_request` |
| Runtime settings | Only declared keys; exact type (a boolean is not accepted as an integer); bounds | `settings_service._coerce` |
| Chat | Message 1..2000 characters and not blank; at most 20 history turns of at most 4000 characters; the service then uses at most 1000 characters of the message and the last 6 turns cut to 600 characters each | `schemas.ChatRequest`, `assistant/service.py` |
| `X-Request-ID` | Never adopted from the client; the backend always mints a new UUID, because the request id becomes the default audit correlation id | `core/request_context.py` |

Database access goes through the SQLAlchemy ORM with bound parameters; no SQL is built from request text. Free-text search uses `LIKE` with the term as a bound parameter.

## Scanner safety

The scanner reads files that may have been written by someone else, so it treats them as untrusted input (`backend/app/security_scanner/engine.py`, `backend/app/services/scan_service.py`).

| Risk | Control |
|---|---|
| Code execution through YAML tags | `yaml.safe_load` only: no arbitrary object construction |
| Alias expansion ("billion laughs") memory attack | The token stream is inspected first (`yaml.scan`) and any anchor or alias token rejects the document |
| Very large input | The file size is checked before reading (`SCAN_MAX_FILE_BYTES`, default 262144 bytes) and a document may contain at most 500 resources |
| Wrong encoding or malformed syntax | Non-UTF-8 content and YAML errors are reported as a scan input error with the line number; the file's existing findings are left untouched |
| Unexpected structure | The top level must be a mapping with `schema_version: vigilops/v1` and a `resources` list; every resource must be a mapping with a supported `type` and a non-empty `name` of at most 120 characters; duplicate (type, name) pairs are rejected |
| Directory traversal, absolute paths | The target must match the plain-file-name pattern, which cannot contain a path separator |
| Symbolic links pointing outside the workspace | The candidate path is fully resolved and its parent directory must equal the workspace directory (`resolve_target`); `list_targets` applies the same check |
| The API changing what it scans | The backend container mounts the workspace read-only |
| Non-determinism | Rules are pure functions of the document; violations are sorted, so the same file always produces the same findings |

### Input schema `vigilops/v1`

The rule catalog `security-rules/policies.yaml` refers to this description.

```yaml
schema_version: vigilops/v1        # required, exact value
resources:                         # required list, at most 500 entries
  - type: storage_bucket           # one of: storage_bucket, disk_volume, database,
    name: example-bucket           #         iam_policy, security_group, container
    public_access: false           # SEC-001: true is a violation
    acl: private                   # SEC-001: public-read or public-read-write is a violation
    encryption:                    # SEC-002 (storage_bucket, disk_volume, database)
      enabled: true                #   missing block, enabled not true, or
      algorithm: AES-256           #   algorithm empty or NONE is a violation
  - type: iam_policy
    name: example-policy
    statements:                    # SEC-003: an Allow statement with action "*" or "service:*",
      - effect: Allow              #          or resource "*", is a violation
        actions: ["s3:GetObject"]
        resources: ["arn:aws:s3:::example-bucket/*"]
  - type: security_group
    name: example-sg
    ingress:                       # SEC-004: cidr 0.0.0.0/0 or ::/0 together with a sensitive port
      - protocol: tcp              #          (22, 23, 3389, 1433, 3306, 5432, 6379, 9200, 27017),
        port: 443                  #          given as port, port_range "low-high" or protocol all
        cidr: 0.0.0.0/0
  - type: container
    name: example-container
    privileged: false              # SEC-005: privileged true, or
    security_context:              #          security_context.privileged true, is a violation
      privileged: false
```

Keys that no rule reads are ignored. The files describe sample resources; the scanner does not contact a cloud provider.

## Remediation safety model

Remediation is the most sensitive function of the platform. Its design answers the question "what is the worst a single mistake or a single compromised component can do?"

| Layer | Control | Where |
|---|---|---|
| Allowlist | A request can name only an action code present in `ACTIONS` (ACTION-001, ACTION-002). The request schema has no field for a command, a script or a path | `services/remediation_catalog.py`, `schemas.RemediationCreate` |
| Applicability | ACTION-001 only for an active incident on the demo application resource; ACTION-002 only for an OPEN SEC-001 finding in a file named in `REMEDIATION_WRITABLE_TARGETS` | `action_for_incident`, `action_for_finding` |
| Justification | At least 10 characters, stored and audited | `remediation_service.create_request` |
| One request at a time | Partial unique indexes allow one in-flight request per incident or finding | `models.RemediationRequest` |
| Approval | Only `remediation:approve` (Administrator) can approve or reject; rejection needs a reason | `api/remediation.py`, `remediation_service` |
| Self-approval rule | The requester cannot approve their own request unless the runtime setting `remediation.allow_self_approval` is enabled (default off); attempts are audited as DENIED | `remediation_service.approve` |
| Separate dispatch | Approval does not start anything. A second, explicit `execute` moves APPROVED to QUEUED | `remediation_service.execute` |
| Process isolation | The API never performs the action. The worker has no inbound port, a read-only root filesystem, no Linux capabilities, the only write access to the workspace and the recovery token | `compose.yaml`, `workers/remediation_worker.py` |
| State validation at claim time | `claim_next` takes only rows in QUEUED, locks the row (`FOR UPDATE SKIP LOCKED`) so two workers cannot run the same request, and refuses a row that has no recorded approver (`REMEDIATION_EXECUTION_REFUSED`, outcome DENIED) | `workers/remediation_worker.py` |
| Trusted parameters | Handler parameters are built from the finding or incident row; nothing typed by a user or produced by the assistant reaches a handler | `_build_params`, `workers/actions.py` |
| Narrow handlers | ACTION-001 calls one HTTP endpoint with the recovery token. ACTION-002 changes two keys of one resource in one allowlisted file, through the same path confinement as the scanner, and writes atomically (temporary file, `fsync`, rename; the file gets mode 0640: owner read/write, group read). No shell, no Docker socket | `workers/actions.py` |
| Timeouts | Action timeout `ACTION_TIMEOUT_SECONDS` (30 s); verification budget `VERIFY_TIMEOUT_SECONDS` (150 s); HTTP timeouts on every call | `_run_with_timeout`, `workers/verification.py` |
| Retries | Inside ACTION-001 the idempotent recovery call is attempted up to three times with back-off, and not at all after an authorisation failure. A FAILED request can be retried by an Administrator while `attempt_count < max_attempts` (3) | `actions.recover_demo_application`, `remediation_service.retry` |
| Verification before success | The handler reporting "done" is never enough. ACTION-001 needs three consecutive successful readiness probes, a healthy Prometheus scrape newer than the action, and the alert no longer firing. ACTION-002 needs a new persisted scan in which the rule no longer matches the resource and which itself set the finding to RESOLVED | `workers/verification.py` |
| Honest failure | A failed or unverifiable action ends as FAILED with the reason; the finding returns to OPEN and the incident stays active | `_finish_failed` |
| Interrupted work | Requests left RUNNING or VERIFYING by a worker that stopped are marked FAILED with "outcome unknown" at the next start | `recover_interrupted` |
| Evidence | Every execution stores before and after values, a diff or the call log, and each verification check with its time | `remediation_executions` |
| Assistant excluded | VigilAI has no tool that changes state, refuses instructions to act, and its output cannot reach the worker | `assistant/*.py` |

## Audit integrity

Implemented in `backend/app/services/audit_service.py` and the initial migration.

- **Same-transaction writes.** `record_audit` adds the event to the caller's session and does not commit; the caller commits the state change and its audit event together. A change cannot be stored without its audit record, and an audit record cannot describe a change that was rolled back.
- **Denials are recorded too.** Events that describe a refusal (`ACCESS_DENIED`, `AUTH_LOGIN_FAILED`, `REMEDIATION_APPROVAL_DENIED`, `INCIDENT_STATUS_CHANGE_DENIED`, `ASSISTANT_REQUEST_BLOCKED`) are committed on their own before the error or refusal is returned.
- **Sanitised metadata.** `sanitize_metadata` replaces the value of any key whose name looks sensitive (`password`, `passwd`, `passphrase`, `secret`, `token`, `api_key`, `authorization`, `credential`) with `[REDACTED]`, truncates strings to 600 characters, limits collections to 40 items and nesting to 5 levels.
- **No update or delete path.** The service has no function that edits or removes an event, and the API has no such endpoint.
- **Append-only at database level.** On PostgreSQL the trigger `trg_audit_events_immutable` raises an exception for any UPDATE or DELETE on `audit_events`. The restore script documents the one legitimate exception: a full restore disables user triggers for its own session.
- **Identification.** Each event has a UUID `event_id`, the actor (user id and e-mail, or a service identity such as `alertmanager`, `system` or the worker id), the outcome (SUCCESS, FAILURE, DENIED), the client address and a correlation id. All events of one remediation request share the request's `correlation_id`; other events carry the HTTP request id.
- **Visibility scoping.** Administrators (`audit:view_all`) see everything. For Operators `_apply_visibility` restricts every query, including the single-event lookup, to events whose action starts with `INCIDENT_`, `ALERT_`, `SECURITY_SCAN_`, `FINDING_`, `REMEDIATION_` or `DEMO_`, plus events in which the Operator is the recorded actor. Sign-ins of other users, user administration, settings changes and access denials of other users are therefore not visible to Operators. The same function is used by the dashboard and by VigilAI.

## VigilAI safeguards

VigilAI is read-only by construction: the package `backend/app/assistant` contains no function that changes platform state. The nine required safeguards map to code as follows. The pipeline order is shown in the [VigilAI architecture diagram](diagrams/vigilai-architecture.md).

| # | Safeguard | Implementation | What it does |
|---|---|---|---|
| 1 | Backend topic and scope validation | `assistant/scope.py`: `classify`, with `relevance`, `is_action_instruction` and the patterns `_OFF_TOPIC_TASK`, `_SECRET_REQUEST`, `_INJECTION`; called from `assistant/service.py: chat` before any retrieval, live-data access or model call | Classifies the message as in scope, out of scope, privileged action, secret request or prompt injection. Only "in scope" continues; the others receive a fixed reply. A second gate in `chat` refuses when neither documentation nor live data matched. Does not depend on the model obeying its prompt |
| 2 | Restricted knowledge retrieval | `assistant/retrieval.py`: `KnowledgeBase.search`, `chunk_markdown`, `get_knowledge_base` | The only documentation the assistant can quote is the Markdown in `knowledge_base/` (`KNOWLEDGE_BASE_DIR`). BM25 ranking with a minimum score and a relative cut-off returns at most four sections; no web access, no vector store, no user-supplied documents |
| 3 | Authorised live-data functions | `assistant/context_tools.py`: `get_monitoring_summary`, `get_authorized_open_incidents`, `get_authorized_incident_details`, `get_authorized_security_findings`, `get_latest_security_scan`, `get_authorized_remediation_requests`, `get_authorized_remediation_status`, `get_recent_audit_events`; selected by `select_tools`, executed by `run_tools` | The assistant has no database credentials and builds no SQL. It can see only what these eight fixed read-only functions return. Which ones run is decided by deterministic keyword routing (at most four per question); the model neither chooses nor parameterises them |
| 4 | Role-aware access checks | `require_permission("assistant:use")` in `api/assistant.py`; `has_permission(user, ...)` at the top of every context tool, returning `_denied(...)`; `audit_service.list_audit_events(db, user, ...)` inside `get_recent_audit_events` | Each tool checks the current user's permission before reading and goes through the same service layer as the REST API, so the Operator's restricted audit view applies identically. A denied tool contributes only the statement that the role may not view the information |
| 5 | Context minimisation | `context_tools.py`: `_clip`, `MAX_ITEMS`, `_incident_brief`, `_finding_brief`, `_remediation_brief`; `prompts.py: build_prompt` (`max_context_chars`); `service.py: _clean_history` | Tools return short summaries: at most 10 incidents or requests, 15 findings, the last 8 timeline or audit entries, text fields clipped. The prompt has a character budget (half documentation, 40 percent live data, 10 percent conversation). History is cut to the last `AI_MAX_HISTORY_TURNS` turns of 600 characters. No secret, password hash or raw configuration file is ever part of the context |
| 6 | Prompt-injection resistance | `scope.py: _INJECTION` (refusal plus `ASSISTANT_REQUEST_BLOCKED` audit event); `prompts.py: SYSTEM_INSTRUCTION` rule 4, `_escape`, `build_prompt`; `gemini_provider.py: _call` (system instruction passed separately); structural: `select_tools` | Instruction-override phrases are refused before the model is called. Documentation, live data, history and the question are wrapped in delimiter tags and declared to be data, with `<` and `>` replaced so content cannot close or open a tag. Because tools are chosen by code and nothing the model writes is executed, a successful injection can at most change the wording of an answer |
| 7 | Response validation | `assistant/sanitize.py: validate_reply` (`SENTINEL_OUT_OF_SCOPE`, `_ACTION_CLAIM`, `_NEGATED`); empty answers handled in `service.py: chat` | If the model signals out of scope, the fixed out-of-scope reply is returned. If a sentence claims that the assistant performed an action ("I have approved ..."), the whole reply is replaced by the read-only explanation. An empty answer triggers the documentation fallback |
| 8 | Output sanitisation | `sanitize.py: validate_reply` (`_HTML_TAG`, `_SCRIPTY`, `MAX_REPLY_CHARS`), `strip_secrets` (configured secret values plus `core/logging.redact` patterns); `frontend/src/features/vigilai/SafeText.jsx` | HTML tags and script-like fragments are removed, anything equal to a configured secret or shaped like a key or token is replaced by `[REDACTED]`, and the reply is limited to 4000 characters. The fallback text passes through `strip_secrets` as well. The browser renders replies as React text nodes, never as HTML |
| 9 | Request rate limiting | `service.py: _user_limiter` (`SlidingWindowLimiter(AI_RATE_LIMIT_PER_MINUTE, 60)` per user), raising `AssistantRateLimited`, mapped to HTTP 429 with `Retry-After` in `api/assistant.py`; `service.py: _consume_daily_budget` (`AI_DAILY_REQUEST_LIMIT`); limits in `schemas.ChatRequest` | A user can send `AI_RATE_LIMIT_PER_MINUTE` (default 10) messages per minute. A server-wide daily cap (default 400 provider calls) protects the provider quota; when it is used up the assistant answers in fallback mode. Provider calls have a timeout (`AI_TIMEOUT_SECONDS`), one retry for transient server errors and none for quota errors |

Additional properties:

- **Refusals are explicit.** Instructions to act receive a reply that explains the read-only nature and the workflow a person must follow (`prompts.READ_ONLY_REPLY`). Requests for credentials receive `SECRET_REPLY`. Both, and injection attempts, are audited with the category and reason but without the message text.
- **Privacy of usage logs.** The assistant logs the user id, mode, model, token counts, tool names and timings, but not the question or the answer (`service.py`).
- **Graceful degradation.** Without a key, on error, on timeout or on quota exhaustion, the documentation fallback returns the retrieved sections and live data with a notice (`providers.FALLBACK_NOTICES`).
- **Administrator switch.** The runtime setting `assistant.enabled` turns the assistant off for everyone.

Verification status: safeguards 1 to 9 and the fallback path are exercised by `backend/tests/unit/test_assistant_guards.py` and `backend/tests/integration/test_assistant.py` with a stub provider. The live call to Google Gemini was verified on 2026-11-23 with a real API key and the default model `gemini-3.5-flash-lite` by `scripts/verify_gemini_live.py` (19 of 19 checks passed; evidence in [`evidence/gemini-live.json`](evidence/gemini-live.json)). In that run 9 of 9 platform questions were answered in `ai` mode and each passed a grounding check against the documentation or live data. Six refusal messages (three unrelated questions, an instruction to approve remediation, a request for the API key and a prompt injection) were refused by the backend without a call to the model: the provider-call counter was 10 before and 10 after. An instruction planted in the conversation history was not obeyed by the model, and no configured secret appeared in any reply. On the running stack, a model name that does not exist (HTTP 404 from the provider) and an invalid API key (HTTP 400, reason `API_KEY_INVALID`) each produced the documentation fallback with the matching notice while the rest of the platform kept working. Real quota exhaustion (HTTP 429 from the provider) and provider timeouts were not observed; those paths are covered only by tests with a stubbed SDK client. See the [verification report](verification-report.md).

## Logging and redaction

Implemented in `backend/app/core/logging.py`.

- Logs are single-line JSON on standard output with timestamp, level, logger, message, request id and structured fields.
- A redaction step is applied to the message, to every string field and to exception text. It masks Google API keys (both the `AIza...` and the newer `AQ....` format), JWTs, `Bearer` credentials, and `password=`, `secret=`, `token=` or `api_key=` style assignments.
- The access log records the method, the path without the query string, the status, the duration and the client address. The `/health/*` probes and `/metrics` are not logged.
- The alert webhook logs a rejected call without the presented token.
- Unhandled exceptions are logged with a stack trace on the server and answered with "Internal server error." and the request id.
- Prometheus labels use the route template, never the raw URL, so identifiers do not leak into metrics.

## Demo-control gating

The demonstration controls can break the demo application on purpose, so they are gated several times.

| Gate | Where |
|---|---|
| `settings.demo_controls_active` is true only when `DEMO_CONTROLS_ENABLED=true` **and** the environment is not production. In production mode it is true only if the explicit opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION=true` is set as well (default `false`). The opt-in exists only for a hosted demonstration instance whose only workload is the bundled demo application; the controls stay Administrator-only and audited | `core/config.py` |
| The production overlay forces `DEMO_CONTROLS_ENABLED=false` on the backend, the worker and the demo application | `compose.prod.yaml` |
| `POST /api/demo/faults` and `POST /api/demo/reset-config` require `demo:control` (Administrator) and return HTTP 404 when the controls are inactive | `api/demo.py`, `demo_service.ensure_enabled` |
| The demo application's `/internal/fault` returns 404 unless its own `DEMO_CONTROLS_ENABLED` is true, and requires the control token (constant-time comparison) | `test-app/app.py` |
| The worker refuses demo tasks when the controls are inactive and seeds the workspace only in demo mode | `workers/remediation_worker.py` |
| Faults are bounded: the CPU and memory faults end after 10 minutes, the memory block has a fixed size, and the container has memory and CPU limits. A deployment can switch individual fault modes off with `DEMO_DISABLED_FAULTS`; they are then not offered and are refused with HTTP 422 | `test-app/app.py`, `compose.yaml`, `demo_service.py` |
| The demo application has no published port | `compose.yaml` |
| Transparency: every use is audited (`DEMO_*`), incidents opened during a fault are flagged `is_simulated`, and the interface shows a demo-mode indicator | `demo_service.py`, `incident_service._handle_firing` |

The reset of the sample configuration is carried out by the worker through the `demo_tasks` table, because the API cannot write to the workspace.

The recovery endpoint `/internal/recover` is not a demo control: it is the mechanism of ACTION-001 and stays available whenever the recovery token is configured.

## Container hardening

| Service | User | Root filesystem | Capabilities | Other |
|---|---|---|---|---|
| `worker` | uid 10001 | read-only, `tmpfs` at `/tmp` | all dropped | `no-new-privileges`, no ports |
| `test-app` | uid 10001 | read-only, `tmpfs` at `/tmp` | all dropped | `no-new-privileges`, 512 MB memory, 1 CPU |
| `backend` | uid 10001 | read-only, `tmpfs` at `/tmp` | all dropped | `no-new-privileges`, scan workspace mounted read-only |
| `web` | image default | writable | all dropped except `NET_BIND_SERVICE` | `no-new-privileges` |
| `workspace-init` | root | writable | default | `network_mode: none`, runs once and exits |
| `prometheus`, `alertmanager` | image defaults | writable | default | configuration files bind-mounted read-only |
| `postgres` | image defaults | writable | default | - |

## Residual risks and limitations

These are known weaknesses of the current build. None of them is hidden by the interface, and each has a stated reason or a suggested improvement.

**Authentication and sessions**

- **No multi-factor authentication and no single sign-on.** A password is the only factor. There is no self-service password reset; an Administrator resets passwords.
- **Token in `sessionStorage`.** Any script that runs in the application's origin can read the token. The mitigations are the Content-Security-Policy (`script-src 'self'`), React's escaping, never rendering HTML from data, the 60-minute lifetime and server-side revocation. An `HttpOnly` cookie would remove this exposure but would add a cross-site request forgery surface; the trade-off was decided in favour of the header.
- **Symmetric signing key.** HS256 uses one shared secret; rotating `SECRET_KEY` signs out everyone. There are no refresh tokens.
- **Password policy is basic.** Length and character classes only; no check against known-breached passwords and no password history.

**Rate limiting**

- **In-process limiters.** Login and assistant limits live in the memory of the single backend process. They reset on restart and would not be shared if the backend were scaled to several processes; the image therefore starts Uvicorn with `--workers 1`. The assistant's daily budget also resets on restart.
- **Login limiter keys.** Failures are counted per (address, e-mail) and per e-mail regardless of the address, with a coarse limit of 30 logins per minute per address. Guessing a few passwords against many accounts from many addresses is slowed but not blocked. The per-e-mail limit is a temporary account-wide lock-out: someone who knows an account's e-mail can lock that account out of sign-in by failing 20 times (four times `LOGIN_RATE_LIMIT_ATTEMPTS`), until the window passes.
- **Only login and chat are rate limited.** Other endpoints rely on authentication and on `page_size` limits.

**Trust in forwarded headers**

- **Trusted proxy addresses default to any peer.** Uvicorn is started with `--forwarded-allow-ips` set from `FORWARDED_ALLOW_IPS`, which defaults to `*` so that the client address behind Caddy is recorded correctly without knowing the proxy's container address. Through Caddy this works as intended, because Caddy sets `X-Forwarded-For` itself. A client that can reach the backend port directly (the development port on 127.0.0.1, or another container on the internal network) can spoof its address, which defeats the per-address parts of the login limit (the per-e-mail limit does not depend on the address and still applies) and falsifies `source_ip` in audit events. Setting `FORWARDED_ALLOW_IPS` to the proxy's address closes this. A caller-supplied `X-Request-ID` is never adopted: the backend always mints its own request id, so a client cannot choose an audit correlation id.

**Database**

- **One database role for the API and the worker, and it is the owner.** Both processes connect as `POSTGRES_USER`, the role created by the PostgreSQL image; it is that instance's superuser and, because the backend runs the migrations with it, the owner of every table. A compromised API process could therefore insert a QUEUED request with an approver directly into the table, or remove the audit trigger. The worker's approval check and the trigger protect against application bugs and against misuse through the API, not against an attacker holding the database password. Separate roles with table-level grants (the API without UPDATE on audit rows, the worker limited to its queue) would be the next step.
- **Audit trail is not tamper-evident.** There is no hash chain and no export to an external log store, so a database administrator can alter history without leaving a trace in the application.
- **Audit sanitisation is key based.** A secret pasted into a free-text field such as a justification is stored as written (up to 600 characters); only values under keys whose names look sensitive are masked.

**Network**

- **No TLS inside the Docker network.** Caddy to backend, backend to PostgreSQL, Alertmanager to the webhook (bearer token) and worker to demo application (recovery token) are plain HTTP or unencrypted PostgreSQL protocol on the private bridge network.
- **Flat internal network.** All services share one network. The worker has no inbound port, but it can reach every other service, and outbound internet access is not restricted for any container.
- **Unauthenticated internal services.** Prometheus, Alertmanager, the backend's `/metrics` and `/health/*`, and the demo application's `/metrics`, `/health/*` and (token-protected) `/internal/*` endpoints rely on not being published; its storefront and store API are public by design and have no authentication (in the single-container image, where the API port is the public port, `/metrics` and `/health/ready` rely on `INTERNAL_ENDPOINTS_LOCAL_ONLY` instead). A container on the internal network could post a fabricated alert to Alertmanager, which would reach the webhook with the valid token.
- **Local stack is plain HTTP.** `compose.yaml` publishes the web port without TLS. It is bound to 127.0.0.1 by default; setting `VIGILOPS_BIND_ADDRESS=0.0.0.0` exposes it to the local network, where credentials and tokens then travel in clear text. Use the production overlay for anything beyond a trusted network.
- **HSTS without preload.** The Caddyfile sets `Strict-Transport-Security: max-age=31536000` (effective over HTTPS only); it does not include subdomains and the domain is not preloaded, so a visitor's very first request can still be made over HTTP.
- **Public status endpoints.** `/api/health` and `/api/version` are reachable without authentication. In development they include the version, environment name and uptime; in production mode they return only a status and the project title.

**Secrets**

- **Environment variables.** Except for Alertmanager's token, secrets are passed as environment variables and are visible to anyone who can inspect the containers. Bootstrap passwords remain in the backend's environment after first use.
- **Start-up checks are limited.** The production check looks for placeholder markers in the signing key, webhook token, bootstrap passwords, both demo-application tokens and the password inside `DATABASE_URL`. It measures length and known placeholder text, not randomness, so a weak but unusual secret is accepted. Only the bootstrap passwords are additionally checked against the password policy.

**Remediation**

- **Timeout does not kill.** The action timeout stops waiting for a handler thread but cannot terminate it.
- **Self-approval is a runtime setting.** An Administrator can enable `remediation.allow_self_approval`; the change is audited, but one Administrator acting alone can then request, approve and dispatch.
- **Approve and dispatch may be the same person.** Separation of duties is enforced between requester and approver only.

**VigilAI**

- **Heuristic classification.** Scope validation and tool routing are regular expressions and keyword scores. They can refuse a legitimate question or admit an unrelated one that happens to use platform vocabulary; the model's own instruction and the response validation are the second line.
- **History is browser supplied.** Earlier turns, including "assistant" turns, come from the client. They are bounded, normalised and escaped, and turns that match the injection patterns are dropped; a planted instruction worded so that it passes those patterns still reaches the model as data, where only the system instruction stands against it. History is never used to decide whether a question is in scope.
- **Data leaves the deployment when Gemini is configured.** The question, the user's role, the retrieved documentation and the live-data summaries (which include incident titles, resource names and the e-mail addresses of requesters, approvers and audit actors) are sent to Google. Without a key nothing is sent.
- **Live generation was verified on a small scale only.** The real provider was exercised with one model and a small question set. The answers were checked with keyword grounding checks and by reading the replies; there was no systematic human evaluation of answer quality. Real quota exhaustion (HTTP 429 from the provider) was never observed; that path and provider timeouts are covered only by tests with a stubbed SDK client.

**Containers and supply chain**

- **Uneven hardening.** The backend, the worker and the demo application run as a non-root user with a read-only root filesystem, without capabilities and with `no-new-privileges`. The web container (Caddy) drops all capabilities except `NET_BIND_SERVICE` and sets `no-new-privileges`, but keeps its image's default user and a writable root filesystem. PostgreSQL, Prometheus and Alertmanager run with their image defaults, and the one-shot `workspace-init` container runs as root (without network access).
- **Unpinned dependencies.** `backend/requirements.txt` specifies version ranges, and base images are referenced by tag rather than digest, so builds are not exactly reproducible.

**Scope**

- **Two roles, one tenant.** Every authenticated user can read every incident, finding, remediation request and the content of the files in the scan workspace (`GET /api/security/targets/{name}`); configuration files placed there should not contain secrets.
- **The scanner is not a cloud assessment.** A clean scan says only that the YAML files do not violate the five rules.
