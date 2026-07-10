"""Unit tests for server.tools._common — helpers shared by every parser tool.

parse_timestamp and records_out sit on the hot path of all four transcript
tools, so their edge cases (bad input, naive vs aware, JSON-safety) matter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from server.contracts.records import NormalizedRecord
from server.tools._common import parse_timestamp, records_out


def test_parse_timestamp_epoch_seconds():
    assert parse_timestamp(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)
    dt = parse_timestamp(1_700_000_000)
    assert dt is not None and dt.tzinfo is timezone.utc and dt.year == 2023


def test_parse_timestamp_float_epoch():
    dt = parse_timestamp(1_700_000_000.5)
    assert dt is not None and dt.tzinfo is timezone.utc


def test_parse_timestamp_iso_with_z():
    dt = parse_timestamp("2026-01-02T03:04:05Z")
    assert dt == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_parse_timestamp_iso_with_offset():
    dt = parse_timestamp("2026-01-02T03:04:05+02:00")
    assert dt is not None and dt.utcoffset() == timedelta(hours=2)


def test_parse_timestamp_iso_naive_stays_naive():
    # fromisoformat without tz yields a naive datetime; the helper doesn't coerce.
    dt = parse_timestamp("2026-01-02T03:04:05")
    assert dt is not None and dt.tzinfo is None


def test_parse_timestamp_bad_inputs_return_none():
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None
    assert parse_timestamp("not a date") is None
    assert parse_timestamp(10**20) is None  # out-of-range epoch -> caught


def test_records_out_shape_and_count():
    recs = [NormalizedRecord(source="a"), NormalizedRecord(source="b")]
    out = records_out(recs, parser="demo")
    assert [r["source"] for r in out["records"]] == ["a", "b"]
    assert out["stats"] == {"record_count": 2, "parser": "demo"}


def test_records_out_is_json_safe():
    rec = NormalizedRecord(source="a", occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    out = records_out([rec])
    # datetimes are serialized to strings (JSON-safe), not left as datetime objects.
    assert isinstance(out["records"][0]["occurred_at"], str)
    assert out["stats"]["record_count"] == 1


def test_records_out_empty():
    out = records_out([])
    assert out["records"] == []
    assert out["stats"]["record_count"] == 0
