"""Unit tests for evidence.normalize — the canonical bitemporal record.

The Part-2 "abuse made legible" delta filters on occurred_at / knowledge_time /
disclosure_tier, so the tz-coercion validator and finalize() defaults are
load-bearing. Both are pure and fast to test.
"""

from __future__ import annotations

from datetime import datetime, timezone

from evidence.normalize import (
    DisclosureTier,
    NormalizedRecord,
    RecordType,
    finalize,
)


def test_naive_datetime_is_coerced_to_utc():
    rec = NormalizedRecord(source="t", occurred_at=datetime(2026, 1, 1, 12, 0, 0))
    assert rec.occurred_at is not None
    assert rec.occurred_at.tzinfo is timezone.utc


def test_aware_datetime_is_preserved():
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    rec = NormalizedRecord(source="t", knowledge_time=aware)
    assert rec.knowledge_time == aware


def test_defaults():
    rec = NormalizedRecord(source="chatgpt-export")
    assert rec.record_type is RecordType.message
    assert rec.disclosure_tier is DisclosureTier.contemporaneous
    assert rec.content == ""
    assert rec.participants == []
    assert rec.attrs == {}


def test_finalize_fills_missing_knowledge_time():
    rec = NormalizedRecord(source="t")
    assert rec.knowledge_time is None
    [out] = finalize([rec])
    assert out.knowledge_time is not None
    assert out.knowledge_time.tzinfo is timezone.utc


def test_finalize_preserves_existing_knowledge_time():
    # Re-processing historical material with an explicit knowledge_time is a
    # deliberate Part-2 operation — finalize() must NOT clobber it.
    explicit = datetime(2020, 5, 1, tzinfo=timezone.utc)
    rec = NormalizedRecord(source="t", knowledge_time=explicit)
    [out] = finalize([rec])
    assert out.knowledge_time == explicit


def test_finalize_is_stable_across_records():
    recs = [NormalizedRecord(source="t") for _ in range(3)]
    out = finalize(recs)
    assert len(out) == 3
    assert all(r.knowledge_time is not None for r in out)


def test_enum_string_values_are_stable():
    # These strings are persisted to Postgres; changing them is a migration.
    assert DisclosureTier.discovered.value == "discovered"
    assert DisclosureTier.hindsight.value == "hindsight"
    assert RecordType.media.value == "media"
