"""server/analysis/graphiti_case_client.py — minimal Graphiti MCP client, CASE
lane only.

AI-chat context must land in Graphiti's **`memory`** Neo4j database (case
lane), never the `neo4j` platform/dev database and never the `evidence`
database (ADR-0036: `memory` = graphiti_writer, `evidence` = semantica_writer,
permission-isolated by design). This module only ever talks to the case-lane
endpoint; there is deliberately no "platform" option here — a caller that
wants the dev graph should use a different client, not a flag on this one,
so a missing `--lane` can never silently misroute case data.

Protocol: MCP streamable-HTTP JSON-RPC (initialize -> notifications/initialized
-> tools/call), stdlib `urllib` only — no new dependency. This is a trimmed,
in-repo port of the case-lane subset of the personal `grc` CLI
(``~/.claude/skills/graphiti-client/scripts/grc.py``, McpClient class):
ported rather than imported/shelled-out-to because durable-infra-touching code
must live in THIS repo (``require_tracked_code`` hook) and a personal
`~/.claude` skill is not part of it. Endpoint/group defaults match `grc.py`
exactly (verified live 2026-08-01, case lane: Coolify app
`wi3vzgd4hekbddvqj8nkn33j` on ovh-files, ghcr.io/cursedpotential/graphiti-mcp
0.29.3, writes DozerDB database `memory`).
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

CASE_URL = os.environ.get("GRAPHITI_CASE_URL", "http://100.91.190.107:8073/mcp")
CASE_GROUP_ID = os.environ.get("GRAPHITI_CASE_GROUP_ID", "case-salem-kinzel")
PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "context-chat-ingest"
CLIENT_VERSION = "0.1.0"


class GraphitiClientError(RuntimeError):
    """Any failure talking to the Graphiti case-lane MCP endpoint."""


class GraphitiCaseClient:
    """One session against the Graphiti CASE lane (memory DB, case-salem-kinzel
    group by default). Lazily initializes on first call_tool()."""

    def __init__(self, url: str = CASE_URL, group_id: str = CASE_GROUP_ID, timeout: float = 30.0):
        self.url = url
        self.group_id = group_id
        self.timeout = timeout
        self.session_id: str | None = None
        self._next_id = 1
        self._initialized = False

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, body: dict) -> tuple[int, dict, str]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers=self._headers(), method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            return resp.status, dict(resp.headers.items()), resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers.items()), e.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise GraphitiClientError(f"connection failed: {e.reason} (url={self.url})") from e

    @staticmethod
    def _parse_sse_or_json(raw: str) -> dict:
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:") :].strip())
        if not raw.strip():
            return {}
        return json.loads(raw)

    def initialize(self) -> dict:
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        }
        self._next_id += 1
        status, headers, raw = self._post(body)
        if status >= 400:
            raise GraphitiClientError(f"initialize failed: HTTP {status}: {raw[:300]}")
        self.session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise GraphitiClientError(f"initialize error: {obj['error']}")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})  # fire-and-forget
        self._initialized = True
        return obj.get("result", {})

    def _ensure_init(self) -> None:
        if not self._initialized:
            self.initialize()

    def call_tool(self, name: str, arguments: dict) -> dict:
        self._ensure_init()
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        self._next_id += 1
        status, _headers, raw = self._post(body)
        if status >= 400:
            raise GraphitiClientError(f"tools/call({name}) failed: HTTP {status}: {raw[:300]}")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise GraphitiClientError(f"tools/call({name}) error: {obj['error']}")
        result = obj.get("result", {})
        if result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "") if content else ""
            raise GraphitiClientError(f"{name} returned isError: {text[:400]}")
        # Prefer the text content block over structuredContent: the latter
        # sometimes double-wraps as {"result": {...}} (verified live against
        # this same server by grc.py's McpClient — see its docstring).
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except json.JSONDecodeError:
                return {"text": content[0]["text"]}
        if "structuredContent" in result:
            sc = result["structuredContent"]
            if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
                return sc["result"]
            return sc
        return result

    def add_memory(
        self,
        *,
        name: str,
        episode_body: str,
        group_id: str | None = None,
        source: str = "text",
        source_description: str = "",
    ) -> dict:
        """Queue an episode on the case lane. Async ingestion upstream — this
        only confirms the episode was queued, not that entities/facts were
        extracted yet (matches grc.py's documented `add` semantics)."""
        return self.call_tool(
            "add_memory",
            {
                "name": name,
                "episode_body": episode_body,
                "group_id": group_id or self.group_id,
                "source": source,
                "source_description": source_description or f"{CLIENT_NAME}/{CLIENT_VERSION}",
            },
        )
