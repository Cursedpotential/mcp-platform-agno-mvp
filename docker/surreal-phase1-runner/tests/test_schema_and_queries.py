"""Static safety checks for the reviewed physical artifacts.

Byline: Codex · GPT-5 · 2026-08-16
"""

from pathlib import Path

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
    assert "DEFINE TABLE WALK_SNAPSHOT" in upper


def test_vector_query_prefilters_before_exact_cosine_and_captures_plan() -> None:
    query = (ROOT / "queries" / "retrieve_exact.surql").read_text(encoding="utf-8")
    upper = query.upper()
    assert "EXPLAIN FULL" in upper
    assert upper.index("WHERE") < upper.index("VECTOR::SIMILARITY::COSINE")
    for binding in (
        "$MATTER_ID",
        "$PROJECTION_REVISION",
        "$POLICY_VERSION",
        "$POLICY_HASH",
        "$HORIZON_AT",
        "$MODE",
    ):
        assert binding in upper
