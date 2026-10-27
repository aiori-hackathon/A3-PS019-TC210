
import json
import re
import threading
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

import regex as regex_module
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

from app.core.config import (
    DATA_CLASSES,
    DETECTION_SETTINGS,
    RULES_CONFIG,
    RULES_STATE_FILE,
)
from app.services import storage
from app.services.validators import VALIDATORS

print("Loading Presidio NLP engine (spaCy en_core_web_lg)...")
analyzer = AnalyzerEngine()
_SUPPORTED_BUILTIN = set(analyzer.get_supported_entities("en"))

_lock = threading.RLock()
_rules: Dict[str, Dict[str, Any]] = {}   # rule id -> rule
_rules_version = 0                        # bumped on every change (used to invalidate evaluation cache)

IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,40}$")
CUSTOM_BASE_SCORE = 0.85




def _load_state() -> Dict[str, Any]:
    try:
        return storage.read_json(RULES_STATE_FILE) or {}
    except Exception as e:
        print(f"Warning: could not read {RULES_STATE_FILE.name}: {e}")
    return {}


def _save_state() -> None:
    state = {
        "enabled": {rid: r["enabled"] for rid, r in _rules.items()},
        "custom": [r for r in _rules.values() if not r.get("builtin")],
    }
    storage.write_json(RULES_STATE_FILE, state)


class ValidatedPatternRecognizer(PatternRecognizer):
    """PatternRecognizer that discards regex matches failing a checksum validator.

    Valid matches keep the pattern's own score (so weak patterns still need column
    context); invalid matches are dropped by Presidio.
    """

    def __init__(self, validator, **kwargs):
        self._validator = validator
        super().__init__(**kwargs)

    def invalidate_result(self, pattern_text: str) -> Optional[bool]:
        return not self._validator(pattern_text)


def _recognizer_name(rule: Dict[str, Any]) -> str:
    return f"privista_{rule['id']}"


def _register(rule: Dict[str, Any]) -> None:
    """Make the rule usable by the analyzer."""
    if rule["engine"] == "regex":
        patterns = [
            Pattern(name=p["name"], regex=p["regex"], score=float(p.get("score", CUSTOM_BASE_SCORE)))
            for p in rule["patterns"]
        ]
        kwargs = dict(
            supported_entity=rule["entity"],
            name=_recognizer_name(rule),
            patterns=patterns,
            context=rule.get("context") or None,
        )
        validator = rule.get("validator")
        if validator:
            if validator not in VALIDATORS:
                raise ValueError(f"unknown validator {validator!r} (known: {', '.join(VALIDATORS)})")
            recognizer = ValidatedPatternRecognizer(VALIDATORS[validator], **kwargs)
        else:
            recognizer = PatternRecognizer(**kwargs)
        analyzer.registry.add_recognizer(recognizer)
        rule["available"] = True
    else:
        
        if rule.get("validator") and rule["validator"] not in VALIDATORS:
            raise ValueError(f"unknown validator {rule['validator']!r} (known: {', '.join(VALIDATORS)})")
        rule["available"] = rule["entity"] in _SUPPORTED_BUILTIN
        if rule["available"] and rule.get("context"):
            for rec in analyzer.registry.recognizers:
                if rule["entity"] in rec.supported_entities and hasattr(rec, "context"):
                    rec.context = list(rule["context"])


def _normalise(rule: Dict[str, Any], builtin: bool) -> Dict[str, Any]:
    return {
        "id": rule["id"],
        "name": rule.get("name", rule["id"]),
        "entity": rule.get("entity", rule["id"]),
        "data_class": rule["data_class"],
        "engine": rule.get("engine", "regex"),
        "algorithm": rule.get("algorithm", "Custom Regex Pattern"),
        "patterns": rule.get("patterns", []),
        "validator": rule.get("validator"),
        "display_pattern": rule.get("display_pattern"),
        "context": [str(c).lower() for c in (rule.get("context") or [])],
        "column_keywords": [str(c).lower() for c in (rule.get("column_keywords") or [])],
        "negative_column_keywords": [str(c).lower() for c in (rule.get("negative_column_keywords") or [])],
        "min_score": float(rule.get("min_score", 0.5)),
        "enabled": bool(rule.get("enabled", True)),
        "builtin": builtin,
    }


def _init_rules() -> None:
    state = _load_state()
    for raw in RULES_CONFIG.get("rules", []):
        rule = _normalise(raw, builtin=True)
        if rule["data_class"] not in DATA_CLASSES:
            print(f"Warning: rule {rule['id']} has unknown data class {rule['data_class']!r}; skipped")
            continue
        _rules[rule["id"]] = rule
    for raw in state.get("custom", []):
        try:
            rule = _normalise(raw, builtin=False)
            if rule["id"] not in _rules and rule["data_class"] in DATA_CLASSES:
                _rules[rule["id"]] = rule
        except Exception as e:
            print(f"Warning: skipping invalid custom rule {raw!r}: {e}")
    for rid, enabled in (state.get("enabled") or {}).items():
        if rid in _rules:
            _rules[rid]["enabled"] = bool(enabled)
    for rule in _rules.values():
        try:
            _register(rule)
        except Exception as e:
            rule["available"] = False
            print(f"Warning: could not register rule {rule['id']}: {e}")


_init_rules()
print(f"Registered {len(_rules)} detection rules.")



def rules_version() -> int:
    return _rules_version


def _bump() -> None:
    global _rules_version
    _rules_version += 1


def _to_public(rule: Dict[str, Any]) -> Dict[str, Any]:
    if rule["engine"] == "regex":
        pattern = " | ".join(p["regex"] for p in rule["patterns"])
    else:
        pattern = rule.get("display_pattern") or f"Presidio {rule['entity']}"
    return {
        "id": rule["id"],
        "name": rule["name"],
        "identifier": rule["entity"],
        "category": rule["data_class"],
        "engine": rule["engine"],
        "algorithm": rule["algorithm"],
        "pattern": pattern,
        "validator": rule.get("validator"),
        "context": rule["context"],
        "columnKeywords": rule["column_keywords"],
        "negativeColumnKeywords": rule["negative_column_keywords"],
        "confidenceThreshold": round(rule["min_score"] * 100),
        "enabled": rule["enabled"],
        "builtin": rule["builtin"],
        "available": rule.get("available", False),
        "source": "config/rules.yaml" if rule["builtin"] else "custom (data/rules_state.json)",
    }


def list_rules() -> List[Dict[str, Any]]:
    with _lock:
        return [_to_public(r) for r in _rules.values()]


def get_rule(rule_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        r = _rules.get(rule_id)
        return _to_public(r) if r else None


def toggle_rule(rule_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        rule = _rules.get(rule_id)
        if not rule:
            return None
        rule["enabled"] = not rule["enabled"]
        _save_state()
        _bump()
        return _to_public(rule)


def _split_words(value: Any) -> List[str]:
    if isinstance(value, list):
        items = value
    else:
        items = str(value or "").split(",")
    return [str(i).strip().lower() for i in items if str(i).strip()]


def create_rule(payload: Dict[str, Any]) -> Dict[str, Any]:
    
    name = str(payload.get("name", "")).strip()
    identifier = str(payload.get("identifier", "")).strip().upper()
    category = str(payload.get("category", "")).strip()
    pattern = str(payload.get("pattern", "")).strip()
    threshold = payload.get("confidenceThreshold", 60)

    if not name or len(name) > 80:
        raise ValueError("Rule name is required (max 80 characters).")
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError("Identifier must be UPPER_SNAKE_CASE (letters, digits, underscore), 2-41 chars.")
    if category not in DATA_CLASSES:
        raise ValueError(f"Category must be one of: {', '.join(DATA_CLASSES)}.")
    if not pattern or len(pattern) > 500:
        raise ValueError("Regex pattern is required (max 500 characters).")
    try:
        regex_module.compile(pattern)
    except Exception as e:
        raise ValueError(f"Invalid regex pattern: {e}")
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        raise ValueError("confidenceThreshold must be a number between 30 and 99.")
    if not 30 <= threshold <= 99:
        raise ValueError("confidenceThreshold must be between 30 and 99.")

    with _lock:
        if identifier in _rules or any(r["entity"] == identifier for r in _rules.values()):
            raise ValueError(f"A rule with identifier {identifier} already exists.")
        rule = _normalise(
            {
                "id": identifier,
                "name": name,
                "entity": identifier,
                "data_class": category,
                "engine": "regex",
                "algorithm": "Custom Regex Pattern",
                "patterns": [{"name": identifier.lower(), "regex": pattern, "score": CUSTOM_BASE_SCORE}],
                "context": _split_words(payload.get("context")),
                "column_keywords": _split_words(payload.get("columnKeywords")),
                "negative_column_keywords": _split_words(payload.get("negativeColumnKeywords")),
                "min_score": threshold / 100.0,
                "enabled": True,
            },
            builtin=False,
        )
        _register(rule)
        _rules[rule["id"]] = rule
        _save_state()
        _bump()
        return _to_public(rule)


def delete_rule(rule_id: str) -> bool:
    """Delete a custom rule. Built-in rules can only be disabled. Raises PermissionError."""
    with _lock:
        rule = _rules.get(rule_id)
        if not rule:
            return False
        if rule["builtin"]:
            raise PermissionError("Built-in rules from config/rules.yaml can be disabled but not deleted.")
        try:
            analyzer.registry.remove_recognizer(_recognizer_name(rule))
        except Exception:
            pass
        del _rules[rule_id]
        _save_state()
        _bump()
        return True


def _active_rules() -> Dict[str, Dict[str, Any]]:
   
    with _lock:
        return {r["entity"]: dict(r) for r in _rules.values() if r["enabled"] and r.get("available")}


# ─── Helpers ───────────────────────────────────────────────────────────────────

def column_tokens(column_name: str) -> List[str]:
    """'customerPanNumber' / 'pan_number' -> ['customer', 'pan', 'number']"""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(column_name))
    return [t.lower() for t in re.split(r"[^A-Za-z0-9]+", s) if t]


def mask_value(value: str) -> str:
    """Mask a sample value so evidence never contains raw personal data."""
    v = str(value).strip()
    if "@" in v:
        local, _, domain = v.partition("@")
        return f"{local[:1]}***@{domain}"
    digits = sum(c.isdigit() for c in v)
    if digits >= 6:
        keep, out = 4, []
        for c in reversed(v):
            if c.isdigit():
                out.append(c if keep > 0 else "X")
                keep -= 1
            elif c.isalpha():
                out.append("X")
            else:
                out.append(c)
        return "".join(reversed(out))
    if any(c.isdigit() for c in v) and any(c.isalpha() for c in v):
        return v[:1] + "X" * max(len(v) - 2, 0) + v[-1:]
    return " ".join(w[:1] + "*" * (len(w) - 1) for w in v.split())


def sample_values(values: List[Any], n: int) -> List[str]:
    """Deterministic sample of up to n unique, non-empty string values (first-seen order)."""
    seen, out = set(), []
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "null") or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= n:
            break
    return out


def _keyword_in_column(kw: str, tokens: set, joined: str) -> bool:
    """Token match ('order_id' -> order), or prefix/suffix of a run-together name ('orderid')."""
    if kw in tokens or kw == joined:
        return True
    return len(kw) >= 4 and (joined.startswith(kw) or joined.endswith(kw))


def _excluded_entities(context: Optional[List[str]], active: Dict[str, Dict[str, Any]]) -> set:
    """Entities whose rule lists a negative column keyword present in the column name
    (e.g. a phone-shaped value in 'order_id' is an order number, not a phone)."""
    if not context:
        return set()
    tokens, joined = set(context), "".join(context)
    return {
        entity for entity, rule in active.items()
        if any(_keyword_in_column(kw, tokens, joined) for kw in rule.get("negative_column_keywords", []))
    }


def _passes(rule: Dict[str, Any], matched_text: str) -> bool:
    """Validator post-filter (used for built-in Presidio rules such as PERSON)."""
    name = rule.get("validator")
    return not name or name not in VALIDATORS or VALIDATORS[name](matched_text)


def _accepted_results(text: str, results: List[Any], rules: Dict[str, Dict[str, Any]]) -> List[Any]:
    """Results that pass their rule's validator and min_score, minus results nested in a larger match.

    A match lying strictly inside a longer match of a different class is part of that longer value
    (a name inside an address, the digits before '@' in a UPI ID), so it is dropped. The longer match
    counts even when it is below its own threshold: '9876543210@somebank' is not a phone number, even
    if the UPI rule alone is not confident enough to report it.
    """
    valid = [r for r in results if r.entity_type in rules and _passes(rules[r.entity_type], text[r.start:r.end])]

    def nested(r: Any) -> bool:
        cls = rules[r.entity_type]["data_class"]
        return any(
            o is not r and rules[o.entity_type]["data_class"] != cls
            and o.start <= r.start and o.end >= r.end and (o.end - o.start) > (r.end - r.start)
            for o in valid
        )

    return [r for r in valid if r.score >= rules[r.entity_type]["min_score"] and not nested(r)]


def analyze_text(text: str, context: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Run all enabled rules on free text. Used by the rule sandbox."""
    active = _active_rules()
    for entity in _excluded_entities(context, active):
        del active[entity]
    if not text or not active:
        return []
    results = analyzer.analyze(
        text=text, language="en", entities=list(active.keys()),
        context=context or None, return_decision_process=True,
    )
    out = []
    for res in _accepted_results(text, results, active):
        rule = active[res.entity_type]
        out.append({
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "entity": res.entity_type,
            "data_class": rule["data_class"],
            "text": text[res.start:res.end],
            "start": res.start,
            "end": res.end,
            "score": round(float(res.score), 2),
        })
    return sorted(out, key=lambda r: r["start"])


# ─── Column analysis ───────────────────────────────────────────────────────────

def _column_hint(column_name: str, active: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    tokens = set(column_tokens(column_name))
    joined = "".join(column_tokens(column_name))
    excluded = _excluded_entities(column_tokens(column_name), active)
    for rule in active.values():
        if rule["entity"] in excluded:  # e.g. 'plan_name' is not a person-name column
            continue
        for kw in rule["column_keywords"]:
            if kw in tokens or kw == joined:
                return rule
    return None


def analyze_column(
    column_name: str,
    values: List[Any],
    on_value: Optional[Callable[[str, Optional[str]], None]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Analyse sampled values of one column.
    Returns detection evidence for the dominant data class, or None if no rule matched.

    on_value (optional, used by the evaluation): called once per sampled value with the
    class that value would get if it were scanned on its own under this column name
    (best-scoring match, else the column-name hint, else None).
    """
    active = _active_rules()
    if not active:
        return None

    sample = sample_values(values, int(DETECTION_SETTINGS["sample_size"]))
    min_ratio = float(DETECTION_SETTINGS["min_match_ratio"])
    context = column_tokens(column_name)
    value_rules = {e: r for e, r in active.items() if e not in _excluded_entities(context, active)}
    hint_rule = _column_hint(column_name, active) if on_value and DETECTION_SETTINGS.get("column_name_hints") else None

    stats: Dict[str, Dict[str, Any]] = {}
    if on_value and not value_rules:
        for val in sample:
            on_value(val, hint_rule["data_class"] if hint_rule else None)
    for val in sample if value_rules else []:
        results = analyzer.analyze(
            text=val, language="en", entities=list(value_rules.keys()),
            context=context or None, return_decision_process=True,
        )
        best: Dict[str, Any] = {}
        for res in _accepted_results(val, results, value_rules):
            cls = value_rules[res.entity_type]["data_class"]
            if cls not in best or res.score > best[cls].score:
                best[cls] = res
        if on_value:
            top = max(best, key=lambda k: best[k].score) if best else None
            on_value(val, top or (hint_rule["data_class"] if hint_rule else None))
        for cls, res in best.items():
            s = stats.setdefault(cls, {"hits": 0, "scores": [], "entities": Counter(), "examples": [], "boosted": 0})
            s["hits"] += 1
            s["scores"].append(float(res.score))
            s["entities"][res.entity_type] += 1
            expl = getattr(res, "analysis_explanation", None)
            if expl is not None and (getattr(expl, "score_context_improvement", 0) or 0) > 0:
                s["boosted"] += 1
            if len(s["examples"]) < 2:
                s["examples"].append(mask_value(val))

    n = len(sample)
    candidates = []
    for cls, s in stats.items():
        ratio = s["hits"] / n
        mean = sum(s["scores"]) / len(s["scores"])
        if ratio >= min_ratio:
            candidates.append((ratio * mean, cls, ratio, mean, s))

    if candidates:
        _, cls, ratio, mean, s = max(candidates, key=lambda c: c[0])
        entity = s["entities"].most_common(1)[0][0]
        rule = active[entity]
        method = "NLP named-entity recognition" if rule["engine"] == "presidio" and entity == "PERSON" else (
            "Validated pattern (Presidio)" if rule["engine"] == "presidio" else "Configurable regex rule"
        )
        return {
            "data_class": cls,
            "pii_type": entity,
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "confidence": round(mean, 2),
            "match_ratio": round(ratio, 2),
            "samples_scanned": n,
            "samples_matched": s["hits"],
            "context_boost": s["boosted"] > 0,
            "detection_method": method,
            "masked_examples": s["examples"],
        }

   
    if DETECTION_SETTINGS.get("column_name_hints"):
        rule = _column_hint(column_name, active)
        if rule:
            return {
                "data_class": rule["data_class"],
                "pii_type": rule["entity"],
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "confidence": 0.35,
                "match_ratio": 0.0,
                "samples_scanned": n,
                "samples_matched": 0,
                "context_boost": False,
                "detection_method": "Column-name heuristic only (values did not match)",
                "masked_examples": [],
            }
    return None
