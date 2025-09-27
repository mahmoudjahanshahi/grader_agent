from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
from html import escape

@dataclass
class ReportSummary:
    grade: int                 # total points (int)
    max_total: int             # max points
    comment_text: str          # plain text body
    comment_html: str          # HTML body

# ---------- helpers ----------

def _rows_from_a3(a3: Dict[str, Any]) -> List[tuple[str, int, int, str]]:
    rows: List[tuple[str, int, int, str]] = []
    for cid, e in a3.get("scores", {}).items():
        score = int(e.get("score", 0))
        mx = int(e.get("max", 0))
        why = str(e.get("justification", ""))
        rows.append((cid, score, mx, why))
    return rows

def render_text(a3: Dict[str, Any], a4: Dict[str, Any]) -> str:
    total = int(a3.get("total", 0)); max_total = int(a3.get("max_total", 0))
    lines = [f"Total: {total} / {max_total}", ""]
    lines.append("Per-criterion:")
    for cid, score, mx, why in _rows_from_a3(a3):
        lines.append(f"- {cid}: {score}/{mx} — {why}")
    def bl(label, items: List[str]):
        if items:
            lines.append(f"\n{label}:")
            for it in items: lines.append(f"- {it}")
    bl("Strengths", a4.get("strengths", []))
    bl("Gaps", a4.get("gaps", []))
    bl("Next actions", a4.get("actions", []))
    return "\n".join(lines).strip()

def render_html(a3: Dict[str, Any], a4: Dict[str, Any], rubric: Dict[str, Any] | None = None) -> str:
    total = int(a3.get("total", 0)); max_total = int(a3.get("max_total", 0))
    # optional pretty names from rubric
    name_map = {c["id"]: c.get("text", c["id"]) for c in (rubric or {}).get("criteria", [])}
    rows = []
    for cid, score, mx, why in _rows_from_a3(a3):
        name = escape(name_map.get(cid, cid))
        rows.append(
            f"<tr><td>{name}</td><td>{score} / {mx}</td><td>{escape(why)}</td></tr>"
        )
    strengths = "".join(f"<li>{escape(s)}</li>" for s in a4.get("strengths", []))
    gaps = "".join(f"<li>{escape(g)}</li>" for g in a4.get("gaps", []))
    actions = "".join(f"<li>{escape(a)}</li>" for a in a4.get("actions", []))
    return f"""<div style="font-family:system-ui,Arial,sans-serif;line-height:1.45">
  <h2 style="margin:0 0 8px">Assignment Feedback</h2>
  <p style="margin:0 0 12px"><strong>Total:</strong> {total} / {max_total}</p>
  <table cellpadding="6" cellspacing="0" border="1" style="border-collapse:collapse;width:100%;margin:8px 0">
    <thead style="background:#f6f6f6"><tr><th align="left">Criterion</th><th align="left">Score</th><th align="left">Why</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h3 style="margin:12px 0 6px">Strengths</h3>
  <ul>{strengths}</ul>
  <h3 style="margin:12px 0 6px">Gaps</h3>
  <ul>{gaps}</ul>
  <h3 style="margin:12px 0 6px">Next actions</h3>
  <ul>{actions}</ul>
</div>"""

# ---------- main API ----------

def summarize(a3: Dict[str, Any], a4: Dict[str, Any], rubric: Dict[str, Any] | None = None) -> ReportSummary:
    """
    Deterministic formatter. No I/O. No network.
    Returns grade and three renderings for delivery.
    """
    grade = int(a3.get("total", 0))
    max_total = int(a3.get("max_total", 0))
    txt = render_text(a3, a4)
    html = render_html(a3, a4, rubric)
    return ReportSummary(grade=grade, max_total=max_total, comment_text=txt, comment_html=html)
