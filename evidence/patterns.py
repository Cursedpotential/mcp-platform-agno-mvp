"""evidence/patterns.py — behavioral-pattern seed: models, loader, SQL emitter.

The pattern library (P2.1, port-backlog Tier 1) as DATA: 28 analysis modules
(22 coded in the pre-Agno pattern-analyzer + 6 research-taxonomy additions),
their indicator phrases, MCL 722.23 factor mappings, and contradiction rules.
Canonical source: evidence/config/behavioral_patterns.json (provenance per
module). This module validates the seed and generates the self-contained
sql/0005_behavioral_patterns.sql migration from it.

Regenerate the migration after editing the seed JSON:
    python -m evidence.patterns

Owner triage: modules with needs_review=True carry NO MCL mapping and few/no
phrases — statutory mapping is an owner decision, never inferred here.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

SEED_PATH = Path(__file__).parent / "config" / "behavioral_patterns.json"
MIGRATION_PATH = Path(__file__).parent.parent / "sql" / "0005_behavioral_patterns.sql"

MCL_LETTERS = tuple("abcdefghijkl")
POLARITIES = ("negative", "positive", "neutral")


class MclFactor(BaseModel):
    letter: str
    name: str
    description: str

    @field_validator("letter")
    @classmethod
    def _letter(cls, v: str) -> str:
        if v not in MCL_LETTERS:
            raise ValueError(f"invalid MCL factor letter {v!r}")
        return v


class PatternModule(BaseModel):
    id: str
    name: str
    description: str
    polarity: str
    subcategory: str
    weight: int = Field(ge=0, le=100)
    mcl_factors: list[str] = Field(default_factory=list)
    phrases: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    provenance: str = ""
    needs_review: bool = False

    @field_validator("polarity")
    @classmethod
    def _polarity(cls, v: str) -> str:
        if v not in POLARITIES:
            raise ValueError(f"invalid polarity {v!r}")
        return v

    @field_validator("mcl_factors")
    @classmethod
    def _factors(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in MCL_LETTERS]
        if bad:
            raise ValueError(f"invalid MCL letters {bad}")
        return v

    @field_validator("phrases")
    @classmethod
    def _phrases(cls, v: list[str]) -> list[str]:
        if any(not p.strip() for p in v):
            raise ValueError("empty phrase")
        if len(set(p.lower() for p in v)) != len(v):
            raise ValueError("duplicate phrases within module")
        return v


class ContradictionRule(BaseModel):
    id: str
    positive_module: str
    negative_modules: list[str] = Field(default_factory=list)
    description: str
    provenance: str = ""


class PatternSeed(BaseModel):
    meta: dict
    mcl_factors: list[MclFactor]
    modules: list[PatternModule]
    contradiction_rules: list[ContradictionRule]

    @model_validator(mode="after")
    def _cross_check(self) -> "PatternSeed":
        ids = [m.id for m in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate module ids")
        letters = {f.letter for f in self.mcl_factors}
        if letters != set(MCL_LETTERS):
            raise ValueError(f"mcl_factors must cover a-l exactly, got {sorted(letters)}")
        known = set(ids)
        for rule in self.contradiction_rules:
            missing = [m for m in [rule.positive_module, *rule.negative_modules] if m not in known]
            if missing:
                raise ValueError(f"contradiction rule {rule.id!r} references unknown modules {missing}")
        return self


def load_seed(path: Path = SEED_PATH) -> PatternSeed:
    """Load + validate the canonical seed JSON."""
    return PatternSeed.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _q(s: str) -> str:
    """SQL single-quote escape."""
    return "'" + s.replace("'", "''") + "'"


def _arr(items: list[str]) -> str:
    if not items:
        return "'{}'"
    return "ARRAY[" + ", ".join(_q(i) for i in items) + "]"


def emit_seed_sql(seed: PatternSeed) -> str:
    """Render the full, idempotent migration (DDL + seed rows)."""
    lines: list[str] = []
    a = lines.append

    a("-- 0005_behavioral_patterns.sql — behavioral pattern library as data (P2.1).")
    a("--")
    a("-- GENERATED from evidence/config/behavioral_patterns.json by")
    a("-- `python -m evidence.patterns` — edit the JSON, not this file.")
    a(
        f"-- Seed: {len(seed.modules)} modules, "
        f"{sum(len(m.phrases) for m in seed.modules)} phrases, "
        f"{len(seed.mcl_factors)} MCL factors, "
        f"{len(seed.contradiction_rules)} contradiction rules."
    )
    a("--")
    a("-- Provenance: pre-Agno pattern-analyzer.ts BUILT_IN_MODULES/BUILT_IN_PATTERNS,")
    a("-- forensics-router.ts MCL_FACTORS, RESEARCH_BEHAVIORAL_ANALYSIS.md taxonomy")
    a("-- (see docs/planning/port-backlog.md Tier 1). needs_review rows have NO MCL")
    a("-- mapping by design — statutory mapping is an owner decision.")
    a("--")
    a("-- Idempotent: re-running upserts the seed. Requires 0002 (analysis schema)")
    a("-- and 0004 (mcl_factor enum).")
    a("")
    a("CREATE TABLE IF NOT EXISTS analysis.mcl_factor_ref (")
    a("  letter mcl_factor PRIMARY KEY,")
    a("  name TEXT NOT NULL,")
    a("  description TEXT NOT NULL   -- MCL 722.23 statutory language")
    a(");")
    a("")
    a("CREATE TABLE IF NOT EXISTS analysis.analysis_module (")
    a("  id TEXT PRIMARY KEY,        -- stable module id, e.g. 'gaslighting'")
    a("  name TEXT NOT NULL,")
    a("  description TEXT NOT NULL,")
    a("  polarity TEXT NOT NULL CHECK (polarity IN ('negative','positive','neutral')),")
    a("  subcategory TEXT NOT NULL,")
    a("  weight INT NOT NULL CHECK (weight BETWEEN 0 AND 100),")
    a("  enabled BOOLEAN NOT NULL DEFAULT TRUE,")
    a("  mcl_factors mcl_factor[] NOT NULL DEFAULT '{}',")
    a("  needs_review BOOLEAN NOT NULL DEFAULT FALSE,  -- owner triage pending")
    a("  provenance TEXT NOT NULL DEFAULT ''")
    a(");")
    a("")
    a("CREATE TABLE IF NOT EXISTS analysis.pattern_phrase (")
    a("  id UUID PRIMARY KEY DEFAULT uuidv7(),")
    a("  module_id TEXT NOT NULL REFERENCES analysis.analysis_module(id) ON DELETE CASCADE,")
    a("  phrase TEXT NOT NULL,")
    a("  kind TEXT NOT NULL DEFAULT 'literal' CHECK (kind IN ('literal','regex')),")
    a("  UNIQUE (module_id, phrase)")
    a(");")
    a("CREATE INDEX IF NOT EXISTS pattern_phrase_module_idx ON analysis.pattern_phrase (module_id);")
    a("")
    a("CREATE TABLE IF NOT EXISTS analysis.contradiction_rule (")
    a("  id TEXT PRIMARY KEY,")
    a("  positive_module TEXT NOT NULL REFERENCES analysis.analysis_module(id),")
    a("  negative_modules TEXT[] NOT NULL DEFAULT '{}',")
    a("  description TEXT NOT NULL,")
    a("  provenance TEXT NOT NULL DEFAULT ''")
    a(");")
    a("")

    a("-- ---- MCL 722.23 factor reference ----")
    for f in seed.mcl_factors:
        a(
            f"INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES "
            f"({_q(f.letter)}, {_q(f.name)}, {_q(f.description)}) "
            f"ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;"
        )
    a("")

    a("-- ---- Analysis modules ----")
    for m in seed.modules:
        factors = (
            "ARRAY[" + ", ".join(f"{_q(x)}::mcl_factor" for x in m.mcl_factors) + "]"
            if m.mcl_factors
            else "'{}'::mcl_factor[]"
        )
        a(
            "INSERT INTO analysis.analysis_module "
            "(id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES "
            f"({_q(m.id)}, {_q(m.name)}, {_q(m.description)}, {_q(m.polarity)}, {_q(m.subcategory)}, "
            f"{m.weight}, {factors}, {str(m.needs_review).upper()}, {_q(m.provenance)}) "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, "
            "polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, "
            "mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, "
            "provenance = EXCLUDED.provenance;"
        )
    a("")

    a("-- ---- Indicator phrases ----")
    for m in seed.modules:
        for p in m.phrases:
            a(
                "INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES "
                f"({_q(m.id)}, {_q(p)}) ON CONFLICT (module_id, phrase) DO NOTHING;"
            )
    a("")

    a("-- ---- Contradiction rules ----")
    for r in seed.contradiction_rules:
        a(
            "INSERT INTO analysis.contradiction_rule (id, positive_module, negative_modules, description, provenance) "
            f"VALUES ({_q(r.id)}, {_q(r.positive_module)}, {_arr(r.negative_modules)}, "
            f"{_q(r.description)}, {_q(r.provenance)}) "
            "ON CONFLICT (id) DO UPDATE SET positive_module = EXCLUDED.positive_module, "
            "negative_modules = EXCLUDED.negative_modules, description = EXCLUDED.description, "
            "provenance = EXCLUDED.provenance;"
        )
    a("")
    return "\n".join(lines)


def main() -> None:
    seed = load_seed()
    MIGRATION_PATH.write_text(emit_seed_sql(seed), encoding="utf-8")
    print(
        f"wrote {MIGRATION_PATH.name}: {len(seed.modules)} modules, "
        f"{sum(len(m.phrases) for m in seed.modules)} phrases, "
        f"{len(seed.mcl_factors)} factors, {len(seed.contradiction_rules)} rules"
    )


if __name__ == "__main__":
    main()
