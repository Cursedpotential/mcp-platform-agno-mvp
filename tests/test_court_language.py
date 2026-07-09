"""Tests for evidence.court_language — the court-safe language map + loader.

Load-bearing invariant: NO clinical/diagnostic term ever reaches a court-facing
string, and the map stays in sync with the analyzer prompt's category set. This
is a court-safety guarantee, not a nicety — a leak here is a prejudicial filing.
"""

from __future__ import annotations

import pytest

from server.analysis.court_language import (
    MAP_PATH,
    PROMPT_PATH,
    _FORBIDDEN_IN_COURT,
    analyzer_prompt,
    category_keys,
    court_safe_heading,
    load_language_map,
)

# The eight category keys the analyzer emits (rubric §4).
EXPECTED_KEYS = {
    "financial_control",
    "gaslighting_reality_distortion",
    "love_bombing_discarding_cycle",
    "triangulation_isolation",
    "instrumental_use_of_child",
    "legal_threats_procedural_abuse",
    "sexual_degradation_weaponized_intimacy",
    "cluster_b_traits_behavioral_indicators",
}


def test_map_loads_and_covers_all_categories():
    assert set(category_keys()) == EXPECTED_KEYS


def test_headings_are_court_safe_descriptive():
    # e.g. the internal 'gaslighting' key surfaces as behavior, not the label.
    assert court_safe_heading("gaslighting_reality_distortion") == "Undermining Confidence in Memory or Judgment"
    assert (
        court_safe_heading("cluster_b_traits_behavioral_indicators")
        == "Patterns of Avoiding Responsibility and Shifting Blame"
    )


def test_no_clinical_term_leaks_into_any_court_facing_string():
    data = load_language_map()
    for key, entry in data["categories"].items():
        heading = entry["court_safe_heading"].lower()
        for term in _FORBIDDEN_IN_COURT:
            assert term not in heading, f"{key} heading leaks {term!r}"
    # the internal_labels field MAY carry clinical terms (that's the mapping's
    # whole point) — but the court-safe heading must be clean. Sanity-check the
    # design actually moved a clinical label out of the heading:
    cb = data["categories"]["cluster_b_traits_behavioral_indicators"]
    assert any("narcissist" in lab.lower() or "cluster b" in lab.lower() for lab in cb["internal_labels"])


def test_unknown_category_raises():
    with pytest.raises(KeyError, match="unknown category"):
        court_safe_heading("not_a_category")


def test_validation_rejects_leaky_heading(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        '{"categories": {"x": {"court_safe_heading": "Narcissistic Behavior Pattern"}}}',
        encoding="utf-8",
    )
    load_language_map.cache_clear()
    with pytest.raises(ValueError, match="leaks clinical term"):
        load_language_map(str(bad))
    load_language_map.cache_clear()  # restore cached default for other tests


def test_analyzer_prompt_loads_and_is_court_safe_framed():
    text = analyzer_prompt()
    assert "never diagnose" in text.lower() or "not diagnose" in text.lower() or "never a diagnos" in text.lower()
    assert "symmetric" in text.lower()  # Kubicki symmetric-application caveat
    assert "[MESSAGE LOGS]" in text  # input placeholder present


def test_resource_files_exist():
    assert MAP_PATH.is_file()
    assert PROMPT_PATH.is_file()
