
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import column, create_engine, inspect, select, table
from sqlalchemy.engine import URL

from app.core.config import DEFAULT_REQUIRED_ATTRS, NON_PII, class_sensitivity
from app.services.detector import analyze_column
from app.services.registry import lookup_metadata

ProgressFn = Optional[Callable[[str, int], None]]

MAX_CSV_ROWS = 20000   # rows read per CSV for sampling
MAX_SQL_ROWS = 500     # rows read per table for sampling


def build_record(
    source: str,
    source_type: str,
    field: str,
    result: Optional[Dict[str, Any]],
    required_attrs: List[str],
    scan_id: Optional[str] = None,
    data_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Create one inventory record (technical evidence) for a scanned column."""
    base = {
        "field": field,
        "source": source,
        "source_type": source_type,
        "data_type": data_type,
        "scan_id": scan_id,
        "required_attributes": list(required_attrs),
    }
    if not result:
        return {
            **base,
            "class": NON_PII,
            "detected_class": NON_PII,
            "pii_type": "NONE",
            "rule_id": None,
            "rule_name": None,
            "confidence": 0.0,
            "match_ratio": 0.0,
            "samples_scanned": None,
            "samples_matched": 0,
            "detection_method": "No enabled rule matched",
            "context_boost": False,
            "masked_examples": [],
            "purpose": None,
            "retention": None,
            "owner": None,
            "metadata_link": None,
            "sensitivity": "None",
        }

    meta = lookup_metadata(source, field)
    return {
        **base,
        "class": result["data_class"],
        "detected_class": result["data_class"],
        "pii_type": result["pii_type"],
        "rule_id": result["rule_id"],
        "rule_name": result["rule_name"],
        "confidence": result["confidence"],
        "match_ratio": result["match_ratio"],
        "samples_scanned": result["samples_scanned"],
        "samples_matched": result["samples_matched"],
        "detection_method": result["detection_method"],
        "context_boost": result["context_boost"],
        "masked_examples": result["masked_examples"],
        "purpose": meta.get("purpose"),
        "retention": meta.get("retention"),
        "owner": meta.get("owner"),
        "metadata_link": meta.get("link"),
        "sensitivity": class_sensitivity(result["data_class"]),
    }


def read_csv(file_path: Union[str, Path], nrows: Optional[int] = MAX_CSV_ROWS) -> pd.DataFrame:
    last_err = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(file_path, dtype=str, nrows=nrows, encoding=enc, on_bad_lines="skip")
        except UnicodeDecodeError as e:
            last_err = e
    raise ValueError(f"Could not decode CSV: {last_err}")


def scan_csv(
    file_path: Union[str, Path],
    source_name: Optional[str] = None,
    required_attrs: Optional[List[str]] = None,
    progress: ProgressFn = None,
    scan_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Scan every column of a CSV file. Raises on unreadable files."""
    required_attrs = required_attrs if required_attrs is not None else DEFAULT_REQUIRED_ATTRS
    source = source_name or Path(file_path).name
    df = read_csv(file_path)
    cols = list(df.columns)
    out = []
    for idx, col in enumerate(cols, start=1):
        if progress:
            progress(f"Analysing column {idx}/{len(cols)}: {col}", 25 + int(65 * idx / max(len(cols), 1)))
        values = df[col].dropna().tolist()
        result = analyze_column(str(col), values)
        out.append(build_record(source, "csv", str(col), result, required_attrs, scan_id, "text"))
    return out


def scan_sql(
    url: Union[str, URL],
    db_label: str,
    schema: Optional[str] = None,
    required_attrs: Optional[List[str]] = None,
    progress: ProgressFn = None,
    scan_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Scan every column of every table in a SQL database. Raises on connection errors."""
    required_attrs = required_attrs if required_attrs is not None else DEFAULT_REQUIRED_ATTRS
    engine = create_engine(url)
    out: List[Dict[str, Any]] = []
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=schema)
        if progress:
            progress(f"Found {len(tables)} table(s): {', '.join(tables) or '—'}", 20)
        for t_idx, tname in enumerate(tables, start=1):
            cols = inspector.get_columns(tname, schema=schema)
            col_names = [c["name"] for c in cols]
            col_types = {c["name"]: str(c.get("type", "")) for c in cols}
            if progress:
                progress(f"Sampling table {t_idx}/{len(tables)}: {tname} ({len(col_names)} columns)",
                         20 + int(70 * (t_idx - 1) / max(len(tables), 1)))
            stmt = select(*[column(c) for c in col_names]).select_from(table(tname, schema=schema)).limit(MAX_SQL_ROWS)
            with engine.connect() as conn:
                rows = conn.execute(stmt).fetchall()
            prefix = f"{db_label}.{schema}" if schema and schema not in ("public", "main", "dbo") else db_label
            source = f"{prefix}.{tname}"
            for c_idx, cname in enumerate(col_names):
                values = [r[c_idx] for r in rows if r[c_idx] is not None and not isinstance(r[c_idx], (bytes, bytearray, memoryview))]
                result = analyze_column(cname, values)
                out.append(build_record(source, "sql", cname, result, required_attrs, scan_id, col_types.get(cname)))
    finally:
        engine.dispose()
    return out
