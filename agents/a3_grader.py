from __future__ import annotations
import json, os
from dataclasses import dataclass
from typing import Dict, Any, List
from jsonschema import validate
from math import floor
EPS = 1e-9

# ---------- Rubric schema (criteria + max_score) ----------
_RUBRIC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["criteria"],
    "properties": {
        "criteria": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "text", "max_score"],
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "max_score": {"type": "number", "minimum": 0}
                },
                "additionalProperties": True
            }
        }
    },
    "additionalProperties": True
}

# ---------- Output schema ----------
_A3_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["scores", "total", "max_total"],
    "properties": {
        "scores": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["score", "max", "justification"],
                "properties": {
                    "score": {"type": "number", "minimum": 0},
                    "max": {"type": "number", "minimum": 0},
                    "justification": {"type": "string"}
                },
                "additionalProperties": False
            }
        },
        "total": {"type": "number", "minimum": 0},
        "max_total": {"type": "number", "minimum": 0}
    },
    "additionalProperties": False
}

@dataclass
class A3Result:
    scores: Dict[str, Dict[str, Any]]  # {"C1":{"score":4,"max":5,"justification":"..."}}
    total: float
    max_total: float

# ---------- Modes ----------
_MODE_POLICY = {
    "forgiving": {"partial_factor": 0.8, "missed_factor": 0.4, "bonus_floor": 0.2, "round": "nearest"},
    "realistic": {"partial_factor": 0.6, "missed_factor": 0.2, "bonus_floor": 0.1, "round": "nearest"},
    "strict":    {"partial_factor": 0.4, "missed_factor": 0.1, "bonus_floor": 0.0, "round": "nearest"},
}

def _mode_note(mode: str) -> str:
    if mode == "forgiving":
        return ("When uncertain, prefer higher scores. Small issues reduce few points. "
                "Partial compliance should earn a majority of the max.")
    if mode == "strict":
        return ("Penalize any variance. Partial compliance earns a small fraction. "
                "Be conservative and deduct wherever requirements are weak.")
    return ("Be neutral and reasonable. Balance strengths and weaknesses.")

# ---------- Prompts ----------
_SYSTEM = (
    "You are a strict grader. Use the rubric to assign scores per criterion.\n"
    "Use only information found in the COVERAGE facts and short quotes from the submission evidence.\n"
    "No external facts. No hallucinations. Be consistent. Return STRICT JSON matching the schema."
)

_USER_TMPL = """RUBRIC (JSON):
{rubric_json}

COVERAGE (JSON from A2):
{coverage_json}

Return JSON:
{{
  "scores": {{
    "<criterion_id>": {{"score": <0..max>, "max": <max>, "justification": "<1-2 sentences>"}}
  }},
  "total": <sum of scores>,
  "max_total": <sum of max values>
}}
Rules:
- For each rubric criterion id, produce an entry in "scores".
- Justification must reference the coverage statuses/evidence where relevant.
- Use whole numbers when possible; otherwise allow one decimal.
- Do not exceed each criterion's max_score.
- Mode guidance: {mode_note}
"""

# ---------- Public API ----------
def validate_rubric(rubric: Dict[str, Any]) -> Dict[str, Any]:
    validate(instance=rubric, schema=_RUBRIC_SCHEMA)
    # normalize and compute max_total
    crits = rubric["criteria"]
    max_total = 0.0
    ids = set()
    for c in crits:
        cid = c["id"]
        if cid in ids:
            raise ValueError(f"Duplicate criterion id: {cid}")
        ids.add(cid)
        max_total += float(c["max_score"])
    rubric["_max_total"] = max_total
    return rubric

def _apply_mode_policy(scores: dict, coverage: dict, rubric: dict, mode: str) -> dict:
    """Deterministic adjustment of model scores per mode using A2 coverage as a coarse signal."""
    pol = _MODE_POLICY[mode]
    cov = coverage.get("coverage", {})
    out = {}
    # overall requirement status fractions
    statuses = [v.get("status", "missed") for v in cov.values()]
    partial = statuses.count("partial"); 
    missed = statuses.count("missed")
    total_req = max(1, len(statuses))
    frac_missed = missed / total_req
    frac_partial = partial / total_req

    for crit in rubric["criteria"]:
        cid, maxv = crit["id"], float(crit["max_score"])
        entry = scores.get(cid, {"score": 0, "max": maxv, "justification": ""})
        base = float(entry.get("score", 0))

        if base >= maxv - EPS:
            out[cid] = {"score": maxv, "max": maxv, "justification": entry.get("justification","")}
            continue

        # scale down the impact of misses/partials depending on mode
        adj = base
        adj *= (1 - frac_missed*(1 - pol["missed_factor"]) - frac_partial*(1 - pol["partial_factor"]))

        # minimum floor in forgiving mode
        if pol["bonus_floor"] > 0:
            adj = max(adj, pol["bonus_floor"] * maxv)

        # rounding
        if pol["round"] == "down":
            adj = floor(adj + EPS)
        else:
            adj = floor(adj + 0.5)

        # clamp
        adj = max(0, min(maxv, adj))
        out[cid] = {"score": adj, "max": maxv, "justification": entry.get("justification", "")}
    return out

def grade_by_rubric(
    client,                 # AzureOpenAI client (configured)
    coverage: Dict[str, Any],
    rubric: Dict[str, Any],
    *,
    model: str | None = None,
    temperature: float = 0.1,
    mode: str = "realistic"
) -> A3Result:
    """
    Inputs:
      - client: AzureOpenAI client
      - coverage: output dict from A2 (must contain key 'coverage')
      - rubric: {"criteria":[{"id","text","max_score"},...]}
      - mode: "forgiving" | "realistic" | "strict"
    Output:
      - A3Result with per-criterion scores, total, max_total
    """
    if mode not in _MODE_POLICY:
        raise ValueError("mode must be one of: forgiving, realistic, strict")
    if not isinstance(coverage, dict) or "coverage" not in coverage:
        raise ValueError("coverage must be A2 output dict containing key 'coverage'")

    rubric = validate_rubric(rubric)
    model_name = model or os.environ["AZURE_OPENAI_DEPLOYMENT"]

    prompt = _USER_TMPL.format(
        rubric_json=json.dumps(rubric, ensure_ascii=False),
        coverage_json=json.dumps(coverage, ensure_ascii=False),
        mode_note=_mode_note(mode)
    )

    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    data = json.loads(resp.choices[0].message.content)

    # --- Normalize to schema ---
    if "scores" not in data or not isinstance(data["scores"], dict):
        data["scores"] = {}

    # Ensure every rubric criterion is present; clamp to max
    expected_ids = [c["id"] for c in rubric["criteria"]]
    max_map = {c["id"]: float(c["max_score"]) for c in rubric["criteria"]}
    for cid in expected_ids:
        entry = data["scores"].get(cid, {})
        score = entry.get("score", 0)
        just = entry.get("justification", "")
        try:
            score = float(score)
        except Exception:
            score = 0.0
        max_allowed = max_map[cid]
        if score < 0:
            score = 0.0
        if score > max_allowed:
            score = max_allowed
        data["scores"][cid] = {"score": score, "max": max_allowed, "justification": str(just)}

    # Drop unexpected criterion keys
    for cid in list(data["scores"].keys()):
        if cid not in max_map:
            data["scores"].pop(cid, None)

    # Apply mode policy deterministically
    data["scores"] = _apply_mode_policy(data["scores"], coverage, rubric, mode)

    # Recompute totals
    total = sum(v["score"] for v in data["scores"].values())
    max_total = sum(v["max"] for v in data["scores"].values())
    data["total"] = float(total)
    data["max_total"] = float(max_total)

    # Final validation
    validate(instance=data, schema=_A3_SCHEMA)

    return A3Result(scores=data["scores"], total=data["total"], max_total=data["max_total"])
