# VigilOps backend image (used by both the API and the remediation worker).
# Build context: repository root  ->  docker build -f backend/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Unprivileged runtime user; the scan workspace is owned by it.
RUN groupadd --system --gid 10001 vigilops \
 && useradd --system --uid 10001 --gid vigilops --home-dir /srv/vigilops vigilops \
 && mkdir -p /srv/vigilops/backend /data/scan-workspace \
 && chown -R vigilops:vigilops /data

WORKDIR /srv/vigilops/backend

# constraints.txt pins the exact versions that were tested (reproducible builds).
COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY knowledge_base /srv/vigilops/knowledge_base
COPY security-rules /srv/vigilops/security-rules

ENV KNOWLEDGE_BASE_DIR=/srv/vigilops/knowledge_base \
    SECURITY_RULES_DIR=/srv/vigilops/security-rules \
    SCAN_WORKSPACE_DIR=/data/scan-workspace

USER vigilops
EXPOSE 8000

# Default: apply migrations, then serve the API with a single worker process
# (in-process rate limiters assume one process).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-*}\""]
