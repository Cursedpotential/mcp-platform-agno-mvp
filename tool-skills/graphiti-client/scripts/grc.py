#!/usr/bin/env python3
"""
grc — Graphiti client CLI. Speaks MCP streamable-HTTP JSON-RPC directly
(initialize -> notifications/initialized -> tools/call), so any session or
plugin can write/read Graphiti episodes without the graphiti MCP server
being registered/connected. stdlib-only (urllib), no third-party deps.

Transport-agnostic:
  --via direct (default) -> tailnet sidecar http://100.119.96.29:8071/mcp
  --via cf                -> ContextForge vserver (Bearer token from
                              ~/.secrets/contextforge.env, key CF_MCP_CLIENT_TOKEN)

Never prints a full token/secret — only lengths/prefixes when diagnosing.

# Byline: Claude Code · Sonnet · 2026-07-19
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DIRECT_URL = os.environ.get("GRAPHITI_DIRECT_URL", "http://100.119.96.29:8071/mcp")
CF_URL = os.environ.get(
    "GRAPHITI_CF_URL",
    "http://100.72.169.40:4444/servers/9128872f7a9e43e484e1312917901828/mcp",
)
CF_ENV_FILE = os.environ.get("CONTEXTFORGE_ENV_FILE", r"C:/Users/matts/.secrets/contextforge.env")
DEFAULT_GROUP = os.environ.get("GRAPHITI_GROUP_ID", "platform")
PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "grc"
CLIENT_VERSION = "0.1.0"


def _load_env_file(path: str) -> dict:
    """Parse a simple KEY=VALUE env file (quotes stripped). Never logs values."""
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return out


class GrcError(Exception):
    pass


# ---------------------------------------------------------------------------
# MCP streamable-HTTP client
# ---------------------------------------------------------------------------


class McpClient:
    """One session against one MCP streamable-HTTP endpoint.

    Handles: initialize -> Mcp-Session-Id header capture -> notifications/initialized
    -> tools/call. Responses may come back as plain JSON or SSE-framed
    ("event: message\\ndata: {...}\\n\\n") — both are parsed.
    """

    def __init__(self, url: str, bearer: str | None = None, timeout: float = 30.0, tool_prefix: str = ""):
        self.url = url
        self.bearer = bearer
        self.timeout = timeout
        self.session_id: str | None = None
        self._next_id = 1
        self._initialized = False
        # ContextForge fronts Graphiti's tools with a "graphiti-" prefix and
        # hyphens instead of underscores (verified live 2026-07-19:
        # get_status -> graphiti-get-status). The direct sidecar uses the
        # server's native names unprefixed. call_tool() translates.
        self.tool_prefix = tool_prefix

    def _tool_name(self, name: str) -> str:
        if not self.tool_prefix:
            return name
        return self.tool_prefix + name.replace("_", "-")

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        if self.bearer:
            h["Authorization"] = f"Bearer {self.bearer}"
        return h

    def _post(self, body: dict) -> tuple[int, dict, str]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers=self._headers(), method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers.items()), raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            return e.code, dict(e.headers.items()), raw
        except urllib.error.URLError as e:
            raise GrcError(f"connection failed: {e.reason}") from e

    @staticmethod
    def _parse_sse_or_json(raw: str) -> dict:
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:"):].strip())
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
            raise GrcError(f"initialize failed: HTTP {status}: {raw[:300]}")
        self.session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise GrcError(f"initialize error: {obj['error']}")
        # notifications/initialized — fire-and-forget, no id, 202 expected
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True
        return obj.get("result", {})

    def _ensure_init(self) -> None:
        if not self._initialized:
            self.initialize()

    def list_tools(self) -> list:
        self._ensure_init()
        body = {"jsonrpc": "2.0", "id": self._next_id, "method": "tools/list", "params": {}}
        self._next_id += 1
        status, _headers, raw = self._post(body)
        if status >= 400:
            raise GrcError(f"tools/list failed: HTTP {status}: {raw[:300]}")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise GrcError(f"tools/list error: {obj['error']}")
        return obj.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        self._ensure_init()
        wire_name = self._tool_name(name)
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": wire_name, "arguments": arguments},
        }
        self._next_id += 1
        status, _headers, raw = self._post(body)
        if status >= 400:
            raise GrcError(f"tools/call({wire_name}) failed: HTTP {status}: {raw[:300]}")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise GrcError(f"tools/call({name}) error: {obj['error']}")
        result = obj.get("result", {})
        if result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "") if content else ""
            raise GrcError(f"{name} returned isError: {text[:400]}")
        # Prefer the text content block: it's the consistently-shaped payload.
        # structuredContent sometimes wraps the SAME payload under an extra
        # {"result": {...}} envelope (matches its outputSchema's SuccessResponse/
        # ErrorResponse union — e.g. get_episodes, add_memory) while the text
        # block does not. Verified live 2026-07-19: get_episodes structuredContent
        # = {"result": {"message":..., "episodes":[...]}} but content[0].text =
        # {"message":..., "episodes":[...]} (no wrapper). Using structuredContent
        # directly silently broke result["episodes"]/result["facts"] lookups.
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


def _build_client(via: str) -> McpClient:
    if via == "cf":
        env = _load_env_file(CF_ENV_FILE)
        token = env.get("CF_MCP_CLIENT_TOKEN")
        if not token:
            raise GrcError(f"CF_MCP_CLIENT_TOKEN not found in {CF_ENV_FILE}")
        return McpClient(CF_URL, bearer=token, tool_prefix="graphiti-")
    return McpClient(DIRECT_URL)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _truncate(s: str, n: int = 100) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_status(args) -> int:
    client = _build_client(args.via)
    try:
        result = client.call_tool("get_status", {})
    except GrcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if args.json:
        _print_json(result)
    else:
        print(f"status:  {result.get('status', '?')}")
        print(f"message: {result.get('message', '')}")
        print(f"via:     {args.via} ({client.url})")
    return 0 if result.get("status") == "ok" else 1


def cmd_search(args) -> int:
    client = _build_client(args.via)
    group_ids = [args.group] if args.group else [DEFAULT_GROUP]
    try:
        if args.nodes:
            result = client.call_tool(
                "search_nodes",
                {"query": args.query, "group_ids": group_ids, "max_nodes": args.max},
            )
            items = result.get("nodes", [])
        else:
            result = client.call_tool(
                "search_memory_facts",
                {"query": args.query, "group_ids": group_ids, "max_facts": args.max},
            )
            items = result.get("facts", [])
    except GrcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    if args.json:
        _print_json(result)
        return 0

    if not items:
        print(f"(no {'nodes' if args.nodes else 'facts'} found for query: {args.query!r}, group(s): {group_ids})")
        return 0

    if args.nodes:
        for n in items:
            print(f"- [{n.get('uuid', '')[:8]}] {n.get('name', '')}")
            summary = n.get("summary") or ""
            if summary:
                print(f"    {_truncate(summary, 140)}")
    else:
        for f in items:
            print(f"- [{f.get('uuid', '')[:8]}] {_truncate(f.get('fact', ''), 140)}")
            print(f"    valid_at={f.get('valid_at')}  group={f.get('group_id')}")
    return 0


def cmd_add(args) -> int:
    client = _build_client(args.via)
    group_id = args.group or DEFAULT_GROUP
    source_description = args.desc or f"grc CLI ({CLIENT_NAME}/{CLIENT_VERSION})"
    try:
        result = client.call_tool(
            "add_memory",
            {
                "name": args.name,
                "episode_body": args.body,
                "group_id": group_id,
                "source": args.source,
                "source_description": source_description,
            },
        )
    except GrcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if args.json:
        _print_json(result)
    else:
        print(result.get("message", "queued"))
        print(f"name:  {args.name}")
        print(f"group: {group_id}")
        print("note: ingestion is async — poll `grc search`/`grc episodes` in ~30s-3min.")
    return 0


def cmd_episodes(args) -> int:
    client = _build_client(args.via)
    group_id = args.group or DEFAULT_GROUP
    try:
        # NOTE (verified live 2026-07-19): the real param names are
        # group_ids (array) + max_episodes — NOT group_id/last_n as a naive
        # reading of the tool description would suggest. Also: results are
        # NOT returned in created_at order, so we over-fetch (floor 50) and
        # sort+slice client-side — asking for exactly args.last upstream would
        # silently truncate BEFORE sorting and could drop the true most-recent
        # episodes (verified: happened with max_episodes=3).
        fetch_n = max(args.last, 50)
        result = client.call_tool("get_episodes", {"group_ids": [group_id], "max_episodes": fetch_n})
    except GrcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    episodes = result.get("episodes", [])
    episodes = sorted(episodes, key=lambda e: e.get("created_at", ""), reverse=True)[: args.last]
    if args.json:
        _print_json({**result, "episodes": episodes})
        return 0
    if not episodes:
        print(f"(no episodes for group={group_id})")
        return 0
    for ep in episodes:
        print(f"- [{ep.get('uuid', '')[:8]}] {ep.get('name', '')}  ({ep.get('created_at', '')})")
        content = ep.get("content", "")
        if content:
            print(f"    {_truncate(content, 140)}")
    return 0


def cmd_raw(args) -> int:
    client = _build_client(args.via)
    try:
        arguments = json.loads(args.json_args) if args.json_args else {}
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON args: {e}", file=sys.stderr)
        return 1
    try:
        result = client.call_tool(args.tool, arguments)
    except GrcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def cmd_doctor(args) -> int:
    rows = []  # (check, status, detail)

    def row(check: str, ok: bool, detail: str = ""):
        rows.append((check, "PASS" if ok else "FAIL", detail))

    # 1. direct endpoint init
    direct_client = McpClient(DIRECT_URL)
    direct_ok = False
    try:
        t0 = time.time()
        direct_client.initialize()
        row("direct init", True, f"{DIRECT_URL} ({(time.time() - t0) * 1000:.0f}ms, session={direct_client.session_id[:8] if direct_client.session_id else '?'})")
        direct_ok = True
    except GrcError as e:
        row("direct init", False, str(e)[:200])

    # 2. CF fallback init
    cf_client = None
    cf_ok = False
    try:
        env = _load_env_file(CF_ENV_FILE)
        token = env.get("CF_MCP_CLIENT_TOKEN")
        if not token:
            row("cf init", False, f"no CF_MCP_CLIENT_TOKEN in {CF_ENV_FILE}")
        else:
            cf_client = McpClient(CF_URL, bearer=token, tool_prefix="graphiti-")
            t0 = time.time()
            cf_client.initialize()
            row("cf init", True, f"{CF_URL} ({(time.time() - t0) * 1000:.0f}ms, token=len:{len(token)})")
            cf_ok = True
    except GrcError as e:
        row("cf init", False, str(e)[:200])

    active = direct_client if direct_ok else (cf_client if cf_ok else None)
    active_via = "direct" if direct_ok else ("cf" if cf_ok else None)

    if active is None:
        row("status", False, "no working transport — cannot proceed")
        row("tools/list", False, "skipped")
        row("search roundtrip", False, "skipped")
        row("episode freshness", False, "skipped")
    else:
        # 3. get_status
        try:
            result = active.call_tool("get_status", {})
            row("status", result.get("status") == "ok", f"via {active_via}: {result.get('message', '')[:150]}")
        except GrcError as e:
            row("status", False, str(e)[:200])

        # 4. tools/list count
        try:
            tools = active.list_tools()
            row("tools/list", len(tools) > 0, f"{len(tools)} tools: {', '.join(t['name'] for t in tools)}")
        except GrcError as e:
            row("tools/list", False, str(e)[:200])

        # 5. search roundtrip (embedder probe)
        try:
            t0 = time.time()
            result = active.call_tool(
                "search_memory_facts",
                {"query": "grc doctor connectivity probe", "group_ids": [DEFAULT_GROUP], "max_facts": 1},
            )
            elapsed = (time.time() - t0) * 1000
            facts = result.get("facts", [])
            row("search roundtrip", True, f"{len(facts)} fact(s) in {elapsed:.0f}ms (embedder path OK)")
        except GrcError as e:
            msg = str(e)
            fix = ""
            if "403" in msg:
                fix = " LIKELY FIX: embed-text route/NIM key on exec tier (litellm)."
            elif "500" in msg:
                fix = " LIKELY FIX: check Graphiti/Neo4j logs, embedder or LLM route down."
            elif "421" in msg:
                fix = " LIKELY FIX: sidecar/nginx hostfix down on ovh-data."
            row("search roundtrip", False, msg[:200] + fix)

        # 6. episode freshness (stale-graph alarm). get_episodes does NOT
        # return results in created_at order (verified live), so pull a
        # decent-sized batch and take the max created_at ourselves.
        try:
            result = active.call_tool("get_episodes", {"group_ids": [DEFAULT_GROUP], "max_episodes": 50})
            episodes = result.get("episodes", [])
            if episodes:
                newest = max(episodes, key=lambda e: e.get("created_at", ""))
                created = newest.get("created_at", "")
                try:
                    ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
                    stale = age_h > 72
                    row(
                        "episode freshness",
                        not stale,
                        f"newest episode in '{DEFAULT_GROUP}' is {age_h:.1f}h old"
                        + (" -- STALE (>72h, check for silent-stall)" if stale else ""),
                    )
                except ValueError:
                    row("episode freshness", True, f"newest created_at={created} (unparsed)")
            else:
                row("episode freshness", True, f"no episodes yet in group={DEFAULT_GROUP}")
        except GrcError as e:
            row("episode freshness", False, str(e)[:200])

    # print table
    width_check = max(len(r[0]) for r in rows) + 2
    width_status = 6
    print(f"{'CHECK'.ljust(width_check)}{'RESULT'.ljust(width_status)}DETAIL")
    print("-" * (width_check + width_status + 60))
    all_pass = True
    for check, status, detail in rows:
        if status != "PASS":
            all_pass = False
        print(f"{check.ljust(width_check)}{status.ljust(width_status)}{detail}")
    print()
    print(f"OVERALL: {'PASS' if all_pass else 'FAIL'} (active transport: {active_via or 'none'})")
    return 0 if all_pass else 1


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    # Shared flags (--via, --json) go AFTER the subcommand only:
    # `grc search "q" --via cf`, not `grc --via cf search "q"`.
    # (argparse gotcha: if the same dest is declared on both the top-level
    # parser and a subparser via a shared `parents=` list, the subparser's
    # own default silently overwrites whatever the top-level parser already
    # parsed — verified live: `grc --via cf status` printed "via: direct".
    # Declaring it only once, on the subparsers, avoids the clobber.)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--via", choices=["direct", "cf"], default="direct", help="transport: direct tailnet endpoint (default) or ContextForge fallback")
    common.add_argument("--json", action="store_true", help="raw JSON output where applicable")

    p = argparse.ArgumentParser(prog="grc", description="Graphiti client CLI — MCP streamable-HTTP JSON-RPC, no session-registered MCP required.")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("status", help="server status", parents=[common])
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("search", help="search facts or nodes", parents=[common])
    sp.add_argument("query")
    sp.add_argument("--nodes", action="store_true", help="search entity nodes instead of facts")
    sp.add_argument("--group", default=None, help=f"group_id (default: {DEFAULT_GROUP})")
    sp.add_argument("--max", type=int, default=10, help="max results (default 10)")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("add", help="add an episode", parents=[common])
    sp.add_argument("name")
    sp.add_argument("body")
    sp.add_argument("--group", default=None, help=f"group_id (default: {DEFAULT_GROUP})")
    sp.add_argument("--source", choices=["text", "json", "message"], default="text")
    sp.add_argument("--desc", default=None, help="source_description")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("episodes", help="recent episodes", parents=[common])
    sp.add_argument("--last", type=int, default=10)
    sp.add_argument("--group", default=None, help=f"group_id (default: {DEFAULT_GROUP})")
    sp.set_defaults(func=cmd_episodes)

    sp = sub.add_parser("raw", help="escape hatch: call any tool with raw JSON arguments", parents=[common])
    sp.add_argument("tool")
    sp.add_argument("json_args", nargs="?", default="{}")
    sp.set_defaults(func=cmd_raw)

    sp = sub.add_parser("doctor", help="full connectivity + health diagnosis (PASS/FAIL table)", parents=[common])
    sp.set_defaults(func=cmd_doctor)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except GrcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
