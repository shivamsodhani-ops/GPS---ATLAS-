from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import Role


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------
class DepartmentCreate(BaseModel):
    name: str
    code: str


class DepartmentOut(BaseModel):
    id: str
    name: str
    code: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.EMPLOYEE
    department_id: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Role] = None
    department_id: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: Role
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class DocumentCreateMeta(BaseModel):
    title: str
    doc_type: str
    description: str = ""
    tags: list[str] = []
    department_id: str
    allowed_department_ids: list[str] = []
    allowed_roles: list[str] = []
    expiry_date: Optional[datetime] = None
    supersedes_document_id: Optional[str] = None  # upload a new version of an existing doc


class DocumentVersionOut(BaseModel):
    id: str
    version_number: int
    original_filename: str
    mime_type: str
    file_size_bytes: int
    extraction_status: str
    near_duplicate_of_version_id: Optional[str] = None
    near_duplicate_score: Optional[float] = None
    uploaded_by: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: str
    title: str
    doc_type: str
    description: str
    tags: list[str]
    department_id: str
    department_name: str
    allowed_department_ids: list[str]
    allowed_roles: list[str]
    uploader_id: str
    uploader_name: str
    status: str
    current_version_id: Optional[str] = None
    version_count: int
    expiry_date: Optional[datetime] = None
    expiry_source: str
    created_at: datetime
    updated_at: datetime
    can_download: bool = True

    class Config:
        from_attributes = True


class AccessGrantRequest(BaseModel):
    user_id: str


# ---------------------------------------------------------------------------
# Search / Ask
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    department_ids: list[str] = []  # optional narrowing filter
    doc_types: list[str] = []


class Citation(BaseModel):
    marker: str  # e.g. "[1]"
    document_id: str
    document_title: str
    version_id: str
    chunk_id: str
    page_number: Optional[int] = None
    snippet: str
    verified: bool


class AskResponse(BaseModel):
    answer: str
    provider_used: str
    citations: list[Citation]
    unverified_claims: list[str]
    searched_document_count: int
    denied_document_count: int


class SearchHit(BaseModel):
    document_id: str
    document_title: str
    doc_type: str
    department_name: str
    version_id: str
    chunk_id: str
    score: float
    snippet: str
    page_number: Optional[int] = None


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    total_accessible_documents: int


# ---------------------------------------------------------------------------
# Audit / analytics
# ---------------------------------------------------------------------------
class AuditLogOut(BaseModel):
    id: str
    user_id: Optional[str]
    user_name: Optional[str]
    action: str
    document_id: Optional[str]
    document_title: Optional[str]
    detail: str
    ip_address: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyticsOut(BaseModel):
    total_documents: int
    total_versions: int
    total_storage_bytes: int
    documents_by_department: dict[str, int]
    documents_by_type: dict[str, int]
    uploads_last_30_days: dict[str, int]
    documents_expiring_soon: list[dict]
    near_duplicate_flags: int
    total_users: int
    active_users_last_30_days: int
