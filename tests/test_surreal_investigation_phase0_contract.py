"""Framework-neutral Phase-0 planted-future-fact contract tests.

Byline: Codex · GPT-5 · 2026-08-16

These tests validate the proposed contract and synthetic gold fixture. They do
not prove any live PostgreSQL, Weaviate, Neo4j, Graphiti, or Surreal adapter.
Each later adapter must run this behavior against its real pre-ranking filter.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "surreal_investigation_phase0_horizon.json"
SURFACES = ("postgresql", "weaviate", "neo4j", "surreal")
AGENT_VISIBLE_SURFACES = (
    "retrieval",
    "prompt",
    "handoff",
    "coordination_wal",
    "belief",
    "summary",
    "observation",
    "trace",
)
FORBIDDEN_IMPORT_ROOTS = {
    "agno",
    "autogen",
    "graphiti_core",
    "neo4j",
    "psycopg",
    "surrealdb",
    "weaviate",
}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Document:
    id: str
    matter_id: str
    occurred_at: datetime
    visible_from: datetime
    recorded_at: datetime
    disclosure_tier: str
    authority_state: str
    promotion_state: str
    similarity: float
    content: str


@dataclass(frozen=True)
class HorizonRequest:
    matter_id: str
    horizon_at: datetime
    mode: Literal["as_lived_so_far", "hindsight"]
    top_k: int


@dataclass(frozen=True)
class SearchTrace:
    surface: str
    eligible_ids_before_ranking: tuple[str, ...]
    ranked_ids: tuple[str, ...]


class UnsupportedPrefilter(RuntimeError):
    """The adapter cannot prove that it filters before ranking/traversal."""


def _load_fixture() -> tuple[dict[str, Any], tuple[Document, ...]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    documents = tuple(
        Document(
            id=row["id"],
            matter_id=row["matter_id"],
            occurred_at=_parse_time(row["occurred_at"]),
            visible_from=_parse_time(row["visible_from"]),
            recorded_at=_parse_time(row["recorded_at"]),
            disclosure_tier=row["disclosure_tier"],
            authority_state=row["authority_state"],
            promotion_state=row["promotion_state"],
            similarity=row["similarity"],
            content=row["content"],
        )
        for row in payload["documents"]
    )
    return payload, documents


def _eligible(document: Document, request: HorizonRequest) -> bool:
    if document.matter_id != request.matter_id:
        return False
    if document.authority_state != "approved":
        return False
    if document.promotion_state != "active":
        return False
    if request.mode == "as_lived_so_far":
        return document.visible_from <= request.horizon_at and document.disclosure_tier != "hindsight"
    return True


def _prefilter_then_rank(
    surface: str,
    documents: tuple[Document, ...],
    request: HorizonRequest,
    *,
    supports_prefilter: bool = True,
) -> tuple[tuple[Document, ...], SearchTrace]:
    if not supports_prefilter:
        raise UnsupportedPrefilter(f"{surface} cannot prove pre-ranking filtering")
    eligible = tuple(document for document in documents if _eligible(document, request))
    ranked = tuple(sorted(eligible, key=lambda document: document.similarity, reverse=True)[: request.top_k])
    trace = SearchTrace(
        surface=surface,
        eligible_ids_before_ranking=tuple(document.id for document in eligible),
        ranked_ids=tuple(document.id for document in ranked),
    )
    return ranked, trace


def _rank_then_postfilter(documents: tuple[Document, ...], request: HorizonRequest) -> tuple[Document, ...]:
    """Known-bad reference used to ensure the canary catches top-k shrinkage."""
    ranked = sorted(documents, key=lambda document: document.similarity, reverse=True)[: request.top_k]
    return tuple(document for document in ranked if _eligible(document, request))


def _agent_visible_envelope(documents: tuple[Document, ...]) -> dict[str, list[dict[str, str]]]:
    entries = [{"id": document.id, "content": document.content} for document in documents]
    return {surface: entries for surface in AGENT_VISIBLE_SURFACES}


def test_fixture_is_versioned_and_has_two_distinct_future_fact_shapes() -> None:
    payload, documents = _load_fixture()
    assert payload["schema_version"] == "phase0-horizon-canary-v1"
    by_id = {document.id: document for document in documents}
    future_occurring = by_id["future-occurring-canary"]
    late_realized = by_id["late-realized-old-source-canary"]
    early_horizon = _parse_time(payload["horizons"]["early"])

    assert future_occurring.occurred_at > early_horizon
    assert late_realized.occurred_at < early_horizon < late_realized.visible_from
    assert late_realized.recorded_at < early_horizon


@pytest.mark.parametrize("surface", SURFACES)
def test_early_as_lived_prefilters_future_facts_before_ranking(surface: str) -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )

    results, trace = _prefilter_then_rank(surface, documents, request)

    expected = tuple(payload["expected"]["early_as_lived_ranked_ids"])
    assert trace.ranked_ids == expected
    assert len(results) == request.top_k
    assert all(payload["canary_literal"] not in document.content for document in results)
    assert not any("canary" in document_id for document_id in trace.eligible_ids_before_ranking)


def test_canary_detects_rank_then_filter_top_k_shrinkage() -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )

    bad_results = _rank_then_postfilter(documents, request)

    assert bad_results == ()
    assert len(bad_results) < request.top_k


def test_late_realized_old_source_is_hidden_by_visible_from_not_other_clocks() -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=20,
    )
    results, _ = _prefilter_then_rank("reference", documents, request)
    result_ids = {document.id for document in results}

    assert "late-realized-old-source-canary" not in result_ids
    late_realized = next(document for document in documents if document.id == "late-realized-old-source-canary")
    assert late_realized.occurred_at < request.horizon_at
    assert late_realized.recorded_at < request.horizon_at
    assert late_realized.visible_from > request.horizon_at


def test_late_as_lived_and_hindsight_have_explicit_expected_deltas() -> None:
    payload, documents = _load_fixture()
    late_horizon = _parse_time(payload["horizons"]["late"])
    late_request = HorizonRequest(payload["matter_id"], late_horizon, "as_lived_so_far", payload["top_k"])
    hindsight_request = HorizonRequest(payload["matter_id"], late_horizon, "hindsight", payload["top_k"])

    late_results, _ = _prefilter_then_rank("reference", documents, late_request)
    hindsight_results, _ = _prefilter_then_rank("reference", documents, hindsight_request)

    assert [document.id for document in late_results] == payload["expected"]["late_as_lived_top_ids"]
    assert [document.id for document in hindsight_results] == payload["expected"]["hindsight_top_ids"]
    assert {document.id for document in late_results} != {document.id for document in hindsight_results}
    assert "hindsight-only-canary" not in {document.id for document in late_results}
    assert "hindsight-only-canary" in {document.id for document in hindsight_results}
    assert all(document.matter_id == payload["matter_id"] for document in hindsight_results)
    assert all(document.promotion_state == "active" for document in hindsight_results)


def test_canary_never_enters_any_early_agent_visible_surface_or_query_generation() -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )
    results, _ = _prefilter_then_rank("reference", documents, request)
    envelope = _agent_visible_envelope(results)
    serialized = json.dumps(envelope, sort_keys=True)
    query_terms = " ".join(document.content for document in results)

    assert set(envelope) == set(AGENT_VISIBLE_SURFACES)
    assert payload["canary_literal"] not in serialized
    assert payload["canary_literal"] not in query_terms


@pytest.mark.parametrize("surface", SURFACES)
def test_unverifiable_prefilter_support_fails_closed(surface: str) -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )

    with pytest.raises(UnsupportedPrefilter, match="cannot prove pre-ranking"):
        _prefilter_then_rank(surface, documents, request, supports_prefilter=False)


def test_contract_test_has_no_runtime_or_store_client_imports() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", maxsplit=1)[0])

    assert imports.isdisjoint(FORBIDDEN_IMPORT_ROOTS)
