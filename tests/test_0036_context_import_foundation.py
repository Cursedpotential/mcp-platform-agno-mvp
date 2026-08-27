"""Static invariant coverage for migration 0036; no database or container required."""

from __future__ import annotations

import re
from pathlib import Path

import sqlparse


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "sql" / "0036_context_import_foundation.sql"
APPLY_SCRIPT = ROOT / "scripts" / "apply_0036_live.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_0036_live.py"
SQL = MIGRATION.read_text(encoding="utf-8")
NORMALIZED = re.sub(r"\s+", " ", SQL.lower())

EXPECTED_CONTEXT_TABLES = {
    "activity_execution",
    "activity_receipt",
    "hash_batch",
    "hash_batch_member",
    "hash_manifest",
    "hash_manifest_member",
    "hash_receipt",
    "normalization_lineage",
    "normalized_generation",
    "normalized_generation_publication",
    "normalized_record_identity",
    "raw_format_registry",
    "raw_generation",
    "raw_record_identity",
    "reconciliation_receipt",
    "retained_object",
    "source",
    "source_metadata",
    "source_version",
    "source_version_object",
}


def _fresh_sql() -> tuple[str, str]:
    """Read the migration at assertion time so concurrent migration edits are visible."""
    sql = MIGRATION.read_text(encoding="utf-8")
    return sql, re.sub(r"\s+", " ", sql.lower())


def test_migration_is_context_only_transactional_additive_ddl() -> None:
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    assert "apply/status is recorded by the production migration ledger" in NORMALIZED
    assert "create schema if not exists context" in NORMALIZED
    assert "references evidence." not in NORMALIZED
    assert "working.normalized_record" not in NORMALIZED
    assert "drop table" not in NORMALIZED


def test_migration_is_platform_only_and_authors_objects_as_context_owner() -> None:
    assert "current_database() <> 'platform'" in NORMALIZED
    assert "set local role platform_admin" in NORMALIZED
    assert "set local role context_owner" in NORMALIZED
    assert "create schema if not exists context authorization context_owner" in NORMALIZED
    assert "context schema exists with an unexpected owner" in NORMALIZED
    assert "reset role" in NORMALIZED
    assert "security definer" in NORMALIZED
    assert "set search_path = pg_catalog, context" in NORMALIZED


def test_context_acl_is_least_privilege_and_covers_future_subtype_tables() -> None:
    assert "revoke all on schema context from public" in NORMALIZED
    assert "grant usage on schema context to context_import_writer, context_reader" in NORMALIZED
    assert "grant select, insert on all tables in schema context to context_import_writer" in NORMALIZED
    assert "revoke insert on context.raw_format_registry from context_import_writer" in NORMALIZED
    assert "grant select on all tables in schema context to context_reader" in NORMALIZED
    assert "grant update on context.source_version," in NORMALIZED
    assert "revoke execute on all functions in schema context from public" in NORMALIZED
    assert "grant execute on all functions in schema context to context_import_writer" in NORMALIZED
    assert "alter default privileges for role context_owner in schema context" in NORMALIZED
    assert "grant select, insert on tables to context_import_writer" in NORMALIZED
    assert "grant select on tables to context_reader" in NORMALIZED
    assert "grant execute on functions to context_import_writer" in NORMALIZED
    assert "grant create on schema context" not in NORMALIZED
    assert "grant delete" not in NORMALIZED


def test_runtime_roles_are_preflighted_without_elevated_attributes() -> None:
    for role in (
        "platform_admin",
        "platform_runtime",
        "context_owner",
        "context_import_writer",
        "context_reader",
    ):
        assert f"'{role}'" in NORMALIZED
    for attribute in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls"):
        assert attribute in NORMALIZED
    assert "pg_has_role('platform_admin', 'context_owner', 'member')" in NORMALIZED
    assert "pg_has_role('platform_runtime', 'context_import_writer', 'member')" in NORMALIZED


def test_apply_and_validator_require_platform_and_the_rich_ledger() -> None:
    for path in (APPLY_SCRIPT, VALIDATE_SCRIPT):
        source = path.read_text(encoding="utf-8")
        assert 'database != "platform"' in source
        assert "dbname={database}" in source
        assert "current_database()" in source
        assert "datname = 'ai'" in source
        for column in (
            "id",
            "version_label",
            "applies_to",
            "ddl_uri",
            "ddl_hash",
            "migration_id",
            "status",
            "notes",
            "created_by",
            "created_at",
        ):
            assert f'"{column}"' in source
        for elevated in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls"):
            assert elevated in source


def test_byte_coverage_not_applicable_is_auditable_but_cannot_seal() -> None:
    assert "not_applicable reconciliation is permitted only for byte_coverage" in NORMALIZED
    assert "new.observed->>'locator_based_records' is distinct from '0'" in NORMALIZED
    assert "raw.stored_bytes is null" in NORMALIZED
    assert "status <> 'not_applicable' or discrepancies = '[]'::jsonb" in NORMALIZED
    assert "not_applicable byte coverage requires exact stored bytes for every raw record" in NORMALIZED
    raw_seal = NORMALIZED.split("create function context.guard_raw_generation_transition", 1)[1].split(
        "create trigger raw_generation_seal_gate", 1
    )[0]
    assert "from (values ('record_accounting'), ('byte_coverage'), ('raw_source_verification'))" in raw_seal
    assert "and r.status = 'success'" in raw_seal
    assert "r.status in ('success', 'not_applicable')" not in raw_seal


def test_migration_declares_exactly_the_twenty_foundation_tables() -> None:
    sql, _ = _fresh_sql()
    declared = set(
        re.findall(
            r"(?im)^\s*create\s+table\s+if\s+not\s+exists\s+context\.([a-z0-9_]+)\s*\(",
            sql,
        )
    )
    assert len(EXPECTED_CONTEXT_TABLES) == 20
    assert declared == EXPECTED_CONTEXT_TABLES


def test_database_dependencies_are_explicitly_exercised_by_the_ddl() -> None:
    _, normalized = _fresh_sql()
    assert "default uuidv7()" in normalized
    assert "digest(inline_bytes, 'sha256')" in normalized
    assert "language plpgsql" in normalized


def test_critical_functions_and_triggers_are_present() -> None:
    sql, normalized = _fresh_sql()
    declared_functions = set(re.findall(r"(?im)^\s*create\s+function\s+context\.([a-z0-9_]+)\s*\(", sql))
    assert {
        "assert_hash_manifest_complete",
        "assert_normalized_generation_open",
        "assert_raw_generation_open",
        "assert_raw_subtype_completeness",
        "assert_source_version_retained",
        "forbid_mutation",
        "guard_activity_execution_insert",
        "guard_hash_batch_member_insert",
        "guard_hash_batch_transition",
        "guard_hash_manifest_member_insert",
        "guard_hash_manifest_transition",
        "guard_hash_receipt_insert",
        "guard_normalized_generation_transition",
        "guard_normalized_publication",
        "guard_raw_generation_transition",
        "guard_reconciliation_receipt_insert",
        "guard_source_metadata_insert",
        "guard_source_version_mutation",
        "guard_source_version_object_insert",
        "register_raw_format_subtype",
        "seal_hash_manifest_from_receipt",
    } <= declared_functions
    for trigger_name in (
        "activity_execution_retention_gate",
        "hash_batch_member_open_gate",
        "hash_batch_transition_gate",
        "hash_manifest_member_open_gate",
        "hash_manifest_seal_gate",
        "hash_receipt_insert_gate",
        "normalization_lineage_open_generation_gate",
        "normalized_generation_publication_receipt_gate",
        "normalized_generation_seal_publish_gate",
        "raw_generation_seal_gate",
        "raw_record_identity_open_generation_gate",
        "reconciliation_receipt_insert_gate",
        "source_metadata_open_generation_gate",
        "source_version_object_insert_gate",
    ):
        assert f"create trigger {trigger_name}" in normalized


def test_source_version_object_parent_is_same_source_and_parent_row_is_locked() -> None:
    sql, normalized = _fresh_sql()
    source_object_ddl = normalized.split("create table if not exists context.source_version_object", 1)[1].split(
        "create unique index", 1
    )[0]
    assert "foreign key (source_version_id, parent_object_id)" in source_object_ddl
    assert "references context.source_version_object(source_version_id, object_id)" in source_object_ddl

    guard_match = re.search(
        r"create\s+function\s+context\.guard_source_version_object_insert\s*\(\s*\).*?\$\$(.*?)\$\$\s*;",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert guard_match is not None
    guard_body = re.sub(r"\s+", " ", guard_match.group(1).lower())
    assert "from context.source_version" in guard_body
    assert "for update" in guard_body


def test_raw_and_normalized_storage_have_no_redaction_or_masking_semantics() -> None:
    """0036 preserves source content; only a later explicit export may redact."""
    sql, normalized = _fresh_sql()
    executable_sql = sqlparse.format(sql, strip_comments=True).lower()

    declared_columns = set(
        re.findall(
            r"(?im)^\s*([a-z][a-z0-9_]*)\s+"
            r"(?:bytea|jsonb|text|varchar|character\s+varying)\b",
            executable_sql,
        )
    )
    forbidden_storage_columns = {
        column
        for column in declared_columns
        if re.search(r"(?:^|_)(?:redact(?:ed|ion)?|mask(?:ed|ing)?|saniti[sz]ed|censored)(?:_|$)", column)
    }
    assert forbidden_storage_columns == set()
    assert not re.search(
        r"create\s+function\s+context\.[a-z0-9_]*(?:redact|mask|saniti[sz]e|censor)[a-z0-9_]*",
        executable_sql,
    )
    assert not re.search(
        r"(?:regexp_replace|replace|overlay)\s*\(\s*(?:[a-z0-9_]+\.)?"
        r"(?:stored_bytes|inline_bytes|normalized_payload|canonical_bytes)\b",
        executable_sql,
    )
    assert "canonical_bytes = convert_to(normalized_payload::text, 'utf8')" in normalized


def test_source_version_references_a_retained_immutable_object() -> None:
    assert "create table if not exists context.retained_object" in NORMALIZED
    assert "content_sha256 bytea not null check (octet_length(content_sha256) = 32)" in NORMALIZED
    assert "original_object_id uuid references context.retained_object(id)" in NORMALIZED
    assert "status text not null default 'registered' check (status in ('registered', 'retained'))" in NORMALIZED
    assert "status = 'registered' and original_object_id is null" in NORMALIZED
    assert "status = 'retained' and original_object_id is not null" in NORMALIZED
    assert "source_version_original_object_membership_fk" in NORMALIZED
    assert "unique (source_id, submission_idempotency_key)" in NORMALIZED
    assert "inline_bytes bytea" in NORMALIZED
    assert "storage_class = 'inline' and inline_bytes is not null" in NORMALIZED
    assert "octet_length(inline_bytes) = byte_length" in NORMALIZED
    assert "storage_class <> 'inline' and inline_bytes is null" in NORMALIZED


def test_raw_identity_requires_exact_range_or_stored_bytes_and_retains_all_spans() -> None:
    assert "create table if not exists context.raw_record_identity" in NORMALIZED
    assert "record_status in ('parsed', 'rejected', 'malformed', 'unknown', 'unparsed', 'envelope')" in NORMALIZED
    assert "raw_hash_construction text not null" in NORMALIZED
    assert "raw_hash_construction in (" in NORMALIZED
    assert "record_status not in ('envelope', 'unparsed')" in NORMALIZED
    assert "or raw_hash_construction = 'h2-rawspan-v1'" in NORMALIZED
    assert "persist stage, not the parser, assigns the exact h2 construction" in NORMALIZED
    assert "(record_status = 'parsed') or status_reason is not null" in NORMALIZED
    assert "stored_bytes is not null" in NORMALIZED
    assert "locator_object_id is not null" in NORMALIZED
    assert "byte_offset is not null and byte_offset >= 0" in NORMALIZED
    assert "foreign key (source_version_id, locator_object_id)" in NORMALIZED


def test_format_subtypes_use_shared_fk_and_registry_relation_identity_not_raw_table_pointer() -> None:
    assert "create table if not exists context.raw_format_registry" in NORMALIZED
    assert "subtype_relation regclass not null unique" in NORMALIZED
    assert "create function context.register_raw_format_subtype" in NORMALIZED
    assert "raw_record_id uuid primary key" in NORMALIZED
    assert "references context.raw_record_identity(id)" in NORMALIZED
    assert "assert_raw_subtype_completeness" in NORMALIZED
    assert "format_id ~ '^[a-z][a-z0-9_]{0,58}$'" in NORMALIZED
    assert "unique (id, format_id)" in NORMALIZED
    assert "foreign key (raw_generation_id, format_id)" in NORMALIZED
    assert "raw_table text" not in NORMALIZED


def test_normalized_to_raw_lineage_is_real_many_to_many_foreign_keys() -> None:
    assert "create table if not exists context.normalization_lineage" in NORMALIZED
    assert "foreign key (normalized_record_id, normalized_generation_id)" in NORMALIZED
    assert "foreign key (normalized_generation_id, raw_generation_id)" in NORMALIZED
    assert "foreign key (raw_record_id, raw_generation_id)" in NORMALIZED
    assert "unique (normalized_record_id, raw_record_id, derivation_role)" in NORMALIZED
    assert (
        "derivation_role in ('primary_source', 'supplementary', 'merge_source', 'attachment_source', 'correction_source')"
        in NORMALIZED
    )
    assert "field_map jsonb not null default '[]'::jsonb check (jsonb_typeof(field_map) = 'array')" in NORMALIZED


def test_receipts_cover_idempotency_five_hash_kinds_and_reconciliation() -> None:
    assert "create table if not exists context.activity_execution" in NORMALIZED
    assert "unique (source_version_id, activity_name, idempotency_key)" in NORMALIZED
    assert "create table if not exists context.activity_receipt" in NORMALIZED
    for hash_kind in (
        "h1_source",
        "raw_record_digest",
        "h3_raw_generation",
        "normalized_record_digest",
        "normalized_generation_manifest_digest",
    ):
        assert f"'{hash_kind}'" in NORMALIZED
    for reconciliation_kind in (
        "record_accounting",
        "byte_coverage",
        "raw_source_verification",
        "raw_lineage_validation",
        "normalized_generation_verification",
    ):
        assert f"'{reconciliation_kind}'" in NORMALIZED


def test_activity_receipt_terminal_shapes_are_mutually_exclusive() -> None:
    assert "status = 'success' and completed_at is not null" in NORMALIZED
    assert "result_ref is not null and error_detail is null and not_applicable_reason is null" in NORMALIZED
    assert "status = 'failed' and completed_at is not null" in NORMALIZED
    assert "result_ref is null and error_detail is not null and not_applicable_reason is null" in NORMALIZED
    assert "status = 'not_applicable' and completed_at is not null" in NORMALIZED
    assert "result_ref is null and error_detail is null and not_applicable_reason is not null" in NORMALIZED


def test_activity_receipt_does_not_reference_undeclared_subject_columns() -> None:
    """Subject ownership is derived through activity_execution, not phantom columns."""
    activity_receipt_ddl = NORMALIZED.split("create table if not exists context.activity_receipt", 1)[1].split(
        "create table if not exists context.hash_batch", 1
    )[0]
    assert "foreign key (activity_execution_id, source_version_id)" not in activity_receipt_ddl
    assert "foreign key (raw_generation_id, source_version_id)" not in activity_receipt_ddl
    assert "foreign key (normalized_generation_id, source_version_id)" not in activity_receipt_ddl


def test_generation_manifest_membership_is_bounded_durable_and_sealed() -> None:
    assert "create table if not exists context.hash_batch" in NORMALIZED
    assert "create table if not exists context.hash_batch_member" in NORMALIZED
    assert "unique (activity_execution_id, attempt)" in NORMALIZED
    assert "hash batch lifecycle only permits immutable open -> completed/aborted" in NORMALIZED
    assert "completed hash batch requires exact durable membership and activity result" in NORMALIZED
    assert "create trigger hash_batch_member_open_gate" in NORMALIZED
    assert "create trigger hash_batch_transition_gate" in NORMALIZED
    assert "member staging is durable and uses short transactions" in NORMALIZED
    assert "postgresql transaction or pool connection while reading an external object" in NORMALIZED
    assert "create table if not exists context.hash_manifest" in NORMALIZED
    assert "create table if not exists context.hash_manifest_member" in NORMALIZED
    assert "primary key (hash_manifest_id, ordinal)" in NORMALIZED
    assert "member_digest bytea not null check (octet_length(member_digest) = 32)" in NORMALIZED
    assert "ordered_member_digests" not in NORMALIZED
    assert "create function context.assert_hash_manifest_complete" in NORMALIZED
    assert "create function context.seal_hash_manifest_from_receipt" in NORMALIZED
    assert "create trigger hash_manifest_member_open_gate" in NORMALIZED
    assert "create trigger hash_manifest_seal_gate" in NORMALIZED
    assert "member_count > 0" in NORMALIZED
    assert "cannot seal with zero members" in NORMALIZED


def test_hash_and_reconciliation_receipts_require_successful_exact_stage_activity() -> None:
    assert "activity_receipt_id uuid not null references context.activity_receipt(id)" in NORMALIZED
    assert "create function context.guard_hash_receipt_insert" in NORMALIZED
    assert "create function context.guard_reconciliation_receipt_insert" in NORMALIZED
    for activity_name in (
        "hash_source_activity",
        "hash_raw_records_activity",
        "hash_raw_generation_activity",
        "hash_normalized_records_activity",
        "hash_normalized_generation_activity",
        "reconcile_record_accounting_activity",
        "reconcile_byte_coverage_activity",
        "verify_raw_coverage_against_source_activity",
        "validate_raw_lineage_activity",
        "verify_normalized_generation_activity",
    ):
        assert f"'{activity_name}'" in NORMALIZED
    assert "receipt.status = 'success'" in NORMALIZED
    assert "execution.source_version_id = v_subject_source_version_id" in NORMALIZED
    assert "create trigger hash_receipt_insert_gate" in NORMALIZED
    assert "create trigger reconciliation_receipt_insert_gate" in NORMALIZED


def test_hash_canon_tags_and_manifest_members_are_exact_and_security_critical() -> None:
    assert "construction text not null" in NORMALIZED
    for canon in (
        "h1-rawbytes-v1",
        "h2-rawelement-v1",
        "h2-rawrecord-v1",
        "h2-rawspan-v1",
        "h3-chain-platform-rawall-genesisempty-v1",
        "normalized-record-postgresql18-jsonb-text-utf8-sha256-v1",
        "normalized-generation-ordered-digests-lengthframed-sha256-v1",
    ):
        assert f"'{canon}'" in NORMALIZED
    assert "h.construction = new.member_canon" in NORMALIZED


def test_metadata_and_normalized_bytes_have_nonoptional_verified_provenance() -> None:
    assert "extraction_activity_receipt_id uuid not null" in NORMALIZED
    assert "create function context.guard_source_metadata_insert" in NORMALIZED
    for activity_name in (
        "capture_filesystem_metadata_activity",
        "inventory_container_activity",
        "extract_embedded_metadata_activity",
        "execute_parser_activity",
    ):
        assert f"'{activity_name}'" in NORMALIZED
    assert "canonical_bytes bytea not null" in NORMALIZED
    assert "canonicalization text not null" in NORMALIZED
    assert "canonicalization = 'normalized-record-postgresql18-jsonb-text-utf8-sha256-v1'" in NORMALIZED
    assert "canonical_bytes = convert_to(normalized_payload::text, 'utf8')" in NORMALIZED
    assert "digest(normalized.canonical_bytes, 'sha256') = new.digest" in NORMALIZED
    assert "normalized.canonicalization = new.construction" in NORMALIZED
    assert "length(btrim(not_applicable_reason)) > 0" in NORMALIZED


def test_h1_and_db_resident_h2_receipts_verify_exact_retained_bytes() -> None:
    assert "create function context.guard_hash_receipt_insert" in NORMALIZED
    assert "original_object.content_sha256 = new.digest" in NORMALIZED
    assert "h1 receipt must equal the retained original content_sha256" in NORMALIZED
    assert "digest(raw.stored_bytes, 'sha256') = new.digest" in NORMALIZED
    assert "locator_object.storage_class = 'inline'" in NORMALIZED
    assert "from raw.byte_offset + 1 for raw.byte_length" in NORMALIZED
    assert "raw.byte_offset + raw.byte_length <= locator_object.byte_length" in NORMALIZED
    assert "raw.raw_hash_construction = new.construction" in NORMALIZED
    assert "raw h2 receipt does not match db-resident stored bytes or inline byte range" in NORMALIZED


def test_retention_transition_is_narrow_and_downstream_writes_require_retained_source() -> None:
    assert "create function context.guard_source_version_mutation" in NORMALIZED
    assert "source version lifecycle only permits registered -> retained with its original object" in NORMALIZED
    assert "create function context.assert_source_version_retained" in NORMALIZED
    assert "create trigger raw_generation_retention_gate" in NORMALIZED
    assert "create trigger normalized_generation_retention_gate" in NORMALIZED
    assert "create trigger activity_execution_retention_gate" in NORMALIZED
    assert "only the original object may be attached before source version retention" in NORMALIZED
    assert "receipt.result_ref->>'ref_kind' = 'retained_object'" in NORMALIZED
    assert "receipt.result_ref->>'ref_id' = new.original_object_id::text" in NORMALIZED


def test_activity_result_refs_bind_authorized_receipts_to_exact_output_rows() -> None:
    assert "receipt.result_ref->>'ref_kind' = 'hash_receipt'" in NORMALIZED
    assert "receipt.result_ref->>'ref_id' = new.id::text" in NORMALIZED
    assert "receipt.result_ref->>'ref_kind' = 'raw_hash_receipt_set'" in NORMALIZED
    assert "select raw_generation_id::text" in NORMALIZED
    assert "where id = new.raw_record_id" in NORMALIZED
    assert "receipt.result_ref->>'ref_kind' = 'normalized_hash_receipt_set'" in NORMALIZED
    assert "select normalized_generation_id::text" in NORMALIZED
    assert "where id = new.normalized_record_id" in NORMALIZED
    assert "stream an exact source-generation" in NORMALIZED
    assert "receipt.result_ref->>'ref_kind' = 'reconciliation_receipt'" in NORMALIZED
    assert "receipt.result_ref->>'ref_kind' = 'normalized_generation_publication'" in NORMALIZED


def test_generation_seal_requires_contiguous_nonempty_rows_and_span_rows_are_not_orphaned() -> None:
    assert "raw generation % cannot seal with zero records or envelope spans" in NORMALIZED
    assert "raw generation % has non-contiguous record ordinals" in NORMALIZED
    assert "normalized generation % cannot seal with zero records" in NORMALIZED
    assert "normalized generation % has non-contiguous record ordinals" in NORMALIZED
    assert "no orphan span table is permitted" in NORMALIZED


def test_verification_receipts_declare_independent_digest_recomputation() -> None:
    assert "expected ? 'h3_raw_generation'" in NORMALIZED
    assert "expected ? 'normalized_generation_manifest_digest'" in NORMALIZED
    assert "verification_mode' = 'independent_recomputation'" in NORMALIZED


def test_hash_subjects_are_unique_and_generation_seal_checks_sealed_manifest() -> None:
    for index_name in (
        "hash_receipt_h1_source_uq",
        "hash_receipt_h2_raw_record_uq",
        "hash_receipt_h3_raw_generation_uq",
        "hash_receipt_normalized_record_uq",
        "hash_receipt_normalized_generation_manifest_uq",
    ):
        assert f"create unique index if not exists {index_name}" in NORMALIZED
    assert "manifest.status = 'sealed'" in NORMALIZED
    assert "manifest.member_count = (" in NORMALIZED


def test_normalized_seal_and_publish_are_fail_closed() -> None:
    assert "create function context.guard_raw_generation_transition" in NORMALIZED
    assert "raw generation % lacks required h1/h2/h3 receipts" in NORMALIZED
    assert "create function context.guard_normalized_generation_transition" in NORMALIZED
    assert "cannot seal without raw-record lineage for every member" in NORMALIZED
    assert "lacks required normalized digest receipts" in NORMALIZED
    assert "lacks required successful reconciliation receipts" in NORMALIZED
    assert "cannot publish without a publication receipt" in NORMALIZED
    assert "create trigger normalized_generation_seal_publish_gate" in NORMALIZED
