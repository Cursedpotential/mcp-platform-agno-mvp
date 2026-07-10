"""Unit tests for evidence.normalize — the canonical bitemporal record.

The Part-2 "abuse made legible" delta filters on occurred_at / knowledge_time /
disclosure_tier, so the tz-coercion validator and finalize() defaults are
load-bearing. Both are pure and fast to test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from server.contracts.records import (
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
    # Use a non-UTC offset so a regression that coerces *everything* to UTC fails.
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    rec = NormalizedRecord(source="t", knowledge_time=aware)
    assert rec.knowledge_time == aware
    assert rec.knowledge_time is not None
    assert rec.knowledge_time.utcoffset() == timedelta(hours=2)


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
    # Non-UTC offset: a regression that converts to UTC would change utcoffset.
    explicit = datetime(2020, 5, 1, tzinfo=timezone(timedelta(hours=2)))
    rec = NormalizedRecord(source="t", knowledge_time=explicit)
    [out] = finalize([rec])
    assert out.knowledge_time == explicit
    assert out.knowledge_time is not None
    assert out.knowledge_time.utcoffset() == timedelta(hours=2)


def test_finalize_is_stable_across_records():
    recs = [NormalizedRecord(source="t") for _ in range(3)]
    out = finalize(recs)
    assert len(out) == 3
    assert all(r.knowledge_time is not None for r in out)
    # finalize() stamps one timestamp per batch — all records share it, rather
    # than calling datetime.now() separately per record.
    assert len({r.knowledge_time for r in out}) == 1


def test_enum_string_values_are_stable():
    # These strings are persisted to Postgres; changing any is a migration, so
    # pin every member of both enums.
    assert {t.value for t in DisclosureTier} == {"contemporaneous", "hindsight", "discovered"}
    assert {t.value for t in RecordType} == {"message", "call", "event", "media"}
