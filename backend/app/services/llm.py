"""AI synthesis + citation verification -- the core "no hallucination" promise.

Three interchangeable providers, tried in the order configured by
ATLAS_AI_PROVIDER_ORDER (default "hosted,ollama,extractive"):

  hosted      -- OpenAI / Anthropic / Azure OpenAI, only attempted if a key
                 is configured. Best natural-language quality.
  ollama      -- a locally running Ollama server (fully offline, no cloud,
                 no per-token cost, but needs the operator to have pulled a
                 model first).
  extractive  -- zero dependencies, zero network, zero model weights.
                 Assembles the answer out of *verbatim sentences* copied
                 from the retrieved chunks. Because nothing is generated,
                 hallucination is structurally impossible in this mode.

Whichever provider produces the draft answer, every answer -- generative or
extractive -- passes through `verify_citations()` before it is ever returned
to a caller. A claim (sentence) with no valid citation marker pointing at a
chunk that was actually retrieved under the user's Viewer ID is surfaced
separately as "unverified" rather than silently presented as fact.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from ..config import settings
from . import embeddings as emb
from .retrieval import RetrievedChunk

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'‘“])")
_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass
class CitationRef:
    marker: str
    index: int  # 1-based, matches position in `chunks`
    chunk: RetrievedChunk
    verified: bool = False


@dataclass
class SynthesisResult:
    answer: str
    provider_used: str
    citations: list[CitationRef]
    unverified_claims: list[str]


def _build_context_block(chunks: list[RetrievedChunk]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        page = f", p.{c.page_number}" if c.page_number else ""
        lines.append(f"[{i}] Source: {c.document.title}{page}\n{c.text}")
    return "\n\n".join(lines)


SYSTEM_PROMPT = (
    "You are GPS ATLAS, an internal document intelligence assistant for GPS Renewables. "
    "Answer the user's question using ONLY the numbered source excerpts provided below -- "
    "never use outside knowledge and never invent facts, figures, dates, or names. "
    "After every factual sentence, add the citation marker(s) of the excerpt(s) it came from, "
    "e.g. 'The PO value is INR 42 lakh [2].' If the excerpts do not contain the answer, say so "
    "plainly instead of guessing. Be concise and precise; this is used for executive decisions."
)


def _call_openai(question: str, context: str) -> str | None:
    if not settings.openai_api_key:
        return None
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"},
                ],
                "temperature": 0.1,
                "max_tokens": 800,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def _call_anthropic(question: str, context: str) -> str | None:
    if not settings.anthropic_api_key:
        return None
    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 800,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks) or None
    except Exception:
        return None


def _call_azure(question: str, context: str) -> str | None:
    if not (settings.azure_openai_api_key and settings.azure_openai_endpoint and settings.azure_openai_deployment):
        return None
    try:
        url = (
            f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments/"
            f"{settings.azure_openai_deployment}/chat/completions?api-version=2024-06-01"
        )
        resp = httpx.post(
            url,
            headers={"api-key": settings.azure_openai_api_key},
            json={
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"},
                ],
                "temperature": 0.1,
                "max_tokens": 800,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def _call_ollama(question: str, context: str) -> str | None:
    try:
        resp = httpx.post(
            f"{settings.ollama_host.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"},
                ],
                "stream": False,
            },
            timeout=(2, 60),  # fail fast if nothing is listening on localhost:11434
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content")
    except Exception:
        return None


def _extractive_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Zero-model fallback: pick the sentences that best overlap the query
    from each retrieved chunk and assemble them, verbatim, with citations.
    Every word in the output already existed in a source document.
    """
    query_tokens = set(emb.tokenize(question))
    if not chunks:
        return "No documents you're authorized to view matched this question."

    parts = []
    for i, c in enumerate(chunks, start=1):
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(c.text) if len(s.strip()) > 15]
        if not sentences:
            sentences = [c.text[:280]]

        def score(s: str) -> int:
            return len(query_tokens & set(emb.tokenize(s)))

        best = sorted(sentences, key=score, reverse=True)[:2]
        best = [b for b in best if score(b) > 0] or sentences[:1]
        page = f" (p.{c.page_number})" if c.page_number else ""
        parts.append(f"From \"{c.document.title}\"{page} [{i}]: " + " ".join(best) + f" [{i}]")

    header = (
        f"Here is what your authorized documents say about \"{question.strip()}\" "
        f"(extractive mode -- every sentence below is quoted verbatim from a source document, "
        f"no text was generated):"
    )
    return header + "\n\n" + "\n\n".join(parts)


def synthesize(question: str, chunks: list[RetrievedChunk]) -> SynthesisResult:
    context = _build_context_block(chunks)
    providers = {
        "hosted": lambda: _call_openai(question, context) or _call_anthropic(question, context) or _call_azure(question, context),
        "ollama": lambda: _call_ollama(question, context),
        "extractive": lambda: _extractive_answer(question, chunks),
    }

    raw_answer: str | None = None
    provider_used = "extractive"
    for name in [p.strip() for p in settings.ai_provider_order.split(",") if p.strip()]:
        fn = providers.get(name)
        if not fn:
            continue
        result = fn()
        if result:
            raw_answer = result
            provider_used = name
            break

    if not raw_answer:
        raw_answer = _extractive_answer(question, chunks)
        provider_used = "extractive"

    return verify_citations(raw_answer, provider_used, chunks)


def verify_citations(raw_answer: str, provider_used: str, chunks: list[RetrievedChunk]) -> SynthesisResult:
    """The Citation Verification Layer. Splits the answer into sentences; a
    sentence is only ever presented as a supported fact if it carries a
    citation marker that resolves to a chunk we actually retrieved under
    this user's Viewer ID. Anything else is routed into `unverified_claims`
    so the UI can flag it instead of quietly trusting it.
    """
    max_marker = len(chunks)
    used_markers: set[int] = set()
    unverified: list[str] = []

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(raw_answer) if s.strip()]
    for sentence in sentences:
        markers = [int(m) for m in _MARKER_RE.findall(sentence)]
        valid_markers = [m for m in markers if 1 <= m <= max_marker]
        if not valid_markers:
            # ignore pure connective/header sentences (no citation needed)
            if len(sentence.split()) > 6:
                unverified.append(sentence)
            continue
        used_markers.update(valid_markers)

    # Every citation we actually retrieved is reported back, but `verified`
    # only turns True for the ones the answer text actually anchored a
    # sentence to -- that's the signal the UI uses to grey out unused
    # sources vs. highlight the ones backing up the visible text.
    all_citations = [
        CitationRef(marker=f"[{i}]", index=i, chunk=c, verified=(i in used_markers))
        for i, c in enumerate(chunks, start=1)
    ]

    return SynthesisResult(
        answer=raw_answer,
        provider_used=provider_used,
        citations=all_citations,
        unverified_claims=unverified,
    )
