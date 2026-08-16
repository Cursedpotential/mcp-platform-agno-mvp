"""Observed Semantica extraction with no persistence or projection capability.

This adapter executes the vendored Semantica pattern extractors, immediately
converts their framework objects into platform candidate contracts, and never
loads a model provider or store. RelationExtractor is intentionally not used:
its final fallback fabricates ``related_to`` adjacency edges.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any, cast

from server.analysis.semantica_contracts import (
    CandidateBatch,
    CandidateProvenance,
    EntityCandidate,
    EventCandidate,
    ExtractionBatch,
    ExtractionFailure,
    ExtractionRecord,
    ExtractionRejection,
    FactCandidate,
)
from server.vendored.semantica.semantica.semantic_extract import event_detector as _event_module
from server.vendored.semantica.semantica.semantic_extract import methods as _methods
from server.vendored.semantica.semantica.semantic_extract.event_detector import Event, EventDetector
from server.vendored.semantica.semantica.semantic_extract.ner_extractor import Entity


_IDENTITY_LABELS = {
    "PERSON": "person",
    "PER": "person",
    "ORG": "organization",
    "ORGANIZATION": "organization",
    "GPE": "location",
    "LOC": "location",
    "LOCATION": "location",
    "FAC": "location",
    "DEVICE": "device",
    "ACCOUNT": "account",
}
_CONFIG = {
    "entity_method": "pattern",
    "relation_method": "pattern-direct-no-fallback",
    "event_method": "pattern",
    "fabricated_adjacency": False,
    "horizon_blind": True,
}


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _module_hash(module: Any) -> str:
    path = Path(module.__file__ or "")
    return sha256(path.read_bytes()).hexdigest()


def _version() -> str:
    source_hash = sha256(f"{_module_hash(_methods)}:{_module_hash(_event_module)}".encode()).hexdigest()[:16]
    return f"vendored-0.3.0-alpha+{source_hash}"


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _provenance(
    record: ExtractionRecord,
    *,
    version: str,
    config_hash: str,
    method: str,
    span_start: int | None = None,
    span_end: int | None = None,
    evidence_quote: str | None = None,
) -> CandidateProvenance:
    return CandidateProvenance(
        source_raw_table=record.source_raw_table,
        source_raw_id=record.source_raw_id,
        source_content_sha256=record.content_sha256,
        source_provenance_ref=record.provenance_ref,
        extractor_version=version,
        config_sha256=config_hash,
        method=method,
        span_start=span_start,
        span_end=span_end,
        evidence_quote=evidence_quote,
    )


def _time_window(value: str | None) -> tuple[datetime | None, datetime | None, datetime | None, float]:
    """Keep vague dates as bounded intervals; never invent a precise event time."""
    if not value:
        return None, None, None, 0.0
    raw = value.strip().replace(",", "")
    if re.fullmatch(r"\d{4}", raw):
        start = datetime(int(raw), 1, 1, tzinfo=timezone.utc)
        return None, start, datetime(int(raw) + 1, 1, 1, tzinfo=timezone.utc), 0.5
    for pattern in ("%m/%d/%Y", "%m-%d-%Y", "%B %d %Y"):
        try:
            start = datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
            return None, start, start + timedelta(days=1), 0.75
        except ValueError:
            continue
    return None, None, None, 0.0


class SemanticaPatternWorker:
    """Deterministic first slice over Semantica's real, torch-free methods."""

    def __init__(self) -> None:
        self.extractor_version = _version()
        self.config_sha256 = _canonical_hash(_CONFIG)
        self._event_detector = EventDetector(method="pattern")

    def extract(self, batch: ExtractionBatch) -> CandidateBatch:
        entities: list[EntityCandidate] = []
        facts: list[FactCandidate] = []
        events: list[EventCandidate] = []
        rejections: list[ExtractionRejection] = []
        failures: list[ExtractionFailure] = []

        for record in batch.records:
            try:
                record_entities, identity_entities, entity_keys = self._entities(record, rejections)
                entities.extend(record_entities)
                facts.extend(self._relations(record, identity_entities, entity_keys))
                record_events, event_rejections = self._events(record)
                events.extend(record_events)
                rejections.extend(event_rejections)
            except Exception as error:
                failures.append(
                    ExtractionFailure(source_raw_id=record.source_raw_id, stage="extract", error=str(error)[:500])
                )

        return CandidateBatch(
            batch_id=batch.batch_id,
            matter_id=batch.matter_id,
            extractor_version=self.extractor_version,
            config_sha256=self.config_sha256,
            source_count=len(batch.records),
            entities=tuple(entities),
            facts=tuple(facts),
            events=tuple(events),
            rejections=tuple(rejections),
            failures=tuple(failures),
        )

    def _entities(
        self,
        record: ExtractionRecord,
        rejections: list[ExtractionRejection],
    ) -> tuple[list[EntityCandidate], list[Entity], dict[tuple[str, int, int], str]]:
        raw_entities = _methods.extract_entities_pattern(record.content)
        candidates: list[EntityCandidate] = []
        identity_entities: list[Entity] = []
        keys: dict[tuple[str, int, int], str] = {}
        seen: set[tuple[str, int, int, str]] = set()
        for entity in raw_entities:
            entity_type = _IDENTITY_LABELS.get(entity.label.upper())
            if entity_type is None:
                rejections.append(
                    ExtractionRejection(
                        source_raw_id=record.source_raw_id,
                        stage="entity",
                        reason="non_identity_entity",
                        detail=f"{entity.label}:{entity.text}",
                    )
                )
                continue
            identity = (_normalized_name(entity.text), entity.start_char, entity.end_char, entity_type)
            if identity in seen:
                continue
            seen.add(identity)
            payload = {
                "kind": "entity",
                "source": record.source_raw_id,
                "source_sha256": record.content_sha256,
                "type": entity_type,
                "name": entity.text,
                "start": entity.start_char,
                "end": entity.end_char,
            }
            digest = _canonical_hash(payload)
            key = f"entity:{digest}"
            identity_entities.append(entity)
            keys[(_normalized_name(entity.text), entity.start_char, entity.end_char)] = key
            candidates.append(
                EntityCandidate(
                    key=key,
                    entity_type=entity_type,
                    name=entity.text,
                    normalized_name=_normalized_name(entity.text),
                    confidence=entity.confidence,
                    content_sha256=digest,
                    provenance=_provenance(
                        record,
                        version=self.extractor_version,
                        config_hash=self.config_sha256,
                        method=str(entity.metadata.get("extraction_method") or "pattern"),
                        span_start=entity.start_char,
                        span_end=entity.end_char,
                        evidence_quote=record.content[entity.start_char : entity.end_char],
                    ),
                )
            )
        return candidates, identity_entities, keys

    def _relations(
        self,
        record: ExtractionRecord,
        identity_entities: list[Entity],
        key_by_identity: dict[tuple[str, int, int], str],
    ) -> list[FactCandidate]:
        # Use the direct Semantica method, never RelationExtractor's fallback chain.
        raw_relations = _methods.extract_relations_pattern(record.content, identity_entities)
        candidates: list[FactCandidate] = []
        for relation in raw_relations:
            if (
                relation.predicate == "related_to"
                or relation.metadata.get("extraction_method") == "last_resort_adjacency"
            ):
                raise ValueError("Semantica fabricated adjacency relation reached governed adapter")
            subject_key = key_by_identity.get(
                (_normalized_name(relation.subject.text), relation.subject.start_char, relation.subject.end_char)
            )
            object_key = key_by_identity.get(
                (_normalized_name(relation.object.text), relation.object.start_char, relation.object.end_char)
            )
            if not subject_key or not object_key:
                continue
            statement = f"{relation.subject.text} {relation.predicate} {relation.object.text}"
            payload = {
                "kind": "fact",
                "source": record.source_raw_id,
                "source_sha256": record.content_sha256,
                "subject": subject_key,
                "predicate": relation.predicate,
                "object": object_key,
            }
            digest = _canonical_hash(payload)
            candidates.append(
                FactCandidate(
                    key=f"fact:{digest}",
                    subject_key=subject_key,
                    object_key=object_key,
                    predicate=relation.predicate,
                    statement=statement,
                    confidence=relation.confidence,
                    content_sha256=digest,
                    provenance=_provenance(
                        record,
                        version=self.extractor_version,
                        config_hash=self.config_sha256,
                        method=str(relation.metadata.get("extraction_method") or "pattern"),
                        evidence_quote=relation.context or record.content,
                    ),
                )
            )
        return candidates

    def _events(self, record: ExtractionRecord) -> tuple[list[EventCandidate], list[ExtractionRejection]]:
        # The vendored progress tracker writes presentation noise to stdout.
        # Capture only that display stream; exceptions still propagate.
        with redirect_stdout(StringIO()):
            raw_events = cast(list[Event], self._event_detector.detect_events(record.content))
        candidates: list[EventCandidate] = []
        rejections: list[ExtractionRejection] = []
        for event in raw_events:
            occurred_at, valid_from, valid_to, temporal_confidence = _time_window(event.time)
            if occurred_at is None and valid_from is None:
                rejections.append(
                    ExtractionRejection(
                        source_raw_id=record.source_raw_id,
                        stage="event",
                        reason="unresolved_event_time",
                        detail=f"{event.event_type}:{event.text}",
                    )
                )
                continue
            payload = {
                "kind": "event",
                "source": record.source_raw_id,
                "source_sha256": record.content_sha256,
                "event_type": event.event_type,
                "span": [event.start_char, event.end_char],
                "raw_time": event.time,
            }
            digest = _canonical_hash(payload)
            context = str(event.metadata.get("context") or record.content)
            candidates.append(
                EventCandidate(
                    key=f"event:{digest}",
                    event_type=event.event_type,
                    summary=context,
                    occurred_at=occurred_at,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    temporal_confidence=temporal_confidence,
                    confidence=event.confidence,
                    content_sha256=digest,
                    provenance=_provenance(
                        record,
                        version=self.extractor_version,
                        config_hash=self.config_sha256,
                        method="pattern",
                        span_start=event.start_char,
                        span_end=event.end_char,
                        evidence_quote=context,
                    ),
                )
            )
        return candidates, rejections
