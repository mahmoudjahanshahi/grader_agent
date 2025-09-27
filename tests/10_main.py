import json
import sys
from pathlib import Path
import csv

import pytest

import main as app


def _make_assignment_tree(tmp_path: Path) -> Path:
    # assignments/
    #   instructions.txt
    #   rubric.json
    #   submissions/{stu1.txt, stu2.md}
    adir = tmp_path / "assignments"
    (adir / "submissions").mkdir(parents=True)
    (adir / "outputs").mkdir(parents=True)

    (adir / "instructions.txt").write_text(
        "- State a clear thesis.\n- Provide two pieces of evidence.\n- Include a conclusion.\n",
        encoding="utf-8",
    )
    (adir / "rubric.json").write_text(
        json.dumps(
            {
                "criteria": [
                    {"id": "C1", "text": "Thesis clarity", "max_score": 5},
                    {"id": "C2", "text": "Use of evidence", "max_score": 10},
                    {"id": "C3", "text": "Organization", "max_score": 5},
                ]
            }
        ),
        encoding="utf-8",
    )
    (adir / "submissions" / "stu1.txt").write_text(
        "Clear thesis. Two studies cited. Concludes with recommendations.",
        encoding="utf-8",
    )
    (adir / "submissions" / "stu2.md").write_text(
        "# Essay\n\nThesis present. One study only. Brief conclusion.",
        encoding="utf-8",
    )
    return adir


# --- Lightweight fakes for A2/A3/A4 to avoid network calls ---

class _A2Res:
    def __init__(self, cov): self.coverage, self.gaps, self.warnings = cov, [], []

class _A3Res:
    def __init__(self, scores):
        self.scores = scores
        self.total = sum(s["score"] for s in scores.values())
        self.max_total = sum(s["max"] for s in scores.values())

class _A4Res:
    def __init__(self, tone):
        self.strengths = ["Clear thesis"]
        self.gaps = ["Conclusion is brief"]
        self.actions = ["Expand conclusion"]
        self.tone = tone


@pytest.fixture(autouse=True)
def patch_agents(monkeypatch):
    # A2: return deterministic coverage based on presence of the word "Two"
    def fake_align_to_instructions(client, text_clean, reqs, **kwargs):
        met_two = "Two" in text_clean or "two" in text_clean
        cov = {
            "REQ_1": {"status": "met", "evidence": "Clear thesis"},
            "REQ_2": {"status": "met" if met_two else "partial", "evidence": "evidence mention"},
            "REQ_3": {"status": "partial", "evidence": "brief conclusion"},
        }
        # ensure req ids match
        cov = {r["id"]: cov.get(r["id"], {"status": "missed", "evidence": ""}) for r in reqs}
        return _A2Res(cov)

    # A3: map statuses to scores
    def fake_grade_by_rubric(client, coverage, rubric, **kwargs):
        status2score = {"met": 1.0, "partial": 0.5, "missed": 0.0}
        scores = {}
        # crude scoring: average status over requirements to drive each criterion
        avg = sum(status2score[v["status"]] for v in coverage["coverage"].values()) / max(
            1, len(coverage["coverage"])
        )
        for c in rubric["criteria"]:
            mx = float(c["max_score"])
            scores[c["id"]] = {
                "score": round(mx * avg),
                "max": mx,
                "justification": f"{c['text']}: avg compliance {avg:.2f}",
            }
        return _A3Res(scores)

    # A4: constant structure with chosen tone
    def fake_build_feedback(client, grade_json, coverage_json=None, tone_mode="neutral", **_):
        return _A4Res(tone_mode)

    monkeypatch.setattr(app, "align_to_instructions", fake_align_to_instructions)
    monkeypatch.setattr(app, "grade_by_rubric", fake_grade_by_rubric)
    monkeypatch.setattr(app, "build_feedback", fake_build_feedback)

    # Avoid importing real Azure client inside pipeline; stub class usage in main
    class DummyClient: ...
    monkeypatch.setattr(app, "AzureOpenAI", lambda **_: DummyClient())


def test_main_csv_end_to_end(tmp_path, monkeypatch, capsys):
    assign_dir = _make_assignment_tree(tmp_path)
    out_csv = assign_dir / "outputs" / "grades.csv"

    # Simulate CLI
    argv = [
        "main.py",
        "--dir", str(assign_dir),
        "--mode", "csv",
        "--grading-mode", "realistic",
        "--tone", "neutral",
        "--out-csv", str(out_csv),
    ]
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "x")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-chat")
    monkeypatch.setattr(sys, "argv", argv)

    app.main()

    # CSV exists and has header + 2 rows
    assert out_csv.exists()
    with out_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0][:3] == ["student_id", "grade", "comment"]
    assert len(rows) == 3  # header + 2 students
    assert {r[0] for r in rows[1:]} == {"stu1", "stu2"}


    # Per-student artifacts written
    outputs = assign_dir / "outputs"
    for sid in ("stu1", "stu2"):
        assert (outputs / f"{sid}.a3.json").exists()
        assert (outputs / f"{sid}.a4.json").exists()
        assert (outputs / f"{sid}.feedback.txt").exists()
        assert (outputs / f"{sid}.feedback.html").exists()
