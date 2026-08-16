"""Contract and streaming tests for the neutral Portkey chat route.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, MockTransport, Request, Response
import pytest

from app.runtime import chat
from app.service import chat_gateway
from app.types.chat import ChatRequest


def _request() -> ChatRequest:
    return ChatRequest.model_validate(
        {
            "messages": [
                {"id": "u1", "role": "user", "parts": [{"type": "text", "text": "Hello"}]},
                {"id": "a1", "role": "assistant", "parts": [{"type": "text", "text": "Hi"}]},
                {"id": "u2", "role": "user", "parts": [{"type": "text", "text": "Continue"}]},
            ],
            "context": {"page": "runs"},
        }
    )


@pytest.mark.asyncio
async def test_portkey_stream_has_fallback_trace_audit_and_text_deltas(monkeypatch) -> None:
    monkeypatch.setattr(chat_gateway.settings, "portkey_api_key", "pk-test")
    monkeypatch.setattr(chat_gateway.settings, "portkey_config", "fallback-config")
    monkeypatch.setattr(chat_gateway.settings, "portkey_environment", "test")
    monkeypatch.setattr(chat_gateway.settings, "portkey_base_url", "https://gateway.test/v1")

    def handler(request: Request) -> Response:
        assert request.url == "https://gateway.test/v1/chat/completions"
        assert request.headers["x-portkey-api-key"] == "pk-test"
        assert request.headers["x-portkey-config"] == "fallback-config"
        assert request.headers["x-portkey-trace-id"]
        metadata = json.loads(request.headers["x-portkey-metadata"])
        assert metadata == {
            "_user": "owner",
            "_environment": "test",
            "surface": "horizon-workbench",
            "route": "v1-chat",
        }
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert "model" not in payload
        assert payload["messages"][0]["role"] == "system"
        assert "runs" in payload["messages"][0]["content"]
        assert [message["content"] for message in payload["messages"][1:]] == ["Hello", "Hi", "Continue"]
        return Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"world"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    async with AsyncClient(transport=MockTransport(handler)) as client:
        chunks, trace_id = await chat_gateway.open_chat_stream(_request(), principal="owner", client=client)
        text = "".join([chunk async for chunk in chunks])

    assert text == "Hello world"
    assert trace_id


@pytest.mark.asyncio
async def test_portkey_route_fails_closed_without_saved_fallback_config(monkeypatch) -> None:
    monkeypatch.setattr(chat_gateway.settings, "portkey_api_key", "pk-test")
    monkeypatch.setattr(chat_gateway.settings, "portkey_config", "")

    with pytest.raises(chat_gateway.ChatGatewayError) as caught:
        await chat_gateway.open_chat_stream(_request(), principal="owner")

    assert caught.value.status_code == 503
    assert "fallback config" in caught.value.detail


@pytest.mark.asyncio
async def test_v1_route_returns_ai_sdk_plain_text_stream(monkeypatch) -> None:
    async def fake_stream(body: ChatRequest, *, principal: str):
        assert body.messages[-1].text_content() == "Continue"
        assert principal == "owner"

        async def chunks():
            yield "streamed "
            yield "reply"

        return chunks(), "trace-123"

    monkeypatch.setattr(chat, "open_chat_stream", fake_stream)
    app = FastAPI()
    app.include_router(chat.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/chat", json=_request().model_dump(mode="json"))

    assert response.status_code == 200
    assert response.text == "streamed reply"
    assert response.headers["x-horizon-model-route"] == "portkey"
    assert response.headers["x-portkey-trace-id"] == "trace-123"


def test_public_chat_contract_has_no_framework_or_legacy_copilot_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    sources = "\n".join(
        (root / relative).read_text(encoding="utf-8").lower()
        for relative in ("types/chat.py", "service/chat_gateway.py", "runtime/chat.py")
    )
    for forbidden in ("import agno", "import opencode", "import graphiti", "import surreal", "agentos"):
        assert forbidden not in sources
