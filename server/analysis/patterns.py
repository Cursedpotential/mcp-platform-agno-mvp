"""evidence/patterns.py — behavioral-ontology chain: parser, validator, cross-check.

The ontology's single source of truth is the LIVE analysis schema, reproduced
in git by the migration chain under
docs/planning/forensic-db-reconciliation/migrations/:

    0006_behavior_seed.sql          base seed (G1-G9 union; applied 2026-06-30)
    0007_behavior_seed_sweep.sql    sweep-2026-07-03 delta (applied live, captured 2026-07-04)
    0008_*                          pattern-analyzer.ts corpus delta (committed, NOT yet applied)

This module parses that chain offline (no DB), validates its invariants, and
cross-checks it against the archived P2.1 corpus
(evidence/config/behavioral_patterns.json — the verbatim pattern-analyzer.ts
extraction + contradiction rules). The live smoke derives its expected counts
from `chain_prefix_counts()`, so "live == some prefix of the committed chain"
is the invariant that detects both data loss and uncaptured drift.

The corpus JSON's contradiction_rules remain UNHOMED — the live schema has no
contradiction table yet; that is a pending owner decision, tracked here.

History: this module previously generated sql/0005_behavioral_patterns.sql
(parallel tables superseded by the richer live 0005/0006 chain — see
docs/planning/port-backlog.md and the PR #8/#9 reconciliation).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).parent.parent.parent
MIGRATIONS_DIR = _REPO / "docs" / "planning" / "forensic-db-reconciliation" / "migrations"
CORPUS_PATH = Path(__file__).parent / "config" / "behavioral_patterns.json"

# chain files that carry ontology DATA, in apply order (0005 is schema-only)
CHAIN_GLOB = "000[6-9]_*.sql"

POLARITIES = {"negative", "positive", "neutral", "linguistic_marker"}
MCL_LETTERS = set("abcdefghijkl")
MATCH_TYPES = {"literal", "regex"}


@dataclass
class Category:
    category_id: str
    label: str
    polarity: str
    default_severity: int
    mcl_factors: str  # pg array literal, e.g. '{j,k}'
    source: str
    migration: str


@dataclass
class DetectionPattern:
    category_id: str
    match_type: str
    pattern: str
    severity: int
    source: str
    migration: str


@dataclass
class OntologyChain:
    files: list[str] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    patterns: list[DetectionPattern] = field(default_factory=list)

    def category_ids(self) -> set[str]:
        return {c.category_id for c in self.categories}

    def pattern_keys(self) -> set[tuple[str, str, str]]:
        return {(p.category_id, p.match_type, p.pattern.lower()) for p in self.patterns}


# ---------------------------------------------------------------------------
# SQL VALUES parsing (quote-aware: patterns contain commas/parens; '' escapes ')
# ---------------------------------------------------------------------------
def _split_rows(values_body: str) -> list[list[str]]:
    """Split a VALUES body into rows of raw field strings."""
    rows: list[list[str]] = []
    fields: list[str] = []
    buf: list[str] = []
    depth = 0
    in_str = False
    i = 0
    s = values_body
    while i < len(s):
        ch = s[i]
        if in_str:
            if ch == "'":
                if i + 1 < len(s) and s[i + 1] == "'":  # escaped quote
                    buf.append("''")
                    i += 2
                    continue
                in_str = False
            buf.append(ch)
        elif ch == "'":
            in_str = True
            buf.append(ch)
        elif ch == "(":
            depth += 1
            if depth == 1:  # row opens — start fresh
                fields, buf = [], []
            else:
                buf.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:  # row closes
                fields.append("".join(buf).strip())
                rows.append(fields)
                fields, buf = [], []
            else:
                buf.append(ch)
        elif ch == "," and depth == 1:
            fields.append("".join(buf).strip())
            buf = []
        elif depth >= 1:
            buf.append(ch)
        i += 1
    return rows


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


# Either schema. The ontology seed migrations were written before 0014 moved these
# taxonomy tables from `analysis` to `reference`, and an applied migration is never
# edited — so the historical files legitimately say `analysis.` forever while
# anything new says `registry.`. Matching both is the only correct behaviour here.
_BLOCK_RE = re.compile(
    r"INSERT INTO (?:analysis|reference)\."
    r"(?P<table>behavior_category|detection_pattern)\b.*?"
    r"\(VALUES(?P<body>.*?)\)\s*AS v\((?P<cols>[^)]*)\)",
    re.DOTALL | re.IGNORECASE,
)


def parse_migration(path: Path) -> tuple[list[Category], list[DetectionPattern]]:
    """Extract category/pattern rows from one chain migration file."""
    sql = path.read_text(encoding="utf-8")
    cats: list[Category] = []
    pats: list[DetectionPattern] = []
    for m in _BLOCK_RE.finditer(sql):
        cols = [c.strip() for c in m.group("cols").split(",")]
        for row in _split_rows(m.group("body")):
            if len(row) != len(cols):
                raise ValueError(f"{path.name}: row width {len(row)} != cols {len(cols)}: {row[:3]}...")
            d = dict(zip(cols, row))
            if m.group("table").lower() == "behavior_category":
                cats.append(
                    Category(
                        category_id=_unquote(d["category_id"]),
                        label=_unquote(d["label"]),
                        polarity=_unquote(d["polarity"]),
                        default_severity=int(d["default_severity"]),
                        mcl_factors=_unquote(d["mcl_factors"]),
                        source=_unquote(d["source"]),
                        migration=path.name,
                    )
                )
            else:
                # 0006's hand-written blocks vary: match_type/severity/source may
                # be SQL constants in the SELECT instead of VALUES columns.
                pats.append(
                    DetectionPattern(
                        category_id=_unquote(d["category_id"]),
                        match_type=_unquote(d.get("match_type", "'literal'")),
                        pattern=_unquote(d["pattern"]),
                        severity=int(d["severity"]) if "severity" in d else 0,
                        source=_unquote(d.get("source", "''")),
                        migration=path.name,
                    )
                )
    return cats, pats


def load_chain(migrations_dir: Path = MIGRATIONS_DIR) -> OntologyChain:
    chain = OntologyChain()
    for path in sorted(migrations_dir.glob(CHAIN_GLOB)):
        cats, pats = parse_migration(path)
        chain.files.append(path.name)
        chain.categories.extend(cats)
        chain.patterns.extend(pats)
    return chain


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_chain(chain: OntologyChain) -> list[str]:
    """Invariant violations (empty list = healthy)."""
    errs: list[str] = []
    seen: dict[str, str] = {}
    for c in chain.categories:
        if c.category_id in seen:
            errs.append(f"duplicate category {c.category_id!r} ({seen[c.category_id]} + {c.migration})")
        seen[c.category_id] = c.migration
        if c.polarity not in POLARITIES:
            errs.append(f"{c.category_id}: invalid polarity {c.polarity!r}")
        if not 0 <= c.default_severity <= 10:
            errs.append(f"{c.category_id}: severity {c.default_severity} out of 0-10")
        letters = set(c.mcl_factors.strip("{}").split(",")) - {""}
        if not letters <= MCL_LETTERS:
            errs.append(f"{c.category_id}: invalid MCL letters {sorted(letters - MCL_LETTERS)}")
    ids = chain.category_ids()
    for p in chain.patterns:
        if p.category_id not in ids:
            errs.append(f"pattern {p.pattern[:40]!r} references unknown category {p.category_id!r}")
        if p.match_type not in MATCH_TYPES:
            errs.append(f"{p.category_id}: invalid match_type {p.match_type!r}")
        if not 0 <= p.severity <= 10:
            errs.append(f"{p.category_id}: pattern severity {p.severity} out of 0-10")
        if p.match_type == "regex":
            try:
                re.compile(p.pattern)
            except re.error as exc:
                errs.append(f"{p.category_id}: unusable regex {p.pattern[:40]!r} ({exc})")
    return errs


def chain_prefix_counts(chain: OntologyChain | None = None) -> list[dict]:
    """Cumulative DISTINCT (categories, patterns) after each chain file — the
    live smoke matches live counts against these prefixes to tell 'behind'
    from 'drifted'. Distinct keys mirror the migrations' ON CONFLICT upserts
    (a re-stated row never adds a second DB row)."""
    chain = chain or load_chain()
    out: list[dict] = []
    cat_ids: set[str] = set()
    pat_keys: set[tuple[str, str, str]] = set()
    for f in chain.files:
        cat_ids |= {c.category_id for c in chain.categories if c.migration == f}
        pat_keys |= {(p.category_id, p.match_type, p.pattern.lower()) for p in chain.patterns if p.migration == f}
        out.append({"through": f, "categories": len(cat_ids), "patterns": len(pat_keys)})
    return out


# ---------------------------------------------------------------------------
# Corpus cross-check (the archived P2.1 pattern-analyzer.ts extraction)
# ---------------------------------------------------------------------------
def load_corpus(path: Path = CORPUS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cross_check_corpus(chain: OntologyChain | None = None, corpus: dict | None = None) -> dict:
    """What the corpus has that the committed chain does not."""
    chain = chain or load_chain()
    corpus = corpus or load_corpus()
    ids = chain.category_ids()
    chain_phrases = {p.pattern.lower() for p in chain.patterns}

    missing_categories = [m["id"] for m in corpus["modules"] if m["id"] not in ids]
    missing_phrases: dict[str, list[str]] = {}
    for m in corpus["modules"]:
        miss = [p for p in m["phrases"] if p.lower() not in chain_phrases]
        if miss:
            missing_phrases[m["id"]] = miss
    return {
        "missing_categories": missing_categories,
        "missing_phrases": missing_phrases,
        "missing_phrase_count": sum(len(v) for v in missing_phrases.values()),
        "unhomed_contradiction_rules": [r["id"] for r in corpus.get("contradiction_rules", [])],
    }


if __name__ == "__main__":
    chain = load_chain()
    errs = validate_chain(chain)
    print(f"chain: {chain.files}")
    print(f"categories: {len(chain.categories)}, patterns: {len(chain.patterns)}")
    print(f"prefix counts: {chain_prefix_counts(chain)}")
    print(f"validation: {'OK' if not errs else errs}")
    report = cross_check_corpus(chain)
    print(
        f"corpus cross-check: {len(report['missing_categories'])} categories, "
        f"{report['missing_phrase_count']} phrases missing; "
        f"{len(report['unhomed_contradiction_rules'])} contradiction rules unhomed"
    )
