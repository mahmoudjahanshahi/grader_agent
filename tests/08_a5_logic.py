from agents.a5_report import summarize, ReportSummary

def _a3():
    return {
        "scores": {
            "C1": {"score": 4, "max": 5, "justification": "Clear thesis"},
            "C2": {"score": 8, "max": 10, "justification": "Two sources | peer-reviewed"},
        },
        "total": 12,
        "max_total": 15,
    }

def _a4():
    return {
        "strengths": ["Focused argument"],
        "gaps": ["Conclusion is brief"],
        "actions": ["Expand conclusion", "Add one source"],
    }

def _rubric():
    return {
        "criteria": [
            {"id": "C1", "text": "Thesis clarity", "max_score": 5},
            {"id": "C2", "text": "Use of evidence", "max_score": 10},
        ]
    }

def test_summarize_shapes_and_pass_through():
    rep = summarize(_a3(), _a4(), _rubric())
    assert isinstance(rep, ReportSummary)
    assert rep.grade == 12 and rep.max_total == 15
    assert isinstance(rep.comment_text, str)
    assert isinstance(rep.comment_html, str)

def test_text_contains_sections_no_tone():
    rep = summarize(_a3(), _a4(), _rubric())
    t = rep.comment_text
    assert "Total: 12 / 15" in t
    assert "Strengths:" in t and "Gaps:" in t and "Next actions:" in t
    assert "tone:" not in t  # tone removed from output

def test_html_table_and_content():
    rep = summarize(_a3(), _a4(), _rubric())
    html = rep.comment_html
    # table structure present
    assert "<table" in html and "<thead" in html and "<tbody" in html
    # rubric names are used
    assert "Thesis clarity" in html and "Use of evidence" in html
    # justification with pipe renders safely
    assert "Two sources | peer-reviewed" in html
