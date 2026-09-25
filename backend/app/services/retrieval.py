"""Hybrid retrieval: BM25 (lexical/keyword) + cosine similarity over local
embeddings, scoped to only the documents the calling user is authorized to
see. Access control is applied as a SQL filter BEFORE any chunk is scored --
an unauthorized document's text never even reaches the ranking step, let
alone the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from ..deps import accessible_document_filter
from ..models import Chunk, Document, DocumentVersion, User
from . import embeddings as emb


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    page_number: int | None
    score: float
    document: Document
    version: DocumentVersion


def _candidate_documents(db: Session, user: User, department_ids: list[str], doc_types: list[str]) -> tuple[list[Document], int]:
    query = db.query(Document).filter(Document.status == "active")
    access_filter = accessible_document_filter(db, user)
    if access_filter is not None:
        query = query.filter(access_filter)

    total_accessible = query.count()

    if department_ids:
        query = query.filter(Document.department_id.in_(department_ids))
    if doc_types:
        query = query.filter(Document.doc_type.in_(doc_types))

    return query.all(), total_accessible


def retrieve(
    db: Session,
    user: User,
    query_text: str,
    top_k: int = 8,
    department_ids: list[str] | None = None,
    doc_types: list[str] | None = None,
) -> tuple[list[RetrievedChunk], int]:
    documents, total_accessible = _candidate_documents(db, user, department_ids or [], doc_types or [])
    if not documents:
        return [], total_accessible

    doc_by_id = {d.id: d for d in documents}
    current_version_ids = [d.current_version_id for d in documents if d.current_version_id]
    if not current_version_ids:
        return [], total_accessible

    versions = db.query(DocumentVersion).filter(DocumentVersion.id.in_(current_version_ids)).all()
    version_by_id = {v.id: v for v in versions}

    chunks = (
        db.query(Chunk)
        .filter(Chunk.version_id.in_(current_version_ids), Chunk.embedding.isnot(None))
        .all()
    )
    if not chunks:
        return [], total_accessible

    # --- lexical score (BM25) ------------------------------------------------
    tokenized_corpus = [emb.tokenize(c.text) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus) if any(tokenized_corpus) else None
    query_tokens = emb.tokenize(query_text)
    bm25_scores = bm25.get_scores(query_tokens) if bm25 else np.zeros(len(chunks))
    bm25_scores = np.asarray(bm25_scores, dtype=np.float32)

    # --- semantic score (cosine over local embeddings) -----------------------
    query_vec = emb.embed_text(query_text)
    cosine_scores = np.array(
        [emb.cosine(query_vec, emb.unpack(c.embedding)) for c in chunks],
        dtype=np.float32,
    )

    def _norm(arr: np.ndarray) -> np.ndarray:
        lo, hi = float(arr.min()), float(arr.max())
        if hi - lo < 1e-9:
            return np.zeros_like(arr)
        return (arr - lo) / (hi - lo)

    hybrid = 0.5 * _norm(bm25_scores) + 0.5 * _norm(cosine_scores)

    ranked_idx = np.argsort(-hybrid)[: max(top_k * 3, top_k)]  # overfetch, dedupe by doc below
    results: list[RetrievedChunk] = []
    seen_docs_count: dict[str, int] = {}
    for i in ranked_idx:
        chunk = chunks[i]
        version = version_by_id.get(chunk.version_id)
        if version is None:
            continue
        document = doc_by_id.get(version.document_id)
        if document is None:
            continue
        # cap how many chunks from a single document can dominate the answer
        if seen_docs_count.get(document.id, 0) >= 3:
            continue
        seen_docs_count[document.id] = seen_docs_count.get(document.id, 0) + 1
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                text=chunk.text,
                page_number=chunk.page_number,
                score=float(hybrid[i]),
                document=document,
                version=version,
            )
        )
        if len(results) >= top_k:
            break

    return results, total_accessible
