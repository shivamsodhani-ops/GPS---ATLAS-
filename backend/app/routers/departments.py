from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import AuditAction, Department, User
from ..schemas import DepartmentCreate, DepartmentOut
from ..services import sheets_store, sheets_sync
from ..utils.audit import log as audit_log

logger = logging.getLogger("atlas.departments")

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Department).order_by(Department.name).all()


@router.post("", response_model=DepartmentOut)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    code = payload.code.strip().upper()[:20]
    # Deterministic id (== code) so a document filed under this department
    # can be mirrored to Sheets and restored after a restart without a
    # code->id translation step -- see seed.py's departments loop.
    dept = Department(id=code, name=payload.name.strip(), code=code)
    db.add(dept)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A department with that name or code already exists")
    db.refresh(dept)
    audit_log(db, user_id=admin.id, action=AuditAction.DEPARTMENT_CREATED.value, detail={"department_id": dept.id, "name": dept.name})
    if sheets_store.enabled():
        try:
            sheets_sync.push_department(dept)
        except Exception:
            logger.exception("Could not mirror new department %s to Sheets.", dept.id)
    return dept
