from __future__ import annotations

import json

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .database import get_db
from .models import Document, DocumentAccessGrant, Role, User
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled or not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user


def require_manager_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in (Role.ADMIN, Role.MANAGER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager or admin privileges required")
    return user


# ---------------------------------------------------------------------------
# Core authorization logic for documents ("Viewer ID" enforcement)
# ---------------------------------------------------------------------------
def _json_list(raw: str) -> list[str]:
    try:
        val = json.loads(raw or "[]")
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def can_view_document(db: Session, user: User, document: Document) -> bool:
    """Single source of truth for the Viewer ID model. EVERY read path
    (search, ask, download, metadata) must call this -- never trust a client
    supplied document id without re-checking here, and never filter access
    on the frontend only.
    """
    if user.role == Role.ADMIN:
        return True
    if document.department_id == user.department_id and user.department_id is not None:
        return True
    if user.department_id and user.department_id in _json_list(document.allowed_department_ids):
        return True
    if user.role.value in _json_list(document.allowed_roles):
        return True
    grant = (
        db.query(DocumentAccessGrant)
        .filter(DocumentAccessGrant.document_id == document.id, DocumentAccessGrant.user_id == user.id)
        .first()
    )
    return grant is not None


def accessible_document_filter(db: Session, user: User):
    """Returns a SQLAlchemy filter expression restricting a Document query to
    only rows `user` is authorized to see. Applied BEFORE any ranking/limit
    so an unauthorized document is never even scored, let alone returned.
    """
    if user.role == Role.ADMIN:
        return None  # no filter -- sees everything

    granted_doc_ids = [
        row.document_id
        for row in db.query(DocumentAccessGrant.document_id).filter(DocumentAccessGrant.user_id == user.id).all()
    ]

    conditions = []
    if user.department_id:
        conditions.append(Document.department_id == user.department_id)
        # allowed_department_ids is a JSON text column; SQLite has no native JSON
        # contains operator we can index on cheaply, so we match on the
        # substring-safe quoted id. This is fine at hackathon/demo scale; at
        # larger scale, replace with a proper join table (see README).
        conditions.append(Document.allowed_department_ids.like(f'%"{user.department_id}"%'))
    conditions.append(Document.allowed_roles.like(f'%"{user.role.value}"%'))
    if granted_doc_ids:
        conditions.append(Document.id.in_(granted_doc_ids))

    return or_(*conditions) if conditions else Document.id == "__none__"
