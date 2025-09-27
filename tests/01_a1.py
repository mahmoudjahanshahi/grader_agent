import re
from agents.a1_cleaner import clean_text, CleanResult

RAW = """\ufeff“This is, like, an ex-
ample”\u00A0with ZW\u200B and ZWJ\u200D chars.
Paragraph  one\twith   extra    spaces.

Line with [1] citation and smart ‘quotes’.
"""

def test_returns_dataclass_and_basic_stats():
    r = clean_text(RAW)
    assert isinstance(r, CleanResult)
    assert isinstance(r.text_clean, str)
    assert r.stats["chars"] == len(r.text_clean)
    assert r.stats["words"] == len(r.text_clean.split())

def test_removes_zero_width_and_nbsp():
    r = clean_text(RAW)
    assert "\u200B" not in r.text_clean and "\u200D" not in r.text_clean
    assert "\u00A0" not in r.text_clean  # NBSP replaced with space

def test_fixes_pdf_hyphenation():
    r = clean_text(RAW)
    assert "example" in r.text_clean
    assert "ex-\nample" not in r.text_clean

def test_collapses_spaces_and_preserves_paragraphs():
    r = clean_text(RAW)
    # No runs of >1 spaces or tabs within a line
    for line in r.text_clean.split("\n"):
        assert re.search(r"[ \t]{2,}", line) is None
    # At most two consecutive newlines
    assert "\n\n\n" not in r.text_clean

def test_keeps_citations_and_content():
    r = clean_text(RAW)
    assert "[1]" in r.text_clean
    assert "like" in r.text_clean  # no semantic deletions

def test_normalizes_quotes_by_default():
    r = clean_text(RAW)
    assert "“" not in r.text_clean and "”" not in r.text_clean
    assert "‘" not in r.text_clean and "’" not in r.text_clean
    assert '"' in r.text_clean or "'" in r.text_clean

def test_can_disable_quote_normalization():
    r = clean_text(RAW, normalize_quotes=False)
    # original smart quotes remain when disabled
    assert "“" in r.text_clean or "”" in r.text_clean or "‘" in r.text_clean or "’" in r.text_clean
