from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin, require_manager_or_admin
from ..models import AuditLog, Department, Document, DocumentVersion, Role, User
from ..schemas import AnalyticsOut, AuditLogOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-logs", response_model=list[AuditLogOut])
def audit_logs(
    limit: int = Query(200, le=1000),
    action: str | None = None,
    user_id: str | None = None,
    document_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if document_id:
        query = query.filter(AuditLog.document_id == document_id)

    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    users = {u.id: u.name for u in db.query(User).all()}
    docs = {d.id: d.title for d in db.query(Document).all()}

    return [
        AuditLogOut(
            id=r.id,
            user_id=r.user_id,
            user_name=users.get(r.user_id) if r.user_id else None,
            action=r.action,
            document_id=r.document_id,
            document_title=docs.get(r.document_id) if r.document_id else None,
            detail=r.detail,
            ip_address=r.ip_address,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/analytics", response_model=AnalyticsOut)
def analytics(db: Session = Depends(get_db), user: User = Depends(require_manager_or_admin)):
    doc_query = db.query(Document).filter(Document.status == "active")
    if user.role == Role.MANAGER and user.department_id:
        doc_query = doc_query.filter(Document.department_id == user.department_id)
    docs = doc_query.all()

    dept_names = {d.id: d.name for d in db.query(Department).all()}
    by_dept: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    near_dup_flags = 0
    expiring_soon: list[dict] = []
    now = datetime.utcnow()

    total_storage = 0
    version_count = 0
    for doc in docs:
        by_dept[dept_names.get(doc.department_id, "Unknown")] += 1
        by_type[doc.doc_type] += 1
        for v in doc.versions:
            version_count += 1
            total_storage += v.file_size_bytes
            if v.near_duplicate_of_version_id:
                near_dup_flags += 1
        if doc.expiry_date and now <= doc.expiry_date <= now + timedelta(days=60):
            expiring_soon.append(
                {
                    "document_id": doc.id,
                    "title": doc.title,
                    "expiry_date": doc.expiry_date.isoformat(),
                    "source": doc.expiry_source,
                    "days_remaining": (doc.expiry_date - now).days,
                }
            )
    expiring_soon.sort(key=lambda x: x["days_remaining"])

    uploads_by_day: Counter[str] = Counter()
    version_query = db.query(DocumentVersion).filter(DocumentVersion.uploaded_at >= now - timedelta(days=30))
    for v in version_query.all():
        uploads_by_day[v.uploaded_at.strftime("%Y-%m-%d")] += 1

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.last_login_at >= now - timedelta(days=30)).count()

    return AnalyticsOut(
        total_documents=len(docs),
        total_versions=version_count,
        total_storage_bytes=total_storage,
        documents_by_department=dict(by_dept),
        documents_by_type=dict(by_type),
        uploads_last_30_days=dict(sorted(uploads_by_day.items())),
        documents_expiring_soon=expiring_soon,
        near_duplicate_flags=near_dup_flags,
        total_users=total_users,
        active_users_last_30_days=active_users,
    )
