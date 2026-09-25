"""Local, dependency-light embeddings.

Design goal: retrieval quality must never depend on internet access at query
time. We use the classic "hashing trick" (a stateless bag-of-words/bigrams
hashed into a fixed-size vector) as the guaranteed-always-available
embedding backend -- no vocabulary to fit, no model weights to download, no
drift between the index and the query encoder, and it is deterministic and
auditable.

If `sentence-transformers` is installed AND a model is already cached
locally (HF_HUB_OFFLINE=1 below means we never attempt a network call at
request time -- either the weights are already on disk from a one-time
`python -m app.services.embeddings --warm` during setup, or we silently fall
back), we transparently upgrade to real neural embeddings. Both paths
produce a fixed-length float32 vector, so nothing else in the codebase needs
to know which one is active.
"""
from __future__ import annotations

import hashlib
import os
import re
from functools import lru_cache

import numpy as np

EMBEDDING_DIM = 768
_TOKEN_RE = re.compile(r"[a-z0-9]+")

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # never let a query silently try the network
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# public alias -- other modules should use this rather than reaching into a
# "private" helper by name.
tokenize = _tokenize


def _stable_hash(token: str) -> int:
    # Python's built-in hash() is randomized per-process (PYTHONHASHSEED) for
    # strings, which would silently scramble every previously-indexed vector
    # space after a simple server restart. blake2b is deterministic across
    # processes and machines, which is what makes the index durable.
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "little")


def _hashing_embed(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    tokens = _tokenize(text)
    vec = np.zeros(dim, dtype=np.float32)
    if not tokens:
        return vec
    # unigrams + bigrams: bigrams recover some of the phrase-level meaning
    # word-hashing alone would lose (e.g. "not approved" vs "approved").
    grams = list(tokens) + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    for gram in grams:
        h = _stable_hash(gram)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    # sublinear (log) scaling tempers very repetitive chunks, then L2 normalize
    vec = np.sign(vec) * np.log1p(np.abs(vec))
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.astype(np.float32)


@lru_cache(maxsize=1)
def _neural_model():
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model
    except Exception:
        return None


def backend_name() -> str:
    return "neural (all-MiniLM-L6-v2)" if _neural_model() is not None else "hashing (offline, no external model)"


def embed_text(text: str) -> np.ndarray:
    model = _neural_model()
    if model is not None:
        try:
            vec = model.encode([text])[0]
            return np.asarray(vec, dtype=np.float32)
        except Exception:
            pass  # fall through to the always-available backend
    return _hashing_embed(text)


def pack(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)
