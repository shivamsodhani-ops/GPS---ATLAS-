from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from .extraction import PageText


@dataclass
class TextChunk:
    index: int
    text: str
    page_number: int | None


def chunk_pages(pages: list[PageText]) -> list[TextChunk]:
    size = settings.chunk_size_chars
    overlap = settings.chunk_overlap_chars
    chunks: list[TextChunk] = []
    idx = 0

    for page in pages:
        text = " ".join(page.text.split())  # normalize whitespace
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            piece = text[start:end]
            # avoid cutting mid-word where cheap to do so
            if end < len(text):
                last_space = piece.rfind(" ")
                if last_space > size * 0.6:
                    piece = piece[:last_space]
                    end = start + last_space
            chunks.append(TextChunk(index=idx, text=piece.strip(), page_number=page.page_number))
            idx += 1
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)

    return [c for c in chunks if c.text]
