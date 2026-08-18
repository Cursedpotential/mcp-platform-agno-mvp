"""Native Weaviate evidence-vector boundary.

This module deliberately does not import Agno.  Evidence-horizon predicates are
typed Weaviate properties and are supplied to ``near_vector``/``hybrid`` as a
single compound filter, so Weaviate builds the eligible allow-list *before*
ranking.  The old ``Platform_knowledge`` collection remains untouched.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Sequence
from uuid import UUID

from weaviate.classes.config import Configure, DataType, Property, Tokenization
from weaviate.classes.query import Filter, MetadataQuery

EVIDENCE_VECTOR_COLLECTION_VERSION = 1
EVIDENCE_VECTOR_COLLECTION = f"EvidenceChunkV{EVIDENCE_VECTOR_COLLECTION_VERSION}"
EVIDENCE_VECTOR_ALIAS = "EvidenceChunks"
EVIDENCE_EMBED_MODEL = "nvidia/nv-embed-v1"
EVIDENCE_EMBED_DIM = 4096
EVIDENCE_PROJECTION_VERSION = "evidence-vector@1"

DisclosureTier = Literal["contemporaneous", "discovered", "hindsight"]
SearchMode = Literal["near_vector", "hybrid"]

_RETURN_PROPERTIES = [
    "chunk_id",
    "artifact_id",
    "source_sha256",
    "case_id",
    "disclosure_tier",
    "source_kind",
    "projection_kind",
    "authority_state",
    "occurred_at",
    "source_available_from",
    "source_available_from_epoch",
    "normalized_record_id",
    "conversation_id",
    "chunker_id",
    "embed_model",
    "embed_dimension",
    "embedder_version",
    "projection_version",
    "projection_hash",
    "content_hash",
    "source_content_hash",
    "content",
]


@dataclass(frozen=True, slots=True)
class EvidenceVectorDocument:
    """One derived, horizon-safe evidence chunk and its supplied vector."""

    chunk_id: str
    artifact_id: str
    source_sha256: str
    case_id: str
    disclosure_tier: DisclosureTier
    source_kind: str
    projection_kind: str
    authority_state: Literal["active", "revoked", "superseded"]
    source_available_from: datetime
    normalized_record_id: str
    chunker_id: str
    embed_model: str
    embed_dimension: int
    embedder_version: str
    projection_version: str
    projection_hash: str
    content_hash: str
    source_content_hash: str
    content: str
    vector: Sequence[float]
    occurred_at: datetime | None = None
    conversation_id: str | None = None

    def properties(self) -> dict[str, Any]:
        available = _utc(self.source_available_from, field="source_available_from")
        if not self.vector:
            raise ValueError("vector must not be empty")
        if not self.content_hash:
            raise ValueError("content_hash must not be empty")
        if self.embed_model != EVIDENCE_EMBED_MODEL:
            raise ValueError(f"embed_model must be {EVIDENCE_EMBED_MODEL}")
        if self.embed_dimension != EVIDENCE_EMBED_DIM or len(self.vector) != EVIDENCE_EMBED_DIM:
            raise ValueError(f"evidence vectors must have exactly {EVIDENCE_EMBED_DIM} dimensions")
        values: dict[str, Any] = {
            "chunk_id": UUID(self.chunk_id),
            "artifact_id": UUID(self.artifact_id),
            "source_sha256": self.source_sha256,
            "case_id": self.case_id,
            "disclosure_tier": self.disclosure_tier,
            "source_kind": self.source_kind,
            "projection_kind": self.projection_kind,
            "authority_state": self.authority_state,
            "source_availability_complete": True,
            "source_available_from": available,
            "source_available_from_epoch": int(available.timestamp()),
            "normalized_record_id": UUID(self.normalized_record_id),
            "chunker_id": self.chunker_id,
            "embed_model": self.embed_model,
            "embed_dimension": self.embed_dimension,
            "embedder_version": self.embedder_version,
            "projection_version": self.projection_version,
            "projection_hash": self.projection_hash,
            "content_hash": self.content_hash,
            "source_content_hash": self.source_content_hash,
            "content": self.content,
        }
        if self.occurred_at is not None:
            values["occurred_at"] = _utc(self.occurred_at, field="occurred_at")
        if self.conversation_id is not None:
            values["conversation_id"] = self.conversation_id
        return values


def _utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def evidence_vector_properties() -> list[Property]:
    """Return the immutable V1 schema property contract."""

    def filterable_text(name: str, *, description: str | None = None) -> Property:
        return Property(
            name=name,
            description=description,
            data_type=DataType.TEXT,
            index_filterable=True,
            tokenization=Tokenization.FIELD,
        )

    return [
        Property(
            name="chunk_id",
            description="Stable derived chunk id",
            data_type=DataType.UUID,
            index_filterable=True,
        ),
        Property(
            name="artifact_id",
            description="Structured custody artifact lookup",
            data_type=DataType.UUID,
            index_filterable=True,
        ),
        filterable_text("source_sha256", description="Custody H1 SHA-256 digest"),
        filterable_text("case_id", description="Mandatory case isolation key"),
        filterable_text("disclosure_tier"),
        filterable_text("source_kind"),
        filterable_text("projection_kind"),
        filterable_text("authority_state"),
        Property(name="source_availability_complete", data_type=DataType.BOOL, index_filterable=True),
        Property(name="occurred_at", data_type=DataType.DATE, index_filterable=True, index_range_filters=True),
        Property(
            name="source_available_from",
            description="Canonical raw-source horizon boundary (ADR-0059)",
            data_type=DataType.DATE,
            index_filterable=True,
            index_range_filters=True,
        ),
        Property(
            name="source_available_from_epoch",
            data_type=DataType.INT,
            index_filterable=True,
            index_range_filters=True,
        ),
        Property(name="normalized_record_id", data_type=DataType.UUID, index_filterable=True),
        filterable_text("conversation_id"),
        filterable_text("chunker_id"),
        filterable_text("embed_model"),
        Property(name="embed_dimension", data_type=DataType.INT, index_filterable=True),
        filterable_text("embedder_version"),
        filterable_text("projection_version"),
        filterable_text("projection_hash"),
        filterable_text("content_hash"),
        filterable_text("source_content_hash"),
        Property(name="content", data_type=DataType.TEXT, index_searchable=True),
    ]


def ensure_evidence_vector_collection(client: Any) -> bool:
    """Create V1 if absent; never alter, delete, alias, or contact another collection.

    Returns ``True`` only when this call created the versioned collection.  A
    future incompatible schema gets a new ``EvidenceChunkV<N>`` constant and
    is backfilled before an operator separately switches the stable alias.
    """

    if client.collections.exists(EVIDENCE_VECTOR_COLLECTION):
        validate_evidence_vector_collection(client)
        return False
    client.collections.create(
        name=EVIDENCE_VECTOR_COLLECTION,
        description="Derived evidence chunks with pre-ranking knowledge-horizon fields",
        vector_config=Configure.Vectors.self_provided(),
        properties=evidence_vector_properties(),
    )
    return True


def validate_evidence_vector_collection(client: Any) -> None:
    """Fail closed when an existing V1 collection differs from its contract."""

    config = client.collections.get(EVIDENCE_VECTOR_COLLECTION).config.get()
    if _field(config, "name") != EVIDENCE_VECTOR_COLLECTION:
        raise RuntimeError(f"native evidence collection name mismatch: {_field(config, 'name')!r}")
    vector_config = _field(config, "vector_config")
    if not isinstance(vector_config, dict) or set(vector_config) != {"default"}:
        raise RuntimeError("EvidenceChunkV1 must define exactly the V1 default vector configuration")
    vectorizer = _field(vector_config["default"], "vectorizer")
    if _config_value(_field(vectorizer, "vectorizer")) != "none":
        raise RuntimeError("EvidenceChunkV1 must use self-provided vectors (vectorizer=none)")
    actual = {prop.name: prop for prop in config.properties}
    expected = {prop.name: prop for prop in evidence_vector_properties()}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise RuntimeError(f"{EVIDENCE_VECTOR_COLLECTION} schema property mismatch: missing={missing}, extra={extra}")
    for name, wanted in expected.items():
        got = actual[name]
        checks = {
            "data type": (_field(got, "dataType", "data_type"), _field(wanted, "dataType", "data_type")),
            "filterable": (
                _field(got, "indexFilterable", "index_filterable"),
                _field(wanted, "indexFilterable", "index_filterable"),
            ),
            "searchable": (
                _field(got, "indexSearchable", "index_searchable"),
                _field(wanted, "indexSearchable", "index_searchable"),
            ),
            "range filters": (
                _field(got, "indexRangeFilters", "index_range_filters"),
                _field(wanted, "indexRangeFilters", "index_range_filters"),
            ),
            "tokenization": (_field(got, "tokenization"), _field(wanted, "tokenization")),
        }
        for label, (found, required) in checks.items():
            if required is None:
                continue
            if _config_value(found) != _config_value(required):
                raise RuntimeError(
                    f"{EVIDENCE_VECTOR_COLLECTION}.{name} {label} mismatch: "
                    f"found={_config_value(found)!r}, required={_config_value(required)!r}"
                )


def validate_evidence_vector_activation(client: Any) -> None:
    """Require the stable reader alias to point at the validated V1 collection."""

    validate_evidence_vector_collection(client)
    alias = client.alias.get(alias_name=EVIDENCE_VECTOR_ALIAS)
    if alias is None or alias.collection != EVIDENCE_VECTOR_COLLECTION:
        target = None if alias is None else alias.collection
        raise RuntimeError(
            f"native evidence activation is not reconciled: {EVIDENCE_VECTOR_ALIAS} targets {target!r}, "
            f"expected {EVIDENCE_VECTOR_COLLECTION!r}"
        )


def _field(value: Any, *names: str) -> Any:
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _config_value(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_config_value(item) for item in value)
    return getattr(value, "value", value)


class NativeEvidenceVectorStore:
    """Small native client over a versioned collection or activated alias."""

    def __init__(self, client: Any, *, collection: str = EVIDENCE_VECTOR_ALIAS) -> None:
        self._collection = client.collections.use(collection)

    @staticmethod
    def object_uuid(chunk_id: str) -> Any:
        """Return the deterministic Weaviate UUID for a PostgreSQL chunk id."""

        from weaviate.util import generate_uuid5

        return generate_uuid5(chunk_id)

    def replace(self, document: EvidenceVectorDocument) -> Any:
        """Insert or fully replace one chunk and verify the object exists."""

        object_uuid = self.object_uuid(document.chunk_id)
        properties = document.properties()
        if self._collection.data.exists(object_uuid):
            result = self._collection.data.replace(
                uuid=object_uuid, properties=properties, vector=list(document.vector)
            )
        else:
            result = self._collection.data.insert(properties=properties, uuid=object_uuid, vector=list(document.vector))
        if not self._collection.data.exists(object_uuid):
            raise RuntimeError(f"Weaviate projection postcondition failed for chunk {document.chunk_id}")
        return result

    def deactivate(self, chunk_id: str, *, authority_state: Literal["revoked", "superseded"]) -> bool:
        """Retain a stale vector but make it ineligible for evidence reads."""

        object_uuid = self.object_uuid(chunk_id)
        if not self._collection.data.exists(object_uuid):
            return False
        self._collection.data.update(
            uuid=object_uuid,
            properties={"authority_state": authority_state, "source_availability_complete": False},
        )
        if not self._collection.data.exists(object_uuid):
            raise RuntimeError(f"Weaviate deactivation postcondition failed for chunk {chunk_id}")
        return True

    def find_projection(self, *, artifact_id: str, content_hash: str | None = None, limit: int = 100) -> Any:
        """Structured retry-gap lookup; never searches serialized JSON metadata."""

        filters = Filter.by_property("artifact_id").equal(UUID(artifact_id))
        if content_hash is not None:
            filters &= Filter.by_property("content_hash").equal(content_hash)
        return self._collection.query.fetch_objects(filters=filters, limit=limit, return_properties=_RETURN_PROPERTIES)

    def find_by_source_sha256(self, source_sha256: str, *, limit: int = 1) -> Any:
        """Structured custody-source lookup for retry-gap reconciliation."""

        if not source_sha256:
            raise ValueError("source_sha256 must not be empty")
        return self._collection.query.fetch_objects(
            filters=Filter.by_property("source_sha256").equal(source_sha256),
            limit=limit,
            return_properties=_RETURN_PROPERTIES,
        )

    def search(
        self,
        *,
        vector: Sequence[float],
        horizon: datetime | None,
        case_id: str,
        disclosure_tiers: Sequence[DisclosureTier],
        limit: int = 10,
        mode: SearchMode = "near_vector",
        query: str | None = None,
        source_kinds: Sequence[str] | None = None,
        projection_kinds: Sequence[str] | None = None,
        alpha: float = 0.75,
    ) -> Any:
        """Search only candidates visible to this horizon, before ranking.

        Missing availability is excluded by the explicit completeness equality
        and by the date comparison itself.  There is intentionally no unfiltered
        search method on this class.
        """

        if len(vector) != EVIDENCE_EMBED_DIM:
            raise ValueError(f"query vector must have exactly {EVIDENCE_EMBED_DIM} dimensions")
        if not case_id:
            raise ValueError("case_id must not be empty")
        if not disclosure_tiers:
            raise ValueError("at least one disclosure_tier is required")
        if limit < 1:
            raise ValueError("limit must be positive")

        tier_set = set(disclosure_tiers)
        all_tiers = {"contemporaneous", "discovered", "hindsight"}
        if horizon is None and tier_set != all_tiers:
            raise ValueError("an unbounded hindsight search requires the complete permission-derived tier set")
        predicates = [
            Filter.by_property("case_id").equal(case_id),
            Filter.by_property("source_availability_complete").equal(True),
            Filter.by_property("authority_state").equal("active"),
            _one_of("disclosure_tier", disclosure_tiers),
            *([_one_of("source_kind", source_kinds)] if source_kinds else []),
            *([_one_of("projection_kind", projection_kinds)] if projection_kinds else []),
        ]
        if horizon is not None:
            predicates.insert(
                3,
                Filter.by_property("source_available_from").less_or_equal(_utc(horizon, field="horizon")),
            )
        filters = Filter.all_of(predicates)
        common = {
            "filters": filters,
            "limit": limit,
            "return_properties": _RETURN_PROPERTIES,
            "return_metadata": MetadataQuery(distance=True, score=True, explain_score=True),
        }
        if mode == "near_vector":
            return self._collection.query.near_vector(near_vector=list(vector), **common)
        if mode == "hybrid":
            if not query:
                raise ValueError("hybrid search requires query text")
            return self._collection.query.hybrid(
                query=query,
                vector=list(vector),
                alpha=alpha,
                query_properties=["content"],
                **common,
            )
        raise ValueError(f"unsupported search mode: {mode}")


def _one_of(property_name: str, values: Sequence[str]) -> Any:
    clean = list(dict.fromkeys(value for value in values if value))
    if not clean:
        raise ValueError(f"{property_name} filter must not be empty")
    return Filter.any_of([Filter.by_property(property_name).equal(value) for value in clean])
