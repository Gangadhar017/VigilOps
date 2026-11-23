"""First-start setup: bootstrap accounts and monitored-resource registration.

Only *configuration* records are created here.  No incidents, findings,
metrics or audit history are ever seeded - those come exclusively from real
platform activity.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, validate_password_strength
from app.models.models import MonitoredResource, Role, User
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)


def _ensure_user(db: Session, email: str, password: str, role: str, full_name: str) -> None:
    email = email.strip().lower()
    if not email or not password:
        return
    if db.query(User).filter(User.email == email).first() is not None:
        return  # never overwrite an existing account or its password
    problem = validate_password_strength(password)
    if problem:
        logger.error("bootstrap account skipped: weak password", extra={"email": email, "problem": problem})
        return
    user = User(email=email, full_name=full_name, password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()
    record_audit(
        db,
        action="USER_BOOTSTRAPPED",
        entity_type="user",
        entity_id=user.id,
        actor_label="system",
        metadata={"email": email, "role": role},
    )
    logger.info("bootstrap account created", extra={"email": email, "role": role})


def _ensure_resource(db: Session, name: str, resource_type: str, job: str, description: str) -> None:
    existing = (
        db.query(MonitoredResource)
        .filter((MonitoredResource.name == name) | (MonitoredResource.monitoring_identifier == job))
        .first()
    )
    if existing is not None:
        return
    db.add(
        MonitoredResource(
            name=name,
            resource_type=resource_type,
            environment="local" if not settings.is_production else "production",
            monitoring_identifier=job,
            description=description,
            status="UNKNOWN",
        )
    )


def run_bootstrap(db: Session) -> None:
    _ensure_user(
        db,
        settings.BOOTSTRAP_ADMIN_EMAIL,
        settings.BOOTSTRAP_ADMIN_PASSWORD,
        Role.ADMIN.value,
        "Platform Administrator",
    )
    _ensure_user(
        db,
        settings.BOOTSTRAP_OPERATOR_EMAIL,
        settings.BOOTSTRAP_OPERATOR_PASSWORD,
        Role.OPERATOR.value,
        "Platform Operator",
    )
    _ensure_resource(
        db,
        "demo-app",
        "application",
        settings.DEMO_APP_JOB,
        "Monitored demonstration web application (order service).",
    )
    _ensure_resource(
        db,
        "vigilops-backend",
        "platform_service",
        settings.BACKEND_JOB,
        "VigilOps API backend.",
    )
    db.commit()
    if not db.query(User).filter(User.role == Role.ADMIN.value, User.is_active.is_(True)).first():
        logger.warning(
            "no active administrator exists; set BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD"
        )
