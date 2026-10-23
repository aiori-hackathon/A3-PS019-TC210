
import io
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import CHECKLIST_ATTRIBUTES, DATA_CLASSES
from app.services import store
from app.services.detector import list_rules

DISCLAIMER = (
    "This report contains technical discovery evidence only. It does not determine lawful basis, "
    "legal compliance, or data flows between systems. Every finding is a candidate that requires "
    "review by an accountable human (e.g. privacy / compliance officer)."
)

SCOPE = {
    "technical_evidence": [
        "Which columns matched which detection rule, with match ratio and confidence",
        "Masked sample values supporting each detection",
        "Whether purpose / retention / owner metadata is declared for each field",
        "Missing checklist attributes (evidence gaps)",
        "Detector precision / recall on a labelled test set",
    ],
    "requires_human_interpretation": [
        "Whether a field is legally 'personal data' in context",
        "Lawful basis for processing",
        "Whether declared purposes and retention periods are adequate or lawful",
        "Data flows / sharing between systems (not inferred by this tool)",
        "Any compliance or remediation decision",
    ],
}

CATALOG = [
    {"id": "evidence_manifest", "title": "Final Technical Evidence Report",
     "summary": "Complete technical report: inventory, metadata mapping, evidence gaps, detection rules, evaluation metrics and review sign-off."},
    {"id": "rep-001", "title": "Evidence Inventory Summary",
     "summary": "All scanned fields with detection evidence and linked purpose / retention / owner metadata."},
    {"id": "rep-002", "title": "Evidence Gap Register",
     "summary": "Personal-data fields missing one or more required checklist attributes."},
    {"id": "rep-003", "title": "Detection Rules Configuration",
     "summary": "Snapshot of configured detection rules, thresholds and enabled state."},
    {"id": "rep-004", "title": "Detector Evaluation Report",
     "summary": "Per-class precision, recall and F1 on the labelled test datasets."},
]


def _score(report_id: str, st: Dict[str, Any], gaps: int, rules: List[Dict[str, Any]], ev: Optional[Dict[str, Any]]) -> str:
    if report_id in ("evidence_manifest", "rep-001"):
        return f"{st['coverage_pct']}% of {st['pii_fields']} PII fields documented"
    if report_id == "rep-002":
        return f"{gaps} gap(s) open"
    if report_id == "rep-003":
        return f"{sum(1 for r in rules if r['enabled'])} of {len(rules)} rules active"
    if report_id == "rep-004":
        return f"Micro F1 {ev['overall']['f1_score']}%" if ev else "Not run yet"
    return ""


def list_reports() -> List[Dict[str, Any]]:
    from app.services.evaluation import cached_evaluation
    st = store.stats()
    gaps = len(store.list_gaps())
    rules = list_rules()
    ev = cached_evaluation()
    last = store.scan_history[-1]["finished_at"][:10] if store.scan_history else datetime.now().strftime("%Y-%m-%d")
    return [
        {**c, "framework": "Technical Evidence (PS-019)", "generatedDate": last,
         "score": _score(c["id"], st, gaps, rules, ev), "status": "Ready"}
        for c in CATALOG
    ]


def get_report_data(report_id: str) -> Optional[Dict[str, Any]]:
    entry = next((c for c in CATALOG if c["id"] == report_id), None)
    if not entry:
        return None
    from app.services.evaluation import get_evaluation

    st = store.stats()
    items = list(store.inventory.values())
    gaps = store.list_gaps()
    rules = list_rules()
    now = datetime.now()

    report: Dict[str, Any] = {
        **entry,
        "framework": "Technical Evidence (PS-019)",
        "status": "Evidence compiled for human review",
        "generatedDate": now.strftime("%Y-%m-%d"),
        "generatedTimestamp": now.astimezone().isoformat(timespec="seconds"),
        "generator": "PriVista discovery engine",
        "disclaimer": DISCLAIMER,
        "scope": SCOPE,
        "metrics": {
            "totalSources": len(st["sources"]),
            "fieldsScanned": st["total_fields"],
            "discoveredPII": st["pii_fields"],
            "metadataMatched": st["matched"],
            "unresolvedGaps": st["gaps"],
            "coverageScore": f"{st['coverage_pct']}%",
            "activeRules": sum(1 for r in rules if r["enabled"]),
        },
        "categoryBreakdown": {c: st["by_class"].get(c, 0) for c in DATA_CLASSES},
        "sources": [{"source": s, "type": t} for s, t in sorted(st["sources"].items())],
        "checklist": CHECKLIST_ATTRIBUTES,
    }
    full = report_id == "evidence_manifest"
    if full or report_id == "rep-001":
        report["inventory"] = items
    if full or report_id == "rep-002":
        report["evidenceGaps"] = gaps
    if full or report_id == "rep-003":
        report["rules"] = rules
    if full or report_id == "rep-004":
        ev = get_evaluation()
        report["evaluation"] = {k: ev[k] for k in ("dataset", "samples", "overall", "macro", "categories", "confusion_matrix", "column_level", "evaluated_at")}
    if full:
        report["scanHistory"] = store.scan_history[-20:]
    report["score"] = _score(report_id, st, len(gaps), rules, report.get("evaluation"))
    return report


# ─── PDF ───────────────────────────────────────────────────────────────────────

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for 'Page X of Y' plus header/footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._decorate(n)
            super().showPage()
        super().save()

    def _decorate(self, page_count):
        w, h = letter
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        if self._pageNumber > 1:
            self.drawString(36, h - 28, "PriVista - Technical Privacy Evidence")
            self.drawRightString(w - 36, h - 28, "TECHNICAL EVIDENCE - FOR HUMAN REVIEW")
            self.line(36, h - 32, w - 36, h - 32)
        self.line(36, 36, w - 36, 36)
        self.drawString(36, 24, "Not a legal compliance determination")
        self.drawRightString(w - 36, 24, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def _txt(v: Any, default: str = "-") -> str:
    if v is None or v == "" or v == []:
        return default
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v)
    return escape(str(v))


def generate_pdf_report(report: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=44, bottomMargin=44,
                            title=report.get("title", "PriVista Report"))
    ss = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#0F172A"))
    sub = ParagraphStyle("s", parent=ss["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#64748B"))
    h1 = ParagraphStyle("h1", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1E293B"))
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#334155"))
    note = ParagraphStyle("n", parent=body, fontName="Helvetica-Oblique", fontSize=8, leading=11)
    cell = ParagraphStyle("c", parent=ss["Normal"], fontSize=7.5, leading=9.5, textColor=colors.HexColor("#1E293B"))
    cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")
    head = ParagraphStyle("hd", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)

    def grid(rows, widths, header_bg="#1E293B"):
        data = [[Paragraph(f"<b>{escape(h)}</b>", head) for h in rows[0]]] + [
            [c if isinstance(c, Paragraph) else Paragraph(_txt(c), cell) for c in r] for r in rows[1:]
        ]
        t = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(2, len(data), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8FAFC")))
        t.setStyle(TableStyle(style))
        return t

    story: List[Any] = []
    section = [0]

    def heading(text):
        section[0] += 1
        story.append(Paragraph(f"{section[0]}. {escape(text)}", h1))

    story.append(Paragraph(_txt(report.get("title")), title))
    story.append(Paragraph(
        f"{_txt(report.get('framework'))} &bull; Generated {_txt(report.get('generatedTimestamp'))} &bull; Status: {_txt(report.get('status'))}", sub))
    story.append(Spacer(1, 10))

    box = Table([[Paragraph(f"<b>NOTICE - TECHNICAL EVIDENCE ONLY:</b> {_txt(report.get('disclaimer'))}", note)]], colWidths=[540])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#2563EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story += [box, Spacer(1, 12)]

    m = report.get("metrics", {})
    kpis = [("FIELDS SCANNED", m.get("fieldsScanned", 0), "#334155"), ("PII CANDIDATES", m.get("discoveredPII", 0), "#1e3a8a"),
            ("METADATA LINKED", m.get("metadataMatched", 0), "#16a34a"), ("EVIDENCE GAPS", m.get("unresolvedGaps", 0), "#dc2626"),
            ("COVERAGE", m.get("coverageScore", "0%"), "#2563eb")]
    kt = Table([[Paragraph(f"<b>{k}</b>", sub) for k, _, _ in kpis],
                [Paragraph(f"<font size=14 color='{c}'><b>{_txt(v, '0')}</b></font>", body) for _, v, c in kpis]], colWidths=[108] * 5)
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(kt)

    scope = report.get("scope")
    if scope:
        heading("Technical Evidence vs. Human / Legal Interpretation")
        n = max(len(scope["technical_evidence"]), len(scope["requires_human_interpretation"]))
        rows = [["Provided by this tool (technical evidence)", "Out of scope - requires human / legal interpretation"]]
        for i in range(n):
            rows.append([scope["technical_evidence"][i] if i < len(scope["technical_evidence"]) else "",
                         scope["requires_human_interpretation"][i] if i < len(scope["requires_human_interpretation"]) else ""])
        story.append(grid(rows, [270, 270]))

    if report.get("sources"):
        heading("Scanned Sources")
        story.append(grid([["Source", "Type"]] + [[s["source"], s["type"].upper()] for s in report["sources"]], [400, 140]))

    inv = report.get("inventory")
    if inv is not None:
        pii = [i for i in inv if i.get("status") != "Non-PII"]
        heading("Personal-Data Inventory and Metadata Mapping")
        story.append(Paragraph(f"{len(pii)} candidate personal-data field(s); {len(inv) - len(pii)} scanned field(s) not flagged or rejected as Non-PII.", body))
        story.append(Spacer(1, 6))
        rows = [["Source.Field", "Class / Rule", "Evidence", "Purpose", "Retention", "Owner", "Status"]]
        for i in pii:
            colour = "#16a34a" if i.get("status") == "Matched" else "#dc2626"
            evidence = f"{int((i.get('match_ratio') or 0) * 100)}% of {i.get('samples_scanned') or 0} samples, conf {i.get('confidence') or 0}"
            rows.append([Paragraph(f"<b>{_txt(i.get('source'))}.{_txt(i.get('field'))}</b>", cellb),
                         f"{i.get('class')} / {i.get('rule_name') or '-'}", evidence,
                         i.get("purpose"), i.get("retention"), i.get("owner"),
                         Paragraph(f"<font color='{colour}'><b>{_txt(i.get('status'))}</b></font>", cell)])
        story.append(grid(rows, [110, 85, 85, 80, 65, 60, 55]))

    gaps = report.get("evidenceGaps")
    if gaps is not None:
        heading("Missing-Metadata / Evidence Gap Register")
        if not gaps:
            story.append(Paragraph("No evidence gaps: every candidate field has all required checklist attributes.", body))
        else:
            rows = [["Source.Field", "Class", "Severity", "Missing", "Suggested next step"]]
            for g in gaps:
                colour = {"Critical": "#dc2626", "High": "#ea580c"}.get(g.get("severity"), "#64748b")
                rows.append([Paragraph(f"<b>{_txt(g.get('source'))}.{_txt(g.get('field'))}</b>", cellb), g.get("class"),
                             Paragraph(f"<font color='{colour}'><b>{_txt(g.get('severity'))}</b></font>", cell),
                             g.get("missingAttributes"), g.get("recommendation")])
            story.append(grid(rows, [120, 70, 50, 80, 220], "#0F172A"))

    if report.get("checklist"):
        heading("Evidence Checklist")
        story.append(grid([["Attribute", "Description", "Required by default"]] +
                          [[a["label"], a.get("description", ""), "Yes" if a.get("required") else "No"] for a in report["checklist"]], [120, 320, 100]))

    rules = report.get("rules")
    if rules is not None:
        heading("Detection Rules Configuration")
        story.append(grid([["Rule", "Entity", "Class", "Method", "Min conf.", "Enabled"]] +
                          [[r["name"], r["identifier"], r["category"], r["algorithm"], f"{r['confidenceThreshold']}%", "Yes" if r["enabled"] else "No"] for r in rules],
                          [100, 85, 80, 165, 55, 55]))

    ev = report.get("evaluation")
    if ev:
        heading("Detector Evaluation (Per-Class Precision / Recall)")
        o = ev["overall"]
        story.append(Paragraph(
            f"Datasets: {_txt(ev['dataset'])} ({len((ev.get('column_level') or {}).get('columns', []))} labelled columns, "
            f"{ev['samples']} sampled values). Micro precision {o['precision']}%, "
            f"recall {o['recall']}%, F1 {o['f1_score']}%; accuracy {o['accuracy']}%.", body))
        story.append(Spacer(1, 6))
        story.append(grid([["Class", "Precision", "Recall", "F1", "Support", "TP", "FP", "FN"]] +
                          [[c["name"], f"{c['precision']}%", f"{c['recall']}%", f"{c['f1']}%", c["support"], c["tp"], c["fp"], c["fn"]] for c in ev["categories"]],
                          [110, 70, 70, 60, 60, 55, 55, 60]))
        col = ev.get("column_level")
        if col:
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"Column-level check ({_txt(col['dataset'])}): {col['accuracy']}% of columns classified correctly.", body))

    heading("Human Review Sign-Off")
    so = Table([[Paragraph("<b>Evidence compiled by:</b>", cell), Paragraph(_txt(report.get("generator")), cellb),
                 Paragraph("<b>Reviewer name / signature:</b>", cell), Paragraph("____________________________", cell)],
                [Paragraph("<b>Generated:</b>", cell), Paragraph(_txt(report.get("generatedDate")), cell),
                 Paragraph("<b>Review outcome (reviewer's own judgement):</b>", cell), Paragraph("____________________________", cell)]],
               colWidths=[100, 150, 150, 140])
    so.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(KeepTogether([so]))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()
