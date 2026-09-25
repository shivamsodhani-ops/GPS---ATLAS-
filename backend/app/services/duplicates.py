from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Chunk, Document, DocumentVersion
from . import embeddings as emb


def find_exact_duplicate(db: Session, sha256: str, exclude_document_id: str | None = None) -> DocumentVersion | None:
    query = db.query(DocumentVersion).filter(DocumentVersion.sha256 == sha256)
    if exclude_document_id:
        query = query.filter(DocumentVersion.document_id != exclude_document_id)
    return query.first()


def document_mean_embedding(db: Session, version_id: str) -> np.ndarray | None:
    chunks = db.query(Chunk).filter(Chunk.version_id == version_id, Chunk.embedding.isnot(None)).all()
    if not chunks:
        return None
    vectors = np.stack([emb.unpack(c.embedding) for c in chunks])
    return vectors.mean(axis=0)


def find_near_duplicate(
    db: Session, new_version_id: str, exclude_document_id: str
) -> tuple[str, float] | None:
    """Compares the new version's mean chunk embedding against every other
    *current* version's mean embedding. Returns (version_id, score) for the
    closest match above the configured threshold, else None.
    """
    new_vec = document_mean_embedding(db, new_version_id)
    if new_vec is None:
        return None

    other_docs = db.query(Document).filter(Document.id != exclude_document_id, Document.status == "active").all()
    best: tuple[str, float] | None = None
    for doc in other_docs:
        if not doc.current_version_id:
            continue
        other_vec = document_mean_embedding(db, doc.current_version_id)
        if other_vec is None:
            continue
        score = emb.cosine(new_vec, other_vec)
        if score >= settings.near_duplicate_threshold and (best is None or score > best[1]):
            best = (doc.current_version_id, score)
    return best
