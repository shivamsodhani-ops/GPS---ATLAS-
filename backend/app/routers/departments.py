from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import AuditAction, Department, User
from ..schemas import DepartmentCreate, DepartmentOut
from ..utils.audit import log as audit_log

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Department).order_by(Department.name).all()


@router.post("", response_model=DepartmentOut)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    dept = Department(name=payload.name.strip(), code=payload.code.strip().upper())
    db.add(dept)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A department with that name or code already exists")
    db.refresh(dept)
    audit_log(db, user_id=admin.id, action=AuditAction.DEPARTMENT_CREATED.value, detail={"department_id": dept.id, "name": dept.name})
    return dept
