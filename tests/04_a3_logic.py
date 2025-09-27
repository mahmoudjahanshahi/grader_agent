import json
from agents.a3_grader import grade_by_rubric, validate_rubric, A3Result

# ----- Mock OpenAI client -----
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

def _rubric():
    return {
        "criteria": [
            {"id": "C1", "text": "Thesis clarity", "max_score": 5},
            {"id": "C2", "text": "Use of evidence", "max_score": 10},
            {"id": "C3", "text": "Organization", "max_score": 5},
        ]
    }

def _coverage():
    # Simplified A2 output shape
    return {
        "coverage": {
            "REQ_1": {"status": "met", "evidence": "clear thesis"},
            "REQ_2": {"status": "partial", "evidence": "one study"},
            "REQ_3": {"status": "missed", "evidence": ""},
        },
        "gaps": ["Conclusion weak"],
        "warnings": []
    }

def test_a3_basic_shape_and_totals():
    # Model base output (before mode adjustments)
    payload = {
        "scores": {
            "C1": {"score": 4, "max": 5, "justification": "Clear thesis"},
            "C2": {"score": 7, "max": 10, "justification": "Some evidence"},
            "C3": {"score": 3, "max": 5, "justification": "Mostly organized"}
        },
        "total": 14, "max_total": 20
    }
    client = MockClient(payload)
    rubric = validate_rubric(_rubric())
    res = grade_by_rubric(client, coverage=_coverage(), rubric=rubric, model="dummy", mode="realistic")
    assert isinstance(res, A3Result)
    # ensure all rubric criteria present and clamped
    assert set(res.scores.keys()) == {"C1", "C2", "C3"}
    assert res.scores["C1"]["max"] == 5 and 0 <= res.scores["C1"]["score"] <= 5
    assert res.max_total == 20
    assert 0 <= res.total <= 20

def test_a3_mode_monotonicity():
    payload = {
        "scores": {
            "C1": {"score": 3, "max": 5, "justification": ""},
            "C2": {"score": 6, "max": 10, "justification": ""},
            "C3": {"score": 4, "max": 5, "justification": ""}
        },
        "total": 13, "max_total": 20
    }
    client = MockClient(payload)
    rubric = validate_rubric(_rubric())
    cov = _coverage()

    forgiving = grade_by_rubric(client, cov, rubric, model="dummy", mode="forgiving")
    realistic = grade_by_rubric(client, cov, rubric, model="dummy", mode="realistic")
    strict = grade_by_rubric(client, cov, rubric, model="dummy", mode="strict")

    assert forgiving.total >= realistic.total >= strict.total
    # per-criterion should also not increase when going stricter
    for cid in ("C1","C2","C3"):
        assert forgiving.scores[cid]["score"] >= realistic.scores[cid]["score"] >= strict.scores[cid]["score"]

def test_a3_clamps_and_fills_missing_criteria():
    # Model forgets C3 and overshoots C2
    payload = {
        "scores": {
            "C1": {"score": 5, "max": 5, "justification": ""},
            "C2": {"score": 99, "max": 10, "justification": ""}  # should clamp to 10
        },
        "total": 104, "max_total": 20
    }
    client = MockClient(payload)
    rubric = validate_rubric(_rubric())
    res = grade_by_rubric(client, coverage=_coverage(), rubric=rubric, model="dummy", mode="realistic")

    # C2 clamped, C3 filled with defaults, totals recomputed
    assert res.scores["C2"]["score"] == 10
    assert "C3" in res.scores and 0 <= res.scores["C3"]["score"] <= 5
    assert res.max_total == 20
