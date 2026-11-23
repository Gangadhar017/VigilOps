"""Container health check for the remediation worker.

Exits 0 when this worker's heartbeat in the database is fresh, 1 otherwise:

    python -m app.workers.healthcheck
"""
from __future__ import annotations

import sys

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.models.models import WorkerHeartbeat

MAX_AGE_SECONDS = 60


def main() -> int:
    try:
        with SessionLocal() as db:
            row = db.get(WorkerHeartbeat, settings.WORKER_ID)
            if row is None:
                return 1
            age = (utcnow() - row.last_seen_at).total_seconds()
            return 0 if age <= MAX_AGE_SECONDS else 1
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":
    sys.exit(main())
