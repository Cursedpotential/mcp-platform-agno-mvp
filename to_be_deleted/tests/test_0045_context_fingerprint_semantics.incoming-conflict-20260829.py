"""Contracts for the guarded 0045 supersession slot.

The abandoned implementation is preserved under ``to_be_deleted/sql``. 0045
must now be an explicit, non-mutating bridge from the real 0036 foundation to
the fix-forward implementation in 0048.
"""

from __future__ import annotations

from pathlib import Path

import sqlparse


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0045_context_fingerprint_semantics.sql"
PRESERVED = (
    ROOT
    / "to_be_deleted"
    / "sql"
    / "0045_context_fingerprint_semantics.broken-historical-20260829.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
NORMALIZED = " ".join(SQL.lower().split())


def test_0045_is_an_explicit_transactional_supersession() -> None:
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    assert "migration 0048 is the governed fix-forward" in NORMALIZED
    assert "current_database() <> 'platform'" in NORMALIZED
    for statement in statements:
        assert sqlparse.parse(statement), statement[:120]


def test_0045_guards_the_real_0036_shape_and_partial_draft_state() -> None:
    for relation in (
        "context.hash_receipt",
        "context.raw_generation",
        "context.activity_execution",
    ):
        assert f"to_regclass('{relation}')" in NORMALIZED
    for column in (
        "hash_kind",
        "construction",
        "computed_by",
        "source_version_id",
        "raw_record_id",
        "raw_generation_id",
    ):
        assert f"'{column}'" in NORMALIZED
    for abandoned in (
        "context.hash_kind",
        "context.hash_canon",
        "context.receipt_kind",
        "context.custody_chain",
    ):
        assert f"to_regclass('{abandoned}') is not null" in NORMALIZED


def test_0045_live_slot_is_non_mutating() -> None:
    executable = "\n".join(
        line for line in SQL.splitlines() if not line.lstrip().startswith("--")
    ).lower()
    for mutation in (
        "create table",
        "alter table",
        "drop table",
        "insert into",
        "update ",
        "delete from",
        "truncate ",
    ):
        assert mutation not in executable


def test_abandoned_0045_source_is_preserved_outside_live_migration_chain() -> None:
    assert PRESERVED.is_file()
    historical = PRESERVED.read_text(encoding="utf-8")
    assert "INSERT INTO context.hash_kind" in historical
    assert "INSERT INTO context.hash_canon" in historical
    assert "INSERT INTO context.receipt_kind" in historical
    assert "context.custody_chain" in historical
