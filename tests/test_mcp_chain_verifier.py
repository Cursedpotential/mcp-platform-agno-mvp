"""Tests for read-only ContextForge -> Portkey MCP publication parity.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from server.tools.gateway.mcp_chain import (
    McpChainError,
    compare_catalogs,
    list_tools,
    load_manifest,
    validate_endpoints,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "deploy/docker/gateway/mcp/publications.json"


def _tool(name: str, *, description: str = "tool") -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    }


def test_manifest_locks_one_way_contextforge_to_portkey_authority() -> None:
    publications = load_manifest(MANIFEST)

    assert [publication.key for publication in publications] == ["platform-tools"]
    publication = publications[0]
    assert publication.publication_mode == "source_exact"
    assert publication.require_adr0046_annotations is True
    assert publication.require_trace_correlation is True
    raw = MANIFEST.read_text(encoding="utf-8")
    assert "http://" not in raw and "https://" not in raw
    assert '"token":' not in raw.lower()
    assert '"api_key":' not in raw.lower()


def test_endpoint_validation_rejects_bare_contextforge_gateway() -> None:
    with pytest.raises(McpChainError, match="virtual-server UUID"):
        validate_endpoints("https://contextforge.example/mcp", "https://mcp.portkey.ai/platform/mcp")


def test_exact_annotated_catalogs_pass() -> None:
    tools = [_tool("search_tools"), _tool("describe_tool")]

    report = compare_catalogs("platform-tools", tools, tools)

    assert report.ok is True
    assert report.source_count == 2
    assert report.to_dict()["ok"] is True


def test_missing_extra_contract_drift_and_annotations_fail() -> None:
    source = [_tool("search_tools"), _tool("describe_tool")]
    downstream = [
        _tool("search_tools", description="changed"),
        {"name": "rogue_tool", "inputSchema": {}, "annotations": {}},
    ]

    report = compare_catalogs("platform-tools", source, downstream)

    assert report.ok is False
    assert report.missing_downstream == ("describe_tool",)
    assert report.unexpected_downstream == ("rogue_tool",)
    assert report.contract_drift == ("search_tools",)
    assert any(item.startswith("portkey:rogue_tool:") for item in report.annotation_violations)


def test_mcp_client_performs_only_handshake_and_tools_list() -> None:
    methods: list[str] = []
    params: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        methods.append(body["method"])
        params.append(body["params"])
        if body["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "session-1"},
                json={"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": "2025-06-18"}},
            )
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        if body["params"] == {}:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"tools": [_tool("search_tools")], "nextCursor": "page-2"},
                },
            )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"tools": [_tool("describe_tool")]}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        tools = list_tools(
            "https://contextforge.example/servers/server-id/mcp",
            {"Authorization": "Bearer redacted"},
            client=client,
        )

    assert [tool["name"] for tool in tools] == ["search_tools", "describe_tool"]
    assert methods == ["initialize", "notifications/initialized", "tools/list", "tools/list"]
    assert params[-2:] == [{}, {"cursor": "page-2"}]


def test_mcp_client_rejects_cursor_loops_and_duplicate_names() -> None:
    def loop_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 0, "result": {}})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": [], "nextCursor": "same"}},
        )

    with httpx.Client(transport=httpx.MockTransport(loop_handler)) as client:
        with pytest.raises(McpChainError, match="cursor loop"):
            list_tools("https://example.test/servers/id/mcp", {}, client=client)

    def duplicate_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 0, "result": {}})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": {"tools": [_tool("same"), _tool("same")]}},
        )

    with httpx.Client(transport=httpx.MockTransport(duplicate_handler)) as client:
        with pytest.raises(McpChainError, match="duplicate tool names"):
            list_tools("https://example.test/servers/id/mcp", {}, client=client)


def test_verifier_source_contains_no_registration_or_tool_call_rpc() -> None:
    source = (ROOT / "server/tools/gateway/mcp_chain.py").read_text(encoding="utf-8")
    assert '"tools/call"' not in source
    assert '"gateways/create"' not in source
    assert '"servers/create"' not in source
