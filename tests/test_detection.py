"""Tests for evidence.detection — the behavioral detection runner's pure core.

No DB: exercises scan_record / Pattern.compiled / subject mapping /
_finding_params. What matters forensically: literal+keyword span discovery,
regex sentinel handling for unusable patterns, match caps, context capture,
and that every finding carries the COURT-SAFETY posture (bias_caution,
hypothesis-not-conclusion fields) unchanged from the pattern.
"""

from __future__ import annotations

from server.analysis.detection import (
    CONTEXT_CHARS,
    MAX_HITS_PER_PATTERN,
    Match,
    Pattern,
    _finding_params,
    scan_record,
    subject_type_for,
)


def _pat(**kw) -> Pattern:
    base: dict[str, object] = {
        "id": "p1",
        "pattern_set_id": "set1",
        "category_id": "gaslighting",
        "subcategory": None,
        "match_type": "literal",
        "pattern": "you're crazy",
    }
    base.update(kw)
    return Pattern(**base)  # type: ignore[arg-type]


def test_literal_scan_finds_phrase_and_keywords_case_insensitively():
    p = _pat(keywords=("imagining things",))
    content = "You're CRAZY. Stop imagining things. you're crazy again."
    matches = scan_record(content, [p])
    texts = sorted(m.matched_text.lower() for m in matches)
    assert texts == ["imagining things", "you're crazy", "you're crazy"]
    # spans are real offsets into the ORIGINAL content (verbatim capture)
    m0 = next(m for m in matches if m.start_char == 0)
    assert content[m0.start_char : m0.end_char] == "You're CRAZY"


def test_context_capture_is_bounded():
    p = _pat(pattern="target")
    content = ("a" * 200) + "target" + ("b" * 200)
    [m] = scan_record(content, [p])
    assert m.context_before == "a" * CONTEXT_CHARS
    assert m.context_after == "b" * CONTEXT_CHARS


def test_regex_pattern_matches_and_reports_method():
    p = _pat(match_type="regex", pattern=r"call(ed|ing)?\s+block", id="rx1")
    matches = scan_record("She called block- no, call blocked me again", [p])
    assert matches and all(m.detection_method == "regex" for m in matches)


def test_unusable_regex_is_skipped_cleanly():
    bad = _pat(match_type="regex", pattern=r"([unclosed", id="bad")
    good = _pat(pattern="hello", id="ok")
    matches = scan_record("hello hello", [bad, good])
    # bad regex contributes nothing; literal still fires (sentinel path)
    assert {m.pattern.id for m in matches} == {"ok"}
    assert bad.compiled() is False  # cached unusable sentinel


def test_match_cap_bounds_blowups():
    p = _pat(match_type="regex", pattern=r"x", id="flood")
    matches = scan_record("x" * (MAX_HITS_PER_PATTERN * 3), [p])
    assert len(matches) == MAX_HITS_PER_PATTERN


def test_empty_content_returns_nothing():
    assert scan_record(None, [_pat()]) == []
    assert scan_record("", [_pat()]) == []


def test_subject_type_mapping_defaults_to_message():
    assert subject_type_for("message") == "message"
    assert subject_type_for("SMS") == "message"
    assert subject_type_for("weird-unknown") == "message"
    assert subject_type_for(None) == "message"


def test_finding_params_carries_court_safety_posture():
    p = _pat(bias_caution=True, authored_perspective="single_party_complainant", severity=8, score=80)
    [m] = scan_record("well you're crazy", [p])
    params = _finding_params({"id": "rec-1", "record_type": "message"}, m, "prov-9")

    # hypothesis-not-conclusion invariants
    assert params["bias_caution"] is True
    assert params["authored_perspective"] == "single_party_complainant"
    assert params["author_party"] is None  # attribution deferred by design
    # provenance + verbatim capture
    assert params["provenance_id"] == "prov-9"
    assert params["matched_text"] == "you're crazy"
    assert params["category_id"] == "gaslighting"
    assert params["start_char"] == 5 and params["end_char"] == 17


def test_match_is_dataclass_with_offsets():
    [m] = scan_record("abc you're crazy xyz", [_pat()])
    assert isinstance(m, Match)
    assert m.matched_pattern == "you're crazy"
