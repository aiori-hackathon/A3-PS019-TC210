

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

load_dotenv() 

STRATUS_BUCKET_URL = os.getenv("STRATUS_BUCKET_URL", "").rstrip("/")
ZOHO_ACCOUNTS_URL = os.getenv("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.in").rstrip("/")
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "")


_client: Optional[httpx.Client] = None
_token_lock = threading.Lock()
_token: Dict[str, Any] = {"value": None, "expires": 0.0}


def provider() -> Optional[str]:
    if STRATUS_BUCKET_URL and ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET and ZOHO_REFRESH_TOKEN:
        return "stratus"
    if SUPABASE_URL and SUPABASE_KEY:
        return "supabase"
    return None


def enabled() -> bool:
    return provider() is not None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=60)
    return _client


def _zoho_token() -> str:
    """Return a cached OAuth access token, refreshing it shortly before it expires (1 h lifetime)."""
    with _token_lock:
        if _token["value"] and time.time() < _token["expires"] - 120:
            return _token["value"]
        r = _http().post(f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token", data={
            "refresh_token": ZOHO_REFRESH_TOKEN,
            "client_id": ZOHO_CLIENT_ID,
            "client_secret": ZOHO_CLIENT_SECRET,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        body = r.json()
        if "access_token" not in body:
            # Zoho returns 200 with {"error": ...} for bad credentials; don't log the secrets.
            raise RuntimeError(f"Zoho token refresh failed: {body.get('error', 'unknown error')}")
        _token["value"] = body["access_token"]
        _token["expires"] = time.time() + int(body.get("expires_in", 3600))
        return _token["value"]


def _request(method: str, key: str, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {})
    if provider() == "stratus":
        url = f"{STRATUS_BUCKET_URL}/{quote(key)}"
        headers["Authorization"] = f"Zoho-oauthtoken {_zoho_token()}"
    else:
        url = f"{SUPABASE_URL}/storage/v1/object/{quote(SUPABASE_BUCKET)}/{quote(key)}"
        headers.update({"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY})
    return _http().request(method, url, headers=headers, **kwargs)


# ─── Raw objects ──────────────────────────────────────────────────────────────

def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    if provider() == "stratus":
        r = _request("PUT", key, content=data, headers={"Content-Type": content_type, "overwrite": "true"})
    else:
        r = _request("POST", key, content=data, headers={"Content-Type": content_type, "x-upsert": "true"})
    r.raise_for_status()


def get_bytes(key: str) -> Optional[bytes]:
    r = _request("GET", key)
    # Missing objects come back as 404 (Stratus) or 400/404 (Supabase, depending on version).
    if r.status_code in (400, 404):
        return None
    r.raise_for_status()
    return r.content


def delete(key: str) -> None:
    if provider() == "stratus":
        # Only state files are ever deleted; overwrite with an empty object instead.
        put_bytes(key, b"{}", "application/json")
        return
    r = _request("DELETE", key)
    if r.status_code not in (200, 400, 404):
        r.raise_for_status()


# ─── Uploaded CSVs ────────────────────────────────────────────────────────────

def upload_key(upload_id: str, ext: str = ".csv") -> str:
    return f"uploads/{upload_id}{ext}"


def save_upload(upload_id: str, local_path: Path, ext: str = ".csv",
                content_type: str = "text/csv") -> Optional[str]:
    """Copy a local upload to cloud storage. Returns the storage key, or None when running locally."""
    if not enabled():
        return None
    key = upload_key(upload_id, ext)
    put_bytes(key, local_path.read_bytes(), content_type)
    return key


def ensure_local(local_path: Path, key: Optional[str]) -> bool:
    """Make sure an upload exists on local disk, downloading it from cloud storage if needed."""
    if local_path.exists():
        return True
    if not (enabled() and key):
        return False
    data = get_bytes(key)
    if data is None:
        return False
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    return True


# ─── JSON state files ─────────────────────────────────────────────────────────

def _state_key(path: Path) -> str:
    return f"state/{path.name}"


def read_json(path: Path) -> Optional[Any]:
    """Read a JSON state file from cloud storage (if enabled) or local disk. None if missing."""
    if enabled():
        data = get_bytes(_state_key(path))
        return json.loads(data.decode("utf-8")) if data is not None else None
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    text = json.dumps(obj, indent=2)
    if enabled():
        put_bytes(_state_key(path), text.encode("utf-8"), "application/json")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def delete_json(path: Path) -> None:
    if enabled():
        delete(_state_key(path))
    elif path.exists():
        path.unlink()
