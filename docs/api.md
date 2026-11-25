# VigilOps REST API Reference

This reference was written by reading the routers in `backend/app/api/*.py`, the application module `backend/app/main.py`, the schemas in `backend/app/schemas/schemas.py` and the permission matrix in `backend/app/core/permissions.py`. In a development stack the same contract is available interactively at `http://localhost:8000/docs` (OpenAPI), which is generated from the same code.

Related documents: [Architecture](architecture.md) · [Security](security.md) · [User guide](user-guide.md) · [Configuration](configuration.md) · [Troubleshooting](troubleshooting.md)

All example values (identifiers, e-mail addresses, timestamps, tokens, counts) are illustrative and obviously fake. They show the shape of a message, not a measured result; measured results are in the [verification report](verification-report.md). In examples, `"..."` marks content that was shortened.

## Contents

- [Conventions](#conventions)
- [Permission matrix](#permission-matrix)
- [Health, version and metrics](#health-version-and-metrics)
- [Authentication](#authentication)
- [Users](#users)
- [Dashboard and monitoring](#dashboard-and-monitoring)
- [Alertmanager webhook](#alertmanager-webhook)
- [Incidents](#incidents)
- [Security scanning](#security-scanning)
- [Remediation](#remediation)
- [Audit](#audit)
- [VigilAI assistant](#vigilai-assistant)
- [Settings](#settings)
- [Demo controls](#demo-controls)
- [Appendix A: audit actions](#appendix-a-audit-actions)
- [Appendix B: incident timeline event types](#appendix-b-incident-timeline-event-types)

## Conventions

### Base path

Every functional endpoint is under `/api`. Through the reverse proxy the base URL is `http://localhost:8080/api` locally and `https://<your-domain>/api` in production. Caddy forwards only `/api/*`; the endpoints outside `/api` (`/health/live`, `/health/ready`, `/metrics`, `/docs`, `/openapi.json`) are reachable only on the backend itself (port 8000, bound to 127.0.0.1 in the local stack and not published in production).

Requests and responses are JSON (`Content-Type: application/json`).

### Authentication header

```
Authorization: Bearer <access token from POST /api/auth/login>
```

All endpoints require this header except:

| Endpoint | Authentication |
|---|---|
| `POST /api/auth/login` | None (rate limited) |
| `GET /api/health`, `GET /api/version`, `GET /health/live`, `GET /health/ready`, `GET /metrics` | None |
| `POST /api/alerts/webhook` | The shared Alertmanager token, not a user token |

There are no cookies and no API keys for users.

### Pagination, sorting and search

List endpoints accept the following query parameters (`backend/app/api/deps.py`):

| Parameter | Type | Default | Limits | Meaning |
|---|---|---|---|---|
| `page` | integer | 1 | 1 to 100000 | Page number, starting at 1 |
| `page_size` | integer | 25 | 1 to 100 | Items per page |
| `sort` | string | endpoint specific | at most 40 characters | Field to sort by; the accepted names are listed for each endpoint. An unknown name is not an error: the endpoint falls back to a fixed column (its default, or `id`) |
| `order` | `asc` or `desc` | `desc` | - | Sort direction |
| `q` | string | none | at most 120 characters | Case-insensitive substring search over the fields named for each endpoint |

Response envelope:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 25
}
```

`total` is the number of items matching the filters, not the number on the page.

### Timestamps

All timestamps are UTC in ISO 8601 format. Endpoints with a declared response model write the offset as `Z`; endpoints that return a free-form object write `+00:00`. Both forms denote UTC.

### Errors

Errors are JSON objects with a human-readable `detail` and the `request_id` of the call. Stack traces are never returned.

```json
{
  "detail": "Incident not found.",
  "request_id": "5b0e7c1e-0000-4000-8000-000000000001"
}
```

Validation errors (HTTP 422 raised by schema validation) add a list of fields; `detail` summarises the first three:

```json
{
  "detail": "justification: String should have at least 10 characters",
  "errors": [
    { "field": "justification", "message": "String should have at least 10 characters" }
  ],
  "request_id": "5b0e7c1e-0000-4000-8000-000000000002"
}
```

`field` is the location of the value; body fields appear by name (`justification`), query and path parameters with a prefix (`query.page_size`, `path.incident_id`). Business-rule errors that also use status 422 (for example a weak password) have `detail` and `request_id` only.

### Response headers

| Header | When |
|---|---|
| `X-Request-ID` | Every response. The same id appears in the server log and, as `correlation_id`, in audit events written by the request |
| `Cache-Control: no-store` | Every `/api` response |
| `X-Content-Type-Options: nosniff` | Every response |
| `WWW-Authenticate: Bearer` | HTTP 401 |
| `Retry-After: <seconds>` | HTTP 429 |

### Status codes

| Code | Meaning in this API |
|---|---|
| 200 | Success |
| 201 | Created (user, scan, remediation request, incident comment) |
| 204 | Success without a body (logout, password change, password reset) |
| 400 | Invalid request that is not a schema error (unknown metric, invalid scan target name, wrong current password) |
| 401 | Missing, invalid, expired or revoked token; wrong credentials; invalid webhook token |
| 403 | The role lacks the required permission, or an object-level rule forbids the action |
| 404 | The object does not exist; also demo controls that are disabled |
| 409 | The operation conflicts with the current state (invalid transition, duplicate, wrong workflow status) |
| 422 | Validation error, or a business rule about the content of the request |
| 429 | Rate limited (login, assistant chat) |
| 500 | Unexpected server error: `{"detail": "Internal server error.", "request_id": "..."}` |
| 502 | The demo application could not be reached or rejected a demo-control call |
| 503 | Not ready (health), or the worker did not complete a demo reset |

### Errors common to every authenticated endpoint

These are not repeated for each endpoint below.

| Status | `detail` | Cause |
|---|---|---|
| 401 | `Authentication required` | No `Authorization: Bearer` header |
| 401 | `Session is invalid or has expired. Please sign in again.` | Bad signature, expired token, or missing claims |
| 401 | `Account is disabled or no longer exists.` | The user was deactivated |
| 401 | `Session was invalidated. Please sign in again.` | Password or role changed since the token was issued |
| 401 | `Session was signed out. Please sign in again.` | The token was revoked by logout |
| 403 | `Your role (operator) is not permitted to perform this action (remediation:approve).` | The role lacks the endpoint's permission. An `ACCESS_DENIED` audit event is written |
| 422 | see above | Schema validation failed |

## Permission matrix

Source: `PERMISSIONS` in `backend/app/core/permissions.py`. The same matrix is returned by `GET /api/auth/permissions` and `GET /api/settings`.

| Permission | Description | Administrator | Operator |
|---|---|---|---|
| `dashboard:view` | View the operations overview | yes | yes |
| `monitoring:view` | View monitoring data and targets | yes | yes |
| `incidents:view` | View and investigate incidents | yes | yes |
| `incidents:update` | Acknowledge, work on, comment on and resolve incidents | yes | yes |
| `incidents:close` | Close or reopen incidents | yes | no |
| `findings:view` | View security findings and scan history | yes | yes |
| `scans:run` | Run security scans | yes | yes |
| `findings:accept_risk` | Mark a finding as accepted risk | yes | no |
| `remediation:view` | View remediation requests and results | yes | yes |
| `remediation:request` | Request remediation | yes | yes |
| `remediation:approve` | Approve or reject remediation requests | yes | no |
| `remediation:execute` | Dispatch approved remediation to the worker and retry failures | yes | no |
| `remediation:cancel` | Cancel remediation requests (Operators: their own only) | yes | yes |
| `audit:view` | View operational audit events | yes | yes |
| `audit:view_all` | View all audit events, including sign-ins and administration | yes | no |
| `assistant:use` | Use the VigilAI assistant | yes | yes |
| `users:manage` | Create, update and deactivate users | yes | no |
| `settings:view` | View platform configuration | yes | yes |
| `settings:manage` | Change platform settings | yes | no |
| `demo:control` | Use demonstration controls (demonstration environments only) | yes | no |

Endpoints that only need a signed-in user, with no specific permission: `POST /api/auth/logout`, `GET /api/auth/me`, `GET /api/auth/permissions`, `POST /api/auth/change-password`.

## Health, version and metrics

Defined in `backend/app/main.py`. None of these requires authentication.

| Method and path | Routed by Caddy | Purpose |
|---|---|---|
| `GET /health/live` | no | Liveness: the process is running. Does not check dependencies. Also answers `HEAD` |
| `GET /health/ready` | no | Readiness: the database is reachable and the migrations are applied. HTTP 503 otherwise |
| `GET /api/health` | yes | Combined summary for people and uptime checks. HTTP 503 when not ready. Also answers `HEAD`, which some uptime monitors send |
| `GET /api/version` | yes | Project title, version and environment |
| `GET /metrics` | no | Prometheus exposition format, scraped by Prometheus over the internal network |

`GET /health/live`

```json
{ "status": "alive", "service": "VigilOps", "version": "2.0.0" }
```

In production mode the response is only `{ "status": "alive" }`; `service` and `version` are included in development.

`GET /health/ready` (HTTP 200, or 503 with `"status": "not_ready"`)

```json
{
  "status": "ready",
  "checks": {
    "database": { "ok": true, "error": null },
    "schema": { "ok": true }
  }
}
```

When the database check fails, `error` contains the exception class name only (for example `OperationalError`).

When the backend setting `INTERNAL_ENDPOINTS_LOCAL_ONLY` is `true` (default `false`; used by the single-container image, see [deployment-render-vercel.md](deployment-render-vercel.md)), `GET /health/ready` and `GET /metrics` answer HTTP 404 unless the caller is on the loopback interface and the request carries no `X-Forwarded-For` or `Forwarded` header.

`GET /api/health`

```json
{
  "status": "healthy",
  "service": "VigilOps",
  "version": "2.0.0",
  "environment": "development",
  "uptime_seconds": 1234.5,
  "checks": {
    "database": { "ok": true, "error": null },
    "schema": { "ok": true }
  }
}
```

In production mode the response is only `{ "status": "healthy" }`, or `{ "status": "unhealthy" }` with HTTP 503 when the backend is not ready; the other fields are included outside production.

`GET /api/version`

```json
{ "project": "VigilOps: Secure Cloud Operations", "version": "2.0.0", "environment": "development" }
```

In production mode the response is only `{ "project": "VigilOps: Secure Cloud Operations" }`.

`GET /metrics` exposes, besides the default process metrics of `prometheus_client`:

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | counter | `method`, `path` (route template), `status` |
| `http_request_duration_seconds` | histogram | `method`, `path` |
| `vigilops_alert_webhook_events_total` | counter | `result` (`created`, `deduplicated`, `reopened`, `resolved`, `cleared`, `ignored`) |
| `vigilops_alert_webhook_rejected_total` | counter | `reason` |
| `vigilops_security_scans_total` | counter | `status` |
| `vigilops_remediation_transitions_total` | counter | `status` |
| `vigilops_assistant_requests_total` | counter | `outcome` |
| `vigilops_assistant_provider_seconds` | histogram | - |
| `vigilops_open_incidents` | gauge | - |
| `vigilops_open_findings` | gauge | - |

## Authentication

Router: `backend/app/api/auth.py`.

### `POST /api/auth/login`

Exchanges an e-mail and password for an access token.

- **Permission:** none (public, rate limited).
- **Request body:**

  | Field | Type | Rules |
  |---|---|---|
  | `email` | string | 3 to 255 characters; trimmed and lower-cased |
  | `password` | string | 1 to 128 characters |

- **Success:** 200 with the token, its expiry and the user including the list of permissions.

```http
POST /api/auth/login
Content-Type: application/json

{ "email": "operator@example.test", "password": "<password>" }
```

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_at": "2026-01-15T11:00:00Z",
  "user": {
    "id": 2,
    "email": "operator@example.test",
    "full_name": "Example Operator",
    "role": "operator",
    "is_active": true,
    "last_login_at": "2026-01-15T10:00:00Z",
    "created_at": "2026-01-10T08:30:00Z",
    "permissions": [
      "assistant:use", "audit:view", "dashboard:view", "findings:view",
      "incidents:update", "incidents:view", "monitoring:view", "remediation:cancel",
      "remediation:request", "remediation:view", "scans:run", "settings:view"
    ]
  }
}
```

- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 401 | `Incorrect e-mail or password.` | Unknown e-mail, wrong password or deactivated account (deliberately the same message) |
  | 429 | `Too many sign-in attempts. Try again in N seconds.` | 5 failed attempts for the same client address and e-mail within 300 seconds, 20 failed attempts for the same e-mail from any address within 300 seconds (four times `LOGIN_RATE_LIMIT_ATTEMPTS`; sign-in for that e-mail is then refused from every address until the window passes), or more than 30 login requests from one address within 60 seconds. `Retry-After` is set |
  | 422 | validation | Missing or over-long field |

### `POST /api/auth/logout`

Revokes the presented token on the server so that it cannot be reused before it expires.

- **Permission:** signed-in user. **Request body:** none. **Success:** 204, no body.

### `GET /api/auth/me`

Returns the current user in the same shape as `user` in the login response. The frontend uses it to restore a session after a page reload.

- **Permission:** signed-in user. **Success:** 200.

### `GET /api/auth/permissions`

Returns the caller's role and the complete permission matrix.

- **Permission:** signed-in user. **Success:** 200.

```json
{
  "role": "operator",
  "matrix": [
    { "permission": "dashboard:view", "description": "View the operations overview", "admin": true, "operator": true },
    { "permission": "incidents:close", "description": "Close or reopen incidents", "admin": true, "operator": false },
    "..."
  ]
}
```

### `POST /api/auth/change-password`

Changes the caller's own password. Every existing session of the user, including the one making the call, is invalidated; the user signs in again with the new password.

- **Permission:** signed-in user.
- **Request body:**

  | Field | Type | Rules |
  |---|---|---|
  | `current_password` | string | 1 to 128 characters |
  | `new_password` | string | 1 to 128 characters, must satisfy the password policy and differ from the current password |

  Password policy: at least 10 characters, at most 72 bytes, upper-case and lower-case letters, at least one digit.

- **Success:** 204, no body.
- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 400 | `Current password is incorrect.` | Audited as `AUTH_PASSWORD_CHANGE_FAILED` |
  | 422 | `Password must be at least 10 characters long.` / `Password must be at most 72 bytes long.` / `Password must contain both upper-case and lower-case letters.` / `Password must contain at least one digit.` | Policy violation |
  | 422 | `The new password must be different from the current password.` | Same password |

## Users

Router: `backend/app/api/users.py`. All endpoints require `users:manage` (Administrator). There is no endpoint that deletes a user; accounts are deactivated instead.

User object:

```json
{
  "id": 3,
  "email": "new.operator@example.test",
  "full_name": "New Operator",
  "role": "operator",
  "is_active": true,
  "last_login_at": null,
  "created_at": "2026-01-15T10:00:00Z"
}
```

### `GET /api/users`

Paginated list of users.

- **Query parameters:** pagination. `q` searches e-mail and full name. `sort` accepts `email`, `role`, `created_at`; without `sort` the list is ordered by id ascending.
- **Success:** 200, envelope of user objects.

### `POST /api/users`

Creates a user.

- **Request body:**

  | Field | Type | Rules |
  |---|---|---|
  | `email` | string | Valid address pattern, at most 255 characters; lower-cased |
  | `full_name` | string | Optional, at most 120 characters |
  | `password` | string | 1 to 128 characters and the password policy |
  | `role` | `admin` or `operator` | Default `operator` |

- **Success:** 201 with the user object.
- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 409 | `A user with this e-mail already exists.` | Duplicate e-mail |
  | 422 | password policy message | Weak password |
  | 422 | validation | Invalid e-mail, role or length |

### `PATCH /api/users/{user_id}`

Changes the name, role or active flag. A change of role or active flag invalidates the user's existing sessions.

- **Request body** (all fields optional):

  | Field | Type | Rules |
  |---|---|---|
  | `full_name` | string | At most 120 characters |
  | `role` | `admin` or `operator` | - |
  | `is_active` | boolean | - |

- **Success:** 200 with the user object (also when nothing changed).
- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 404 | `User not found.` | Unknown id |
  | 409 | `The last active Administrator cannot be demoted or deactivated.` | The change would leave no active Administrator |
  | 409 | `You cannot deactivate your own account.` | `is_active: false` on the caller |

### `POST /api/users/{user_id}/reset-password`

Sets a new password for a user and invalidates that user's sessions.

- **Request body:** `{ "new_password": "<password>" }` (1 to 128 characters and the password policy).
- **Success:** 204, no body.
- **Errors:** 404 `User not found.`; 422 with a password policy message.

## Dashboard and monitoring

Router: `backend/app/api/monitoring.py`. Every monitoring value is the result of a Prometheus query made by the backend at request time (cached for 3 seconds). When a value cannot be obtained the response says so with `available: false` and a `reason`; no value is ever substituted.

### `GET /api/dashboard/summary`

Counts and platform health for the Overview page, computed from stored records.

- **Permission:** `dashboard:view`.
- **Success:** 200. `recent_audit_events` contains the eight most recent events the caller is allowed to see.

```json
{
  "generated_at": "2026-01-15T10:00:00+00:00",
  "incidents": {
    "active": 1,
    "by_status": { "OPEN": 1, "ACKNOWLEDGED": 0, "IN_PROGRESS": 0, "RESOLVED": 3, "CLOSED": 2 },
    "active_by_severity": { "CRITICAL": 1, "HIGH": 0, "MEDIUM": 0, "LOW": 0 },
    "resolved_last_24h": 1,
    "simulated_active": 1
  },
  "findings": {
    "open": 4,
    "by_status": { "OPEN": 4, "REMEDIATION_PENDING": 1, "RESOLVED": 0, "ACCEPTED_RISK": 0 },
    "unresolved_by_severity": { "CRITICAL": 1, "HIGH": 3, "MEDIUM": 1, "LOW": 0 }
  },
  "remediation": {
    "pending_approval": 1,
    "in_progress": 0,
    "succeeded": 2,
    "failed": 0,
    "by_status": {
      "PENDING_APPROVAL": 1, "APPROVED": 0, "REJECTED": 0, "QUEUED": 0, "RUNNING": 0,
      "VERIFYING": 0, "SUCCEEDED": 2, "FAILED": 0, "CANCELLED": 0
    }
  },
  "latest_scan": {
    "id": 7,
    "status": "COMPLETED",
    "trigger": "MANUAL",
    "target": "*",
    "requested_by": "operator@example.test",
    "started_at": "2026-01-15T09:58:00+00:00",
    "completed_at": "2026-01-15T09:58:00+00:00",
    "summary": { "...": "same object as result_summary of a scan" }
  },
  "recent_audit_events": [
    {
      "id": 120,
      "created_at": "2026-01-15T09:58:00+00:00",
      "actor": "operator@example.test",
      "action": "SECURITY_SCAN_COMPLETED",
      "entity_type": "security_scan",
      "entity_id": "7",
      "outcome": "SUCCESS"
    }
  ],
  "platform": {
    "backend": { "healthy": true, "version": "2.0.0", "environment": "development" },
    "database": { "healthy": true, "error": null },
    "worker": {
      "online": true,
      "worker_id": "remediation-worker-1",
      "last_seen_at": "2026-01-15T09:59:57+00:00",
      "last_seen_age_seconds": 3.0,
      "started_at": "2026-01-15T08:00:00+00:00",
      "jobs_processed": 5
    },
    "demo_controls_enabled": true
  }
}
```

`unresolved_by_severity` counts findings in OPEN and REMEDIATION_PENDING. `in_progress` counts requests in APPROVED, QUEUED, RUNNING and VERIFYING. `worker.online` is true when the heartbeat is at most 45 seconds old; if no worker ever reported, `worker` is `{"online": false, "worker_id": null, "last_seen_at": null, "detail": "No worker has reported yet."}`. `latest_scan` is `null` before the first scan.

### `GET /api/monitoring/overview`

Live state of Prometheus, Alertmanager, the scrape targets, the alerts known to Prometheus and the monitored resources with the current value of every catalog metric.

- **Permission:** `monitoring:view`.
- **Success:** 200.

```json
{
  "generated_at": "2026-01-15T10:00:00+00:00",
  "source": "prometheus",
  "scrape_interval_seconds": 5,
  "prometheus": { "available": true, "error": null },
  "alertmanager": { "available": true, "error": null },
  "targets": {
    "available": true,
    "reason": null,
    "targets": [
      {
        "job": "demo-app",
        "instance": "test-app:8001",
        "health": "up",
        "last_scrape": "2026-01-15T09:59:58+00:00",
        "last_scrape_age_seconds": 2.0,
        "last_error": null,
        "scrape_url": "http://test-app:8001/metrics",
        "stale": false
      }
    ]
  },
  "alerts": {
    "available": true,
    "reason": null,
    "alerts": [
      {
        "name": "HighApiLatency",
        "state": "firing",
        "severity": "MEDIUM",
        "resource": "demo-app",
        "instance": "test-app:8001",
        "summary": "High API latency on the demo application",
        "active_at": "2026-01-15T09:55:00Z"
      }
    ]
  },
  "resources": [
    {
      "id": 1,
      "name": "demo-app",
      "resource_type": "application",
      "environment": "local",
      "job": "demo-app",
      "description": "OrbitCrate storefront, the monitored demonstration application.",
      "status": "UP",
      "last_known_status": "UP",
      "status_checked_at": "2026-01-15T10:00:00+00:00",
      "metrics": {
        "request_rate": {
          "label": "HTTP request rate",
          "unit": "req/s",
          "description": "Requests per second over the last minute.",
          "available": true,
          "value": 2.0,
          "reason": null,
          "sampled_at": "2026-01-15T09:59:59+00:00"
        },
        "latency_p95": {
          "label": "Response latency (p95)",
          "unit": "seconds",
          "description": "95th percentile request duration over the last minute.",
          "available": false,
          "value": null,
          "reason": "no data",
          "sampled_at": null
        }
      }
    }
  ]
}
```

Notes: a target is `stale` when its last scrape is older than four scrape intervals; `status` is `UP`, `DOWN` or `UNKNOWN` as derived from the targets now, while `last_known_status` is the last status that was actually observed and stored. If Prometheus is not ready, `targets` and `alerts` have `available: false` with the reason, resources have `status: "UNKNOWN"` and empty `metrics`. The `metrics` object has one entry per key of the metric catalog (two are shown).

### `GET /api/monitoring/metrics`

The metric catalog and the available range presets.

- **Permission:** `monitoring:view`.
- **Success:** 200.

```json
{
  "metrics": [
    { "key": "availability", "label": "Availability", "unit": "state", "description": "Prometheus scrape success (1 = target reachable, 0 = down)." },
    { "key": "request_rate", "label": "HTTP request rate", "unit": "req/s", "description": "Requests per second over the last minute." },
    "..."
  ],
  "ranges": ["5m", "15m", "1h", "6h"]
}
```

Catalog keys: `availability`, `request_rate`, `error_rate_5xx`, `error_rate_4xx`, `latency_p95`, `cpu_usage`, `memory_rss`, `uptime`.

### `GET /api/monitoring/timeseries`

Historical samples of one catalog metric for one monitored resource. Arbitrary PromQL is not accepted.

- **Permission:** `monitoring:view`.
- **Query parameters:**

  | Parameter | Required | Rules |
  |---|---|---|
  | `job` | yes | At most 80 characters; must be the Prometheus job of a registered monitored resource (`demo-app`, `vigilops-backend`) |
  | `metric` | yes | At most 40 characters; a key of the metric catalog |
  | `range` | no | `5m`, `15m` (default), `1h` or `6h` |

- **Success:** 200.

```http
GET /api/monitoring/timeseries?job=demo-app&metric=request_rate&range=15m
```

```json
{
  "job": "demo-app",
  "metric": "request_rate",
  "label": "HTTP request rate",
  "unit": "req/s",
  "range": "15m",
  "step_seconds": 15,
  "source": "prometheus",
  "generated_at": "2026-01-15T10:00:00+00:00",
  "available": true,
  "reason": null,
  "points": [
    { "t": "2026-01-15T09:45:00+00:00", "v": 2.0 },
    { "t": "2026-01-15T09:45:15+00:00", "v": null },
    { "t": "2026-01-15T09:45:45+00:00", "v": 2.0 }
  ]
}
```

A point with `"v": null` marks a gap: Prometheus had no sample for that step (for example while the target was down), so a chart can draw a break instead of a line. With an empty range the response has `available: true`, `reason: "no data in the selected range"` and no points; when Prometheus cannot be queried it has `available: false` and the reason.

- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 400 | `Unknown monitored resource.` | `job` is malformed or not registered |
  | 400 | `Unknown metric.` | `metric` is not a catalog key |
  | 400 | `Unknown time range.` | `range` is not a preset |
  | 422 | validation | A required parameter is missing or too long |

## Alertmanager webhook

### `POST /api/alerts/webhook`

Receives firing and resolved notifications from Alertmanager and feeds the incident engine. It follows Alertmanager's `webhook_config` payload format; fields that the engine does not use are ignored.

- **Authentication:** `Authorization: Bearer <ALERT_WEBHOOK_TOKEN>`. The token is compared in constant time. A user's JWT is not accepted. In the Compose stack Alertmanager reads the token from the secret file `/run/secrets/alert_webhook_token`.
- **Request body:**

  | Field | Type | Rules |
  |---|---|---|
  | `version`, `status`, `receiver` | string | Optional, not used |
  | `alerts` | array | 1 to 100 alert objects |
  | `alerts[].status` | `firing` or `resolved` | Required |
  | `alerts[].labels` | object of strings | Must contain a non-empty `alertname`; at most 60 labels |
  | `alerts[].annotations` | object of strings | Optional; `summary` becomes the incident title and `description` its description |
  | `alerts[].startsAt`, `alerts[].endsAt` | string | Optional, at most 64 characters, RFC 3339 |
  | `alerts[].fingerprint` | string | Optional, 8 to 64 hexadecimal characters. If absent, the backend hashes the sorted label set |

  Labels with a meaning for the engine: `alertname`, `severity` (`critical`, `high` or `error`, `warning` or `medium`, `low` or `info`; anything else becomes MEDIUM), `resource` and `job` (looked up among the monitored resources), `instance`.

```http
POST /api/alerts/webhook
Authorization: Bearer <ALERT_WEBHOOK_TOKEN>
Content-Type: application/json

{
  "version": "4",
  "status": "firing",
  "receiver": "vigilops-backend",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "ApplicationUnavailable",
        "severity": "critical",
        "job": "demo-app",
        "resource": "demo-app",
        "instance": "test-app:8001",
        "action_code": "ACTION-001"
      },
      "annotations": {
        "summary": "Demo application is unavailable",
        "description": "Prometheus has been unable to scrape test-app:8001 for more than 15 seconds."
      },
      "startsAt": "2026-01-15T10:00:00.000Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "fingerprint": "0123456789abcdef"
    }
  ]
}
```

- **Success:** 200 with one counter per outcome.

```json
{
  "status": "processed",
  "alerts": 1,
  "results": { "created": 1, "deduplicated": 0, "reopened": 0, "resolved": 0, "cleared": 0, "ignored": 0 }
}
```

  | Outcome | Meaning |
  |---|---|
  | `created` | Firing alert, no active incident with this fingerprint: a new incident was opened |
  | `deduplicated` | Firing alert for an active incident: its notification counter and last occurrence were updated |
  | `reopened` | Firing alert for an incident resolved within the reopen window: the incident was reopened |
  | `resolved` | Resolved alert for an active incident: the incident was resolved with the monitoring signal as evidence |
  | `cleared` | Resolved alert for an incident that was already resolved: only the "alert active" flag was cleared |
  | `ignored` | Resolved alert with no matching incident |

- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 401 | `Invalid webhook credentials.` | Missing or wrong token |
  | 422 | validation | Payload does not match the schema (for example an empty `alerts` list or a missing `alertname`) |

  The token is checked by a dependency before the body is parsed, so a request without a valid token is always answered with 401, even when its payload is malformed.

The `action_code` label in the alert rules is informational; the backend decides which automated action applies from its own catalog.

## Incidents

Router: `backend/app/api/incidents.py`. Incidents are created only by the alert webhook; there is no endpoint that creates or deletes an incident.

Incident summary object (`IncidentOut`):

```json
{
  "id": 12,
  "title": "Demo application is unavailable",
  "description": "Prometheus has been unable to scrape test-app:8001 for more than 15 seconds.",
  "severity": "CRITICAL",
  "status": "OPEN",
  "source": "alertmanager",
  "alert_name": "ApplicationUnavailable",
  "alert_fingerprint": "0123456789abcdef",
  "resource_id": 1,
  "affected_resource": "demo-app",
  "action_code": "ACTION-001",
  "is_simulated": true,
  "simulation_note": "Controlled demo fault 'outage' was active when this alert fired.",
  "alert_active": true,
  "occurrence_count": 3,
  "detected_at": "2026-01-15T10:00:00Z",
  "last_occurrence_at": "2026-01-15T10:04:20Z",
  "acknowledged_at": null,
  "resolved_at": null,
  "closed_at": null,
  "resolution_summary": null,
  "signal_stale": false
}
```

`severity` is `CRITICAL`, `HIGH`, `MEDIUM` or `LOW`; `status` is `OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED` or `CLOSED`. `signal_stale` is true when the alert is recorded as still firing but no notification has arrived for 420 seconds (three repeat intervals plus one minute).

### `GET /api/incidents`

- **Permission:** `incidents:view`.
- **Query parameters:** pagination, plus

  | Parameter | Rules |
  |---|---|
  | `status` | Comma-separated statuses, at most 80 characters |
  | `severity` | Comma-separated severities, at most 60 characters |
  | `active_only` | `true` limits the list to OPEN, ACKNOWLEDGED and IN_PROGRESS |

  `q` searches title, description, alert name and affected resource; a number (optionally written `#12` or `inc-12`) also matches the id. `sort` accepts `id`, `detected_at` (default), `last_occurrence_at`, `status`, `title`, `occurrence_count`, `severity`.

- **Success:** 200, envelope of incident summary objects.

### `GET /api/incidents/{incident_id}`

- **Permission:** `incidents:view`.
- **Success:** 200 with the summary fields plus:

```json
{
  "id": 12,
  "status": "OPEN",
  "...": "all summary fields",
  "labels": { "alertname": "ApplicationUnavailable", "severity": "critical", "job": "demo-app", "resource": "demo-app", "instance": "test-app:8001" },
  "annotations": { "summary": "Demo application is unavailable", "description": "..." },
  "events": [
    {
      "id": 40,
      "event_type": "ALERT_RECEIVED",
      "actor_label": "alertmanager",
      "previous_state": null,
      "new_state": "OPEN",
      "details": "Incident opened from alert ApplicationUnavailable.",
      "metadata": { "fingerprint": "0123456789abcdef", "simulated": true },
      "created_at": "2026-01-15T10:00:20Z",
      "updated_at": "2026-01-15T10:00:20Z"
    }
  ],
  "remediation_requests": [
    { "id": 5, "action_code": "ACTION-001", "status": "PENDING_APPROVAL", "created_at": "2026-01-15T10:02:00Z", "completed_at": null }
  ],
  "recommendation": {
    "problem": "Prometheus can no longer scrape the application: the target is down.",
    "affected_resource": "demo-app",
    "evidence": { "alert": "ApplicationUnavailable", "description": "...", "occurrences": 3, "alert_still_firing": true },
    "possible_causes": ["..."],
    "recommended_steps": ["..."],
    "troubleshooting": ["..."],
    "automation": {
      "supported": true,
      "action_code": "ACTION-001",
      "action": { "code": "ACTION-001", "name": "Recover monitored demonstration application", "...": "see GET /api/remediation/actions" },
      "reason": null
    }
  },
  "allowed_transitions": ["ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED"]
}
```

  `recommendation` is static runbook content selected by alert name; it is not generated by the assistant. `allowed_transitions` lists the target statuses the caller may request now, taking the role into account.

- **Errors:** 404 `Incident not found.`

### `POST /api/incidents/{incident_id}/transition`

Moves an incident through its lifecycle.

- **Permission:** `incidents:update`. Closing (`CLOSED`) and reopening (`RESOLVED` to `OPEN`) additionally require `incidents:close`.
- **Request body:**

  | Field | Type | Rules |
  |---|---|---|
  | `status` | `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED`, `CLOSED` or `OPEN` | Required |
  | `note` | string | Optional, at most 2000 characters. Required with at least 10 characters when resolving or reopening |
  | `override_monitoring` | boolean | Default `false`. Honoured only for an Administrator and only when Prometheus cannot be queried: the incident is then resolved without confirmation from monitoring. It has no effect while Prometheus reports the alert as firing. Recorded in the evidence |

  Allowed transitions: OPEN to ACKNOWLEDGED, IN_PROGRESS or RESOLVED; ACKNOWLEDGED to IN_PROGRESS or RESOLVED; IN_PROGRESS to RESOLVED; RESOLVED to CLOSED or OPEN; none from CLOSED.

```http
POST /api/incidents/12/transition
Authorization: Bearer <JWT>
Content-Type: application/json

{ "status": "RESOLVED", "note": "Service restarted by the on-call engineer; readiness probe returns 200 again." }
```

- **Success:** 200 with the incident detail object. Resolving also cancels remediation requests for the incident that were not yet dispatched.
- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 404 | `Incident not found.` | Unknown id |
  | 409 | `Invalid transition CLOSED -> OPEN. Allowed from CLOSED: none (terminal state).` | The transition is not in the table (the message names the allowed targets) |
  | 403 | `Only an Administrator can close or reopen an incident.` | Caller lacks `incidents:close`. Audited as `INCIDENT_STATUS_CHANGE_DENIED` |
  | 422 | `A reason is required to reopen an incident.` | Reopen note shorter than 10 characters |
  | 422 | `Resolution evidence is required: describe how recovery was verified (at least 10 characters).` | Resolution note shorter than 10 characters |
  | 409 | `Monitoring still reports this alert as firing. The incident can only be resolved once the condition has cleared.` | The alert is still firing in Prometheus (an override does not change this) |
  | 409 | `Recovery cannot be verified because Prometheus is unavailable (<reason>). An Administrator may override with a documented reason.` | Prometheus could not be queried and no Administrator override was given |

### `POST /api/incidents/{incident_id}/comments`

Adds a comment to the timeline. Comments are possible in every status.

- **Permission:** `incidents:update`.
- **Request body:** `{ "note": "<text>" }`, 2 to 2000 characters.
- **Success:** 201 with the new timeline event.

```json
{
  "id": 44,
  "event_type": "COMMENT",
  "actor_label": "operator@example.test",
  "previous_state": null,
  "new_state": null,
  "details": "Checked the application logs: the service component stopped at 10:00.",
  "metadata": {},
  "created_at": "2026-01-15T10:03:00Z",
  "updated_at": "2026-01-15T10:03:00Z"
}
```

- **Errors:** 404 `Incident not found.`

## Security scanning

Router: `backend/app/api/security.py`. Responses of `rules` and `targets` carry a `scope` sentence stating that the scanner evaluates authorised local YAML files and does not assess a live cloud account.

### `GET /api/security/rules`

The rule catalog.

- **Permission:** `findings:view`.
- **Success:** 200.

```json
{
  "scope": "The scanner evaluates authorised local YAML configuration files in the scan workspace against rules SEC-001 to SEC-005. It does not assess a live cloud account.",
  "rules": [
    {
      "id": "SEC-001",
      "name": "Public Storage Access",
      "severity": "HIGH",
      "description": "A storage bucket allows anonymous (public) access to its contents.",
      "detection_logic": "A resource of type storage_bucket is flagged when `public_access` is true, or when `acl` is `public-read` or `public-read-write`.",
      "impact": "...",
      "recommendation": "...",
      "resource_types": ["storage_bucket"],
      "automated_action": "ACTION-002"
    },
    "..."
  ]
}
```

### `GET /api/security/targets`

The files that may be scanned: plain `.yaml` or `.yml` files directly inside the scan workspace.

- **Permission:** `findings:view`.
- **Success:** 200.

```json
{
  "scope": "...",
  "targets": [
    {
      "name": "cloud-infrastructure.yaml",
      "size_bytes": 1650,
      "modified_at": "2026-01-15T08:00:05+00:00",
      "remediation_allowed": true
    }
  ]
}
```

`remediation_allowed` is true when the file is named in `REMEDIATION_WRITABLE_TARGETS`.

### `GET /api/security/targets/{name}`

Returns the content of one target so that a finding can be compared with the file.

- **Permission:** `findings:view`.
- **Success:** 200 with `name`, `size_bytes`, `modified_at` and `content` (text).
- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 400 | `Target must be the name of a .yaml file in the authorised scan workspace.` | Not a plain file name |
  | 400 | `Target is outside the authorised scan workspace.` | The resolved path leaves the workspace (for example through a symbolic link) |
  | 400 | `Target file is too large to display.` | Larger than `SCAN_MAX_FILE_BYTES` |
  | 404 | `Target 'x.yaml' does not exist in the scan workspace.` | No such file |

### `POST /api/security/scans`

Runs a scan synchronously and returns its record.

- **Permission:** `scans:run`.
- **Request body:** `{ "target": "<file name>" }` (at most 130 characters) to scan one file, or `{}` to scan every file in the workspace.
- **Success:** 201 with the scan object.

```http
POST /api/security/scans
Authorization: Bearer <JWT>
Content-Type: application/json

{ "target": "cloud-infrastructure.yaml" }
```

```json
{
  "id": 7,
  "requested_by": 2,
  "requested_by_label": "operator@example.test",
  "trigger": "MANUAL",
  "target": "cloud-infrastructure.yaml",
  "status": "COMPLETED",
  "started_at": "2026-01-15T09:58:00Z",
  "completed_at": "2026-01-15T09:58:00Z",
  "result_summary": {
    "files_scanned": ["cloud-infrastructure.yaml"],
    "files_failed": {},
    "violations_detected": 5,
    "new_findings": 5,
    "reopened_findings": 0,
    "unchanged_findings": 0,
    "resolved_findings": 0,
    "by_rule": { "SEC-001": 1, "SEC-002": 1, "SEC-003": 1, "SEC-004": 1, "SEC-005": 1 },
    "by_severity": { "HIGH": 3, "MEDIUM": 1, "CRITICAL": 1 },
    "orphaned_findings": 0,
    "note": null
  },
  "error": null
}
```

  The example corresponds to a first scan of the shipped baseline file `security-rules/samples/baseline/cloud-infrastructure.yaml`. `trigger` is `MANUAL`, `REMEDIATION_VERIFICATION` (run by the worker) or `DEMO_RESET`. `target` is `*` for a scan of all files. A file that fails validation is listed in `files_failed` with the reason; the scan is `FAILED` (with `error` set) only when no file could be scanned. With an empty workspace the scan is `COMPLETED` and `note` says that no configuration files are present.

- **Errors:** the same 400 and 404 target errors as above (returned before a scan is recorded).

### `GET /api/security/scans`

Scan history, newest first.

- **Permission:** `findings:view`. **Query parameters:** `page`, `page_size` (sorting and search are not applied). **Success:** 200, envelope of scan objects.

### `GET /api/security/scans/{scan_id}`

- **Permission:** `findings:view`. **Success:** 200 with the scan object. **Errors:** 404 `Scan not found.`

### `GET /api/security/findings`

- **Permission:** `findings:view`.
- **Query parameters:** pagination, plus

  | Parameter | Rules |
  |---|---|
  | `status` | Comma-separated: `OPEN`, `REMEDIATION_PENDING`, `RESOLVED`, `ACCEPTED_RISK` |
  | `severity` | Comma-separated severities |
  | `rule_id` | For example `SEC-001` |
  | `target_file` | Exact file name |

  `q` searches rule id, rule name, resource identifier and file name. `sort` accepts `id`, `severity`, `status`, `rule_id`, `resource`, `first_detected_at`, `last_seen_at`. Without `sort` the list is ordered by severity with CRITICAL first; `order` is applied only together with `sort`.

- **Success:** 200, envelope of finding objects (`FindingOut`):

```json
{
  "id": 3,
  "scan_id": 7,
  "last_scan_id": 7,
  "stable_finding_key": "<64 hexadecimal characters>",
  "rule_id": "SEC-001",
  "rule_name": "Public Storage Access",
  "severity": "HIGH",
  "target_file": "cloud-infrastructure.yaml",
  "resource_type": "storage_bucket",
  "resource_name": "customer-records",
  "resource_identifier": "storage_bucket/customer-records",
  "evidence": {
    "summary": "Bucket allows public access (public_access = true, acl = public-read).",
    "matches": [ { "public_access": true, "acl": "public-read" } ],
    "details": [ "Bucket allows public access (public_access = true, acl = public-read)." ]
  },
  "recommendation": "...",
  "status": "OPEN",
  "detection_count": 1,
  "first_detected_at": "2026-01-15T09:58:00Z",
  "last_seen_at": "2026-01-15T09:58:00Z",
  "resolved_at": null,
  "accepted_risk_reason": null,
  "accepted_risk_at": null
}
```

### `GET /api/security/findings/{finding_id}`

- **Permission:** `findings:view`.
- **Success:** 200 with the finding fields plus:

  | Field | Content |
  |---|---|
  | `rule` | The rule's catalog entry (as in `GET /api/security/rules`), or `null` |
  | `guidance` | `problem`, `affected_resource`, `evidence`, `detection_logic`, `security_impact`, `recommendation`, `recommended_steps` (list) and `automation` (`supported`, `action_code`, `action`, `reason`) |
  | `remediation_requests` | Brief list: `id`, `action_code`, `status`, `created_at`, `completed_at` |
  | `history` | Audit events of this finding in chronological order: `at`, `action`, `actor`, `outcome`, `metadata` |

- **Errors:** 404 `Security finding not found.`

### `POST /api/security/findings/{finding_id}/accept-risk`

Marks an OPEN finding as accepted risk with a recorded justification.

- **Permission:** `findings:accept_risk` (Administrator).
- **Request body:** `{ "reason": "<text>" }`, 10 to 2000 characters.
- **Success:** 200 with the finding detail (status `ACCEPTED_RISK`).
- **Errors:** 404 `Security finding not found.`; 409 `Only OPEN findings can be marked as accepted risk (current: RESOLVED).`

### `POST /api/security/findings/{finding_id}/revoke-risk-acceptance`

Returns an accepted-risk finding to OPEN.

- **Permission:** `findings:accept_risk`. **Request body:** none.
- **Success:** 200 with the finding detail.
- **Errors:** 404 `Security finding not found.`; 409 `Finding is not in ACCEPTED_RISK state.`

## Remediation

Router: `backend/app/api/remediation.py`. The API records decisions and moves a request to QUEUED; execution and verification are done by the restricted worker, and their progress is observed by reading the request.

Statuses: `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `QUEUED`, `RUNNING`, `VERIFYING`, `SUCCEEDED`, `FAILED`, `CANCELLED`. The state machine is described in [architecture.md](architecture.md#remediation-requests).

Request summary object (`RemediationOut`):

```json
{
  "id": 5,
  "correlation_id": "00000000-0000-4000-8000-000000000005",
  "source_type": "finding",
  "source_id": 3,
  "incident_id": null,
  "finding_id": 3,
  "action_code": "ACTION-002",
  "action_name": "Correct public storage configuration",
  "target": "cloud-infrastructure.yaml#storage_bucket/customer-records",
  "status": "PENDING_APPROVAL",
  "justification": "Customer records must not be publicly readable.",
  "decision_comment": null,
  "requested_by": 2,
  "requested_by_email": "operator@example.test",
  "approved_by": null,
  "approved_by_email": null,
  "attempt_count": 0,
  "max_attempts": 3,
  "failure_reason": null,
  "created_at": "2026-01-15T10:02:00Z",
  "decided_at": null,
  "queued_at": null,
  "started_at": null,
  "completed_at": null,
  "allowed_operations": ["cancel"]
}
```

`approved_by` holds the Administrator who approved or rejected. `allowed_operations` lists the workflow operations the caller may perform now (`approve`, `reject`, `execute`, `retry`, `cancel`); it is a hint for the user interface, and each endpoint checks again.

Request detail object (`RemediationDetail`) adds:

```json
{
  "...": "all summary fields",
  "executions": [
    {
      "id": 9,
      "attempt": 1,
      "worker_identifier": "remediation-worker-1",
      "status": "SUCCEEDED",
      "execution_details": {
        "action": "ACTION-002",
        "operation": "Edit cloud-infrastructure.yaml in the scan workspace",
        "target_file": "cloud-infrastructure.yaml",
        "resource": "storage_bucket/customer-records",
        "changed": true,
        "changes": ["public_access: false", "acl: private"],
        "before": { "public_access": true, "acl": "public-read" },
        "after": { "public_access": false, "acl": "private" },
        "sha256_before": "<hash>",
        "sha256_after": "<hash>",
        "diff": "--- cloud-infrastructure.yaml (before)\n+++ cloud-infrastructure.yaml (after)\n...",
        "completed_at": "2026-01-15T10:06:01+00:00"
      },
      "verification_result": {
        "passed": true,
        "summary": "SEC-001 is no longer detected for storage_bucket/customer-records; confirmed by verification scan #8.",
        "checks": [
          { "name": "security_rescan", "passed": true, "detail": "Verification scan #8 finished with status COMPLETED.", "observed_at": "2026-01-15T10:06:01+00:00", "scan_id": 8 },
          { "name": "rule_not_detected", "passed": true, "detail": "SEC-001 is no longer detected for storage_bucket/customer-records.", "observed_at": "2026-01-15T10:06:01+00:00" },
          { "name": "finding_resolved_by_scan", "passed": true, "detail": "Finding #3 status is RESOLVED.", "observed_at": "2026-01-15T10:06:01+00:00" }
        ],
        "verified_at": "2026-01-15T10:06:01+00:00"
      },
      "error": null,
      "started_at": "2026-01-15T10:06:00Z",
      "completed_at": "2026-01-15T10:06:01Z"
    }
  ],
  "action": { "code": "ACTION-002", "name": "Correct public storage configuration", "...": "see GET /api/remediation/actions" },
  "source_summary": {
    "type": "finding",
    "id": 3,
    "title": "SEC-001 Public Storage Access",
    "status": "RESOLVED",
    "severity": "HIGH",
    "resource": "storage_bucket/customer-records",
    "target_file": "cloud-infrastructure.yaml"
  },
  "timeline": [
    { "at": "2026-01-15T10:02:00Z", "action": "REMEDIATION_REQUESTED", "actor": "operator@example.test", "outcome": "SUCCESS", "metadata": { "...": "..." } }
  ]
}
```

For ACTION-001 the verification checks are named `application_health`, `prometheus_target_up` and `alert_cleared`, and `execution_details` contains the readiness probe before the action, the list of recovery calls and the application's response. For an incident source, `source_summary` contains `type`, `id`, `title`, `status` and `severity`. `timeline` holds every audit event that shares the request's `correlation_id`.

### `GET /api/remediation/actions`

The complete allowlist of automated actions and the liveness of the worker.

- **Permission:** `remediation:view`.
- **Success:** 200.

```json
{
  "actions": [
    {
      "code": "ACTION-001",
      "name": "Recover monitored demonstration application",
      "description": "Calls the demo application's token-protected internal recovery endpoint, which re-initialises its service component and clears any active fault condition.",
      "source_type": "incident",
      "risk": "Low - affects only the demonstration application; no host or Docker access.",
      "steps": ["..."],
      "verification": ["..."]
    },
    {
      "code": "ACTION-002",
      "name": "Correct public storage configuration",
      "description": "...",
      "source_type": "finding",
      "risk": "...",
      "steps": ["..."],
      "verification": ["..."]
    }
  ],
  "worker": {
    "online": true,
    "worker_id": "remediation-worker-1",
    "last_seen_at": "2026-01-15T09:59:57+00:00",
    "last_seen_age_seconds": 3.0,
    "started_at": "2026-01-15T08:00:00+00:00",
    "jobs_processed": 5
  }
}
```

### `GET /api/remediation/requests`

- **Permission:** `remediation:view`.
- **Query parameters:** pagination, plus

  | Parameter | Rules |
  |---|---|
  | `status` | Comma-separated statuses, at most 160 characters |
  | `action_code` | `ACTION-001` or `ACTION-002` |
  | `source_type` | `incident` or `finding` |
  | `mine` | `true` limits the list to requests submitted by the caller |

  `q` searches target, justification and action code; a number also matches the id. `sort` accepts `id`, `created_at` (default), `status`, `action_code`, `completed_at`.

- **Success:** 200, envelope of request summary objects.

### `POST /api/remediation/requests`

Submits a remediation request. It always starts in `PENDING_APPROVAL`.

- **Permission:** `remediation:request`.
- **Request body:**

  | Field | Type | Rules |
  |---|---|---|
  | `source_type` | `incident` or `finding` | Required |
  | `source_id` | integer | Greater than 0 |
  | `action_code` | string | 3 to 20 characters matching `^[A-Z]+-\d{3}$`; must be in the action catalog |
  | `justification` | string | 10 to 2000 characters (at least 10 after trimming) |

  There is no field for a command, a script or a path.

```http
POST /api/remediation/requests
Authorization: Bearer <JWT>
Content-Type: application/json

{
  "source_type": "finding",
  "source_id": 3,
  "action_code": "ACTION-002",
  "justification": "Customer records must not be publicly readable."
}
```

- **Success:** 201 with the request detail object. For a finding, the finding's status becomes `REMEDIATION_PENDING`.
- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 422 | `'ACTION-999' is not a supported remediation action. Only allowlisted actions can be requested.` | Code not in the catalog |
  | 422 | `ACTION-002 applies to a finding, not to a incident.` | Action and source type do not match |
  | 422 | `A justification of at least 10 characters is required.` | Justification too short after trimming |
  | 404 | `Incident not found.` / `Security finding not found.` | Unknown source |
  | 409 | `Remediation request #5 is already in progress for this finding (PENDING_APPROVAL).` | Another request for the source is in flight |
  | 409 | `No automated action exists for this resource; follow the manual steps.` | Incident on a resource other than the demo application |
  | 409 | `The incident is already RESOLVED.` | Incident no longer active |
  | 409 | `Automated correction is not implemented for SEC-003; apply the recommended change manually and run the scan again.` | Finding of a rule other than SEC-001 |
  | 409 | `This configuration file is not on the remediation allowlist.` | File not in `REMEDIATION_WRITABLE_TARGETS` |
  | 409 | `The finding is ACCEPTED_RISK; only OPEN findings can be remediated.` | Finding not OPEN |

### `GET /api/remediation/requests/{request_id}`

- **Permission:** `remediation:view`. **Success:** 200 with the request detail object. **Errors:** 404 `Remediation request not found.`

### Workflow operations

All five operations return 200 with the request detail object, 404 `Remediation request not found.` for an unknown id, and 409 when the request is not in the required status, with a message of the form `Request #5 is APPROVED; this operation requires PENDING_APPROVAL.` A refused operation changes nothing.

| Method and path | Permission | Required status | Body | Result |
|---|---|---|---|---|
| `POST /api/remediation/requests/{id}/approve` | `remediation:approve` | PENDING_APPROVAL | `{ "comment": "<optional, at most 2000 characters>" }` | APPROVED; the approver and time are recorded |
| `POST /api/remediation/requests/{id}/reject` | `remediation:approve` | PENDING_APPROVAL | `{ "comment": "<reason, at least 5 characters>" }` | REJECTED; a REMEDIATION_PENDING finding returns to OPEN |
| `POST /api/remediation/requests/{id}/execute` | `remediation:execute` | APPROVED | none | QUEUED for the worker |
| `POST /api/remediation/requests/{id}/retry` | `remediation:execute` | FAILED | none | QUEUED again |
| `POST /api/remediation/requests/{id}/cancel` | `remediation:cancel` | PENDING_APPROVAL or APPROVED | `{ "comment": "<optional reason>" }` | CANCELLED; a REMEDIATION_PENDING finding returns to OPEN |

`approve`, `reject` and `cancel` expect a JSON body; send `{}` when there is no comment.

Additional errors:

| Operation | Status | `detail` | When |
|---|---|---|---|
| approve | 403 | `You cannot approve a remediation request that you submitted yourself. Another Administrator must review it.` | Caller is the requester and `remediation.allow_self_approval` is off. Audited as `REMEDIATION_APPROVAL_DENIED` |
| reject | 422 | `A reason is required when rejecting a remediation request.` | Comment shorter than 5 characters |
| retry | 409 | `Request #5 has used all 3 attempts. Submit a new request after investigating the failure.` | Attempt limit reached |
| retry | 409 | `The incident is already RESOLVED.` / `The finding is already RESOLVED.` | The problem no longer exists |
| retry | 409 | `Another remediation request is already in progress for this source.` | A newer request is in flight |
| cancel | 403 | `Operators can only cancel their own remediation requests.` | Operator cancelling someone else's request |

Example: approve, then dispatch.

```http
POST /api/remediation/requests/5/approve
Authorization: Bearer <administrator JWT>
Content-Type: application/json

{ "comment": "Reviewed the finding; the change is limited to the sample bucket." }
```

```http
POST /api/remediation/requests/5/execute
Authorization: Bearer <administrator JWT>
```

After `execute` the response shows `"status": "QUEUED"`. Poll `GET /api/remediation/requests/5` to follow `RUNNING`, `VERIFYING` and the final `SUCCEEDED` or `FAILED`; on failure `failure_reason` and the last execution's `verification_result` explain why.

## Audit

Router: `backend/app/api/audit.py`. The audit API is read-only: no endpoint edits or deletes audit history.

Audit event object:

```json
{
  "id": 131,
  "event_id": "00000000-0000-4000-8000-000000000131",
  "actor_id": 1,
  "actor_label": "admin@example.test",
  "action": "REMEDIATION_APPROVED",
  "entity_type": "remediation_request",
  "entity_id": "5",
  "outcome": "SUCCESS",
  "metadata": {
    "action_code": "ACTION-002",
    "target": "cloud-infrastructure.yaml#storage_bucket/customer-records",
    "source_type": "finding",
    "source_id": 3,
    "status": "APPROVED",
    "comment": "Reviewed the finding; the change is limited to the sample bucket."
  },
  "correlation_id": "00000000-0000-4000-8000-000000000005",
  "source_ip": "203.0.113.10",
  "created_at": "2026-01-15T10:05:00Z"
}
```

`actor_id` is `null` for service identities (`alertmanager`, `system`, the worker id) and for failed sign-ins. `outcome` is `SUCCESS`, `FAILURE` or `DENIED`. Values of metadata keys that look like credentials are stored as `[REDACTED]`.

**Visibility.** Administrators see every event. Operators see events whose action starts with `INCIDENT_`, `ALERT_`, `SECURITY_SCAN_`, `FINDING_`, `REMEDIATION_` or `DEMO_`, plus events in which they are the recorded actor. The restriction applies to the list, to the single-event lookup and to the totals.

### `GET /api/audit/events`

- **Permission:** `audit:view`.
- **Query parameters:** pagination, plus

  | Parameter | Rules |
  |---|---|
  | `action` | Exact action name, at most 80 characters (case-insensitive) |
  | `category` | Action prefix, at most 40 characters, for example `REMEDIATION` (see `GET /api/audit/meta`) |
  | `outcome` | `SUCCESS`, `FAILURE` or `DENIED` |
  | `entity_type` | For example `incident`, `finding`, `remediation_request`, `security_scan`, `user`, `setting` |
  | `entity_id` | At most 64 characters |
  | `correlation_id` | At most 64 characters |
  | `actor` | Substring of the actor label, at most 120 characters |
  | `date_from`, `date_to` | ISO 8601 date-times (inclusive) |

  `q` searches action, actor, entity type, entity id, correlation id and the metadata text. `sort` accepts `created_at` (default), `action`, `outcome`, `actor`, `entity_type`.

- **Success:** 200, envelope of audit event objects.

```http
GET /api/audit/events?category=REMEDIATION&outcome=DENIED&page_size=10
```

### `GET /api/audit/meta`

Filter values for the audit page and the caller's visibility.

- **Permission:** `audit:view`. **Success:** 200.

```json
{
  "categories": [
    { "key": "AUTH", "label": "Authentication" },
    { "key": "INCIDENT", "label": "Incidents" },
    { "key": "SECURITY_SCAN", "label": "Security scans" },
    { "key": "FINDING", "label": "Findings" },
    { "key": "REMEDIATION", "label": "Remediation" },
    { "key": "USER", "label": "User administration" },
    { "key": "SETTINGS", "label": "Settings" },
    { "key": "ACCESS", "label": "Access denied" },
    { "key": "ASSISTANT", "label": "VigilAI" },
    { "key": "DEMO", "label": "Demo controls" }
  ],
  "outcomes": ["SUCCESS", "FAILURE", "DENIED"],
  "visibility": "operational",
  "visibility_note": "Your role shows operational events (incidents, scans, findings, remediation) and your own activity (such as sign-ins)."
}
```

For an Administrator `visibility` is `all`.

### `GET /api/audit/events/{event_pk}`

One event by its numeric `id`.

- **Permission:** `audit:view`. **Success:** 200 with the audit event object.
- **Errors:** 404 `Audit event not found.` - also returned when the event exists but is outside the caller's visibility.

## VigilAI assistant

Router: `backend/app/api/assistant.py`. The assistant is read-only; its pipeline and safeguards are described in [security.md](security.md#vigilai-safeguards). The Gemini API is called only by the backend.

### `GET /api/assistant/status`

- **Permission:** `assistant:use`. **Success:** 200.

```json
{
  "enabled": true,
  "provider": "gemini",
  "model": "<value of GEMINI_MODEL>",
  "live_ai_configured": false,
  "mode": "documentation",
  "welcome_message": "Hi! I'm VigilAI, your VigilOps assistant. I can help you understand monitoring, incidents, security findings, remediation workflows, and platform troubleshooting. How can I help?",
  "suggested_questions": ["Why is my application unhealthy?", "Show my authorized open incidents.", "..."],
  "knowledge_base_topics": [ { "document": "alerting.md", "title": "Alerting and Alert Management" }, "..." ],
  "max_input_chars": 1000,
  "capabilities": { "read_only": true, "can_execute_actions": false }
}
```

`mode` is `ai` when the assistant is enabled and a Gemini API key is configured, otherwise `documentation`. `model` is `null` when `AI_PROVIDER` is `none`.

### `POST /api/assistant/chat`

Asks a question. Refusals are normal 200 responses with `mode: "refusal"`, not errors.

- **Permission:** `assistant:use`.
- **Request body:**

  | Field | Type | Rules |
  |---|---|---|
  | `message` | string | 1 to 2000 characters, not blank. The service uses at most `AI_MAX_INPUT_CHARS` (default 1000) characters |
  | `history` | array | Optional, at most 20 turns. The service passes the last 6 to the model, each cut to 600 characters, and drops turns that look like an attempt to override the assistant's rules. History is never used to decide whether a question is in scope: for short follow-ups the server remembers each user's last in-scope question itself (for 15 minutes) |
  | `history[].role` | `user` or `assistant` | - |
  | `history[].content` | string | At most 4000 characters |

- **Response fields:**

  | Field | Content |
  |---|---|
  | `reply` | Plain text. May contain `**bold**`, `` `code` `` and `- ` bullet lines; never HTML |
  | `mode` | `ai` (generated by Gemini), `fallback` (documentation and live data without the model) or `refusal` |
  | `scope` | `in_scope`, `out_of_scope`, `privileged_action`, `secret_request` or `prompt_injection` |
  | `notice` | In `fallback` mode, the reason why live AI generation was not used; otherwise `null` |
  | `provider`, `model` | Set in `ai` mode (`provider` also in `fallback` mode when a provider is configured) |
  | `sources` | Knowledge-base sections used: `document`, `title`, `section` |
  | `live_data` | Read-only context tools that ran: `tool`, `retrieved_at`, `denied` |

```http
POST /api/assistant/chat
Authorization: Bearer <JWT>
Content-Type: application/json

{ "message": "What does SEC-001 mean?", "history": [] }
```

Example response in documentation mode (no Gemini key configured):

```json
{
  "reply": "Here is what the VigilOps documentation and live platform data say:\n\nFrom the documentation - Security Rules and Scanner › SEC-001 Public Storage Access:\nSEC-001 means a storage bucket allows anonymous public access. ...",
  "mode": "fallback",
  "scope": "in_scope",
  "notice": "Live AI generation is not configured on this server (no Gemini API key).",
  "provider": null,
  "model": null,
  "sources": [
    { "document": "security_rules.md", "title": "Security Rules and Scanner", "section": "SEC-001 Public Storage Access" }
  ],
  "live_data": []
}
```

Example refusal (an instruction to act):

```http
POST /api/assistant/chat

{ "message": "Approve remediation request 5", "history": [] }
```

```json
{
  "reply": "I can't do that - VigilAI is a read-only assistant. I cannot approve, reject or execute remediation, run scans or commands, or change incidents, configurations, users or settings.\n\n...",
  "mode": "refusal",
  "scope": "privileged_action",
  "notice": null,
  "provider": null,
  "model": null,
  "sources": [],
  "live_data": []
}
```

Refusals with scope `privileged_action`, `secret_request` or `prompt_injection` are written to the audit trail as `ASSISTANT_REQUEST_BLOCKED` (outcome DENIED) with the category, without the message text. When the runtime setting `assistant.enabled` is off, every call returns a refusal with the text "VigilAI has been turned off by an administrator."

The `ai` mode has the same shape with `mode: "ai"`, `provider: "gemini"` and the configured model. Live generation was verified with a real Gemini key on 2026-11-23 (default model `gemini-3.5-flash-lite`, 9 of 9 platform questions answered in `ai` mode; evidence in [`evidence/gemini-live.json`](evidence/gemini-live.json)); see the [verification report](verification-report.md).

- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 429 | `You are sending messages too quickly. Try again in N seconds.` | More than `AI_RATE_LIMIT_PER_MINUTE` (default 10) messages from one user within 60 seconds. `Retry-After` is set |
  | 422 | validation | Blank or over-long message, more than 20 history turns |

  A failure of the AI provider is not an error for the client: the response is a `fallback` reply with a `notice`.

## Settings

Router: `backend/app/api/settings.py`.

### `GET /api/settings`

The effective configuration. Secret values are never returned, only whether they are set.

- **Permission:** `settings:view`.
- **Success:** 200.

```json
{
  "can_manage": true,
  "system": {
    "project": "VigilOps: Secure Cloud Operations",
    "version": "2.0.0",
    "environment": "development",
    "demo_controls_enabled": true,
    "session_minutes": 60,
    "login_rate_limit": { "attempts": 5, "window_seconds": 300 },
    "api_docs_enabled": true,
    "placeholder_secrets_in_use": false
  },
  "assistant": {
    "provider": "gemini",
    "model": "<value of GEMINI_MODEL>",
    "api_key_configured": false,
    "rate_limit_per_minute": 10,
    "daily_request_limit": 400,
    "timeout_seconds": 20.0
  },
  "scanner": {
    "workspace": "scan workspace (authorised local YAML files)",
    "max_file_bytes": 262144,
    "remediation_writable_targets": ["cloud-infrastructure.yaml"]
  },
  "remediation": {
    "max_attempts": 3,
    "action_timeout_seconds": 30.0,
    "verification_timeout_seconds": 150.0,
    "worker": { "online": true, "worker_id": "remediation-worker-1", "...": "as in GET /api/remediation/actions" }
  },
  "runtime_settings": [
    {
      "key": "remediation.allow_self_approval",
      "label": "Allow self-approval of remediation",
      "description": "...",
      "type": "bool",
      "value": false,
      "default": false,
      "minimum": null,
      "maximum": null,
      "updated_at": null
    },
    {
      "key": "incidents.reopen_window_minutes",
      "label": "Incident reopen window (minutes)",
      "description": "...",
      "type": "int",
      "value": 10,
      "default": 10,
      "minimum": 0,
      "maximum": 1440,
      "updated_at": null
    },
    {
      "key": "assistant.enabled",
      "label": "VigilAI assistant enabled",
      "description": "...",
      "type": "bool",
      "value": true,
      "default": true,
      "minimum": null,
      "maximum": null,
      "updated_at": null
    }
  ],
  "permission_matrix": [
    { "permission": "dashboard:view", "description": "View the operations overview", "admin": true, "operator": true },
    "..."
  ]
}
```

### `PUT /api/settings/{key}`

Changes one runtime setting. The change is audited as `SETTINGS_UPDATED` with the previous and new value.

- **Permission:** `settings:manage` (Administrator).
- **Path parameter:** `key` - one of the three keys above (for example `PUT /api/settings/incidents.reopen_window_minutes`).
- **Request body:** `{ "value": <new value> }`. The type must match exactly: `true` or `false` for `bool` settings; a whole number within `minimum` and `maximum` for `int` settings.
- **Success:** 200 with the updated entry in the shape of one `runtime_settings` item.

```http
PUT /api/settings/incidents.reopen_window_minutes
Authorization: Bearer <administrator JWT>
Content-Type: application/json

{ "value": 15 }
```

- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 404 | `Unknown setting.` | The key is not declared |
  | 422 | `incidents.reopen_window_minutes must be a whole number` / `... must be at least 0` / `... must be at most 1440` | Wrong type or out of bounds |
  | 422 | `remediation.allow_self_approval must be true or false` | Not a boolean |

## Demo controls

Router: `backend/app/api/demo.py`. These endpoints drive the local demonstration. They are active only when `DEMO_CONTROLS_ENABLED=true` and the environment is not production, or, in production mode, when the hosted-demonstration opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION=true` is set as well (default `false`); otherwise the two POST endpoints return 404.

### `GET /api/demo/status`

Whether the controls are available and the demo application's current fault state.

- **Permission:** `settings:view`.
- **Success:** 200.

```json
{
  "enabled": true,
  "environment": "development",
  "fault_modes": {
    "none": "No fault - normal operation.",
    "outage": "Service outage: every service endpoint and /metrics answer HTTP 503.",
    "errors": "Error burst: the business endpoint answers HTTP 500 for most requests.",
    "latency": "Slow responses: the business endpoint takes about 1.5 seconds.",
    "cpu": "CPU saturation: a bounded background thread keeps one core busy.",
    "memory": "Memory pressure: the service allocates a bounded block of memory."
  },
  "disabled_fault_modes": [],
  "demo_app": {
    "service": "vigilops-demo-app",
    "fault_mode": "none",
    "fault_since": null,
    "serving": true,
    "service_started_at": "2026-01-15T08:00:00+00:00",
    "service_restarts": 0,
    "demo_controls_enabled": true
  },
  "demo_app_reachable": true
}
```

`fault_modes` contains only the modes this deployment offers. Modes switched off with `DEMO_DISABLED_FAULTS` are left out of it and listed in `disabled_fault_modes` instead (for example `["cpu", "memory"]`).

When the controls are disabled: `enabled: false`, `fault_modes: {}`, `disabled_fault_modes: []`, `demo_app: null`, `demo_app_reachable: null`.

### `POST /api/demo/faults`

Injects or clears a controlled fault on the demonstration application.

- **Permission:** `demo:control` (Administrator).
- **Request body:** `{ "mode": "none" | "outage" | "errors" | "latency" | "cpu" | "memory" }`. `none` clears the fault.
- **Success:** 200.

```json
{
  "status": "applied",
  "simulated": true,
  "demo_app": {
    "status": "applied",
    "simulated": true,
    "service": "vigilops-demo-app",
    "fault_mode": "outage",
    "fault_since": "2026-01-15T10:00:00+00:00",
    "serving": false,
    "service_started_at": "2026-01-15T08:00:00+00:00",
    "service_restarts": 0,
    "demo_controls_enabled": true
  }
}
```

- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 404 | `Demonstration controls are disabled in this environment.` | Controls inactive (in production unless `ALLOW_DEMO_CONTROLS_IN_PRODUCTION` is set) |
  | 502 | `The demonstration application could not be reached.` | Network error; audited with outcome FAILURE |
  | 502 | `The demonstration application rejected the request (HTTP 401).` | The demo application refused the call |
  | 422 | validation | Unknown mode |
  | 422 | `The 'cpu' fault is switched off in this deployment because the host does not have the resources to run it.` | The mode is listed in `DEMO_DISABLED_FAULTS` |

### `POST /api/demo/reset-config`

Restores the insecure sample configuration in the scan workspace and scans it again. The API has only read access to the workspace, so it queues a task for the worker and waits up to 20 seconds for the result.

- **Permission:** `demo:control`. **Request body:** none.
- **Success:** 200.

```json
{
  "status": "reset",
  "simulated": true,
  "restored_files": ["cloud-infrastructure.yaml"],
  "scan": { "id": 9, "trigger": "DEMO_RESET", "target": "*", "status": "COMPLETED", "...": "scan object" }
}
```

- **Errors:**

  | Status | `detail` | When |
  |---|---|---|
  | 404 | `Demonstration controls are disabled in this environment.` | Controls inactive |
  | 503 | `The remediation worker did not complete the reset in time. Is the worker running?` | No result within the waiting time |
  | 503 | the worker's error text | The worker reported the task as FAILED |

## Appendix A: audit actions

Values of `action` in audit events, grouped by the categories of `GET /api/audit/meta`.

| Category | Actions |
|---|---|
| AUTH | `AUTH_LOGIN_SUCCESS`, `AUTH_LOGIN_FAILED`, `AUTH_LOGIN_RATE_LIMITED`, `AUTH_LOGOUT`, `AUTH_PASSWORD_CHANGED`, `AUTH_PASSWORD_CHANGE_FAILED` |
| INCIDENT | `INCIDENT_CREATED`, `INCIDENT_STATUS_CHANGED`, `INCIDENT_RESOLVED`, `INCIDENT_REOPENED`, `INCIDENT_COMMENT_ADDED`, `INCIDENT_STATUS_CHANGE_DENIED` |
| SECURITY_SCAN | `SECURITY_SCAN_COMPLETED`, `SECURITY_SCAN_FAILED` |
| FINDING | `FINDING_DETECTED`, `FINDING_REOPENED`, `FINDING_RESOLVED`, `FINDING_REMEDIATION_PENDING`, `FINDING_RISK_ACCEPTED`, `FINDING_RISK_ACCEPTANCE_REVOKED` |
| REMEDIATION | `REMEDIATION_REQUESTED`, `REMEDIATION_APPROVED`, `REMEDIATION_APPROVAL_DENIED`, `REMEDIATION_REJECTED`, `REMEDIATION_QUEUED`, `REMEDIATION_CANCELLED`, `REMEDIATION_RETRY_QUEUED`, `REMEDIATION_EXECUTION_STARTED`, `REMEDIATION_EXECUTION_REFUSED`, `REMEDIATION_EXECUTION_ERROR`, `REMEDIATION_EXECUTED`, `REMEDIATION_VERIFICATION_PASSED`, `REMEDIATION_VERIFICATION_FAILED`, `REMEDIATION_SUCCEEDED`, `REMEDIATION_FAILED` |
| USER | `USER_BOOTSTRAPPED`, `USER_CREATED`, `USER_UPDATED`, `USER_PASSWORD_RESET` |
| SETTINGS | `SETTINGS_UPDATED` |
| ACCESS | `ACCESS_DENIED` |
| ASSISTANT | `ASSISTANT_REQUEST_BLOCKED` |
| DEMO | `DEMO_FAULT_INJECTED`, `DEMO_FAULT_CLEARED`, `DEMO_CONFIG_RESET_REQUESTED`, `DEMO_CONFIG_RESET`, `DEMO_WORKSPACE_INITIALISED` |

## Appendix B: incident timeline event types

Values of `event_type` in `events` of an incident.

| Event type | Written when |
|---|---|
| `ALERT_RECEIVED` | The incident is opened from a firing alert |
| `ALERT_REPEATED` | Alertmanager repeats the notification (one event, updated in place with the current count) |
| `ALERT_CLEARED` | Alertmanager reports the alert as resolved |
| `STATUS_CHANGED` | A user acknowledges, starts work on or closes the incident |
| `RESOLVED` | The incident is resolved; `metadata.evidence` holds the evidence |
| `REOPENED` | An Administrator, or a returning alert, reopens the incident |
| `COMMENT` | A user adds a comment |
| `REMEDIATION_REQUESTED`, `REMEDIATION_APPROVED`, `REMEDIATION_REJECTED`, `REMEDIATION_QUEUED`, `REMEDIATION_CANCELLED`, `REMEDIATION_RETRY` | Workflow steps performed through the API |
| `REMEDIATION_STARTED`, `REMEDIATION_EXECUTED`, `REMEDIATION_FAILED`, `REMEDIATION_SUCCEEDED` | Steps performed by the worker |
