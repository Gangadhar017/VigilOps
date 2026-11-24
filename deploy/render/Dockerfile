# VigilOps - single-container image for a hosted demonstration
#
# For hosts that offer exactly one small free web service and no background
# workers, private services or shared volumes (for example Render's free plan).
# The API, the remediation worker, the demonstration application, Prometheus
# and Alertmanager run as separate processes inside one container, started and
# supervised by deploy/render/launcher.py.  PostgreSQL is external (DATABASE_URL)
# and the React frontend is served elsewhere (for example Vercel).
#
# The Compose stack (compose.yaml) remains the reference deployment: it keeps
# every component in its own container.  See docs/deployment-render-vercel.md.
#
# Build context: repository root
#   docker build -f deploy/render/Dockerfile -t vigilops-hosted .
FROM prom/prometheus:v2.51.0 AS prometheus
FROM prom/alertmanager:v0.27.0 AS alertmanager

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# One unprivileged user per component.  The API and the worker share a group so
# that the API can read (never write) the scan workspace the worker owns.
RUN groupadd --system --gid 10001 vigilops \
 && useradd --system --uid 10001 --gid vigilops --home-dir /srv/vigilops --shell /usr/sbin/nologin vigilops \
 && groupadd --system --gid 10002 vigilworker \
 && useradd --system --uid 10002 --gid vigilworker --home-dir /srv/vigilops --shell /usr/sbin/nologin vigilworker \
 && groupadd --system --gid 10003 demoapp \
 && useradd --system --uid 10003 --gid demoapp --home-dir /srv/vigilops --shell /usr/sbin/nologin demoapp \
 && groupadd --system --gid 10004 monitoring \
 && useradd --system --uid 10004 --gid monitoring --home-dir /srv/vigilops --shell /usr/sbin/nologin monitoring \
 && mkdir -p /srv/vigilops/backend /srv/vigilops/test-app /srv/vigilops/monitoring /srv/vigilops/deploy

WORKDIR /srv/vigilops/backend

# The same pinned versions as the backend image.  They cover the demonstration
# application's dependencies too (FastAPI, Uvicorn, prometheus-client, Pydantic).
COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

COPY --from=prometheus /bin/prometheus /usr/local/bin/prometheus
COPY --from=alertmanager /bin/alertmanager /usr/local/bin/alertmanager

COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY knowledge_base /srv/vigilops/knowledge_base
COPY security-rules /srv/vigilops/security-rules
COPY test-app/app.py /srv/vigilops/test-app/app.py
COPY test-app/static /srv/vigilops/test-app/static
# The monitoring configuration is the version-controlled one used by the Compose
# stack; the launcher only rewrites the host names to 127.0.0.1.
COPY monitoring /srv/vigilops/monitoring
COPY deploy/render/launcher.py /srv/vigilops/deploy/launcher.py

# Compile the application to bytecode now.  The components run as users that
# cannot write next to the code, so without this every start would compile
# everything again - seconds that matter on a small CPU share.
RUN python -m compileall -q /srv/vigilops/backend/app /srv/vigilops/backend/alembic \
      /srv/vigilops/test-app /srv/vigilops/deploy

ENV KNOWLEDGE_BASE_DIR=/srv/vigilops/knowledge_base \
    SECURITY_RULES_DIR=/srv/vigilops/security-rules \
    SCAN_WORKSPACE_DIR=/data/scan-workspace \
    PORT=10000

# This image has no reverse proxy, so the API passes the demonstration
# application's storefront through under /orbitcrate/ (page, static files and
# store API only).  Set SERVE_DEMO_APP=false on the host to keep it private.
ENV SERVE_DEMO_APP=true

EXPOSE 10000

# The launcher starts as root only to create the runtime directories and to
# drop each component to its own user; nothing it starts keeps root.
CMD ["python", "/srv/vigilops/deploy/launcher.py"]
