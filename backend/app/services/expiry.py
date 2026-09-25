"""Best-effort contract/PO expiry-date detection.

This is a convenience signal for the analytics dashboard ("documents
expiring soon"), never a legal source of truth -- it always stays editable
by a human (Document.expiry_source flips to "manual" the moment someone
overrides it) and is clearly labelled as detected vs. confirmed everywhere
it's shown.
"""
from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateparser

_KEYWORD_WINDOW = re.compile(
    r"(valid\s+(?:until|through|till)|expir(?:y|es|ation)(?:\s+date)?|end\s+date|termination\s+date|"
    r"contract\s+period\s+(?:ends|until))\s*[:\-]?\s*([A-Za-z0-9,./\- ]{6,40})",
    re.IGNORECASE,
)

def detect_expiry_date(full_text: str) -> datetime | None:
    candidates: list[datetime] = []
    for match in _KEYWORD_WINDOW.finditer(full_text):
        raw = match.group(2).strip().split("\n")[0]
        raw = re.split(r"\s{2,}|(?<=\d)\s+(?=[A-Za-z]{4,}\b(?!\s*\d))", raw)[0]
        try:
            dt = dateparser.parse(raw, fuzzy=True, dayfirst=True, default=datetime(1900, 1, 1))
        except (ValueError, OverflowError):
            continue
        if dt and dt.year > 1999 and dt.year < 2100:
            candidates.append(dt)
    if not candidates:
        return None
    future = [d for d in candidates if d >= datetime.utcnow()]
    return min(future) if future else max(candidates)
