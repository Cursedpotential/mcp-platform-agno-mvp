"""Static safety checks for the reviewed physical artifacts.

Byline: Codex · GPT-5 · 2026-08-16
# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""

from pathlib import Path

import pytest

from horizon_surreal_phase1.runner import _assert_statement_success

ROOT = Path(__file__).parents[1]


def test_schema_is_schemafull_record_scoped_and_non_destructive() -> None:
    schema = (ROOT / "schema" / "001_phase1_t0.surql").read_text(encoding="utf-8")
    upper = schema.upper()
    assert "SCHEMAFULL" in upper
    assert "TYPE RECORD" in upper
    assert "PERMISSIONS FULL" not in upper
    assert "REMOVE TABLE" not in upper
    assert "DROP " not in upper
    assert "DELETE " not in upper
    assert "DEFINE TABLE RETRIEVAL_CHUNK" in upper
    assert "DEFINE TABLE THIRD_PARTY_CONVERSATION" in upper
    assert "DEFINE TABLE THIRD_PARTY_MESSAGE" in upper
    assert "DEFINE TABLE THIRD_PARTY_REALIZATION_LINK" in upper
    assert "DEFINE TABLE WALK_CHECKPOINT" in upper
    assert "DEFINE TABLE WALK_SNAPSHOT" in upper
    assert "DEFINE TABLE REWALK_OF TYPE RELATION" in upper
    assert "FOR UPDATE" in upper
    assert "FIELDS PLATFORM_ID, PROJECTION_REVISION UNIQUE" in upper
    assert "RESUMABLE ON TABLE WALK_SNAPSHOT TYPE BOOL ASSERT $VALUE = FALSE" in upper
    assert "RESUMABLE ON TABLE WALK_CHECKPOINT" not in upper
    assert '$BEFORE.STATUS IN ["ACTIVE", "PAUSED"]' in upper
    assert '$BEFORE.STATUS IN ["BUILDING", "ACTIVE"]' in upper
    assert "$AFTER.WALK_ID = $BEFORE.WALK_ID" in upper
    assert "$AFTER.PROJECTION_REVISION = $BEFORE.PROJECTION_REVISION" in upper
    assert 'STATUS = "PAUSED" AND TYPE::RECORD("PROJECTION_GUARD", PROJECTION_REVISION).STATUS = "ACTIVE"' in upper
    assert 'STATUS = "ACTIVE" AND TYPE::RECORD("PROJECTION_GUARD", PROJECTION_REVISION).STATUS = "ACTIVE"' in upper
    assert 'STATUS = "SEALED" AND TYPE::RECORD("PROJECTION_GUARD", PROJECTION_REVISION).STATUS = "QUARANTINED"' in upper


def test_vector_query_prefilters_before_exact_cosine_and_captures_plan() -> None:
    query = (ROOT / "queries" / "retrieve_exact.surql").read_text(encoding="utf-8")
    upper = query.upper()
    assert "EXPLAIN FULL" in upper
    assert upper.index("WHERE") < upper.index("VECTOR::SIMILARITY::COSINE")
    assert "SOURCE_AVAILABLE_FROM" in upper
    assert "VISIBLE_FROM" not in upper
    for binding in (
        "$MATTER_ID",
        "$PROJECTION_REVISION",
        "$POLICY_VERSION",
        "$POLICY_HASH",
        "$HORIZON_AT",
        "$MODE",
    ):
        assert binding in upper


def test_multi_statement_schema_failure_is_not_hidden() -> None:
    raw = {
        "result": [
            {"status": "OK", "result": None},
            {"status": "ERR", "result": "definition rejected"},
        ]
    }
    with pytest.raises(RuntimeError, match="schema:1:definition rejected"):
        _assert_statement_success(raw, "schema")
