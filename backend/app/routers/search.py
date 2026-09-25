from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_client_ip, get_current_user
from ..models import AuditAction, User
from ..schemas import AskRequest, AskResponse, Citation, SearchHit, SearchResponse
from ..services import llm
from ..services.retrieval import retrieve, unindexed_documents
from ..utils.audit import log as audit_log

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(payload: AskRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    hits, total_accessible = retrieve(
        db, user, payload.question, top_k=15, department_ids=payload.department_ids, doc_types=payload.doc_types
    )
    audit_log(
        db,
        user_id=user.id,
        action=AuditAction.SEARCH.value,
        detail={"query": payload.question, "result_count": len(hits)},
        ip_address=get_client_ip(request),
    )
    return SearchResponse(
        hits=[
            SearchHit(
                document_id=h.document.id,
                document_title=h.document.title,
                doc_type=h.document.doc_type,
                department_name=h.document.department.name if h.document.department else "",
                version_id=h.version.id,
                chunk_id=h.chunk_id,
                score=round(h.score, 4),
                snippet=h.text[:400],
                page_number=h.page_number,
            )
            for h in hits
        ],
        total_accessible_documents=total_accessible,
    )


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..config import settings

    chunks, total_accessible = retrieve(
        db,
        user,
        payload.question,
        top_k=settings.top_k_chunks,
        department_ids=payload.department_ids,
        doc_types=payload.doc_types,
    )

    result = llm.synthesize(payload.question, chunks)

    # retrieve() only ever scores chunks that already have an embedding, so a
    # document that's still being processed, or one whose extraction failed
    # outright, contributes nothing -- silently. If *other* documents in the
    # library still have usable chunks (the seeded demo docs, say),
    # retrieve() happily answers from those instead, so the response above
    # can look complete while quietly never having read the one file the
    # question was actually about. Surface that explicitly rather than
    # leaving it looking like the AI ignored the upload.
    pending_titles, failed_titles = unindexed_documents(db, user)
    notes = []
    if pending_titles:
        names = ", ".join(f'"{t}"' for t in pending_titles[:5])
        notes.append(
            f"Still processing {names} -- this can take a few seconds (longer for scanned/image-heavy "
            "files) and isn't reflected in the answer above yet. Try asking again in a moment."
        )
    if failed_titles:
        names = ", ".join(f'"{t}"' for t in failed_titles[:5])
        notes.append(
            f"Could not extract readable text from {names} -- it exists in the library but isn't "
            "searchable. Open it in the Library to check the file isn't corrupted or a blank scan."
        )
    if notes:
        result.answer = result.answer + "\n\n" + "\n".join(notes)

    audit_log(
        db,
        user_id=user.id,
        action=AuditAction.SEARCH.value,
        detail={
            "question": payload.question,
            "provider": result.provider_used,
            "citation_count": len(result.citations),
            "unverified_count": len(result.unverified_claims),
        },
        ip_address=get_client_ip(request),
    )

    citations = [
        Citation(
            marker=c.marker,
            document_id=c.chunk.document.id,
            document_title=c.chunk.document.title,
            version_id=c.chunk.version.id,
            chunk_id=c.chunk.chunk_id,
            page_number=c.chunk.page_number,
            snippet=c.chunk.text[:400],
            verified=c.verified,
        )
        for c in result.citations
    ]

    return AskResponse(
        answer=result.answer,
        provider_used=result.provider_used,
        citations=citations,
        unverified_claims=result.unverified_claims,
        searched_document_count=total_accessible,
        denied_document_count=0,
    )
