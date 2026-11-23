"""Authentication endpoints: login, logout, current user, password change."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, utcnow
from app.core.permissions import permission_matrix, permissions_for
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    create_access_token,
    get_current_user,
    get_token_claims,
    hash_password,
    revoke_token,
    validate_password_strength,
    verify_password,
)
from app.models.models import AuditOutcome, User
from app.schemas.schemas import ChangePasswordRequest, LoginRequest, SessionUser, TokenResponse
from app.services.audit_service import record_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Failed attempts per (client address, e-mail) and a coarser per-address limit.
login_failures = SlidingWindowLimiter(
    settings.LOGIN_RATE_LIMIT_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
)
login_requests_per_ip = SlidingWindowLimiter(30, 60)
# Failures per e-mail, whatever the client address.  The address is taken from
# a forwarding header and can be forged when the API is reachable without a
# trusted proxy in front of it, so the per-address limits alone would not stop
# password guessing against one account.  The allowance is wider than the
# per-address one so that one mistyping user does not lock out the others
# behind the same account name for long.
login_failures_per_email = SlidingWindowLimiter(
    settings.LOGIN_RATE_LIMIT_ATTEMPTS * 4, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
)
_lockout_audit = SlidingWindowLimiter(1, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
# Wrong current-password attempts on the change-password form (per user).
password_change_failures = SlidingWindowLimiter(
    settings.LOGIN_RATE_LIMIT_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
)


def reset_login_limits() -> None:
    """Clear in-memory limiter state (used by tests)."""
    login_failures.clear()
    login_requests_per_ip.clear()
    login_failures_per_email.clear()
    _lockout_audit.clear()
    password_change_failures.clear()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def session_user(user: User) -> SessionUser:
    return SessionUser.model_validate(user).model_copy(update={"permissions": permissions_for(user.role)})


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid credentials"}, 429: {"description": "Too many attempts"}},
)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    ip = _client_ip(request)
    key = f"{ip}|{payload.email}"

    allowed_ip, retry_ip = login_requests_per_ip.allow(ip)
    allowed_key, retry_key = login_failures.check(key)
    allowed_email, retry_email = login_failures_per_email.check(payload.email)
    if not allowed_ip or not allowed_key or not allowed_email:
        retry_after = max(retry_ip, retry_key, retry_email)
        # Audit a lock-out once per window, so a flood cannot bloat the audit trail.
        if _lockout_audit.allow(key)[0]:
            record_audit(
                db,
                action="AUTH_LOGIN_RATE_LIMITED",
                entity_type="user",
                actor_label=payload.email,
                outcome=AuditOutcome.DENIED,
                metadata={"retry_after_seconds": retry_after},
            )
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many sign-in attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.email == payload.email).first()
    # verify_password always performs a bcrypt comparison, even for unknown users.
    password_ok = verify_password(payload.password, user.password_hash if user else None)

    if user is None or not password_ok or not user.is_active:
        login_failures.hit(key)
        login_failures_per_email.hit(payload.email)
        record_audit(
            db,
            action="AUTH_LOGIN_FAILED",
            entity_type="user",
            entity_id=user.id if user else None,
            actor_label=payload.email,
            outcome=AuditOutcome.FAILURE,
            metadata={"reason": "account disabled" if (user and password_ok) else "invalid credentials"},
        )
        db.commit()
        # One generic message: do not reveal whether the e-mail exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect e-mail or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_failures.reset(key)
    user.last_login_at = utcnow()
    token, expires_at, _jti = create_access_token(user)
    record_audit(db, action="AUTH_LOGIN_SUCCESS", entity_type="user", entity_id=user.id, actor=user)
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": session_user(user),
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    claims: Dict[str, Any] = Depends(get_token_claims),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Revoke the presented token server-side so it cannot be reused."""
    revoke_token(db, claims, current_user)
    record_audit(db, action="AUTH_LOGOUT", entity_type="user", entity_id=current_user.id, actor=current_user)
    db.commit()


@router.get("/me", response_model=SessionUser)
def read_current_user(current_user: User = Depends(get_current_user)) -> SessionUser:
    return session_user(current_user)


@router.get("/permissions")
def read_permission_matrix(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """The role/permission matrix enforced by the backend."""
    return {"role": current_user.role, "matrix": permission_matrix()}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    limiter_key = f"user:{current_user.id}"
    allowed, retry_after = password_change_failures.check(limiter_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many incorrect attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    if not verify_password(payload.current_password, current_user.password_hash):
        password_change_failures.hit(limiter_key)
        record_audit(
            db,
            action="AUTH_PASSWORD_CHANGE_FAILED",
            entity_type="user",
            entity_id=current_user.id,
            actor=current_user,
            outcome=AuditOutcome.FAILURE,
            metadata={"reason": "current password incorrect"},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    problem = validate_password_strength(payload.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=422,
            detail="The new password must be different from the current password.",
        )
    current_user.password_hash = hash_password(payload.new_password)
    current_user.token_version += 1  # signs out every existing session
    record_audit(
        db, action="AUTH_PASSWORD_CHANGED", entity_type="user", entity_id=current_user.id, actor=current_user
    )
    db.commit()
