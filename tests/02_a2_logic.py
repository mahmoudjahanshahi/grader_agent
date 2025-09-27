import json
from agents.a2_alignment import (
    load_requirements_from_text,
    align_to_instructions,
    A2Result,
)

# ---- Mock OpenAI client ----
class _Msg:
    def __init__(self, content): self.content = content

class _Choice:
    def __init__(self, content): self.message = _Msg(content)

class _Completions:
    def __init__(self, payload): self._payload = payload
    def create(self, **kwargs):
        # Return the payload as if from the model
        return type("Resp", (), {"choices": [_Choice(self._payload)]})

class _Chat:
    def __init__(self, payload): self.completions = _Completions(payload)

class MockClient:
    def __init__(self, payload_json: dict):
        self.chat = _Chat(json.dumps(payload_json))

def test_load_requirements_from_text_bullets():
    instructions = """- State a clear thesis.
- Provide at least two pieces of evidence.
- Include a concluding paragraph."""
    reqs = load_requirements_from_text(instructions)
    assert len(reqs) == 3
    assert reqs[0]["id"] == "REQ_1" and "thesis" in reqs[0]["text"].lower()
    assert all("text" in r and r["text"] for r in reqs)

def test_align_to_instructions_with_mock_client():
    # Pretend the model aligned three requirements
    payload = {
        "coverage": {
            "REQ_1": {"status": "met", "evidence": "states a thesis"},
            "REQ_2": {"status": "partial", "evidence": "one study cited"},
            "REQ_3": {"status": "missed", "evidence": ""}
        },
        "gaps": ["No concluding paragraph"],
        "warnings": []
    }
    client = MockClient(payload)
    requirements = [
        {"id": "REQ_1", "text": "State a clear thesis."},
        {"id": "REQ_2", "text": "Provide at least two pieces of evidence."},
        {"id": "REQ_3", "text": "Include a concluding paragraph."},
    ]
    res = align_to_instructions(client, "Sample submission text.", requirements, model="dummy")
    assert isinstance(res, A2Result)
    assert set(res.coverage.keys()) == {"REQ_1", "REQ_2", "REQ_3"}
    assert res.coverage["REQ_1"]["status"] == "met"
    assert res.coverage["REQ_2"]["status"] == "partial"
    assert res.coverage["REQ_3"]["status"] == "missed"
    assert "No concluding paragraph" in res.gaps
