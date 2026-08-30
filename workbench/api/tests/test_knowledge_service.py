# Byline: Codex · GPT-5 · 2026-08-15 (case/lane-safe multi-base coverage)
# Byline: Codex · GPT-5 · 2026-08-16 (neutral canonical catalog/detail coverage)
# Byline: Codex · GPT-5 · 2026-08-18 (projection overlay and split chunk coverage)
# Byline: Codex · GPT-5 · 2026-08-18 (native evidence search routing coverage)
# Byline: Codex · GPT-5.6-Sol · 2026-08-29 (retired AgentOS search fails closed)
"""Unit coverage for the Workbench Knowledge anti-corruption adapter."""

from __future__ import annotations

import pytest

from app.repo import platform_api_auth
from app.service import knowledge


def test_search_non_evidence_lane_fails_closed_without_retired_call(monkeypatch):
    def must_not_call(*args, **kwargs):
        raise AssertionError("retired AgentOS knowledge endpoint must not be called")

    monkeypatch.setattr(knowledge, "spine_json", must_not_call)

    with pytest.raises(knowledge.SpineError, match="framework-neutral projection") as error:
        knowledge.search("custody chain", case_id="matter-2", lane="legal", limit=5)
    assert error.value.status_code == 503


def test_search_evidence_uses_native_horizon_route_without_caller_tiers(monkeypatch, tmp_path):
    captured = {}
    secret = tmp_path / "evidence-operator-security-key"
    secret.write_text("owner-search-key\n", encoding="utf-8")
    monkeypatch.setattr(platform_api_auth.settings, "evidence_operator_bearer_secret_file", str(secret))

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {
            "data": [{"id": "chunk-1", "content": "x", "meta_data": {}}],
            "meta": {"total_count": 1},
        }

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.search(
        "what happened",
        case_id="matter-2",
        lane="evidence",
        limit=5,
        horizon="2025-06-01T12:30:00+00:00",
    )

    assert captured == {
        "method": "POST",
        "path": "/v1/operator/evidence/search",
        "kwargs": {
            "headers": {"Authorization": "Bearer owner-search-key"},
            "json": {
                "query": "what happened",
                "case_id": "matter-2",
                "limit": 5,
                "mode": "hybrid",
                "horizon": "2025-06-01T12:30:00+00:00",
            },
        },
    }
    assert "disclosure_tiers" not in captured["kwargs"]["json"]
    assert result["data"][0]["meta_data"]["knowledge_lane"] == "evidence"


def test_search_without_lane_fails_closed_instead_of_returning_partial_results(monkeypatch):
    def must_not_call(*args, **kwargs):
        raise AssertionError("no projection should be queried for an unavailable cross-lane request")

    monkeypatch.setattr(knowledge, "spine_json", must_not_call)

    with pytest.raises(knowledge.SpineError, match="cross-lane semantic search") as error:
        knowledge.search("what happened", case_id="primary", limit=3)
    assert error.value.status_code == 503


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"query": " ", "case_id": "primary"}, "query must be a non-empty string"),
        ({"query": "q", "case_id": " "}, "case_id must be a non-empty string"),
        ({"query": "q", "case_id": "primary", "lane": "unknown"}, "unsupported knowledge lane"),
        ({"query": "q", "case_id": "primary", "limit": 0}, "limit must be between"),
        ({"query": "q", "case_id": "primary", "limit": 101}, "limit must be between"),
    ],
)
def test_search_rejects_unsafe_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        knowledge.search(**kwargs)


def test_list_contents_uses_neutral_canonical_route_and_maps_operator_metadata(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return [
            {
                "artifact_id": "00000000-0000-4000-8000-000000000001",
                "source_name": "messages.xml",
                "source_path": "/staged/messages.xml",
                "source_sha256": "a" * 64,
                "parser_id": "sbv.messages",
                "chunker_id": "chonkie.semantic@1.7.0",
                "lane": "evidence",
                "matter_id": "matter-7",
                "record_count": 12,
                "chunk_count": 20,
                "created_at": "2026-08-16T12:00:00Z",
            }
        ]

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.list_contents(case_id="matter-7", lane="evidence", limit=20, offset=0)

    assert captured == {
        "method": "GET",
        "path": "/v1/knowledge/items",
        "kwargs": {"params": {"matter_id": "matter-7", "lane": "evidence", "limit": 500}},
    }
    row = result["data"][0]
    assert row["name"] == "messages.xml"
    assert row["metadata"] == {
        "matter_id": "matter-7",
        "case_id": "matter-7",
        "knowledge_lane": "evidence",
        "source_path": "/staged/messages.xml",
        "parser_id": "sbv.messages",
        "chunker_id": "chonkie.semantic@1.7.0",
        "source_sha256": "a" * 64,
        "record_count": 12,
        "chunk_count": 20,
    }
    assert result["meta"]["total_count"] == 1
    assert result["meta"]["truncated"] is False


def test_list_contents_paginates_neutral_results(monkeypatch):
    def fake_spine_json(method, path, **kwargs):
        return [
            {"artifact_id": "a", "matter_id": "primary", "lane": "context"},
            {"artifact_id": "b", "matter_id": "primary", "lane": "context"},
        ]

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.list_contents(case_id="primary", lane="context", limit=1, offset=1)

    assert [row["id"] for row in result["data"]] == ["b"]
    assert result["meta"]["total_count"] == 2
    assert result["meta"]["page"] == 2


def test_get_content_forwards_matter_scope_and_enriches_from_record_attrs(monkeypatch):
    captured = []

    def fake_spine_json(method, path, **kwargs):
        captured.append({"method": method, "path": path, "kwargs": kwargs})
        if path == "/v1/records":
            return {
                "records": [
                    {
                        "id": "record-1",
                        "source_kind": "third_party_acquired",
                        "projection_kind": "derived_third_party",
                        "source_available_from": "2026-08-17T00:00:00Z",
                        "normalized_lineage": {"normalized_record_id": "record-1", "artifact_id": "artifact-1"},
                        "third_party_conversation": {"actual_sender": "Alex", "actual_recipients": ["Taylor"]},
                        "realization_events": [{"id": "event-1"}],
                    }
                ]
            }
        return {
            "artifact_id": "artifact-1",
            "source_sha256": "b" * 64,
            "source_ref": "custody/messages.xml",
            "matter_id": "matter-9",
            "record_count": 1,
            "chunk_count": 1,
            "chunks": [{"chunk_id": "chunk-1", "normalized_record_id": "record-1"}],
            "records": [
                {
                    "record_id": "record-1",
                    "domain": "evidence",
                    "attrs": {
                        "source_name": "messages.xml",
                        "source_path": "/staged/messages.xml",
                        "parser_id": "sbv.messages",
                        "chunker_id": "chonkie.semantic@1.7.0",
                        "lane": "evidence",
                    },
                }
            ],
        }

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.get_content("artifact-1", case_id="matter-9")

    assert captured[0] == {
        "method": "GET",
        "path": "/v1/knowledge/items/artifact-1",
        "kwargs": {"params": {"matter_id": "matter-9"}},
    }
    assert captured[1] == {
        "method": "GET",
        "path": "/v1/records",
        "kwargs": {"params": {"artifact_id": "artifact-1", "limit": 1000, "offset": 0}},
    }
    assert result["source_name"] == "messages.xml"
    assert result["parser_id"] == "sbv.messages"
    assert result["chunker_id"] == "chonkie.semantic@1.7.0"
    assert result["lane"] == "evidence"
    assert result["records"][0]["source_kind"] == "third_party_acquired"
    assert result["records"][0]["realization_events"] == [{"id": "event-1"}]
    assert result["chunks"][0]["chunk_id"] == "chunk-1"


def test_get_content_paginates_all_projection_rows(monkeypatch):
    calls = []

    def fake_spine_json(method, path, **kwargs):
        calls.append((path, kwargs.get("params")))
        if path.startswith("/v1/knowledge/items/"):
            return {
                "artifact_id": "artifact-many",
                "source_ref": "source",
                "source_sha256": "c" * 64,
                "matter_id": "primary",
                "record_count": 1,
                "chunk_count": 0,
                "chunks": [],
                "records": [{"record_id": "target", "artifact_id": "artifact-many", "attrs": {}}],
            }
        offset = kwargs["params"]["offset"]
        if offset == 0:
            return {"total": 1001, "records": [{"id": f"r-{index}"} for index in range(1000)]}
        return {
            "total": 1001,
            "records": [
                {
                    "id": "target",
                    "source_kind": "third_party_acquired",
                    "projection_kind": "derived_third_party",
                    "source_available_from": None,
                    "normalized_lineage": {"normalized_record_id": "target", "artifact_id": "artifact-many"},
                    "third_party_conversation": None,
                    "realization_events": [],
                }
            ],
        }

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)

    result = knowledge.get_content("artifact-many", case_id="primary")

    assert calls[-1][1]["offset"] == 1000
    assert result["records"][0]["source_kind"] == "third_party_acquired"
    assert result["records"][0]["projection_kind"] == "derived_third_party"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"case_id": " ", "lane": "legal"}, "case_id must be a non-empty string"),
        ({"case_id": "primary", "lane": "unknown"}, "unsupported knowledge lane"),
        ({"case_id": "primary", "lane": "legal", "offset": -1}, "offset must be"),
    ],
)
def test_list_contents_rejects_unsafe_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        knowledge.list_contents(**kwargs)
