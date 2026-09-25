from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin, require_manager_or_admin
from ..models import AuditAction, User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import hash_password
from ..services import sheets_store, sheets_sync
from ..utils.audit import log as audit_log

logger = logging.getLogger("atlas.users")

router = APIRouter(prefix="/api/users", tags=["users"])


def _sync_user(user: User) -> None:
    if sheets_store.enabled():
        try:
            sheets_sync.push_user(user)
        except Exception:
            logger.exception("Could not mirror user %s to Sheets.", user.id)


def _out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        name=u.name,
        email=u.email,
        role=u.role,
        department_id=u.department_id,
        department_name=u.department.name if u.department else None,
        is_active=u.is_active,
        must_change_password=u.must_change_password,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return [_out(u) for u in db.query(User).order_by(User.name).all()]


@router.get("/lookup", response_model=UserOut)
def lookup_user(email: str, db: Session = Depends(get_db), _: User = Depends(require_manager_or_admin)):
    """Exact-match email lookup so a manager can grant document access to a
    specific colleague without needing the full user-management list (which
    stays admin-only).
    """
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user found with that email")
    return _out(user)


@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
        department_id=payload.department_id,
        must_change_password=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists")
    db.refresh(user)
    audit_log(db, user_id=admin.id, action=AuditAction.USER_CREATED.value, detail={"created_user_id": user.id, "email": user.email})
    _sync_user(user)
    return _out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    action = AuditAction.USER_DEACTIVATED.value if data.get("is_active") is False else AuditAction.USER_UPDATED.value
    audit_log(db, user_id=admin.id, action=action, detail={"target_user_id": user.id, "changes": data})
    _sync_user(user)
    return _out(user)
