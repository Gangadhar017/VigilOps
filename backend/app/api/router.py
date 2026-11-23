"""Aggregates every API router under the /api prefix."""
from fastapi import APIRouter

from app.api import (
    assistant,
    audit,
    auth,
    demo,
    incidents,
    monitoring,
    remediation,
    security,
    settings,
    users,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(monitoring.router)
api_router.include_router(incidents.router)
api_router.include_router(security.router)
api_router.include_router(remediation.router)
api_router.include_router(audit.router)
api_router.include_router(assistant.router)
api_router.include_router(settings.router)
api_router.include_router(demo.router)
