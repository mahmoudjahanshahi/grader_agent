import json
from agents.a4_feedback import build_feedback, A4Result

# ---- Mock OpenAI client ----
class _Msg: 
    def __init__(self, content): self.content = content
class _Choice:
    def __init__(self, content): self.message = _Msg(content)
class _Completions:
    def __init__(self, payload): self._payload = payload
    def create(self, **kwargs):
        return type("Resp", (), {"choices": [_Choice(self._payload)]})
class _Chat:
    def __init__(self, payload): self.completions = _Completions(payload)
class MockClient:
    def __init__(self, payload_json: dict):
        self.chat = _Chat(json.dumps(payload_json))

def _grade_json():
    return {
        "scores": {
            "C1": {"score": 4, "max": 5, "justification": "Clear thesis"},
            "C2": {"score": 8, "max": 10, "justification": "Two sources"},
            "C3": {"score": 5, "max": 5, "justification": "Well organized"}
        },
        "total": 17, "max_total": 20
    }

def _coverage_json():
    return {
        "coverage": {
            "REQ_1": {"status": "met", "evidence": "intro thesis"},
            "REQ_2": {"status": "met", "evidence": "two studies"}
        },
        "gaps": [], "warnings": []
    }

def test_a4_shapes_and_tone_control():
    payload = {
        "strengths": ["Clear thesis", "Good structure"],
        "gaps": ["Conclusion brief"],
        "actions": ["Expand conclusion", "Add one scholarly source"]
    }
    client = MockClient(payload)
    res = build_feedback(client, _grade_json(), _coverage_json(), model="dummy", tone_mode="encouraging")
    assert isinstance(res, A4Result)
    assert len(res.strengths) >= 1
    assert len(res.actions) >= 1
    assert res.tone == "encouraging"  # instructor-controlled

def test_a4_normalizes_bad_shapes():
    # Model returns wrong shapes; agent should normalize
    payload = {
        "strengths": {"0": "Clear thesis"},
        "gaps": {},
        "actions": "Add citations"
    }
    client = MockClient(payload)
    res = build_feedback(client, _grade_json(), None, model="dummy", tone_mode="strict")
    assert res.tone == "strict"
    assert res.strengths == ["Clear thesis"]
    assert res.gaps == []
    assert res.actions == ["Add citations"]
