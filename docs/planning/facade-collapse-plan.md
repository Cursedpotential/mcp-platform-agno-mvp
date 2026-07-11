# Facade-Collapse Execution Plan

> _Byline: Claude Code · Sonnet 5 · 2026-07-09_
> Status: **PLAN ONLY — not executed.** Deploy-coupled (every push to `main` auto-redeploys the
> exec tier, D-011); needs owner review + a coordinated redeploy window before any step runs.
> Tracked TODO: `docs/COORDINATION.md` line 98 ("FACADE COLLAPSE + SEMANTICA MOVE").
> Supersedes the MCP-exposure decision in `docs/planning/sbv-mcp-integration-plan.md` (that plan's
> "Facade + ContextForge REST-wrap" decision, line 15, is the thing this plan replaces — SBV's
> other build tasks there, e.g. `sbv_sms.py` as primary SMS-XML parser, are unaffected and stay).

> ---
> ## ⚠️ SUPERSEDED / PARTIALLY MOOT — corrected 2026-07-10
>
> **Batch A** (add the G4 gateway + SBV toolkit as agno `@tool`s) was **built, merged, and deployed**
> (`bec5596`). **Batches B and C are MOOT — do not execute them.** This plan's core premise — that
> `enable_mcp_server` re-exports granular `@tool` functions over `agentos-mcp`, so ContextForge could
> be repointed there (Batch B) and the facade removed (Batch C) — is **FALSE.** Verified from agno
> source (`agno/os/app.py:588-595`): AgentOS's MCP surface collects only `MCPTools`/`MultiMCPTools`
> instances (external MCP servers) and exposes ~19 AgentOS *operations* (run_agent/team/workflow,
> session/memory mgmt) — **never** the parser/SBV `@tool`s. The **facade therefore STAYS**: it is the
> only granular-tool MCP surface. All 14 facade tools were instead registered directly in
> ContextForge as REST tools (virtual server `platform_tools`, 2026-07-10). The clean future is
> promoting the G4 `tool_finder` into a *dedicated* MCP gateway, not removing the facade.
>
> Also: since ADR-0035 (2026-07-10) `tool_finder` now lives at **`server/tools/gateway/`**, not
> `server/evidence/tool_finder/` as the paths below still say. This document is retained as a
> historical record of the (corrected) plan.
> ---

## 0. Ground truth this plan was verified against

All paths relative to `Agno-MCP-Platform/`. Re-verified directly from source on `main`
(HEAD `3068266`, 2026-07-09) — not carried over from the scout report uncritically. Two
corrections to the scout findings are called out inline where my read of the file differed.

- `server/agents/providers.py:169` — `source_tools = [*code_tools, *db_tools]`, appended to at
  `:178-189` only for Graphiti. This is the single append point for goals 1 and 2.
- `server/evidence/tool_finder/toolfinder.py` — the five G4 meta-ops (`get_tool_categories`,
  `search_tools`, `describe_tool`, `execute_tool`, `get_ref`) already exist here, pure functions
  over `server.tools.registry` (imported at `:17`). **Correction to the scout report:** this file
  lives under `server/evidence/tool_finder/`, not `server/tools/` — the G4 layer was never moved
  in the D-026 promotion (`docs/COORDINATION.md:114-132`). See open question OQ-6.
- `server/evidence/tool_finder/api.py` — a FastAPI wrapper over the same five functions, built
  for ContextForge REST-wrapping (docstring cites ADR-0023), confirmed **not mounted in any
  compose file today** (`grep -rn "tool_finder.api\|build_app" compose*.yaml` → no hits).
- `docker/tools/supervisord.conf` — two programs: `[program:sbv]` (:1-10) and
  `[program:tools-facade]` (:12-18, `uvicorn facade:app --port 8090`).
- `docker/tools/Dockerfile` — bakes the whole `server/` tree (`COPY server/ /opt/tools/server/`,
  line 63) into the facade image; `EXPOSE 8080 8090` (line 67, note 8080 is stale/unused — the
  container actually listens on 8085 for SBV per supervisord, and neither compose file publishes
  container-side 8080). **Correction to the scout report:** the Dockerfile's own comment at line
  54 says facade.py imports `server.evidence.registry` — that comment is stale prose left over
  from before D-026; the actual code (verified directly) imports `server.tools.registry`
  (`docker/tools/tools/facade.py:70`) and `server.tools._sbv_client` (`:142`). Functionally
  correct today, comment is not — worth a one-line fix while this file is being edited anyway.
- `compose.exec.yaml` (OVH-1, the box that actually redeploys on push) — `agentos-api` env block
  `:49-82`, `agentos-mcp` env block `:123-158`, `platform-tools` service `:202-234` with port
  publishes at `:215-216` (`8085:8085`, `8090:8090`) and volumes at `:217-219` (`sbv_data`,
  `r2-nexus`) — **no `server/` bind mount exists in the committed file**, confirming the bake, not
  a mount, is what actually ships.
- `compose.yaml` (the non-exec/local variant) mirrors this: `platform-tools` ports `:93-94`
  (`8080:8085`, `8090:8090`).
- **Cross-cutting flag — bake-vs-mount drift is real and multi-source, not just one stale
  comment.** Three independent sources describe a *mounted* `server/` tree that does not match
  the committed Dockerfile/compose:
  1. `docs/COORDINATION.md:114-132` (2026-07-09 ledger entry) describes a branch,
     `restructure/tools-layer` (commit `9bba295`), that mounts `./server:/opt/tools/server:ro`.
  2. `server/tools/registry.py:117-130` — `load_builtin_tools()`'s own docstring says the module
     "is also volume-mounted standalone into the docker/tools platform-tools facade container,
     where it's imported as the top-level `tools` package" — describing a *different* mount shape
     (renamed top-level `tools`, not `server.tools`) than either the ledger entry or the current
     Dockerfile.
  3. The Dockerfile's own stale comment (previous bullet).
  None of these three descriptions match the committed `docker/tools/Dockerfile`, which **bakes**
  the full `server/` tree preserving the `server.tools.*` import path. I verified `9bba295` is an
  ancestor of `main` (`git merge-base main restructure/tools-layer` → `9bba295`) but `git log
  --oneline -- docker/tools/Dockerfile` shows only 3 commits ever, none matching that ledger
  entry's description of the file — so whatever `restructure/tools-layer` did to `compose*.yaml`,
  it either never touched `docker/tools/Dockerfile` or was superseded before merge. **Net: trust
  the file, not the comments.** Ground truth is the bake. This plan removes the bake (§3); if the
  owner separately knows of an in-flight branch reintroducing a mount, reconcile before merging.
- SBV facade proxy routes actually implemented (`docker/tools/tools/facade.py:198-296`):
  `/sbv/health, /sbv/version, /sbv/upload, /sbv/progress, /sbv/messages, /sbv/conversations,
  /sbv/calls, /sbv/analytics, /sbv/search, /sbv/export` (`export` synthesized client-side from
  `messages`+`calls`, `:270-296`, because SBV's deployed build has no server-side `/api/export`).
  `SBVClient` (`server/tools/_sbv_client.py`) has more methods than the facade proxies —
  `hashes(import_id)` (forensic H1/H3 custody hashes, `:346-354`) and `wait_for_processing`
  (`:247-261`) are used internally by `/sbv/upload` but never exposed as their own route. Worth
  carrying `hashes` into the new toolkit (forensic custody chain is the whole point of the SBV
  fork) — flagged in §2.
- ContextForge is **live at v1.0.4** today (`docs/COORDINATION.md:180`, "41 tools / 4 gateways"),
  not the 0.8.0 the registration script hedges for (`scripts/register_sbv_contextforge.sh:27-30`).
  A proven native-MCP-peer registration already exists for `coolify-mcp`
  (`docs/COORDINATION.md:156-169`): CF gateway with `transport: STREAMABLEHTTP` pointed at a
  tailnet `host:port` (`100.72.169.40:8765`), NOT a compose/docker-network hostname — because
  ContextForge itself may not be on the same docker network as `agentos-mcp`. This is the concrete
  template for §4, and it corrects an assumption in the scout report that CF would reach
  `agentos-mcp` via a docker-network name (`http://agentos-mcp:8001/mcp`) — verify which is
  actually reachable before registering (see §4 preflight).
- `agno.tools.tool` decorator convention confirmed in `server/agents/factory.py:40,73-105`
  (`from agno.tools import tool`; `@tool(requires_confirmation=True)` for the HITL write). Plain
  read tools (what §1/§2 need) use `@tool` with no `requires_confirmation`.

---

## 1. Wire `server.tools` parsers into Agno so `agentos-mcp` serves them as MCP tools

**Decision (already locked, `docs/COORDINATION.md:98-100`):** wrap the five G4 progressive-disclosure
meta-ops, not all 23 raw parsers, to avoid flooding agent context with the full catalog.

### 1.1 New file: `server/agents/tools/gateway_tools.py`

(New subpackage `server/agents/tools/` — keeps agent-facing tool *wrappers* next to the agents
that consume them, distinct from `server/tools/` which is the atomic-parser registry itself and
`server/evidence/tool_finder/` which is the meta-op logic. See OQ-6 on whether tool_finder should
also move.)

```python
"""agents/tools/gateway_tools.py — agno @tool wrappers over the G4 progressive-
disclosure meta-ops (server/evidence/tool_finder/toolfinder.py). Exposes the
23-tool parser registry to agents/MCP clients as 5 thin functions instead of
one FunctionTool per parser, so the catalog never floods context (locked
decision, docs/COORDINATION.md:98-100).
"""

from __future__ import annotations

from typing import Any

from agno.tools import tool

from server.evidence.tool_finder.content_store import ContentStore
from server.evidence.tool_finder import toolfinder as _tf

_store = ContentStore()  # module-level singleton, mirrors toolfinder's own default


@tool
def get_tool_categories() -> list[dict[str, Any]]:
    """List every parser capability (category) with its tool count. Start here."""
    return _tf.get_tool_categories()


@tool
def search_tools(query: str = "", category: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Search parser tools by keyword, optionally scoped to one category."""
    return _tf.search_tools(query=query, category=category, limit=limit)


@tool
def describe_tool(tool_id: str) -> dict[str, Any]:
    """Full contract for one parser tool (payload shape, substitution candidates)."""
    return _tf.describe_tool(tool_id)


@tool
def execute_tool(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run a parser tool. Small results return inline; large ones return a REF
    (retrieve pages with get_ref) so a single call can't blow the context budget."""
    return _tf.execute_tool(tool_id, payload, store=_store)


@tool
def get_ref(ref: str, page: int = 0, page_size: int | None = None) -> dict[str, Any]:
    """Paged retrieval of a stored large result from execute_tool."""
    return _tf.get_ref(ref, page=page, page_size=page_size, store=_store)


GATEWAY_TOOLS: list[Any] = [get_tool_categories, search_tools, describe_tool, execute_tool, get_ref]
```

Notes:
- Module-level `ContentStore()` singleton so `execute_tool` REFs are retrievable by a later
  `get_ref` call in the same process — matches how `toolfinder.py` itself defaults `store=None ->
  ContentStore()` per-call in its own module (`toolfinder.py:100`, `:110`) but the wrapper needs
  one shared instance across calls or every REF dies with the call that made it. **Verify
  `ContentStore`'s backing store survives across a Python-process-local singleton in a multi-worker
  ASGI deployment** — `agentos-mcp` runs as a single `uvicorn` process (`compose.exec.yaml:114`,
  no `--workers`), so in-process singleton is safe today; would need a shared backend (Redis/DB) if
  that ever changes. Flag OQ-7.
- `execute_tool`'s payload is `dict[str, Any]` end-to-end (parsers take `{"path": <file>}`) — no
  new validation added here; the atomic tools already validate.

### 1.2 Edit: `server/agents/providers.py`

One-line append after the existing `source_tools` assembly, mirroring the Graphiti append pattern
already there:

```python
# after line 169: source_tools = [*code_tools, *db_tools]
from server.agents.tools.gateway_tools import GATEWAY_TOOLS  # add to the import block at top

source_tools = [*code_tools, *db_tools, *GATEWAY_TOOLS]
```

Concretely: add the import to the top-level import block (near `agno.context.workspace`
imports, `providers.py:34-35`), and change line 169 from
`source_tools = [*code_tools, *db_tools]` to `source_tools = [*code_tools, *db_tools,
*GATEWAY_TOOLS]`. No other file changes — `factory.py` and `main.py` are untouched, exactly as
the scout report found; every agent that receives `source_tools` (ingestion orchestrator,
analysis orchestrator, etc., `factory.py:143,173,...`) picks up the five gateway tools
automatically, and they ride the existing `enable_mcp_server=True` surface
(`server/api/main.py:157`) onto `agentos-mcp` (`server/api/mcp_main.py:23-28`) with zero compose
changes — the agentos images already bake the full `server/` tree via the repo-root `Dockerfile`.

### 1.3 Tests

Add `tests/agents/test_gateway_tools.py` (new, if `tests/agents/` doesn't exist, place under
whatever the existing agent-tool test layout uses — check `tests/` structure first, don't assume):
- `get_tool_categories()` returns >0 categories after `load_builtin_tools()` runs once.
- `search_tools("sms")` returns at least the SMS-XML parser card.
- `execute_tool` on a tiny known-good fixture returns `inline: True`; forcing a large synthetic
  payload through the same call returns a REF, and `get_ref` on that REF returns the same content
  page-by-page. (Reuses whatever fixtures `server/evidence/tool_finder/` already has tests
  against, if any — check for `tests/evidence/tool_finder/` before writing new ones from scratch.)

### 1.4 Deploy-only verification (cannot be verified pre-deploy)

- That `agentos-mcp`'s `tools/list` actually surfaces the five new tools over the wire — this is
  an integration property of FastMCP's sub-app extraction (`mcp_main.py`) that unit tests don't
  exercise. **Gate:** after this ships (bundled with §2, see §6), `curl`/MCP-client `tools/list`
  against `agentos-mcp:8001/mcp` (or via a temporary CF gateway pointed at it) and confirm
  `get_tool_categories` etc. appear before touching the facade in §3.

---

## 2. Wrap SBV's REST API (`:8085`) as an agno tool

### 2.1 New file: `server/agents/tools/sbv_tools.py`

Mirrors the facade's proxy surface (`docker/tools/tools/facade.py:198-296`) plus the two
`SBVClient` methods the facade never exposed (`hashes`, needed for the forensic custody chain —
see §0), as agno `@tool` functions over one `SBVClient` singleton:

```python
"""agents/tools/sbv_tools.py — agno @tool wrappers over SBVClient
(server/tools/_sbv_client.py), the SBV REST API (:8085). Mirrors the facade's
/sbv/* proxy surface (docker/tools/tools/facade.py:198-296) plus `hashes`
(forensic custody chain, never exposed by the facade)."""

from __future__ import annotations

from typing import Any

from agno.tools import tool

from server.tools._sbv_client import SBVClient, SBVError

_client: SBVClient | None = None


def _sbv() -> SBVClient:
    global _client
    if _client is None:
        _client = SBVClient()
    return _client


def _call(fn, *a, **kw) -> Any:
    try:
        return fn(*a, **kw)
    except SBVError as exc:
        return {"error": str(exc), "status": getattr(exc, "status", None)}


@tool
def sbv_health() -> dict[str, Any]:
    """SBV service health (public endpoint, no auth)."""
    return {"healthy": _sbv().health()}


@tool
def sbv_version() -> Any:
    return _call(_sbv().version)


@tool
def sbv_upload(path: str, wait: bool = True) -> Any:
    """Upload an SMS backup XML (path must be visible to this process — use
    the shared /r2 mount). Waits for processing to complete by default."""
    client = _sbv()
    result = _call(client.upload, path)
    if wait and isinstance(result, dict) and result.get("processing"):
        _call(client.wait_for_processing)
        result = {**result, "processing": False, "waited": True}
    return result


@tool
def sbv_progress() -> Any:
    return _call(_sbv().progress)


@tool
def sbv_messages(
    address: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Any:
    return _call(_sbv().messages, address=address, limit=limit, offset=offset,
                 start_date=start_date, end_date=end_date)


@tool
def sbv_conversations() -> Any:
    return _call(_sbv().conversations)


@tool
def sbv_calls(limit: int | None = None, offset: int | None = None) -> Any:
    return _call(_sbv().calls, limit=limit, offset=offset)


@tool
def sbv_analytics() -> Any:
    return _call(_sbv().analytics)


@tool
def sbv_search(query: str, limit: int | None = None) -> Any:
    return _call(_sbv().search, query, limit=limit)


@tool
def sbv_hashes(import_id: str = "latest") -> dict[str, Any]:
    """Forensic custody hashes (H1 file hash, H3 chain hash) for an SBV import
    batch. Ported from the SBV fork's custody-chain feature; never exposed by
    the old facade proxy."""
    return _call(_sbv().hashes, import_id)


@tool
def sbv_export(format: str = "json", address: str | None = None, include_calls: bool = True) -> Any:
    """Export-as-a-function. SBV's deployed build has no server-side
    /api/export (export is client-side in the GUI); this synthesizes the
    export from messages+calls, porting docker/tools/tools/facade.py:270-296
    so that logic isn't lost when the facade is removed (§3)."""
    client = _sbv()
    messages = _call(client.all_messages, address=address)
    calls = _call(client.all_calls) if include_calls else []
    if format == "csv":
        import csv
        import io
        buf = io.StringIO()
        if isinstance(messages, list) and messages:
            cols = sorted({k for m in messages for k in m.keys()})
            w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(messages)
        return {"format": "csv", "csv": buf.getvalue(),
                "message_count": len(messages) if isinstance(messages, list) else 0,
                "call_count": len(calls) if isinstance(calls, list) else 0}
    return {"format": "json", "messages": messages, "calls": calls}


SBV_TOOLS: list[Any] = [
    sbv_health, sbv_version, sbv_upload, sbv_progress, sbv_messages, sbv_conversations,
    sbv_calls, sbv_analytics, sbv_search, sbv_hashes, sbv_export,
]
```

Note: `_sbv_call`'s error mapping in the facade raises `HTTPException` (`facade.py:187-195`);
agno tools have no HTTP layer, so this plan returns a `{"error": ..., "status": ...}` dict instead
of raising — matches how agno tool functions are generally expected to surface soft failures back
to the calling agent rather than throwing. Confirm this convention against how other tools in the
codebase signal errors (`apply_db_modification` returns `"ERROR: ..."` strings, `factory.py:104`)
before finalizing — may want string-prefixed returns instead of dicts for consistency. Flag OQ-8.

### 2.2 Edit: `server/agents/providers.py` (same hook as §1.2)

```python
from server.agents.tools.sbv_tools import SBV_TOOLS

source_tools = [*code_tools, *db_tools, *GATEWAY_TOOLS, *SBV_TOOLS]
```

### 2.3 Config at cutover — `SBV_BASE_URL`/`SBV_SERVICE_*` on the agentos services

Today `agentos-api`/`agentos-mcp` have no `SBV_*` env at all (confirmed: `grep -n "SBV_"
compose.exec.yaml` → no hits outside `docker/tools/`). `_sbv_client.py:44` defaults
`SBV_BASE_URL` to `http://localhost:8085`, which is wrong from inside the `agentos-api`/
`agentos-mcp` containers — SBV is reachable on the `agentos` docker network at
`http://platform-tools:8085` (compose service name `platform-tools`, same network,
`compose.exec.yaml:233-234`).

Add to **both** `agentos-api` (`compose.exec.yaml:49-82` env block) and `agentos-mcp`
(`compose.exec.yaml:123-158` env block):

```yaml
      SBV_BASE_URL: ${SBV_BASE_URL:-http://platform-tools:8085}
      SBV_SERVICE_USER: ${SBV_SERVICE_USER:-mcp_service}
      SBV_SERVICE_PASS: ${SBV_SERVICE_PASS:?set SBV_SERVICE_PASS in Coolify app env}
```

`SBV_SERVICE_PASS` has no safe default (`_sbv_client.py:50` defaults to `""`, which raises
`SBVError` on first `login()`, `_sbv_client.py:174-175`) — this **must** be set in the Coolify app
env before the redeploy that adds these tools, or every SBV tool call fails at first use (not at
boot — `SBVClient` is lazy). Same credential the facade's `/sbv/*` proxy already uses today
(`_sbv_client.py:47-50` — check whether Coolify already has `SBV_SERVICE_PASS` set for
`platform-tools`; if so, reuse the same value for `agentos-api`/`agentos-mcp` — same service
account, same SBV instance).

Also add both to `compose.yaml` (the local/dev variant) mirroring the same keys, pointing at
whatever hostname the local compose uses for `platform-tools` — check `compose.yaml`'s network
section before writing this (not fully audited in this plan; do it in the PR diff, not blind).

### 2.4 Tests

`tests/agents/test_sbv_tools.py` — mock `SBVClient` (module already has no live-network test
dependency at import time; `SBVClient.__init__` doesn't connect) to verify: `sbv_export` CSV/JSON
shape parity with the old `facade.py:270-296` behavior (this is the one piece of business logic
being ported, not just re-plumbed — needs its own regression test so the port is provably
faithful), and that `sbv_health`/`sbv_*` degrade to the `{"error": ...}` shape on a simulated
`SBVError` rather than raising.

### 2.5 Deploy-only verification

- `SBV_SERVICE_PASS` actually resolves to a real value in the Coolify env (not the compose
  `:?` failure — if unset, the **container won't start**, which is a harder failure than a runtime
  auth error, so this is the first thing to check in the redeploy log).
- A live `sbv_health`/`sbv_conversations` call from an agent (or direct MCP `tools/call`) succeeds
  over the docker network, not just against `localhost` in dev.

---

## 3. Shrink `platform-tools` to SBV-only

**Do this only after §1+§2 are deployed and verified serving on `agentos-mcp`** (§6 sequencing) —
otherwise there is a coverage gap where the parser tools are reachable nowhere.

### 3.1 `docker/tools/supervisord.conf`

Remove `[program:tools-facade]` (lines 12-18). Keep `[program:sbv]` (lines 1-10) unchanged.

Optional simplification (not required, flag for owner): with only one supervised program left,
drop supervisord entirely and set the Dockerfile `CMD` to run `/opt/sbv/sbv` directly (still needs
`LD_LIBRARY_PATH=/opt/sbv-libs`, per the current `environment=` line in supervisord.conf:6). This
is a bigger blast-radius change (touches health-check assumptions, log capture via
`stdout_logfile=/dev/stdout`) for a modest simplification — recommend deferring to a follow-up,
not bundling into this cutover. OQ-9.

### 3.2 `docker/tools/Dockerfile`

Remove:
- `COPY docker/tools/tools/ /opt/tools/` (line 58)
- `COPY server/ /opt/tools/server/` (line 63) — the server-tree bake; confirmed this is a bake not
  a mount (§0)
- `RUN pip install --no-cache-dir fastapi uvicorn python-multipart pydantic` (line 64) — these
  deps exist ONLY for the facade; SBV itself is a static Go/musl binary with no Python deps
  (verify no other consumer in this image imports fastapi/pydantic before deleting — grep
  `docker/tools/` for `fastapi`/`pydantic` post-edit to confirm zero remaining references)
- `WORKDIR /opt/tools` (line 57) — no longer needed once nothing is copied there
- Change `EXPOSE 8080 8090` (line 67) → `EXPOSE 8085` (drop the unused 8080 too — see §0, nothing
  publishes container-side 8080 in either compose file today; if that's wrong, keep it, but the
  scout report's suggested `EXPOSE 8080 8085` doesn't match what's actually published — verify
  against Coolify's actual generated compose before finalizing, not just the repo's compose files,
  since Coolify materializes its own values per the global CLAUDE.md Coolify note)

Keep the SBV build stage (`FROM ghcr.io/cursedpotential/sbv-forensic:0.2.3-forensic AS sbv`, line
32) and the final-stage `COPY --from=sbv` layers (lines 46-48) untouched — this is the actual SBV
runtime, unaffected by the facade removal.

While in this file: fix the stale `server.evidence.registry` comment at line 54/59 — or just
delete the whole comment block since it's about to be irrelevant (the facade section is gone).

### 3.3 `compose.exec.yaml` + `compose.yaml` (`platform-tools` service)

- Remove the `:8090` port publish — `compose.exec.yaml:216`, `compose.yaml:94`.
- Keep the `:8085` publish — `compose.exec.yaml:215`, `compose.yaml:93`.
- Keep `sbv_data` + `r2-nexus` volumes (`compose.exec.yaml:217-219`) — `r2-nexus` may turn out to
  be facade-only (used for `/sbv/upload`'s `path` reads pointing at `/r2/...xml`, per
  `facade.py:211-212`); but SBV's own upload flow may also need `/r2` if agents pass R2-resident
  files. **Check whether `sbv_upload`'s `path` argument in the new `sbv_tools.py` (§2.1) needs the
  same `/r2` mount on `platform-tools` — it does, unchanged, since `SBVClient.upload()` just reads
  a local file path** (`_sbv_client.py:220-224`) and that path has to resolve inside
  `platform-tools` regardless of which process calls it. Keep the mount.
- Remove the stale "server baked in" explanatory comment (`compose.exec.yaml:220-223`).
- Add `SBV_BASE_URL`/`SBV_SERVICE_*` to `agentos-api`/`agentos-mcp` per §2.3 (same commit, since
  it's part of the same redeploy).

### 3.4 Net effect

`platform-tools` shrinks to a pure SBV host: Go/musl binary + REST `:8085`, no Python, no facade.
The `server.tools` parser registry ceases to exist in the `platform-tools` image; it lives only in
the `agentos-api`/`agentos-mcp` images (which already bake the full `server/` tree via the
repo-root `Dockerfile`, unaffected by this change).

### 3.5 Deploy-only verification

- Image builds and `platform-tools` boots with only `sbv` under supervisord (or directly, if OQ-9
  is taken) — watch the Coolify build log for the removed pip install actually shrinking build
  time/image size as a sanity signal.
- `:8085` still serves the SBV GUI/API; `:8090` is gone (curl should refuse/timeout, not 404 —
  confirms the port isn't published, not just unrouted).
- **This step is irreversible in the sense that it deletes the parser registry from this image** —
  rollback is redeploying the previous image tag (Coolify keeps prior builds), not a quick config
  flip. Doubly confirms why §1+§2 verification must precede this step (§6).

---

## 4. Repoint ContextForge from the facade OpenAPI to `agentos-mcp` + SBV

### 4.1 What changes

Stop REST-wrapping `platform-tools-sbv` (the facade's single OpenAPI covering both `/sbv/*` and
`/tools/*`, `scripts/register_sbv_contextforge.sh:9-14`). That registration was **never actually
applied** — `docs/COORDINATION.md:80-81` confirms it's still queued/DRY-RUN-only, so there is
nothing live to migrate off of; this is a clean swap, not a cutover with existing traffic.

Register `agentos-mcp` as a native MCP peer instead — same shape already proven for `coolify-mcp`
(`docs/COORDINATION.md:156-169`): a ContextForge gateway with `transport: STREAMABLEHTTP`
(**not** the default SSE — CF hangs on streamable-http servers without this explicit field, same
footgun noted for graphiti, `providers.py:184-188`) pointed at wherever ContextForge can actually
reach `agentos-mcp`.

### 4.2 Target URL — needs a preflight check, not an assumption

The `coolify-mcp` precedent points at a **tailnet IP:port** (`100.72.169.40:8765`), not a
docker-compose network hostname — implying ContextForge may not share a docker network with every
MCP peer it federates. `agentos-mcp` publishes `${BIND_IP:-127.0.0.1}:8001:8001`
(`compose.exec.yaml:117`) on OVH-1's tailnet IP when `BIND_IP` is set correctly per the exec-tier
convention (`compose.exec.yaml:9-10`) — so the reachable URL is almost certainly
`http://100.72.169.40:8001/mcp` (tailnet), mirroring the `coolify-mcp` pattern, rather than
`http://agentos-mcp:8001/mcp` (docker-network name) as the scout report assumed. **Verify which one
resolves from wherever ContextForge itself runs** (check `docs/COORDINATION.md` for
ContextForge's own host/network placement, or just try both from inside the CF container) before
writing the registration payload. This is a deploy-time preflight, not something resolvable from
the repo alone. Flag OQ-1 (also the top rollback-relevant unknown — see §6).

Also confirm whether `agentos-mcp`'s `/mcp` route requires the basic-auth Traefik middleware seen
at `compose.exec.yaml:168-169` (`mcp-auth`, user `matt`) when reached via the **public** Traefik
route (`agentos.mitechconsult.com` + `PathPrefix(/mcp)`) — if CF registers against the public
HTTPS route instead of the tailnet-direct port, it needs those credentials in the gateway config;
if it registers against the tailnet-direct `:8001`, no Traefik/auth layer is in the path at all.
Prefer the tailnet-direct path (matches the `coolify-mcp` precedent, avoids putting a shared
password in a CF gateway config). OQ-2.

### 4.3 New/updated script

Retire or rewrite `scripts/register_sbv_contextforge.sh`. Given the script currently hard-targets
`FACADE_URL:8090` end-to-end (preflight curl at `:39-44`, registration payloads at `:66-94`), a
rewrite is cleaner than patching:

```bash
# scripts/register_agentos_mcp_contextforge.sh (new name — reflects the new target)
# Registers agentos-mcp as a native MCP peer Gateway (transport=STREAMABLEHTTP),
# same pattern as coolify-mcp (docs/COORDINATION.md:156-169).
CF_URL="${CF_URL:-http://contextforge:4444}"
AGENTOS_MCP_URL="${AGENTOS_MCP_URL:?set to the tailnet-reachable agentos-mcp URL — verify per OQ-1}"
CF_TOKEN="${CF_TOKEN:?set CF_TOKEN to a ContextForge admin JWT}"

curl -fsS -X POST "${CF_URL}/gateways" \
  -H "Authorization: Bearer ${CF_TOKEN}" -H "Content-Type: application/json" \
  -d '{
    "name": "agentos-mcp",
    "description": "AgentOS MCP surface — agents/teams + parser gateway tools (G4) + SBV toolkit",
    "transport": "STREAMABLEHTTP",
    "url": "'"${AGENTOS_MCP_URL}"'"
  }'
```

Since CF is confirmed live at v1.0.4 (§0), drop the script's 0.8.x dual-path hedge
(`register_server_0_8`, `:81-94`) entirely — that branch is now dead weight, not a real target.
Keep the DRY-RUN-by-default / `--apply` gate (`:96-108`) — same safety property, still a live prod
write.

### 4.4 Retire the old facade gateway registration

Since `platform-tools-sbv` was never actually registered (§4.1), there is nothing to de-register.
If the owner runs the OLD script's `--apply` before this plan executes (it's sitting ready to fire
per `docs/COORDINATION.md:80-81`), reconcile: either skip that and go straight to §4.3, or if it's
already been applied by the time this plan is picked up, add a de-registration step (`DELETE
{CF_URL}/gateways/{id}` or the CF admin UI) before or alongside registering `agentos-mcp`, per the
"doors policy" the scout report cites (matches how the old read-only `coolify` gateway was left
registered-but-redundant rather than deleted, `docs/COORDINATION.md:166-167` — confirm which
policy — delete vs. leave-redundant — actually applies here with the owner). OQ-3.

### 4.5 Deploy-only verification

- `curl -s -H "Authorization: Bearer $CF_TOKEN" $CF_URL/tools | grep -i "sbv\|get_tool_categories"`
  — confirms the new tools actually federated through, not just that the POST returned 200.
- End-to-end: call one gateway tool and one SBV tool through ContextForge (not directly against
  `agentos-mcp`) to prove the federation hop works, mirroring how `coolify-write` was verified
  end-to-end (`docs/COORDINATION.md:164-165`, "verified end-to-end (initialize/tools-list/
  list-projects with real data)").

---

## 5. G4 tool_finder progressive-disclosure layer — OPTIONAL, in front of CF

This is explicitly a *contingency*, not part of the primary path (`docs/COORDINATION.md:98-100`
locks agno-native as the target). Nothing in §1-4 requires it. Document it here only so it's not
lost as an option:

- `server/evidence/tool_finder/api.py` already exposes the same five meta-ops as a standalone
  FastAPI app (`build_app()`), designed from the start for ContextForge OpenAPI-wrapping
  (docstring cites ADR-0023 explicitly). It is **not mounted anywhere today** — no compose service
  runs it.
- If a future need arises for a REST-facing (non-MCP) consumer of the meta-ops — e.g. the "shell's
  tool-catalog page" the module docstring mentions (`toolfinder.py:6`) — mount `api.py`'s
  `build_app()` behind a small uvicorn service (its own tiny container, or as a route on an
  existing FastAPI app if one is already running) and CF-REST-wrap that, additively, alongside the
  native `agentos-mcp` federation from §4. It would NOT replace §1/§2 — those still need to exist
  for agents to have direct in-process tool access without a network hop.
- No file changes proposed here; this section is a pointer for if/when the owner wants it, not a
  step to execute.

---

## 6. Sequencing, deploy gates, and rollback

Every step below is a push to `main`-adjacent branches; **the auto-deploy trigger is the merge to
`main` itself** (D-011), so "deploy" in this section always means "merge this batch to `main`."
Per repo convention, work happens on a branch, gates run there, and only the owner merges.

### Batch A — add the tools (agentos images only; platform-tools untouched)
**Ships:** §1 (`server/agents/tools/gateway_tools.py`, `providers.py` append) + §2
(`server/agents/tools/sbv_tools.py`, `providers.py` append, `SBV_BASE_URL`/`SBV_SERVICE_*` env on
`agentos-api`+`agentos-mcp` in both compose files).
**Why bundled:** both are additive, low-risk, touch only the `agentos-*` images/services, and
share the single `providers.py:169` edit point — no reason to split into two redeploys.
**Pre-merge gates:** `uv run ruff check .`, `uv run mypy .`, `uv run python -m pytest -q`
(baseline 191 pass + new tests from §1.3/§2.4). Confirm `SBV_SERVICE_PASS` is set in the Coolify
app env for `agentos-api`/`agentos-mcp` **before** merging (the compose `:?` will hard-fail
container start otherwise — worse than a soft runtime error).
**Post-deploy verification (must pass before Batch B):**
1. `agentos-mcp` boots clean (no import errors from the new `server/agents/tools/` modules).
2. MCP `tools/list` against `agentos-mcp` (tailnet URL from §4.2, or via a temp local port-forward)
   includes `get_tool_categories`, `search_tools`, `describe_tool`, `execute_tool`, `get_ref`,
   `sbv_health`, `sbv_upload`, ... — full list from §1/§2.
3. Live call: `get_tool_categories()` returns real categories; `sbv_health()` returns
   `{"healthy": true}` (proves the `SBV_BASE_URL`/`platform-tools` network path works).
4. The OLD facade (`:8090`) is still up and unaffected — this batch does not touch it, so this
   should be trivially true, but confirm as a sanity check that nothing accidentally regressed the
   facade's own image build (it shares the `server/` tree source, not the container).
**If any of 1-4 fail:** do not proceed to Batch B. Roll back Batch A by reverting the merge commit
(redeploy previous `main` HEAD) — cheap, since nothing downstream depends on it yet.

### Batch B — repoint ContextForge
**Ships:** §4 (new/rewritten registration script; **script execution**, i.e. `--apply`, is a
manual owner-gated action, not a file change that auto-deploys — running it is a live write to
prod CF, same caution class as the existing script already carries).
**Pre-condition:** Batch A's post-deploy verification (all 4 checks) passed.
**Gate:** owner runs the new script with `--apply` only after confirming OQ-1/OQ-2 (the actual
reachable URL for `agentos-mcp` from ContextForge's vantage point) — this cannot be verified from
the repo, only from the live CF box.
**Post-apply verification:** §4.5's two checks (tools list via CF, end-to-end call via CF).
**Rollback:** `DELETE` the newly-created CF gateway (or disable it via admin UI) — does not touch
`agentos-mcp` or `platform-tools`, fully reversible with no redeploy needed.

### Batch C — shrink platform-tools (removes the facade)
**Ships:** §3 (supervisord.conf, Dockerfile, both compose files).
**Pre-condition — HARD GATE:** Batch A verification passed AND Batch B verification passed (CF is
actually serving the gateway tools + SBV tools through the new federation). This is the coverage-
gap-prevention gate the task asked for explicitly: **do not remove the facade until there is proof
positive that every consumer that used to reach the facade (CF, and by extension anything CF
fronts) can reach the same functionality through `agentos-mcp` instead.** Since the facade's CF
registration was never actually applied (§4.1/§4.4), the practical risk here is lower than a
"real cutover" — but the *parser registry* itself (23 tools, reachable only via the facade's raw
`/tools/*` REST surface today) still has no other consumer if Batch A's `execute_tool`/`describe_tool`
wrapper isn't proven working, so the gate stands regardless of CF's registration status.
**Gates:** `uv run ruff check .` / `uv run mypy .` / `uv run python -m pytest -q` on the branch —
note this batch has almost no Python surface (Dockerfile/compose/supervisord.conf are not covered
by these gates), so the real gate is the deploy-time image build + boot, not CI.
**Post-deploy verification:** §3.5's three checks (image builds smaller, `:8085` up, `:8090`
refused).
**Rollback:** redeploy the previous `agno-platform-tools:latest` image tag (Coolify retains prior
builds per the platform-wide convention) — restores the facade immediately. This is the step
where rollback is *heaviest* (a redeploy, not a config flip), which is exactly why it's gated last
and requires both prior batches proven first.

### Explicit non-goals for this cutover
- §5 (G4 REST-facing layer) — not scheduled, contingency only.
- SBV Phase 5a (native Go `/api/automation/*`) — separately tracked, deferred
  (`docs/COORDINATION.md:74-77`), unaffected by this plan; the `sbv_export` synthesis (§2.1) is the
  interim shim either way, in the toolkit now instead of the facade.
- Any change to `docker/tools/tools/facade.py`'s twin `/tools/*` registry-run surface being ported
  1:1 — it isn't; only the SBV proxy and the parser *access pattern* (via G4 meta-ops, not raw
  per-tool REST routes) are preserved. If some external consumer depended on
  `POST /tools/{tool_id}/run` directly (raw REST, `facade.py:117`) rather than the G4 meta-ops
  (`/tools`, `/tools/resolve/{capability}`, `facade.py:103,110`), that consumer loses that exact
  shape and must move to MCP `execute_tool` calls instead. Confirm no such consumer exists before
  Batch C. OQ-4.

---

## 7. Open questions for the owner

- **OQ-1 (blocking Batch B):** What URL does ContextForge actually use to reach `agentos-mcp` —
  tailnet IP:port (`100.72.169.40:8001`, matching the `coolify-mcp` precedent) or a docker-network
  hostname (`agentos-mcp:8001`, matching the scout report's assumption)? Depends on whether CF and
  `agentos-mcp` share a docker network — not resolvable from this repo's compose files alone since
  CF's own compose/deployment definition wasn't in scope of this read.
- **OQ-2 (blocking Batch B):** Should the CF registration go through the public Traefik route
  (`agentos.mitechconsult.com/mcp`, behind `mcp-auth` basic auth) or the tailnet-direct port
  (`:8001`, no auth layer)? Recommend tailnet-direct (matches precedent, avoids storing a shared
  password in a CF gateway config) but the owner may have a reason for the public route (e.g. CF
  itself isn't tailnet-joined).
- **OQ-3:** Confirm whether the "doors policy" for a superseded CF gateway is delete or
  leave-registered-but-redundant (precedent for both exists: coolify-mcp's old read-only gateway
  was left registered, `docs/COORDINATION.md:166-167`) — moot here since the facade gateway was
  never actually applied (§4.1), but worth confirming for future retirements.
- **OQ-4 (blocking Batch C):** Does any current or planned consumer call the facade's raw
  per-tool REST route (`POST /tools/{tool_id}/run`, bypassing the G4 meta-ops) directly, rather
  than going through `/tools` (search) → `/tools/resolve/{capability}` → run? If yes, that access
  pattern has no 1:1 replacement in this plan (MCP `execute_tool` is the only path) and needs a
  decision before Batch C removes the facade.
- **OQ-5:** `EXPOSE 8080 8090` in the current Dockerfile includes an already-unused `8080` — is
  that intentional (reserved for something) or just stale? Affects whether §3.2's `EXPOSE` edit
  should drop it too or leave it as future-reserved.
- **OQ-6:** Should `server/evidence/tool_finder/` (the G4 meta-op layer + `content_store.py` +
  `api.py`) move to `server/tools/tool_finder/` for consistency with D-026's rationale ("the tools
  registry is cross-domain, evidence/analysis/agents/workflows/CLI all consume it," `registry.py:
  118-120`)? The meta-ops are equally cross-domain (this plan wires them into `agents/`, not just
  `evidence/`) but weren't included in the original D-026 move. Not required for this plan to
  ship — the new `gateway_tools.py` module just imports across the package boundary — but flagging
  since it's the kind of thing that gets more expensive to fix the longer it's deferred.
- **OQ-7:** Confirm `ContentStore`'s backing store is safe as a per-process singleton in
  `agentos-mcp` today (single uvicorn worker, no `--workers` flag, `compose.exec.yaml:114`) and
  flag it if `agentos-mcp` is ever scaled to multiple workers/replicas (REFs created by
  `execute_tool` on worker A would 404 via `get_ref` on worker B unless the store has a shared
  backend).
- **OQ-8:** Error-signaling convention for the new `sbv_tools.py` — this plan proposes
  `{"error": ..., "status": ...}` dict returns (since agno tools aren't HTTP handlers, unlike the
  facade's `HTTPException` mapping), but `apply_db_modification` uses prefixed strings
  (`"ERROR: ..."`, `factory.py:104`). Pick one convention and apply consistently across
  `gateway_tools.py`/`sbv_tools.py` — this plan doesn't have visibility into every other agno tool
  in the codebase to know which convention is actually dominant; check before implementing.
- **OQ-9:** Worth dropping supervisord from `platform-tools` entirely once it's SBV-only (§3.1)?
  Recommend deferring — smaller win, separate blast radius (log capture, health checks), shouldn't
  block this cutover.

### Owner resolutions (2026-07-09)
- **OQ-1 + OQ-2 RESOLVED → tailnet-direct.** ContextForge registers `agentos-mcp` at the tailnet
  address `100.72.169.40:8001` with `transport: STREAMABLEHTTP`, mirroring the `coolify-mcp`
  precedent. NOT the public `agentos.mitechconsult.com/mcp` route (no shared-password/basic-auth
  layer needed). Tailscale latency is a non-issue for CF→mcp.
- **OQ-4 RESOLVED → no live consumers.** Owner: nothing is currently using any of the tools (facade
  or otherwise). So Batch C (facade removal) has NO coverage-gap risk from live traffic — we still
  verify agentos-mcp serves the parser tools on `tools/list` before removing the facade, but there
  is no consumer to break. The whole collapse is low-risk.
- OQ-3/5/6/7/8/9 remain as noted (non-blocking or handled in-batch).

---

## 8. File-change summary (for the eventual PR)

| File | Change | Batch |
|---|---|---|
| `server/agents/tools/gateway_tools.py` | new | A |
| `server/agents/tools/sbv_tools.py` | new | A |
| `server/agents/providers.py` | 2-line import + 1-line append at `:169` | A |
| `compose.exec.yaml` | add `SBV_*` env to `agentos-api` (`:49-82`) + `agentos-mcp` (`:123-158`) | A |
| `compose.yaml` | mirror the same `SBV_*` env additions | A |
| `tests/agents/test_gateway_tools.py` | new | A |
| `tests/agents/test_sbv_tools.py` | new | A |
| `scripts/register_agentos_mcp_contextforge.sh` | new (retires `register_sbv_contextforge.sh`) | B |
| `docker/tools/supervisord.conf` | remove `[program:tools-facade]` | C |
| `docker/tools/Dockerfile` | remove facade COPY/pip-install layers, fix `EXPOSE`, drop stale comment | C |
| `compose.exec.yaml` | remove `:8090` publish on `platform-tools` (`:216`), drop stale comment (`:220-223`) | C |
| `compose.yaml` | remove `:8090` publish on `platform-tools` (`:94`) | C |
| `docker/tools/tools/facade.py` | delete (or move to `_stale/` per repo convention — never delete outright per root `CLAUDE.md`) | C |
| `docker/tools/tools/` (whole dir, if only `facade.py` lives there) | delete/move to `_stale/` | C |

Note on the delete: the workspace-root `CLAUDE.md` rule is "Never delete files; move to
`_stale/`." — the Dockerfile edit in §3.2 just stops COPYing `docker/tools/tools/` into the image;
the source file itself should be moved to `_stale/`, not `git rm`'d, when this batch lands.
