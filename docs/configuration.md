# Configuration Reference

Everything that can be configured in VigilOps: the `.env` file, every backend setting, the three
runtime settings, how secrets are handled, the monitoring configuration files, the scan workspace,
and the `vigilops/v1` YAML schema that the security scanner reads.

Related documents: [setup](setup.md), [deployment](deployment.md), [security](security.md),
[troubleshooting](troubleshooting.md).

## Contents

1. [How configuration reaches the services](#how-configuration-reaches-the-services)
2. [Variables in .env.example](#variables-in-envexample)
3. [Values set by Compose or by the image](#values-set-by-compose-or-by-the-image)
4. [All backend settings](#all-backend-settings)
5. [Other variables](#other-variables)
6. [Changing a setting that Compose does not pass through](#changing-a-setting-that-compose-does-not-pass-through)
7. [Runtime settings](#runtime-settings)
8. [How secrets are handled](#how-secrets-are-handled)
9. [Monitoring configuration files](#monitoring-configuration-files)
10. [The scan workspace](#the-scan-workspace)
11. [The vigilops/v1 schema](#the-vigilopsv1-schema)

## How configuration reaches the services

1. You edit `.env` in the repository root. It is listed in `.gitignore` and excluded from Docker
   build contexts by `.dockerignore`.
2. Docker Compose reads `.env` and substitutes the values into `compose.yaml`.
3. Each service receives only the variables that `compose.yaml` lists under its `environment` key.
   The `.env` file itself is not mounted into any container.
4. The backend and the worker read their environment through `backend/app/core/config.py`
   (pydantic-settings). Unknown variables are ignored; names are case-sensitive.

Two consequences:

- A backend setting that is not listed in `compose.yaml` keeps its default from `config.py` even if
  you add it to `.env`. See
  [Changing a setting that Compose does not pass through](#changing-a-setting-that-compose-does-not-pass-through).
- Changes to `.env` take effect when the affected containers are recreated:
  `docker compose up -d`. Compose requires `POSTGRES_PASSWORD`, `SECRET_KEY` and
  `ALERT_WEBHOOK_TOKEN` to be set and stops with a message naming the missing variable otherwise.

## Variables in .env.example

"Placeholder" means a public development-only value that is present in `.env.example`; it is not
repeated here.

### Mode and ports

| Variable | Value in `.env.example` | Purpose | Used by |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `development` or `production` (`test` is used by the test suite). Production mode refuses placeholder secrets and SQLite, turns API docs off and disables demonstration controls (unless the hosted-demonstration opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION` is set). `compose.prod.yaml` forces `production`. | backend, worker |
| `VIGILOPS_HTTP_PORT` | `8080` | Host port of the web application in the local stack. Ignored by the production overlay, which publishes 80 and 443. | web (port mapping), `run_e2e_demos.py` |
| `VIGILOPS_BIND_ADDRESS` | `127.0.0.1` | Host interface the web port listens on. `127.0.0.1` means this computer only. `0.0.0.0` makes the local stack reachable from other devices; it speaks plain HTTP, so use that only on a trusted network. Ignored by the production overlay. | web (port mapping) |
| `BACKEND_DEV_PORT` | `8000` | Host port (127.0.0.1 only) of the backend, for API docs and the Vite dev proxy. | Compose port mapping |
| `PROMETHEUS_DEV_PORT` | `9090` | Host port (127.0.0.1 only) of the Prometheus UI. | Compose port mapping, `run_e2e_demos.py` |
| `ALERTMANAGER_DEV_PORT` | `9093` | Host port (127.0.0.1 only) of the Alertmanager UI. | Compose port mapping |
| `VIGILOPS_DOMAIN` | commented out | Public DNS name of the server. Required by `compose.prod.yaml`; Caddy obtains a TLS certificate for it. | web (production overlay) |

### Database

| Variable | Value in `.env.example` | Purpose | Used by |
|---|---|---|---|
| `POSTGRES_USER` | `vigilops` | Database user. | postgres; Compose builds `DATABASE_URL` from it |
| `POSTGRES_PASSWORD` | placeholder | Database password. Use only letters, digits, `-` and `_` because it is placed in a URL. Applied by PostgreSQL only when the data volume is first created. | postgres; `DATABASE_URL` |
| `POSTGRES_DB` | `vigilops` | Database name. | postgres; `DATABASE_URL` |

### Security

| Variable | Value in `.env.example` | Purpose | Used by |
|---|---|---|---|
| `SECRET_KEY` | placeholder | JWT signing key. At least 32 characters, otherwise the API does not start. Changing it invalidates every session. | backend |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Lifetime of an access token. | backend |
| `ALERT_WEBHOOK_TOKEN` | placeholder | Bearer token Alertmanager presents to `POST /api/alerts/webhook`. At least 16 characters. | backend; alertmanager (as a Docker secret file) |

### First accounts

| Variable | Value in `.env.example` | Purpose | Used by |
|---|---|---|---|
| `BOOTSTRAP_ADMIN_EMAIL` | `admin@vigilops.local` | E-mail of the first Administrator. | backend, `run_e2e_demos.py` |
| `BOOTSTRAP_ADMIN_PASSWORD` | placeholder | Its initial password. | backend, `run_e2e_demos.py` |
| `BOOTSTRAP_OPERATOR_EMAIL` | `operator@vigilops.local` | E-mail of the first Operator. | backend, `run_e2e_demos.py` |
| `BOOTSTRAP_OPERATOR_PASSWORD` | placeholder | Its initial password. | backend, `run_e2e_demos.py` |

An account is created at backend start only if no account with that e-mail exists. An empty e-mail
or password skips the account. Password policy: at least 10 characters, upper-case and lower-case
letters and a digit, at most 72 bytes. In production mode the API refuses to start if a bootstrap
password does not meet the policy ("BOOTSTRAP_ADMIN_PASSWORD does not meet the password policy:
..."); outside production the account is skipped and an error is logged.

### Demonstration environment

| Variable | Value in `.env.example` | Purpose | Used by |
|---|---|---|---|
| `DEMO_CONTROLS_ENABLED` | `true` (Compose default when unset: `false`) | Enables fault injection and sample-configuration reset for Administrators, and makes the worker place the sample configuration in an empty scan workspace. Off in production mode unless the hosted-demonstration opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION` is also set; the production overlay forces it to `false`. | backend, worker, test-app |
| `DEMO_APP_CONTROL_TOKEN` | placeholder | Token for the demo application's fault-injection and state endpoints. | backend, test-app |
| `DEMO_APP_RECOVERY_TOKEN` | placeholder | Token for the demo application's recovery endpoint (ACTION-001). The backend does not receive it. | worker, test-app |

### VigilAI

| Variable | Value in `.env.example` | Purpose | Used by |
|---|---|---|---|
| `AI_PROVIDER` | `gemini` | `gemini` or `none`. With `none` VigilAI always runs in documentation mode. | backend |
| `GEMINI_API_KEY` | empty | Google Gemini API key. Empty means documentation mode. | backend |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model name passed to the `google-genai` SDK. | backend |
| `AI_RATE_LIMIT_PER_MINUTE` | `10` | Chat messages per user per minute. Applies in every mode. Exceeding it returns HTTP 429. | backend |
| `AI_DAILY_REQUEST_LIMIT` | `400` | Server-wide cap on provider calls per UTC day; `0` disables the cap. When reached, VigilAI answers in documentation mode. Counted in memory, so it restarts from zero when the backend restarts. | backend |

### Logging and CORS

| Variable | Value in `.env.example` | Purpose | Used by |
|---|---|---|---|
| `LOG_LEVEL` | `INFO` | Python log level. | backend, worker |
| `LOG_FORMAT` | `json` | `json` (one JSON object per line) or `text`. The production overlay sets `json` for the backend. | backend, worker |
| `CORS_ORIGINS` | empty | Comma-separated list of origins allowed to call the API from a browser. Empty means no CORS headers are sent; the bundled web service and the Vite dev proxy are same-origin and do not need it. | backend |

## Values set by Compose or by the image

These are not set in `.env.example`. Compose or the backend image sets them.

| Variable | Value in the stack | Set in | Purpose | Used by |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql://<user>:<password>@postgres:5432/<db>` | `compose.yaml`, from the `POSTGRES_*` variables | Database connection. The backend adds the `psycopg2` driver itself. | backend, worker |
| `PROMETHEUS_URL` | `http://prometheus:9090` | `compose.yaml` | Prometheus HTTP API. | backend, worker |
| `ALERTMANAGER_URL` | `http://alertmanager:9093` | `compose.yaml` | Alertmanager readiness check. | backend, worker |
| `DEMO_APP_URL` | `http://test-app:8001` | `compose.yaml` | Base URL of the demo application. | backend, worker |
| `PROMETHEUS_SCRAPE_INTERVAL_SECONDS` | `5` unless set in `.env` | `compose.yaml` | Tells the backend the scrape interval so it can mark targets stale. Does not change Prometheus; keep it equal to `scrape_interval` in `monitoring/prometheus.yml`. | backend, worker |
| `PROCESS_ROLE` | `api` or `worker` | `compose.yaml` | The worker role does not need `SECRET_KEY` or `ALERT_WEBHOOK_TOKEN` and is not given them. | backend, worker |
| `WORKER_ID` | `remediation-worker-1` | `compose.yaml` | Identity of the worker in heartbeats and audit events. | worker |
| `FORWARDED_ALLOW_IPS` | `*` unless set in `.env` | `compose.yaml`, used in the start command in `backend/Dockerfile` | Peers whose `X-Forwarded-For` header Uvicorn trusts when determining the client address (used for rate limiting and audit). The default trusts any peer on the private Docker network; set it to the proxy's address to tighten it. | backend |
| `SITE_ADDRESS` | `:80` locally, `VIGILOPS_DOMAIN` in production | `compose.yaml`, `compose.prod.yaml` | Caddy site address. A domain name turns on automatic HTTPS. | web |
| `KNOWLEDGE_BASE_DIR` | `/srv/vigilops/knowledge_base` | `backend/Dockerfile` | Knowledge base copied into the image. | backend |
| `SECURITY_RULES_DIR` | `/srv/vigilops/security-rules` | `backend/Dockerfile` | Rule catalog and sample files copied into the image. | backend, worker |
| `SCAN_WORKSPACE_DIR` | `/data/scan-workspace` | `backend/Dockerfile` | Mount point of the `scan_workspace` volume. | backend (read-only), worker |
| `PORT` | `8001` | `compose.yaml` | Listening port of the demo application. | test-app |

## All backend settings

Every field of the `Settings` class in `backend/app/core/config.py`. "Passed by Compose" tells you
whether `compose.yaml` forwards the variable to a container; if it says no, the code default applies
in the Compose stack.

Five settings are not passed through by `compose.yaml` and are used by the single-container image
(`deploy/render/Dockerfile`) described in [deployment-render-vercel.md](deployment-render-vercel.md):
`ALLOW_DEMO_CONTROLS_IN_PRODUCTION`, `DEMO_DISABLED_FAULTS`, `INTERNAL_ENDPOINTS_LOCAL_ONLY`,
`SERVE_DEMO_APP` and `RUN_MIGRATIONS_ON_START`.

### Identity and mode

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `PROJECT_NAME` | `VigilOps` | no | Service name in health responses. | backend |
| `PROJECT_TITLE` | `VigilOps: Secure Cloud Operations` | no | Title in `/api/version` and the settings page. | backend |
| `VERSION` | `2.0.0` | no | Version reported by the API and stored in the worker heartbeat. | backend, worker |
| `ENVIRONMENT` | `development` | yes | `development`, `production` or `test`. Any other value stops the process. | backend, worker |
| `PROCESS_ROLE` | `api` | yes | `api` or `worker`. | backend, worker |

### Authentication and HTTP

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `SECRET_KEY` | empty; must be set, 32+ characters for the API role | yes (backend) | JWT signing key. | backend |
| `ALGORITHM` | `HS256` | no | JWT signing algorithm. | backend |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | yes (backend) | Token lifetime. | backend |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | `5` | yes (backend) | Failed sign-ins allowed per client address and e-mail within the window. Four times this value (20 by default) is the number of failed sign-ins allowed per e-mail from all addresses together; reaching it locks sign-in for that e-mail from every address until the window passes. The same limit applies per user to wrong current-password entries on the change-password form. | backend |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `300` | yes (backend) | Length of that window. | backend |
| `CORS_ORIGINS` | empty | yes (backend) | Allowed browser origins, comma separated. | backend |
| `ENABLE_API_DOCS` | unset: on outside production, off in production | no | Forces `/docs` and `/openapi.json` on or off. | backend |
| `ALERT_WEBHOOK_TOKEN` | empty; must be set, 16+ characters for the API role | yes (backend) | Shared token for the alert webhook. | backend |
| `INTERNAL_ENDPOINTS_LOCAL_ONLY` | `false` | no | When `true`, `/metrics` and `/health/ready` answer HTTP 404 unless the caller is on the loopback interface and the request carries no `X-Forwarded-For` or `Forwarded` header. Needed when the API port itself is the public port. Used by the single-container image. | backend |
| `SERVE_DEMO_APP` | `false` | no | When `true`, the API passes the demonstration application's storefront through under `/orbitcrate/`: the page, `static/*` and `api/*` only, never `/internal/*`, `/metrics` or `/health/*`. No credentials, cookies or query strings are forwarded, a request body may be at most 4096 bytes, and each client address is limited to 300 requests per minute. For hosts with one public port; in the Compose stack the reverse proxy routes that address to the application directly and this stays `false`. The single-container image sets it to `true`. | backend |

Independently of these settings, sign-in requests are also limited to 30 per client address per
minute (a constant in `backend/app/api/auth.py`).

### Database and first accounts

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `DATABASE_URL` | none; required | yes | SQLAlchemy URL. SQLite is refused in production mode. | backend, worker |
| `RUN_MIGRATIONS_ON_START` | `false` | no | When `true`, the API applies the Alembic migrations itself when it starts and retries for about two minutes if the database is not ready. The Compose image runs `alembic upgrade head` as a separate step instead. Used by the single-container image. | backend |
| `BOOTSTRAP_ADMIN_EMAIL` | empty | yes (backend) | First Administrator. | backend |
| `BOOTSTRAP_ADMIN_PASSWORD` | empty | yes (backend) | First Administrator's password. | backend |
| `BOOTSTRAP_OPERATOR_EMAIL` | empty | yes (backend) | First Operator. | backend |
| `BOOTSTRAP_OPERATOR_PASSWORD` | empty | yes (backend) | First Operator's password. | backend |

### Integrated services

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `PROMETHEUS_URL` | `http://localhost:9090` | yes | Prometheus HTTP API. | backend, worker |
| `ALERTMANAGER_URL` | `http://localhost:9093` | yes | Alertmanager readiness. | backend, worker |
| `DEMO_APP_URL` | `http://localhost:8001` | yes | Demo application. | backend, worker |
| `DEMO_APP_JOB` | `demo-app` | no | Prometheus job name of the demo application. ACTION-001 is offered only for incidents on this resource. Must match `monitoring/prometheus.yml`. | backend, worker |
| `BACKEND_JOB` | `vigilops-backend` | no | Prometheus job name under which the backend is registered as a monitored resource. | backend |
| `MONITORING_HTTP_TIMEOUT_SECONDS` | `4.0` | no | Timeout of calls to Prometheus and Alertmanager. | backend, worker |
| `PROMETHEUS_SCRAPE_INTERVAL_SECONDS` | `5` | yes | A scrape target is marked stale when its last scrape is older than four times this value. | backend, worker |
| `ALERT_REPEAT_INTERVAL_SECONDS` | `120` | yes | Must equal `repeat_interval` in `monitoring/alertmanager.yml`. An active incident is flagged "Signal stale" when no notification has arrived for three times this value plus 60 seconds. | backend |

### Demonstration environment

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `DEMO_CONTROLS_ENABLED` | `false` | yes | Demonstration controls; ignored in production unless `ALLOW_DEMO_CONTROLS_IN_PRODUCTION` is `true`. | backend, worker |
| `DEMO_APP_CONTROL_TOKEN` | empty | yes (backend) | Fault injection and reading the demo application's fault state. | backend |
| `DEMO_APP_RECOVERY_TOKEN` | empty | yes (worker) | ACTION-001 recovery call. | worker |
| `ALLOW_DEMO_CONTROLS_IN_PRODUCTION` | `false` | no | Explicit opt-in that keeps the demonstration controls available in production mode when `DEMO_CONTROLS_ENABLED=true`. Only for a hosted demonstration instance whose only workload is the bundled demo application; the controls stay Administrator-only and audited. Used by the single-container image. | backend, worker |
| `DEMO_DISABLED_FAULTS` | empty | no | Comma-separated fault modes that are not offered, for hosts that cannot run them (for example `cpu,memory`). `GET /api/demo/status` leaves them out of `fault_modes` and `POST /api/demo/faults` answers HTTP 422 for them. Used by the single-container image. | backend |

### Security scanner

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `SECURITY_RULES_DIR` | `<repository>/security-rules` | set by the image | Location of `policies.yaml` and the sample files. | backend, worker |
| `SCAN_WORKSPACE_DIR` | `<repository>/.runtime/scan-workspace` | set by the image | Directory whose YAML files may be scanned. | backend, worker |
| `SCAN_MAX_FILE_BYTES` | `262144` | no | Larger files are rejected by the scanner. | backend, worker |
| `REMEDIATION_WRITABLE_TARGETS` | `cloud-infrastructure.yaml` | yes | Comma-separated file names in the workspace that ACTION-002 may modify. The backend uses it to decide whether to offer the action; the worker enforces it again before writing. | backend, worker |

### Remediation worker

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `WORKER_ID` | `remediation-worker-1` | yes (worker) | Worker identity. | worker |
| `WORKER_POLL_INTERVAL_SECONDS` | `2.0` | no | Pause between queue polls when idle. | worker |
| `WORKER_HEARTBEAT_SECONDS` | `10.0` | no | Interval of the heartbeat written between jobs. | worker |
| `ACTION_TIMEOUT_SECONDS` | `30.0` | yes | Execution timeout of one action. | worker; displayed by the backend |
| `VERIFY_TIMEOUT_SECONDS` | `150.0` | yes | Upper bound for verifying ACTION-001. | worker; displayed by the backend |
| `REMEDIATION_MAX_ATTEMPTS` | `3` | yes | Attempts allowed per request; stored on the request when it is created. | backend |

The Settings page shows the backend's values of the two timeouts. Compose passes them from `.env`
to both the backend and the worker, so a value set there applies to both services.

### VigilAI

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `AI_PROVIDER` | `gemini` | yes (backend) | `gemini` or `none`. | backend |
| `GEMINI_API_KEY` | empty | yes (backend) | API key. | backend |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | yes (backend) | Model name. | backend |
| `AI_TIMEOUT_SECONDS` | `20.0` | yes (backend) | Timeout of one provider call. | backend |
| `AI_MAX_OUTPUT_TOKENS` | `800` | no | Output limit requested from the model. | backend |
| `AI_MAX_INPUT_CHARS` | `1000` | no | Maximum length of a question. Longer messages are rejected with HTTP 422; the chat box enforces the same limit. | backend |
| `AI_MAX_HISTORY_TURNS` | `6` | no | Earlier conversation turns used as context. | backend |
| `AI_RATE_LIMIT_PER_MINUTE` | `10` | yes (backend) | Per-user message limit. | backend |
| `AI_DAILY_REQUEST_LIMIT` | `400` | yes (backend) | Daily provider-call cap; `0` disables it. | backend |
| `KNOWLEDGE_BASE_DIR` | `<repository>/knowledge_base` | set by the image | Markdown files VigilAI retrieves from. | backend |

### Logging

| Setting | Default in code | Passed by Compose | Purpose | Used by |
|---|---|---|---|---|
| `LOG_LEVEL` | `INFO` | yes | Log level. | backend, worker |
| `LOG_FORMAT` | `json` | yes | `json` or `text`. | backend, worker |

## Other variables

| Variable | Default | Where | Purpose |
|---|---|---|---|
| `LOAD_GENERATOR_ENABLED` | `true` | `test-app/app.py` | Turns the demo application's synthetic load generator on or off. Not set by Compose. |
| `LOAD_INTERVAL_SECONDS` | `0.5` | `test-app/app.py` | Pause between synthetic requests. Not set by Compose. |
| `HOST` | `0.0.0.0` | `test-app/app.py` | Address the demo application binds to. Not set by Compose; the single-container image sets `127.0.0.1`. |
| `DEMO_DISABLED_FAULTS` | empty | `test-app/app.py` | The demo application honours the same variable as the backend: its `/internal/fault` endpoint answers HTTP 422 for a listed mode. Not set by Compose. |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` | `frontend/vite.config.js` | Where `npm run dev` proxies `/api`. |
| `VITE_API_URL` | empty (same origin) | `frontend/src/api/client.js` | Base URL of the API, fixed at build time. If you point it at another origin you must also set `CORS_ORIGINS`. |
| `TEST_DATABASE_URL` | unset (temporary SQLite file) | `backend/tests/conftest.py` | Runs the backend tests against PostgreSQL. All tables in that database are dropped by the suite. |
| `BASE_URL` | `http://localhost:8080` | `scripts/verify_stack.sh` | Address checked by the script. It reads `VIGILOPS_HTTP_PORT` from the shell environment, not from `.env`. |
| `CONFIRM` | unset | `scripts/restore_db.sh` | `CONFIRM=yes` skips the interactive confirmation. |

## Changing a setting that Compose does not pass through

Settings marked "yes" above that `compose.yaml` fills from `.env` are changed there, followed by
`docker compose up -d`. That includes the ones `.env.example` lists commented out under "Advanced
tuning": `ALERT_REPEAT_INTERVAL_SECONDS`, `REMEDIATION_WRITABLE_TARGETS`,
`REMEDIATION_MAX_ATTEMPTS`, `ACTION_TIMEOUT_SECONDS`, `VERIFY_TIMEOUT_SECONDS`,
`AI_TIMEOUT_SECONDS`, `LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS` and
`FORWARDED_ALLOW_IPS`. (`PROMETHEUS_URL`, `ALERTMANAGER_URL`, `DEMO_APP_URL`, `PROCESS_ROLE` and
`WORKER_ID` are fixed values in `compose.yaml`, and `DATABASE_URL` is built from the `POSTGRES_*`
variables.)

Settings marked "no" above (for example `AI_MAX_OUTPUT_TOKENS`, `SCAN_MAX_FILE_BYTES` or
`WORKER_POLL_INTERVAL_SECONDS`) must be added to the service's environment. Editing `compose.yaml` works;
a separate override file keeps your change apart from the repository's files. Docker Compose merges
a file named `compose.override.yaml` automatically when you run `docker compose` without `-f`:

```yaml
# compose.override.yaml (not part of the repository)
services:
  backend:
    environment:
      AI_MAX_OUTPUT_TOKENS: "1000"
      SCAN_MAX_FILE_BYTES: "524288"
  worker:
    environment:
      SCAN_MAX_FILE_BYTES: "524288"
```

Then run `docker compose up -d`. With the production overlay, add the file explicitly:
`docker compose -f compose.yaml -f compose.prod.yaml -f compose.override.yaml up -d`.

This mechanism is standard Docker Compose behaviour. An override file is not shipped with the project
and is not covered by its verification; do not put secrets in it if you commit it.

## Runtime settings

Three settings are stored in the database and can be changed by an Administrator while the platform
is running, under Settings, tab Platform, section "Runtime settings". Operators see them read-only.
A change takes effect immediately and is recorded in the audit trail as `SETTINGS_UPDATED` with the
previous and the new value. They are defined in `backend/app/services/settings_service.py`.

| Key | Label in the interface | Type | Default | Range | Effect |
|---|---|---|---|---|---|
| `remediation.allow_self_approval` | Allow self-approval of remediation | boolean | `false` | | When off, an Administrator cannot approve a remediation request they submitted; a second Administrator must review it. |
| `incidents.reopen_window_minutes` | Incident reopen window (minutes) | integer | `10` | 0 to 1440 | If the same alert fires again within this many minutes after an incident was resolved, that incident is reopened instead of a new one being created. `0` turns reopening off. Closed incidents are never reopened automatically. |
| `assistant.enabled` | VigilAI assistant enabled | boolean | `true` | | Turns the assistant off for all users. |

Through the API: `PUT /api/settings/{key}` with a JSON body such as `{"value": true}`
(Administrator only). Unknown keys return HTTP 404, values of the wrong type or outside the range
HTTP 422.

## How secrets are handled

- **No secret has a default in source code.** `SECRET_KEY`, `DATABASE_URL` and `ALERT_WEBHOOK_TOKEN`
  must be supplied. The API process stops at start if `SECRET_KEY` is shorter than 32 characters or
  `ALERT_WEBHOOK_TOKEN` shorter than 16.
- **`.env.example` holds public placeholders** so a local stack starts without preparation.
  `python scripts/generate_env.py` writes a `.env` in which `POSTGRES_PASSWORD`, `SECRET_KEY`,
  `ALERT_WEBHOOK_TOKEN`, `DEMO_APP_CONTROL_TOKEN`, `DEMO_APP_RECOVERY_TOKEN` and both bootstrap
  passwords are random. It prints only the file path.
- **Production mode refuses placeholders.** With `ENVIRONMENT=production` the process stops if
  `SECRET_KEY`, `ALERT_WEBHOOK_TOKEN`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_OPERATOR_PASSWORD`,
  `DEMO_APP_RECOVERY_TOKEN`, `DEMO_APP_CONTROL_TOKEN` or the password inside `DATABASE_URL` contains
  one of the markers `change-me`, `changeme`, `replace-me`, `example` or `dev-only`. The error
  message names the offending variables. The check looks for these markers only; it does not judge
  the strength of other values, with one exception: in production mode the API also refuses to
  start if a bootstrap password does not meet the password policy.
- **Each service gets only what it needs.** The worker does not receive `SECRET_KEY`,
  `ALERT_WEBHOOK_TOKEN`, `GEMINI_API_KEY` or the bootstrap passwords. Only the worker and the demo
  application hold `DEMO_APP_RECOVERY_TOKEN`. The web and Prometheus containers receive no secrets;
  PostgreSQL receives only its own credentials.
- **Alertmanager reads the webhook token from a file.** Compose provides `ALERT_WEBHOOK_TOKEN` as the
  Docker secret `alert_webhook_token`, mounted at `/run/secrets/alert_webhook_token`. It is not
  written in `monitoring/alertmanager.yml`.
- **The Gemini key stays on the backend.** The browser only talks to the backend; the settings API
  reports whether a key is configured, never its value.
- **Passwords** are stored as bcrypt hashes. Passwords longer than 72 bytes are rejected rather than
  truncated.
- **The settings API never returns secret values.** It does report whether placeholder values are in
  use for `SECRET_KEY` or `ALERT_WEBHOOK_TOKEN`, which the Settings page shows as a warning.
- **Logs are redacted.** A log filter masks strings that look like Google API keys, JWTs, bearer
  tokens and `password=`, `secret=`, `token=` or `api_key=` assignments.
- **Audit metadata is redacted.** Values whose key contains password, passphrase, secret, token,
  API key, authorization or credential are stored as `[REDACTED]`.
- **VigilAI output is filtered.** Before a reply is returned, the configured secret values are
  replaced with `[REDACTED]`, and requests for credentials are refused before any model call.

Rotating values:

| Value | How | Effect |
|---|---|---|
| `SECRET_KEY` | Edit `.env`, `docker compose up -d backend` | All users must sign in again. |
| `ALERT_WEBHOOK_TOKEN` | Edit `.env`, `docker compose up -d --force-recreate backend alertmanager` | Both sides must be recreated together, otherwise notifications are rejected with HTTP 401. |
| `DEMO_APP_CONTROL_TOKEN`, `DEMO_APP_RECOVERY_TOKEN` | Edit `.env`, `docker compose up -d backend worker test-app` | None for users. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Edit `.env`, `docker compose up -d backend` | VigilAI mode changes after the restart. |
| `POSTGRES_PASSWORD` | Not applied to an existing volume by editing `.env`. Change the password inside PostgreSQL first, or reset the volumes. | See [troubleshooting](troubleshooting.md#containers). |
| User passwords | Settings, tab Profile, or an Administrator under Settings, tab Users | That user's sessions are signed out. |

## Monitoring configuration files

Three version-controlled files in `monitoring/` are mounted read-only into the containers.

### prometheus.yml

| Setting | Value |
|---|---|
| `scrape_interval`, `evaluation_interval` | 5 seconds |
| `scrape_timeout` | 4 seconds |
| Rule file | `/etc/prometheus/alert_rules.yml` |
| Alertmanager | `alertmanager:9093` |

Scrape jobs:

| Job | Target | Extra label | Shown in VigilOps as |
|---|---|---|---|
| `demo-app` | `test-app:8001` | `resource: demo-app` | Monitored resource and scrape target |
| `vigilops-backend` | `backend:8000` | `resource: vigilops-backend` | Monitored resource and scrape target |
| `prometheus` | `localhost:9090` | | Scrape target |
| `alertmanager` | `alertmanager:9093` | | Scrape target |

Prometheus keeps seven days of data (`--storage.tsdb.retention.time=7d` in `compose.yaml`).

### alert_rules.yml

| Alert | Condition | For | Severity label |
|---|---|---|---|
| `ApplicationUnavailable` | `up{job="demo-app"} == 0` | 15s | critical |
| `HighHttp5xxErrorRate` | More than 20% of responses are 5xx over one minute | 30s | high |
| `HighApiLatency` | p95 request duration above 1 second over one minute | 30s | medium |
| `HighCpuUsage` | Process CPU above 0.80 of one core over one minute | 30s | high |
| `HighMemoryUsage` | Resident memory above 250 MiB | 30s | high |

Each rule also carries the labels `resource: demo-app` and `action_code: ACTION-001`. How the backend
uses alert labels:

- `severity` becomes the incident severity: `critical` to CRITICAL, `high` or `error` to HIGH,
  `warning` or `medium` to MEDIUM, `low` or `info` to LOW. Anything else becomes MEDIUM.
- `resource`, then `job`, is matched against the registered monitored resources to set the
  incident's affected resource.
- `action_code` is informational. Whether ACTION-001 is offered is decided by the backend: only for
  active incidents on the demo application.
- The `summary` annotation becomes the incident title and `description` its description.

### alertmanager.yml

| Setting | Value | Meaning |
|---|---|---|
| `group_by` | `alertname`, `instance` | One notification group per alert and instance |
| `group_wait` | 5s | Delay before the first notification of a new group |
| `group_interval` | 15s | Delay before notifying about changes such as resolution |
| `repeat_interval` | 2m | Repeat for alerts that are still firing |
| `resolve_timeout` | 5m | Applies only to alerts received without an end time |
| Receiver | `http://backend:8000/api/alerts/webhook`, `send_resolved: true`, `max_alerts: 50` | Bearer token read from `/run/secrets/alert_webhook_token` |

### Editing these files

After a change, validate and restart:

```bash
docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
docker compose exec prometheus promtool check rules /etc/prometheus/alert_rules.yml
docker compose exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
docker compose restart prometheus alertmanager
```

In Git Bash prefix the first three commands with `MSYS_NO_PATHCONV=1` (see
[troubleshooting](troubleshooting.md#windows-specific-issues)).

Values that are coupled to code and do not follow a change automatically:

| If you change | Also consider |
|---|---|
| `scrape_interval` | `PROMETHEUS_SCRAPE_INTERVAL_SECONDS`, used for the "Stale" marker |
| `repeat_interval` | The backend setting `ALERT_REPEAT_INTERVAL_SECONDS` (default 120), used for the "Signal stale" badge. Compose passes it through from `.env`, so set it there. |
| Job names `demo-app`, `vigilops-backend` | `DEMO_APP_JOB`, `BACKEND_JOB`, and the monitored resources already stored in the database |
| Alert thresholds | The threshold lines on the Monitoring and Overview charts are fixed in the frontend (20%, 1 s, 80%, 250 MiB) |
| Alert names | The built-in runbooks in `backend/app/services/recommendations.py` are keyed by alert name; an unknown alert gets a generic runbook |

Adding a scrape job makes its target appear in the "Scrape targets" table. It does not create a new
monitored resource with metric cards: only the demo application and the backend are registered, and
there is no interface for registering more. An alert rule for any target still opens an incident when
it fires, with the generic runbook and without an automated action.

## The scan workspace

The scanner only reads files that sit directly in the scan workspace, a named Docker volume
(`scan_workspace`, mounted at `/data/scan-workspace`).

- The `backend` container mounts it read-only. It can scan and display files but cannot change them.
- The `worker` container mounts it read-write. It is the only component that modifies files
  (ACTION-002, and restoring the sample configuration).

### What is in it

- In development mode with demonstration controls enabled, the worker copies
  `security-rules/samples/baseline/cloud-infrastructure.yaml` into the workspace when it starts and
  finds no YAML file there. "Reset sample configuration" (Settings, tab Demo controls) overwrites
  that file with the baseline again and leaves other files untouched.
- In production mode (unless the hosted-demonstration opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION`
  is set), or with demonstration controls disabled, the workspace starts empty.

### Adding, listing and removing files

Copy through the worker container, because its mount is writable:

```bash
docker compose cp my-config.yaml worker:/data/scan-workspace/
```

Then choose "Run scan" on the Security Findings page. The tab "Configuration files" lists the
authorised files with size, modification time and whether automated remediation is allowed.

```bash
docker compose exec worker ls -l /data/scan-workspace
docker compose exec worker rm /data/scan-workspace/my-config.yaml
```

In Git Bash prefix these commands with `MSYS_NO_PATHCONV=1`.

To try the fixtures that ship with the project:

```bash
docker compose cp security-rules/samples/insecure/sec-004-open-ingress.yaml worker:/data/scan-workspace/
```

### Rules for files

| Rule | Detail |
|---|---|
| File name | Starts with a letter or digit, then letters, digits, `.`, `_` or `-`, and ends in `.yaml` or `.yml`. Other files are ignored. |
| Location | Directly in the workspace. Subdirectories are not scanned; a link that resolves outside the workspace is ignored. |
| Size | At most `SCAN_MAX_FILE_BYTES` (262144 bytes by default). |
| Encoding | UTF-8 text. |
| YAML features | Parsed with the safe loader. Anchors and aliases are rejected. |

A file that breaks the schema fails as a whole: it is reported in the scan result and its existing
findings are left unchanged. A scan is recorded as FAILED only when no file could be scanned.

### Behaviour worth knowing

- **Finding identity.** A finding is identified by file name, rule, resource type and resource name.
  Repeated scans update the same finding. Renaming a resource or a file produces new findings.
- **Removed files.** A scan only updates findings of files it scanned. If you delete a file from the
  workspace, its findings stay in their last state; a deleted file is not treated as a verified fix.
  A scan of the whole workspace adds a note to its result saying how many unresolved findings refer
  to files that are no longer present.
- **Automated remediation is limited to allowlisted files.** By default only
  `cloud-infrastructure.yaml` is on the allowlist (`REMEDIATION_WRITABLE_TARGETS`). For other files
  the SEC-001 finding shows "This configuration file is not on the remediation allowlist." and must
  be fixed manually.
- **ACTION-002 rewrites the file.** The worker parses the YAML, changes the bucket, and writes the
  whole document back in block style. The comment block at the top of the file is kept; comments
  inside the document and the original quoting or flow-style formatting are not.
- **The demonstration script expects a clean state.** `scripts/run_e2e_demos.py` checks that exactly
  the five findings of the sample configuration exist. Findings from additional files make that
  check fail.

## The vigilops/v1 schema

A configuration file is one YAML document that describes sample cloud resources. It is not connected
to a cloud account.

```yaml
schema_version: vigilops/v1      # required, exactly this value
environment: staging             # optional, not evaluated
description: Any free text       # optional, not evaluated
resources:                       # required list, at most 500 entries
  - type: storage_bucket         # required, one of the six types below
    name: customer-records       # required, non-empty, at most 120 characters
    # type-specific fields follow
```

General rules:

- The top level must be a mapping with `schema_version: vigilops/v1` and a `resources` list.
- Every resource is a mapping with a `type` and a `name`. The pair of type and name must be unique
  within a file.
- Fields that the rules do not evaluate (for example `image`, `engine`, `size_gb`) are allowed and
  ignored.
- The rules test for the YAML boolean `true` and for integer ports. A quoted `"true"` is a string,
  not a boolean: a bucket with `public_access: "true"` is not reported by SEC-001, while
  `encryption.enabled: "true"` is reported by SEC-002 as not enabled. A quoted `port` is not
  evaluated. Write booleans and ports without quotes.

| Resource type | Evaluated by | Evaluated fields |
|---|---|---|
| `storage_bucket` | SEC-001, SEC-002 | `public_access`, `acl`, `encryption` |
| `disk_volume` | SEC-002 | `encryption` |
| `database` | SEC-002 | `encryption` |
| `iam_policy` | SEC-003 | `statements[].effect`, `actions`, `resources` |
| `security_group` | SEC-004 | `ingress[].cidr`, `port`, `port_range`, `protocol` |
| `container` | SEC-005 | `privileged`, `security_context.privileged` |

### storage_bucket

```yaml
- type: storage_bucket
  name: application-logs
  public_access: false        # SEC-001 if true
  acl: private                # SEC-001 if public-read or public-read-write
  encryption:                 # SEC-002 if this block is missing
    enabled: true             # SEC-002 if not true
    algorithm: AES-256        # SEC-002 if empty or NONE
```

SEC-001 (HIGH) is the only rule with an automated action, ACTION-002.

### disk_volume

```yaml
- type: disk_volume
  name: data-volume
  size_gb: 100                # not evaluated
  encryption:
    enabled: true
    algorithm: AES-256
```

A volume without an `encryption` block is reported by SEC-002 (MEDIUM).

### database

```yaml
- type: database
  name: orders-db
  engine: postgres            # not evaluated
  encryption:
    enabled: true
    algorithm: aws:kms        # any value other than empty or NONE is accepted
```

### iam_policy

```yaml
- type: iam_policy
  name: report-reader-role
  statements:
    - effect: Allow           # a missing effect is treated as Allow
      actions:
        - s3:GetObject        # SEC-003 if an action is "*" or ends in ":*", for example "s3:*"
        - s3:ListBucket
      resources:
        - arn:aws:s3:::application-logs      # SEC-003 if a resource is exactly "*"
        - arn:aws:s3:::application-logs/*    # a wildcard inside an identifier is not flagged
```

SEC-003 (CRITICAL) evaluates only statements whose effect is Allow. `Deny` statements with wildcards
are not reported. One finding is created per policy; each offending statement is listed as evidence.

### security_group

```yaml
- type: security_group
  name: web-sg
  ingress:
    - protocol: tcp
      port: 443               # 80 and 443 open to the internet are not flagged
      cidr: 0.0.0.0/0
    - protocol: tcp
      port: 22                # SEC-004 if the cidr were 0.0.0.0/0 or ::/0
      cidr: 10.0.0.0/8
    - protocol: tcp
      port_range: 8000-8100   # a range is checked for every sensitive port it contains
      cidr: 0.0.0.0/0
```

SEC-004 (HIGH) reports an ingress rule whose `cidr` is `0.0.0.0/0` or `::/0` and whose port or port
range includes one of: 22 SSH, 23 Telnet, 3389 RDP, 1433 MSSQL, 3306 MySQL, 5432 PostgreSQL,
6379 Redis, 9200 Elasticsearch, 27017 MongoDB. A `protocol` of `all`, `any` or `-1` counts as every
port. A rule without a readable `port` or `port_range` is skipped.

### container

```yaml
- type: container
  name: web-frontend
  image: registry.local/web-frontend:2.1.0    # not evaluated
  privileged: false                           # SEC-005 if true
  security_context:
    privileged: false                         # SEC-005 if true
    run_as_non_root: true                     # not evaluated
```

SEC-005 (HIGH).

### Sample files in the repository

| Path | Purpose |
|---|---|
| `security-rules/samples/baseline/cloud-infrastructure.yaml` | The demonstration baseline. It violates each of SEC-001 to SEC-005 once and also contains compliant resources. |
| `security-rules/samples/insecure/sec-00N-*.yaml` | One fixture per rule, written to trigger only that rule. |
| `security-rules/samples/secure/sec-00N-*.yaml` | The compliant counterpart of each fixture, written to produce no findings. |

Rule names, severities, descriptions, impact and recommendations are stored in
`security-rules/policies.yaml`. The detection logic is in
`backend/app/security_scanner/rules.py`; the scanner refuses to load if the two files do not describe
the same five rule identifiers.
