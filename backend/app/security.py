from __future__ import annotations

import datetime as dt

import bcrypt
from jose import JWTError, jwt

from .config import settings

ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    # bcrypt has a hard 72-byte input limit; truncate defensively so a very
    # long pasted password can't raise instead of just being handled.
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra: dict | None = None) -> str:
    now = dt.datetime.utcnow()
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
