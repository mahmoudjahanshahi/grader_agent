import os
import pytest
from openai import AzureOpenAI

from agents.a3_grader import grade_by_rubric, validate_rubric, A3Result

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

def _rubric():
    return {
        "criteria": [
            {"id": "C1", "text": "Thesis clarity", "max_score": 5},
            {"id": "C2", "text": "Use of evidence", "max_score": 10},
            {"id": "C3", "text": "Organization", "max_score": 5},
        ]
    }

def _coverage_good():
    # Simulated A2 output showing strong compliance
    return {
        "coverage": {
            "REQ_1": {"status": "met", "evidence": "clear thesis in intro"},
            "REQ_2": {"status": "met", "evidence": "two studies cited"},
            "REQ_3": {"status": "partial", "evidence": "conclusion brief"},
        },
        "gaps": [],
        "warnings": []
    }

def _coverage_weak():
    # Simulated A2 output showing weaker compliance
    return {
        "coverage": {
            "REQ_1": {"status": "partial", "evidence": "implied thesis only"},
            "REQ_2": {"status": "missed", "evidence": ""},
            "REQ_3": {"status": "partial", "evidence": "some structure issues"},
        },
        "gaps": ["Insufficient evidence"],
        "warnings": []
    }

def test_a3_integration_live_model_realistic():
    client = _client()
    rubric = validate_rubric(_rubric())

    res = grade_by_rubric(
        client,
        coverage=_coverage_good(),
        rubric=rubric,
        mode="realistic"
    )
    assert isinstance(res, A3Result)
    assert set(res.scores.keys()) == {"C1", "C2", "C3"}
    assert 0 <= res.total <= res.max_total == 20

def test_a3_integration_modes_monotonic_with_same_coverage():
    client = _client()
    rubric = validate_rubric(_rubric())
    cov = _coverage_weak()

    forgiving = grade_by_rubric(client, cov, rubric, mode="forgiving")
    realistic = grade_by_rubric(client, cov, rubric, mode="realistic")
    strict = grade_by_rubric(client, cov, rubric, mode="strict")

    # totals should not increase as strictness increases
    assert forgiving.total >= realistic.total >= strict.total
    # scores are within bounds
    for cid, entry in strict.scores.items():
        assert 0 <= entry["score"] <= entry["max"]
