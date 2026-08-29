"""Structural contract for the UIW source-version matter/case binding.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0043_context_source_matter_binding.sql"


def test_0043_is_transactional_platform_guarded_and_composite_scoped() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "begin;" in sql and "commit;" in sql
    assert "current_database() <> 'platform'" in sql
    assert "context.source_version" in sql
    assert "add column if not exists matter_id uuid" in sql
    assert "add column if not exists court_case_id uuid" in sql
    assert "check ((matter_id is null) = (court_case_id is null))" in sql
    assert "foreign key (court_case_id, matter_id)" in sql
    assert "references analysis.court_case(id, matter_id)" in sql
    assert "on delete restrict" in sql


def test_0043_has_no_destructive_data_operations() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for forbidden in ("drop table", "delete from", "truncate", "create role", "alter role"):
        assert forbidden not in sql
