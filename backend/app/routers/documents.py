from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import can_view_document, get_client_ip, get_current_user
from ..models import (
    AuditAction,
    Department,
    Document,
    DocumentAccessGrant,
    DocumentStatus,
    DocumentVersion,
    Role,
    User,
)
from ..schemas import AccessGrantRequest, DocumentOut, DocumentVersionOut
from ..services import duplicates, ingestion
from ..services.storage import read_decrypted
from ..utils.audit import log as audit_log

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _doc_out(db: Session, doc: Document, user: User) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        doc_type=doc.doc_type,
        description=doc.description,
        tags=json.loads(doc.tags or "[]"),
        department_id=doc.department_id,
        department_name=doc.department.name if doc.department else "",
        allowed_department_ids=json.loads(doc.allowed_department_ids or "[]"),
        allowed_roles=json.loads(doc.allowed_roles or "[]"),
        uploader_id=doc.uploader_id,
        uploader_name=doc.uploader.name if doc.uploader else "",
        status=doc.status.value if hasattr(doc.status, "value") else doc.status,
        current_version_id=doc.current_version_id,
        version_count=len(doc.versions),
        expiry_date=doc.expiry_date,
        expiry_source=doc.expiry_source,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        can_download=can_view_document(db, user, doc),
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    department_id: str | None = None,
    doc_type: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Document).filter(Document.status != DocumentStatus.ARCHIVED)
    if department_id:
        query = query.filter(Document.department_id == department_id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    if q:
        query = query.filter(Document.title.ilike(f"%{q}%"))

    docs = query.order_by(Document.updated_at.desc()).all()
    visible = [d for d in docs if can_view_document(db, user, d)]
    return [_doc_out(db, d, user) for d in visible]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.get(Document, document_id)
    if not doc or not can_view_document(db, user, doc):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return _doc_out(db, doc, user)


@router.get("/{document_id}/versions", response_model=list[DocumentVersionOut])
def list_versions(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.get(Document, document_id)
    if not doc or not can_view_document(db, user, doc):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc.versions


@router.post("", response_model=DocumentOut)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form(...),
    department_id: str = Form(...),
    description: str = Form(""),
    tags: str = Form("[]"),  # JSON-encoded list[str]
    allowed_department_ids: str = Form("[]"),
    allowed_roles: str = Form("[]"),
    supersedes_document_id: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == Role.EMPLOYEE and department_id != user.department_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only upload documents into your own department")

    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown department")

    raw_bytes = await file.read()
    if len(raw_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File exceeds the {settings.max_upload_mb}MB limit")
    if not raw_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")

    storage_path, sha256 = ingestion.store_upload(raw_bytes, file.filename or "upload.bin")

    # --- new version of an existing document, or a brand new document ------
    if supersedes_document_id:
        doc = db.get(Document, supersedes_document_id)
        if not doc or not can_view_document(db, user, doc):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document to supersede not found")
        next_version_number = len(doc.versions) + 1
    else:
        doc = Document(
            title=title.strip(),
            doc_type=doc_type.strip(),
            description=description,
            tags=json.dumps(json.loads(tags or "[]")),
            department_id=department_id,
            allowed_department_ids=json.dumps(json.loads(allowed_department_ids or "[]")),
            allowed_roles=json.dumps(json.loads(allowed_roles or "[]")),
            uploader_id=user.id,
        )
        db.add(doc)
        db.flush()
        next_version_number = 1

    exact_dup = duplicates.find_exact_duplicate(db, sha256, exclude_document_id=doc.id)

    version = DocumentVersion(
        document_id=doc.id,
        version_number=next_version_number,
        original_filename=file.filename or "upload.bin",
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(raw_bytes),
        storage_path=storage_path,
        sha256=sha256,
        uploaded_by=user.id,
    )
    db.add(version)
    db.flush()

    doc.current_version_id = version.id
    doc.status = DocumentStatus.ACTIVE
    db.commit()
    db.refresh(version)
    db.refresh(doc)

    ingestion.process_new_version(db, doc, version, raw_bytes)

    audit_log(
        db,
        user_id=user.id,
        action=AuditAction.UPLOAD.value if next_version_number == 1 else AuditAction.NEW_VERSION.value,
        document_id=doc.id,
        detail={
            "version": next_version_number,
            "filename": version.original_filename,
            "exact_duplicate_of_version": exact_dup.id if exact_dup else None,
        },
        ip_address=get_client_ip(request),
    )

    db.refresh(doc)
    return _doc_out(db, doc, user)


@router.get("/{document_id}/download")
def download_document(document_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from fastapi.responses import Response

    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if not can_view_document(db, user, doc):
        audit_log(db, user_id=user.id, action=AuditAction.ACCESS_DENIED.value, document_id=doc.id, ip_address=get_client_ip(request))
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this document")

    version = db.get(DocumentVersion, doc.current_version_id) if doc.current_version_id else None
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file available for this document")

    raw = read_decrypted(version.storage_path)
    audit_log(db, user_id=user.id, action=AuditAction.DOWNLOAD_DOCUMENT.value, document_id=doc.id, ip_address=get_client_ip(request))
    return Response(
        content=raw,
        media_type=version.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{version.original_filename}"'},
    )


@router.post("/{document_id}/grants")
def grant_access(document_id: str, payload: AccessGrantRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if user.role == Role.EMPLOYEE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only managers/admins can grant document access")
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    existing = (
        db.query(DocumentAccessGrant)
        .filter(DocumentAccessGrant.document_id == document_id, DocumentAccessGrant.user_id == payload.user_id)
        .first()
    )
    if not existing:
        db.add(DocumentAccessGrant(document_id=document_id, user_id=payload.user_id, granted_by=user.id))
        db.commit()
    audit_log(
        db,
        user_id=user.id,
        action=AuditAction.ACCESS_GRANT_CHANGED.value,
        document_id=document_id,
        detail={"granted_to": payload.user_id},
    )
    return {"ok": True}


@router.delete("/{document_id}")
def archive_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if user.role == Role.EMPLOYEE and doc.uploader_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the uploader, a manager, or an admin can archive this document")
    doc.status = DocumentStatus.ARCHIVED
    db.commit()
    audit_log(db, user_id=user.id, action=AuditAction.DOCUMENT_ARCHIVED.value, document_id=doc.id)
    return {"ok": True}
