"""Workbench run-event HTTP surface tests.

Byline: Codex · GPT-5 · 2026-08-27
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.runtime import auth
from app.runtime import run_events as runtime
from main import app as workbench_app

RUN_ID = "00000000-0000-0000-0000-000000000008"


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(runtime.router)
    return app


def test_runtime_forwards_reconnect_cursor_and_streams(monkeypatch) -> None:
    captured = {}

    async def fake_open(run_id: UUID, **kwargs):
        captured["run_id"] = run_id
        captured.update(kwargs)

        async def stream():
            yield b"id: 8\nevent: run-event\ndata: {}\n\n"

        return stream()

    monkeypatch.setattr(runtime, "open_run_event_stream", fake_open)
    response = TestClient(_app()).get(
        f"/api/runs/{RUN_ID}/events?after=3&follow=false&limit=50",
        headers={"Last-Event-ID": "7"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.text.startswith("id: 8")
    assert captured == {
        "run_id": UUID(RUN_ID),
        "last_event_id": 7,
        "after": 3,
        "follow": False,
        "limit": 50,
    }


def test_runtime_rejects_invalid_cursor_before_upstream() -> None:
    response = TestClient(_app()).get(
        f"/api/runs/{RUN_ID}/events",
        headers={"Last-Event-ID": "-1"},
    )

    assert response.status_code == 422


def test_runtime_preserves_upstream_failure(monkeypatch) -> None:
    async def fake_open(*args, **kwargs):
        raise runtime.RunEventsError("run not found", 404)

    monkeypatch.setattr(runtime, "open_run_event_stream", fake_open)
    response = TestClient(_app()).get(f"/api/runs/{RUN_ID}/events")

    assert response.status_code == 404
    assert response.json() == {"detail": "run not found"}


def test_real_app_registers_route_behind_workbench_auth(monkeypatch) -> None:
    async def fake_open(*args, **kwargs):
        async def stream():
            yield b": keep-alive\n\n"

        return stream()

    monkeypatch.setattr(runtime, "open_run_event_stream", fake_open)
    monkeypatch.setattr(auth.settings, "workbench_api_key", "workbench-test-key")
    client = TestClient(workbench_app)
    path = f"/api/runs/{RUN_ID}/events?follow=false"

    assert client.get(path).status_code == 401
    response = client.get(path, headers={"Authorization": "Bearer workbench-test-key"})

    assert response.status_code == 200
    assert response.text == ": keep-alive\n\n"
