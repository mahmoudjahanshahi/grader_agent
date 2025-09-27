from __future__ import annotations
import json, os
from dataclasses import dataclass
from typing import Dict, Any, List
from jsonschema import validate

# -------- Output contract (tone is optional) --------
_FEEDBACK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["strengths", "gaps"],
    "properties": {
        "strengths": {"type": "array", "items": {"type": "string"}},
        "gaps":       {"type": "array", "items": {"type": "string"}},
        "tone":       {"type": "string"}
    },
    "additionalProperties": False
}

@dataclass
class A4Result:
    strengths: List[str]
    gaps: List[str]
    tone: str | None = None

_SYSTEM = (
    "You are an instructor writing concise, actionable feedback for a student.\n"
    "Use ONLY the provided grade JSON (scores/justifications) and optional coverage facts.\n"
    "Do not invent sources. Be specific and brief. Return STRICT JSON per schema."
)

_USER_TMPL = """TONE_MODE: {tone_mode}

GRADE_JSON:
{grade_json}

COVERAGE_JSON (optional):
{coverage_json}

Write feedback:
- 2–4 strengths (what worked, with brief evidence references).
- 2–4 gaps (what’s missing or weak).
- Keep sentences short and concrete. No fluff. No external facts.

Return JSON only with keys: strengths, gaps.
"""

def build_feedback(
    client,                 # AzureOpenAI client
    grade_json: Dict[str, Any],
    coverage_json: Dict[str, Any] | None = None,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    tone_mode: str = "neutral"        # instructor-controlled: "encouraging" | "neutral" | "strict" | etc.
) -> A4Result:
    """
    Inputs:
      - grade_json: A3 output (must include 'scores' with justifications)
      - coverage_json: optional A2 output (for evidence wording)
      - tone_mode: instructor-controlled tone descriptor applied to the feedback
    Output:
      - A4Result with strengths, gaps; tone is set to tone_mode
    """
    if not isinstance(grade_json, dict) or "scores" not in grade_json:
        raise ValueError("grade_json must be A3 output with key 'scores'")

    model_name = model or os.environ["AZURE_OPENAI_DEPLOYMENT"]

    prompt = _USER_TMPL.format(
        tone_mode=tone_mode,
        grade_json=json.dumps(grade_json, ensure_ascii=False),
        coverage_json=json.dumps(coverage_json or {}, ensure_ascii=False),
    )

    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    data = json.loads(resp.choices[0].message.content)

    # Normalize arrays
    for k in ("strengths", "gaps"):
        v = data.get(k, [])
        if isinstance(v, dict):
            v = [str(x) for x in v.values()] if v else []
        elif v in ("", None):
            v = []
        elif not isinstance(v, list):
            v = [str(v)]
        data[k] = v

    # Force tone to instructor-selected value
    data["tone"] = str(tone_mode)

    # Validate final shape
    validate(instance=data, schema=_FEEDBACK_SCHEMA)

    return A4Result(
        strengths=data["strengths"],
        gaps=data["gaps"],
        tone=data.get("tone"),
    )
