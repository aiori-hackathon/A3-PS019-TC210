
import threading
from typing import Any, Dict, Optional

from app.core.config import CHECKLIST_KEYS, DECLARED_METADATA_FILE, REGISTRY_CONFIG
from app.services import storage

_lock = threading.RLock()


def _key(source: str, field: str) -> str:
    return f"{str(source).strip().lower()}::{str(field).strip().lower()}"


def _clean(meta: Dict[str, Any]) -> Dict[str, Optional[str]]:
    out = {}
    for k in CHECKLIST_KEYS:
        v = meta.get(k)
        v = str(v).strip() if v is not None else ""
        out[k] = v or None
    return out


_config_decl: Dict[str, Dict[str, Optional[str]]] = {
    _key(d["source"], d["field"]): _clean(d)
    for d in (REGISTRY_CONFIG.get("declarations") or [])
    if d.get("source") and d.get("field")
}


def _load_reviewer_decl() -> Dict[str, Dict[str, Any]]:
    try:
        return storage.read_json(DECLARED_METADATA_FILE) or {}
    except Exception as e:
        print(f"Warning: could not read {DECLARED_METADATA_FILE.name}: {e}")
    return {}


_reviewer_decl: Dict[str, Dict[str, Any]] = _load_reviewer_decl()


def lookup_metadata(source: str, field: str) -> Dict[str, Any]:
    """
    Returns {purpose, retention, owner, link} where link describes how the
    metadata was linked (technical provenance for reviewers).
    """
    k = _key(source, field)
    with _lock:
        base = dict(_config_decl.get(k) or {})
        reviewer = _reviewer_decl.get(k)
    meta = {key: base.get(key) for key in CHECKLIST_KEYS}
    link = "Declared in metadata registry" if base else None
    if reviewer:
        for key in CHECKLIST_KEYS:
            if reviewer.get(key):
                meta[key] = reviewer[key]
        link = "Declared by reviewer" if not base else "Registry + reviewer declaration"
    meta["link"] = link or "No declaration found"
    return meta


def declare(source: str, field: str, meta: Dict[str, Any]) -> None:
    """Record reviewer-provided metadata so future scans link to it."""
    k = _key(source, field)
    cleaned = _clean(meta)
    with _lock:
        existing = _reviewer_decl.get(k, {})
        merged = {**existing, **{kk: vv for kk, vv in cleaned.items() if vv is not None}}
        # Explicitly cleared values are removed from the reviewer layer.
        for kk in CHECKLIST_KEYS:
            if kk in meta and not cleaned[kk]:
                merged.pop(kk, None)
        merged["source"], merged["field"] = source, field
        _reviewer_decl[k] = merged
        storage.write_json(DECLARED_METADATA_FILE, _reviewer_decl)


def reset_reviewer_declarations() -> None:
    with _lock:
        _reviewer_decl.clear()
        storage.delete_json(DECLARED_METADATA_FILE)
