#!/usr/bin/env python3
"""
oc — OpenCode-ops CLI. First-class control surface for the platform's headless
OpenCode server plus the surrounding control plane it sits inside: agentos-api
(bearer REST), agentos-mcp (streamable-HTTP JSON-RPC), and the ContextForge
federated tool catalog (streamable-HTTP JSON-RPC, bearer). stdlib-only
(urllib, json, argparse) -- no third-party deps, modeled on the `grc` CLI
(graphiti-client skill) sibling pattern.

Lanes NOT covered here (by design, avoid duplication):
  - Graphiti knowledge-graph memory -> use `grc` (graphiti-client skill).
  - Claude Code's own auto-memory (MEMORY.md) -> internal to this tool, N/A.

Never prints a full secret/token/provider-API-key -- only lengths/prefixes
when diagnosing. See `oc doctor`.

# Byline: Claude Code · Sonnet · 2026-07-20 (agno 2.8 MCP door migration :8001->:8000 + bearer, 2026-07-23)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Config (env-driven; every value below has a sane default for the platform)
# ---------------------------------------------------------------------------

OC_SERVER = os.environ.get("OC_SERVER", "http://100.72.169.40:4096").rstrip("/")
OC_TOKEN = os.environ.get("OC_TOKEN")  # bearer for the opencode server itself,
# IF it ever requires one. As of 2026-07-20 the tailnet deployment is unauthenticated.

# HTTP Basic -- opencode serve's own native auth (OPENCODE_SERVER_USERNAME/
# OPENCODE_SERVER_PASSWORD server-side, see compose.gateway.yaml). This is the
# real fix for known-issues.md #1 (unauthenticated /provider leaking plaintext
# provider keys) once the gateway app is redeployed with the password set.
# OC_SERVER_PASSWORD unset/empty = no Authorization header sent, matching
# today's still-unauthenticated deployment (fix landed 2026-07-21, deploy
# pending -- see references/known-issues.md).
OC_SERVER_USERNAME = os.environ.get("OC_SERVER_USERNAME", "opencode")
OC_SERVER_PASSWORD = os.environ.get("OC_SERVER_PASSWORD")

# When set, `oc run` without an explicit --directory defaults into
# "<OC_WORKSPACE>/<slug>" (a fresh slug per invocation) instead of the shared
# "global" project scope. This is the fix for known-issues.md #2's directory
# half: a `?directory=` that doesn't exist inside the opencode container 500s
# (ENOENT deep in SystemPrompt.environment) -- OC_WORKSPACE must point at a
# directory that's bind-mounted and already exists (see compose.gateway.yaml
# HOST-PREP: /data/agno/volumes/gateway-workdirs -> /workspace). Unset = old
# behavior (shared default scope unless --directory is passed explicitly).
OC_WORKSPACE = os.environ.get("OC_WORKSPACE")

# agno 2.8 door migration (2026-07-23): agentos-mcp :8001 is RETIRED. The MCP
# door is now mounted straight on agentos-api's own port -- streamable-HTTP,
# REQUIRES Authorization: Bearer <OS_SECURITY_KEY> (verified live: initialize
# ok, tools/list = 8 v2 tools: get_agentos_config, run_agent, run_team,
# run_workflow, continue_run, cancel_run, get_sessions, get_session_runs).
# _mcp_client("agentos") below attaches the same OS_SECURITY_KEY bearer
# get_os_security_key() already parses for the REST agentos-api lane.
AGENTOS_URL = os.environ.get("OC_AGENTOS_URL", "http://100.72.169.40:8000").rstrip("/")
AGENTOS_MCP_URL = os.environ.get("OC_AGENTOS_MCP_URL", "http://100.72.169.40:8000/mcp")
CONTEXTFORGE_MCP_URL = os.environ.get("OC_CONTEXTFORGE_MCP_URL", "http://100.72.169.40:4444/mcp")

INFRA_SECRETS_FILE = os.environ.get("OC_INFRA_SECRETS_FILE", r"C:/Users/matts/.secrets/infra-access.md")
CONTEXTFORGE_ENV_FILE = os.environ.get("OC_CONTEXTFORGE_ENV_FILE", r"C:/Users/matts/.secrets/contextforge.env")

PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "oc"
CLIENT_VERSION = "0.1.0"

DEFAULT_TIMEOUT = 30.0
RUN_TIMEOUT = 120.0


class OcError(Exception):
    pass


# ---------------------------------------------------------------------------
# Secrets — read from files, never echoed. Only lengths/prefixes surfaced.
# ---------------------------------------------------------------------------


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


def get_os_security_key() -> str | None:
    """Parse OS_SECURITY_KEY (bearer) out of infra-access.md. Tolerant regex —
    matches the "**OS_SECURITY_KEY (bearer):** `<hex>`" line shape but doesn't
    hard-require exact markdown formatting. Env override: OC_OS_SECURITY_KEY."""
    override = os.environ.get("OC_OS_SECURITY_KEY")
    if override:
        return override
    try:
        with open(INFRA_SECRETS_FILE, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return None
    m = re.search(r"OS_SECURITY_KEY[^`\n]*`([0-9a-fA-F]{16,})`", content)
    return m.group(1) if m else None


def get_cf_token() -> str | None:
    """CF_MCP_CLIENT_TOKEN from the ContextForge env file. Env override:
    OC_CF_MCP_CLIENT_TOKEN."""
    override = os.environ.get("OC_CF_MCP_CLIENT_TOKEN")
    if override:
        return override
    env = _load_env_file(CONTEXTFORGE_ENV_FILE)
    return env.get("CF_MCP_CLIENT_TOKEN")


def _secret_hint(value: str | None) -> str:
    if not value:
        return "MISSING"
    return f"present (len={len(value)})"


def _opencode_auth_headers() -> dict[str, str] | None:
    """HTTP Basic Authorization header for the opencode server itself. None
    when OC_SERVER_PASSWORD isn't set -- see its module-level doc comment."""
    if not OC_SERVER_PASSWORD:
        return None
    token = base64.b64encode(f"{OC_SERVER_USERNAME}:{OC_SERVER_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ---------------------------------------------------------------------------
# Plain REST helper (urllib only)
# ---------------------------------------------------------------------------


def http_request(
    method: str,
    url: str,
    bearer: str | None = None,
    json_body=None,
    timeout: float = DEFAULT_TIMEOUT,
    extra_headers: dict | None = None,
) -> tuple[int, dict, str]:
    headers = {"Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, dict(resp.headers.items()), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return e.code, dict(e.headers.items()), raw
    except urllib.error.URLError as e:
        raise OcError(f"connection failed: {e.reason}") from e
    except TimeoutError as e:
        raise OcError(f"timed out after {timeout}s") from e


def http_json(method: str, url: str, **kw):
    status, headers, raw = http_request(method, url, **kw)
    try:
        body = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        body = {"_raw": raw}
    return status, body


# ---------------------------------------------------------------------------
# MCP streamable-HTTP client (shared by agentos-mcp + contextforge)
# ---------------------------------------------------------------------------


class McpClient:
    """One session against one MCP streamable-HTTP endpoint. Handshake:
    initialize -> (optional) Mcp-Session-Id header capture -> notifications/
    initialized -> tools/list / tools/call. Tolerates stateless gateways
    (ContextForge answers tools/call with no session id at all — verified
    live 2026-07-20) as well as stateful ones (agentos-mcp issues a session id
    on initialize). Responses may be plain JSON or SSE-framed."""

    def __init__(self, url: str, bearer: str | None = None, timeout: float = DEFAULT_TIMEOUT):
        self.url = url
        self.bearer = bearer
        self.timeout = timeout
        self.session_id: str | None = None
        self._next_id = 1
        self._initialized = False

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
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
            raise OcError(f"connection failed: {e.reason}") from e

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
            raise OcError(f"initialize failed: HTTP {status}: {raw[:300]}")
        self.session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise OcError(f"initialize error: {obj['error']}")
        if self.session_id:
            # fire-and-forget; some gateways 202, some ignore it entirely
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
            raise OcError(f"tools/list failed: HTTP {status}: {raw[:300]}")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise OcError(f"tools/list error: {obj['error']}")
        return obj.get("result", {}).get("tools", [])

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
            raise OcError(f"tools/call({name}) failed: HTTP {status}: {raw[:300]}")
        obj = self._parse_sse_or_json(raw)
        if "error" in obj:
            raise OcError(f"tools/call({name}) error: {obj['error']}")
        result = obj.get("result", {})
        if result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "") if content else ""
            raise OcError(f"{name} returned isError: {text[:400]}")
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


def _mcp_client(server: str) -> McpClient:
    if server == "agentos":
        # agno 2.8: the mounted /mcp door requires the same OS_SECURITY_KEY
        # bearer as every other gated route on agentos-api (see the
        # AGENTOS_MCP_URL comment above) -- unlike the old agentos-mcp :8001
        # door, which was unauthenticated.
        return McpClient(AGENTOS_MCP_URL, bearer=get_os_security_key())
    if server == "contextforge":
        token = get_cf_token()
        if not token:
            raise OcError(f"CF_MCP_CLIENT_TOKEN not found ({CONTEXTFORGE_ENV_FILE} / OC_CF_MCP_CLIENT_TOKEN)")
        return McpClient(CONTEXTFORGE_MCP_URL, bearer=token)
    raise OcError(f"unknown MCP server {server!r} (expected: agentos, contextforge)")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _truncate(s: str, n: int = 120) -> str:
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _redact_providers(provider_doc: dict) -> dict:
    """Provider config from the opencode server embeds live provider API keys
    in plaintext (verified live 2026-07-20: /provider and /config/providers
    both return a "key" field for env-sourced connected providers, e.g.
    NVIDIA_API_KEY/OPENROUTER_API_KEY/GROQ_API_KEY). Never forward that
    upstream — strip to a length hint before printing or returning --json."""
    out = json.loads(json.dumps(provider_doc))  # deep copy
    for p in out.get("all", []):
        if isinstance(p, dict) and "key" in p and isinstance(p["key"], str):
            p["key"] = f"<redacted len={len(p['key'])}>"
    return out


# ---------------------------------------------------------------------------
# Subcommands — doctor
# ---------------------------------------------------------------------------


def cmd_doctor(args) -> int:
    rows = []  # (check, PASS/FAIL, detail)

    def row(check: str, ok: bool, detail: str = ""):
        rows.append((check, "PASS" if ok else "FAIL", detail))

    # 1. OpenCode headless server root
    try:
        t0 = time.time()
        status, _h, raw = http_request(
            "GET", f"{OC_SERVER}/", bearer=OC_TOKEN, timeout=args.timeout, extra_headers=_opencode_auth_headers()
        )
        ms = (time.time() - t0) * 1000
        row("opencode: GET /", status == 200, f"{OC_SERVER} HTTP {status} ({ms:.0f}ms)")
    except OcError as e:
        row("opencode: GET /", False, str(e)[:200])

    # 2. OpenCode providers
    try:
        status, doc = http_json(
            "GET", f"{OC_SERVER}/provider", bearer=OC_TOKEN, timeout=args.timeout, extra_headers=_opencode_auth_headers()
        )
        connected = doc.get("connected", []) if isinstance(doc, dict) else []
        total = len(doc.get("all", [])) if isinstance(doc, dict) else 0
        row("opencode: GET /provider", status == 200, f"HTTP {status}, {len(connected)} connected / {total} known: {', '.join(connected)}")
    except OcError as e:
        row("opencode: GET /provider", False, str(e)[:200])

    # 3. agentos-api health (unauth)
    try:
        status, doc = http_json("GET", f"{AGENTOS_URL}/health", timeout=args.timeout)
        row("agentos-api: GET /health", status == 200 and doc.get("status") == "ok", f"HTTP {status} {doc}")
    except OcError as e:
        row("agentos-api: GET /health", False, str(e)[:200])

    # 4. agentos-api bearer-gated route
    key = get_os_security_key()
    if not key:
        row("agentos-api: GET /info (bearer)", False, f"OS_SECURITY_KEY not found in {INFRA_SECRETS_FILE}")
    else:
        try:
            status, doc = http_json("GET", f"{AGENTOS_URL}/info", bearer=key, timeout=args.timeout)
            row(
                "agentos-api: GET /info (bearer)",
                status == 200,
                f"HTTP {status}, agno={doc.get('agno_version')}, agents={doc.get('agent_count')}, teams={doc.get('team_count')}, workflows={doc.get('workflow_count')} [key {_secret_hint(key)}]",
            )
        except OcError as e:
            row("agentos-api: GET /info (bearer)", False, str(e)[:200])

    # 5. agentos-mcp (agno 2.8: bearer-gated, same OS_SECURITY_KEY as /info)
    mcp_key = get_os_security_key()
    try:
        client = McpClient(AGENTOS_MCP_URL, bearer=mcp_key, timeout=args.timeout)
        t0 = time.time()
        client.initialize()
        tools = client.list_tools()
        ms = (time.time() - t0) * 1000
        row(
            "agentos-mcp: initialize + tools/list",
            len(tools) > 0,
            f"{AGENTOS_MCP_URL} -> {len(tools)} tools ({ms:.0f}ms) [key {_secret_hint(mcp_key)}]",
        )
    except OcError as e:
        row("agentos-mcp: initialize + tools/list", False, str(e)[:200])

    # 6. contextforge-mcp (bearer)
    cf_token = get_cf_token()
    if not cf_token:
        row("contextforge-mcp: tools/list (bearer)", False, f"CF_MCP_CLIENT_TOKEN not found in {CONTEXTFORGE_ENV_FILE}")
    else:
        try:
            client = McpClient(CONTEXTFORGE_MCP_URL, bearer=cf_token, timeout=args.timeout)
            t0 = time.time()
            tools = client.list_tools()
            ms = (time.time() - t0) * 1000
            row(
                "contextforge-mcp: tools/list (bearer)",
                len(tools) > 0,
                f"{CONTEXTFORGE_MCP_URL} -> {len(tools)} tools ({ms:.0f}ms) [token {_secret_hint(cf_token)}]",
            )
        except OcError as e:
            row("contextforge-mcp: tools/list (bearer)", False, str(e)[:200])

    width_check = max(len(r[0]) for r in rows) + 2
    print(f"{'CHECK'.ljust(width_check)}{'RESULT'.ljust(7)}DETAIL")
    print("-" * (width_check + 7 + 70))
    all_pass = True
    for check, status, detail in rows:
        if status != "PASS":
            all_pass = False
        print(f"{check.ljust(width_check)}{status.ljust(7)}{detail}")
    print()
    print(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


# ---------------------------------------------------------------------------
# Subcommands — providers / models
# ---------------------------------------------------------------------------


def _fetch_providers(timeout: float) -> dict:
    status, doc = http_json(
        "GET", f"{OC_SERVER}/provider", bearer=OC_TOKEN, timeout=timeout, extra_headers=_opencode_auth_headers()
    )
    if status != 200:
        raise OcError(f"GET /provider failed: HTTP {status}")
    return doc


def cmd_providers(args) -> int:
    try:
        doc = _fetch_providers(args.timeout)
    except OcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    redacted = _redact_providers(doc)
    if args.json:
        _print_json(redacted)
        return 0
    connected = set(redacted.get("connected", []))
    print(f"connected ({len(connected)}): {', '.join(sorted(connected)) or '(none)'}")
    print()
    for p in redacted.get("all", []):
        pid = p.get("id", "?")
        mark = "*" if pid in connected else " "
        print(f"[{mark}] {pid:<20} {p.get('name', ''):<20} models={len(p.get('models', {}))}")
    print("\n(* = connected/usable now; run `oc models --provider <id>` for its model list)")
    return 0


def cmd_models(args) -> int:
    try:
        doc = _fetch_providers(args.timeout)
    except OcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    connected = set(doc.get("connected", []))
    providers = doc.get("all", [])
    if args.provider:
        providers = [p for p in providers if p.get("id") == args.provider]
        if not providers:
            print(f"FAIL: unknown provider {args.provider!r}", file=sys.stderr)
            return 1
    if args.json:
        out = []
        for p in providers:
            out.append({"id": p.get("id"), "connected": p.get("id") in connected, "models": list(p.get("models", {}).keys())})
        _print_json(out)
        return 0
    for p in providers:
        pid = p.get("id", "?")
        is_conn = pid in connected
        if args.connected_only and not is_conn:
            continue
        models = p.get("models", {})
        print(f"{pid} ({'connected' if is_conn else 'not connected'}, {len(models)} models):")
        for mid, m in list(models.items())[: args.limit]:
            fam = m.get("family", "")
            ctx = (m.get("limit") or {}).get("context", "?")
            print(f"  - {mid}  family={fam}  context={ctx}")
        if len(models) > args.limit:
            print(f"  ... ({len(models) - args.limit} more; raise --limit)")
        print()
    return 0


# ---------------------------------------------------------------------------
# Subcommands — sessions / run
# ---------------------------------------------------------------------------


def cmd_sessions(args) -> int:
    if args.action == "get":
        if not args.id:
            print("FAIL: `oc sessions get <id>` needs a session id", file=sys.stderr)
            return 1
        try:
            status, doc = http_json(
                "GET", f"{OC_SERVER}/session/{args.id}", bearer=OC_TOKEN, timeout=args.timeout,
                extra_headers=_opencode_auth_headers(),
            )
        except OcError as e:
            print(f"FAIL: {e}", file=sys.stderr)
            return 1
        if status != 200:
            print(f"FAIL: HTTP {status}: {doc}", file=sys.stderr)
            return 1
        if args.json:
            _print_json(doc)
        else:
            print(f"id:        {doc.get('id')}")
            print(f"title:     {doc.get('title')}")
            print(f"directory: {doc.get('directory')}")
            print(f"cost:      {doc.get('cost')}")
            tok = doc.get("tokens", {})
            print(f"tokens:    in={tok.get('input')} out={tok.get('output')}")
        return 0

    # default: list
    try:
        status, doc = http_json(
            "GET", f"{OC_SERVER}/session", bearer=OC_TOKEN, timeout=args.timeout,
            extra_headers=_opencode_auth_headers(),
        )
    except OcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if status != 200:
        print(f"FAIL: HTTP {status}: {doc}", file=sys.stderr)
        return 1
    if args.json:
        _print_json(doc)
        return 0
    items = doc if isinstance(doc, list) else []
    if not items:
        print("(no sessions)")
        return 0
    for s in items[: args.limit]:
        print(f"- {s.get('id')}  {s.get('title', '')!r}  dir={s.get('directory')}  updated={s.get('time', {}).get('updated')}")
    return 0


def _pick_default_model(provider_doc: dict) -> tuple[str, str] | None:
    connected = provider_doc.get("connected", [])
    if not connected:
        return None
    defaults = provider_doc.get("default", {})
    pid = connected[0]
    mid = defaults.get(pid)
    if not mid:
        for p in provider_doc.get("all", []):
            if p.get("id") == pid:
                models = list(p.get("models", {}).keys())
                mid = models[0] if models else None
                break
    if not mid:
        return None
    return pid, mid


def cmd_run(args) -> int:
    timeout = args.timeout or RUN_TIMEOUT

    # OC_WORKSPACE-gated directory default (see its module-level doc comment)
    # -- an explicit --directory always wins; otherwise, if OC_WORKSPACE is
    # set, isolate this run under a fresh slug beneath it instead of the
    # shared default scope.
    directory = args.directory
    if directory is None and OC_WORKSPACE:
        slug = f"{int(time.time())}-{os.getpid()}"
        directory = f"{OC_WORKSPACE.rstrip('/')}/{slug}"

    # model selection
    if args.model:
        if "/" not in args.model:
            print("FAIL: --model must be provider/model, e.g. groq/llama-3.1-8b-instant", file=sys.stderr)
            return 1
        provider_id, model_id = args.model.split("/", 1)
    else:
        try:
            doc = _fetch_providers(timeout)
        except OcError as e:
            print(f"FAIL: could not discover a default model: {e}", file=sys.stderr)
            return 1
        picked = _pick_default_model(doc)
        if not picked:
            print("FAIL: no connected provider to pick a default model from; pass --model provider/model", file=sys.stderr)
            return 1
        provider_id, model_id = picked

    # session: reuse or create
    session_id = args.session
    if not session_id:
        try:
            qs = f"?directory={urllib.request.quote(directory)}" if directory else ""
            status, doc = http_json(
                "POST", f"{OC_SERVER}/session{qs}", bearer=OC_TOKEN, json_body={}, timeout=timeout,
                extra_headers=_opencode_auth_headers(),
            )
        except OcError as e:
            print(f"FAIL: session create: {e}", file=sys.stderr)
            return 1
        if status != 200:
            print(f"FAIL: session create HTTP {status}: {doc}", file=sys.stderr)
            return 1
        session_id = doc.get("id")
        if not session_id:
            print(f"FAIL: session create returned no id: {doc}", file=sys.stderr)
            return 1

    body = {
        "model": {"providerID": provider_id, "modelID": model_id},
        "parts": [{"type": "text", "text": args.prompt}],
    }
    try:
        qs = f"?directory={urllib.request.quote(directory)}" if directory else ""
        status, doc = http_json(
            "POST", f"{OC_SERVER}/session/{session_id}/message{qs}", bearer=OC_TOKEN, json_body=body, timeout=timeout,
            extra_headers=_opencode_auth_headers(),
        )
    except OcError as e:
        print(f"FAIL: prompt: {e}", file=sys.stderr)
        return 1

    if args.json:
        _print_json({"session_id": session_id, "provider": provider_id, "model": model_id, "response": doc})

    if status != 200:
        print(f"FAIL: HTTP {status}: {_truncate(doc, 400)}", file=sys.stderr)
        print(f"session: {session_id}  model: {provider_id}/{model_id}", file=sys.stderr)
        return 1

    info = doc.get("info", {}) if isinstance(doc, dict) else {}
    err = info.get("error")
    if err:
        name = err.get("name", "Error")
        message = (err.get("data") or {}).get("message", "")
        print(f"FAIL: server error [{name}]: {message}", file=sys.stderr)
        print(f"session: {session_id}  model: {provider_id}/{model_id}", file=sys.stderr)
        return 1

    if not args.json:
        parts = doc.get("parts", []) if isinstance(doc, dict) else []
        text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
        print(text if text.strip() else "(no text content in response — pass --json to inspect parts)")
        print(f"\n[session: {session_id}  model: {provider_id}/{model_id}]")
    return 0


# ---------------------------------------------------------------------------
# Subcommands — runs (agentos-api spine run ledger)
# ---------------------------------------------------------------------------


def cmd_runs(args) -> int:
    key = get_os_security_key()
    if not key:
        print(f"FAIL: OS_SECURITY_KEY not found in {INFRA_SECRETS_FILE}", file=sys.stderr)
        return 1

    if args.action == "get":
        if not args.id:
            print("FAIL: `oc runs get <run_id>` needs a run id", file=sys.stderr)
            return 1
        url = f"{AGENTOS_URL}/v1/runs/{args.id}"
        status, doc = http_json("GET", url, bearer=key, timeout=args.timeout)
    elif args.action == "start":
        if not args.file:
            print("FAIL: `oc runs start <file> --workflow X --domain Y` needs a file", file=sys.stderr)
            return 1
        try:
            with open(args.file, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            print(f"FAIL: cannot read {args.file}: {e}", file=sys.stderr)
            return 1
        body = {"workflow": args.workflow, "domain": args.domain, "input": content, "source_path": args.file}
        status, doc = http_json("POST", f"{AGENTOS_URL}/v1/runs", bearer=key, json_body=body, timeout=args.timeout)
    else:  # list
        status, doc = http_json("GET", f"{AGENTOS_URL}/v1/runs", bearer=key, timeout=args.timeout)

    if status == 404:
        # Spec'd contract (POST/GET /v1/runs) is not deployed on this build
        # yet (verified live 2026-07-20 — AgentOS currently only exposes
        # per-type run ledgers: /workflows/{id}/runs, /agents/{id}/runs,
        # /teams/{id}/runs; workflow_count=0 on this instance). Clean,
        # documented, non-crashing 404 — this is the expected state until a
        # parallel build lands the unified spine ledger.
        print("runs API not deployed on this AgentOS build yet (HTTP 404 on /v1/runs).")
        print("Current live shape instead nests runs per resource type: /agents/{id}/runs,")
        print("/workflows/{id}/runs, /teams/{id}/runs (see `oc doctor` / SKILL.md notes).")
        return 1

    if args.json:
        _print_json(doc)
        return 0 if status < 400 else 1

    if status >= 400:
        print(f"FAIL: HTTP {status}: {_truncate(doc, 300)}", file=sys.stderr)
        return 1

    if args.action == "list":
        items = doc if isinstance(doc, list) else doc.get("data", []) if isinstance(doc, dict) else []
        if not items:
            print("(no runs)")
            return 0
        for r in items:
            print(f"- {r.get('id', r.get('run_id', '?'))}  status={r.get('status')}  workflow={r.get('workflow')}")
        return 0

    print(json.dumps(doc, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# Subcommands — tools (MCP catalogs)
# ---------------------------------------------------------------------------


def cmd_tools(args) -> int:
    if args.action == "call":
        if not args.target or ":" not in args.target:
            print("FAIL: `oc tools call <server>:<tool> --args '<json>'` — server must be agentos or contextforge", file=sys.stderr)
            return 1
        server, tool_name = args.target.split(":", 1)
        try:
            arguments = json.loads(args.args) if args.args else {}
        except json.JSONDecodeError as e:
            print(f"FAIL: invalid JSON in --args: {e}", file=sys.stderr)
            return 1
        try:
            client = _mcp_client(server)
            result = client.call_tool(tool_name, arguments)
        except OcError as e:
            print(f"FAIL: {e}", file=sys.stderr)
            return 1
        _print_json(result)
        return 0

    # default: list
    servers = [args.server] if args.server else ["agentos", "contextforge"]
    exit_code = 0
    for server in servers:
        print(f"=== {server} ===")
        try:
            client = _mcp_client(server)
            tools = client.list_tools()
        except OcError as e:
            print(f"FAIL: {e}", file=sys.stderr)
            exit_code = 1
            continue
        if args.json:
            _print_json({server: tools})
            continue
        for t in tools:
            print(f"{server}:{t['name']:<40} {_truncate(t.get('description', ''), 90)}")
        print(f"({len(tools)} tools)\n")
    return exit_code


# ---------------------------------------------------------------------------
# Subcommands — ksearch (agentos knowledge search)
# ---------------------------------------------------------------------------


def cmd_ksearch(args) -> int:
    key = get_os_security_key()
    if not key:
        print(f"FAIL: OS_SECURITY_KEY not found in {INFRA_SECRETS_FILE}", file=sys.stderr)
        return 1
    body = {"query": args.query, "limit": args.limit}
    try:
        status, doc = http_json("POST", f"{AGENTOS_URL}/knowledge/search", bearer=key, json_body=body, timeout=args.timeout)
    except OcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if args.json:
        _print_json(doc)
        return 0 if status < 400 else 1
    if status >= 400:
        print(f"FAIL: HTTP {status}: {_truncate(doc, 300)}", file=sys.stderr)
        return 1
    items = doc.get("data", []) if isinstance(doc, dict) else []
    meta = doc.get("meta", {}) if isinstance(doc, dict) else {}
    if not items:
        note = ""
        if meta.get("total_count", 0) == 0:
            note = " (empty result — collection may be gated/unindexed, not necessarily an error)"
        print(f"(no results for {args.query!r}{note})")
        return 0
    for hit in items:
        print(f"- {_truncate(hit.get('content', hit), 160)}")
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="raw JSON output")
    common.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"request timeout in seconds (default {DEFAULT_TIMEOUT})")

    p = argparse.ArgumentParser(
        prog="oc",
        description="OpenCode-ops CLI — headless OpenCode server + agentos-api + agentos-mcp + ContextForge, one control surface.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("doctor", help="probe all endpoints (opencode, agentos-api, both MCP doors)", parents=[common])
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("providers", help="list OpenCode providers (connected + known)", parents=[common])
    sp.set_defaults(func=cmd_providers)

    sp = sub.add_parser("models", help="list models for OpenCode providers", parents=[common])
    sp.add_argument("--provider", default=None, help="filter to one provider id")
    sp.add_argument("--limit", type=int, default=15, help="max models shown per provider (default 15)")
    sp.add_argument("--connected-only", action="store_true", help="only show connected/usable providers")
    sp.set_defaults(func=cmd_models)

    sp = sub.add_parser("sessions", help="list or get OpenCode sessions", parents=[common])
    sp.add_argument("action", nargs="?", choices=["list", "get"], default="list")
    sp.add_argument("id", nargs="?", default=None)
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_sessions)

    sp = sub.add_parser("run", help="create/reuse a session, send a prompt, print the final text", parents=[common])
    sp.add_argument("prompt")
    sp.add_argument("--model", default=None, help="provider/model, e.g. groq/llama-3.1-8b-instant (default: first connected provider's default)")
    sp.add_argument("--session", default=None, help="reuse this session id instead of creating one")
    sp.add_argument("--directory", default=None, help="isolate the session under this directory (avoids the shared 'global' project context)")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("runs", help="agentos-api run ledger: list | get <run_id> | start <file> --workflow X --domain Y", parents=[common])
    sp.add_argument("action", nargs="?", choices=["list", "get", "start"], default="list")
    sp.add_argument("target", nargs="?", default=None, help="run_id (get) or input file (start)")
    sp.add_argument("--workflow", default=None, choices=["chat-transcript", "sms-xml"], help="workflow slug (start)")
    sp.add_argument("--domain", default=None, help="domain tag (start)")
    sp.set_defaults(func=_dispatch_runs)

    sp = sub.add_parser("tools", help="MCP tool catalogs: list | call <server>:<tool> --args '<json>'", parents=[common])
    sp.add_argument("action", nargs="?", choices=["list", "call"], default="list")
    sp.add_argument("target", nargs="?", default=None, help="server:tool for call")
    sp.add_argument("--server", choices=["agentos", "contextforge"], default=None, help="restrict `list` to one server")
    sp.add_argument("--args", default=None, help="JSON arguments object for call")
    sp.set_defaults(func=_dispatch_tools)

    sp = sub.add_parser("ksearch", help="POST /knowledge/search on agentos-api", parents=[common])
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.set_defaults(func=cmd_ksearch)

    return p


def _dispatch_runs(args) -> int:
    # normalize `runs get <id>` / `runs start <file>` into the id/file fields
    args.id = args.target if args.action == "get" else None
    args.file = args.target if args.action == "start" else None
    return cmd_runs(args)


def _dispatch_tools(args) -> int:
    args.target = args.target  # already set; kept for symmetry/readability
    return cmd_tools(args)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OcError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
