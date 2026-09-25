"""Encrypted-at-rest file storage.

Original uploaded bytes are never written to disk in plaintext. Every file is
encrypted with a server-held Fernet key (AES-128-CBC + HMAC) before it
touches disk, and decrypted only in memory, on demand, after the caller has
already passed the Viewer ID authorization check in deps.py.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from cryptography.fernet import Fernet

from ..config import get_or_create_file_encryption_key, settings

_fernet = Fernet(get_or_create_file_encryption_key())


def save_encrypted(raw_bytes: bytes, suggested_ext: str = "") -> str:
    """Encrypts `raw_bytes` and writes it under storage_dir. Returns the
    relative storage path (safe to store in the DB)."""
    token = _fernet.encrypt(raw_bytes)
    name = f"{uuid.uuid4().hex}{suggested_ext}.enc"
    # two-level sharding so a single directory never gets unwieldy
    shard = name[:2]
    directory = settings.storage_dir / shard
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(token)
    return f"{shard}/{name}"


def read_decrypted(storage_path: str) -> bytes:
    path = settings.storage_dir / storage_path
    if not path.exists():
        raise FileNotFoundError(storage_path)
    token = path.read_bytes()
    return _fernet.decrypt(token)


def delete_file(storage_path: str) -> None:
    path = settings.storage_dir / storage_path
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
