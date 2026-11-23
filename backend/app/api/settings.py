"""Platform settings: effective configuration (never secrets) and runtime-tunable options."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import has_permission, permission_matrix, require_permission
from app.models.models import User
from app.schemas.schemas import SettingUpdate
from app.services import settings_service
from app.services.dashboard_service import worker_status

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
def read_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:view")),
) -> Dict[str, Any]:
    """Effective configuration.  Secret values are never returned - only whether they are set."""
    return {
        "can_manage": has_permission(user, "settings:manage"),
        "system": {
            "project": settings.PROJECT_TITLE,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "demo_controls_enabled": settings.demo_controls_active,
            "session_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "login_rate_limit": {
                "attempts": settings.LOGIN_RATE_LIMIT_ATTEMPTS,
                "window_seconds": settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            },
            "api_docs_enabled": settings.api_docs_enabled,
            "placeholder_secrets_in_use": settings.uses_placeholder_secrets(),
        },
        "assistant": {
            "provider": settings.AI_PROVIDER,
            "model": settings.GEMINI_MODEL if settings.AI_PROVIDER == "gemini" else None,
            "api_key_configured": settings.ai_configured,
            "rate_limit_per_minute": settings.AI_RATE_LIMIT_PER_MINUTE,
            "daily_request_limit": settings.AI_DAILY_REQUEST_LIMIT,
            "timeout_seconds": settings.AI_TIMEOUT_SECONDS,
        },
        "scanner": {
            "workspace": "scan workspace (authorised local YAML files)",
            "max_file_bytes": settings.SCAN_MAX_FILE_BYTES,
            "remediation_writable_targets": settings.writable_target_names,
        },
        "remediation": {
            "max_attempts": settings.REMEDIATION_MAX_ATTEMPTS,
            "action_timeout_seconds": settings.ACTION_TIMEOUT_SECONDS,
            "verification_timeout_seconds": settings.VERIFY_TIMEOUT_SECONDS,
            "worker": worker_status(db),
        },
        "runtime_settings": settings_service.list_settings(db),
        "permission_matrix": permission_matrix(),
    }


@router.put("/{key:path}")
def update_setting(
    key: str,
    payload: SettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("settings:manage")),
) -> Dict[str, Any]:
    try:
        return settings_service.update_setting(db, user, key, payload.value)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown setting.")
    except settings_service.SettingError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
