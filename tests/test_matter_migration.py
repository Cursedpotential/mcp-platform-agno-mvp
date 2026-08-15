"""Static contract tests for held migration 0030.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import sqlparse

from scripts._matter_validate_0030 import (
    strip_transaction_control,
    validate_promotion_contract,
    validate_static,
    validate_target,
)
from scripts._matter_validate_repository import run_repository_validation

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "sql" / "0030_matter_case_foundation.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
NORMALIZED = re.sub(r"\s+", " ", SQL.lower())


def test_static_validator_accepts_migration() -> None:
    assert validate_static(SQL) == []


def test_migration_is_held_transactional_and_parseable() -> None:
    assert "held for owner" in NORMALIZED
    assert "not applied to any database" in NORMALIZED
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"


def test_partition_bridge_preserves_primary_text_scope() -> None:
    assert "create table analysis.matter_knowledge_partition" in NORMALIZED
    assert "partition_key text primary key" in NORMALIZED
    assert "select 'primary', matter_id, id, 'migration-0030'" in NORMALIZED
    assert "on conflict (partition_key) do nothing" in NORMALIZED


def test_evidence_scope_is_additive_and_legacy_case_id_is_untouched() -> None:
    assert "add column matter_id uuid" in NORMALIZED
    assert "add column court_case_id uuid" in NORMALIZED
    assert "check ((matter_id is null) = (court_case_id is null))" in NORMALIZED
    forbidden = (
        r"drop\s+column\s+case_id",
        r"alter\s+column\s+case_id\s+type",
        r"rename\s+column\s+case_id",
    )
    assert not any(re.search(pattern, NORMALIZED) for pattern in forbidden)


def test_promotion_ledger_is_scoped_idempotent_and_append_only() -> None:
    assert "create table analysis.knowledge_evidence_promotion" in NORMALIZED
    assert "unique (matter_id, idempotency_key)" in NORMALIZED
    assert "unique (court_case_id, source_pointer_hash)" in NORMALIZED
    assert "foreign key (partition_key, matter_id)" in NORMALIZED
    assert "foreign key (evidence_item_id, matter_id, court_case_id)" in NORMALIZED
    assert "before update or delete on analysis.knowledge_evidence_promotion" in NORMALIZED
    assert "execute function working.forbid_mutation()" in NORMALIZED
    assert "check (knowledge_lane = 'evidence')" in NORMALIZED
    assert "analysis.knowledge_evidence_pointer_hash" in NORMALIZED


def test_promotion_guard_requires_default_unsafe_custody_bound_evidence() -> None:
    assert "create trigger knowledge_evidence_promotion_guard" in NORMALIZED
    assert "item.review_status <> 'unreviewed'::ai.review_state" in NORMALIZED
    assert "item.hitl_required is not true" in NORMALIZED
    assert "item.safe_for_legal_use is not false" in NORMALIZED
    assert "item.is_authenticated is not false" in NORMALIZED
    assert "record_row.case_id is distinct from new.partition_key" in NORMALIZED
    assert "record_row.artifact_id is distinct from new.evidence_hash_id" in NORMALIZED
    assert "record_row.provenance_id is distinct from new.source_run_id" in NORMALIZED
    assert "new.source_pointer_hash is distinct from" in NORMALIZED
    assert "source pointer fields do not match promotion ledger" in NORMALIZED
    assert "hash_algo <> 'sha256'" in NORMALIZED
    assert "hash_canon <> 'h1-rawbytes-v1'" in NORMALIZED


def test_production_database_validation_is_refused() -> None:
    with pytest.raises(ValueError, match="production is forbidden"):
        validate_target("production")


def test_database_validator_exercises_promotion_safety_and_rollback_contract() -> None:
    source = Path(validate_promotion_contract.__code__.co_filename).read_text(encoding="utf-8")
    assert "unreviewed" in source
    assert "hitl_required" in source
    assert "safe_for_legal_use" in source
    assert "is_authenticated" in source
    assert "knowledge_evidence_promotion_request_key" in source
    assert "knowledge_evidence_promotion_pointer_key" in source
    assert "knowledge_evidence_promotion_partition_fkey" in source
    assert "append-only" in source
    assert "custody hash source/file provenance does not match promotion" in source


def test_repository_harness_uses_real_repository_audit_and_outer_rollback() -> None:
    source = Path(run_repository_validation.__code__.co_filename).read_text(encoding="utf-8")
    fixture = (ROOT / "tests" / "fixtures" / "matter_0030_prerequisites.sql").read_text(encoding="utf-8")
    assert "repository.resolve_source" in source
    assert source.count("repository.promote_evidence") == 2
    assert "ops.audit_ledger" in source
    assert "outer.rollback()" in source
    assert "Byline: Codex · GPT-5" in fixture
    assert "CREATE TABLE ops.audit_ledger" in fixture


def test_transaction_stripping_preserves_plpgsql_begin_block() -> None:
    stripped = strip_transaction_control(SQL)
    assert not re.search(r"^\s*commit\s*;\s*$", stripped, re.IGNORECASE | re.MULTILINE)
    assert "BEGIN\n    NEW.updated_at := now();" in stripped


def test_migration_does_not_reference_generated_baseline() -> None:
    assert "sql/bootstrap/schema_baseline.sql" not in NORMALIZED
