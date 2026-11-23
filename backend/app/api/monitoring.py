"""Monitoring APIs (read-only views over Prometheus) and the alert webhook."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.metrics import ALERT_WEBHOOK_REJECTED
from app.core.permissions import require_permission
from app.core.security import constant_time_equals
from app.models.models import User
from app.schemas.schemas import AlertmanagerWebhook
from app.services import dashboard_service, incident_service, monitoring_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Monitoring"])


@router.get("/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard:view")),
) -> Dict[str, Any]:
    """Counts and platform health for the Overview page (from stored records)."""
    return dashboard_service.summary(db, user)


@router.get("/monitoring/overview")
def monitoring_overview(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring:view")),
) -> Dict[str, Any]:
    """Live state of Prometheus, Alertmanager, scrape targets and monitored resources."""
    return monitoring_service.overview(db)


@router.get("/monitoring/metrics")
def monitoring_metric_catalog(
    _user: User = Depends(require_permission("monitoring:view")),
) -> Dict[str, Any]:
    return {
        "metrics": monitoring_service.metric_catalog(),
        "ranges": list(monitoring_service.RANGE_PRESETS.keys()),
    }


@router.get("/monitoring/timeseries")
def monitoring_timeseries(
    job: str = Query(..., max_length=80, description="Prometheus job of a monitored resource"),
    metric: str = Query(..., max_length=40, description="Metric key from /monitoring/metrics"),
    range: str = Query("15m", max_length=8, description="Time range preset"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("monitoring:view")),
) -> Dict[str, Any]:
    """Historical samples for one catalog metric.  Arbitrary PromQL is not accepted."""
    try:
        return monitoring_service.timeseries(db, job, metric, range)
    except monitoring_service.MetricRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def verify_webhook_token(authorization: Optional[str] = Header(default=None)) -> None:
    """Dependency: runs before the request body is parsed, so an unauthenticated
    caller learns nothing about the expected payload (401, never 422)."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token or not constant_time_equals(
        token.strip(), settings.ALERT_WEBHOOK_TOKEN
    ):
        ALERT_WEBHOOK_REJECTED.labels(reason="unauthorized").inc()
        logger.warning("alert webhook rejected: invalid token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/alerts/webhook",
    tags=["Alerting"],
    summary="Alertmanager webhook receiver",
    dependencies=[Depends(verify_webhook_token)],
    responses={401: {"description": "Missing or invalid webhook token"}},
)
def alertmanager_webhook(payload: AlertmanagerWebhook, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Receives firing/resolved alerts from Alertmanager and feeds the incident engine.

    Protected by a shared bearer token that only Alertmanager holds; user JWTs
    are not accepted here.
    """
    results = incident_service.process_alerts(db, [alert.model_dump() for alert in payload.alerts])
    logger.info("alert webhook processed", extra={"alerts": len(payload.alerts), "results": results})
    return {"status": "processed", "alerts": len(payload.alerts), "results": results}
