# VigilOps demonstration application
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system --gid 10001 demo \
 && useradd --system --uid 10001 --gid demo --home-dir /app demo

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY static ./static

USER demo
EXPOSE 8001

# Liveness only: a simulated service outage must not make Docker restart the container.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/live', timeout=2)"

CMD ["python", "app.py"]
