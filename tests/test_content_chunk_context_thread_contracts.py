"""Contract tests for format-neutral chunks and cross-platform context threads.

Byline: Codex · GPT-5 · 2026-08-29
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

import pytest
from pydantic import ValidationError

from server.contracts.context_thread import (
    ConflictAdjudicationDecision,
    ConflictReviewActivityRequest,
    ConflictReviewCase,
    ConflictReviewDecisionSignal,
    ConflictReviewDispatchReceipt,
    ConflictReviewQueueEvent,
    ConflictReviewTerminalReconciliation,
    ConflictReviewWorkflowReference,
    EventCandidateRelativeTimeAnchorLink,
    FirstPartySourceRepresentationEquivalenceConflictReviewLink,
    FirstPartyContextThread,
    FirstPartyMessageAnchor,
    FirstPartyOwnerAnchor,
    FirstPartyParticipant,
    FirstPartyRelativeDateAnchor,
    FirstPartySourceRepresentation,
    FirstPartyTimestampMetadata,
    ReviewedRealizationLink,
    ThirdPartyAcquisitionAnchor,
    ThirdPartyApprovalAnchor,
    ThirdPartyContextThread,
    ThirdPartyMessageAnchor,
    ThirdPartyParticipant,
    ThirdPartyRelativeDateAnchor,
    ThirdPartySourceRepresentation,
    ThirdPartyTimestampMetadata,
)
from server.contracts.ingest import IngestReceipt, IngestRequest
from server.contracts.records import (
    ChunkCompletenessResult,
    ChunkGeneration,
    ChunkGenerationCompletenessBinding,
    ContentChunk,
    LaneClassification,
    SourceByteRange,
    SourceDerivationManifest,
    TimelineEventCandidateProvenance,
)


UTC = timezone.utc
T1 = datetime(2020, 1, 1, tzinfo=UTC)
T2 = datetime(2020, 1, 2, tzinfo=UTC)
ACQUIRED = datetime(2025, 1, 1, tzinfo=UTC)
HASH = sha256(b"hello").hexdigest()


def _content_chunk(**updates) -> ContentChunk:
    values = {
        "chunk_id": "chunk-1",
        "chunk_generation_id": "generation-1",
        "source_version_ref": "source-version-1",
        "chunk_index": 0,
        "derivation_mode": "verbatim_span",
        "content_bytes": b"hello",
        "content_sha256": HASH,
        "source_sha256": HASH,
        "source_byte_length": 5,
        "source_ranges": [SourceByteRange(offset=0, length=5)],
        "chunker_id": "pending",
        "chunk_policy_version": "policy-v1",
        "chunk_schema_version": "schema-v1",
        "implementation_version": "implementation-v1",
    }
    return ContentChunk(**(values | updates))


def _metadata(*, third_party: bool = False):
    cls = ThirdPartyTimestampMetadata if third_party else FirstPartyTimestampMetadata
    return cls(
        raw_metadata_ref="metadata/raw/1",
        extractor_id="metadata-reader",
        extractor_version="1.0.0",
        clock_basis="device_local",
        timezone_basis="America/Detroit",
        parsed_timestamp=T1,
        confidence=0.8,
        review_status="needs_review",
        ambiguity_notes=["device clock may drift"],
    )


def _first_representation(representation_id: str, kind: str = "screenshot"):
    values = {
        "representation_id": representation_id,
        "source_version_ref": f"source/{representation_id}",
        "representation_kind": kind,
        "media_type": "image/png" if kind == "screenshot" else "application/json",
        "platform": "sms",
        "device_principal": "owner-phone",
        "perspective_party_id": "owner",
        "source_sha256": HASH,
        "byte_length": 5,
        "immutable_receipt_ref": f"receipt/{representation_id}",
        "metadata": _metadata(),
    }
    if kind == "screenshot":
        values["metadata_captured_or_created_at"] = T2
    else:
        values["metadata_exported_at"] = T2
        values["observed_metadata_acquired_at"] = T2
    return FirstPartySourceRepresentation(**values)


def _third_representation(representation_id: str, kind: str = "third_party_export"):
    values = {
        "representation_id": representation_id,
        "source_version_ref": f"source/{representation_id}",
        "representation_kind": kind,
        "media_type": "image/png" if kind == "screenshot" else "application/json",
        "platform": "elator",
        "device_principal": "katrina-device",
        "perspective_party_id": "katrina",
        "source_sha256": HASH,
        "byte_length": 5,
        "immutable_receipt_ref": f"receipt/{representation_id}",
        "metadata": _metadata(third_party=True),
        "acquired_at": ACQUIRED,
        "acquisition_receipt_ref": f"receipt/acquisition/{representation_id}",
    }
    if kind == "screenshot":
        values["metadata_captured_or_created_at"] = T2
    else:
        values["metadata_exported_at"] = T2
        values["observed_metadata_acquired_at"] = ACQUIRED
    return ThirdPartySourceRepresentation(**values)


def test_content_chunk_is_byte_addressed_hash_verified_and_has_no_char_offsets() -> None:
    chunk = _content_chunk()
    assert chunk.source_ranges[0].end_offset == 5
    assert "char_start" not in ContentChunk.model_fields
    assert "char_end" not in ContentChunk.model_fields
    with pytest.raises(ValidationError, match="content_sha256"):
        _content_chunk(content_sha256="0" * 64)
    with pytest.raises(ValidationError, match="exactly one"):
        _content_chunk(source_ranges=[])


def test_unverified_chunk_cannot_claim_source_ranges() -> None:
    with pytest.raises(ValidationError, match="cannot claim verified"):
        _content_chunk(derivation_mode="unverified_derived")


def test_completeness_proof_requires_exact_hash_length_and_range_coverage() -> None:
    result = ChunkCompletenessResult(
        status="pass",
        chunk_generation_id="generation-1",
        source_sha256=HASH,
        reassembled_sha256=HASH,
        source_byte_length=5,
        covered_byte_length=5,
        covered_ranges=[SourceByteRange(offset=0, length=2), SourceByteRange(offset=2, length=3)],
        exact_range_coverage=True,
        chunk_count=1,
        chunk_manifest_sha256=HASH,
        locator_set_sha256=HASH,
        receipt_ref="receipt-1",
        activity_ref="activity-1",
    )
    assert result.status == "pass"
    with pytest.raises(ValidationError, match="status does not match"):
        ChunkCompletenessResult(**(result.model_dump() | {"reassembled_sha256": "0" * 64}))
    with pytest.raises(ValidationError, match="not_run"):
        ChunkCompletenessResult(**(result.model_dump() | {"status": "not_run"}))


def test_chunk_generation_manifest_pins_every_child_and_rejects_unknown_fields() -> None:
    chunk = _content_chunk()
    manifest = ChunkGeneration(
        chunk_generation_id="generation-1",
        source_version_ref="source-version-1",
        source_sha256=HASH,
        source_byte_length=5,
        chunker_id="pending",
        chunk_policy_version="policy-v1",
        chunk_schema_version="schema-v1",
        implementation_version="implementation-v1",
        chunks=[chunk],
        receipt_ref="receipt/generation-1",
        activity_ref="activity/generation-1",
        created_at=T1,
    )
    assert manifest.chunks == [chunk]
    with pytest.raises(ValidationError, match="implementation pins"):
        ChunkGeneration(**(manifest.model_dump() | {"implementation_version": "changed"}))
    with pytest.raises(ValidationError, match="Extra inputs"):
        _content_chunk(char_start=0)


def test_timeline_extraction_is_a_sibling_pass_and_reuses_exact_byte_locators() -> None:
    full_chunk_proof = ChunkCompletenessResult(
        status="pass",
        chunk_generation_id="chunk-generation-1",
        source_sha256=HASH,
        reassembled_sha256=HASH,
        source_byte_length=5,
        covered_byte_length=5,
        covered_ranges=[SourceByteRange(offset=0, length=5)],
        exact_range_coverage=True,
        chunk_count=1,
        chunk_manifest_sha256=HASH,
        locator_set_sha256=HASH,
        receipt_ref="receipt/chunk-proof",
        activity_ref="activity/chunk-proof",
    )
    event = TimelineEventCandidateProvenance(
        event_candidate_ref="timeline/event-candidate-1",
        extraction_generation_id="event-generation-1",
        source_version_ref="source-version-1",
        source_sha256=HASH,
        source_ranges=[SourceByteRange(offset=1, length=2)],
        extractor_id="timeline-extractor",
        extraction_policy_version="policy-v1",
        implementation_version="implementation-v1",
        receipt_ref="receipt/event-extraction",
        activity_ref="activity/event-extraction",
    )
    manifest = SourceDerivationManifest(
        source_version_ref="source-version-1",
        source_sha256=HASH,
        chunk_generation_ids=[full_chunk_proof.chunk_generation_id],
        timeline_extraction_generation_ids=[event.extraction_generation_id],
    )
    assert full_chunk_proof.covered_byte_length == 5
    assert event.source_ranges[0].end_offset == 3
    assert manifest.chunk_generation_ids != manifest.timeline_extraction_generation_ids


def test_intake_classification_is_context_only_and_evidence_is_not_a_chat_target() -> None:
    assert IngestRequest(staged_path="incoming/file.md").classification_target == "context"
    with pytest.raises(ValidationError):
        IngestRequest(staged_path="incoming/file.md", classification_target="evidence")
    with pytest.raises(ValidationError, match="evidence lane"):
        LaneClassification(lane="evidence", confidence=0.9, review_status="approved")


def test_legacy_non_context_lanes_are_rejected_fail_closed() -> None:
    for lane in ("evidence", "legal", "personal_history", "platform"):
        with pytest.raises(ValidationError):
            IngestRequest(staged_path="incoming/legacy.bin", lane=lane)


def test_ingest_receipt_additive_completeness_fields_fail_closed() -> None:
    base = {
        "receipt_id": "receipt-1",
        "status": "completed",
        "lane": "context",
        "matter_id": "primary",
        "source_name": "file.md",
        "source_path": "incoming/file.md",
        "chunker_id": "pending",
        "started_at": T1,
        "completed_at": T2,
    }
    assert IngestReceipt(**base).chunk_completeness_status == "not_run"
    with pytest.raises(ValidationError, match="requires completeness"):
        IngestReceipt(**(base | {"chunk_completeness_status": "pass"}))


def test_first_party_thread_is_owner_anchored_and_platform_hops_in_thread_order() -> None:
    representations = [_first_representation("screenshot-1"), _first_representation("export-1", "native_export")]
    messages = [
        FirstPartyMessageAnchor(
            message_anchor_id="message-a",
            platform="sms",
            platform_message_id="sms-10",
            thread_order=0,
            source_order=10,
            occurred_at=T1,
            source_representation_ids=["screenshot-1", "export-1"],
            timestamp_metadata_ref="metadata/raw/1",
            content_fingerprint=HASH,
            participants=[FirstPartyParticipant(party_id="owner", role="sender", is_case_owner=True)],
        ),
        FirstPartyMessageAnchor(
            message_anchor_id="message-b",
            platform="elator",
            platform_message_id="elator-2",
            thread_order=1,
            source_order=2,
            occurred_at=T2,
            source_representation_ids=["export-1"],
            timestamp_metadata_ref="metadata/raw/1",
            content_fingerprint=HASH,
            participants=[FirstPartyParticipant(party_id="katrina", role="sender")],
        ),
    ]
    thread_values = {
        "context_thread_id": "thread-stable-1",
        "thread_version": 1,
        "provenance_receipt_refs": ["receipt/thread-1"],
        "confidence": 0.85,
        "review_status": "approved",
        "first_occurred_at": T1,
        "last_occurred_at": T2,
        "owner_anchor": FirstPartyOwnerAnchor(
            owner_party_id="owner", authenticated_assertion_receipt_ref="receipt/owner-assertion"
        ),
        "messages": messages,
        "source_representations": representations,
    }
    with pytest.raises(ValidationError, match="greatest required message"):
        FirstPartyContextThread(
            **thread_values,
            source_available_from=T1,
            realizable_from=T1,
        )
    thread = FirstPartyContextThread(
        **thread_values,
        source_available_from=T2,
        realizable_from=T2,
    )
    assert [message.platform for message in thread.messages] == ["sms", "elator"]
    assert [message.source_order for message in thread.messages] == [10, 2]
    assert len(thread.source_representations) == 2
    assert thread.source_representations[0].source_sha256 == thread.source_representations[1].source_sha256


def test_third_party_thread_requires_acquisition_approval_and_never_invents_owner() -> None:
    representation = _third_representation("elator-export")
    message_values = {
        "message_anchor_id": "message-third",
        "platform": "elator",
        "thread_order": 0,
        "source_order": 0,
        "occurred_at": T1,
        "source_representation_ids": ["elator-export"],
        "timestamp_metadata_ref": "metadata/raw/1",
        "content_fingerprint": HASH,
    }
    with pytest.raises(ValidationError, match="case owner"):
        ThirdPartyMessageAnchor(
            **message_values,
            participants=[ThirdPartyParticipant(party_id="owner", role="recipient", is_case_owner=True)],
        )
    message = ThirdPartyMessageAnchor(
        **message_values,
        participants=[ThirdPartyParticipant(party_id="katrina", role="sender")],
    )
    thread = ThirdPartyContextThread(
        context_thread_id="thread-third-1",
        thread_version=1,
        provenance_receipt_refs=["receipt/thread-third"],
        confidence=0.7,
        review_status="approved",
        first_occurred_at=T1,
        last_occurred_at=T1,
        source_available_from=ACQUIRED,
        realizable_from=ACQUIRED,
        acquisition_anchor=ThirdPartyAcquisitionAnchor(
            representation_id="elator-export",
            acquired_at=ACQUIRED,
            acquisition_receipt_ref="receipt/acquisition/elator-export",
            source_principal="katrina-device",
        ),
        approval_anchor=ThirdPartyApprovalAnchor(
            approved_at=ACQUIRED,
            approved_by="owner",
            approval_receipt_ref="receipt/approval",
        ),
        messages=[message],
        source_representations=[representation],
    )
    assert isinstance(thread, ThirdPartyContextThread)
    assert not isinstance(thread, FirstPartyContextThread)


def test_third_party_screenshot_capture_never_backdates_source_availability() -> None:
    representation = _third_representation("screenshot-1", "screenshot")
    assert representation.metadata_captured_or_created_at == T2
    assert representation.acquired_at == ACQUIRED
    assert representation.acquisition_receipt_ref == "receipt/acquisition/screenshot-1"
    message = ThirdPartyMessageAnchor(
        message_anchor_id="message-third",
        platform="sms",
        thread_order=0,
        source_order=0,
        occurred_at=T1,
        source_representation_ids=["screenshot-1"],
        timestamp_metadata_ref="metadata/raw/1",
        content_fingerprint=HASH,
        participants=[ThirdPartyParticipant(party_id="katrina", role="sender")],
    )
    values = {
        "context_thread_id": "thread-third-screenshot",
        "thread_version": 1,
        "provenance_receipt_refs": ["receipt/thread-third"],
        "confidence": 0.7,
        "review_status": "approved",
        "first_occurred_at": T1,
        "last_occurred_at": T1,
        "realizable_from": ACQUIRED,
        "acquisition_anchor": ThirdPartyAcquisitionAnchor(
            representation_id="screenshot-1",
            acquired_at=ACQUIRED,
            acquisition_receipt_ref="receipt/acquisition/screenshot-1",
            source_principal="katrina-device",
        ),
        "approval_anchor": ThirdPartyApprovalAnchor(
            approved_at=ACQUIRED,
            approved_by="owner",
            approval_receipt_ref="receipt/approval",
        ),
        "messages": [message],
        "source_representations": [representation],
    }
    with pytest.raises(ValidationError, match="greatest required custody-backed"):
        ThirdPartyContextThread(**(values | {"source_available_from": T2}))
    assert ThirdPartyContextThread(**(values | {"source_available_from": ACQUIRED})).source_available_from == ACQUIRED


def test_missing_primary_timestamps_use_reviewed_relative_anchors_without_fabrication() -> None:
    first_relative = FirstPartyRelativeDateAnchor(
        anchor_id="relative-first-v2",
        anchor_version=2,
        supersedes_anchor_id="relative-first-v1",
        last_known_before=T1,
        first_known_after=T2,
        contextual_order_ref="sequence/owner-export/14",
        metadata_basis="adjacent timestamped messages",
        raw_metadata_ref="metadata/raw/relative-1",
        confidence=0.6,
        ambiguity_notes=["message has no timestamp"],
        review_status="needs_review",
    )
    first_message = FirstPartyMessageAnchor(
        message_anchor_id="undated-first",
        platform="sms",
        thread_order=0,
        source_order=14,
        occurred_at=None,
        relative_date_anchor_ref=first_relative.anchor_id,
        source_representation_ids=["screenshot-1"],
        timestamp_metadata_ref="metadata/raw/relative-1",
        content_fingerprint=HASH,
        participants=[FirstPartyParticipant(party_id="owner", role="sender", is_case_owner=True)],
    )
    first_thread = FirstPartyContextThread(
        context_thread_id="thread-undated-first",
        thread_version=1,
        provenance_receipt_refs=["receipt/thread-undated"],
        confidence=0.6,
        review_status="needs_review",
        relative_date_anchor_ref=first_relative.anchor_id,
        availability_relative_date_anchor_ref=first_relative.anchor_id,
        owner_anchor=FirstPartyOwnerAnchor(
            owner_party_id="owner", authenticated_assertion_receipt_ref="receipt/owner-assertion"
        ),
        messages=[first_message],
        source_representations=[_first_representation("screenshot-1")],
    )
    assert first_thread.first_occurred_at is None
    assert first_thread.source_available_from is None

    third_relative = ThirdPartyRelativeDateAnchor(
        anchor_id="relative-third-v1",
        anchor_version=1,
        contextual_order_ref="sequence/elator/5",
        metadata_basis="export order only",
        raw_metadata_ref="metadata/raw/relative-third",
        confidence=0.4,
        ambiguity_notes=["source message has no timestamp"],
        review_status="needs_review",
    )
    third_message = ThirdPartyMessageAnchor(
        message_anchor_id="undated-third",
        platform="elator",
        thread_order=0,
        source_order=5,
        occurred_at=None,
        relative_date_anchor_ref=third_relative.anchor_id,
        source_representation_ids=["elator-export"],
        timestamp_metadata_ref="metadata/raw/relative-third",
        content_fingerprint=HASH,
        participants=[ThirdPartyParticipant(party_id="katrina", role="sender")],
    )
    third_thread = ThirdPartyContextThread(
        context_thread_id="thread-undated-third",
        thread_version=1,
        provenance_receipt_refs=["receipt/thread-undated-third"],
        confidence=0.4,
        review_status="needs_review",
        occurrence_relative_date_anchor_ref=third_relative.anchor_id,
        source_available_from=ACQUIRED,
        realizable_from=ACQUIRED,
        acquisition_anchor=ThirdPartyAcquisitionAnchor(
            representation_id="elator-export",
            acquired_at=ACQUIRED,
            acquisition_receipt_ref="receipt/acquisition/elator-export",
            source_principal="katrina-device",
        ),
        approval_anchor=ThirdPartyApprovalAnchor(
            approved_at=ACQUIRED,
            approved_by="owner",
            approval_receipt_ref="receipt/approval",
        ),
        messages=[third_message],
        source_representations=[_third_representation("elator-export")],
    )
    assert third_thread.first_occurred_at is None
    assert third_thread.source_available_from == ACQUIRED


def test_relative_anchor_corrections_are_versioned_and_exact_time_is_not_combined_with_fallback() -> None:
    with pytest.raises(ValidationError, match="must identify"):
        FirstPartyRelativeDateAnchor(
            anchor_id="relative-v2",
            anchor_version=2,
            contextual_order_ref="sequence/1",
            metadata_basis="message order",
            raw_metadata_ref="metadata/raw/1",
            confidence=0.5,
            ambiguity_notes=["unknown day"],
            review_status="needs_review",
        )
    with pytest.raises(ValidationError, match="exactly one"):
        FirstPartyMessageAnchor(
            message_anchor_id="invalid-dual-clock",
            platform="sms",
            thread_order=0,
            source_order=0,
            occurred_at=T1,
            relative_date_anchor_ref="relative-v1",
            source_representation_ids=["screenshot-1"],
            timestamp_metadata_ref="metadata/raw/1",
            content_fingerprint=HASH,
            participants=[FirstPartyParticipant(party_id="owner", role="sender", is_case_owner=True)],
        )


def test_representation_missing_exact_metadata_uses_external_relative_anchor_ref() -> None:
    screenshot = FirstPartySourceRepresentation(
        representation_id="undated-screenshot",
        source_version_ref="source/undated-screenshot",
        representation_kind="screenshot",
        media_type="image/png",
        source_sha256=HASH,
        byte_length=5,
        immutable_receipt_ref="receipt/undated-screenshot",
        metadata=_metadata(),
        relative_date_anchor_ref="relative/screenshot-clock-v1",
    )
    export = ThirdPartySourceRepresentation(
        representation_id="undated-export",
        source_version_ref="source/undated-export",
        representation_kind="third_party_export",
        media_type="application/json",
        source_sha256=HASH,
        byte_length=5,
        immutable_receipt_ref="receipt/undated-export",
        metadata=_metadata(third_party=True),
        relative_date_anchor_ref="relative/export-clock-v1",
        acquisition_receipt_ref="receipt/acquisition/undated-export",
        acquisition_relative_date_anchor_ref="relative/acquisition-clock-v1",
    )
    assert screenshot.metadata_captured_or_created_at is None
    assert screenshot.relative_date_anchor_ref == "relative/screenshot-clock-v1"
    assert export.metadata_exported_at is None
    assert export.acquired_at is None
    assert export.acquisition_relative_date_anchor_ref == "relative/acquisition-clock-v1"


def test_third_party_representations_keep_distinct_custody_backed_acquisitions() -> None:
    later = ACQUIRED.replace(day=2)
    first = _third_representation("screenshot-first", "screenshot")
    second = _third_representation("export-later").model_copy(
        update={"acquired_at": later, "acquisition_receipt_ref": "receipt/acquisition/export-later"}
    )
    message = ThirdPartyMessageAnchor(
        message_anchor_id="message-multi-source",
        platform="elator",
        thread_order=0,
        source_order=0,
        occurred_at=T1,
        source_representation_ids=["screenshot-first", "export-later"],
        timestamp_metadata_ref="metadata/raw/1",
        content_fingerprint=HASH,
        participants=[ThirdPartyParticipant(party_id="katrina", role="sender")],
    )
    thread_values = {
        "context_thread_id": "thread-multi-source",
        "thread_version": 1,
        "provenance_receipt_refs": ["receipt/thread-multi-source"],
        "confidence": 0.8,
        "review_status": "approved",
        "first_occurred_at": T1,
        "last_occurred_at": T1,
        "acquisition_anchor": ThirdPartyAcquisitionAnchor(
            representation_id="screenshot-first",
            acquired_at=ACQUIRED,
            acquisition_receipt_ref="receipt/acquisition/screenshot-first",
            source_principal="katrina-device",
        ),
        "messages": [message],
        "source_representations": [first, second],
    }
    with pytest.raises(ValidationError, match="greatest required custody-backed"):
        ThirdPartyContextThread(
            **thread_values,
            source_available_from=ACQUIRED,
            realizable_from=ACQUIRED,
            approval_anchor=ThirdPartyApprovalAnchor(
                approved_at=later,
                approved_by="owner",
                approval_receipt_ref="receipt/approval",
            ),
        )
    thread = ThirdPartyContextThread(
        **thread_values,
        source_available_from=later,
        realizable_from=later,
        approval_anchor=ThirdPartyApprovalAnchor(
            approved_at=later,
            approved_by="owner",
            approval_receipt_ref="receipt/approval",
        ),
    )
    assert [item.acquired_at for item in thread.source_representations] == [ACQUIRED, later]
    assert len({item.acquisition_receipt_ref for item in thread.source_representations}) == 2


def test_relative_required_acquisition_withholds_exact_whole_thread_horizon() -> None:
    exact = _third_representation("exact-source")
    relative = ThirdPartySourceRepresentation(
        representation_id="relative-source",
        source_version_ref="source/relative-source",
        representation_kind="third_party_export",
        media_type="application/json",
        platform="elator",
        source_sha256=HASH,
        byte_length=5,
        immutable_receipt_ref="receipt/relative-source",
        metadata=_metadata(third_party=True),
        relative_date_anchor_ref="relative/export-clock",
        acquisition_receipt_ref="receipt/acquisition/relative-source",
        acquisition_relative_date_anchor_ref="relative/acquisition-clock",
    )
    message = ThirdPartyMessageAnchor(
        message_anchor_id="mixed-acquisition-message",
        platform="elator",
        thread_order=0,
        source_order=0,
        occurred_at=T1,
        source_representation_ids=["exact-source", "relative-source"],
        timestamp_metadata_ref="metadata/raw/1",
        content_fingerprint=HASH,
        participants=[ThirdPartyParticipant(party_id="katrina", role="sender")],
    )
    values = {
        "context_thread_id": "thread-mixed-acquisition",
        "thread_version": 1,
        "provenance_receipt_refs": ["receipt/thread-mixed-acquisition"],
        "confidence": 0.5,
        "review_status": "needs_review",
        "first_occurred_at": T1,
        "last_occurred_at": T1,
        "acquisition_anchor": ThirdPartyAcquisitionAnchor(
            representation_id="exact-source",
            acquired_at=ACQUIRED,
            acquisition_receipt_ref="receipt/acquisition/exact-source",
            source_principal="katrina-device",
        ),
        "approval_anchor": ThirdPartyApprovalAnchor(
            approved_at=ACQUIRED,
            approved_by="owner",
            approval_receipt_ref="receipt/approval",
        ),
        "messages": [message],
        "source_representations": [exact, relative],
    }
    with pytest.raises(ValidationError, match="prevents an exact"):
        ThirdPartyContextThread(
            **values,
            source_available_from=ACQUIRED,
            realizable_from=ACQUIRED,
            availability_relative_date_anchor_ref="relative/thread-availability",
        )
    thread = ThirdPartyContextThread(
        **values,
        availability_relative_date_anchor_ref="relative/thread-availability",
    )
    assert thread.source_available_from is None
    assert thread.realizable_from is None


def test_realization_membership_uses_greatest_required_message_clock() -> None:
    representations = [_first_representation("source-a"), _first_representation("source-b")]
    messages = [
        FirstPartyMessageAnchor(
            message_anchor_id="message-early",
            platform="sms",
            thread_order=0,
            source_order=0,
            occurred_at=T1,
            source_representation_ids=["source-a"],
            timestamp_metadata_ref="metadata/raw/1",
            content_fingerprint=HASH,
            participants=[FirstPartyParticipant(party_id="owner", role="sender", is_case_owner=True)],
        ),
        FirstPartyMessageAnchor(
            message_anchor_id="message-late",
            platform="elator",
            thread_order=1,
            source_order=0,
            occurred_at=T2,
            source_representation_ids=["source-b"],
            timestamp_metadata_ref="metadata/raw/2",
            content_fingerprint=HASH,
            participants=[FirstPartyParticipant(party_id="katrina", role="sender")],
        ),
    ]
    link_values = {
        "realization_id": "realization-1",
        "realized_at": T2,
        "reviewed_by": "owner",
        "review_receipt_ref": "receipt/realization-1",
        "required_message_anchor_ids": ["message-early", "message-late"],
        "required_source_representation_ids": ["source-a", "source-b"],
    }
    thread_values = {
        "context_thread_id": "thread-realization",
        "thread_version": 1,
        "provenance_receipt_refs": ["receipt/thread-realization"],
        "confidence": 0.8,
        "review_status": "approved",
        "first_occurred_at": T1,
        "last_occurred_at": T2,
        "source_available_from": T2,
        "realizable_from": T2,
        "owner_anchor": FirstPartyOwnerAnchor(
            owner_party_id="owner", authenticated_assertion_receipt_ref="receipt/owner-assertion"
        ),
        "messages": messages,
        "source_representations": representations,
    }
    with pytest.raises(ValidationError, match="greatest required message clock"):
        FirstPartyContextThread(
            **thread_values,
            realization_links=[ReviewedRealizationLink(**link_values, required_source_available_from=T1)],
        )
    thread = FirstPartyContextThread(
        **thread_values,
        realization_links=[ReviewedRealizationLink(**link_values, required_source_available_from=T2)],
    )
    assert thread.realization_links[0].required_source_available_from == T2


def test_event_candidate_relative_time_link_is_external_typed_and_versioned() -> None:
    link = EventCandidateRelativeTimeAnchorLink(
        link_id="event-time-link-v2",
        link_version=2,
        supersedes_link_id="event-time-link-v1",
        event_candidate_ref="timeline/event-candidate-1",
        relative_date_anchor_ref="relative/event-clock-v2",
        temporal_role="occurred_at",
        review_status="approved",
        receipt_ref="receipt/event-time-link-v2",
        created_at=T2,
    )
    assert link.relative_date_anchor_ref == "relative/event-clock-v2"
    assert "relative_date_anchor" not in EventCandidateRelativeTimeAnchorLink.model_fields
    with pytest.raises(ValidationError, match="must identify"):
        EventCandidateRelativeTimeAnchorLink(**(link.model_dump() | {"supersedes_link_id": None}))


def test_conflict_review_plane_is_append_only_typed_and_non_merging() -> None:
    review_case = ConflictReviewCase(
        review_case_id="review/source-equivalence-v1",
        case_version=1,
        conflict_kind="first_party_source_representation_equivalence",
        status="queued",
        provenance_refs=["receipt/conflict-detection"],
        created_at=T1,
    )
    queue_event = ConflictReviewQueueEvent(
        queue_event_id="queue-event-1",
        review_case_ref=review_case.review_case_id,
        action="enqueue",
        queue_name="source-equivalence",
        actor_ref="system/conflict-detector",
        occurred_at=T1,
        provenance_ref="receipt/queue-event-1",
    )
    typed_link = FirstPartySourceRepresentationEquivalenceConflictReviewLink(
        link_id="conflict-link-1",
        link_version=1,
        review_case_ref=review_case.review_case_id,
        receipt_ref="receipt/conflict-link-1",
        created_at=T1,
        left_first_party_representation_ref="representation/screenshot-1",
        right_first_party_representation_ref="representation/export-1",
    )
    decision = ConflictAdjudicationDecision(
        decision_id="decision-1",
        decision_version=1,
        review_case_ref=review_case.review_case_id,
        typed_conflict_link_ref=typed_link.link_id,
        disposition="coexist",
        accepted_side="both",
        reviewer_ref="owner",
        rationale="Both immutable representations independently corroborate the source thread.",
        provenance_refs=[queue_event.provenance_ref, typed_link.receipt_ref],
        decided_at=T2,
    )
    assert decision.disposition == "coexist"
    assert "merged_assertion_ref" not in ConflictAdjudicationDecision.model_fields
    assert "accepted_assertion_refs" not in ConflictAdjudicationDecision.model_fields
    with pytest.raises(ValidationError, match="distinct"):
        FirstPartySourceRepresentationEquivalenceConflictReviewLink(
            **(
                typed_link.model_dump()
                | {"right_first_party_representation_ref": typed_link.left_first_party_representation_ref}
            )
        )


def test_conflict_review_orchestration_is_reference_only_and_preserves_authority_boundaries() -> None:
    workflow = ConflictReviewWorkflowReference(
        workflow_id="conflict-review/review-1",
        run_id="temporal-run-1",
        review_case_ref="review-1",
        expected_review_case_version=3,
        idempotency_key="review-1:v3",
        escalation_policy_ref="policy/escalation-v1",
        reminder_policy_ref="policy/reminder-v1",
    )
    dispatch = ConflictReviewDispatchReceipt(
        workflow_id=workflow.workflow_id,
        run_id=workflow.run_id,
        review_case_ref=workflow.review_case_ref,
        expected_review_case_version=workflow.expected_review_case_version,
        idempotency_key="review-1:v3:dispatch",
        implementation_ref="review-implementation/current",
        dispatch_receipt_ref="receipt/n8n-dispatch-1",
        dispatched_at=T1,
    )
    signal = ConflictReviewDecisionSignal(
        workflow_id=workflow.workflow_id,
        run_id=workflow.run_id,
        review_case_ref=workflow.review_case_ref,
        expected_review_case_version=workflow.expected_review_case_version,
        decision_ref="decision-1",
        authenticated_reviewer_ref="owner",
        authentication_receipt_ref="receipt/auth-1",
        decision_signal_receipt_ref="receipt/signal-1",
        idempotency_key="review-1:v3:signal:decision-1",
        signaled_at=T2,
    )
    activity = ConflictReviewActivityRequest(
        activity_kind="persist",
        workflow_id=workflow.workflow_id,
        run_id=workflow.run_id,
        review_case_ref=workflow.review_case_ref,
        expected_review_case_version=workflow.expected_review_case_version,
        input_ref=signal.decision_ref,
        idempotency_key="review-1:v3:persist:decision-1",
    )
    terminal = ConflictReviewTerminalReconciliation(
        workflow_id=workflow.workflow_id,
        run_id=workflow.run_id,
        review_case_ref=workflow.review_case_ref,
        reconciled_review_case_version=3,
        decision_ref=signal.decision_ref,
        decision_signal_receipt_ref=signal.decision_signal_receipt_ref,
        persistence_receipt_ref="receipt/pg-persist-1",
        reprojection_receipt_refs=["receipt/reproject-1"],
        status="reconciled",
        reconciled_at=T2,
    )
    assert workflow.canonical_authority == "postgresql"
    assert workflow.durable_orchestrator == "temporal"
    assert dispatch.dispatch_adapter == "n8n"
    assert dispatch.approval_authority == "none"
    assert activity.input_ref == "decision-1"
    assert terminal.canonical_authority == "postgresql"
    for contract in (workflow, dispatch, signal, activity, terminal):
        assert not any("payload" in field_name for field_name in type(contract).model_fields)


def test_chunk_ranges_and_generation_proof_are_bound_fail_closed() -> None:
    with pytest.raises(ValidationError, match="byte-range length"):
        _content_chunk(source_ranges=[SourceByteRange(offset=0, length=4)])
    with pytest.raises(ValidationError, match="ordered and nonoverlapping"):
        _content_chunk(
            derivation_mode="composed",
            source_ranges=[SourceByteRange(offset=2, length=3), SourceByteRange(offset=1, length=1)],
        )
    with pytest.raises(ValidationError, match="exceeds"):
        _content_chunk(source_ranges=[SourceByteRange(offset=2, length=5)])

    chunk = _content_chunk()
    generation = ChunkGeneration(
        chunk_generation_id="generation-1",
        source_version_ref="source-version-1",
        source_sha256=HASH,
        source_byte_length=5,
        chunker_id="pending",
        chunk_policy_version="policy-v1",
        chunk_schema_version="schema-v1",
        implementation_version="implementation-v1",
        chunks=[chunk],
        receipt_ref="receipt/generation",
        activity_ref="activity/generation",
        created_at=T1,
    )
    proof = ChunkCompletenessResult(
        status="pass",
        chunk_generation_id=generation.chunk_generation_id,
        source_sha256=HASH,
        reassembled_sha256=HASH,
        source_byte_length=5,
        covered_byte_length=5,
        covered_ranges=chunk.source_ranges,
        exact_range_coverage=True,
        chunk_count=1,
        chunk_manifest_sha256=generation.chunk_manifest_sha256,
        locator_set_sha256=generation.locator_set_sha256,
        receipt_ref="receipt/completeness",
        activity_ref="activity/completeness",
    )
    assert ChunkGenerationCompletenessBinding(generation=generation, completeness=proof)
    with pytest.raises(ValidationError, match="actual generation"):
        ChunkGenerationCompletenessBinding(
            generation=generation,
            completeness=proof.model_copy(update={"locator_set_sha256": "0" * 64}),
        )


def test_completed_chunked_ingest_requires_matching_passing_proof() -> None:
    proof = ChunkCompletenessResult(
        status="pass",
        chunk_generation_id="generation-1",
        source_sha256=HASH,
        reassembled_sha256=HASH,
        source_byte_length=5,
        covered_byte_length=5,
        covered_ranges=[SourceByteRange(offset=0, length=5)],
        exact_range_coverage=True,
        chunk_count=1,
        chunk_manifest_sha256=HASH,
        locator_set_sha256=HASH,
        receipt_ref="receipt/completeness",
        activity_ref="activity/completeness",
    )
    base = {
        "receipt_id": "receipt-chunked",
        "status": "completed",
        "lane": "context",
        "matter_id": "primary",
        "source_name": "file.md",
        "source_path": "incoming/file.md",
        "source_sha256": HASH,
        "chunker_id": "pending",
        "chunk_generation_id": "generation-1",
        "chunk_count": 1,
        "started_at": T1,
        "completed_at": T2,
    }
    with pytest.raises(ValidationError, match="requires passing"):
        IngestReceipt(**base)
    receipt = IngestReceipt(
        **base,
        chunk_completeness_status="pass",
        chunk_completeness_result=proof,
        chunk_completeness_receipt_id=proof.receipt_ref,
        chunk_manifest_sha256=proof.chunk_manifest_sha256,
        chunk_locator_set_sha256=proof.locator_set_sha256,
    )
    assert receipt.chunk_completeness_status == "pass"


def test_whole_thread_members_cannot_opt_out_of_horizon() -> None:
    with pytest.raises(ValidationError):
        FirstPartyMessageAnchor(
            message_anchor_id="message-opt-out",
            platform="sms",
            thread_order=0,
            source_order=0,
            occurred_at=T1,
            source_representation_ids=["source-1"],
            timestamp_metadata_ref="metadata/raw/1",
            content_fingerprint=HASH,
            required_for_horizon=False,
            participants=[FirstPartyParticipant(party_id="owner", role="sender", is_case_owner=True)],
        )
    with pytest.raises(ValidationError):
        existing = _third_representation("source-opt-out")
        ThirdPartySourceRepresentation(**(existing.model_dump() | {"required_for_horizon": False}))


def test_third_party_realization_message_requires_all_backing_sources() -> None:
    later = ACQUIRED.replace(day=2)
    first = _third_representation("source-first")
    second = _third_representation("source-second").model_copy(update={"acquired_at": later})
    message = ThirdPartyMessageAnchor(
        message_anchor_id="message-backed-twice",
        platform="elator",
        thread_order=0,
        source_order=0,
        occurred_at=T1,
        source_representation_ids=["source-first", "source-second"],
        timestamp_metadata_ref="metadata/raw/1",
        content_fingerprint=HASH,
        participants=[ThirdPartyParticipant(party_id="katrina", role="sender")],
    )
    link = ReviewedRealizationLink(
        realization_id="realization-third",
        realized_at=later,
        reviewed_by="owner",
        review_receipt_ref="receipt/realization-third",
        required_message_anchor_ids=[message.message_anchor_id],
        required_source_representation_ids=[first.representation_id],
        required_source_available_from=ACQUIRED,
    )
    with pytest.raises(ValidationError, match="backing source representations"):
        ThirdPartyContextThread(
            context_thread_id="thread-realization-third",
            thread_version=1,
            provenance_receipt_refs=["receipt/thread"],
            confidence=0.7,
            review_status="approved",
            first_occurred_at=T1,
            last_occurred_at=T1,
            source_available_from=later,
            realizable_from=later,
            acquisition_anchor=ThirdPartyAcquisitionAnchor(
                representation_id=first.representation_id,
                acquired_at=ACQUIRED,
                acquisition_receipt_ref=first.acquisition_receipt_ref,
                source_principal="katrina-device",
            ),
            approval_anchor=ThirdPartyApprovalAnchor(
                approved_at=later,
                approved_by="owner",
                approval_receipt_ref="receipt/approval",
            ),
            messages=[message],
            source_representations=[first, second],
            realization_links=[link],
        )


def test_source_clocks_are_aware_other_has_fallback_and_acquisition_anchor_is_bound() -> None:
    naive = datetime(2025, 1, 1)
    with pytest.raises(ValidationError, match="timezone"):
        FirstPartyMessageAnchor(
            message_anchor_id="naive-message",
            platform="sms",
            thread_order=0,
            source_order=0,
            occurred_at=naive,
            source_representation_ids=["source-1"],
            timestamp_metadata_ref="metadata/raw/1",
            content_fingerprint=HASH,
            participants=[FirstPartyParticipant(party_id="owner", role="sender", is_case_owner=True)],
        )
    with pytest.raises(ValidationError, match="exact metadata clock"):
        FirstPartySourceRepresentation(
            representation_id="other-undated",
            source_version_ref="source/other",
            representation_kind="other",
            media_type="application/octet-stream",
            source_sha256=HASH,
            byte_length=5,
            immutable_receipt_ref="receipt/other",
            metadata=_metadata(),
        )
    other = FirstPartySourceRepresentation(
        representation_id="other-relative",
        source_version_ref="source/other-relative",
        representation_kind="other",
        media_type="application/octet-stream",
        source_sha256=HASH,
        byte_length=5,
        immutable_receipt_ref="receipt/other-relative",
        metadata=_metadata(),
        relative_date_anchor_ref="relative/other",
    )
    assert other.observed_metadata_at is None
    assert "metadata_acquired_at" not in FirstPartySourceRepresentation.model_fields

    representation = _third_representation("anchor-source")
    message = ThirdPartyMessageAnchor(
        message_anchor_id="anchor-message",
        platform="elator",
        thread_order=0,
        source_order=0,
        occurred_at=T1,
        source_representation_ids=[representation.representation_id],
        timestamp_metadata_ref="metadata/raw/1",
        content_fingerprint=HASH,
        participants=[ThirdPartyParticipant(party_id="katrina", role="sender")],
    )
    with pytest.raises(ValidationError, match="must match its representation"):
        ThirdPartyContextThread(
            context_thread_id="thread-bad-anchor",
            thread_version=1,
            provenance_receipt_refs=["receipt/thread"],
            confidence=0.5,
            review_status="approved",
            first_occurred_at=T1,
            last_occurred_at=T1,
            source_available_from=ACQUIRED,
            realizable_from=ACQUIRED,
            acquisition_anchor=ThirdPartyAcquisitionAnchor(
                representation_id=representation.representation_id,
                acquired_at=ACQUIRED,
                acquisition_receipt_ref="receipt/wrong",
                source_principal="katrina-device",
            ),
            approval_anchor=ThirdPartyApprovalAnchor(
                approved_at=ACQUIRED,
                approved_by="owner",
                approval_receipt_ref="receipt/approval",
            ),
            messages=[message],
            source_representations=[representation],
        )
