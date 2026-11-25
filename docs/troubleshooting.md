# Troubleshooting

Symptoms, causes and fixes, grouped by area. Messages in quotation marks are the texts the
application or Docker Compose actually prints.

Related documents: [setup](setup.md), [configuration](configuration.md), [deployment](deployment.md),
[user guide](user-guide.md).

## Contents

1. [Where to look first](#where-to-look-first)
2. [Installation](#installation)
3. [Containers](#containers)
4. [Login](#login)
5. [Monitoring](#monitoring)
6. [Alerts and incidents](#alerts-and-incidents)
7. [Scanner](#scanner)
8. [Remediation and worker](#remediation-and-worker)
9. [VigilAI](#vigilai)
10. [Scripts and tests](#scripts-and-tests)
11. [Windows-specific issues](#windows-specific-issues)

## Where to look first

```bash
docker compose ps                         # state and health of every service
docker compose ps -a                      # also shows the one-shot workspace-init container
docker compose logs --tail=100 backend    # or worker, web, prometheus, alertmanager, test-app, postgres
docker compose logs -f backend            # follow
```

- Run these from the repository root. With the production overlay add
  `-f compose.yaml -f compose.prod.yaml` or export `COMPOSE_FILE` (see [deployment](deployment.md#start)).
- **Overview**, card "Platform health", shows at a glance whether the backend, the database,
  Prometheus, Alertmanager, the scrape targets and the worker are healthy.
- **Settings**, tab Platform, shows the effective mode, whether demonstration controls are enabled
  and how VigilAI is configured.
- **Audit Logs** records refused actions (outcome Denied) and failures with their reason.
- Error responses of the API contain a `request_id`. The same value appears in the backend's JSON
  log lines, so you can search the log for it.
- Changes to `.env` are applied by `docker compose up -d`, which recreates the affected containers.
  `docker compose restart` does not re-read `.env`.

## Installation

### `docker compose up` stops with "set POSTGRES_PASSWORD in .env"

**Cause.** There is no `.env` file, or a required variable is empty. Compose requires
`POSTGRES_PASSWORD`, `SECRET_KEY` and `ALERT_WEBHOOK_TOKEN`; the message names the missing one.

**Fix.** Create the file from the template (`cp .env.example .env`, in PowerShell
`Copy-Item .env.example .env`) or run `python scripts/generate_env.py`, then start again.

### "docker: 'compose' is not a docker command"

**Cause.** The Compose plugin is not installed, or only the old standalone `docker-compose` exists.

**Fix.** Install Docker Desktop (Windows) or the `docker-compose-plugin` package (Ubuntu). Check with
`docker compose version`.

### The image build fails while downloading packages

**Cause.** No or restricted internet access during `pip install` or `npm ci`, or a temporary registry
problem.

**Fix.** Check the connection and any proxy settings of Docker, then run
`docker compose up --build -d` again. Completed layers are cached.

### The production overlay is rejected with an error about `!reset` or `!override`

**Cause.** The installed Docker Compose is too old for these merge tags.

**Fix.** Update Docker Compose. According to the Docker documentation `!override` needs Compose
2.24.4 or later. The local stack does not use these tags.

### "set VIGILOPS_DOMAIN in .env for production"

**Cause.** `compose.prod.yaml` is in use and `VIGILOPS_DOMAIN` is not set.

**Fix.** Set `VIGILOPS_DOMAIN` in `.env` to the DNS name of the server.

### `generate_env.py` says ".env already exists; use --force to overwrite it."

**Cause.** The script never overwrites an existing file by default.

**Fix.** Add `--force` only if you really want new secrets. For an installation that already has
data, new secrets include a new database password, which does not match the existing database
volume; see [the backend cannot connect to the database](#the-backend-cannot-connect-to-the-database).

## Containers

### `backend` keeps restarting or never becomes healthy

**Cause.** A configuration check failed at start. `docker compose logs backend` shows one of:

| Log message | Meaning |
|---|---|
| "SECRET_KEY must be set and at least 32 characters long" | The signing key is missing or too short |
| "ALERT_WEBHOOK_TOKEN must be set and at least 16 characters long" | The webhook token is missing or too short |
| "Refusing to start in production with placeholder values for: ..." | Production mode with values from `.env.example`; the variables are named |
| "SQLite is not supported in production; use PostgreSQL" | Production mode with a SQLite URL |
| "BOOTSTRAP_ADMIN_PASSWORD does not meet the password policy: ..." (or `BOOTSTRAP_OPERATOR_PASSWORD`) | Production mode with a bootstrap password that fails the password policy |
| "ENVIRONMENT must be development, production or test" | Invalid `ENVIRONMENT` |
| "AI_PROVIDER must be 'gemini' or 'none'" | Invalid `AI_PROVIDER` |

**Fix.** Correct the value in `.env` and run `docker compose up -d`.

### The backend cannot connect to the database

**Symptom.** The backend log shows a connection error such as `password authentication failed`, and
the container restarts while `alembic upgrade head` fails.

**Cause.** `POSTGRES_PASSWORD` in `.env` was changed after the `pgdata` volume was created.
PostgreSQL applies the variable only when it initialises an empty volume. A password containing
characters other than letters, digits, `-` and `_` can also break the connection URL.

**Fix.** One of:

1. Put the previous password back into `.env` and run `docker compose up -d`.
2. Change the password inside PostgreSQL to the new value, then recreate the services:

   ```bash
   docker compose exec postgres psql -U vigilops -d vigilops -c "ALTER USER vigilops WITH PASSWORD 'the-new-password';"
   docker compose up -d
   ```

   Replace `vigilops` with your `POSTGRES_USER` and `POSTGRES_DB` if you changed them.
3. If the data is not needed, start fresh: `docker compose down -v`, then
   `docker compose up --build -d`. This deletes all data.

### `worker` or `web` does not start

**Cause.** Both depend on a healthy `backend`. If the backend does not become healthy, Compose does
not start them and reports that a dependency failed to start.

**Fix.** Solve the backend problem first. A worker that started before the migrations finished logs
"waiting for database schema" and continues by itself.

### `workspace-init` is shown as "Exited (0)"

**Cause.** None; this is expected. It is a one-shot container that sets the ownership of the scan
workspace volume.

**Fix.** Nothing to do. A non-zero exit code is a problem: `docker compose logs workspace-init`.

### "port is already allocated" or "address already in use"

**Cause.** Another program uses a port VigilOps wants to publish.

**Fix.** Change the port in `.env` and run `docker compose up -d`:

| Port | Variable |
|---|---|
| 8080 (web application) | `VIGILOPS_HTTP_PORT` |
| 8000 (backend, API docs) | `BACKEND_DEV_PORT` |
| 9090 (Prometheus) | `PROMETHEUS_DEV_PORT` |
| 9093 (Alertmanager) | `ALERTMANAGER_DEV_PORT` |

Remember the new address when opening the application, and pass it to `verify_stack.sh` with
`BASE_URL`.

### The web application is not reachable from another device

**Cause.** By design. The web port is bound to `127.0.0.1` unless configured otherwise.

**Fix.** Set `VIGILOPS_BIND_ADDRESS=0.0.0.0` in `.env`, run `docker compose up -d`, and allow the
port in the host firewall. The local stack is plain HTTP; do this only on a trusted network. For
anything else use the production overlay.

### `http://localhost:8000/docs` returns "Not Found"

**Cause.** API documentation is served in development mode only. In production mode it is disabled,
and the production overlay does not publish port 8000 at all.

**Fix.** Use the local stack in development mode, or read [api.md](api.md).

### A change in `.env`, `monitoring/*.yml` or the code has no effect

**Cause and fix.**

| What changed | Apply it with |
|---|---|
| `.env` | `docker compose up -d` |
| `monitoring/prometheus.yml`, `alert_rules.yml`, `alertmanager.yml` | `docker compose restart prometheus alertmanager` |
| Backend, worker, frontend, demo application code; `knowledge_base/`; `security-rules/` | `docker compose up --build -d` |
| A backend setting that `compose.yaml` does not pass through | An override file; see [configuration](configuration.md#changing-a-setting-that-compose-does-not-pass-through) |

## Login

### The sign-in page shows "The server is starting. ..." or "The server is not answering."

**Cause.** The sign-in page asks `/api/health` whether the backend is answering, and it is not
answering yet: it is starting, restarting, or runs on a hosting plan that sleeps when idle. While
the page waits, the Sign in button reads "Waiting for the server…" and is disabled. After three
minutes without an answer the page shows "The server is not answering." with a "Check again" button.

**Fix.** Wait; the page continues by itself as soon as the backend answers. If it says the server is
not answering, check that the backend is running (`docker compose ps backend` for the Compose stack,
the service page of the hosting provider for a hosted instance; see
[deployment-render-vercel.md](deployment-render-vercel.md#troubleshooting)) and choose "Check again".

### The store shows "Starting the demonstration server" or "OrbitCrate is not answering yet"

**Cause.** Only on the free-hosting deployment. The store runs on the server that sleeps when idle. Its
address is answered by a start page on the static host, which asks the store every three seconds
whether it answers; "OrbitCrate is not answering yet" is the same wait on the server's own address,
in the few seconds in which the API is up and the store is not.

**Fix.** Wait; both pages open the store by themselves, usually within a minute. After four minutes
the start page shows "The store is not answering" with "Try again": then check the service page of the
hosting provider. To avoid the wait, see
[Keeping the service awake](deployment-render-vercel.md#keeping-the-service-awake).

### "Incorrect e-mail or password."

**Cause.** The same message is shown for a wrong password, an unknown e-mail and a deactivated
account. Common reasons with the bootstrap accounts:

- The password was changed in the application; the value in `.env` is then outdated.
- The bootstrap password in `.env` was edited after the first start. Existing accounts are never
  changed by the bootstrap step.
- The bootstrap password did not meet the policy (10 or more characters, upper and lower case, a
  digit), so the account was not created. The backend log contains
  "bootstrap account skipped: weak password". This applies outside production mode; in production
  mode the API refuses to start instead (see
  [`backend` keeps restarting](#backend-keeps-restarting-or-never-becomes-healthy)).

**Fix.** Use the password that is actually set. An Administrator can reset any password under
Settings, tab Users. If no Administrator can sign in, see the next entry but one.

### "Too many sign-in attempts. Try again in N seconds."

**Cause.** Five failed attempts for the same e-mail from the same address within five minutes, 20
failed attempts for the same e-mail from any address within five minutes, or more than 30 sign-in
requests from one address within a minute. The limit per e-mail locks sign-in for that e-mail from
every address, so it can also be caused by someone else who knows the e-mail and fails 20 times.

**Fix.** Wait for the stated time. The limiter is held in the backend's memory, so
`docker compose restart backend` also clears it.

### No Administrator can sign in any more

**Cause.** The only Administrator password is lost. There is no password-reset e-mail and no
command-line reset.

**Fix.** Let the bootstrap step create a new Administrator: set `BOOTSTRAP_ADMIN_EMAIL` in `.env` to
an address that has no account yet, set a valid `BOOTSTRAP_ADMIN_PASSWORD`, and run
`docker compose up -d backend`. Sign in with the new account and repair the old one under Settings,
tab Users.

### "Your session has ended. Please sign in again."

**Cause.** The access token is no longer accepted: it expired (60 minutes by default), you signed
out, your password or role was changed, your account was deactivated, or `SECRET_KEY` changed.
Closing the browser tab also ends the session because the token is kept in `sessionStorage`.

**Fix.** Sign in again. Increase `ACCESS_TOKEN_EXPIRE_MINUTES` if sessions are too short for your
use.

### "Cannot reach the VigilOps API. Check that the backend is running."

**Cause.** The page was loaded but API calls fail: the backend container is stopped or restarting, or
the Vite dev server cannot reach `127.0.0.1:8000`.

**Fix.** `docker compose ps backend` and `docker compose logs --tail=50 backend`. With `npm run dev`,
check that the Compose stack is running and that `VITE_PROXY_TARGET` matches `BACKEND_DEV_PORT`.

### "Too many incorrect attempts. Try again in N seconds." when changing the password

**Cause.** Five wrong entries of the current password within five minutes.

**Fix.** Wait, or ask an Administrator to reset the password.

## Monitoring

### Metric cards show "Unavailable"

**Cause.** Prometheus returned no value. The card shows the reason:

| Reason shown | Meaning |
|---|---|
| "no data" | No samples yet. Rates and the latency percentile are computed over one minute, so this is normal for a short time after a start or after a target comes back. |
| "timeout", "unreachable (...)", "HTTP ..." | Prometheus itself cannot be queried |

When the target is down, request metrics stop arriving and become unavailable as well.

**Fix.** Wait a minute after a start. Otherwise check the status line at the top of the Monitoring
page and `docker compose ps prometheus`. VigilOps never substitutes a number for a missing value.

### "Prometheus cannot be reached"

**Cause.** The `prometheus` container is stopped, still starting, or its configuration is invalid.

**Fix.** `docker compose logs --tail=50 prometheus`. If you edited the configuration, validate it:

```bash
docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

### `demo-app` is shown as Down

**Cause.** Prometheus cannot scrape it. The scrape error in the "Scrape targets" table tells which
case applies:

| Scrape error | Meaning | What to do |
|---|---|---|
| "server returned HTTP status 503" | The process runs but its service component is in a failed state, for example because the `outage` fault was injected | Recover through the incident with ACTION-001, or use "Clear fault" under Settings, tab Demo controls |
| "connection refused" or a name-resolution error | The container is not running | `docker compose up -d test-app`. ACTION-001 cannot start a container. |

### A scrape target carries the badge "Stale"

**Cause.** Its last scrape is older than four scrape intervals (20 seconds by default). Prometheus is
overloaded, was just restarted, or `PROMETHEUS_SCRAPE_INTERVAL_SECONDS` does not match
`scrape_interval` in `monitoring/prometheus.yml`.

**Fix.** Check Prometheus and keep the two values equal.

### Charts show gaps

**Cause.** No samples exist for that period, typically because the target was down. Gaps are drawn
deliberately instead of connecting the line.

**Fix.** None needed.

### The Prometheus or Alertmanager UI does not open

**Cause.** The ports are published on `127.0.0.1` only, so they open only in a browser on the same
machine. In the production overlay they are not published.

**Fix.** Open <http://localhost:9090> or <http://localhost:9093> on the host itself.

## Alerts and incidents

### No incident appears after a fault

**Cause and fix.** Work through the chain:

1. **Is the alert active?** Monitoring, table "Alert rules currently active". An alert is Pending
   until its condition has held for the rule's duration (15 seconds for the outage, 30 seconds for
   the others) and only then Firing. Alertmanager waits a further 5 seconds before the first
   notification.
2. **Is Alertmanager available?** Status line on the Monitoring page; `docker compose ps alertmanager`.
3. **Was the notification accepted?** `docker compose logs --tail=50 alertmanager` shows failed
   webhook deliveries. If the backend log contains "alert webhook rejected: invalid token", the
   token Alertmanager holds differs from the backend's `ALERT_WEBHOOK_TOKEN`. Recreate both:

   ```bash
   docker compose up -d --force-recreate backend alertmanager
   ```

4. **Is there already an incident?** A repeated notification for an alert that already has an active
   incident only raises that incident's notification count. An alert that fires again within the
   reopen window reopens the earlier incident instead of creating a new one.

### The incident is not marked "Simulated fault"

**Cause.** The badge is set only when the incident is created, and only if demonstration controls
are enabled and the demo application reported an active fault at that moment. If the fault was
cleared before the alert fired, or the incident already existed, it is not set.

**Fix.** None; the badge is informational.

### "Monitoring still reports this alert as firing. The incident can only be resolved once the condition has cleared."

**Cause.** You chose Resolve while Prometheus still reports the alert as firing.

**Fix.** Fix the underlying problem first (for the demo application: ACTION-001 or "Clear fault"),
then resolve. The "Administrator override" checkbox does not help here: it is honoured only when
Prometheus cannot be asked, never while Prometheus reports the alert as firing.

### "Recovery cannot be verified because Prometheus is unavailable"

**Cause.** The incident's alert is recorded as firing and Prometheus could not be asked.

**Fix.** Restore Prometheus, or have an Administrator resolve with the override and a documented
reason.

### "Resolution evidence is required"

**Cause.** The Resolve dialog needs a text of at least 10 characters describing how recovery was
verified. Reopening needs a reason of the same minimum length.

**Fix.** Enter the text.

### The Close or Reopen button is missing

**Cause.** Only Administrators may close or reopen incidents, and only a Resolved incident can be
closed or reopened. Closed is final.

**Fix.** Ask an Administrator.

### An incident was resolved or reopened without anyone doing it

**Cause.** Both are automatic behaviours.

- Resolved: Alertmanager reported that the alert cleared. The `cpu` and `memory` demo faults clear
  themselves after ten minutes, and "Clear fault" has the same effect.
- Reopened: the same alert fired again within the reopen window (10 minutes by default).

**Fix.** None needed. The reopen window is the runtime setting "Incident reopen window (minutes)".

### An incident shows "Signal stale"

**Cause.** The alert is recorded as firing, but no notification has arrived for more than seven
minutes with the default configuration. Alertmanager normally repeats every two minutes. Either the
monitoring pipeline is unhealthy, or `repeat_interval` in `monitoring/alertmanager.yml` was increased
without changing `ALERT_REPEAT_INTERVAL_SECONDS`.

**Fix.** Check Prometheus and Alertmanager on the Monitoring page and in their logs.

## Scanner

### "The scan workspace is empty" or a scan reports that no configuration files are present

**Cause.** The workspace volume contains no YAML file. This is the normal starting state in
production mode (without the hosted-demonstration opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION`) or
with demonstration controls disabled.

**Fix.** Copy files in, or in demo mode use "Reset sample configuration":

```bash
docker compose cp my-config.yaml worker:/data/scan-workspace/
```

### A file I copied is not listed under "Configuration files"

**Cause.** The name does not qualify. It must start with a letter or digit, contain only letters,
digits, `.`, `_` and `-`, end in `.yaml` or `.yml`, and sit directly in the workspace (not in a
subdirectory).

**Fix.** Rename or move the file.

### A scan reports a file as failed

**Cause.** The file is rejected as a whole. The message says why:

| Message contains | Meaning |
|---|---|
| "malformed YAML" | Syntax error; the line number is given |
| "file is not readable UTF-8 text" | Wrong encoding, or the file cannot be read |
| "top level must be a mapping" | The document is a list or a scalar instead of key-value pairs |
| "unsupported schema_version" | The file does not declare `schema_version: vigilops/v1` |
| "'resources' must be a list" | The `resources` key is missing or not a list |
| "type must be one of ..." | A resource has an unknown `type` |
| "name must be a non-empty string" | A resource has no usable `name` |
| "duplicate resource" | Two resources share type and name |
| "YAML anchors and aliases are not allowed" | The file uses `&` or `*` references |
| "file is larger than ... bytes" | Above `SCAN_MAX_FILE_BYTES` |
| "too many resources" | More than 500 resources |

**Fix.** Correct the file (see [configuration](configuration.md#the-vigilopsv1-schema)), copy it again
and rescan. Existing findings of a rejected file are left unchanged.

### I fixed the file but the finding is still Open

**Cause.** The scanner reads the copy inside the Docker volume, not the file on your disk. Or no scan
has run since the change.

**Fix.** Copy the corrected file into the workspace again and choose **Run scan**. A finding becomes
Resolved only through a scan.

### A scan notes findings that "refer to configuration files that are no longer in the scan workspace"

**Cause.** A file was removed from the workspace. Its findings are kept in their last state, because
deleting a file is not a verified fix.

**Fix.** Put a corrected version of the file back under the same name and rescan to resolve them, or
have an Administrator mark them as accepted risk with a justification.

### A misconfiguration is not detected

**Cause.** The rules compare exact values. A quoted `"true"` is a string, not a boolean, and a quoted
port is not a number. The scanner also covers only the five rules and six resource types of the
schema.

**Fix.** Write booleans and ports without quotes. See
[configuration](configuration.md#the-vigilopsv1-schema).

### Findings reappear after "Reset sample configuration"

**Cause.** Expected. The reset restores the insecure sample file and runs a scan, so its resolved
findings reopen.

**Fix.** None needed.

## Remediation and worker

### "Automated remediation is not available"

**Cause.** The panel gives the reason:

| Reason shown | Meaning |
|---|---|
| "No automated action exists for this resource; follow the manual steps." | The incident does not concern the demo application |
| "The incident is already RESOLVED." (or CLOSED) | ACTION-001 applies to active incidents only |
| "Automated correction is not implemented for SEC-00x; ..." | Only SEC-001 has an automated action |
| "This configuration file is not on the remediation allowlist." | ACTION-002 may only edit files named in `REMEDIATION_WRITABLE_TARGETS` (default: `cloud-infrastructure.yaml`) |
| "The finding is ...; only OPEN findings can be remediated." | The finding is resolved, accepted risk or already has a request |

**Fix.** Follow the manual steps shown, or add the file to the allowlist: set
`REMEDIATION_WRITABLE_TARGETS` in `.env` and run `docker compose up -d` (see
[configuration](configuration.md#security-scanner)).

### The "Request remediation" button is disabled

**Cause.** A request for this incident or finding is already in progress; the text next to the
button names it.

**Fix.** Open the existing request from the linked list.

### An Administrator has no Approve button

**Cause.** The Administrator submitted the request. Self-approval is off by default; the API answers
"You cannot approve a remediation request that you submitted yourself. Another Administrator must
review it."

**Fix.** Have another Administrator approve it. For a demonstration with a single Administrator,
submit the request as the Operator, or switch on the runtime setting "Allow self-approval of
remediation".

### "Request #N is ...; this operation requires ..."

**Cause.** The request is not in the status the operation needs, for example Execute before Approve,
or the page showed an outdated status.

**Fix.** Refresh the page and follow the order Approve, then Execute.

### A request stays Queued

**Cause.** The worker is not running or cannot reach the database. The Remediation page shows the
worker as Offline.

**Fix.** `docker compose ps worker`, `docker compose logs --tail=50 worker`, then
`docker compose up -d worker`. The worker picks up queued requests when it starts.

### A request is Failed

**Cause.** The request page shows the reason and the verification checks.

| Failure reason | Meaning | What to do |
|---|---|---|
| "The recovery endpoint could not be reached after 3 attempts." | The demo application container is stopped or unreachable | `docker compose up -d test-app`, then Retry |
| "The application rejected the recovery call (HTTP 401)." | Worker and demo application hold different `DEMO_APP_RECOVERY_TOKEN` values | `docker compose up -d worker test-app`, then Retry |
| "The worker has no recovery token configured (DEMO_APP_RECOVERY_TOKEN)." | The variable is empty | Set it in `.env`, `docker compose up -d worker test-app` |
| "Verification failed at 'application_health': ..." | The application did not answer three consecutive readiness checks | Check `docker compose logs test-app` |
| "Verification failed at 'prometheus_target_up': ..." | Prometheus did not scrape the target successfully after the action, or was unavailable | Check Prometheus, then Retry |
| "Verification failed at 'alert_cleared': ..." | The alert was still firing when the verification timeout ended | Check the Monitoring page; Retry when the condition has cleared |
| "... is not on the remediation allowlist." | The file was removed from the allowlist after the request was made | Restore the allowlist or fix manually |
| "Bucket '...' no longer exists in ..." or "The configuration file is not valid: ..." | The file was changed or replaced after the finding was detected | Rescan and make a new request |
| "Verification failed: SEC-001 is still detected for ..." | The rescan still finds the violation | Inspect the file under "Configuration files" |
| "The worker stopped before this execution finished; the outcome is unknown." | The worker was restarted in the middle of the job | Retry |
| "Refused: the request has no recorded approval." | A queued request had no approval; the worker will not run it | Submit a new request |

A failed request leaves the finding Open and the incident as it was. Nothing is marked as fixed.

### The Retry button is missing on a failed request

**Cause.** The request has used all its attempts (three by default), or you are not an
Administrator. A request that the worker refused for lack of an approval can never be retried.

**Fix.** Investigate the failure and submit a new request. If Retry is offered but answers "The
incident is already RESOLVED." or "The finding is ...; only OPEN findings can be remediated.", the
problem has been settled in the meantime and no retry is needed.

### A request was cancelled by "system"

**Cause.** The incident was resolved before the request was dispatched, either by the monitoring
signal or manually. Requests that are Pending Approval or Approved are then cancelled with that
reason.

**Fix.** None needed.

### "The remediation worker did not complete the reset in time. Is the worker running?"

**Cause.** "Reset sample configuration" is carried out by the worker, which did not respond within
20 seconds.

**Fix.** Check the worker as described above and try again.

### "The demonstration application could not be reached." when injecting a fault

**Cause.** The `test-app` container is not running.

**Fix.** `docker compose up -d test-app`.

### Demonstration controls are missing or disabled

**Cause.** `DEMO_CONTROLS_ENABLED` is not `true`, or the server runs in production mode, where they
are off unless the hosted-demonstration opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION` is set. Only
Administrators can use them; for an Operator the buttons are disabled, a notice
says that only an Administrator can use the controls, and no fault-status badge is shown because the
fault state is reported to Administrators only.

**Fix.** For a local demonstration set `DEMO_CONTROLS_ENABLED=true` with `ENVIRONMENT=development`
and run `docker compose up -d`.

### "The '...' fault is switched off in this deployment because the host does not have the resources to run it."

**Cause.** The fault mode is listed in `DEMO_DISABLED_FAULTS` on this server (the Render profile
sets `cpu,memory`). `POST /api/demo/faults` answers HTTP 422 for such a mode, and the Demo controls
tab does not list it.

**Fix.** Use one of the faults that are offered. The Compose stack does not set the variable, so all
five faults are available there.

## VigilAI

### VigilAI shows "Documentation mode"

**Cause.** No Gemini API key is configured, or `AI_PROVIDER=none`. This is a supported mode: answers
come from the knowledge base and live platform data.

**Fix.** To enable live generation set `GEMINI_API_KEY` in `.env` and run
`docker compose up -d backend`; see the [README](../README.md#gemini-api-setup). Live generation was
verified on 2026-11-23 with a real API key and the default model `gemini-3.5-flash-lite`; see the
[verification report](verification-report.md#7-live-gemini-verification).

### An answer starts with a notice that live AI generation is unavailable

**Cause.** A key is configured but the provider call did not succeed. The notice says which case:

| Notice | Cause | What to do |
|---|---|---|
| "... free quota or rate limit has been reached." | The provider answered with a quota error | Wait; free-tier quotas are limited and can change |
| "... rejected the server's credentials." | The API key is invalid or lacks permission | Check `GEMINI_API_KEY` |
| "... the configured AI model rejected the request." | The model name is wrong or not available to the key | Set `GEMINI_MODEL` to a model your key can use |
| "... did not respond in time." | Timeout (`AI_TIMEOUT_SECONDS`, 20 seconds by default) | Try again |
| "... could not be reached." | Network problem between the backend and the provider | Check the server's internet access |
| "... daily AI request budget has been used up." | `AI_DAILY_REQUEST_LIMIT` was reached | It resets at the next UTC day or when the backend restarts |
| "The AI provider declined to generate an answer ..." or "... returned an empty answer." | The provider produced no text | Rephrase the question |

In every case the answer is still given from the documentation and live data, and the rest of the
platform is unaffected. The backend log line "assistant provider failure" records the kind of
failure.

### "You are sending messages too quickly. Try again in N seconds."

**Cause.** The per-user limit (`AI_RATE_LIMIT_PER_MINUTE`, 10 by default) was reached. Running
`scripts/run_e2e_demos.py` uses up the Administrator's limit on purpose.

**Fix.** Wait for the stated time.

### VigilAI declines a question about the platform

**Cause.** The scope check runs in the backend and is based on platform vocabulary. A question with
unusual wording, or one phrased as an order ("fix the bucket"), is treated as out of scope or as an
instruction to act.

**Fix.** Ask it as a question and use platform terms: "How do I fix public storage access?"

### "VigilAI has been turned off by an administrator."

**Cause.** The runtime setting "VigilAI assistant enabled" is off.

**Fix.** An Administrator switches it on under Settings, tab Platform.

### The conversation disappeared

**Cause.** The conversation is kept in the browser's memory only. Reloading the page or signing out
clears it. Nothing is stored on the server.

**Fix.** None; this is by design.

## Scripts and tests

### `verify_stack.sh` reports failures right after starting the stack

**Cause.** Health checks need some time; the worker's has a start period of 30 seconds.

**Fix.** Wait until `docker compose ps` shows the services as healthy and run it again.

### `verify_stack.sh` checks the wrong address

**Cause.** The script does not read `.env`.

**Fix.** `BASE_URL=http://localhost:<port> sh scripts/verify_stack.sh`.

### `run_e2e_demos.py` stops immediately

| Message | Cause | Fix |
|---|---|---|
| A Python traceback ending in a connection error, or "The stack is not reachable at ..." | The stack is not running, or the port differs | Start it, or pass `--base-url` |
| "Login failed for ...: HTTP 401" | The bootstrap passwords in `.env` are not the accounts' current passwords | Reset the passwords to the `.env` values, or update `.env` |
| "Demo controls are disabled ..." | `DEMO_CONTROLS_ENABLED=false`, or production mode without the hosted-demonstration opt-in | Enable them in a development environment |

### `run_e2e_demos.py` fails the check "Findings are persisted without duplicates"

**Cause.** The script expects exactly the five findings of the sample configuration. Findings from
other files that were scanned at any time are still stored.

**Fix.** Run the script on an installation where only the sample configuration has been scanned, for
example after `docker compose down -v` and a fresh start.

### Backend tests fail to start with a database error

**Cause.** `TEST_DATABASE_URL` points to a database that is unreachable, or to a user that may not
create databases (the PostgreSQL-only tests create scratch databases).

**Fix.** Unset the variable to use SQLite, or provide a disposable PostgreSQL database. Never use a
database with real data: the suite drops all tables.

## Windows-specific issues

### "error during connect" or "cannot connect to the Docker daemon"

**Cause.** Docker Desktop is not running, or its engine has not finished starting.

**Fix.** Start Docker Desktop and wait until it reports that the engine is running. Check with
`docker version`. If Docker Desktop reports that WSL 2 is missing, run `wsl --install` in an
Administrator PowerShell and restart.

### `docker` is not found inside a WSL distribution

**Cause.** WSL integration is not enabled for that distribution.

**Fix.** In Docker Desktop, Settings, Resources, WSL integration, enable the distribution.

### A `.sh` script fails with `$'\r': command not found`, "Illegal option" or "bad interpreter"

**Cause.** The script has Windows (CRLF) line endings. Git for Windows converts text files on
checkout when `core.autocrlf` is `true`, and the repository does not pin line endings with a
`.gitattributes` file.

**Fix.** Convert the scripts and stop Git from converting them again:

```bash
sed -i 's/\r$//' scripts/*.sh
git config core.autocrlf input
```

For a new clone: `git clone -c core.autocrlf=input https://github.com/Gangadhar017/VigilOps.git`.

### A path in a `docker compose exec` command is rewritten in Git Bash

**Symptom.** A command such as

```bash
docker compose exec prometheus promtool check rules /etc/prometheus/alert_rules.yml
```

fails with a message about `C:/Program Files/Git/etc/prometheus/...`.

**Cause.** Git Bash (MSYS) converts arguments that look like Unix paths into Windows paths before
passing them to `docker`.

**Fix.** Prefix the command with `MSYS_NO_PATHCONV=1`:

```bash
MSYS_NO_PATHCONV=1 docker compose exec prometheus promtool check rules /etc/prometheus/alert_rules.yml
MSYS_NO_PATHCONV=1 docker compose exec worker ls -l /data/scan-workspace
MSYS_NO_PATHCONV=1 docker compose cp my-config.yaml worker:/data/scan-workspace/
```

PowerShell and WSL do not convert paths, so the commands work there unchanged.

### Port conflict on Windows

**Symptom.** "Ports are not available", "bind: An attempt was made to access a socket in a way
forbidden by its access permissions", or "port is already allocated".

**Cause.** Another program uses the port, or Windows has reserved a port range that includes it.

**Fix.** Choose another port in `.env`, for example `VIGILOPS_HTTP_PORT=8088`, and run
`docker compose up -d`. The other ports are changed with `BACKEND_DEV_PORT`, `PROMETHEUS_DEV_PORT`
and `ALERTMANAGER_DEV_PORT`.

### `&&` is not accepted in PowerShell

**Cause.** Windows PowerShell 5.1 has no `&&` operator.

**Fix.** Run the commands one after another on separate lines, or use Git Bash.

### `sh` is not recognised

**Cause.** PowerShell and the Command Prompt have no POSIX shell.

**Fix.** Run `scripts/verify_stack.sh`, `backup_db.sh` and `restore_db.sh` in Git Bash or WSL. The
Python scripts and all `docker compose` commands work in PowerShell.

### `python` opens the Microsoft Store or is not found

**Cause.** Python is not installed, or only the Windows app-execution alias exists.

**Fix.** Install Python 3.11 and use the launcher: `py scripts\generate_env.py`,
`py scripts\run_e2e_demos.py`. Python is needed only for these scripts and for the backend tests,
not for running the stack.

### Another device cannot open the application although `VIGILOPS_BIND_ADDRESS=0.0.0.0` is set

**Cause.** Windows Defender Firewall blocks inbound connections to the port.

**Fix.** Allow the port for the private network profile in the firewall. Use this only on a trusted
network; the local stack is plain HTTP.
