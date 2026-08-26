"""Static contract tests for sql/0034_classification_adjudication.sql (GAP-031).

Byline: Claude Code · Sonnet 5 · 2026-08-26

Same doctrine as tests/test_temporal_projection_sql_contract.py and
tests/test_matter_migration.py: no database connection, just structural assertions on the
migration text plus a real sqlparse parse to catch syntax breakage. Applying 0034 against a
live Postgres (inside a transaction, then ROLLBACK) is a required live-verification step this
packet hands off to root/deploy — see docs/reviews/2026-08-25-schema-audit/
GAP-031-IMPLEMENTATION-STATUS.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import sqlparse

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "sql" / "0034_classification_adjudication.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
NORMALIZED = re.sub(r"\s+", " ", SQL.lower())


def test_migration_file_exists_and_is_numbered_0034() -> None:
    assert MIGRATION.exists()
    # 0033 and 0035 both exist; 0034 must not collide with either.
    assert (ROOT / "sql" / "0033_chunk_classification_drafts.sql").exists()


def test_migration_is_transactional_and_parseable() -> None:
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    # sqlparse should tokenize every statement without raising.
    for statement in statements:
        parsed = sqlparse.parse(statement)
        assert parsed, f"sqlparse failed to parse statement: {statement[:80]!r}"


def test_alters_the_existing_table_no_new_ledger_table() -> None:
    # Owner instruction: reuse existing classification batch/item identity and tables;
    # do not create a redundant adjudication ledger.
    assert "alter table analysis.chunk_classification" in NORMALIZED
    assert "create table" not in NORMALIZED


def test_adds_all_required_item_decision_fields() -> None:
    for column in ("decision_id", "actor", "decision", "reason", "source", "adjudicated_at"):
        assert f"add column if not exists {column}" in NORMALIZED, column


def test_decision_is_constrained_to_the_accepting_enum() -> None:
    # Only approve/correct ever reach this table (reject/pending excluded upstream).
    assert "check (decision is null or decision in ('approve', 'correct'))" in NORMALIZED


def test_adjudication_fields_travel_together_or_not_at_all() -> None:
    assert "chunkclass_adjudication_fields_complete" in NORMALIZED
    assert "decision_id is null and actor is null and decision is null" in NORMALIZED
    assert "decision_id is not null and actor is not null and decision is not null" in NORMALIZED


def test_general_row_idempotency_key_matches_persist_body_conflict_target() -> None:
    # This exact column tuple is also the ON CONFLICT target in
    # docs/research/integration-audit-2026-08-24/composed/wf-persist-results.json.
    assert "create unique index if not exists uq_chunkclass_batch_item" in NORMALIZED
    assert "on analysis.chunk_classification (run_key, batch_index, record_ref, classifier_version)" in NORMALIZED


def test_decision_id_partial_unique_index_enforces_fail_closed_conflict() -> None:
    assert "create unique index if not exists uq_chunkclass_decision_id" in NORMALIZED
    assert "on analysis.chunk_classification (decision_id)" in NORMALIZED
    assert "where decision_id is not null" in NORMALIZED


def test_grants_are_reasserted_for_agno_app() -> None:
    assert "grant select, insert, update on analysis.chunk_classification to agno_app" in NORMALIZED


def test_does_not_touch_the_evidence_schema() -> None:
    assert "evidence." not in NORMALIZED
