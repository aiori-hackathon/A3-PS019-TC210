
import json
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

from app.core.config import (
    BASE_DIR,
    CHECKLIST_ATTRIBUTES,
    CHECKLIST_KEYS,
    DATA_CLASSES,
    DATA_CLASSES_CONFIG,
    DEFAULT_REQUIRED_ATTRS,
    MAX_UPLOAD_BYTES,
    NON_PII,
    UPLOAD_DIR,
)
from app.models.schemas import EvaluationRequest, RuleTestRequest, ScanStartRequest, SQLConnection, SQLScanRequest
from app.services import detector, registry, store
from app.services.evaluation import compute_metrics, get_evaluation, normalise_label
from app.services.report_service import generate_pdf_report, get_report_data, list_reports
from app.services.scanner import read_csv, scan_csv, scan_sql

router = APIRouter()

CLASS_COLORS = {"Name": "#2563eb", "Email ID": "#0ea5e9", "Phone Number": "#10b981",
                "Financial Data": "#f59e0b", "Government ID": "#8b5cf6"}




def _required_attrs(checklist: Dict[str, bool]) -> List[str]:
    if not checklist:
        return list(DEFAULT_REQUIRED_ATTRS)
    return [k for k in CHECKLIST_KEYS if checklist.get(k)]


def _sql_target(cfg: SQLConnection):
    
    dialect = cfg.dialect.strip().lower()
    if dialect == "sqlite":
        raw = (cfg.dbName or "data/sample.db").strip()
        path = Path(raw)
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        if path.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
            raise ValueError("SQLite file must end with .db, .sqlite or .sqlite3")
        if not path.exists():
            raise ValueError(f"SQLite file not found: {raw}")
        return URL.create("sqlite", database=str(path)), path.stem, None, {"timeout": 5}
    if dialect not in ("postgresql", "mysql"):
        raise ValueError("Supported database types: SQLite, PostgreSQL, MySQL")
    if not cfg.host.strip() or not cfg.dbName.strip():
        raise ValueError("Host and database name are required")
    driver = "postgresql+psycopg2" if dialect == "postgresql" else "mysql+pymysql"
    port = int(cfg.port) if str(cfg.port).strip().isdigit() else None
    # URL.create escapes special characters in credentials safely.
    url = URL.create(driver, username=cfg.username or None, password=cfg.password or None,
                     host=cfg.host.strip(), port=port, database=cfg.dbName.strip())
    schema = cfg.schema_name.strip() or None
    return url, cfg.dbName.strip(), schema, {"connect_timeout": 5}


def _store_results(results: List[Dict[str, Any]]) -> Dict[str, int]:
    new = 0
    for r in results:
        _, is_new = store.upsert_finding(r)
        new += int(is_new)
    store.save_store()
    pii = [r for r in results if r["class"] != NON_PII]
    return {"new": new, "pii": len(pii)}


def _record_history(scan_id: str, source: str, source_type: str, started: str, results: List[Dict[str, Any]], status: str, error: str = None):
    st = store.stats()
    scanned_items = [i for i in store.inventory.values() if i.get("scan_id") == scan_id]
    entry = {
        "scan_id": scan_id,
        "source": source,
        "source_type": source_type,
        "started_at": started,
        "finished_at": store.now_iso(),
        "status": status,
        "error": error,
        "columns_scanned": len(results),
        "pii_found": sum(1 for i in scanned_items if i["status"] != NON_PII),
        "gaps_found": sum(1 for i in scanned_items if i["status"] == "Evidence Gap"),
        "inventory_pii_total": st["pii_fields"],
        "inventory_gap_total": st["gaps"],
    }
    store.scan_history.append(entry)
    store.save_store()
    return entry



@router.get("/config/checklist")
def get_checklist():
    return CHECKLIST_ATTRIBUTES


@router.get("/config/data-classes")
def get_data_classes():
    return [{"name": c, **(DATA_CLASSES_CONFIG["data_classes"][c] or {}), "color": CLASS_COLORS.get(c)} for c in DATA_CLASSES]


# ─── Scanning ──────────────────────────────────────────────────────────────────

@router.post("/scan/upload")
async def upload_csv(file: UploadFile = File(...)):
    name = Path(file.filename or "upload.csv").name  # strip any directory components
    if not name.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = str(uuid.uuid4())
    path = UPLOAD_DIR / f"{upload_id}.csv"
    size = 0
    with open(path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, "CSV exceeds the 50 MB limit")
            f.write(chunk)
    try:
        df = read_csv(path, nrows=None)
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not parse CSV: {e}")
    if df.shape[1] == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "CSV has no columns")
    store.uploads[upload_id] = {"path": str(path), "filename": name}
    store.save_store()
    return {"scanId": upload_id, "uploadId": upload_id, "filename": name,
            "rowCount": int(len(df)), "columns": [str(c) for c in df.columns]}


@router.post("/scan/test-connection")
def test_connection(cfg: SQLConnection):
    try:
        url, label, schema, connect_args = _sql_target(cfg)
        engine = create_engine(url, connect_args=connect_args)
        try:
            with engine.connect():
                pass
            tables = inspect(engine).get_table_names(schema=schema)
        finally:
            engine.dispose()
        return {"success": True, "message": f"Connected to {label}", "database": label, "tables": tables}
    except Exception as e:
        # Never echo credentials back; SQLAlchemy masks passwords in URL reprs.
        return {"success": False, "message": f"Connection failed: {e}", "tables": []}


def _run_scan_job(scan_id: str, req: ScanStartRequest):
    job = store.scan_jobs[scan_id]
    started = store.now_iso()

    def log(text: str, pct: Optional[int] = None):
        if pct is not None:
            job["progress"] = max(job["progress"], min(pct, 99))
        job["logs"].append({"text": text, "time": time.strftime("%H:%M:%S")})

    required = _required_attrs(req.checklist)
    source_label, source_type = "unknown", req.sourceType
    results: List[Dict[str, Any]] = []
    try:
        log(f"Evidence checklist: {', '.join(required) or 'none selected'}", 5)
        active = [r["name"] for r in detector.list_rules() if r["enabled"]]
        log(f"Active detection rules ({len(active)}): {', '.join(active)}", 10)
        if req.sourceType == "csv":
            up = store.uploads.get(str(req.sourceRef))
            if not up or not Path(up["path"]).exists():
                raise ValueError("Uploaded file not found; please upload the CSV again")
            source_label = up["filename"]
            log(f"Reading CSV {source_label}", 15)
            results = scan_csv(up["path"], source_label, required, log, scan_id)
        elif req.sourceType == "sql":
            cfg = SQLConnection(**(req.sourceRef or {}))
            url, label, schema, _ = _sql_target(cfg)
            source_label = label
            log(f"Connecting to {cfg.dialect} database {label}", 15)
            results = scan_sql(url, label, schema, required, log, scan_id)
        else:
            raise ValueError("sourceType must be 'csv' or 'sql'")

        log("Linking fields to declared metadata and checking evidence checklist", 92)
        summary = _store_results(results)
        entry = _record_history(scan_id, source_label, source_type, started, results, "completed")
        log(f"Scan complete: {len(results)} columns, {entry['pii_found']} personal-data candidates, "
            f"{entry['gaps_found']} evidence gaps ({summary['new']} new records).")
        job["progress"] = 100
        job["results"] = [i for i in store.inventory.values() if i.get("scan_id") == scan_id]
        job["summary"] = entry
        job["status"] = "completed"
    except Exception as e:
        log(f"Scan failed: {e}")
        _record_history(scan_id, source_label, source_type, started, [], "failed", str(e))
        job["status"] = "failed"
        job["error"] = str(e)


@router.post("/scan/start")
def start_scan(req: ScanStartRequest, background_tasks: BackgroundTasks):
    scan_id = str(uuid.uuid4())
    store.scan_jobs[scan_id] = {"status": "running", "progress": 0, "logs": [], "results": [], "summary": None, "error": None}
    background_tasks.add_task(_run_scan_job, scan_id, req)
    return {"scanId": scan_id}


@router.get("/scan/history")
def scan_history(limit: int = Query(20, ge=1, le=200)):
    return list(reversed(store.scan_history[-limit:]))


@router.get("/scan/{scan_id}")
def get_scan(scan_id: str):
    job = store.scan_jobs.get(scan_id)
    if not job:
        raise HTTPException(404, "Scan not found")
    return {k: job[k] for k in ("status", "progress", "logs", "summary", "error")}


@router.get("/scan/{scan_id}/results")
def get_scan_results(scan_id: str):
    job = store.scan_jobs.get(scan_id)
    if not job:
        raise HTTPException(404, "Scan not found")
    return job.get("results", [])


@router.post("/scan/csv")
async def api_scan_csv(file: UploadFile = File(...)):
    """Synchronous CSV scan (API / scripting use). Results are stored in the inventory."""
    name = Path(file.filename or "upload.csv").name
    if not name.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "CSV exceeds the 50 MB limit")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scan.csv"
        path.write_bytes(data)
        scan_id = str(uuid.uuid4())
        started = store.now_iso()
        try:
            results = scan_csv(path, name, DEFAULT_REQUIRED_ATTRS, None, scan_id)
        except Exception as e:
            raise HTTPException(400, f"Scan failed: {e}")
    _store_results(results)
    _record_history(scan_id, name, "csv", started, results, "completed")
    return {"filename": name, "evidence": [i for i in store.inventory.values() if i.get("scan_id") == scan_id]}


@router.post("/scan/sql")
def api_scan_sql(request: SQLScanRequest):
    """Synchronous SQL scan (API / scripting use). Results are stored in the inventory."""
    try:
        url, label, schema, _ = _sql_target(request.connection)
        scan_id = str(uuid.uuid4())
        started = store.now_iso()
        results = scan_sql(url, label, schema, _required_attrs(request.checklist), None, scan_id)
    except Exception as e:
        raise HTTPException(400, f"Scan failed: {e}")
    _store_results(results)
    _record_history(scan_id, label, "sql", started, results, "completed")
    return {"source": label, "evidence": [i for i in store.inventory.values() if i.get("scan_id") == scan_id]}



@router.get("/inventory/")
def list_inventory():
    return sorted(store.inventory.values(), key=lambda i: (i["status"] == NON_PII, i["source"], i["field"]))


@router.get("/inventory/{item_id}")
def get_inventory_item(item_id: str):
    item = store.inventory.get(item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found")
    return item


@router.patch("/inventory/{item_id}")
def update_inventory(item_id: str, patch: Dict[str, Any] = Body(...)):
    item = store.inventory.get(item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found (run a scan first)")
    try:
        store.apply_patch(item, patch)
    except ValueError as e:
        raise HTTPException(400, str(e))
    meta = {k: patch[k] for k in CHECKLIST_KEYS if k in patch}
    if meta and item["status"] != NON_PII:
        registry.declare(item["source"], item["field"], meta)
    store.save_store()
    return item


@router.delete("/inventory/{item_id}")
def delete_inventory(item_id: str):
   
    item = store.inventory.get(item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found")
    if item.get("status") != NON_PII:
        raise HTTPException(403, "Only Non-PII records can be deleted. Mark the field as Non-PII after review first.")
    del store.inventory[item_id]
    store.save_store()
    return {"success": True, "deleted_id": item_id, "message": f"Non-PII record '{item['field']}' deleted"}


@router.post("/inventory/reset")
def reset_inventory(confirm: bool = Query(False), include_declarations: bool = Query(False)):
    if not confirm:
        raise HTTPException(400, "Pass ?confirm=true to reset the inventory")
    store.reset()
    if include_declarations:
        registry.reset_reviewer_declarations()
    return {"success": True}




@router.get("/evidence-gaps/")
def list_gaps():
    return store.list_gaps()


@router.post("/evidence-gaps/{gap_id}/resolve")
def resolve_gap(gap_id: str, payload: Dict[str, Any] = Body(...)):
    gap = store.get_gap(gap_id)
    if not gap:
        raise HTTPException(404, "Gap not found or already resolved")
    item = store.inventory[gap["item_id"]]
    patch = {k: payload[k] for k in CHECKLIST_KEYS if k in payload}
    for k in ("sensitivity", "review_decision"):
        if k in payload:
            patch[k] = payload[k]
    try:
        store.apply_patch(item, patch)
    except ValueError as e:
        raise HTTPException(400, str(e))
    meta = {k: patch[k] for k in CHECKLIST_KEYS if k in patch}
    if meta and item["status"] != NON_PII:
        registry.declare(item["source"], item["field"], meta)
    store.save_store()
    return {"gapId": gap_id, "resolved": item["status"] != "Evidence Gap", "item": item,
            "stillMissing": item.get("missing_attributes", [])}



@router.get("/rules/")
def list_rules():
    return detector.list_rules()


@router.post("/rules/")
def create_rule(rule: Dict[str, Any] = Body(...)):
    try:
        return detector.create_rule(rule)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/rules/test")
def test_rules(payload: RuleTestRequest):
    """Run the real detector (all enabled rules) on sandbox text."""
    context = detector.column_tokens(payload.context) if payload.context else None
    matches = detector.analyze_text(payload.text, context)
    grouped: Dict[str, Dict[str, Any]] = {}
    for m in matches:
        g = grouped.setdefault(m["rule_id"], {"ruleId": m["rule_id"], "ruleName": m["rule_name"], "identifier": m["entity"],
                                              "category": m["data_class"], "matches": [], "confidence": 0})
        g["matches"].append(m["text"])
        g["confidence"] = max(g["confidence"], round(m["score"] * 100))
    return list(grouped.values())


@router.post("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: str):
    rule = detector.toggle_rule(rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    try:
        if not detector.delete_rule(rule_id):
            raise HTTPException(404, "Rule not found")
    except PermissionError as e:
        raise HTTPException(403, str(e))
    return {"success": True, "deleted_id": rule_id}




@router.get("/evaluation/")
def evaluation(refresh: bool = Query(False)):
    try:
        return get_evaluation(refresh)
    except Exception as e:
        raise HTTPException(500, f"Evaluation failed: {e}")


@router.post("/evaluate")
def api_evaluate(request: EvaluationRequest):
    if len(request.true_labels) != len(request.predicted_labels) or not request.true_labels:
        raise HTTPException(400, "true_labels and predicted_labels must be non-empty and the same length")
    return compute_metrics([normalise_label(x) for x in request.true_labels],
                           [normalise_label(x) for x in request.predicted_labels])




@router.get("/dashboard/summary")
def get_summary():
    st = store.stats()
    n_csv = sum(1 for t in st["sources"].values() if t == "csv")
    n_sql = len(st["sources"]) - n_csv
    last = next((h for h in reversed(store.scan_history) if h["status"] == "completed"), None)
    pii = st["pii_fields"]
    return {
        "total_sources": len(st["sources"]),
        "total_sources_sub": f"{n_sql} SQL table(s), {n_csv} CSV file(s)",
        "fields_scanned": st["total_fields"],
        "pii_fields": pii,
        "pii_change": f"{last['pii_found']} in last scan" if last else "No scans yet",
        "metadata_matched": st["matched"],
        "metadata_percentage": f"{st['coverage_pct']}%",
        "evidence_gaps": st["gaps"],
        "gap_percentage": f"{round(st['gaps'] / pii * 100) if pii else 0}%",
        "evidence_coverage": f"{st['coverage_pct']}%",
        "coverage_sub": f"{st['matched']} of {pii} PII fields documented",
        "last_scan_date": last["finished_at"].replace("T", " ")[:19] if last else "Never",
        "last_scan_source": last["source"] if last else None,
        "scans_run": len(store.scan_history),
    }


@router.get("/dashboard/charts")
def get_charts():
    st = store.stats()
    total = sum(st["by_class"].values()) or 1
    pii_by_class = [
        {"name": c, "value": st["by_class"].get(c, 0),
         "percentage": f"{round(st['by_class'].get(c, 0) / total * 100, 1)}%", "color": CLASS_COLORS.get(c, "#64748b")}
        for c in DATA_CLASSES
    ]
    trend = [
        {"date": h["finished_at"][5:16].replace("T", " "), "source": h["source"],
         "value": h["inventory_pii_total"], "gaps": h["inventory_gap_total"]}
        for h in store.scan_history[-12:] if h["status"] == "completed"
    ]
    return {"pii_by_class": pii_by_class, "trend": trend}




@router.get("/reports/")
def reports():
    return list_reports()


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    report = get_report_data(report_id)
    if not report:
        raise HTTPException(404, f"Report '{report_id}' not found")
    return report


@router.get("/reports/{report_id}/download")
def download_report(report_id: str, format: str = "json"):
    report = get_report_data(report_id)
    if not report:
        raise HTTPException(404, f"Report '{report_id}' not found")
    fmt = (format or "json").lower().strip()
    stamp = time.strftime("%Y%m%d")
    if fmt == "json":
        return Response(json.dumps(report, indent=2, default=str), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="privista_{report_id}_{stamp}.json"'})
    if fmt == "pdf":
        try:
            pdf = generate_pdf_report(report)
        except Exception as e:
            raise HTTPException(500, f"PDF generation failed: {e}")
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="privista_{report_id}_{stamp}.pdf"'})
    raise HTTPException(400, "Supported formats: json, pdf")
