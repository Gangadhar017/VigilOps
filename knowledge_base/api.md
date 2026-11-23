# API Usage

## API basics
The REST API is served under /api by the FastAPI backend. Send the access token as "Authorization: Bearer <token>". List endpoints accept page, page_size, sort, order and q (search) and return items, total, page and page_size. Errors return JSON with a "detail" message and a request_id. In development the interactive documentation is at http://localhost:8000/docs.

## Authentication endpoints
POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me, GET /api/auth/permissions, POST /api/auth/change-password.

## Monitoring endpoints
GET /api/dashboard/summary, GET /api/monitoring/overview, GET /api/monitoring/metrics, GET /api/monitoring/timeseries?job=demo-app&metric=request_rate&range=15m.

## Incident endpoints
GET /api/incidents, GET /api/incidents/{id}, POST /api/incidents/{id}/transition, POST /api/incidents/{id}/comments. POST /api/alerts/webhook is for Alertmanager only.

## Security endpoints
GET /api/security/rules, GET /api/security/targets, GET /api/security/targets/{name}, POST /api/security/scans, GET /api/security/scans, GET /api/security/scans/{id}, GET /api/security/findings, GET /api/security/findings/{id}, POST /api/security/findings/{id}/accept-risk, POST /api/security/findings/{id}/revoke-risk-acceptance.

## Remediation endpoints
GET /api/remediation/actions, GET and POST /api/remediation/requests, GET /api/remediation/requests/{id}, and POST .../approve, .../reject, .../execute, .../retry and .../cancel.

## Audit and assistant endpoints
GET /api/audit/events, GET /api/audit/events/{id}, GET /api/audit/meta, GET /api/assistant/status, POST /api/assistant/chat.

## User and settings endpoints
GET and POST /api/users, PATCH /api/users/{id} and POST /api/users/{id}/reset-password are for Administrators only. GET /api/settings shows the effective configuration without secret values; PUT /api/settings/{key} changes a runtime setting (Administrator).

## Demo control endpoints
GET /api/demo/status, POST /api/demo/faults and POST /api/demo/reset-config exist only when demo controls are enabled and the environment is not production; injecting faults and resetting the sample configuration require an Administrator.

## Health endpoints
GET /api/health and GET /api/version are public. The backend also serves GET /health/live, GET /health/ready and GET /metrics on the internal network only; they are not reachable through the reverse proxy.

## HTTP status codes
200 or 201 success; 400 invalid request; 401 not signed in or session expired; 403 role not permitted; 404 not found; 409 the operation conflicts with the current state (for example an invalid incident transition); 422 validation error; 429 rate limited; 503 a dependency is not ready.
