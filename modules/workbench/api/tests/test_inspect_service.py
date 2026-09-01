# Byline: Codex · GPT-5 · 2026-08-16 (neutral Data Explorer proxy coverage)
# Byline: Codex · GPT-5 · 2026-08-18 (record projection compatibility coverage)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (third-party review proxy coverage)
# Byline: Codex · GPT-5 · 2026-08-18 (governed entity proxy coverage)
"""Unit coverage for PostgreSQL and Weaviate Data Explorer proxy paths."""

from __future__ import annotations

from app.service import inspect


def test_list_records_adds_fail_closed_projection_defaults(monkeypatch):
    monkeypatch.setattr(
        inspect,
        "spine_json",
        lambda *args, **kwargs: {"records": [{"id": "r1", "artifact_id": "a1", "seq": 2}]},
    )

    result = inspect.list_records(artifact_id="a1")

    row = result["records"][0]
    assert row["idx"] == 2
    assert row["source_kind"] == "unclassified"
    assert row["realization_events"] == []
    assert row["normalized_lineage"] == {"normalized_record_id": "r1", "artifact_id": "a1"}
    assert row["third_party_review"] is None


def test_approve_third_party_conversation_forwards_exact_review(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {"reprojection": {"status": "replay_pending", "reason": "projector unavailable"}}

    monkeypatch.setattr(inspect, "spine_json", fake_spine_json)
    review = {
        "sender_entity_ids": {"message-1": "entity-1"},
        "participant_entity_ids": {"participant-1": "entity-2"},
        "reason": "manual comparison",
    }
    result = inspect.approve_third_party_conversation("conversation-1", review)

    assert result["reprojection"]["status"] == "replay_pending"
    assert captured == {
        "method": "POST",
        "path": "/v1/third-party-conversations/conversation-1/approve",
        "kwargs": {"json": review},
    }


def test_governed_entities_forward_search_and_create(monkeypatch):
    calls = []
    monkeypatch.setattr(
        inspect, "spine_json", lambda method, path, **kwargs: calls.append((method, path, kwargs)) or {}
    )

    inspect.list_entities(query="Alex", limit=7)
    inspect.create_entity({"display_name": "Alex", "entity_type": "person"})

    assert calls == [
        ("GET", "/v1/entities", {"params": {"limit": 7, "q": "Alex"}}),
        ("POST", "/v1/entities", {"json": {"display_name": "Alex", "entity_type": "person"}}),
    ]


def test_table_detail_uses_neutral_spine_route(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {"schema": "working", "table": "normalized_record", "rows": []}

    monkeypatch.setattr(inspect, "spine_json", fake_spine_json)
    result = inspect.get_table_detail("working", "normalized_record", limit=7)

    assert result["table"] == "normalized_record"
    assert result["authority"] == "authored"
    assert captured == {
        "method": "GET",
        "path": "/v1/inspect/tables/working/normalized_record",
        "kwargs": {"params": {"limit": 7}},
    }


def test_schema_catalog_labels_mixed_postgresql_authority(monkeypatch):
    def fake_spine_json(method, path, **kwargs):
        assert method == "GET"
        assert path == "/v1/inspect/schemas"
        return {
            "pg": {
                "evidence": [{"table": "source", "columns": []}],
                "working": [
                    {"table": "normalized_record", "columns": []},
                    {"table": "third_party_message", "columns": []},
                    {"table": "third_party_conversation_acquisition", "columns": []},
                    {"table": "message_projection_route", "columns": []},
                ],
            },
            "weaviate": [],
        }

    monkeypatch.setattr(inspect, "spine_json", fake_spine_json)

    result = inspect.get_schemas()

    assert result["pg"]["evidence"][0]["authority"] == "authored"
    assert result["pg"]["working"][0]["authority"] == "authored"
    assert result["pg"]["working"][1]["authority"] == "derived"
    assert result["pg"]["working"][2]["authority"] == "audit-control"
    assert result["pg"]["working"][3]["authority"] == "audit-control"


def test_vector_detail_uses_neutral_spine_route(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {"collection": "Platform_knowledge", "objects": []}

    monkeypatch.setattr(inspect, "spine_json", fake_spine_json)
    result = inspect.get_vector_detail("Platform_knowledge", limit=3)

    assert result["collection"] == "Platform_knowledge"
    assert captured == {
        "method": "GET",
        "path": "/v1/inspect/weaviate/Platform_knowledge",
        "kwargs": {"params": {"limit": 3}},
    }
