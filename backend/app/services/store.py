
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import (
    CHECKLIST_KEYS,
    DEFAULT_REQUIRED_ATTRS,
    NON_PII,
    STORE_STATE_FILE,
    class_sensitivity,
)
from app.services import storage

STATE_VERSION = 3

_lock = threading.RLock()
inventory: Dict[str, Dict[str, Any]] = {}
scan_history: List[Dict[str, Any]] = []
scan_jobs: Dict[str, Dict[str, Any]] = {}   # in-memory only
uploads: Dict[str, Dict[str, Any]] = {}     # upload id -> {path, filename}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ─── Persistence ──────────────────────────────────────────────────────────────

def save_store() -> None:
    with _lock:
        try:
            payload = {
                "version": STATE_VERSION,
                "inventory": inventory,
                "scan_history": scan_history[-200:],
                "uploads": uploads,
            }
            storage.write_json(STORE_STATE_FILE, payload)
        except Exception as e:
            print(f"Warning: failed to save store state: {e}")


def load_store() -> None:
    try:
        data = storage.read_json(STORE_STATE_FILE)
    except Exception as e:
        print(f"Warning: failed to load store state: {e}")
        return
    if data is None:
        return
    if data.get("version") != STATE_VERSION:
        # Pre-v2 state contained hard-coded demo records; keep a backup and start clean.
        backup = STORE_STATE_FILE.with_name("store_state.legacy.json")
        storage.write_json(backup, data)
        print(f"Info: legacy store state moved to {backup.name}; starting with an empty inventory.")
        return
    inventory.update(data.get("inventory") or {})
    scan_history.extend(data.get("scan_history") or [])
    uploads.update(data.get("uploads") or {})


# ─── Status evaluation ────────────────────────────────────────────────────────

def is_pii(item: Dict[str, Any]) -> bool:
    return item.get("status") != NON_PII


def evaluate_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute status / missing attributes from the item's checklist."""
    if item.get("review_decision") == "non_pii" or item.get("class") == NON_PII:
        item["status"] = NON_PII
        item["missing_attributes"] = []
        return item
    required = item.get("required_attributes") or DEFAULT_REQUIRED_ATTRS
    item["missing_attributes"] = [k for k in required if not item.get(k)]
    item["status"] = "Evidence Gap" if item["missing_attributes"] else "Matched"
    return item


def review_label(item: Dict[str, Any]) -> str:
    decision = item.get("review_decision")
    if decision == "non_pii":
        return "Rejected as not personal data"
    if decision == "confirmed":
        return "Confirmed by reviewer"
    if item.get("detected_class") in (None, NON_PII):
        return "Not flagged"
    return "Pending review"


def _find(source: str, field: str) -> Optional[Dict[str, Any]]:
    s, f = source.lower(), field.lower()
    for item in inventory.values():
        if item["source"].lower() == s and item["field"].lower() == f:
            return item
    return None


def upsert_finding(rec: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Insert a scanner finding or update the existing record for the same (source, field)."""
    with _lock:
        existing = _find(rec["source"], rec["field"])
        ts = now_iso()
        if existing:
            keep = {
                "id": existing["id"],
                "first_seen": existing.get("first_seen", ts),
                "review_decision": existing.get("review_decision"),
                "sensitivity": existing.get("sensitivity") if existing.get("detected_class") == rec.get("detected_class") else rec.get("sensitivity"),
            }
            existing.clear()
            existing.update(rec)
            existing.update(keep)
            item, is_new = existing, False
        else:
            item = {**rec, "id": f"inv-{uuid.uuid4().hex[:8]}", "first_seen": ts, "review_decision": None}
            inventory[item["id"]] = item
            is_new = True
        item["last_seen"] = ts
        if item.get("review_decision") == "non_pii":
            item["class"] = NON_PII
        evaluate_item(item)
        item["review_status"] = review_label(item)
        return item, is_new


def apply_patch(item: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Apply reviewer edits (metadata, sensitivity, review decision)."""
    with _lock:
        for key in CHECKLIST_KEYS:
            if key in patch:
                v = patch[key]
                item[key] = (str(v).strip() or None) if v is not None else None
        if patch.get("sensitivity") in ("Critical", "High", "Medium", "Low"):
            item["sensitivity"] = patch["sensitivity"]

        decision = patch.get("review_decision")
        # Backwards compatibility with older clients that sent status/class = Non-PII
        if patch.get("status") in (NON_PII, "Non-PII") or patch.get("class") in (NON_PII, "Non-PII"):
            decision = "non_pii"
        if decision == "non_pii":
            item["review_decision"] = "non_pii"
            item["class"] = NON_PII
        elif decision in ("confirmed", "pii"):
            detected = item.get("detected_class")
            if detected in (None, NON_PII):
                raise ValueError("This field was not flagged by any rule; assign a data class via a detection rule instead.")
            item["review_decision"] = "confirmed" if decision == "confirmed" else None
            item["class"] = detected
            if item.get("sensitivity") in (None, "None"):
                item["sensitivity"] = class_sensitivity(detected)
        elif decision == "reset":
            item["review_decision"] = None
            if item.get("detected_class") not in (None, NON_PII):
                item["class"] = item["detected_class"]

        if item.get("metadata_link") in (None, "No declaration found") and any(item.get(k) for k in CHECKLIST_KEYS):
            item["metadata_link"] = "Declared by reviewer"
        item["updated_at"] = now_iso()
        evaluate_item(item)
        item["review_status"] = review_label(item)
        return item


# ─── Derived views ────────────────────────────────────────────────────────────

def gap_for(item: Dict[str, Any]) -> Dict[str, Any]:
    missing = item.get("missing_attributes", [])
    sens = class_sensitivity(item["class"])
    if sens == "Critical":
        severity = "Critical"
    elif "purpose" in missing or "retention" in missing:
        severity = "High"
    else:
        severity = "Medium"
    location = f"{item['source']}.{item['field']}"
    return {
        "id": f"gap-{item['id']}",
        "item_id": item["id"],
        "field": item["field"],
        "source": item["source"],
        "source_type": item.get("source_type"),
        "class": item["class"],
        "severity": severity,
        "missingAttributes": missing,
        "gapReason": "Missing " + ", ".join(missing),
        "recommendation": (
            f"Record the declared {' and '.join(missing)} for {location} in the metadata registry, "
            f"or mark the field as not personal data if review confirms it holds none."
        ),
        "purpose": item.get("purpose"),
        "retention": item.get("retention"),
        "owner": item.get("owner"),
        "confidence": item.get("confidence"),
        "detected_at": item.get("last_seen"),
    }


def list_gaps() -> List[Dict[str, Any]]:
    order = {"Critical": 0, "High": 1, "Medium": 2}
    with _lock:
        gaps = [gap_for(i) for i in inventory.values() if i.get("status") == "Evidence Gap"]
    return sorted(gaps, key=lambda g: (order.get(g["severity"], 3), g["source"], g["field"]))


def get_gap(gap_id: str) -> Optional[Dict[str, Any]]:
    item_id = gap_id[4:] if gap_id.startswith("gap-") else gap_id
    item = inventory.get(item_id)
    if item and item.get("status") == "Evidence Gap":
        return gap_for(item)
    return None


def stats() -> Dict[str, Any]:
    with _lock:
        items = list(inventory.values())
    pii = [i for i in items if is_pii(i)]
    matched = sum(1 for i in pii if i["status"] == "Matched")
    gaps = sum(1 for i in pii if i["status"] == "Evidence Gap")
    sources = {}
    for i in items:
        sources[i["source"]] = i.get("source_type", "csv")
    by_class: Dict[str, int] = {}
    for i in pii:
        by_class[i["class"]] = by_class.get(i["class"], 0) + 1
    return {
        "total_fields": len(items),
        "pii_fields": len(pii),
        "non_pii_fields": len(items) - len(pii),
        "matched": matched,
        "gaps": gaps,
        "coverage_pct": round(matched / len(pii) * 100) if pii else 0,
        "sources": sources,
        "by_class": by_class,
    }


def reset() -> None:
    with _lock:
        inventory.clear()
        scan_history.clear()
        save_store()


load_store()
