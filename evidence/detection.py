"""
evidence/detection.py — behavioral DETECTION RUNNER.

Scans every ``analysis.normalized_record`` against the seeded behavioral
ontology (``analysis.detection_pattern`` + ``analysis.behavior_category``,
migration 0006: 512 patterns / 153 categories / 51 lexicon terms) and writes
one ``analysis.pattern_finding`` per (record × pattern-match), so downstream
review/scoring can work off structured hits instead of raw text.

COURT-SAFETY IS BAKED IN (non-negotiable — see migration 0006 / ADR ~0035):
  * SYMMETRIC APPLICATION. The scan runs over *all* normalized_record rows with
    no party filter. We never look for "the other side's" conduct only; the same
    ruleset hits both parties' messages identically. This is the single most
    important debiasing guarantee (Kubicki v. Sharpe caveat).
  * Every finding is a HYPOTHESIS, not a conclusion. Rows are written with
        bias_caution           = true   (carried from the pattern)
        requires_human_review  = true
        is_verified            = false
        review_status          = 'unreviewed'
        safe_for_legal_use     = false   (the legal-gate CHECK stays closed)
        data_tier              = 'inferred'
    A human must promote a finding before it can ever be safe_for_legal_use.
  * author_party is left NULL until entity-resolution is wired. The DB's
    attribution_gate CHECK only *requires* author_party once safe_for_legal_use
    flips true, so leaving it NULL here is correct and keeps the gate honest.

The runner is:
  * deterministic  — literal + regex matching only (no model calls, $0, local).
  * idempotent     — a NOT EXISTS guard on
                     (subject_id, category_id, detection_method, start/end, matched_text)
                     means re-running never double-writes (pre-empts the dedup
                     unique index TODO in 0005 §pattern_finding).
  * dry-run-first  — run(dry_run=True) wraps the whole pass in one transaction
                     and ROLLS BACK, reporting exactly what *would* be written.

This module reads analysis.normalized_record and writes analysis.pattern_finding
(+ one analysis.processing_run provenance row). It is PIPELINE-owned evidence/*
machinery; the live write is HITL/APPROVALS-gated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Optional

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
CONTEXT_CHARS = 60  # chars of context captured either side of a match
MAX_HITS_PER_PATTERN = 25  # cap matches per (record, pattern) to bound blow-ups
FETCH_BATCH = 500  # normalized_record rows pulled per server-side page

# pattern_finding.subject_type CHECK set (migration 0005). Map record_type onto it.
_SUBJECT_TYPES = frozenset({"message", "ocr_text", "transcript", "event"})
_RECORD_TYPE_TO_SUBJECT = {
    "message": "message",
    "sms": "message",
    "mms": "message",
    "chat": "message",
    "call": "event",
    "call_log": "event",
    "ocr": "ocr_text",
    "ocr_text": "ocr_text",
    "transcript": "transcript",
    "document": "ocr_text",
    "event": "event",
}


# ---------------------------------------------------------------------------
# Pattern model (mirrors analysis.detection_pattern ⋈ behavior_category)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Pattern:
    id: Optional[str]  # detection_pattern.id (uuid) — None in offline tests
    pattern_set_id: Optional[str]
    category_id: str  # behavior_category.category_id (citext)
    subcategory: Optional[str]
    match_type: str  # 'literal' | 'regex'
    pattern: str  # literal phrase OR regex source
    keywords: tuple[str, ...] = ()
    severity: Optional[int] = None
    score: Optional[int] = None
    bias_caution: bool = True
    authored_perspective: Optional[str] = None
    source: Optional[str] = None
    _rx: Any = field(default=None, compare=False, repr=False)

    def compiled(self):
        """Compiled, case-insensitive regex for match_type='regex' (or None)."""
        if self.match_type != "regex":
            return None
        if self._rx is not None:
            return self._rx
        try:
            rx: Any = re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)
        except re.error:
            rx = False  # sentinel: unusable pattern, skip cleanly
        object.__setattr__(self, "_rx", rx)
        return rx


@dataclass
class Match:
    pattern: Pattern
    matched_text: str
    matched_pattern: str
    start_char: int
    end_char: int
    context_before: str
    context_after: str
    detection_method: str  # 'literal' | 'regex'


@dataclass
class RunStats:
    records_scanned: int = 0
    records_with_findings: int = 0
    patterns_loaded: int = 0
    findings_generated: int = 0
    findings_written: int = 0  # after idempotency guard (0 on dry-run)
    by_category: dict[str, int] = field(default_factory=dict)
    by_method: dict[str, int] = field(default_factory=dict)
    dry_run: bool = True

    def bump(self, category_id: str, method: str) -> None:
        self.findings_generated += 1
        self.by_category[category_id] = self.by_category.get(category_id, 0) + 1
        self.by_method[method] = self.by_method.get(method, 0) + 1


# ---------------------------------------------------------------------------
# Core scan (pure — no DB, unit-testable offline)
# ---------------------------------------------------------------------------
def _iter_literal_spans(haystack_lc: str, needle: str) -> Iterator[tuple[int, int]]:
    if not needle:
        return
    needle_lc = needle.lower()
    start = 0
    hits = 0
    while hits < MAX_HITS_PER_PATTERN:
        idx = haystack_lc.find(needle_lc, start)
        if idx == -1:
            return
        yield idx, idx + len(needle_lc)
        start = idx + len(needle_lc)
        hits += 1


def scan_record(content: Optional[str], patterns: Iterable[Pattern]) -> list[Match]:
    """Return every pattern hit in one record's content. Pure function."""
    if not content:
        return []
    content_lc = content.lower()
    out: list[Match] = []
    for p in patterns:
        spans: list[tuple[int, int]] = []
        method = p.match_type
        if p.match_type == "regex":
            rx = p.compiled()
            if not rx:  # None or unusable
                continue
            for m in rx.finditer(content):
                spans.append((m.start(), m.end()))
                if len(spans) >= MAX_HITS_PER_PATTERN:
                    break
        else:  # literal: the phrase itself + any keyword aliases
            method = "literal"
            seen: set[tuple[int, int]] = set()
            for needle in (p.pattern, *p.keywords):
                for span in _iter_literal_spans(content_lc, needle):
                    if span not in seen:
                        seen.add(span)
                        spans.append(span)
        for s, e in spans:
            out.append(
                Match(
                    pattern=p,
                    matched_text=content[s:e],
                    matched_pattern=p.pattern,
                    start_char=s,
                    end_char=e,
                    context_before=content[max(0, s - CONTEXT_CHARS) : s],
                    context_after=content[e : e + CONTEXT_CHARS],
                    detection_method=method,
                )
            )
    return out


def subject_type_for(record_type: Optional[str]) -> str:
    key = (record_type or "").lower()
    return _RECORD_TYPE_TO_SUBJECT.get(key, "message")


# ---------------------------------------------------------------------------
# DB orchestration (SQLAlchemy engine, same convention as store.py / custody.py)
# ---------------------------------------------------------------------------
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        from db.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


_LOAD_PATTERNS_SQL = """
SELECT dp.id, dp.pattern_set_id, dp.category_id, dp.subcategory,
       dp.match_type::text AS match_type, dp.pattern, dp.keywords,
       dp.severity, dp.score, dp.bias_caution, dp.authored_perspective, dp.source
FROM analysis.detection_pattern dp
JOIN analysis.detection_pattern_set ps ON ps.id = dp.pattern_set_id
WHERE dp.is_active AND ps.is_active
"""

_INSERT_FINDING_SQL = """
INSERT INTO analysis.pattern_finding
    (subject_type, subject_id, category_id, pattern_id, pattern_set_id, subcategory,
     detection_method, rule_name, matched_text, matched_pattern,
     start_char, end_char, context_before, context_after,
     author_party, bias_caution, authored_perspective, severity, score,
     requires_human_review, is_verified, review_status, safe_for_legal_use,
     data_tier, provenance_id)
SELECT :subject_type, :subject_id, :category_id, :pattern_id, :pattern_set_id, :subcategory,
       CAST(:detection_method AS detection_method), :rule_name, :matched_text, :matched_pattern,
       :start_char, :end_char, :context_before, :context_after,
       CAST(:author_party AS conduct_party), :bias_caution, :authored_perspective, :severity, :score,
       true, false, CAST('unreviewed' AS review_state), false,
       CAST('inferred' AS evidence_tier), :provenance_id
WHERE NOT EXISTS (
    SELECT 1 FROM analysis.pattern_finding f
    WHERE f.subject_id = :subject_id
      AND f.category_id = :category_id
      AND f.detection_method = CAST(:detection_method AS detection_method)
      AND coalesce(f.start_char, -1) = coalesce(:start_char, -1)
      AND coalesce(f.end_char,   -1) = coalesce(:end_char,   -1)
      AND coalesce(f.matched_text, '') = coalesce(:matched_text, '')
)
"""


def load_patterns(conn) -> list[Pattern]:
    from sqlalchemy import text

    rows = conn.execute(text(_LOAD_PATTERNS_SQL)).mappings().all()
    pats: list[Pattern] = []
    for r in rows:
        pats.append(
            Pattern(
                id=str(r["id"]),
                pattern_set_id=str(r["pattern_set_id"]),
                category_id=r["category_id"],
                subcategory=r["subcategory"],
                match_type=r["match_type"],
                pattern=r["pattern"],
                keywords=tuple(r["keywords"] or ()),
                severity=r["severity"],
                score=r["score"],
                bias_caution=bool(r["bias_caution"]),
                authored_perspective=r["authored_perspective"],
                source=r["source"],
            )
        )
    return pats


def _finding_params(rec: dict, m: Match, provenance_id: Optional[str]) -> dict:
    return {
        "subject_type": subject_type_for(rec.get("record_type")),
        "subject_id": rec["id"],
        "category_id": m.pattern.category_id,
        "pattern_id": m.pattern.id,
        "pattern_set_id": m.pattern.pattern_set_id,
        "subcategory": m.pattern.subcategory,
        "detection_method": m.detection_method,
        "rule_name": m.pattern.source,
        "matched_text": m.matched_text[:2000],
        "matched_pattern": m.matched_pattern[:2000],
        "start_char": m.start_char,
        "end_char": m.end_char,
        "context_before": m.context_before,
        "context_after": m.context_after,
        # Left NULL by design until entity-resolution attributes a party;
        # the attribution_gate CHECK only bites when safe_for_legal_use=true.
        "author_party": None,
        "bias_caution": m.pattern.bias_caution,
        "authored_perspective": m.pattern.authored_perspective,
        "severity": m.pattern.severity,
        "score": m.pattern.score,
        "provenance_id": provenance_id,
    }


def run(dry_run: bool = True, limit: Optional[int] = None, actor: str = "evidence.detection.run") -> RunStats:
    """Scan normalized_record → pattern_finding.

    dry_run=True (default): the ENTIRE pass runs inside one transaction that is
    ROLLED BACK — nothing durable is written; RunStats reports what *would* land.
    dry_run=False: commits (HITL/APPROVALS-gated; do not call unattended).
    """
    from sqlalchemy import text

    engine = _get_engine()
    stats = RunStats(dry_run=dry_run)

    with engine.begin() as conn:  # one transaction for the whole pass
        patterns = load_patterns(conn)
        stats.patterns_loaded = len(patterns)

        # Provenance: one processing_run for this detection pass.
        prov = conn.execute(
            text(
                "INSERT INTO analysis.processing_run "
                "(run_type, run_purpose, status, actor, tool_or_model, "
                " ran_local_only, cloud_exposure, human_review_requirement, "
                " replayable, started_at) "
                "VALUES ('pattern_analysis', :purpose, 'running', :actor, "
                " 'evidence.detection (literal+regex)', true, false, true, true, now()) "
                "RETURNING run_id"
            ),
            {"purpose": "behavioral detection over normalized_record", "actor": actor},
        ).scalar()

        q = "SELECT id, record_type, content FROM analysis.normalized_record WHERE content IS NOT NULL ORDER BY id"
        if limit is not None:
            q += f" LIMIT {int(limit)}"

        result = conn.execution_options(stream_results=True).execute(text(q))
        while True:
            batch = result.mappings().fetchmany(FETCH_BATCH)
            if not batch:
                break
            for rec in batch:
                stats.records_scanned += 1
                matches = scan_record(rec["content"], patterns)
                if not matches:
                    continue
                stats.records_with_findings += 1
                for m in matches:
                    stats.bump(m.pattern.category_id, m.detection_method)
                    res = conn.execute(text(_INSERT_FINDING_SQL), _finding_params(rec, m, prov))
                    stats.findings_written += res.rowcount or 0

        conn.execute(
            text(
                "UPDATE analysis.processing_run SET status = :st, finished_at = now(), "
                "counts_processed = :n, summary = :sm WHERE run_id = :rid"
            ),
            {
                "st": "ok",
                "n": stats.records_scanned,
                "sm": f"{stats.findings_generated} findings from {stats.patterns_loaded} patterns",
                "rid": prov,
            },
        )

        if dry_run:
            # Roll the whole pass back — nothing durable written.
            conn.get_transaction().rollback()
            stats.findings_written = 0

    return stats


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description="behavioral detection runner")
    ap.add_argument("--commit", action="store_true", help="COMMIT findings (gated; default is dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="cap normalized_record rows scanned")
    args = ap.parse_args()
    s = run(dry_run=not args.commit, limit=args.limit)
    print(s)
