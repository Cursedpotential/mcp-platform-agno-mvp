"""Workbench run-event proxy contract tests.

Byline: Codex · GPT-5 · 2026-08-27
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import httpx

from app.service import run_events

RUN_ID = UUID("00000000-0000-0000-0000-000000000008")


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content_type: str = "text/event-stream; charset=utf-8",
        lines: list[str] | None = None,
        body: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._lines = lines or []
        self._body = body
        self.closed = False

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return self._body

    async def aclose(self) -> None:
        self.closed = True


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.request: httpx.Request | None = None

    def build_request(self, method: str, url: str, **kwargs) -> httpx.Request:
        self.request = httpx.Request(method, url, **kwargs)
        return self.request

    async def send(self, request: httpx.Request, *, stream: bool) -> _FakeResponse:
        assert stream is True
        assert request is self.request
        return self.response


async def _collect(stream) -> bytes:
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return b"".join(chunks)


def test_stream_injects_platform_auth_forwards_cursor_and_normalizes_dispatch(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(run_events.settings, "platform_api_url", "https://platform.internal/")
    secret = tmp_path / "os-security-key"
    secret.write_bytes(b"server-only-token")
    monkeypatch.setattr(run_events.settings, "platform_api_bearer_secret_file", str(secret))
    response = _FakeResponse(
        lines=[
            "id: 42",
            "event: stage.completed",
            'data: {"sequence":42,"event_type":"stage.completed"}',
            "",
            ": keep-alive",
            "",
        ]
    )
    client = _FakeClient(response)

    async def exercise() -> bytes:
        stream = await run_events.open_run_event_stream(
            RUN_ID,
            last_event_id=41,
            after=12,
            follow=True,
            limit=100,
            client=client,  # type: ignore[arg-type]
        )
        return await _collect(stream)

    payload = asyncio.run(exercise())

    assert client.request is not None
    assert str(client.request.url).startswith(
        "https://platform.internal/v1/runs/00000000-0000-0000-0000-000000000008/events?"
    )
    assert client.request.url.params["after"] == "12"
    assert client.request.url.params["follow"] == "true"
    assert client.request.url.params["limit"] == "100"
    assert client.request.headers["authorization"] == "Bearer server-only-token"
    assert client.request.headers["last-event-id"] == "41"
    assert b"event: run-event\n" in payload
    assert b'"event_type":"stage.completed"' in payload
    assert b"id: 42\n" in payload
    assert b": keep-alive\n\n" in payload
    assert response.closed is True


def test_stream_preserves_upstream_status_and_detail(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(run_events.settings, "platform_api_url", "https://platform.internal")
    secret = tmp_path / "os-security-key"
    secret.write_bytes(b"server-only-token")
    monkeypatch.setattr(run_events.settings, "platform_api_bearer_secret_file", str(secret))
    response = _FakeResponse(status_code=404, body=b'{"detail":"run not found"}')

    async def exercise() -> None:
        await run_events.open_run_event_stream(RUN_ID, client=_FakeClient(response))  # type: ignore[arg-type]

    try:
        asyncio.run(exercise())
    except run_events.RunEventsError as error:
        assert error.status_code == 404
        assert error.detail == "run not found"
    else:
        raise AssertionError("upstream error was not translated")
    assert response.closed is True


def test_stream_rejects_non_sse_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(run_events.settings, "platform_api_url", "https://platform.internal")
    secret = tmp_path / "os-security-key"
    secret.write_bytes(b"server-only-token")
    monkeypatch.setattr(run_events.settings, "platform_api_bearer_secret_file", str(secret))
    response = _FakeResponse(content_type="application/json")

    async def exercise() -> None:
        await run_events.open_run_event_stream(RUN_ID, client=_FakeClient(response))  # type: ignore[arg-type]

    try:
        asyncio.run(exercise())
    except run_events.RunEventsError as error:
        assert error.status_code == 502
        assert "non-SSE" in error.detail
    else:
        raise AssertionError("non-SSE upstream response was accepted")
    assert response.closed is True
