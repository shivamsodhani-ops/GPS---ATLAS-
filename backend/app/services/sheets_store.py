"""Free-tier persistence via a Google Apps Script Web App bound to a Google
Sheet ("GPS ATLAS Database") + a Google Drive folder ("GPS ATLAS Documents").

This exists because Render's free tier wipes local disk (the SQLite DB and
the encrypted file store) on every restart/redeploy, and a paid managed
Postgres instance needs a payment method on the account. Rather than that,
GPS ATLAS can treat a Sheet+Drive folder as a tiny external database:
lightweight metadata (departments/users/documents) lives in Sheet tabs,
original file bytes live in the Drive folder, and `services.sheets_sync`
rebuilds the local SQLite DB + search index from this on every startup. See
appsscript/Code.gs for the script that backs this and its one-time setup
steps.

Entirely optional: leave ATLAS_SHEETS_WEBAPP_URL / ATLAS_SHEETS_SECRET unset
and the app runs exactly as before, local-only, with no calls out to Google
at all (`enabled()` is checked by every function below).

Every function here is best-effort -- a failure (network hiccup, Apps
Script quota, misconfiguration) is logged and swallowed rather than raised,
so a Sheets/Drive outage never takes the rest of the app down with it.
"""
from __future__ import annotations

import base64
import logging

import httpx

from ..config import settings

logger = logging.getLogger("atlas.sheets_store")

_TIMEOUT_METADATA = 20.0
_TIMEOUT_FILE = 90.0


def enabled() -> bool:
    return bool(settings.sheets_webapp_url and settings.sheets_secret)


def _get(params: dict, timeout: float) -> dict:
    resp = httpx.get(
        settings.sheets_webapp_url,
        params={**params, "token": settings.sheets_secret},
        timeout=timeout,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json()


def _post(payload: dict, timeout: float) -> dict:
    resp = httpx.post(
        settings.sheets_webapp_url,
        json={**payload, "token": settings.sheets_secret},
        timeout=timeout,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json()


def list_rows(sheet: str) -> list[dict]:
    if not enabled():
        return []
    try:
        data = _get({"action": "list", "sheet": sheet}, _TIMEOUT_METADATA)
        if not data.get("ok"):
            logger.warning("Sheets list(%s) returned an error: %s", sheet, data.get("error"))
            return []
        return data.get("rows", [])
    except Exception:
        logger.exception("Sheets list(%s) failed", sheet)
        return []


def upsert_row(sheet: str, data: dict) -> bool:
    if not enabled():
        return False
    try:
        result = _post({"action": "upsert", "sheet": sheet, "data": data}, _TIMEOUT_METADATA)
        if not result.get("ok"):
            logger.warning("Sheets upsert(%s, %s) returned an error: %s", sheet, data.get("id"), result.get("error"))
        return bool(result.get("ok"))
    except Exception:
        logger.exception("Sheets upsert(%s, %s) failed", sheet, data.get("id"))
        return False


def delete_row(sheet: str, row_id: str) -> bool:
    if not enabled():
        return False
    try:
        result = _post({"action": "delete", "sheet": sheet, "id": row_id}, _TIMEOUT_METADATA)
        return bool(result.get("ok"))
    except Exception:
        logger.exception("Sheets delete(%s, %s) failed", sheet, row_id)
        return False


def upload_file(filename: str, mime_type: str, raw_bytes: bytes) -> str | None:
    if not enabled():
        return None
    try:
        data = _post(
            {
                "action": "upload",
                "filename": filename,
                "mimeType": mime_type,
                "base64": base64.b64encode(raw_bytes).decode("ascii"),
            },
            _TIMEOUT_FILE,
        )
        if not data.get("ok"):
            logger.warning("Sheets upload(%s) returned an error: %s", filename, data.get("error"))
            return None
        return data.get("file_id")
    except Exception:
        logger.exception("Sheets upload(%s) failed", filename)
        return None


def download_file(file_id: str) -> bytes | None:
    if not enabled():
        return None
    try:
        data = _get({"action": "download", "file_id": file_id}, _TIMEOUT_FILE)
        if not data.get("ok"):
            logger.warning("Sheets download(%s) returned an error: %s", file_id, data.get("error"))
            return None
        return base64.b64decode(data["base64"])
    except Exception:
        logger.exception("Sheets download(%s) failed", file_id)
        return None
