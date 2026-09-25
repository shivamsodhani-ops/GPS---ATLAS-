"""
Central configuration for GPS ATLAS.

All secrets/behaviour switches are read from environment variables (with safe
local defaults) so the same codebase runs:
  - fully offline on a laptop with zero external dependencies, and
  - with a hosted LLM plugged in, just by setting an API key.

Nothing here should ever be hard-coded elsewhere in the app -- read settings
from this module so the whole security posture stays auditable in one place.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


def _default_secret() -> str:
    # In production you MUST set ATLAS_SECRET_KEY yourself (see .env.example).
    # We generate a random one per-process as a safe fallback so the app never
    # ships with a known, guessable default secret baked into source control.
    return secrets.token_urlsafe(48)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATLAS_", env_file=".env", extra="ignore")

    app_name: str = "GPS ATLAS"
    environment: str = "development"  # development | production

    # --- storage locations -------------------------------------------------
    data_dir: Path = BASE_DIR / "data"
    storage_dir: Path = BASE_DIR / "storage"          # encrypted originals live here
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'atlas.db'}"

    # --- security ------------------------------------------------------------
    secret_key: str = _default_secret()
    file_encryption_key: str | None = None  # base64 Fernet key; auto-generated & persisted if unset
    access_token_expire_minutes: int = 60 * 8       # 8h shift
    refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    bcrypt_rounds: int = 12
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15
    max_upload_mb: int = 100

    # --- seed / bootstrap ------------------------------------------------------
    seed_admin_email: str = "admin@gpsrenewables.com"
    seed_admin_password: str = "ChangeMe!2026"  # you MUST change this after first login
    seed_demo_data: bool = True

    # --- retrieval ------------------------------------------------------------
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 150
    top_k_chunks: int = 8
    near_duplicate_threshold: float = 0.92

    # --- AI provider chain (tried in this order, first available wins) --------
    # "hosted" needs one of OPENAI_API_KEY / ANTHROPIC_API_KEY / AZURE_OPENAI_API_KEY
    # "ollama" needs a reachable Ollama server (OLLAMA_HOST)
    # "extractive" always works -- zero dependencies, zero network, zero hallucination risk
    ai_provider_order: str = "hosted,ollama,extractive"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.storage_dir.mkdir(parents=True, exist_ok=True)


def get_or_create_file_encryption_key() -> bytes:
    """Persist the Fernet key used to encrypt documents at rest.

    Generated once on first run and stored outside the database so that a
    stolen DB file alone never yields plaintext documents. In production,
    point ATLAS_FILE_ENCRYPTION_KEY at a secret manager instead of the local
    file fallback used here for a zero-config local demo.
    """
    if settings.file_encryption_key:
        return settings.file_encryption_key.encode()

    key_path = settings.data_dir / ".file_key"
    if key_path.exists():
        return key_path.read_bytes().strip()

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key
