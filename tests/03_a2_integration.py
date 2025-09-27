import os
import pytest
from openai import AzureOpenAI
from agents.a1_cleaner import clean_text
from agents.a2_alignment import load_requirements_from_text, align_to_instructions, A2Result

REQUIRED_ENV = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT",
]

def _env_ready():
    return all(os.getenv(k) for k in REQUIRED_ENV)

pytestmark = pytest.mark.skipif(not _env_ready(), reason="Azure OpenAI env vars not set")

def _client():
    return AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    )

def test_a2_integration_live_model():
    client = _client()

    instructions = """- State a clear thesis.
- Provide at least two pieces of evidence.
- Include a concluding paragraph."""

    submission = (
        "This essay argues that campus recycling reduces waste. "
        "It cites a 2023 facilities report and a student survey as evidence. "
        "In conclusion, the paper recommends expanding bin locations."
    )

    # A1 clean
    cleaned = clean_text(submission)

    # Build requirements from instructions.txt text
    reqs = load_requirements_from_text(instructions)

    # A2 align (hits your live deployment)
    res = align_to_instructions(client, cleaned.text_clean, reqs)

    # Basic shape checks
    assert isinstance(res, A2Result)
    assert set(res.coverage.keys()) == {r["id"] for r in reqs}
    for v in res.coverage.values():
        assert v["status"] in {"met", "partial", "missed"}
        assert isinstance(v["evidence"], str)

    # Sanity expectation: at least thesis or evidence should be met/partial
    statuses = {k: v["status"] for k, v in res.coverage.items()}
    assert any(s in {"met", "partial"} for s in statuses.values())
