"""Temporal-source contract for the PostgreSQL walk derivation.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from server.evidence.derivation import (
    _HINDSIGHT_SLICE_SQL,
    _SLICE_SQL,
    _canonical_slice,
    _compute_base_version,
)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""

    def execute(self, statement, params):
        self.sql = str(statement)
        assert params == {"cid": "primary"}
        return _Rows(self.rows)


def test_base_version_consumes_complete_version_input_view():
    conn = _Conn(
        [
            ("message_projection_route", "r1", {"projection_kind": "acquired_third_party"}),
            ("third_party_acquisition", "a1", {"acquired_at": "2025-01-01T00:00:00+00:00"}),
        ]
    )
    digest = _compute_base_version(conn, "primary")
    assert len(digest) == 64
    assert "vw_walk_base_version_input" in conn.sql
    assert "ORDER BY input_kind, input_key" in conn.sql


def test_slice_hash_keeps_source_and_realization_atoms_distinct():
    instant = datetime(2025, 1, 1, tzinfo=timezone.utc)
    payload = json.loads(
        _canonical_slice(
            [
                ("realization_event", "same-id", instant, instant, "discovered"),
                ("normalized_record", "same-id", instant, instant, "contemporaneous"),
            ],
            instant,
        )
    )
    assert [(row["atom_kind"], row["atom_id"]) for row in payload["slice"]] == [
        ("normalized_record", "same-id"),
        ("realization_event", "same-id"),
    ]


def test_as_lived_slice_fails_closed_and_hindsight_keeps_atoms_typed():
    assert "FROM working.vw_horizon_atom" in _SLICE_SQL
    assert "visible_from IS NOT NULL" in _SLICE_SQL
    assert "visible_from <= :horizon" in _SLICE_SQL
    assert "FROM working.vw_horizon_atom" in _HINDSIGHT_SLICE_SQL
