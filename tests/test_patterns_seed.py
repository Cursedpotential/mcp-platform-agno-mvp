"""Tests for evidence.patterns — the behavioral-pattern seed (P2.1).

The seed is forensic reference data: what matters is fidelity to the ported
sources (module roster, weights, MCL mappings, phrase corpus), validation that
rejects malformed edits, and that the committed migration stays in sync with
the canonical JSON.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evidence.patterns import (
    MIGRATION_PATH,
    PatternSeed,
    emit_seed_sql,
    load_seed,
)


def test_seed_loads_and_validates():
    seed = load_seed()
    assert len(seed.mcl_factors) == 12  # a-l, exactly
    assert len(seed.modules) >= 28
    assert sum(len(m.phrases) for m in seed.modules) >= 240


def test_ported_module_fidelity():
    seed = load_seed()
    by_id = {m.id: m for m in seed.modules}

    # Spot-checks against the pattern-analyzer.ts source values.
    gas = by_id["gaslighting"]
    assert gas.polarity == "negative" and gas.weight == 90
    assert gas.mcl_factors == ["j", "k", "l"]
    assert "that never happened" in gas.phrases

    lb = by_id["love_bombing"]  # was dropped by a naive parser once — keep guarded
    assert lb.polarity == "positive" and lb.weight == 80 and len(lb.phrases) > 0

    assert by_id["darvo"].weight == 95
    assert by_id["reproductive_coercion"].weight == 100
    assert by_id["scheduling"].mcl_factors == ["a", "b", "d"]


def test_research_modules_flagged_and_unmapped():
    # Statutory mapping is an owner decision — research additions must arrive
    # unmapped and flagged for triage, never with invented MCL letters.
    seed = load_seed()
    research = [m for m in seed.modules if m.needs_review]
    assert {m.id for m in research} >= {
        "guilt_trip",
        "boundary_violation",
        "triangulation",
        "word_salad",
        "hoovering",
        "intermittent_reinforcement",
    }
    assert all(m.mcl_factors == [] for m in research)


def test_contradiction_rules_reference_known_modules():
    seed = load_seed()
    ids = {m.id for m in seed.modules}
    for rule in seed.contradiction_rules:
        assert rule.positive_module in ids
        assert set(rule.negative_modules) <= ids
    assert any(r.id == "love_bomb_devalue" for r in seed.contradiction_rules)


def test_validation_rejects_bad_edits():
    seed = load_seed().model_dump()

    bad = {**seed, "modules": seed["modules"] + [seed["modules"][0]]}
    with pytest.raises(ValidationError, match="duplicate module ids"):
        PatternSeed.model_validate(bad)

    bad = {**seed}
    bad["modules"] = [dict(seed["modules"][0], id="x", mcl_factors=["z"])] + seed["modules"][1:]
    with pytest.raises(ValidationError, match="invalid MCL letters"):
        PatternSeed.model_validate(bad)

    bad = {**seed, "mcl_factors": seed["mcl_factors"][:-1]}
    with pytest.raises(ValidationError, match="cover a-l"):
        PatternSeed.model_validate(bad)

    bad = {
        **seed,
        "contradiction_rules": seed["contradiction_rules"]
        + [
            {
                "id": "ghost",
                "positive_module": "does_not_exist",
                "negative_modules": [],
                "description": "x",
            }
        ],
    }
    with pytest.raises(ValidationError, match="unknown modules"):
        PatternSeed.model_validate(bad)


def test_migration_in_sync_with_seed():
    # The committed SQL must be exactly what the emitter produces from the
    # canonical JSON — regenerate with `python -m evidence.patterns`.
    assert MIGRATION_PATH.read_text(encoding="utf-8") == emit_seed_sql(load_seed())


def test_sql_escaping_of_apostrophes():
    sql = emit_seed_sql(load_seed())
    # the corpus is full of contractions ("you're crazy") — they must arrive doubled
    assert "you''re crazy" in sql
    assert "ON CONFLICT" in sql  # idempotent by construction
