# Byline: Claude Code · Sonnet (agent) · 2026-07-20
"""Minimal MCP streamable-HTTP JSON-RPC client (httpx-based).

Speaks just enough of the MCP streamable-HTTP transport (spec 2025-06-18) to
list and call tools against any compliant server: POST JSON-RPC 2.0
envelopes to a single URL, honor the `Mcp-Session-Id` response header for
the lifetime of one client, and tolerate either a plain `application/json`
response or a `text/event-stream` (SSE) response — the transport allows
either per POST. This is NOT a general MCP SDK: no resources/prompts/
sampling, no persistent session reuse across separate list_tools/call_tool
invocations, no reconnect/resume. Good enough for a read-mostly Tool
Explorer proxy — every public call here does its own initialize handshake.

Never imports app.service/app.runtime (repo is the lowest SDK-touching
layer — see tests/test_structure.py).
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 120.0
_PROTOCOL_VERSION = "2025-06-18"
_ACCEPT_HEADER = "application/json, text/event-stream"


class McpError(Exception):
    """Raised when an MCP call fails — transport error or JSON-RPC error object."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _parse_body(response: httpx.Response) -> dict:
    """Parse either a JSON body or an SSE (`text/event-stream`) body.

    Streamable-HTTP servers may answer a POST with either content type. For
    SSE, each `data:` line is one JSON-RPC message; for a single-request POST
    the LAST parseable one is the actual response (earlier ones, if any, are
    transport-level noise/progress notifications).
    """
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        return response.json()

    data_lines = [
        line[len("data:") :].strip()
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]
    if not data_lines:
        raise McpError("Empty SSE response from MCP server")

    last_error: Exception | None = None
    for line in reversed(data_lines):
        try:
            return json.loads(line)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            continue
    raise McpError(f"Could not parse SSE data as JSON: {last_error}")


def _rpc(
    client: httpx.Client,
    url: str,
    method: str,
    params: dict,
    request_id: int | None,
    session_id: str | None,
    extra_headers: dict[str, str] | None,
) -> tuple[dict | None, str | None]:
    """POST one JSON-RPC envelope. Returns (result, session_id).

    `result` is None for notifications (request_id is None) — no response
    body is expected for those regardless of HTTP status.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": _ACCEPT_HEADER,
        "MCP-Protocol-Version": _PROTOCOL_VERSION,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if extra_headers:
        headers.update(extra_headers)

    body: dict = {"jsonrpc": "2.0", "method": method, "params": params}
    if request_id is not None:
        body["id"] = request_id

    try:
        response = client.post(url, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise McpError(f"MCP request to {url} failed: {e}") from e

    new_session_id = response.headers.get("Mcp-Session-Id") or session_id

    if request_id is None:
        return None, new_session_id

    if response.status_code >= 400:
        raise McpError(
            f"MCP server {url} returned HTTP {response.status_code}: {response.text[:500]}"
        )

    envelope = _parse_body(response)
    error = envelope.get("error")
    if error:
        raise McpError(f"MCP error {error.get('code')}: {error.get('message')}")
    return envelope.get("result", {}), new_session_id


def _handshake(
    client: httpx.Client, url: str, headers: dict[str, str] | None
) -> str | None:
    """initialize -> notifications/initialized. Returns the session id, if any."""
    _, session_id = _rpc(
        client,
        url,
        "initialize",
        {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "knowledge-workbench", "version": "0.1.0"},
        },
        request_id=0,
        session_id=None,
        extra_headers=headers,
    )
    try:
        _rpc(
            client,
            url,
            "notifications/initialized",
            {},
            request_id=None,
            session_id=session_id,
            extra_headers=headers,
        )
    except McpError:
        # Best-effort courtesy notification; some servers gate tools/list on
        # it, others don't implement it at all. Either way, keep going.
        logger.debug("notifications/initialized refused by %s (continuing)", url, exc_info=True)
    return session_id


def list_tools(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> list[dict]:
    """initialize -> tools/list. Returns the raw `tools` array from the server."""
    with httpx.Client(timeout=timeout) as client:
        session_id = _handshake(client, url, headers)
        result, _ = _rpc(client, url, "tools/list", {}, 1, session_id, headers)
    return (result or {}).get("tools", [])


def call_tool(
    url: str,
    name: str,
    arguments: dict,
    headers: dict[str, str] | None = None,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> dict:
    """initialize -> tools/call {name, arguments}. Returns the raw result object."""
    with httpx.Client(timeout=timeout) as client:
        session_id = _handshake(client, url, headers)
        result, _ = _rpc(
            client,
            url,
            "tools/call",
            {"name": name, "arguments": arguments},
            1,
            session_id,
            headers,
        )
    return result or {}
