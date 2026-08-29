"""Static contracts for migration 0047.

Byline: Codex · GPT-5 · 2026-08-29.
"""

from __future__ import annotations

import re
import os
from pathlib import Path

import pytest
import sqlparse

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0047_content_chunk_and_context_thread_foundation.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
NORMALIZED = " ".join(SQL.lower().split())


def _table_body(name: str) -> str:
    match = re.search(
        rf"create table {re.escape(name)}\s*\((.*?)\n\);",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing table {name}"
    return " ".join(match.group(1).lower().split())


def test_targets_fresh_platform_and_is_additive() -> None:
    assert "current_database() <> 'platform'" in NORMALIZED
    assert "migration 0047 requires migrations 0024, 0026, 0036, 0043, and 0044" in NORMALIZED
    assert "drop table" not in NORMALIZED
    assert "alter table working.chat_chunk" not in NORMALIZED
    assert "alter table working.normalized_record_chunk" not in NORMALIZED
    assert "legacy `ai`" not in NORMALIZED
    assert "on delete cascade" not in NORMALIZED


def test_migration_is_transactional_and_sqlparse_tokenizable() -> None:
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    for statement in statements:
        assert sqlparse.parse(statement), statement[:120]


def test_generalized_chunks_are_generation_scoped_without_global_hash_uniqueness() -> None:
    generation = _table_body("working.content_chunk_generation")
    chunk = _table_body("working.content_chunk")
    assert "status in ('open', 'sealed', 'aborted')" in generation
    assert "check (completeness_scope = 'complete')" in generation
    assert "unique (source_version_id, generation_ordinal)" in generation
    assert "normalized_generation_id" in generation
    for contract in (
        "policy_id",
        "policy_version",
        "chunker_id",
        "chunker_version",
        "config_digest",
        "implementation_digest",
        "source_canonicalization",
        "manifest_sha256",
        "activity_execution_id",
        "activity_receipt_id",
    ):
        assert contract in generation
    assert "unique (generation_id, chunk_index)" in chunk
    assert "unique (content_sha256)" not in chunk
    assert "derivation_mode in ('verbatim_span', 'composed', 'unverified_derived')" in chunk
    assert "coordinate_system" not in chunk
    assert "range_start" not in chunk and "range_end" not in chunk
    assert "digest(convert_to(content, 'utf8'), 'sha256') = content_sha256" in chunk


def test_typed_half_open_same_source_lineage_is_not_json_authority() -> None:
    locator = _table_body("context.source_range_locator")
    span = _table_body("working.content_chunk_source_span")
    assert "coordinate_subject" not in locator
    assert "source_object_id" not in locator
    assert "raw_record_id" not in locator
    assert "normalized_record_id" not in locator
    assert "range_start bigint not null check (range_start >= 0)" in locator
    assert "range_end bigint not null check (range_end > range_start)" in locator
    assert "exact_slice_sha256" in locator
    source_object = _table_body("context.source_object_range_locator")
    raw_record = _table_body("context.raw_record_range_locator")
    normalized_record = _table_body("context.normalized_record_range_locator")
    assert "foreign key (source_version_id, source_object_id)" in source_object
    assert "foreign key (raw_record_id, source_version_id)" in raw_record
    assert "foreign key (normalized_record_id, source_version_id)" in normalized_record
    assert "locator_projection" in locator
    assert "source_range_locator_id" in span
    assert "references context.source_range_locator(id, source_version_id)" in span
    assert "locator_projection is non-authoritative" in NORMALIZED
    assert "entity_type" not in locator
    assert "entity_id" not in locator
    assert "source range locator requires exactly one typed subject link" in NORMALIZED


def test_complete_verbatim_seal_requires_exact_reassembly_receipt() -> None:
    receipt = _table_body("working.content_chunk_reassembly_receipt")
    assert "source_sha256 = reassembled_sha256" in receipt
    assert "covered_range_end = source_byte_length" in receipt
    assert "gap_count = 0 and overlap_count = 0" in receipt
    assert "complete verbatim generation requires exact full-coverage reassembly" in NORMALIZED
    assert "one db-verified utf-8 byte locator into source_version.original_object_id per chunk" in NORMALIZED
    assert "cover source bytes exactly once without gaps or overlaps" in NORMALIZED
    assert "proof.span_count <> 1" in NORMALIZED
    assert "locator.exact_slice_sha256 = chunk.content_sha256" in NORMALIZED
    assert "object_subject.source_object_id = version.original_object_id" in NORMALIZED
    assert "retained.inline_bytes is not null" in NORMALIZED
    assert "db-verified utf-8 byte locator into source_version.original_object_id" in NORMALIZED
    assert "sealed chunk/member counts do not match materialized rows" in NORMALIZED
    assert "semantica structuralchunker negative fixture f2e9d2a" in NORMALIZED
    assert "omitted 176 chars" in NORMALIZED
    assert "24/35 chunks were non-verbatim" in NORMALIZED


def test_chunk_children_are_immutable_and_sealed_generation_rejects_writes() -> None:
    for trigger in (
        "content_chunk_generation_transition_gate",
        "content_chunk_open_generation_gate",
        "content_chunk_source_span_gate",
        "content_chunk_reassembly_receipt_gate",
        "content_chunk_classification_append_only",
    ):
        assert f"create trigger {trigger}" in NORMALIZED
    assert "insert requires an open content chunk generation" in NORMALIZED
    assert "source span insert requires an open content chunk generation" in NORMALIZED
    assert "reassembly receipt requires an open generation" in NORMALIZED


def test_context_first_reviewed_classification_has_no_evidence_lane() -> None:
    decision = _table_body("working.content_chunk_classification_decision")
    assert "lane in ('context', 'legal', 'personal_history')" in decision
    assert "initial_context" in decision
    assert "reviewed_assignment" in decision
    assert "supersession" in decision
    assert "lane = 'context' and review_state = 'system_initial'" in decision
    assert "'evidence'" not in decision
    assert "context-first-ingest-policy" in NORMALIZED


def test_first_and_third_party_threads_are_physically_separate_and_mirrored() -> None:
    first = _table_body("working.first_party_context_thread")
    third = _table_body("working.third_party_context_thread")
    assert "context_thread_id uuid primary key" in first
    assert "context_thread_id uuid primary key" in third
    assert "owner_person_id" in first
    assert "owner_person_id" not in third
    for table in (
        "working.first_party_context_thread_version",
        "working.third_party_context_thread_version",
        "working.first_party_context_thread_message",
        "working.third_party_context_thread_message",
        "working.first_party_context_thread_source",
        "working.third_party_context_thread_source",
    ):
        assert f"create table {table}" in NORMALIZED
    first_members = _table_body("working.first_party_context_thread_message")
    third_members = _table_body("working.third_party_context_thread_message")
    assert "references working.message(id)" in first_members
    assert "third_party_message" not in first_members
    assert "references working.third_party_message(id)" in third_members
    assert "references working.message(id)" not in third_members
    assert "thread_ordinal" in first_members and "thread_ordinal" in third_members


def test_owner_anchor_and_third_party_acquisition_exclusion_are_guarded() -> None:
    assert "first-party context thread requires the configured owner person" in NORMALIZED
    assert "role_in_case = 'user'" in NORMALIZED
    assert "third-party context cannot include or invent owner participation" in NORMALIZED
    assert "third-party source perspective cannot be the owner" in NORMALIZED
    assert "conversation_acquisition_id" in _table_body("working.third_party_context_thread_message")
    assert "conversation_acquisition_id" in _table_body("working.third_party_context_thread_source")
    assert "acquisition_activity_receipt_id" in _table_body("working.third_party_context_thread_source")
    assert "approval_state = 'approved'" in NORMALIZED
    assert "successful same-source acquisition receipt" in NORMALIZED


def test_cross_platform_multi_representation_sources_are_many_to_many_and_versioned() -> None:
    for party in ("first_party", "third_party"):
        body = _table_body(f"working.{party}_context_thread_source")
        for field in (
            "thread_version_id",
            "source_version_id",
            "platform",
            "platform_conversation_key",
            "representation_kind",
            "capture_kind",
            "declared_format",
            "originating_device_id",
            "coverage_first_occurred_at",
            "coverage_last_occurred_at",
            "coverage_message_count",
            "assertion_version",
            "supersedes_id",
            "provenance_digest",
        ):
            assert field in body
        assert "unique (source_version_id)" not in body
    assert "none is collapsed or selected as canonical" in NORMALIZED
    assert "native_export" in NORMALIZED and "screenshot" in NORMALIZED and "ocr_derived" in NORMALIZED


def test_representation_clocks_do_not_replace_primary_availability_clocks() -> None:
    for party in ("first_party", "third_party"):
        body = _table_body(f"working.{party}_context_thread_source")
        for field in (
            "metadata_clock_kind",
            "metadata_timestamp",
            "metadata_timezone",
            "metadata_clock_basis",
            "metadata_confidence",
            "metadata_review_state",
            "metadata_ambiguity",
            "raw_metadata",
            "raw_metadata_ref",
            "metadata_extractor_id",
            "metadata_extractor_version",
        ):
            assert field in body
    assert "first-party availability must equal the message occurred_at clock" in NORMALIZED
    first_source = _table_body("working.first_party_context_thread_source")
    first_message = _table_body("working.first_party_context_thread_message")
    assert "source_available_from" in first_source
    assert "source_available_from is not distinct from coverage_last_occurred_at" in first_source
    assert "required_for_horizon" in first_source
    assert "required_for_horizon" in first_message
    assert "from working.first_party_context_thread_message" in NORMALIZED
    assert "third-party source availability cannot be backdated to capture/export metadata" in NORMALIZED
    assert "source_available_from is distinct from v_acquired_at" in NORMALIZED
    assert "third-party thread membership occurred_at must equal the canonical message occurrence" in NORMALIZED


def test_thread_occurrence_horizon_and_realization_are_distinct() -> None:
    for party in ("first_party", "third_party"):
        version = _table_body(f"working.{party}_context_thread_version")
        assert "first_occurred_at" in version
        assert "last_occurred_at" in version
        assert "knowledge_available_from" in version
        realization = _table_body(f"working.{party}_context_thread_realization_assertion")
        assert "required_source_available_from" in realization
        assert "realization_event_id" in realization
        assert "assertion_version" in realization
        assert "supersedes_id" in realization
        required_sources = _table_body(f"working.{party}_context_thread_realization_source")
        assert "required_for_realization" in required_sources
        assert "thread_source_id" in required_sources
        required_messages = _table_body(f"working.{party}_context_thread_realization_message")
        assert "required_for_realization" in required_messages
        assert "message_id" in required_messages
    assert "greatest availability clock" in NORMALIZED
    assert "claim realization actually occurred" in NORMALIZED
    assert "max(source_available_from)" in NORMALIZED
    assert "availability must equal the greatest required source availability" in NORMALIZED


def test_relative_time_is_shared_versioned_and_typed() -> None:
    anchor = _table_body("context.relative_time_anchor")
    for field in (
        "last_known_before_anchor_id",
        "first_known_after_anchor_id",
        "lower_bound_at",
        "upper_bound_at",
        "contextual_sequence_key",
        "contextual_sequence_ordinal",
        "metadata_basis",
        "raw_metadata",
        "raw_metadata_ref",
        "confidence",
        "ambiguity",
        "review_state",
        "provenance_digest",
        "version_ordinal",
        "supersedes_id",
    ):
        assert field in anchor
    for table in (
        "context.first_party_thread_version_relative_time_anchor",
        "context.third_party_thread_version_relative_time_anchor",
        "context.first_party_thread_source_relative_time_anchor",
        "context.third_party_thread_source_relative_time_anchor",
        "context.first_party_thread_message_relative_time_anchor",
        "context.third_party_thread_message_relative_time_anchor",
    ):
        body = _table_body(table)
        assert "anchor_id" in body
        assert "entity_type" not in body and "entity_id" not in body
    assert "presentation_payload" in anchor
    assert "presentation only" in NORMALIZED
    assert "first-party required null clocks prohibit an exact thread horizon" in NORMALIZED
    assert "third-party required null clocks prohibit an exact thread horizon" in NORMALIZED
    assert "link.link_role = 'primary_fallback'" in NORMALIZED
    assert "anchor.review_state in ('proposed', 'approved')" in NORMALIZED
    event_link = _table_body("timeline.event_candidate_relative_time_anchor")
    assert "references timeline.event_candidate(id) on delete restrict" in event_link
    assert "references context.relative_time_anchor(id) on delete restrict" in event_link
    assert (
        "anchor_role in ('occurred_at', 'valid_from', 'valid_to', 'source_available_from', 'realizable_from')"
    ) in event_link
    assert "typed source authority is timeline.event_candidate_source_range" in NORMALIZED


def test_legacy_chunk_stores_are_mapped_not_renamed_or_dropped() -> None:
    assert "create table working.legacy_chat_chunk_content_chunk_map" in NORMALIZED
    assert "create table working.legacy_normalized_chunk_content_chunk_map" in NORMALIZED
    assert "references working.chat_chunk(id) on delete restrict" in NORMALIZED
    assert "references working.normalized_record_chunk(id) on delete restrict" in NORMALIZED
    assert "backfill_receipt_id" in NORMALIZED


def test_no_format_specific_or_engine_owned_implementation_is_added() -> None:
    assert "does not choose or run a chunker" in NORMALIZED
    assert "file format; it does not backfill" in NORMALIZED
    assert "tool implementations remain in platform tools" in NORMALIZED
    assert "the go engine calls that service" in NORMALIZED
    assert "directly; this migration creates no engine-owned" in NORMALIZED
    assert "create function engine." not in NORMALIZED


def test_chunking_and_timeline_extraction_are_independent_sibling_passes() -> None:
    event_ranges = _table_body("timeline.event_candidate_source_range")
    assert "event_candidate_id" in event_ranges
    assert "source_range_locator_id" in event_ranges
    assert "schema_manifest_digest" in event_ranges
    assert "extraction_activity_receipt_id" in event_ranges
    assert "content_chunk" not in event_ranges
    generation = _table_body("working.content_chunk_generation")
    assert "event_candidate" not in generation
    assert "independent sibling passes" in NORMALIZED
    assert "never carves content out of or depends on chunks" in NORMALIZED
    assert "successful independent same-source extraction receipt" in NORMALIZED


def test_shared_hitl_conflict_plane_is_typed_append_only_and_versioned() -> None:
    review_case = _table_body("working.context_review_case")
    decision = _table_body("working.context_review_decision")
    assert "conflict_kind in ('relative_time', 'first_party_thread', 'third_party_thread'" in review_case
    assert "source_representation_equivalence" in review_case
    assert "timeline_event" in review_case
    assert (
        "decision_action in ('accept', 'reject', 'coexist', 'supersede_correct', 'needs_more_evidence')"
    ) in decision
    for field in (
        "reviewer_id",
        "rationale",
        "provenance_digest",
        "decision_activity_receipt_id",
        "decided_at",
        "supersedes_decision_id",
        "supersedes_decision_version",
        "status",
    ):
        assert field in decision
    for table in (
        "working.context_review_relative_time_anchor",
        "working.context_review_first_party_thread_version",
        "working.context_review_third_party_thread_version",
        "working.context_review_first_party_thread_message",
        "working.context_review_third_party_thread_message",
        "working.context_review_first_party_thread_source",
        "working.context_review_third_party_thread_source",
        "working.context_review_timeline_event_candidate",
        "working.context_review_decision_source_version",
        "working.context_review_decision_source_range",
        "working.context_review_decision_evidence_hash",
    ):
        body = _table_body(table)
        assert "entity_type" not in body
    assert "create view working.context_review_current_decision" in NORMALIZED
    assert "create view working.context_review_current_case" in NORMALIZED
    assert "create view working.context_review_open_queue" in NORMALIZED
    assert "create trigger context_review_append_only" in NORMALIZED
    assert "grant select on table %s to platform_runtime, context_review_adjudicator" in NORMALIZED
    assert "grant insert on working.context_review_case" in NORMALIZED
    assert "v_relation::text" not in NORMALIZED
    assert "working.context_review_decision," in NORMALIZED
    assert "status <> 'final' or decision_activity_receipt_id is not null" in decision
    assert "to context_review_adjudicator" in NORMALIZED
    assert "platform_runtime must never inherit context_review_adjudicator" in NORMALIZED
    assert "only context_review_adjudicator may insert adjudication decisions" in NORMALIZED
    assert "only context_review_adjudicator may append review-case lifecycle versions" in NORMALIZED
    assert "shared workbench review queue case" in NORMALIZED


def test_third_party_source_acquisition_is_typed_to_represented_conversation() -> None:
    source = _table_body("working.third_party_context_thread_source")
    assert "represented_conversation_id" in source
    assert "references working.third_party_conversation(id) on delete restrict" in source
    assert "conversation_acquisition_id" in source
    assert "link.conversation_id = new.represented_conversation_id" in NORMALIZED
    assert "platform key must match its typed represented conversation" in NORMALIZED
    assert "represented conversation must belong to the same thread version" in NORMALIZED


def test_hitl_temporal_n8n_workbench_orchestration_is_reference_only() -> None:
    workflow = _table_body("working.context_review_temporal_workflow")
    for field in (
        "review_case_id",
        "expected_case_version",
        "temporal_workflow_id",
        "workflow_idempotency_key",
        "reminder_policy_ref",
        "escalation_policy_ref",
    ):
        assert field in workflow
    assert "payload" not in workflow
    run_state = _table_body("working.context_review_temporal_run_state")
    assert "temporal_run_id" in run_state
    assert "state_version" in run_state
    assert "state_digest" in run_state
    assert "supersedes_state_id" in run_state
    assert "payload" not in run_state
    dispatch = _table_body("working.context_review_dispatch_attempt")
    assert "dispatch_attempt" in dispatch
    assert "dispatch_idempotency_key" in dispatch
    assert "n8n_workflow_ref" in dispatch
    assert "review_service_ref" in dispatch
    assert "dispatch_receipt_digest" in dispatch
    signal = _table_body("working.context_review_signal_receipt")
    assert "signal_idempotency_key" in signal
    assert "decision_id" in signal
    assert "persisted_decision_version" in signal
    terminal = _table_body("working.context_review_terminal_reconciliation")
    assert "expected_case_version" in terminal
    assert "expected_decision_version" in terminal
    assert "reconciliation_status" in terminal
    assert "downstream_projection_receipt_ref" in terminal
    assert "one durable temporal conflictreviewworkflow identity" in NORMALIZED
    assert "n8n selects/invokes swappable review ui/service/notification adapters" in NORMALIZED
    assert "never approval authority" in NORMALIZED
    assert "shared workbench review queue case" in NORMALIZED


def test_locator_verification_handles_bytes_and_codepoints_fail_closed() -> None:
    assert "exact source locator requires retained bytes available to postgresql" in NORMALIZED
    assert "source range locator exceeds its typed subject byte length" in NORMALIZED
    assert "source range locator exceeds its typed subject codepoint length" in NORMALIZED
    assert "unicode-codepoint locator requires valid utf-8 retained bytes" in NORMALIZED
    assert "convert_from(v_bytes, 'utf8')" in NORMALIZED
    assert "digest(v_slice, 'sha256')" in NORMALIZED
    assert "::int4" not in NORMALIZED


def test_role_and_timeline_grants_are_explicit() -> None:
    assert "create role context_review_adjudicator nologin nosuperuser" in NORMALIZED
    assert "grant usage on schema working, context, timeline" in NORMALIZED
    assert "grant select, insert on timeline.event_candidate_source_range" in NORMALIZED
    assert "timeline.event_candidate_relative_time_anchor" in NORMALIZED
    assert "to timeline_writer" in NORMALIZED
    assert "to timeline_projector" in NORMALIZED
    assert "content_chunk_source_span_generation_idx" in NORMALIZED


@pytest.mark.integration
def test_pg18_rollback_role_and_review_lifecycle_behavior() -> None:
    """Apply 0047 and exercise ACL/lifecycle guards in one rollback-only transaction.

    Set ``PLATFORM_0047_TEST_SERVICE`` to a libpq service targeting the already-migrated
    disposable ``platform`` validation database. No password or raw connection string is
    accepted by this test.
    """

    service = os.getenv("PLATFORM_0047_TEST_SERVICE")
    if not service:
        pytest.skip("set PLATFORM_0047_TEST_SERVICE for rollback-only PostgreSQL 18 behavior proof")
    psycopg = pytest.importorskip("psycopg")
    ddl = re.sub(r"^\s*BEGIN;\s*", "", SQL, count=1, flags=re.IGNORECASE)
    ddl = re.sub(r"\s*COMMIT;\s*$", "", ddl, count=1, flags=re.IGNORECASE)
    connection = psycopg.connect(service=service, dbname="platform", connect_timeout=10)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('server_version_num')::INTEGER")
            assert cursor.fetchone()[0] >= 180000
            cursor.execute(ddl)
            cursor.execute("SET LOCAL ROLE platform_runtime")
            cursor.execute(
                """
                INSERT INTO working.context_review_case (
                    case_version, conflict_kind, summary, opened_by, provenance_digest
                ) VALUES (1, 'relative_time', 'rollback lifecycle probe',
                          'rollback-validator', digest('case-v1', 'sha256'))
                RETURNING id, case_key
                """
            )
            case_id, case_key = cursor.fetchone()
            cursor.execute("SELECT count(*) FROM working.context_review_open_queue WHERE case_key = %s", (case_key,))
            assert cursor.fetchone()[0] == 1
            cursor.execute("SAVEPOINT runtime_terminal_probe")
            with pytest.raises(psycopg.errors.RaiseException, match="context_review_adjudicator"):
                cursor.execute(
                    """
                    INSERT INTO working.context_review_case (
                        case_key, case_version, conflict_kind, status, summary, opened_by,
                        provenance_digest, supersedes_case_id, supersedes_case_version
                    ) VALUES (%s, 2, 'relative_time', 'withdrawn', 'forbidden runtime close',
                              'rollback-validator', digest('case-v2', 'sha256'), %s, 1)
                    """,
                    (case_key, case_id),
                )
            cursor.execute("ROLLBACK TO SAVEPOINT runtime_terminal_probe")
            cursor.execute("RESET ROLE")
            cursor.execute(
                "SELECT has_table_privilege('platform_runtime', "
                "'working.context_review_decision', 'INSERT'), "
                "has_table_privilege('context_review_adjudicator', "
                "'working.context_review_decision', 'INSERT')"
            )
            assert cursor.fetchone() == (False, True)
            cursor.execute(
                "SELECT has_table_privilege('timeline_writer', "
                "'timeline.event_candidate_source_range', 'INSERT'), "
                "has_table_privilege('timeline_projector', "
                "'timeline.event_candidate_source_range', 'SELECT')"
            )
            assert cursor.fetchone() == (True, True)
    finally:
        connection.rollback()
        connection.close()
