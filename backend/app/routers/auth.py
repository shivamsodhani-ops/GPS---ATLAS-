from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_client_ip, get_current_user
from ..models import AuditAction, User
from ..schemas import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut
from ..security import create_access_token, hash_password, verify_password
from ..services import sheets_store, sheets_sync
from ..utils.audit import log as audit_log

logger = logging.getLogger("atlas.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    user = db.query(User).filter(User.email == payload.email.lower()).first()

    generic_error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if user is None:
        audit_log(db, user_id=None, action=AuditAction.LOGIN_FAILURE.value, detail={"email": payload.email}, ip_address=ip)
        raise generic_error

    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
        raise HTTPException(status.HTTP_423_LOCKED, f"Account temporarily locked. Try again in {remaining} min.")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated. Contact your administrator.")

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_login_attempts:
            user.locked_until = datetime.utcnow() + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
        db.commit()
        audit_log(db, user_id=user.id, action=AuditAction.LOGIN_FAILURE.value, ip_address=ip)
        raise generic_error

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    db.commit()

    audit_log(db, user_id=user.id, action=AuditAction.LOGIN_SUCCESS.value, ip_address=ip)
    token = create_access_token(user.id, extra={"role": user.role.value})
    return TokenResponse(access_token=token, user=_to_user_out(user))


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    audit_log(db, user_id=user.id, action=AuditAction.LOGOUT.value, ip_address=get_client_ip(request))
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _to_user_out(user)


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()
    if sheets_store.enabled():
        try:
            sheets_sync.push_user(user)
        except Exception:
            logger.exception("Could not mirror password change for user %s to Sheets.", user.id)
    return {"ok": True}
