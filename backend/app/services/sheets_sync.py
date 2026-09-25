"""Bridges GPS ATLAS's local SQLAlchemy models to the Sheets+Drive store in
`sheets_store`. Two directions:

  * push_*    -- called right after a local write (new user, new document,
                 a password change, ...) to mirror that row into the Sheet
                 (and, for documents, the raw file into Drive) so it
                 survives the next restart. Best-effort: never raises.
  * restore_* -- called once at startup, before the usual demo-data seed
                 step, to pull those rows back and rebuild the local SQLite
                 DB (which Render's free tier wipes on every
                 restart/redeploy) -- including re-running text
                 extraction/chunking/embedding for documents, since chunks
                 and embeddings themselves are never stored in the Sheet
                 (impractical at scale, and easy to regenerate from the
                 original file).

Department, User and Document ids are deterministic/stable across a
restart -- a Department's id IS its code (see seed.py/routers/departments.py),
and User/Document ids are minted once and round-tripped verbatim -- so
restoring never has to translate a code or email back into a fresh id: it
just re-inserts rows using the ids the Sheet already has as real primary
keys again.

Known, deliberate limitations (kept simple on purpose): only the CURRENT
version of each document is mirrored/restored, not its older version
history; the audit log and per-document access grants aren't mirrored at
all. None of this is needed for the core ask -- documents and users
surviving a restart, with search/Ask ATLAS working against them -- and
skipping it keeps this fast and avoids piling requests onto the Apps
Script's free quota.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Department, Document, DocumentStatus, DocumentVersion, Role, User
from . import ingestion, sheets_store

logger = logging.getLogger("atlas.sheets_sync")


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def _bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("true", "1", "yes")


def push_department(dept: Department) -> None:
    sheets_store.upsert_row(
        "Departments",
        {"id": dept.id, "name": dept.name, "code": dept.code, "created_at": _iso(dept.created_at)},
    )


def push_user(user: User) -> None:
    sheets_store.upsert_row(
        "Users",
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "password_hash": user.hashed_password,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
            "department_id": user.department_id or "",
            "is_active": bool(user.is_active),
            "must_change_password": bool(user.must_change_password),
            "created_at": _iso(user.created_at),
            "updated_at": _iso(datetime.utcnow()),
        },
    )


def _document_row(doc: Document, version: DocumentVersion | None) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "description": doc.description,
        "tags_json": doc.tags,
        "department_id": doc.department_id,
        "allowed_department_ids_json": doc.allowed_department_ids,
        "allowed_roles_json": doc.allowed_roles,
        "uploader_id": doc.uploader_id,
        "status": doc.status.value if hasattr(doc.status, "value") else doc.status,
        "expiry_date": _iso(doc.expiry_date),
        "expiry_source": doc.expiry_source,
        "drive_file_id": (version.drive_file_id if version else "") or "",
        "original_filename": version.original_filename if version else "",
        "mime_type": version.mime_type if version else "",
        "sha256": version.sha256 if version else "",
        "created_at": _iso(doc.created_at),
        "updated_at": _iso(doc.updated_at),
    }


def push_document_in_background(document_id: str, version_id: str, raw_bytes: bytes) -> None:
    db = SessionLocal()
    try:
        version = db.get(DocumentVersion, version_id)
        doc = db.get(Document, document_id) if version else None
        if not version or not doc:
            logger.error("push_document_in_background: document/version %s/%s vanished", document_id, version_id)
            return
        if not version.drive_file_id:
            file_id = sheets_store.upload_file(version.original_filename, version.mime_type, raw_bytes)
            if file_id:
                version.drive_file_id = file_id
                db.commit()
                db.refresh(version)
        sheets_store.upsert_row("Documents", _document_row(doc, version))
    except Exception:  # noqa: BLE001 -- best-effort background sync, never raise
        logger.exception("Sheets sync failed for document %s", document_id)
    finally:
        db.close()


def push_document_status(doc: Document) -> None:
    version = next((v for v in doc.versions if v.id == doc.current_version_id), None)
    sheets_store.upsert_row("Documents", _document_row(doc, version))


def restore_departments(db: Session) -> None:
    for row in sheets_store.list_rows("Departments"):
        code = (row.get("code") or "").strip()
        if not code:
            continue
        if db.get(Department, code) is None:
            db.add(Department(id=code, name=row.get("name") or code, code=code))
    db.commit()


def restore_users(db: Session) -> None:
    dept_ids = {d.id for d in db.query(Department).all()}
    for row in sheets_store.list_rows("Users"):
        uid = row.get("id")
        email = (row.get("email") or "").strip().lower()
        if not uid or not email:
            continue
        dept_id = row.get("department_id") or None
        if dept_id and dept_id not in dept_ids:
            dept_id = None
        try:
            role = Role(row.get("role") or "employee")
        except ValueError:
            role = Role.EMPLOYEE

        existing = db.get(User, uid)
        if existing is None:
            db.add(
                User(
                    id=uid,
                    name=row.get("name") or email,
                    email=email,
                    hashed_password=row.get("password_hash") or "",
                    role=role,
                    department_id=dept_id,
                    is_active=_bool(row.get("is_active"), True),
                    must_change_password=_bool(row.get("must_change_password"), False),
                )
            )
        else:
            existing.name = row.get("name") or existing.name
            existing.hashed_password = row.get("password_hash") or existing.hashed_password
            existing.role = role
            existing.department_id = dept_id
            existing.is_active = _bool(row.get("is_active"), existing.is_active)
            existing.must_change_password = _bool(row.get("must_change_password"), existing.must_change_password)
    db.commit()


def restore_documents(db: Session) -> None:
    dept_ids = {d.id for d in db.query(Department).all()}
    user_ids = {u.id for u in db.query(User).all()}
    fallback_uploader = db.query(User).filter(User.role == Role.ADMIN).first()

    for row in sheets_store.list_rows("Documents"):
        doc_id = row.get("id")
        if not doc_id or db.get(Document, doc_id) is not None:
            continue

        drive_file_id = row.get("drive_file_id")
        dept_id = row.get("department_id")
        if not drive_file_id or dept_id not in dept_ids:
            logger.warning("Skipping restore of document %s: missing Drive file or unknown department", doc_id)
            continue

        raw_bytes = sheets_store.download_file(drive_file_id)
        if raw_bytes is None:
            logger.warning("Skipping restore of document %s: could not download %s from Drive", doc_id, drive_file_id)
            continue

        uploader_id = row.get("uploader_id")
        if uploader_id not in user_ids:
            uploader_id = fallback_uploader.id if fallback_uploader else None
        if not uploader_id:
            logger.warning("Skipping restore of document %s: no uploader to attribute it to", doc_id)
            continue

        try:
            status = DocumentStatus(row.get("status") or "active")
        except ValueError:
            status = DocumentStatus.ACTIVE

        doc = Document(
            id=doc_id,
            title=row.get("title") or "Untitled document",
            doc_type=row.get("doc_type") or "other",
            description=row.get("description") or "",
            tags=row.get("tags_json") or "[]",
            department_id=dept_id,
            allowed_department_ids=row.get("allowed_department_ids_json") or "[]",
            allowed_roles=row.get("allowed_roles_json") or "[]",
            uploader_id=uploader_id,
            status=status,
            expiry_source=row.get("expiry_source") or "none",
        )
        expiry_str = row.get("expiry_date")
        if expiry_str:
            try:
                doc.expiry_date = datetime.fromisoformat(expiry_str)
            except ValueError:
                pass
        db.add(doc)
        db.flush()

        filename = row.get("original_filename") or f"{doc.title}.bin"
        storage_path, sha256 = ingestion.store_upload(raw_bytes, filename)
        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            original_filename=filename,
            mime_type=row.get("mime_type") or "application/octet-stream",
            file_size_bytes=len(raw_bytes),
            storage_path=storage_path,
            sha256=sha256,
            uploaded_by=uploader_id,
            drive_file_id=drive_file_id,
        )
        db.add(version)
        db.flush()
        doc.current_version_id = version.id
        db.commit()
        db.refresh(doc)
        db.refresh(version)

        try:
            ingestion.process_new_version(db, doc, version, raw_bytes)
        except Exception:  # noqa: BLE001 -- one bad restored file shouldn't block the rest
            logger.exception("Re-indexing failed for restored document %s", doc_id)

        user_ids.add(uploader_id)
