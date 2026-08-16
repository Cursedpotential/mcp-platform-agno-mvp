"""Portkey-routed streaming adapter for the neutral Workbench chat contract.

No framework model object crosses this boundary. Portkey owns provider routing,
fallback, and model-call audit through a required saved gateway config.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any
from uuid import uuid4

import httpx

from app.config import settings
from app.service.chat_context import build_preamble
from app.types.chat import ChatRequest


class ChatGatewayError(Exception):
    """Fail-closed configuration or upstream gateway error."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _gateway_messages(body: ChatRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    context = body.context.model_dump(exclude_none=True) if body.context else None
    preamble = build_preamble(context)
    if preamble:
        messages.append({"role": "system", "content": preamble})
    for message in body.messages:
        content = message.text_content()
        if content:
            messages.append({"role": message.role, "content": content})
    if not any(message["role"] == "user" for message in messages):
        raise ChatGatewayError("at least one non-empty user message is required", 422)
    return messages


def _gateway_headers(trace_id: str, principal: str) -> dict[str, str]:
    if not settings.portkey_api_key:
        raise ChatGatewayError("Portkey authentication is not configured", 503)
    if not settings.portkey_config:
        raise ChatGatewayError("Portkey fallback config is not configured", 503)
    metadata = {
        "_user": principal,
        "_environment": settings.portkey_environment,
        "surface": "horizon-workbench",
        "route": "v1-chat",
    }
    return {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "x-portkey-api-key": settings.portkey_api_key,
        "x-portkey-config": settings.portkey_config,
        "x-portkey-trace-id": trace_id,
        "x-portkey-metadata": json.dumps(metadata, separators=(",", ":")),
    }


def _delta_from_sse(line: str) -> str:
    if not line.startswith("data:"):
        return ""
    payload = line.removeprefix("data:").strip()
    if not payload or payload == "[DONE]":
        return ""
    try:
        event: dict[str, Any] = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ChatGatewayError("Portkey returned an invalid streaming event") from error
    choices = event.get("choices") or []
    if not choices:
        return ""
    content = (choices[0].get("delta") or {}).get("content")
    return content if isinstance(content, str) else ""


async def open_chat_stream(
    body: ChatRequest,
    *,
    principal: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[AsyncIterator[str], str]:
    """Open Portkey before returning HTTP headers, then expose text deltas."""
    trace_id = str(uuid4())
    headers = _gateway_headers(trace_id, principal)
    payload: dict[str, Any] = {
        "messages": _gateway_messages(body),
        "stream": True,
    }
    if body.model:
        payload["model"] = body.model

    owned_client = client is None
    active_client = client or httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=15.0))
    url = f"{settings.portkey_base_url.rstrip('/')}/chat/completions"
    request = active_client.build_request("POST", url, headers=headers, json=payload)
    try:
        response = await active_client.send(request, stream=True)
    except httpx.HTTPError as error:
        if owned_client:
            await active_client.aclose()
        raise ChatGatewayError(f"Portkey is unreachable: {error}") from error

    if not response.is_success:
        detail = (await response.aread()).decode("utf-8", errors="replace")[:500]
        await response.aclose()
        if owned_client:
            await active_client.aclose()
        raise ChatGatewayError(f"Portkey rejected the chat request ({response.status_code}): {detail}")

    async def deltas() -> AsyncIterator[str]:
        try:
            async for line in response.aiter_lines():
                delta = _delta_from_sse(line)
                if delta:
                    yield delta
        finally:
            await response.aclose()
            if owned_client:
                await active_client.aclose()

    return deltas(), trace_id
