"""Native Weaviate schema and horizon-prefilter contract tests.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from weaviate.classes.config import DataType, Tokenization

from server.core.evidence_vector_store import (
    EVIDENCE_EMBED_DIM,
    EVIDENCE_EMBED_MODEL,
    EVIDENCE_PROJECTION_VERSION,
    EVIDENCE_VECTOR_COLLECTION,
    EvidenceVectorDocument,
    NativeEvidenceVectorStore,
    ensure_evidence_vector_collection,
    evidence_vector_properties,
    validate_evidence_vector_activation,
)

VECTOR = [0.1] * EVIDENCE_EMBED_DIM
CHUNK_ID = "11111111-1111-1111-1111-111111111111"
ARTIFACT_ID = "22222222-2222-2222-2222-222222222222"
RECORD_ID = "33333333-3333-3333-3333-333333333333"


def test_schema_has_typed_range_indexed_horizon_fields() -> None:
    properties = {prop.name: prop for prop in evidence_vector_properties()}

    assert properties["source_available_from"].dataType is DataType.DATE
    assert properties["source_available_from"].indexRangeFilters is True
    assert properties["source_available_from_epoch"].dataType is DataType.INT
    assert properties["source_available_from_epoch"].indexRangeFilters is True
    assert properties["occurred_at"].dataType is DataType.DATE
    assert properties["chunk_id"].dataType is DataType.UUID
    assert properties["artifact_id"].dataType is DataType.UUID
    assert properties["normalized_record_id"].dataType is DataType.UUID
    assert properties["case_id"].tokenization is Tokenization.FIELD
    assert properties["content_hash"].tokenization is Tokenization.FIELD
    assert {
        "case_id",
        "disclosure_tier",
        "source_kind",
        "projection_kind",
        "authority_state",
        "artifact_id",
        "source_sha256",
        "normalized_record_id",
        "conversation_id",
        "content_hash",
        "content",
    }.issubset(properties)


def test_collection_creation_is_versioned_and_idempotent() -> None:
    client = MagicMock()
    client.collections.exists.side_effect = [False, True]
    client.collections.get.return_value.config.get.return_value = SimpleNamespace(
        name=EVIDENCE_VECTOR_COLLECTION,
        vector_config={"default": SimpleNamespace(vectorizer=SimpleNamespace(vectorizer="none"))},
        properties=evidence_vector_properties(),
    )

    assert ensure_evidence_vector_collection(client) is True
    assert ensure_evidence_vector_collection(client) is False
    assert client.collections.create.call_count == 1
    kwargs = client.collections.create.call_args.kwargs
    assert kwargs["name"] == EVIDENCE_VECTOR_COLLECTION == "EvidenceChunkV1"


def test_existing_schema_and_reader_alias_must_reconcile_exactly() -> None:
    client = MagicMock()
    client.collections.get.return_value.config.get.return_value = SimpleNamespace(
        name=EVIDENCE_VECTOR_COLLECTION,
        vector_config={"default": SimpleNamespace(vectorizer=SimpleNamespace(vectorizer="none"))},
        properties=evidence_vector_properties(),
    )
    client.alias.get.return_value = SimpleNamespace(collection=EVIDENCE_VECTOR_COLLECTION)
    validate_evidence_vector_activation(client)

    client.alias.get.return_value = SimpleNamespace(collection="EvidenceChunkV0")
    with pytest.raises(RuntimeError, match="not reconciled"):
        validate_evidence_vector_activation(client)


def test_document_emits_date_and_epoch_without_realization_clock() -> None:
    acquired = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)
    doc = EvidenceVectorDocument(
        chunk_id=CHUNK_ID,
        artifact_id=ARTIFACT_ID,
        source_sha256="abc123",
        case_id="primary",
        disclosure_tier="discovered",
        source_kind="acquired_third_party",
        projection_kind="third_party_message",
        authority_state="active",
        source_available_from=acquired,
        occurred_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        normalized_record_id=RECORD_ID,
        chunker_id="recursive@1",
        embed_model=EVIDENCE_EMBED_MODEL,
        embed_dimension=EVIDENCE_EMBED_DIM,
        embedder_version="nv-embed-v1@nim",
        projection_version=EVIDENCE_PROJECTION_VERSION,
        projection_hash="projection-hash",
        conversation_id="conversation-1",
        content_hash="sha256:abc",
        source_content_hash="sha256:def",
        content="message",
        vector=VECTOR,
    )

    props = doc.properties()
    assert props["source_available_from"] == acquired
    assert props["source_available_from_epoch"] == int(acquired.timestamp())
    assert "realized_at" not in props


def test_near_vector_combines_horizon_and_scope_before_ranking() -> None:
    query = MagicMock()
    collection = SimpleNamespace(query=query)
    client = MagicMock()
    client.collections.use.return_value = collection
    store = NativeEvidenceVectorStore(client)
    horizon = datetime(2024, 7, 1, tzinfo=timezone.utc)

    store.search(
        vector=VECTOR,
        horizon=horizon,
        case_id="case-7",
        disclosure_tiers=["contemporaneous", "discovered"],
        source_kinds=["first_party", "acquired_third_party"],
    )

    kwargs = query.near_vector.call_args.kwargs
    assert kwargs["near_vector"] == VECTOR
    filters = kwargs["filters"].filters
    assert filters[0].target == "case_id" and filters[0].value == "case-7"
    assert filters[1].target == "source_availability_complete" and filters[1].value is True
    assert filters[2].target == "authority_state" and filters[2].value == "active"
    assert filters[3].target == "source_available_from" and filters[3].value == horizon
    assert filters[3].operator.value == "LessThanEqual"


def test_hybrid_uses_same_prefilter_and_requires_query() -> None:
    query_api = MagicMock()
    client = MagicMock()
    client.collections.use.return_value = SimpleNamespace(query=query_api)
    store = NativeEvidenceVectorStore(client)
    horizon = datetime(2024, 7, 1, tzinfo=timezone.utc)

    store.search(
        vector=VECTOR,
        query="gaslighting",
        mode="hybrid",
        horizon=horizon,
        case_id="primary",
        disclosure_tiers=["contemporaneous"],
    )

    assert query_api.hybrid.call_args.kwargs["filters"].filters[3].target == "source_available_from"
    with pytest.raises(ValueError, match="query text"):
        store.search(
            vector=VECTOR,
            mode="hybrid",
            horizon=horizon,
            case_id="primary",
            disclosure_tiers=["contemporaneous"],
        )


def test_naive_horizon_fails_closed() -> None:
    client = MagicMock()
    client.collections.use.return_value = SimpleNamespace(query=MagicMock())
    store = NativeEvidenceVectorStore(client)

    with pytest.raises(ValueError, match="timezone-aware"):
        store.search(
            vector=VECTOR,
            horizon=datetime(2024, 7, 1),
            case_id="primary",
            disclosure_tiers=["contemporaneous"],
        )


def test_replace_uses_explicit_replace_branch_and_postcondition() -> None:
    data = MagicMock()
    data.exists.side_effect = [True, True]
    client = MagicMock()
    client.collections.use.return_value = SimpleNamespace(data=data)
    store = NativeEvidenceVectorStore(client)
    document = EvidenceVectorDocument(
        chunk_id=CHUNK_ID,
        artifact_id=ARTIFACT_ID,
        source_sha256="abc123",
        case_id="primary",
        disclosure_tier="contemporaneous",
        source_kind="first_party",
        projection_kind="first_party",
        authority_state="active",
        source_available_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        normalized_record_id=RECORD_ID,
        chunker_id="recursive@1",
        embed_model=EVIDENCE_EMBED_MODEL,
        embed_dimension=EVIDENCE_EMBED_DIM,
        embedder_version="nv-embed-v1@nim",
        projection_version=EVIDENCE_PROJECTION_VERSION,
        projection_hash="projection-hash",
        content_hash="abc",
        source_content_hash="def",
        content="message",
        vector=VECTOR,
    )

    store.replace(document)

    data.replace.assert_called_once()
    data.insert.assert_not_called()


def test_structured_retry_lookup_filters_artifact_and_content_hash() -> None:
    query = MagicMock()
    client = MagicMock()
    client.collections.use.return_value = SimpleNamespace(query=query)
    store = NativeEvidenceVectorStore(client)

    store.find_projection(artifact_id=ARTIFACT_ID, content_hash="content-hash")

    filters = query.fetch_objects.call_args.kwargs["filters"].filters
    assert filters[0].target == "artifact_id" and filters[0].value == UUID(ARTIFACT_ID)
    assert filters[1].target == "content_hash" and filters[1].value == "content-hash"


def test_unbounded_hindsight_requires_full_server_granted_tier_set() -> None:
    query = MagicMock()
    client = MagicMock()
    client.collections.use.return_value = SimpleNamespace(query=query)
    store = NativeEvidenceVectorStore(client)

    with pytest.raises(ValueError, match="complete permission-derived"):
        store.search(vector=VECTOR, horizon=None, case_id="primary", disclosure_tiers=["hindsight"])
    store.search(
        vector=VECTOR,
        horizon=None,
        case_id="primary",
        disclosure_tiers=["contemporaneous", "discovered", "hindsight"],
    )
    assert all(
        getattr(item, "target", None) != "source_available_from"
        for item in query.near_vector.call_args.kwargs["filters"].filters
    )
