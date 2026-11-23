# Setup Guide

This guide installs VigilOps on one machine with Docker Compose, which is the reference way to run
it (a free-hosting variant on Render and Vercel is described in
[deployment-render-vercel.md](deployment-render-vercel.md)). It covers Windows (Docker Desktop with WSL2) and Ubuntu Linux, the first start, signing in,
verifying the installation, updating, resetting, and what is needed to run parts of the project
outside Docker for development.

Related documents: [configuration](configuration.md), [deployment](deployment.md),
[troubleshooting](troubleshooting.md), [user guide](user-guide.md).

## Contents

1. [What is installed](#what-is-installed)
2. [Requirements](#requirements)
3. [Windows: Docker Desktop and WSL2](#windows-docker-desktop-and-wsl2)
4. [Ubuntu Linux](#ubuntu-linux)
5. [Get the code and create .env](#get-the-code-and-create-env)
6. [First start](#first-start)
7. [Signing in with the bootstrap accounts](#signing-in-with-the-bootstrap-accounts)
8. [Verifying the installation](#verifying-the-installation)
9. [Updating](#updating)
10. [Resetting](#resetting)
11. [Development without Docker](#development-without-docker)
12. [Removing VigilOps](#removing-vigilops)

## What is installed

Nothing is installed on the host apart from Docker. `docker compose up` builds three images from this
repository (`vigilops-backend:local`, `vigilops-demo-app:local`, `vigilops-web:local`), pulls the
public images `postgres:16-alpine`, `prom/prometheus:v2.51.0` and `prom/alertmanager:v0.27.0` (plus
the Python, Node.js and Caddy base images used by the builds) and starts eight services:

| Service | Role |
|---|---|
| `postgres` | Database |
| `workspace-init` | Runs once, sets ownership of the scan workspace volume, exits |
| `backend` | API; applies database migrations when it starts |
| `worker` | Restricted remediation worker |
| `test-app` | Monitored demonstration application |
| `prometheus` | Metrics and alert rules |
| `alertmanager` | Alert routing to the backend webhook |
| `web` | Caddy reverse proxy and the built React frontend |

The backend and the worker share one image. Data is stored in named Docker volumes, not in the
repository folder.

## Requirements

- A 64-bit machine that can run Docker with Linux containers.
- Internet access for the first build (base images, Python and npm packages).
- Free ports on the host: 8080 (web) and 8000, 9090, 9093 (local tool ports). All four are bound to
  `127.0.0.1` by default and can be changed in `.env`.
- Git.
- Optional: Python 3.11 for the scripts in `scripts/` and the backend tests, Node.js 20 for the
  frontend tests and dev server. The stack itself does not need them on the host.

No minimum memory or disk figures were measured for this guide. The stack runs seven containers
continuously; the demo application is limited to 512 MB of memory and one CPU by `compose.yaml`.

No AWS account, cloud subscription, Ollama installation or model training is required.

## Windows: Docker Desktop and WSL2

1. **Enable WSL2.** Open PowerShell as Administrator and run:

   ```powershell
   wsl --install
   ```

   Restart when asked. Afterwards `wsl --status` should report default version 2. On older Windows
   builds follow Microsoft's WSL installation instructions instead.

2. **Install Docker Desktop** from <https://www.docker.com/products/docker-desktop/>. In its
   settings, under General, keep "Use the WSL 2 based engine" selected.

3. **Install Git for Windows** from <https://git-scm.com/download/win>. It includes Git Bash, which
   is needed for the `.sh` scripts in `scripts/`.

4. **Start Docker Desktop** and wait until it reports that the engine is running. Check in
   PowerShell:

   ```powershell
   docker version
   docker compose version
   ```

   Both commands must print a version without an error. `compose.prod.yaml` uses the `!reset` and
   `!override` merge tags; according to the Docker Compose documentation `!override` needs
   Compose 2.24.4 or later. The local stack (`compose.yaml` alone) does not use them.

5. **Line endings.** Git for Windows usually has `core.autocrlf=true`, which checks text files out
   with CRLF line endings. The repository does not pin line endings with a `.gitattributes` file,
   so shell scripts cloned this way can fail under WSL or Linux shells. To avoid this, clone with:

   ```powershell
   git clone -c core.autocrlf=input https://github.com/Gangadhar017/VigilOps.git vigilops
   ```

   If you already cloned, see [troubleshooting](troubleshooting.md#windows-specific-issues).

Which shell to use on Windows:

| Task | Shell |
|---|---|
| `docker compose ...`, `python scripts/...`, `npm ...`, `pytest` | PowerShell, Git Bash or WSL |
| `sh scripts/verify_stack.sh`, `backup_db.sh`, `restore_db.sh` | Git Bash or WSL |

Windows PowerShell 5.1 does not support `&&` between commands. Run the commands in this guide one per
line.

## Ubuntu Linux

1. Install Docker Engine and the Compose plugin from Docker's own package repository by following
   <https://docs.docker.com/engine/install/ubuntu/>. After adding the repository as described there,
   the packages are installed with:

   ```bash
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   ```

2. Allow your user to run Docker without `sudo`, then log out and in again:

   ```bash
   sudo usermod -aG docker "$USER"
   ```

3. Check the installation:

   ```bash
   docker version
   docker compose version
   ```

4. Install Git if it is missing: `sudo apt-get install -y git`.

## Get the code and create .env

```bash
git clone https://github.com/Gangadhar017/VigilOps.git vigilops
cd vigilops
```

Create the configuration file. Choose one of the two options.

**Option A: placeholder values (quickest, local development only).**

```bash
cp .env.example .env
```

```powershell
Copy-Item .env.example .env
```

The values in `.env.example` are public. They are acceptable on a machine that only you use. The
application shows a warning under Settings, tab Platform, while they are in use.

**Option B: generated secrets.**

```bash
python scripts/generate_env.py
```

This copies `.env.example` and replaces the database password, the JWT signing key, the webhook
token, the two demo application tokens and both bootstrap account passwords with random values. It
prints only the path of the file. It does not overwrite an existing `.env` unless you add `--force`.
On Windows, if `python` is not found or opens the Microsoft Store, use `py scripts\generate_env.py`.

Do this before the first start. The database password is applied by PostgreSQL only when its volume
is first created, so generating a new `.env` for an existing installation requires a full reset
(see [Resetting](#resetting)).

Optional edits before the first start (all described in [configuration](configuration.md)):

- `VIGILOPS_HTTP_PORT` if port 8080 is taken.
- `VIGILOPS_BIND_ADDRESS=0.0.0.0` if other devices on your network must reach the web application.
  The default `127.0.0.1` restricts it to this computer. The local stack uses plain HTTP, so open
  it only on a trusted network.
- `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_OPERATOR_EMAIL` and their passwords. Passwords need at least
  10 characters with upper-case and lower-case letters and a digit, otherwise the account is skipped
  (in production mode the API refuses to start instead).
- `GEMINI_API_KEY` to enable live AI generation. It can stay empty.

## First start

From the repository root:

```bash
docker compose up --build -d
```

The first run downloads base images and builds the three project images, which takes noticeably
longer than later starts. What happens, in order:

1. `postgres` starts and becomes healthy.
2. `workspace-init` makes the scan workspace volume writable for the worker's user and exits.
3. `backend` runs `alembic upgrade head`, starts the API, creates the bootstrap accounts if their
   e-mail addresses do not exist yet, and registers the two monitored resources (`demo-app` and
   `vigilops-backend`).
4. When the backend is healthy, `worker` and `web` start. If demonstration controls are enabled and
   the scan workspace contains no YAML file, the worker copies the sample configuration
   `cloud-infrastructure.yaml` into it.
5. `prometheus`, `alertmanager` and `test-app` start independently of the backend.

Check the state:

```bash
docker compose ps
```

Expected: `postgres`, `backend`, `worker` and `test-app` are shown as running and healthy;
`prometheus`, `alertmanager` and `web` as running (they define no health check). `workspace-init`
has exited with code 0 and is only listed with `docker compose ps -a`.

Then open <http://localhost:8080> (or the port you set in `VIGILOPS_HTTP_PORT`).

| Address | What it is | Reachable from other machines |
|---|---|---|
| `http://localhost:8080` | Web application | No by default (bound to 127.0.0.1); yes with `VIGILOPS_BIND_ADDRESS=0.0.0.0` |
| `http://localhost:8000/docs` | API documentation (development mode only) | No, bound to 127.0.0.1 |
| `http://localhost:9090` | Prometheus UI | No, bound to 127.0.0.1 |
| `http://localhost:9093` | Alertmanager UI | No, bound to 127.0.0.1 |

Stopping and starting again:

```bash
docker compose down          # stop and remove containers; volumes and data are kept
docker compose up -d         # start again without rebuilding
```

## Signing in with the bootstrap accounts

On first start the backend creates one Administrator and one Operator from these `.env` variables:

| Role | E-mail variable | Password variable |
|---|---|---|
| Administrator | `BOOTSTRAP_ADMIN_EMAIL` | `BOOTSTRAP_ADMIN_PASSWORD` |
| Operator | `BOOTSTRAP_OPERATOR_EMAIL` | `BOOTSTRAP_OPERATOR_PASSWORD` |

To see the values you are using:

```bash
grep '^BOOTSTRAP_' .env
```

```powershell
Select-String -Path .env -Pattern '^BOOTSTRAP_'
```

With an unchanged `.env.example` the e-mail addresses are `admin@vigilops.local` and
`operator@vigilops.local`, and the passwords are the placeholder values in that file.

Things to know:

- An account is created only when no account with that e-mail exists. Editing a bootstrap password in
  `.env` afterwards does not change the existing account.
- E-mail addresses are compared in lower case.
- If a bootstrap password does not meet the password policy, the account is not created and the
  backend log contains `bootstrap account skipped: weak password`. In production mode the API
  refuses to start instead, with "BOOTSTRAP_ADMIN_PASSWORD does not meet the password policy: ...".
- There is no self-registration. Further users are created by an Administrator under Settings,
  tab Users.
- After the first sign-in, change the password under Settings, tab Profile. This signs out all
  sessions of that account.
- A session lasts 60 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`) and ends when the browser tab
  is closed.

## Verifying the installation

**Quick manual check.**

1. Sign in as Administrator.
2. Overview: the "Platform health" card lists Backend API, Database, Prometheus, Alertmanager,
   Monitoring targets and Remediation worker as Healthy.
3. Monitoring: `demo-app` and `vigilops-backend` are Up and the metric cards show values. Request
   rate, error rate and latency are computed over one minute, so they can read "Unavailable" for a
   short time right after the first start.
4. Security Findings, tab "Configuration files": `cloud-infrastructure.yaml` is listed (development
   mode with demonstration controls enabled).
5. Select the chat button at the bottom-right and ask "What does SEC-001 mean?".

**Scripted health check** (Git Bash, WSL or Linux; needs `curl`):

```bash
sh scripts/verify_stack.sh
```

It checks that the seven long-running containers are running, that `postgres`, `backend`, `worker`
and `test-app` are healthy, that the web application and `/api/health` answer, that protected API
routes and the alert webhook reject unauthenticated calls, that `/metrics`, `/openapi.json` and the
backend's `/health/ready` are not reachable through the reverse proxy, and that the security headers
are present. It exits with 0 only if every check passed.

The script does not read `.env`. If you changed the web port, pass the address:

```bash
BASE_URL=http://localhost:9000 sh scripts/verify_stack.sh
```

**Health endpoints** you can call directly:

```bash
curl http://localhost:8080/healthz        # reverse proxy only
curl http://localhost:8080/api/health     # API, database and schema
curl http://localhost:8000/health/ready   # backend readiness (local tool port)
```

**Functional check** of the three demonstrations (changes state, takes several minutes):

```bash
python scripts/run_e2e_demos.py
```

See the [README](../README.md#demonstration-instructions) for what it does. Recorded results of the
project's own verification are in [verification-report.md](verification-report.md).

## Updating

```bash
sh scripts/backup_db.sh              # optional but recommended; see deployment.md
git pull
docker compose up --build -d
```

- Database migrations are applied automatically when the new backend container starts.
- Compare `.env.example` with your `.env` after pulling; new variables have defaults in
  `compose.yaml`, so a missing optional variable does not stop the stack.
- Volumes are kept, so accounts, incidents, findings and audit history remain.
- The knowledge base and the security rule catalog are copied into the backend image at build time.
  Changes to `knowledge_base/` or `security-rules/` take effect after a rebuild.
- `monitoring/*.yml` are mounted into the Prometheus and Alertmanager containers. After editing them
  run `docker compose restart prometheus alertmanager`.

## Resetting

| Goal | How |
|---|---|
| Return the demo application to normal | Settings, tab Demo controls, "Clear fault" |
| Restore the insecure sample configuration | Settings, tab Demo controls, "Reset sample configuration" |
| Start completely fresh | `docker compose down -v`, then `docker compose up --build -d` |
| Fresh start with new secrets | `docker compose down -v`, `python scripts/generate_env.py --force`, `docker compose up --build -d` |

`docker compose down -v` deletes every named volume of the project: the database (`pgdata`),
Prometheus history (`prometheus_data`), Alertmanager state (`alertmanager_data`), the scan workspace
(`scan_workspace`) and Caddy's data (`caddy_data`, `caddy_config`). All accounts, incidents, findings,
remediation requests and audit history are lost. Take a backup first if you need them. On the next
start the bootstrap accounts are created again from `.env`.

There is no command-line tool for resetting a single password. If no Administrator can sign in, set
`BOOTSTRAP_ADMIN_EMAIL` in `.env` to an address that does not exist yet, set a valid
`BOOTSTRAP_ADMIN_PASSWORD`, and run `docker compose up -d backend`; a new Administrator account is
created at start.

## Development without Docker

The verified way to run the platform is the Compose stack. The options below are for working on the
code. They are listed from simplest to most involved.

### Frontend dev server against the Docker backend

Requires Node.js 20. Keep the stack running, then:

```bash
cd frontend
npm install
npm run dev
```

Vite serves the application on <http://localhost:5173> with hot reload and proxies `/api` to
`http://127.0.0.1:8000`, the backend port published by `compose.yaml`. The browser sees a single
origin, so `CORS_ORIGINS` does not have to be set. If you changed `BACKEND_DEV_PORT`, set
`VITE_PROXY_TARGET` (for example `http://127.0.0.1:8010`) before starting Vite.

Other frontend commands: `npm test` (Vitest, no backend needed) and `npm run build` (writes
`frontend/dist`).

### Backend tests

Requires Python 3.11.

```bash
cd backend
python -m venv .venv
. .venv/bin/activate              # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest
ruff check app tests
```

- By default the suite creates a temporary SQLite database and replaces Prometheus with a test
  double. No service has to be running.
- To run the same suite on PostgreSQL, set `TEST_DATABASE_URL`, for example
  `postgresql://user:password@localhost:5432/vigilops_test`. The PostgreSQL-only tests (migrations,
  append-only audit trigger, row locking) are skipped on SQLite.
- The suite drops and recreates every table before each test, and the PostgreSQL-only tests create
  and drop scratch databases. Use a disposable database and a user that may create databases. Never
  point `TEST_DATABASE_URL` at a database with data you need.
- The PostgreSQL instance of the Compose stack is not published to the host, so it cannot be used
  for this without changing the Compose file.

### Backend process on the host

This is not part of the verified setup; it is described from the code for developers who want a
debugger attached.

The API refuses to start unless these are set (`backend/app/core/config.py`):

| Variable | Requirement |
|---|---|
| `DATABASE_URL` | Required, no default. A PostgreSQL URL, or a SQLite URL for experiments. |
| `SECRET_KEY` | At least 32 characters |
| `ALERT_WEBHOOK_TOKEN` | At least 16 characters |

The settings loader also reads the `.env` file in the repository root. That file provides
`SECRET_KEY`, `ALERT_WEBHOOK_TOKEN` and the bootstrap accounts, but not `DATABASE_URL`, because
Compose builds it from the `POSTGRES_*` variables. So at minimum:

```bash
cd backend
export DATABASE_URL=sqlite:///./vigilops-dev.db     # PowerShell: $env:DATABASE_URL = "sqlite:///./vigilops-dev.db"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

What to expect:

- Port 8000 is also published by the Compose `backend` service. Stop that container first
  (`docker compose stop backend`) or use another port.
- SQLite is for development and tests only. It is rejected in production mode, has no append-only
  audit trigger and no row locking for the worker queue. Use PostgreSQL 16 for anything else.
- The defaults for `PROMETHEUS_URL` (`http://localhost:9090`) and `ALERTMANAGER_URL`
  (`http://localhost:9093`) match the ports the Compose stack publishes, so monitoring pages can show
  data from the running stack.
- Alertmanager inside Docker still delivers alerts to the containerised backend, not to the host
  process. The demo application is not published to the host, so fault injection and ACTION-001
  from a host process do not reach it unless you also run `test-app/app.py` locally (port 8001).
- Without the image's environment, the scan workspace defaults to `.runtime/scan-workspace` in the
  repository, the rule catalog to `security-rules/` and the knowledge base to `knowledge_base/`.
- The worker is a separate process: `python -m app.workers.remediation_worker` with
  `PROCESS_ROLE=worker` and the same `DATABASE_URL`.

## Removing VigilOps

```bash
docker compose down -v
docker image rm vigilops-backend:local vigilops-demo-app:local vigilops-web:local
```

The first command removes the containers, the network and all data volumes. The second removes the
images built from this repository. The pulled PostgreSQL, Prometheus and Alertmanager images can be
removed with `docker image rm` as well if nothing else uses them.
