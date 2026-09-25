"""Orchestrates the full "Phase 1: Document Depository & Processing" pipeline
from the ATLAS flowchart: encrypt + store -> extract -> chunk -> embed ->
detect exact/near duplicates -> detect expiry date.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Chunk, Document, DocumentVersion
from . import duplicates, embeddings as emb, expiry, storage
from .chunking import chunk_pages
from .extraction import ExtractionError, extract


def sha256_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def process_new_version(db: Session, document: Document, version: DocumentVersion, raw_bytes: bytes) -> None:
    """Runs synchronously after a DocumentVersion row + encrypted blob exist.
    Kept as one call so the API layer can later move this to a background
    worker/queue without touching the pipeline logic itself.
    """
    try:
        pages = extract(version.original_filename, raw_bytes, version.mime_type)
    except ExtractionError as exc:
        version.extraction_status = "failed"
        version.extraction_error = str(exc)[:500]
        db.commit()
        return

    text_chunks = chunk_pages(pages)
    full_text = "\n".join(p.text for p in pages)
    version.extracted_chars = len(full_text)

    if not text_chunks:
        version.extraction_status = "empty"
        db.commit()
        return

    for tc in text_chunks:
        vec = emb.embed_text(tc.text)
        db.add(
            Chunk(
                version_id=version.id,
                chunk_index=tc.index,
                text=tc.text,
                page_number=tc.page_number,
                embedding=emb.pack(vec),
            )
        )
    version.extraction_status = "ok"
    db.commit()

    # --- duplicate detection ------------------------------------------------
    near = duplicates.find_near_duplicate(db, version.id, exclude_document_id=document.id)
    if near:
        version.near_duplicate_of_version_id, version.near_duplicate_score = near
        db.commit()

    # --- expiry detection (only if not already manually set) ---------------
    if document.expiry_source != "manual":
        detected = expiry.detect_expiry_date(full_text)
        if detected:
            document.expiry_date = detected
            document.expiry_source = "detected"
            db.commit()


def store_upload(raw_bytes: bytes, filename: str) -> tuple[str, str]:
    """Encrypts + persists the raw bytes. Returns (storage_path, sha256)."""
    ext = ("." + filename.rsplit(".", 1)[-1]) if "." in filename else ""
    digest = sha256_of(raw_bytes)
    path = storage.save_encrypted(raw_bytes, suggested_ext=ext)
    return path, digest
