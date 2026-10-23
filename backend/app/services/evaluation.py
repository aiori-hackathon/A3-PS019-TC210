
"""
Evaluation of the detector against labelled test data.

The only inputs are the datasets named in data/ground_truth.csv (dataset,column,true_class):
  large_test_set.csv, synthetic_kyc_payment_test_data.csv, synthetic_kyc_payment_test_data (2).csv

Each labelled column is scanned once, with the same code path as the scanner (analyze_column):
1. Column-level: the column's predicted class vs its true class.
2. Value-level:  every sampled value of the column vs the column's true class. A value's
                 prediction is the class it would get if scanned on its own under that column name.

Per-class precision / recall / F1 are computed over the 5 predefined classes.
"Non-PII" columns act as negatives: predicting a class for them is a false positive.
"""
import threading
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from app.core.config import COLUMN_GROUND_TRUTH, DATA_CLASSES, DATA_DIR, NON_PII
from app.services.detector import analyze_column, rules_version

MAX_ERRORS_SHOWN = 100  # misclassified values returned to the UI (the total is always reported)

_LABEL_ALIASES = {
    "name": "Name", "person": "Name",
    "email": "Email ID", "email id": "Email ID", "email_address": "Email ID",
    "phone": "Phone Number", "phone number": "Phone Number", "mobile": "Phone Number",
    "financial": "Financial Data", "financial data": "Financial Data",
    "government id": "Government ID", "gov id": "Government ID", "govt id": "Government ID",
    "unknown": NON_PII, "non-pii": NON_PII, "none": NON_PII, "": NON_PII,
}

_cache: Dict[str, Any] = {"version": None, "result": None}
_cache_lock = threading.Lock()


def normalise_label(label: Any) -> str:
    s = str(label if label is not None else "").strip()
    if s in DATA_CLASSES:
        return s
    return _LABEL_ALIASES.get(s.lower(), NON_PII)


def _pct(x: float) -> float:
    return round(float(x) * 100, 1)


def compute_metrics(true_labels: List[str], predicted_labels: List[str]) -> Dict[str, Any]:
    """Per-class and averaged metrics over the 5 data classes (Non-PII = negative class)."""
    precision, recall, f1, support = precision_recall_fscore_support(
        true_labels, predicted_labels, labels=DATA_CLASSES, average=None, zero_division=0
    )
    categories = []
    for i, cls in enumerate(DATA_CLASSES):
        tp = sum(1 for t, p in zip(true_labels, predicted_labels) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(true_labels, predicted_labels) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(true_labels, predicted_labels) if t == cls and p != cls)
        categories.append({
            "name": cls,
            "precision": _pct(precision[i]),
            "recall": _pct(recall[i]),
            "f1": _pct(f1[i]),
            "support": int(support[i]),
            "tp": tp, "fp": fp, "fn": fn,
        })

    micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(
        true_labels, predicted_labels, labels=DATA_CLASSES, average="micro", zero_division=0
    )
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        true_labels, predicted_labels, labels=DATA_CLASSES, average="macro", zero_division=0
    )

    # Binary "is this personal data?" view - each sample counted exactly once.
    def is_pii(x: str) -> bool:
        return x != NON_PII

    binary = {
        "true_positive": sum(1 for t, p in zip(true_labels, predicted_labels) if is_pii(t) and is_pii(p)),
        "false_positive": sum(1 for t, p in zip(true_labels, predicted_labels) if not is_pii(t) and is_pii(p)),
        "false_negative": sum(1 for t, p in zip(true_labels, predicted_labels) if is_pii(t) and not is_pii(p)),
        "true_negative": sum(1 for t, p in zip(true_labels, predicted_labels) if not is_pii(t) and not is_pii(p)),
        "wrong_class": sum(1 for t, p in zip(true_labels, predicted_labels) if is_pii(t) and is_pii(p) and t != p),
    }

    labels = DATA_CLASSES + [NON_PII]
    matrix = [[sum(1 for t, p in zip(true_labels, predicted_labels) if t == r and p == c) for c in labels] for r in labels]
    correct = sum(1 for t, p in zip(true_labels, predicted_labels) if t == p)

    return {
        "categories": categories,
        "micro": {"precision": _pct(micro_p), "recall": _pct(micro_r), "f1": _pct(micro_f1)},
        "macro": {"precision": _pct(macro_p), "recall": _pct(macro_r), "f1": _pct(macro_f1)},
        "accuracy": _pct(correct / len(true_labels)) if true_labels else 0.0,
        "binary": binary,
        "class_confusion": {"labels": labels, "matrix": matrix},
    }


def _load_ground_truth() -> pd.DataFrame:
    if not COLUMN_GROUND_TRUTH.exists():
        raise ValueError(f"{COLUMN_GROUND_TRUTH.name} not found")
    truth = pd.read_csv(COLUMN_GROUND_TRUTH, dtype=str, keep_default_na=False)
    missing = {"dataset", "column", "true_class"} - set(truth.columns)
    if missing:
        raise ValueError(f"{COLUMN_GROUND_TRUTH.name} is missing column(s): {', '.join(sorted(missing))}")
    return truth


def run_evaluation() -> Dict[str, Any]:
    from app.services.scanner import read_csv  # local import avoids a cycle

    truth = _load_ground_truth()
    datasets = list(dict.fromkeys(truth["dataset"].str.strip()))

    col_rows: List[Dict[str, Any]] = []
    col_true: List[str] = []
    col_pred: List[str] = []
    val_true: List[str] = []
    val_pred: List[str] = []
    errors: List[Dict[str, Any]] = []
    subsets: List[Dict[str, Any]] = []
    skipped: List[str] = []
    used: List[str] = []
    started = time.perf_counter()

    for name in datasets:
        path = DATA_DIR / name
        if not path.is_file():
            skipped.append(f"{name} (file not found)")
            continue
        df = read_csv(path)
        used.append(name)
        sub_val_true, sub_val_pred, sub_col_true, sub_col_pred = [], [], [], []

        for _, r in truth[truth["dataset"].str.strip() == name].iterrows():
            col = str(r["column"])
            if col not in df.columns:
                skipped.append(f"{name}: column '{col}' not found")
                continue
            expected = normalise_label(r["true_class"])
            per_value: List[tuple] = []
            res = analyze_column(col, df[col].dropna().tolist(),
                                 on_value=lambda v, c: per_value.append((v, c or NON_PII)))
            pred = res["data_class"] if res else NON_PII

            sub_col_true.append(expected)
            sub_col_pred.append(pred)
            col_rows.append({
                "dataset": name,
                "column": col,
                "true": expected,
                "predicted": pred,
                "correct": expected == pred,
                "rule": res["rule_name"] if res else None,
                "confidence": res["confidence"] if res else None,
                "match_ratio": res["match_ratio"] if res else None,
                "values_correct": sum(1 for _, c in per_value if c == expected),
                "values_tested": len(per_value),
            })
            for value, value_pred in per_value:
                sub_val_true.append(expected)
                sub_val_pred.append(value_pred)
                if value_pred != expected:
                    errors.append({
                        "value": value,  # synthetic test data, safe to display
                        "column": col,
                        "dataset": name,
                        "true": expected,
                        "predicted": value_pred,
                    })

        sub_val = compute_metrics(sub_val_true, sub_val_pred)
        sub_col = compute_metrics(sub_col_true, sub_col_pred)
        subsets.append({
            "dataset": name,
            "samples": len(sub_val_true),
            "columns": len(sub_col_true),
            "column_accuracy": sub_col["accuracy"],
            "accuracy": sub_val["accuracy"],
            "micro": sub_val["micro"],
        })
        val_true += sub_val_true
        val_pred += sub_val_pred
        col_true += sub_col_true
        col_pred += sub_col_pred

    if not val_true:
        raise ValueError("No evaluation data found. Check data/ground_truth.csv and the dataset files it names.")

    elapsed_ms = (time.perf_counter() - started) * 1000
    value = compute_metrics(val_true, val_pred)
    column = compute_metrics(col_true, col_pred)
    return {
        "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rules_version": rules_version(),
        "dataset": " + ".join(used),
        "samples": len(val_true),
        "distribution": {c: val_true.count(c) for c in DATA_CLASSES + [NON_PII]},
        "overall": {
            "precision": value["micro"]["precision"],
            "recall": value["micro"]["recall"],
            "f1_score": value["micro"]["f1"],
            "accuracy": value["accuracy"],
            "latency_ms": round(elapsed_ms / len(val_true), 1),
        },
        "macro": value["macro"],
        "categories": value["categories"],
        "subsets": subsets,
        "confusion_matrix": value["binary"],
        "class_confusion": value["class_confusion"],
        "errors": errors[:MAX_ERRORS_SHOWN],
        "errors_total": len(errors),
        "skipped": skipped,
        "column_level": {
            "dataset": f"{' + '.join(used)} + {COLUMN_GROUND_TRUTH.name}",
            "columns": col_rows,
            "accuracy": column["accuracy"],
            "micro": column["micro"],
            "macro": column["macro"],
            "categories": column["categories"],
        },
    }


def get_evaluation(refresh: bool = False) -> Dict[str, Any]:
    """Cached evaluation; recomputed when rules change or refresh is requested."""
    with _cache_lock:
        if not refresh and _cache["result"] is not None and _cache["version"] == rules_version():
            return _cache["result"]
        result = run_evaluation()
        _cache.update(version=result["rules_version"], result=result)
        return result


def cached_evaluation() -> Optional[Dict[str, Any]]:
    return _cache["result"]
