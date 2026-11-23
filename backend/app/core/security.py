"""Authentication primitives: password hashing, JWT issue/verify, current user."""
from __future__ import annotations

import hmac
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, utcnow
from app.models.models import RevokedToken, User

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token from /api/auth/login")

# bcrypt only considers the first 72 bytes; longer inputs are rejected rather
# than silently truncated.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 10

# A valid hash used to equalise timing when the e-mail is unknown.
_DUMMY_HASH = bcrypt.hashpw(b"vigilops-timing-equaliser", bcrypt.gensalt(rounds=12)).decode()


def validate_password_strength(password: str) -> Optional[str]:
    """Return a human-readable problem, or None when the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return f"Password must be at most {MAX_PASSWORD_BYTES} bytes long."
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        return "Password must contain both upper-case and lower-case letters."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, password_hash: Optional[str]) -> bool:
    """Constant-time-ish verification; always performs one bcrypt comparison."""
    encoded = plain_password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        encoded = encoded[:MAX_PASSWORD_BYTES]
        oversized = True
    else:
        oversized = False
    try:
        matched = bcrypt.checkpw(encoded, (password_hash or _DUMMY_HASH).encode("utf-8"))
    except ValueError:
        matched = False
    return bool(matched and password_hash and not oversized)


def create_access_token(user: User) -> Tuple[str, datetime, str]:
    """Issue a signed JWT.  Returns (token, expiry, jti)."""
    now = utcnow()
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = uuid.uuid4().hex
    claims: Dict[str, Any] = {
        "sub": str(user.id),
        "role": user.role,
        "ver": user.token_version,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, expires_at, jti


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        claims = decode_access_token(credentials.credentials)
    except JWTError:
        raise _unauthorized("Session is invalid or has expired. Please sign in again.")
    if not claims.get("sub") or not claims.get("jti"):
        raise _unauthorized("Session is invalid or has expired. Please sign in again.")
    return claims


def get_current_user(
    claims: Dict[str, Any] = Depends(get_token_claims),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError):
        raise _unauthorized("Session is invalid or has expired. Please sign in again.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Account is disabled or no longer exists.")
    if claims.get("ver") != user.token_version:
        raise _unauthorized("Session was invalidated. Please sign in again.")
    if db.get(RevokedToken, claims["jti"]) is not None:
        raise _unauthorized("Session was signed out. Please sign in again.")
    return user


def revoke_token(db: Session, claims: Dict[str, Any], user: User) -> None:
    """Record a logout so the token cannot be reused before it expires."""
    expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=timezone.utc)
    if db.get(RevokedToken, claims["jti"]) is None:
        db.add(RevokedToken(jti=claims["jti"], user_id=user.id, expires_at=expires_at))
    # Opportunistic clean-up of tokens that have expired anyway.
    db.query(RevokedToken).filter(RevokedToken.expires_at < utcnow()).delete(
        synchronize_session=False
    )


def constant_time_equals(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
