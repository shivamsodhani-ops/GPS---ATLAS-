from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import AuditLog


def log(
    db: Session,
    *,
    user_id: str | None,
    action: str,
    document_id: str | None = None,
    detail: dict | None = None,
    ip_address: str = "",
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            document_id=document_id,
            detail=json.dumps(detail or {}),
            ip_address=ip_address,
        )
    )
    db.commit()
