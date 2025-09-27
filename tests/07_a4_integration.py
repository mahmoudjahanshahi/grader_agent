import os, pytest
from openai import AzureOpenAI
from agents.a4_feedback import build_feedback, A4Result

REQUIRED_ENV = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
]
pytestmark = pytest.mark.skipif(not all(os.getenv(k) for k in REQUIRED_ENV),
                                reason="Azure OpenAI env vars not set")

def _client():
    return AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    )

def test_a4_integration_live_model():
    client = _client()
    grade_json = {
        "scores": {
            "C1": {"score": 4, "max": 5, "justification": "Clear thesis"},
            "C2": {"score": 7, "max": 10, "justification": "Some evidence"},
            "C3": {"score": 4, "max": 5, "justification": "Mostly organized"}
        },
        "total": 15, "max_total": 20
    }
    coverage_json = {
        "coverage": {
            "REQ_1": {"status": "met", "evidence": "intro thesis"},
            "REQ_2": {"status": "partial", "evidence": "one study"}
        },
        "gaps": [], "warnings": []
    }
    res = build_feedback(client, grade_json, coverage_json, tone_mode="neutral")
    assert isinstance(res, A4Result)
    assert len(res.strengths) >= 1
    assert len(res.actions) >= 1
    assert res.tone == "neutral"
