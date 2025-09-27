from __future__ import annotations
import os, json, csv, argparse
from pathlib import Path
from typing import Dict, Any, Iterable, Literal
import requests

from openai import AzureOpenAI

from agents.a1_cleaner import clean_text
from agents.a2_alignment import load_requirements_from_text, align_to_instructions
from agents.a3_grader import validate_rubric, grade_by_rubric
from agents.a4_feedback import build_feedback
from agents.a5_report import summarize

# ---------- delivery helpers (no LLM) ----------

def export_csv(rows: Iterable[tuple[str,int,str]], out_csv_path: Path) -> None:
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with out_csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["student_id", "grade", "comment"])
        for sid, grade, comment in rows:
            w.writerow([sid, grade, comment])

class CanvasClient:
    def __init__(self, base_url: str, token: str, timeout: float = 15.0):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}"})
        self.timeout = timeout

    def grade_and_comment(
        self,
        course_id: str|int,
        assignment_id: str|int,
        user_identifier: str,
        id_kind: Literal["user_id","sis_user_id","login_id"] = "sis_user_id",
        score: int = 0,
        comment: str = "",
    ) -> None:
        # target selector
        if id_kind == "user_id":
            ident_q = f"user_id={user_identifier}"
            sub_path = f"/submissions/{user_identifier}"
        elif id_kind == "login_id":
            ident_q = f"as_user_id=login:{user_identifier}"
            sub_path = "/submissions/self"
        else:
            ident_q = f"as_user_id=sis_user_id:{user_identifier}"
            sub_path = "/submissions/self"

        # grade
        url_g = f"{self.base}/api/v1/courses/{course_id}/assignments/{assignment_id}{sub_path}"
        r = self.s.put(f"{url_g}?{ident_q}", data={"submission[posted_grade]": score}, timeout=self.timeout)
        r.raise_for_status()
        # comment
        if comment:
            url_c = f"{self.base}/api/v1/courses/{course_id}/assignments/{assignment_id}{sub_path}/comments"
            rc = self.s.post(f"{url_c}?{ident_q}", data={"comment[text_comment]": comment}, timeout=self.timeout)
            rc.raise_for_status()

# ---------- pipeline ----------

def run_pipeline_for_student(
    client: AzureOpenAI,
    submission_text: str,
    reqs_text: str,
    rubric: Dict[str, Any],
    *,
    grading_mode: Literal["forgiving","realistic","strict"] = "realistic",
    tone_mode: str = "neutral",
) -> dict:
    a1 = clean_text(submission_text)
    reqs = load_requirements_from_text(reqs_text, client=client)
    a2 = align_to_instructions(client, a1.text_clean, reqs)
    a3 = grade_by_rubric(client, coverage=a2.__dict__, rubric=rubric, mode=grading_mode)
    a4 = build_feedback(
        client,
        grade_json={"scores": a3.scores, "total": a3.total, "max_total": a3.max_total},
        coverage_json=a2.__dict__,
        tone_mode=tone_mode,
    )
    rep = summarize(
        a3={"scores": a3.scores, "total": a3.total, "max_total": a3.max_total},
        a4={"strengths": a4.strengths, "gaps": a4.gaps, "actions": a4.actions, "tone": a4.tone},
        rubric=rubric,
    )
    return {
        "grade": rep.grade,
        "max_total": rep.max_total,
        "comment_text": rep.comment_text,
        "comment_html": rep.comment_html,
        "a2": {"coverage": a2.coverage, "gaps": a2.gaps, "warnings": a2.warnings},
        "a3": {"scores": a3.scores, "total": a3.total, "max_total": a3.max_total},
        "a4": {"strengths": a4.strengths, "gaps": a4.gaps, "actions": a4.actions, "tone": a4.tone},
    }

# ---------- CLI ----------

def main():
    p = argparse.ArgumentParser(description="Assignment Grader")
    p.add_argument(
        "--dir",
        required=True,
        help="Path to the assignment folder (must contain instructions.txt, rubric.json, and submissions/).",
    )
    p.add_argument(
        "--mode",
        choices=["csv", "canvas"],
        default="csv",
        help="Output mode. 'csv' writes results to a CSV file. 'canvas' posts directly to Canvas API. "
            f"(default: %(default)s)",
    )
    p.add_argument(
        "--grading-mode",
        choices=["forgiving", "realistic", "strict"],
        default="forgiving",
        help="Grading strictness policy. 'forgiving' gives higher floor scores, 'realistic' balances, "
            "'strict' penalizes every miss. (default: %(default)s)",
    )
    p.add_argument(
        "--tone",
        choices=["encouraging", "neutral", "formal", "critical"],
        default="encouraging",
        help="Tone of instructor feedback. Controls wording of Agent 4 output. (default: %(default)s)",
    )
    p.add_argument(
        "--out-csv",
        default="grades_and_comments.csv",
        help="Path for CSV output when using --mode=csv. Ignored in canvas mode. (default: %(default)s)",
    )
    # Canvas-only params
    p.add_argument(
        "--canvas-base-url",
        help="Base URL of Canvas instance, e.g., https://utk.instructure.com. "
            "Required if --mode=canvas.",
    )
    p.add_argument(
        "--canvas-course-id",
        help="Canvas course ID (numeric). Required if --mode=canvas.",
    )
    p.add_argument(
        "--canvas-assignment-id",
        help="Canvas assignment ID (numeric). Required if --mode=canvas.",
    )
    p.add_argument(
        "--id-kind",
        choices=["sis_user_id", "login_id", "user_id"],
        default="sis_user_id",
        help="Identifier type used to match submissions with Canvas users. "
            "Options: sis_user_id, login_id, user_id. (default: %(default)s)",
    )
    args = p.parse_args()

    # Azure client from env
    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    )

    assign_dir = Path(args.dir)
    instr_path = assign_dir / "instructions.txt"
    rubric_json_path = assign_dir / "rubric.json"
    subs_dir = assign_dir / "submissions"
    outputs_dir = assign_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    reqs_text = instr_path.read_text(encoding="utf-8")
    rubric = json.loads(rubric_json_path.read_text(encoding="utf-8"))
    rubric = validate_rubric(rubric)

    # iterate submissions (.txt and .md)
    rows_for_csv: list[tuple[str,int,str]] = []
    for sub_file in sorted(list(subs_dir.glob("*.txt")) + list(subs_dir.glob("*.md"))):
        student_id = sub_file.stem  # e.g., SIS id or login
        submission_text = sub_file.read_text(encoding="utf-8", errors="ignore")
        result = run_pipeline_for_student(
            client,
            submission_text,
            reqs_text,
            rubric,
            grading_mode=args.grading_mode,
            tone_mode=args.tone,
        )
        # write artifacts
        (outputs_dir / f"{student_id}.a2.json").write_text(json.dumps(result["a2"], indent=2), encoding="utf-8")
        (outputs_dir / f"{student_id}.a3.json").write_text(json.dumps(result["a3"], indent=2), encoding="utf-8")
        (outputs_dir / f"{student_id}.a4.json").write_text(json.dumps(result["a4"], indent=2), encoding="utf-8")
        (outputs_dir / f"{student_id}.feedback.html").write_text(result["comment_html"], encoding="utf-8")
        (outputs_dir / f"{student_id}.feedback.txt").write_text(result["comment_text"], encoding="utf-8")

        rows_for_csv.append((student_id, result["grade"], result["comment_text"]))


    if args.mode == "csv":
        export_csv(rows_for_csv, Path(args.out_csv))
    else:
        # Canvas push
        base_url = args.canvas_base_url or os.environ.get("CANVAS_BASE_URL")
        token = os.environ.get("CANVAS_TOKEN")
        course_id = args.canvas_course_id or os.environ.get("CANVAS_COURSE_ID")
        assignment_id = args.canvas_assignment_id or os.environ.get("CANVAS_ASSIGNMENT_ID")
        if not all([base_url, token, course_id, assignment_id]):
            raise SystemExit("Canvas mode requires --canvas-base-url, --canvas-course-id, --canvas-assignment-id and CANVAS_TOKEN env.")
        client_canvas = CanvasClient(base_url, token)
        for sid, grade, comment in rows_for_csv:
            client_canvas.grade_and_comment(
                course_id=course_id,
                assignment_id=assignment_id,
                user_identifier=sid,
                id_kind=args.id_kind,
                score=grade,
                comment=comment,
            )

if __name__ == "__main__":
    main()
