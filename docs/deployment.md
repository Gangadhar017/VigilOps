# Deployment Guide

How to run VigilOps locally and on a Linux server with the production overlay, which ports are
exposed, where data is stored, how to back it up and restore it, how to upgrade, and what to harden.
The last section states plainly what was and was not verified.

A free-hosting variant (one container on Render, the frontend on Vercel) is described in
[deployment-render-vercel.md](deployment-render-vercel.md). The Docker Compose stack described here
remains the reference deployment.

Related documents: [setup](setup.md), [configuration](configuration.md), [security](security.md),
[troubleshooting](troubleshooting.md), [deployment diagram](diagrams/deployment.md).

## Contents

1. [Two ways to run it](#two-ways-to-run-it)
2. [Local deployment](#local-deployment)
3. [Production deployment on a Linux server](#production-deployment-on-a-linux-server)
4. [What production mode changes](#what-production-mode-changes)
5. [Ports: what is exposed and what is not](#ports-what-is-exposed-and-what-is-not)
6. [Persistent volumes](#persistent-volumes)
7. [Backup and restore](#backup-and-restore)
8. [Upgrades](#upgrades)
9. [Hardening checklist](#hardening-checklist)
10. [What was and was not verified](#what-was-and-was-not-verified)

## Two ways to run it

| | Local stack | Production overlay |
|---|---|---|
| Command | `docker compose up --build -d` | `docker compose -f compose.yaml -f compose.prod.yaml up --build -d` |
| Files | `compose.yaml` | `compose.yaml` and `compose.prod.yaml` |
| Mode | `ENVIRONMENT` from `.env` (development by default) | `production`, forced by the overlay |
| Entry point | `http://localhost:8080`, plain HTTP, bound to 127.0.0.1 | `https://<VIGILOPS_DOMAIN>`, ports 80 and 443 |
| Tool ports (API docs, Prometheus, Alertmanager) | Published on 127.0.0.1 | Not published |
| Demonstration controls | Available when `DEMO_CONTROLS_ENABLED=true` | Always off |
| Placeholder secrets | Accepted, with a warning | Refused at start |
| Verification status | See [verification-report.md](verification-report.md) | Not tested on a public domain |

Both use the same images and the same eight services. The platform is designed for a single host:
one backend process, one worker, one database.

## Local deployment

The full procedure is in the [setup guide](setup.md). In short:

```bash
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
docker compose up --build -d
```

- Web application: <http://localhost:8080>.
- The web port listens on `127.0.0.1` only. To let other devices on a trusted network reach it, set
  `VIGILOPS_BIND_ADDRESS=0.0.0.0` in `.env` and run `docker compose up -d`. The local stack has no
  TLS: sign-in credentials and tokens travel unencrypted, so do not do this on an untrusted
  network.
- Stop with `docker compose down` (data kept) or `docker compose down -v` (data deleted).

## Production deployment on a Linux server

This section describes how the production overlay is meant to be used. It follows from
`compose.prod.yaml`, `reverse-proxy/Caddyfile` and the start-up checks in
`backend/app/core/config.py`. It has not been exercised on a real public domain; read
[What was and was not verified](#what-was-and-was-not-verified) first.

### Prerequisites

- A Linux VPS or VM with a public IP address.
- Docker Engine with the Compose plugin (see [setup](setup.md#ubuntu-linux)). `compose.prod.yaml`
  uses the `!reset` and `!override` merge tags; according to the Docker Compose documentation
  `!override` needs Compose 2.24.4 or later. Check with `docker compose version`.
- Git, and Python 3 for `scripts/generate_env.py`.
- A DNS name you control.

### DNS

Create an `A` record (and an `AAAA` record if the server has IPv6) for the name you will use, for
example `vigilops.example.com`, pointing to the server. The record must resolve before the stack is
started, because Caddy requests the TLS certificate for that name on start.

### Firewall

| Port | Protocol | Purpose | Open to |
|---|---|---|---|
| 80 | TCP | Certificate issuance and redirect to HTTPS | Internet |
| 443 | TCP | HTTPS | Internet, or the networks your users come from |
| 443 | UDP | HTTP/3 (optional) | Same as 443/TCP |
| 22 | TCP | SSH administration | Your administration addresses only |

Nothing else needs to be open. With `ufw` on Ubuntu, for example:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443
sudo ufw enable
```

Ports published by Docker are opened through Docker's own firewall rules and can bypass `ufw`.
The production overlay publishes only 80 and 443, so this does not expose anything further, but keep
it in mind if you add port mappings.

### Prepare .env

```bash
git clone https://github.com/Gangadhar017/VigilOps.git vigilops
cd vigilops
python3 scripts/generate_env.py
chmod 600 .env
```

Then edit `.env`:

| Variable | What to set |
|---|---|
| `VIGILOPS_DOMAIN` | Your DNS name, for example `vigilops.example.com`. Required by the overlay. |
| `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_OPERATOR_EMAIL` | Real addresses of the first two users. The generated passwords are in the file. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Optional. Leave the key empty for documentation mode. |
| `ENVIRONMENT`, `DEMO_CONTROLS_ENABLED` | The overlay forces `production` and `false` for the backend, the worker and the demo application, whatever the file says. Setting `ENVIRONMENT=production` in the file as well avoids confusion. |

`VIGILOPS_HTTP_PORT`, `VIGILOPS_BIND_ADDRESS` and the three `*_DEV_PORT` variables have no effect
with the overlay.

Do not reuse `.env.example` unchanged. In production mode the backend and the worker refuse to start
while placeholder values remain (see [What production mode changes](#what-production-mode-changes)).

### Start

```bash
docker compose -f compose.yaml -f compose.prod.yaml up --build -d
docker compose -f compose.yaml -f compose.prod.yaml ps
```

Every later `docker compose` command for this deployment needs the same two `-f` options. To avoid
repeating them, set the standard Compose variable in your shell:

```bash
export COMPOSE_FILE=compose.yaml:compose.prod.yaml
docker compose ps
```

The scripts in `scripts/` call `docker compose` without `-f`. They only address running containers
of the `vigilops` project (`exec`, `stop`, `start`, `ps`), so they work either way; exporting
`COMPOSE_FILE` keeps everything consistent.

### First sign-in and first checks

1. Open `https://<VIGILOPS_DOMAIN>`. Caddy obtains the certificate on first start; if the page is
   not served over HTTPS yet, look at `docker compose logs web`.
2. Sign in as the bootstrap Administrator and change the password under Settings, tab Profile.
3. Create individual accounts under Settings, tab Users.
4. Settings, tab Platform, shows Environment "Production", Demo controls "Disabled" and API
   documentation "Disabled".
5. The scan workspace is empty in production. Copy your configuration files into it (see
   [configuration](configuration.md#the-scan-workspace)):

   ```bash
   docker compose cp my-config.yaml worker:/data/scan-workspace/
   ```

6. Optional health check from the server or your workstation:

   ```bash
   BASE_URL=https://vigilops.example.com sh scripts/verify_stack.sh
   ```

`scripts/run_e2e_demos.py` does not run against a production deployment: it needs the demonstration
controls and stops with a message when they are disabled.

## What production mode changes

### Changes made by compose.prod.yaml

| Service | Change |
|---|---|
| `backend` | `ENVIRONMENT=production`, `DEMO_CONTROLS_ENABLED=false`, `LOG_FORMAT=json`, published port removed, `restart: always` |
| `worker` | `ENVIRONMENT=production`, `DEMO_CONTROLS_ENABLED=false`, `restart: always` |
| `test-app` | `DEMO_CONTROLS_ENABLED=false`, `restart: always` |
| `prometheus`, `alertmanager` | Published ports removed, `restart: always` |
| `postgres` | `restart: always` |
| `web` | `SITE_ADDRESS` set to `VIGILOPS_DOMAIN`; publishes `80`, `443/tcp` and `443/udp` on all interfaces instead of the local port; `restart: always` |

Compose stops with "set VIGILOPS_DOMAIN in .env for production" when the variable is missing.

### Changes made by the application in production mode

From `Settings._validate` and the properties in `backend/app/core/config.py`:

- **Placeholder values are refused.** The process exits at start if `SECRET_KEY`,
  `ALERT_WEBHOOK_TOKEN`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_OPERATOR_PASSWORD`,
  `DEMO_APP_RECOVERY_TOKEN`, `DEMO_APP_CONTROL_TOKEN` or the database password inside `DATABASE_URL`
  contains `change-me`, `changeme`, `replace-me`, `example` or `dev-only`. The log line names the
  variables: "Refusing to start in production with placeholder values for: ...".
- **SQLite is refused** as a database.
- **API documentation is off.** `/docs` and `/openapi.json` are not served.
- **Bootstrap passwords must meet the password policy.** The API exits at start with
  "BOOTSTRAP_ADMIN_PASSWORD does not meet the password policy: ..." (or the Operator's variable) if
  a bootstrap password is set and fails the policy. Outside production the account is skipped and an
  error is logged.
- **Demonstration controls are off regardless of `DEMO_CONTROLS_ENABLED`,** unless the explicit
  opt-in `ALLOW_DEMO_CONTROLS_IN_PRODUCTION=true` is set as well. The opt-in is `false` by default,
  is not passed through by the Compose files, and exists only for a hosted demonstration instance
  whose only workload is the bundled demo application. Without it the fault-injection and
  reset endpoints answer HTTP 404, the Demo controls tab reports that they are disabled, the demo
  application's fault endpoint does not exist, and the worker does not place the sample
  configuration in the scan workspace.

The length checks apply in every mode: `SECRET_KEY` at least 32 characters and `ALERT_WEBHOOK_TOKEN`
at least 16 for the API process.

### Changes made by Caddy

With a domain name as site address, Caddy obtains and renews a certificate for it automatically and
redirects HTTP to HTTPS. Certificates and account data are kept in the `caddy_data` volume. The
Caddyfile also sends `Strict-Transport-Security: max-age=31536000`; browsers honour it over HTTPS
and will then insist on HTTPS for that host name for a year.

### What does not change

- The demo application still runs, still generates its synthetic load and is still monitored.
  Incidents for it are opened as usual and ACTION-001 remains available.
- Roles, the remediation workflow, the scanner rules, the audit trail and VigilAI behave as in
  development mode.
- Prometheus and Alertmanager use the same `monitoring/*.yml` files, including the short 5-second
  scrape interval and the 2-minute repeat interval chosen for demonstrations. For a long-running
  deployment consider longer intervals and adjust the coupled settings listed in
  [configuration](configuration.md#editing-these-files).

## Ports: what is exposed and what is not

### On the host

| Service | Container port | Local stack | Production overlay |
|---|---|---|---|
| `web` | 80 | `VIGILOPS_BIND_ADDRESS:VIGILOPS_HTTP_PORT`, default `127.0.0.1:8080` | `0.0.0.0:80` |
| `web` | 443 (TCP and UDP) | not published | `0.0.0.0:443` |
| `backend` | 8000 | `127.0.0.1:8000` | not published |
| `prometheus` | 9090 | `127.0.0.1:9090` | not published |
| `alertmanager` | 9093 | `127.0.0.1:9093` | not published |
| `postgres` | 5432 | not published | not published |
| `test-app` | 8001 | not published | not published |
| `worker` | none | no listening port | no listening port |

Services reach each other by name on the private bridge network `internal`.

### Through the reverse proxy

| Path | Goes to |
|---|---|
| `/api/*` | The backend |
| `/healthz` | Answered by Caddy itself with `ok` |
| Everything else | The web application (static files, with `index.html` as fallback) |

The backend's `/metrics`, `/docs`, `/openapi.json` and `/health/*` endpoints are outside `/api` and are
therefore not routed to the backend; a request for such a path receives the web application's page.
Prometheus scrapes `/metrics` over the private network. Prometheus, Alertmanager, PostgreSQL, the demo
application and the worker have no route through the proxy at all.

The proxy adds these response headers: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a `Permissions-Policy` that disables camera,
microphone and geolocation, and a `Content-Security-Policy` restricted to the application's own
origin. Caddy's admin API is turned off.

## Persistent volumes

All state is in named Docker volumes. Docker prefixes them with the project name, so `pgdata` appears
as `vigilops_pgdata` in `docker volume ls`.

| Volume | Mounted in | Contains | If it is lost |
|---|---|---|---|
| `pgdata` | `postgres` | Users, incidents, findings, scans, remediation requests, audit events, runtime settings | All platform records; restore from a backup |
| `scan_workspace` | `worker` (read-write), `backend` (read-only) | The YAML configuration files that are scanned | Copy the files in again |
| `prometheus_data` | `prometheus` | Metric history, retained for 7 days | Charts start empty; alerts continue |
| `alertmanager_data` | `alertmanager` | Notification state and silences | Alerts that are firing are notified again |
| `caddy_data` | `web` | TLS certificates and ACME account (production) | Caddy requests new certificates |
| `caddy_config` | `web` | Caddy's saved configuration state | Recreated automatically |

Volumes survive `docker compose down` and image rebuilds. `docker compose down -v` deletes all of
them.

Not in a volume: the three files in `monitoring/` are bind-mounted read-only from the repository
checkout, so the checkout must stay where it is. The knowledge base and the rule catalog are part of
the backend image. `.env` exists only on the host.

## Backup and restore

Both scripts are POSIX shell scripts. Run them from the repository root while the stack is running,
on Linux or in WSL or Git Bash on Windows.

### Backup

```bash
sh scripts/backup_db.sh                    # writes backups/vigilops-<UTC timestamp>.sql.gz
sh scripts/backup_db.sh /var/backups/vigilops
```

What it does:

- Runs `pg_dump --clean --if-exists --no-owner` inside the `postgres` container, so the database
  port never has to be published, and compresses the output with gzip on the host.
- Checks that the file is a valid, non-empty gzip archive; otherwise it deletes the file and exits
  with an error.
- Prints the path and size of the backup.

Things to know:

- The default directory `backups/` is inside the repository and is not listed in `.gitignore`. A
  dump contains e-mail addresses, password hashes and the audit trail. Prefer a directory outside the
  repository, and never commit a backup.
- The backup covers the PostgreSQL database only. It does not include the scan workspace, Prometheus
  history, Alertmanager state, Caddy certificates or `.env`.
- Keep a copy of `.env` in a safe place. To copy the workspace files out:
  `docker compose cp worker:/data/scan-workspace ./scan-workspace-backup`.
- For regular backups, call the script from a scheduler. A crontab line could look like this
  (example, adjust the paths):

  ```text
  0 2 * * * cd /opt/vigilops && sh scripts/backup_db.sh /var/backups/vigilops >> /var/log/vigilops-backup.log 2>&1
  ```

  The script does not delete old backups and does not copy them off the host; arrange both yourself.

### Restore

```bash
sh scripts/restore_db.sh /var/backups/vigilops/vigilops-20261123-101500.sql.gz
```

What it does:

1. Refuses a file that does not exist or is not valid gzip.
2. Asks you to type `yes`, because the current database content is replaced. `CONFIRM=yes` in the
   environment skips the question for scripted use.
3. Stops `backend` and `worker` so nothing writes during the restore.
4. Pipes the dump into `psql` inside the `postgres` container with `ON_ERROR_STOP`. The session
   disables user triggers (`session_replication_role=replica`), which is necessary because the audit
   table normally rejects UPDATE and DELETE.
5. Starts `backend` and `worker` again. The backend applies any newer migrations on start.

After a restore, accounts, roles and passwords are those stored in the backup, and users may have to
sign in again.

To move to a new server: install the stack there with its own `.env`, start it once, then run the
restore script with a backup from the old server and copy the scan workspace files.

## Upgrades

```bash
sh scripts/backup_db.sh /var/backups/vigilops
git pull
docker compose -f compose.yaml -f compose.prod.yaml up --build -d     # local stack: docker compose up --build -d
docker compose ps
```

- The backend container runs `alembic upgrade head` before serving, so schema changes are applied on
  start. The worker waits until the schema is available.
- Compare `.env.example` with your `.env` for new variables.
- Named volumes are kept across rebuilds.
- There is a short interruption while containers are recreated. Remediation requests that were
  running at that moment are marked FAILED by the worker when it starts again, with the reason "The
  worker stopped before this execution finished; the outcome is unknown." An Administrator can retry
  them.
- To go back to an earlier version, check out that version, restore the backup taken before the
  upgrade, and start the stack. Do not expect an older version to work with a database that a newer
  version has migrated.

## Hardening checklist

Secrets and accounts:

- [ ] `.env` was created with `scripts/generate_env.py` or contains your own strong values; no
      placeholder remains.
- [ ] `.env` is readable only by the deploying user (`chmod 600 .env`) and is not committed.
- [ ] The bootstrap passwords were changed after the first sign-in. Once the accounts exist, the
      `BOOTSTRAP_*_PASSWORD` values are no longer used and can be removed from `.env`.
- [ ] Every person has an individual account; unused accounts are deactivated; at least two
      Administrators exist so that remediation can be approved by someone other than the requester.
- [ ] The runtime setting "Allow self-approval of remediation" is off.

Network:

- [ ] Only ports 80 and 443 (and restricted SSH) are reachable from outside.
- [ ] The production overlay is used on any host that is reachable by others. The local stack is
      plain HTTP.
- [ ] No port mappings were added for PostgreSQL, Prometheus, Alertmanager or the backend.
- [ ] `FORWARDED_ALLOW_IPS` is left at its default only while the backend is reachable solely from
      the private Docker network, which is the case with the shipped Compose files.

Operation:

- [ ] Backups run regularly, are stored outside the repository and off the host, and a restore has
      been tried.
- [ ] The host and Docker are kept updated. `postgres:16-alpine` and the Caddy and Python base images
      are floating tags; rebuild and pull regularly, or pin them to digests.
- [ ] Logs are collected. Backend and worker write one JSON object per line to standard output;
      API error responses and log lines carry a `request_id`.
- [ ] The backend runs as a single process and the stack as a single instance. The rate limiters and
      VigilAI's daily counter are held in memory and are not shared between processes.

VigilAI:

- [ ] Decide deliberately whether to configure `GEMINI_API_KEY`. With a key, questions, recent
      conversation turns, matching documentation and a summary of the relevant live platform data
      are sent to Google's API.
- [ ] Billing on the Google account stays disabled unless the owner decides otherwise.
      `AI_RATE_LIMIT_PER_MINUTE` and `AI_DAILY_REQUEST_LIMIT` limit usage.

What the Compose files already do: the backend, the worker and the demo application run as an
unprivileged user with a read-only root filesystem, no Linux capabilities and `no-new-privileges`;
the web container keeps only the capability to bind ports 80 and 443; the backend mounts the scan
workspace read-only; the worker has no listening port. Details and residual risks are in
[security.md](security.md).

## What was and was not verified

The project's verification is recorded in [verification-report.md](verification-report.md), with
measurements in [evaluation.md](evaluation.md). This guide does not repeat results. The following
points are stated here so that nobody relies on something that was not tested.

**Not verified:**

- **Deployment on a real public domain with HTTPS.** The production overlay has not been run on an
  internet-facing server. Certificate issuance and renewal by Caddy, the HTTP to HTTPS redirect, the
  effect of the HSTS header, HTTP/3 on 443/UDP and behaviour behind an external firewall or load
  balancer are therefore untested. The DNS, firewall and first-sign-in steps above are derived from
  the configuration files, not from a test run.
- **Exhaustion of the Gemini quota.** Live Gemini generation itself was verified on 2026-11-23 with a
  real API key and the default model `gemini-3.5-flash-lite` (`scripts/verify_gemini_live.py`,
  evidence in [`evidence/gemini-live.json`](evidence/gemini-live.json)). A real quota error (HTTP 429
  from the provider) was never observed; that path and provider timeouts are covered only by tests
  with a stubbed SDK client. Answer quality was checked on a small question set with one model, not
  by a systematic human evaluation.
- **Operational suggestions in this guide** that go beyond the repository: the `ufw` commands, the
  crontab example, off-host backup handling, moving to a new server, and the `COMPOSE_FILE`
  convenience are standard practice but were not exercised as part of this project.

**Checked automatically by the CI workflow** (`.github/workflows/ci.yml`): the merged production
configuration is validated with `docker compose -f compose.yaml -f compose.prod.yaml config --quiet`.
That confirms the two files combine into a valid configuration. It is not a deployment test.

**Known limits of a production deployment:**

- The scanner evaluates files you copy into the workspace. It does not connect to a cloud account.
- Only two automated remediation actions exist, and ACTION-001 targets the bundled demo application.
- ACTION-001 cannot start a stopped container; the platform has no Docker or host access.
- The browser keeps the access token in `sessionStorage`.
- Rate limiters are in-process, so the backend must stay a single process.
- No capacity or load figures for production use are claimed; see
  [evaluation.md](evaluation.md) for what was measured.
