"""Tests for evidence.patterns — the behavioral-ontology migration chain.

Load-bearing contracts: the SQL VALUES parser is quote/paren-safe (patterns
contain commas, parens, and '' escapes), the chain prefix counts pin the
live-DB apply history (0006=153/512, 0007=164/527, 0008=165/661 — these are
the numbers the live smoke matches against), validation catches malformed
edits, and the P2.1 corpus is FULLY covered by the committed chain (the
don't-lose-the-patterns guarantee).
"""

from __future__ import annotations

from pathlib import Path

from server.analysis.patterns import (
    _split_rows,
    chain_prefix_counts,
    cross_check_corpus,
    load_chain,
    load_corpus,
    parse_migration,
    validate_chain,
)

# ---------------------------------------------------------------------------
# SQL VALUES parser
# ---------------------------------------------------------------------------


def test_split_rows_handles_quotes_commas_parens():
    body = """
 ('gaslighting','literal','you''re crazy',9,'G2'),
 ('guilt_trip','regex','how could you (do this|treat me) (to me|like this)',6,'sweep')
"""
    rows = _split_rows(body)
    assert len(rows) == 2
    assert rows[0][2] == "'you''re crazy'"  # escaped quote survives raw
    # parens and commas INSIDE the quoted regex don't split the row
    assert rows[1][2] == "'how could you (do this|treat me) (to me|like this)'"
    assert rows[1][3] == "6"


def test_split_rows_pg_array_literals():
    rows = _split_rows(" ('threats','Threats','negative',10,'{j,k}','{threat,intimidation}',false,'G1')")
    assert rows[0][4] == "'{j,k}'"
    assert rows[0][6] == "false"


# ---------------------------------------------------------------------------
# The committed chain
# ---------------------------------------------------------------------------


def test_chain_files_present_in_order():
    chain = load_chain()
    assert chain.files == [
        "0006_behavior_seed.sql",
        "0007_behavior_seed_sweep.sql",
        "0008_behavior_seed_pattern_analyzer.sql",
    ]


def test_prefix_counts_pin_live_apply_history():
    # These are the numbers the live smoke compares against — 0006/0007 match
    # the recorded live applies; 0008 is committed but pending owner apply.
    prefixes = chain_prefix_counts()
    assert [(p["through"], p["categories"], p["patterns"]) for p in prefixes] == [
        ("0006_behavior_seed.sql", 153, 512),
        ("0007_behavior_seed_sweep.sql", 164, 527),
        ("0008_behavior_seed_pattern_analyzer.sql", 165, 661),
    ]


def test_chain_validates_clean():
    assert validate_chain(load_chain()) == []


def test_sweep_delta_shape():
    chain = load_chain()
    sweep_cats = [c for c in chain.categories if c.migration == "0007_behavior_seed_sweep.sql"]
    assert len(sweep_cats) == 11
    assert {c.category_id for c in sweep_cats} >= {"guilt_trip", "boundary_violation", "pronoun_ratio"}
    # sweep rows are generic — none case-specific, all sweep-sourced
    assert all(c.source.startswith("sweep-2026-07-03") for c in sweep_cats)


def test_pattern_analyzer_delta_shape_and_court_safety():
    chain = load_chain()
    pa_pats = [p for p in chain.patterns if p.migration == "0008_behavior_seed_pattern_analyzer.sql"]
    assert len(pa_pats) == 134
    assert all(p.match_type == "literal" for p in pa_pats)
    # source + court-safety posture are SQL constants in the migration itself
    sql = (
        Path(__file__).parent.parent
        / "docs/planning/forensic-db-reconciliation/migrations/0008_behavior_seed_pattern_analyzer.sql"
    ).read_text(encoding="utf-8")
    assert "'P2.1:pattern-analyzer.ts'" in sql
    assert "bias_caution" in sql and "single_party_complainant" in sql
    assert "NOT YET APPLIED" in sql  # application is owner-gated


# ---------------------------------------------------------------------------
# Corpus coverage — the don't-lose-the-patterns guarantee
# ---------------------------------------------------------------------------


def test_corpus_fully_covered_by_chain():
    report = cross_check_corpus()
    assert report["missing_categories"] == []
    assert report["missing_phrase_count"] == 0, report["missing_phrases"]


def test_contradiction_rules_tracked_as_unhomed():
    # The live schema has no contradiction table yet — pending owner decision.
    # These rules must stay tracked in the corpus until they get a home.
    report = cross_check_corpus()
    assert set(report["unhomed_contradiction_rules"]) == {
        "love_bomb_devalue",
        "promise_broken",
        "apology_repeat",
        "affirmation_devaluation",
    }


def test_corpus_still_carries_the_verbatim_extraction():
    corpus = load_corpus()
    assert len(corpus["modules"]) >= 28
    assert sum(len(m["phrases"]) for m in corpus["modules"]) >= 240


# ---------------------------------------------------------------------------
# Validation catches malformed edits
# ---------------------------------------------------------------------------


def test_validation_flags_bad_rows(tmp_path):
    bad = tmp_path / "0009_bad.sql"
    bad.write_text(
        """
INSERT INTO analysis.behavior_category (...)
SELECT ... FROM (VALUES
 ('dup_cat','Dup','negative',5,'{j}','{}',false,'x'),
 ('dup_cat','Dup again','sideways',99,'{z}','{}',false,'x')
) AS v(category_id, label, polarity, default_severity, mcl_factors, aliases, is_case_specific, source)
ON CONFLICT DO NOTHING;

INSERT INTO analysis.detection_pattern (...)
SELECT ... CROSS JOIN (VALUES
 ('ghost_cat','regex','([unclosed',7,'x')
) AS v(category_id, match_type, pattern, severity, source)
ON CONFLICT DO NOTHING;
""",
        encoding="utf-8",
    )
    from server.analysis.patterns import OntologyChain

    cats, pats = parse_migration(bad)
    errs = validate_chain(OntologyChain(files=[bad.name], categories=cats, patterns=pats))
    text = "\n".join(errs)
    assert "duplicate category" in text
    assert "invalid polarity" in text
    assert "out of 0-10" in text
    assert "invalid MCL letters" in text
    assert "unknown category" in text
    assert "unusable regex" in text
