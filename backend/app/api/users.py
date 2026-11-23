"""User management (Administrators only)."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, paged
from app.core.database import get_db
from app.core.permissions import require_permission
from app.core.security import hash_password, validate_password_strength
from app.models.models import Role, User
from app.schemas.schemas import Page, PasswordReset, UserCreate, UserOut, UserUpdate
from app.services.audit_service import record_audit

router = APIRouter(prefix="/users", tags=["Users"])


def _active_admin_count(db: Session) -> int:
    return (
        db.query(func.count(User.id))
        .filter(User.role == Role.ADMIN.value, User.is_active.is_(True))
        .scalar()
        or 0
    )


@router.get("", response_model=Page[UserOut])
def list_users(
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users:manage")),
) -> Dict[str, Any]:
    query = db.query(User)
    if params.q:
        pattern = f"%{params.q.lower()}%"
        query = query.filter(or_(func.lower(User.email).like(pattern), func.lower(User.full_name).like(pattern)))
    total = query.count()
    column = {"email": User.email, "role": User.role, "created_at": User.created_at}.get(
        params.sort or "", User.id
    )
    ordering = column.desc() if (params.sort and params.order == "desc") else column.asc()
    items = query.order_by(ordering).offset((params.page - 1) * params.page_size).limit(params.page_size).all()
    return paged(items, total, params)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users:manage")),
) -> User:
    problem = validate_password_strength(payload.password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this e-mail already exists.")
    user = User(
        email=payload.email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        action="USER_CREATED",
        entity_type="user",
        entity_id=user.id,
        actor=admin,
        metadata={"email": user.email, "role": user.role},
    )
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users:manage")),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    changes: Dict[str, Any] = {}
    removing_admin = user.role == Role.ADMIN.value and user.is_active and (
        (payload.role is not None and payload.role != Role.ADMIN.value) or payload.is_active is False
    )
    if removing_admin and _active_admin_count(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active Administrator cannot be demoted or deactivated.",
        )
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate your own account.")

    if payload.full_name is not None and payload.full_name.strip() != user.full_name:
        changes["full_name"] = {"from": user.full_name, "to": payload.full_name.strip()}
        user.full_name = payload.full_name.strip()
    if payload.role is not None and payload.role != user.role:
        changes["role"] = {"from": user.role, "to": payload.role}
        user.role = payload.role
        user.token_version += 1  # existing tokens carry the old role
    if payload.is_active is not None and payload.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": payload.is_active}
        user.is_active = payload.is_active
        user.token_version += 1

    if changes:
        record_audit(
            db,
            action="USER_UPDATED",
            entity_type="user",
            entity_id=user.id,
            actor=admin,
            metadata={"email": user.email, "changes": changes},
        )
        db.commit()
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users:manage")),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    problem = validate_password_strength(payload.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    record_audit(
        db,
        action="USER_PASSWORD_RESET",
        entity_type="user",
        entity_id=user.id,
        actor=admin,
        metadata={"email": user.email},
    )
    db.commit()
