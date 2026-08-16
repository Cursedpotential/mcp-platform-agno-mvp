# Byline: Codex · GPT-5 · 2026-08-16 (Data Explorer HTTP boundary coverage)
"""HTTP contract coverage for bounded Data Explorer detail routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.runtime import inspect as runtime


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(runtime.router)
    return TestClient(app)


def test_table_detail_forwards_bounded_request(monkeypatch):
    captured = {}

    def fake_detail(schema, table_name, **kwargs):
        captured.update(schema=schema, table_name=table_name, **kwargs)
        return {"schema": schema, "table": table_name, "rows": []}

    monkeypatch.setattr(runtime.inspect_service, "get_table_detail", fake_detail)
    response = _client().get("/api/schemas/postgresql/working/normalized_record", params={"limit": 8})

    assert response.status_code == 200
    assert captured == {"schema": "working", "table_name": "normalized_record", "limit": 8}


def test_vector_detail_forwards_bounded_request(monkeypatch):
    captured = {}

    def fake_detail(collection_name, **kwargs):
        captured.update(collection_name=collection_name, **kwargs)
        return {"collection": collection_name, "objects": []}

    monkeypatch.setattr(runtime.inspect_service, "get_vector_detail", fake_detail)
    response = _client().get("/api/schemas/weaviate/Platform_knowledge", params={"limit": 4})

    assert response.status_code == 200
    assert captured == {"collection_name": "Platform_knowledge", "limit": 4}


def test_data_explorer_limits_fail_closed_before_spine():
    client = _client()
    assert client.get("/api/schemas/postgresql/working/normalized_record", params={"limit": 26}).status_code == 422
    assert client.get("/api/schemas/weaviate/Platform_knowledge", params={"limit": 11}).status_code == 422
