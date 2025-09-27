import os
import pytest
from openai import AzureOpenAI

from agents.a1_cleaner import clean_text
from agents.a2_alignment import load_requirements_from_text, align_to_instructions, A2Result
from agents.a3_grader import validate_rubric, grade_by_rubric, A3Result
from agents.a4_feedback import build_feedback, A4Result
from agents.a5_report import summarize, ReportSummary

REQUIRED_ENV = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
]

pytestmark = pytest.mark.skipif(
    not all(os.getenv(k) for k in REQUIRED_ENV),
    reason="Azure OpenAI env vars not set"
)

def _client():
    return AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    )

def test_pipeline_a1_to_a5_live_model():
    client = _client()

    # Inputs
    instructions = """- State a clear thesis.
- Provide at least two pieces of evidence.
- Include a concluding paragraph."""
    rubric = validate_rubric({
        "criteria": [
            {"id": "C1", "text": "Thesis clarity", "max_score": 5},
            {"id": "C2", "text": "Use of evidence", "max_score": 10},
            {"id": "C3", "text": "Organization", "max_score": 5},
        ]
    })
    submission = (
        "This essay argues that campus recycling reduces waste. "
        "It cites a 2023 facilities report and a student survey as evidence. "
        "In conclusion, the paper recommends expanding bin locations."
    )

    # A1
    a1 = clean_text(submission)
    assert a1.stats["words"] > 0

    # A2
    reqs = load_requirements_from_text(instructions)
    a2 = align_to_instructions(client, a1.text_clean, reqs)
    assert isinstance(a2, A2Result)
    assert set(a2.coverage.keys()) == {r["id"] for r in reqs}

    # A3
    a3 = grade_by_rubric(client, coverage=a2.__dict__, rubric=rubric, mode="realistic")
    assert isinstance(a3, A3Result)
    assert 0 <= a3.total <= a3.max_total == 20

    # A4
    a4 = build_feedback(client, grade_json={
        "scores": a3.scores, "total": a3.total, "max_total": a3.max_total
    }, coverage_json=a2.__dict__, tone_mode="neutral")
    assert isinstance(a4, A4Result)
    assert len(a4.actions) >= 1

    # A5
    rep = summarize(
        a3={"scores": a3.scores, "total": a3.total, "max_total": a3.max_total},
        a4={"strengths": a4.strengths, "gaps": a4.gaps, "actions": a4.actions},
        rubric=rubric
    )
    assert isinstance(rep, ReportSummary)
    assert rep.grade == int(a3.total)
    assert str(rep.comment_text) and str(rep.comment_html)
