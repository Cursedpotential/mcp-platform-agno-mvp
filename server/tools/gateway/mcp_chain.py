"""Read-only ContextForge-to-Portkey MCP publication verification.

ContextForge is the authored registry. Portkey is a downstream access-control,
audit, and trace gateway. This module only performs MCP initialize/tools-list;
it has no registration, mutation, or tool-invocation operation.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

_PROTOCOL_VERSION = "2025-06-18"
_ACCEPT = "application/json, text/event-stream"
_REQUIRED_ANNOTATIONS = ("readOnlyHint", "destructiveHint", "idempotentHint")


class McpChainError(RuntimeError):
    """Invalid manifest, endpoint, or MCP catalog response."""


@dataclass(frozen=True)
class Publication:
    """One ContextForge virtual server published through one Portkey slug."""

    key: str
    source_url_env: str
    source_token_env: str
    downstream_url_env: str
    downstream_token_env: str
    publication_mode: str
    require_adr0046_annotations: bool
    require_trace_correlation: bool


@dataclass(frozen=True)
class ChainReport:
    """Secret-free parity result for one publication."""

    publication: str
    source_count: int
    downstream_count: int
    missing_downstream: tuple[str, ...]
    unexpected_downstream: tuple[str, ...]
    contract_drift: tuple[str, ...]
    annotation_violations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (
            self.missing_downstream or self.unexpected_downstream or self.contract_drift or self.annotation_violations
        )

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok}


def load_manifest(path: Path) -> list[Publication]:
    """Load and validate the one-way publication manifest."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise McpChainError(f"cannot load MCP publication manifest: {error}") from error
    if document.get("schema_version") != 1:
        raise McpChainError("MCP publication manifest schema_version must be 1")
    if document.get("registry_authority") != "contextforge":
        raise McpChainError("ContextForge must remain the registry authority")
    if document.get("audit_gateway") != "portkey":
        raise McpChainError("Portkey must remain the downstream audit gateway")
    publications = document.get("publications")
    if not isinstance(publications, list) or not publications:
        raise McpChainError("MCP publication manifest needs at least one publication")
    try:
        loaded = [Publication(**item) for item in publications]
    except (TypeError, KeyError) as error:
        raise McpChainError(f"invalid MCP publication entry: {error}") from error
    if len({item.key for item in loaded}) != len(loaded):
        raise McpChainError("MCP publication keys must be unique")
    for item in loaded:
        if item.publication_mode != "source_exact":
            raise McpChainError(f"{item.key}: only source_exact publication is currently sanctioned")
        if item.require_adr0046_annotations is not True:
            raise McpChainError(f"{item.key}: ADR-0046 annotations must be required")
        if item.require_trace_correlation is not True:
            raise McpChainError(f"{item.key}: trace correlation must be required")
        for env_name in (
            item.source_url_env,
            item.source_token_env,
            item.downstream_url_env,
            item.downstream_token_env,
        ):
            if not env_name or env_name.upper() != env_name:
                raise McpChainError(f"{item.key}: credential and URL references must be uppercase env names")
    return loaded


def validate_endpoints(source_url: str, downstream_url: str) -> None:
    """Reject bare gateways and accidental same-endpoint configurations."""
    if not source_url.rstrip("/").endswith("/mcp"):
        raise McpChainError("ContextForge source must be an exact /servers/<uuid>/mcp endpoint")
    if "/servers/" not in source_url:
        raise McpChainError("ContextForge source must name a virtual-server UUID")
    if not downstream_url.rstrip("/").endswith("/mcp"):
        raise McpChainError("Portkey downstream must be an exact /<server-slug>/mcp endpoint")
    if source_url.rstrip("/") == downstream_url.rstrip("/"):
        raise McpChainError("ContextForge source and Portkey downstream must be distinct endpoints")


def _parse_response(response: httpx.Response) -> dict[str, Any]:
    if "text/event-stream" not in response.headers.get("content-type", ""):
        return response.json()
    for line in reversed(response.text.splitlines()):
        if line.startswith("data:"):
            try:
                return json.loads(line.removeprefix("data:").strip())
            except json.JSONDecodeError:
                continue
    raise McpChainError("MCP endpoint returned no parseable SSE data")


def _rpc(
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    method: str,
    params: dict[str, Any],
    request_id: int | None,
    session_id: str | None,
) -> tuple[dict[str, Any], str | None]:
    request_headers = {
        "Accept": _ACCEPT,
        "Content-Type": "application/json",
        "MCP-Protocol-Version": _PROTOCOL_VERSION,
        **headers,
    }
    if session_id:
        request_headers["Mcp-Session-Id"] = session_id
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
    if request_id is not None:
        payload["id"] = request_id
    try:
        response = client.post(url, headers=request_headers, json=payload)
    except httpx.HTTPError as error:
        raise McpChainError(f"MCP catalog request failed: {error}") from error
    if response.status_code >= 400:
        raise McpChainError(f"MCP catalog endpoint returned HTTP {response.status_code}")
    next_session = response.headers.get("Mcp-Session-Id") or session_id
    if request_id is None:
        return {}, next_session
    envelope = _parse_response(response)
    if envelope.get("error"):
        rpc_error = envelope["error"]
        raise McpChainError(f"MCP catalog error {rpc_error.get('code')}: {rpc_error.get('message')}")
    return envelope.get("result") or {}, next_session


def list_tools(
    url: str,
    headers: dict[str, str],
    *,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Perform initialize + paged tools/list only; never invoke or mutate a tool."""
    owned = client is None
    active = client or httpx.Client(timeout=30.0)
    try:
        _, session_id = _rpc(
            active,
            url,
            headers,
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "horizon-mcp-chain-verifier", "version": "1.0"},
            },
            0,
            None,
        )
        _rpc(active, url, headers, "notifications/initialized", {}, None, session_id)
        tools: list[dict[str, Any]] = []
        seen_cursors: set[str] = set()
        cursor: str | None = None
        request_id = 1
        while True:
            params = {"cursor": cursor} if cursor else {}
            result, _ = _rpc(active, url, headers, "tools/list", params, request_id, session_id)
            page = result.get("tools")
            if not isinstance(page, list):
                raise McpChainError("MCP tools/list result did not contain a tools array")
            if not all(isinstance(tool, dict) for tool in page):
                raise McpChainError("MCP tools/list contained a non-object tool")
            tools.extend(page)
            next_cursor = result.get("nextCursor")
            if next_cursor is None:
                break
            if not isinstance(next_cursor, str) or not next_cursor:
                raise McpChainError("MCP tools/list returned an invalid nextCursor")
            if next_cursor in seen_cursors:
                raise McpChainError("MCP tools/list cursor loop detected")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            request_id += 1
    finally:
        if owned:
            active.close()
    names = [tool.get("name") for tool in tools]
    if any(not isinstance(name, str) or not name for name in names):
        raise McpChainError("MCP tools/list contained a tool without a valid name")
    if len(set(names)) != len(names):
        raise McpChainError("MCP tools/list contained duplicate tool names")
    return tools


def _contract_hash(tool: dict[str, Any]) -> str:
    contract = {
        "name": tool.get("name"),
        "description": tool.get("description"),
        "inputSchema": tool.get("inputSchema") or {},
        "annotations": tool.get("annotations") or {},
    }
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compare_catalogs(
    publication: str,
    source_tools: list[dict[str, Any]],
    downstream_tools: list[dict[str, Any]],
) -> ChainReport:
    """Require exact downstream parity and mandatory ADR-0046 annotations."""
    source = {str(tool.get("name")): tool for tool in source_tools if tool.get("name")}
    downstream = {str(tool.get("name")): tool for tool in downstream_tools if tool.get("name")}
    missing = tuple(sorted(source.keys() - downstream.keys()))
    unexpected = tuple(sorted(downstream.keys() - source.keys()))
    drift = tuple(
        sorted(
            name
            for name in source.keys() & downstream.keys()
            if _contract_hash(source[name]) != _contract_hash(downstream[name])
        )
    )
    violations: list[str] = []
    for surface_name, tools in (("contextforge", source), ("portkey", downstream)):
        for name, tool in tools.items():
            annotations = tool.get("annotations") or {}
            absent = [key for key in _REQUIRED_ANNOTATIONS if not isinstance(annotations.get(key), bool)]
            if absent:
                violations.append(f"{surface_name}:{name}:{','.join(absent)}")
    return ChainReport(
        publication=publication,
        source_count=len(source),
        downstream_count=len(downstream),
        missing_downstream=missing,
        unexpected_downstream=unexpected,
        contract_drift=drift,
        annotation_violations=tuple(sorted(violations)),
    )
