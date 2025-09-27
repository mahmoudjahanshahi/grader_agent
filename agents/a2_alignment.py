from __future__ import annotations
import json, os, re
from dataclasses import dataclass
from typing import Dict, Any, List
from jsonschema import validate

# Result contract
@dataclass
class A2Result:
    coverage: Dict[str, Dict[str, str]]  # {"REQ_1": {"status": "met|partial|missed", "evidence": "..."}}
    gaps: List[str]
    warnings: List[str]

# Output schema for validation
_A2_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["coverage", "gaps", "warnings"],
    "properties": {
        "coverage": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["status", "evidence"],
                "properties": {
                    "status": {"type": "string", "enum": ["met", "partial", "missed"]},
                    "evidence": {"type": "string"}
                },
                "additionalProperties": False
            }
        },
        "gaps": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}}
    },
    "additionalProperties": False
}

# ---- Requirement extraction from plain text instructions ----

_BULLET = re.compile(r"^\s*(?:[-*•·]|[0-9]+[.)])\s+(.*)$")
_HEADING = re.compile(r"^\s*(?:#+\s+|[A-Z][A-Za-z0-9 ]{3,}:)(.*)$")

def load_requirements_from_text(instructions_text: str) -> List[Dict[str, str]]:
    """
    Parse requirements from plain text/Markdown instructions.
    - Prefer bullet/numbered lines.
    - Fallback to heading-like lines.
    - If nothing matches, use the whole text as one requirement.
    Returns: [{"id":"REQ_1","text":"..."}, ...]
    """
    if not isinstance(instructions_text, str):
        raise TypeError("instructions_text must be a string")
    lines = [ln.rstrip() for ln in instructions_text.splitlines()]
    reqs: List[Dict[str, str]] = []
    idx = 1
    for ln in lines:
        m = _BULLET.match(ln)
        if m:
            txt = m.group(1).strip()
            if txt:
                reqs.append({"id": f"REQ_{idx}", "text": txt})
                idx += 1
    if not reqs:
        for ln in lines:
            m = _HEADING.match(ln)
            if m:
                txt = m.group(1).strip() or ln.strip()
                if txt:
                    reqs.append({"id": f"REQ_{idx}", "text": txt})
                    idx += 1
    if not reqs:
        body = " ".join(ln.strip() for ln in lines if ln.strip())[:800]
        if not body:
            raise ValueError("instructions_text is empty")
        reqs = [{"id": "REQ_1", "text": body}]
    return reqs

# ---- LLM alignment ----

_SYSTEM = (
    "You align a student submission to a list of assignment requirements.\n"
    "Return STRICT JSON only with keys: coverage, gaps, warnings.\n"
    "For each requirement id, set status = met|partial|missed and include a short evidence quote from the submission.\n"
    "Do not invent facts not present in the submission. No scores.\n"
    "Return JSON where 'gaps' and 'warnings' are arrays (use [] if empty)."
)

_USER_TMPL = """REQUIREMENTS_LIST (JSON):
{requirements_json}

STUDENT_SUBMISSION:
{text_clean}

Return JSON with: coverage, gaps, warnings.
"""

def align_to_instructions(
    client,  # openai.AzureOpenAI or compatible client
    text_clean: str,
    requirements: List[Dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.1
) -> A2Result:
    """
    Pure function: takes cleaned submission text and a requirements list.
    Uses the provided OpenAI client to produce alignment JSON.
    - `client` must already be configured (endpoint, key, api_version).
    - `model`: deployment name; if None, reads from env AZURE_OPENAI_DEPLOYMENT.
    """
    if not isinstance(text_clean, str):
        raise TypeError("text_clean must be a string")
    if not isinstance(requirements, list) or not all("text" in r for r in requirements):
        raise ValueError("requirements must be a list of {'id','text'} dicts")

    model_name = model or os.environ["AZURE_OPENAI_DEPLOYMENT"]

    prompt = _USER_TMPL.format(
        requirements_json=json.dumps(requirements, ensure_ascii=False),
        text_clean=text_clean.strip()
    )

    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content
    data = json.loads(raw)

    # normalize optional fields
    for k in ("gaps", "warnings"):
        v = data.get(k, [])
        if isinstance(v, dict):
            v = [str(x) for x in v.values()] if v else []
        elif v in ("", None):
            v = []
        elif not isinstance(v, list):
            v = [str(v)]
        data[k] = v

    # coverage must be dict
    cov = data.get("coverage", {})
    if not isinstance(cov, dict):
        raise ValueError("coverage must be an object mapping requirement IDs")
    data["coverage"] = cov

    # shape validation
    validate(instance=data, schema=_A2_SCHEMA)

    # ensure coverage has exactly the requirement IDs
    req_ids = {r["id"] for r in requirements}
    cov = data.get("coverage", {})
    for rid in req_ids - set(cov.keys()):
        cov[rid] = {"status": "missed", "evidence": ""}
    for rid in list(cov.keys()):
        if rid not in req_ids:
            cov.pop(rid, None)

    return A2Result(
        coverage=cov,
        gaps=list(data.get("gaps", [])),
        warnings=list(data.get("warnings", [])),
    )
