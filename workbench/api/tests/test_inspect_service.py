# Byline: Codex · GPT-5 · 2026-08-16 (neutral Data Explorer proxy coverage)
"""Unit coverage for PostgreSQL and Weaviate Data Explorer proxy paths."""

from __future__ import annotations

from app.service import inspect


def test_table_detail_uses_neutral_spine_route(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {"schema": "working", "table": "normalized_record", "rows": []}

    monkeypatch.setattr(inspect, "spine_json", fake_spine_json)
    result = inspect.get_table_detail("working", "normalized_record", limit=7)

    assert result["table"] == "normalized_record"
    assert captured == {
        "method": "GET",
        "path": "/v1/inspect/tables/working/normalized_record",
        "kwargs": {"params": {"limit": 7}},
    }


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
