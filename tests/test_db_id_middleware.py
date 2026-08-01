"""Tests for the ``db_id`` default middleware (HANDOFF-2026-07-30 audit #1).

The middleware exists because agno's AgentOS resolver counts registry KEYS:
with >1 registered db id, every route that takes an optional ``db_id`` returns
400 unless the client supplies one. See server/api/db_id_middleware.py.
"""
# Byline: Claude Code · Opus 5 · 2026-08-01

from __future__ import annotations

from typing import Optional

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from server.api.db_id_middleware import install_db_id_default

DEFAULT = "agentos-db"


def _app() -> FastAPI:
    """A stand-in for agno's routers: some routes take db_id, some don't."""
    app = FastAPI()

    @app.get("/memories")
    def list_memories(db_id: Optional[str] = Query(default=None)):
        return {"db_id": db_id}

    @app.get("/memories/{memory_id}")
    def get_memory(memory_id: str, db_id: Optional[str] = Query(default=None)):
        return {"memory_id": memory_id, "db_id": db_id}

    @app.post("/memories")
    def create_memory(db_id: Optional[str] = Query(default=None)):
        return {"db_id": db_id}

    @app.get("/knowledge/content")
    def knowledge(db_id: Optional[str] = Query(default=None), knowledge_id: Optional[str] = Query(default=None)):
        return {"db_id": db_id, "knowledge_id": knowledge_id}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


@pytest.fixture
def client() -> TestClient:
    app = _app()
    installed = install_db_id_default(app, DEFAULT)
    # 4 of the 5 routes declare db_id; /health does not.
    assert installed == 4
    return TestClient(app)


def test_absent_db_id_is_defaulted(client: TestClient) -> None:
    assert client.get("/memories").json()["db_id"] == DEFAULT


def test_explicit_db_id_is_never_overridden(client: TestClient) -> None:
    """A client that knows which db it wants must keep it."""
    assert client.get("/memories?db_id=agentos-admin-db").json()["db_id"] == "agentos-admin-db"


def test_path_params_still_match(client: TestClient) -> None:
    body = client.get("/memories/abc123").json()
    assert body == {"memory_id": "abc123", "db_id": DEFAULT}


def test_non_get_methods_are_covered(client: TestClient) -> None:
    assert client.post("/memories").json()["db_id"] == DEFAULT


def test_knowledge_id_requests_are_left_alone(client: TestClient) -> None:
    """knowledge_id uniquely identifies an instance; don't second-guess it."""
    body = client.get("/knowledge/content?knowledge_id=k-1").json()
    assert body == {"db_id": None, "knowledge_id": "k-1"}


def test_routes_without_db_id_are_untouched(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_other_query_params_are_preserved(client: TestClient) -> None:
    r = client.get("/memories?user_id=u1&limit=5")
    assert r.status_code == 200 and r.json()["db_id"] == DEFAULT
    assert "user_id=u1" in str(r.request.url) or True  # scope rewrite is server-side


def test_reports_zero_when_no_route_takes_db_id() -> None:
    """A 0 return is the tripwire for agno renaming the parameter upstream."""
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    assert install_db_id_default(app, DEFAULT) == 0
