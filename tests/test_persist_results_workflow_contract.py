"""Contract tests for the composed n8n persist-results body (GAP-031).

Byline: Claude Code · Sonnet 5 · 2026-08-26

docs/research/integration-audit-2026-08-24/composed/wf-persist-results.json is a staged n8n
workflow export, not executable Python — these tests parse it as JSON and assert on node
structure/code-node source text, mirroring the file's own "no unintended write" doctrine:
- the Normalize/Validate Code node must not drop decision_id/actor/decision/reason/source,
- the SQL INSERT's column list and $N placeholder count must agree,
- the ON CONFLICT target matches sql/0034's general row-idempotency unique index,
- item identity precedence (chunk_id > record_id > record_ref) matches
  ClassificationBatchPipeline._item_key in server/temporal/classification_workflow.py.

No n8n instance, Postgres, or Temporal server is touched. A live smoke run (posting a real
accepted+adjudicated batch through an imported copy of this workflow) is a required
live-verification step this packet hands off — see docs/reviews/2026-08-25-schema-audit/
GAP-031-IMPLEMENTATION-STATUS.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PERSIST_BODY = ROOT / "docs" / "research" / "integration-audit-2026-08-24" / "composed" / "wf-persist-results.json"


@pytest.fixture(scope="module")
def body() -> dict:
    return json.loads(PERSIST_BODY.read_text(encoding="utf-8"))


def _node(body: dict, name: str) -> dict:
    for node in body["nodes"]:
        if node["name"] == name:
            return node
    raise AssertionError(f"node {name!r} not found; have: {[n['name'] for n in body['nodes']]}")


def test_composed_body_is_valid_json_with_expected_nodes(body: dict) -> None:
    names = {n["name"] for n in body["nodes"]}
    for expected in (
        "Webhook - persist results",
        "Normalize + Validate Accepted Rows",
        "Postgres - Insert Classification (parameterized)",
        "Build Confirmation",
        "Respond - persist confirmation",
    ):
        assert expected in names


def test_webhook_path_is_persist_results(body: dict) -> None:
    node = _node(body, "Webhook - persist results")
    assert node["parameters"]["path"] == "d068/persist-results"


def test_normalize_node_reads_top_level_run_key_batch_index_classifier_version(body: dict) -> None:
    # These come from ClassificationBatchPipeline._call(PERSIST_PATH, {"run_key": ..., "batch_index": ...,
    # "classifier_version": ..., "items": accepted}) - top-level on the body, not per-item.
    code = _node(body, "Normalize + Validate Accepted Rows")["parameters"]["jsCode"]
    assert "body.run_key" in code
    assert "body.batch_index" in code
    assert "body.classifier_version" in code


def test_normalize_node_extracts_every_adjudication_field(body: dict) -> None:
    code = _node(body, "Normalize + Validate Accepted Rows")["parameters"]["jsCode"]
    for field in ("decision_id", "actor", "decision", "reason", "source"):
        assert f"adj.{field}" in code, f"adjudication.{field} is read by the Code node"
    # And every one of them is written into the outgoing row, not silently dropped.
    for field in ("decision_id", "actor", "decision", "reason", "source", "adjudicated_at"):
        assert re.search(rf"\b{field}:", code), f"{field} is assigned onto the outgoing row"


def test_normalize_node_rejects_incomplete_adjudication(body: dict) -> None:
    code = _node(body, "Normalize + Validate Accepted Rows")["parameters"]["jsCode"]
    assert "adjudication is missing decision_id/actor/reason/source" in code
    assert "VALID_DECISIONS" in code
    assert "'approve'" in code and "'correct'" in code


def test_normalize_node_item_identity_precedence_matches_temporal_item_key(body: dict) -> None:
    # ClassificationBatchPipeline._item_key: chunk_id > record_id > record_ref.
    code = _node(body, "Normalize + Validate Accepted Rows")["parameters"]["jsCode"]
    assert "it.chunk_id || it.record_id || it.record_ref" in code


def test_normalize_node_rejects_non_accepted_gate_outcomes(body: dict) -> None:
    code = _node(body, "Normalize + Validate Accepted Rows")["parameters"]["jsCode"]
    assert "gate_outcome" in code
    assert "is not accepted" in code


def test_insert_column_list_matches_placeholder_count_and_param_array(body: dict) -> None:
    node = _node(body, "Postgres - Insert Classification (parameterized)")
    query = node["parameters"]["query"]
    replacement = node["parameters"]["options"]["queryReplacement"]

    columns_block = query.split("(", 1)[1].split(")", 1)[0]
    columns = [c.strip() for c in columns_block.replace("\n", " ").split(",") if c.strip()]

    placeholders = sorted(set(re.findall(r"\$(\d+)", query)), key=int)
    assert [int(p) for p in placeholders] == list(range(1, len(placeholders) + 1))
    assert len(columns) == len(placeholders), (columns, placeholders)

    array_items = [expr.strip() for expr in replacement.split("[", 1)[1].rsplit("]", 1)[0].split(",") if expr.strip()]
    assert len(array_items) == len(placeholders)


def test_insert_carries_every_adjudication_column(body: dict) -> None:
    query = _node(body, "Postgres - Insert Classification (parameterized)")["parameters"]["query"]
    for column in ("decision_id", "actor", "decision", "reason", "source", "adjudicated_at"):
        assert re.search(rf"\b{column}\b", query), column


def test_on_conflict_target_matches_sql_0034_general_row_key(body: dict) -> None:
    query = _node(body, "Postgres - Insert Classification (parameterized)")["parameters"]["query"]
    assert "ON CONFLICT (run_key, batch_index, record_ref, classifier_version) DO NOTHING" in query

    migration = (ROOT / "sql" / "0034_classification_adjudication.sql").read_text(encoding="utf-8")
    assert "run_key, batch_index, record_ref, classifier_version" in migration


def test_on_conflict_does_not_target_decision_id_so_conflicts_there_error(body: dict) -> None:
    # Fail-closed design: decision_id has its OWN partial unique index (sql/0034) that is
    # deliberately NOT the ON CONFLICT arbiter, so a reused decision_id on a different item
    # raises instead of silently upserting.
    query = _node(body, "Postgres - Insert Classification (parameterized)")["parameters"]["query"]
    conflict_clause = query.split("ON CONFLICT", 1)[1].split("DO NOTHING", 1)[0]
    assert "decision_id" not in conflict_clause


def test_transaction_batching_is_still_enabled(body: dict) -> None:
    node = _node(body, "Postgres - Insert Classification (parameterized)")
    assert node["parameters"]["options"]["queryBatching"] == "transaction"


def test_build_confirmation_reports_adjudicated_count_not_stale_batch_id(body: dict) -> None:
    code = _node(body, "Build Confirmation")["parameters"]["jsCode"]
    assert "adjudicated_count" in code
    assert "src.filter(r => r.decision_id)" in code
    # The old body_id/record_id based counting is gone.
    assert "batch_id" not in code
    assert "r.record_id" not in code
