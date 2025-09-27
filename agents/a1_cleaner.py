import re
import unicodedata
from dataclasses import dataclass
from typing import Dict

# Zero-width chars (ZWSP, ZWNJ, ZWJ, BOM)
ZW_PATTERN = r"[\u200B-\u200D\uFEFF]"
NBSP = "\u00A0"

# Collapse runs of spaces/tabs per line; keep paragraph breaks
MULTISPACE = re.compile(r"[ \t]+")
MULTINEWLINE = re.compile(r"\n{3,}")   # cap to at most 2 newlines

# Join words split by hyphen at end of line: "exam-\nple" -> "example"
HARD_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")

SMART_QUOTES = (
    ("“", '"'), ("”", '"'), ("„", '"'), ("‟", '"'),
    ("‘", "'"), ("’", "'"), ("‚", "'"), ("‛", "'"),
)

CONTROL_CHARS = re.compile(
    "[\u0000-\u0008\u000B\u000C\u000E-\u001F]"  # C0 controls except \t \n \r
)

@dataclass
class CleanResult:
    text_clean: str
    stats: Dict[str, int]

def clean_text(
    raw: str,
    *,
    normalize_quotes: bool = True,
    fix_pdf_hyphenation: bool = True,
    collapse_spaces: bool = True
) -> CleanResult:
    if not isinstance(raw, str):
        raise TypeError("raw must be a string")

    # 1) Unicode normalize
    t = unicodedata.normalize("NFKC", raw)

    # 2) Remove control chars (keep \n) and zero-widths; NBSP -> space
    t = CONTROL_CHARS.sub("", t)
    t = re.sub(ZW_PATTERN, "", t)
    t = t.replace(NBSP, " ")

    # 3) Normalize newlines
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    # 4) Fix PDF hyphenation across line breaks
    if fix_pdf_hyphenation:
        prev = None
        while prev != t:
            prev = t
            t = HARD_HYPHEN_BREAK.sub(r"\1\2", t)

    # 5) Optional: normalize smart quotes to ASCII
    if normalize_quotes:
        for src, dst in SMART_QUOTES:
            t = t.replace(src, dst)

    # 6) Collapse spaces per line; cap blank lines to max two; trim
    if collapse_spaces:
        t = "\n".join(MULTISPACE.sub(" ", ln).strip() for ln in t.split("\n"))
        t = MULTINEWLINE.sub("\n\n", t)

    t = t.strip()
    return CleanResult(
        text_clean=t,
        stats={"chars": len(t), "words": len(t.split())}
    )
