from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Role(str, enum.Enum):
    ADMIN = "admin"          # sees everything, manages users/departments
    MANAGER = "manager"      # sees own department(s) + any cross-department grants
    EMPLOYEE = "employee"    # sees own department(s) only, plus explicit grants


class DocumentStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"   # an older version of a doc that now has a newer version
    ARCHIVED = "archived"


class AuditAction(str, enum.Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    UPLOAD = "upload"
    NEW_VERSION = "new_version"
    VIEW_DOCUMENT = "view_document"
    DOWNLOAD_DOCUMENT = "download_document"
    SEARCH = "search"
    ACCESS_DENIED = "access_denied"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    DEPARTMENT_CREATED = "department_created"
    DOCUMENT_ARCHIVED = "document_archived"
    ACCESS_GRANT_CHANGED = "access_grant_changed"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="department")
    documents: Mapped[list["Document"]] = relationship(back_populates="department")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.EMPLOYEE, nullable=False)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    department: Mapped[Department | None] = relationship(back_populates="users")


class Document(Base):
    """A logical document (e.g. 'Vendor XYZ Supply Agreement'). The actual
    bytes + text live in DocumentVersion rows so full version history is kept.
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(60), nullable=False)  # contract, PO, drawing, report, MOM, datasheet, ...
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str]

    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"), nullable=False)
    allowed_department_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str] extra depts granted view
    allowed_roles: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str], e.g. ["manager"] -> all managers org-wide

    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.ACTIVE)
    current_version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expiry_source: Mapped[str] = mapped_column(String(20), default="none")  # none | detected | manual

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department: Mapped[Department] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", order_by="DocumentVersion.version_number")
    access_grants: Mapped[list["DocumentAccessGrant"]] = relationship(back_populates="document")
    uploader: Mapped["User"] = relationship(foreign_keys=[uploader_id])


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_doc_version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(400), nullable=False)  # encrypted blob on disk
    sha256: Mapped[str] = mapped_column(String(64), index=True)

    extracted_chars: Mapped[int] = mapped_column(Integer, default=0)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|ok|failed|empty
    extraction_error: Mapped[str] = mapped_column(Text, default="")
    near_duplicate_of_version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    near_duplicate_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Set once this version's raw bytes have been mirrored to the Drive
    # folder (see services/sheets_sync.py). Lets the app rebuild this row
    # from Sheets+Drive after a restart wipes local disk, and lets a later
    # metadata-only update (e.g. archiving) re-push the full Sheets row
    # without needing to re-read the file first.
    drive_file_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="version", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # float32 vector, packed

    version: Mapped[DocumentVersion] = relationship(back_populates="chunks")


class DocumentAccessGrant(Base):
    """Explicit, per-document, per-user override -- e.g. give one Finance
    analyst read access to a single Legal contract without opening the whole
    Legal department. Optional layer on top of the primary role+department
    model; used sparingly.
    """

    __tablename__ = "document_access_grants"
    __table_args__ = (UniqueConstraint("document_id", "user_id", name="uq_doc_user_grant"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    granted_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="access_grants")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")  # JSON blob, free-form
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
