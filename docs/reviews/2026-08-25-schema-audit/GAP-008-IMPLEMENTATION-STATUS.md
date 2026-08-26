# GAP-008 — Retired-Graphiti zero-caller path: implementation status

> _Byline: Claude Code · Sonnet 5 · 2026-08-26_
> Closes (in-boundary portion): [GAP-008](AUDIT-GAP-REGISTER.md) / packet P-09
> ([PARALLEL-GAP-EXECUTION-BOARD.md](PARALLEL-GAP-EXECUTION-BOARD.md))
> Packet owner: this document's authoring session only, strictly limited to
> `server/analysis/context_chat_ingest.py`, `server/agents/providers.py`,
> `deploy/data-graphiti.yaml` (narrow port-deny edit only), new dedicated tests,
> and this status document. No other file was touched. Root reviews, commits/pushes,
> and Coolify deploys/restarts are explicitly out of scope for this session.

## Status: code-level implementation + targeted tests complete and locally verified in this packet's exclusive files. NOT committed, NOT pushed, NOT deployed, NOT live-restarted, NOT live-verified against the running Coolify apps. The deploy-manifest edit has no live effect until an actual redeploy (deferred — see "Remaining live handoff").

## Settled authority this packet recovered and obeyed

- **D-070** (`docs/DECISION_LOG.md`, owner-ruled 2026-08-25 03:12): *"Graphiti is retired for
  now."* Memory/graph lane = SurrealDB (ADR-0056) + n8n as the agent layer + Temporal as the
  durable spine (D-068); the graph engine is an OPEN choice between Cognee and Memgraph.
  ADR-0014/0031/0037/0038/0039 (Graphiti) are suspended, not deleted. **No replacement graph
  store is authorized by this packet** — none was created.
- **GAP-008** (`AUDIT-GAP-REGISTER.md:18`): *"Retired Graphiti remains writable and directly
  tailnet-exposed; the tracked manifest alone does not establish public-internet exposure
  (`server/agents/providers.py:194-212`; `server/analysis/context_chat_ingest.py:320-357,532-562`;
  `deploy/data-graphiti.yaml:90-118`). Live exec still sets `GRAPHITI_MCP_URL` (read-only Coolify
  probe, 2026-08-26)."* Acceptance gate: *"Approved retirement/cutover removes Graphiti MCP from
  the agent roster and its sink/outbox producer, unsets the live URL, and proves zero
  callers/pending jobs through a controlled restart; the direct port is denied or the application
  is retired."*
- **P-09 execution-board row** (`PARALLEL-GAP-EXECUTION-BOARD.md:49`): scope = "Graphiti
  caller/sink retirement in context ingestion, agent roster cleanup, Graphiti deploy manifest and
  zero-caller proof"; after P-08 (GAP-004, already landed — `providers.py` was locked against this
  packet until that packet's `write=False` change merged, which it has, commit `a358fd2`).
- Nested `server/agents/AGENTS.md`: confirms `providers.py` is *"the single append point for new
  agno `@tool` lists (Graphiti, `gateway_tools`, `sbv_tools` all append here)"* — the correct,
  sole file for the agent-roster half of this fix.

No new ledger, no replacement store, and no file deletion were introduced anywhere in this change.

## What GAP-008 found (three separate mechanisms, all in the two owned source files)

1. **Agent roster** — `server/agents/providers.py` conditionally appended an `agno.tools.mcp.MCPTools`
   entry (prefixed `"graphiti"`) to every ordinary agent's `source_tools` whenever the
   `GRAPHITI_MCP_URL` environment variable was non-empty. Because `source_tools` is handed
   unfiltered to `ingestion_orchestrator`, `analysis_orchestrator`, and `transcript_miner`
   (`factory.py`), any of those three agents could call Graphiti write tools through the MCP
   bridge whenever the deployed container had that variable set — which the register's live
   Coolify probe (2026-08-26) confirmed it still did.
2. **Outbox producer** — `server/analysis/context_chat_ingest.py::_store_classifications` wrote a
   `working.chat_chunk_projection` row for **both** `sink IN ('weaviate', 'graphiti')` for every
   projection-eligible chat chunk, unconditionally. Every ingest run kept creating new pending
   Graphiti jobs regardless of whether anything ever drained them.
3. **Outbox consumer** — `_project_graphiti()` in the same file imported
   `server.analysis.graphiti_case_client.GraphitiCaseClient` and called `client.add_memory(...)`
   for every pending item, and `ingest_chat_file(..., project=True)` invoked
   `sync_pending_context("graphiti")` directly (in addition to `"weaviate"`) on every projecting
   ingest run — a second, code-path-independent live caller from the one already unset by removing
   the producer.

A fourth, deployment-topology mechanism sits in the one deploy manifest this packet is authorized
to touch: `deploy/data-graphiti.yaml`'s `graphiti-hostfix` nginx sidecar published
`${BIND_IP}:8071:8071` — a direct tailnet host-port bind in front of `graphiti-mcp`, independent of
whether any application code called it.

## What was implemented (in-boundary)

### `server/agents/providers.py` — Graphiti MCP attachment removed unconditionally

- Deleted the `if graphiti_url:` block that built `agno.tools.mcp.MCPTools(url=graphiti_url, ...,
  tool_name_prefix="graphiti", ...)` and appended it to `source_tools`.
- Deleted the now-unused `graphiti_url = os.getenv("GRAPHITI_MCP_URL", "")` line and the
  now-unused `import os` (the only remaining `os.*` use in the module was this one line — `ruff`
  confirms no other reference).
- The removal is **unconditional**: `build_context()` no longer reads `GRAPHITI_MCP_URL` at all,
  so zero-caller holds even if a deploy manifest (`deploy/contextforge.yaml`,
  `deploy/workbench.yaml` — both outside this packet's ownership, both still export the variable
  for other consumers) or the live `agentos-api` container still has that variable set. This is
  deliberately more robust than "unset the live URL" alone, which the register's acceptance gate
  also lists as a required live action (see "Remaining live handoff").
- Module docstring and byline updated (doc-drift rule): the former "MCP servers (Graphiti, future
  tools) are wired here" line now states plainly that no MCP server is attached today and points at
  D-070/GAP-008, with the historical text struck through rather than silently deleted.
- `ADR-0014/0031/0037/0038/0039` are referenced as suspended-not-deleted, matching D-070's own
  language — this packet did not touch those ADR files (out of ownership) or mark them superseded;
  that remains a documentation-lifecycle decision for whoever owns `docs/adr/`.

### `server/analysis/context_chat_ingest.py` — sink/outbox producer and consumer retired

- **Producer** (`_store_classifications`): the sink loop `for sink in ("weaviate", "graphiti"):`
  became `for sink in ("weaviate",):`. No new `sink='graphiti'` row can be inserted into
  `working.chat_chunk_projection` from this code path going forward. Pre-existing rows (if any
  exist in the live database from before this change) are left untouched — this packet performs no
  DDL, no DELETE, and creates no new ledger to track them; see "Remaining live handoff" for the
  disposition question.
- **Consumer** (`_project_graphiti`): rewritten to a permanent no-op. It no longer imports
  `server.analysis.graphiti_case_client.GraphitiCaseClient` and never constructs or calls it; it
  returns `(0, 0)` unconditionally instead of driving a live MCP call. The
  `graphiti_case_client.py` module itself is untouched and un-deleted (out of ownership; now has
  zero callers anywhere in `server/`, confirmed by repo-wide grep — see "Verification" below).
- **`sync_pending_context`**: unchanged dispatch shape (`sink == "graphiti"` still routes to
  `_project_graphiti`), but that routing now always resolves to the no-op. This keeps the function
  signature and behavior contract stable for the one caller this packet does **not** own —
  `server/tools/ingest/context_drain.py` (a registered agent/CLI/MCP tool, `_SINKS = ("weaviate",
  "graphiti")`, default `sink="both"`) — so that unowned file's existing "both" default keeps
  working exactly as before, just with the `"graphiti"` half now reporting a truthful zero instead
  of performing a live call. This was a deliberate compatibility choice over the alternative of
  making `sync_pending_context("graphiti")` raise, which would have broken that unowned caller's
  default behavior — see "Scope discipline" below.
- **`ingest_chat_file`**: removed the `graphiti_objects, graphiti_chunks =
  await sync_pending_context("graphiti")` call entirely (the second, independent live-caller
  mechanism). `IngestReport.graphiti_chunks` / `.graphiti_records_synced` remain on the dataclass
  (unchanged shape, no downstream reader depends on a nonzero value — confirmed by repo-wide grep)
  but are now always `0`, sourced from a local constant rather than a real sync call.
- Module byline updated.

### `deploy/data-graphiti.yaml` — direct tailnet port publish denied, nothing deleted

- Removed the `ports: - "${BIND_IP:-127.0.0.1}:8071:8071"` mapping from the `graphiti-hostfix`
  service. The service definition, the `graphiti-mcp` service, and the `graphiti-portkeyfix`
  sidecar are all still present and unchanged otherwise — no service was deleted or stopped, per
  this packet's "prefer narrow, don't move files, never delete" constraint and the register's own
  "the direct port is denied **or** the application is retired" acceptance wording (denial chosen
  over retirement, since retirement requires a live Coolify app-stop this packet cannot perform).
- Added an inline comment (dated, attributed) documenting the removal and pointing at this status
  document, per the doc-drift/strike-through convention rather than silently deleting the old line.
- This edit is a file change only. It has **no live effect** until the `data-graphiti` Coolify app
  is redeployed from this commit — deploying is explicitly forbidden for this session (see
  "Remaining live handoff").
- `deploy/data-graphiti-case.yaml` (a second Graphiti-adjacent manifest) was inspected but **not**
  touched — it is outside this packet's exclusive ownership (only `data-graphiti.yaml` was
  authorized).

## Scope discipline — files inspected but deliberately not touched

- `server/tools/ingest/context_drain.py` — the one real unowned caller of `sync_pending_context`
  with a `"graphiti"`/`"both"` sink option (a registered `ingest.context-drain` tool, reachable by
  agent/CLI/MCP). Not edited. Its behavior is now safe by construction because the function it
  calls into resolves to a no-op — verified live in this packet by unit test (see below), not by
  editing its file.
- `server/analysis/graphiti_case_client.py` — the Graphiti MCP client class itself. Not edited, not
  moved, not deleted. Confirmed zero remaining callers anywhere under `server/` after this change.
- `docs/adr/0014-*`, `0031-*`, `0037-*`, `0038-*`, `0039-*` (Graphiti ADRs) — not edited; D-070
  already states they are "suspended, not deleted" and this packet has no ADR-editing ownership.
- `deploy/contextforge.yaml`, `deploy/workbench.yaml` — both still export `GRAPHITI_MCP_URL` for
  other consumers (ContextForge gateway config, workbench env). Not edited; out of this packet's
  deploy-manifest ownership (only `data-graphiti.yaml` was authorized), and moot for the agent-roster
  half of the fix because `providers.py` no longer reads the variable at all.
- `AUDIT-GAP-REGISTER.md` — the GAP-008 row / resolution log is not updated in this document,
  matching the precedent set by the GAP-004 status document (same file, same reasoning: it is
  outside this packet's exclusive ownership). Root should add the resolution-log entry once this
  packet's live-verification items below are complete.
- `working.chat_chunk_projection` (live data) — no migration, DELETE, or cleanup script was
  written for any pre-existing `sink='graphiti'` rows. Owner ruling forbids treating ingested/test
  rows as untouchable, but this packet has no SQL-migration ownership here and no live DB
  connection was used at any point.

## Verification performed (local, no live services)

Exact commands run from the repository root, in this order:

```
uv run ruff check server/agents/providers.py server/analysis/context_chat_ingest.py tests/test_gap008_graphiti_retirement.py
uv run ruff format --check server/agents/providers.py server/analysis/context_chat_ingest.py tests/test_gap008_graphiti_retirement.py
uv run mypy server/agents/providers.py server/analysis/context_chat_ingest.py
uv run pytest -q tests/test_gap008_graphiti_retirement.py tests/test_agent_authority_boundary.py tests/test_context_chat_ingest.py tests/test_context_drain_tool.py
```

Outcomes:

- `ruff check`: **All checks passed!** (0 errors after removing one unused-`pytest`-import lint
  finding in the new test file during authoring).
- `ruff format --check`: **3 files already formatted.**
- `mypy` (both owned source files): **Success: no issues found in 2 source files.** (An unrelated
  pre-existing `pyproject.toml` note about unused per-module overrides for other packages printed
  and does not concern these files.)
- `pytest`: **34 passed, 1 warning in 14.24s.** The one warning is a pre-existing,
  unrelated `EXA_API_KEY not set` runtime warning from `server/tools/exa_search.py`'s import-time
  check, not a failure and not caused by this change.
- A broader, non-required sanity pass — `uv run pytest -q` (the repository's full default unit
  suite, all directories) — was also started from this session to look for any unexpected
  regression outside the targeted files; it exceeded this shell's interactive timeout and was still
  running in the background when this document was written. **Not included as a completion claim**
  — see "Remaining live handoff" below for how to re-run and read the result. The four targeted
  files above are the required-and-verified evidence for this packet's bounded scope.

### What the nine tests in the new file prove

`tests/test_gap008_graphiti_retirement.py` (all DB-free, no live services):

1. `build_context()` attaches no `MCPTools` instance and no tool with a `"graphiti"`
   `tool_name_prefix` to `source_tools` — asserted directly, not inferred.
2. `build_context()`'s `source_tools` roster is byte-for-byte the same length whether
   `GRAPHITI_MCP_URL` is unset or set to a live-shaped URL — proves the removal is unconditional,
   not merely re-gated.
3. `server.agents.providers` no longer has a module-level `os` name — regression guard that the
   only `os` use (the deleted `os.getenv("GRAPHITI_MCP_URL", ...)` line) is fully gone, not
   dead-code-shadowed.
4. `_store_classifications`, given one eligible classification, writes exactly one projection row
   and its `sink` is `"weaviate"` — `"graphiti"` never appears — using a capturing fake connection
   (no DB).
5. `_project_graphiti` returns `(0, 0)` and does not import `graphiti_case_client` even when that
   module is deliberately poisoned in `sys.modules` to raise if imported.
6. `sync_pending_context("graphiti")` against three fake "legacy pending" items still returns
   `(0, 0)` — proves old pending rows (if they exist live) cannot trigger a live call through this
   path either.
7. `sync_pending_context("graphiti", dry_run=True)` still reports an honest pending count without
   syncing — preserves the read-only "how many are stuck" diagnostic for whoever does the live
   pending-row audit.
8. `ingest_chat_file(..., project=True, dry_run=False, classify=False)` calls `sync_pending_context`
   exactly once, with `sink="weaviate"` only — `"graphiti"` is never requested.

## Remaining live handoff (root / owner action — not performed here)

1. **Unset `GRAPHITI_MCP_URL` on the live `agentos-api` app** (the register's live Coolify probe,
   2026-08-26, found it still set). This packet's code change makes that variable inert for the
   agent-roster path regardless, but the register's acceptance gate explicitly also asks to unset
   it — do this as defense in depth and to stop the exec-tier manifest from advertising a retired
   dependency.
2. **Redeploy `agentos-api`** from the commit containing this packet's `providers.py` /
   `context_chat_ingest.py` changes, then confirm via a live negative test: attempt to reach any
   `graphiti`-prefixed tool through `ingestion_orchestrator`, `analysis_orchestrator`, or
   `transcript_miner` and confirm none is offered — mirrors the GAP-004 live-verification pattern
   already used for this same file.
3. **Redeploy `data-graphiti`** from the commit containing this packet's `data-graphiti.yaml`
   change, then confirm port `8071` is no longer reachable at `${BIND_IP}` from another host on the
   tailnet (e.g. a probe from `agentos-api`'s or a workbench box's tailnet address should
   connection-refuse rather than reach `graphiti-hostfix`).
4. **Controlled-restart proof of zero pending jobs**, per the register's exact acceptance wording
   ("proves zero callers/pending jobs through a controlled restart"): after the above two
   redeploys, run a live query against `working.chat_chunk_projection WHERE sink = 'graphiti' AND
   projected_at IS NULL` to get the current pending count (any nonzero count is pre-existing legacy
   data this packet deliberately left untouched, not new since the producer is now weaviate-only),
   and confirm no process drains them going forward (this packet's `_project_graphiti` no-op
   guarantees that structurally, but a live restart-and-observe pass is still the register's
   required proof, not a code-level guarantee alone).
5. **Decide the disposition of any pre-existing `sink='graphiti'` rows** in
   `working.chat_chunk_projection` — leave them permanently pending (harmless, inert), or write a
   dedicated, separately-authorized migration/cleanup pass. This packet does not decide or implement
   that; no new ledger or migration was created here.
6. **Update `AUDIT-GAP-REGISTER.md`'s GAP-008 row / resolution log** once the above live items are
   complete, following the format already used for the GAP-032 resolution-log entry (per that
   document's own convention) — deferred to root since the register is outside this packet's
   exclusive ownership.
7. **Re-run the full local suite to completion** (`uv run pytest -q`, no path filter) and confirm no
   unrelated regression, since this session's attempt exceeded its interactive shell timeout and was
   left running in the background rather than awaited to completion.
8. Optionally, once live-verified, consider whether `docs/adr/0014-*` /
   `0031-*`/`0037-*`/`0038-*`/`0039-*` should gain an explicit "suspended by D-070 / GAP-008" banner
   — out of this packet's ownership, noted for whoever owns `docs/adr/`.

## Changed files

| File | Change |
|---|---|
| `server/agents/providers.py` | Removed the conditional Graphiti `MCPTools` attachment block and the now-unused `os` import; docstring/byline updated |
| `server/analysis/context_chat_ingest.py` | `_store_classifications` producer loop is `("weaviate",)` only; `_project_graphiti` is a permanent no-op (no `GraphitiCaseClient` import/call); `ingest_chat_file` no longer calls `sync_pending_context("graphiti")`; byline updated |
| `deploy/data-graphiti.yaml` | Removed `graphiti-hostfix`'s `${BIND_IP}:8071:8071` host-port publish (service definitions otherwise unchanged, nothing deleted); dated inline comment added |
| `tests/test_gap008_graphiti_retirement.py` | New — 8 unit tests (agent-roster non-attachment, producer sink restriction, consumer no-op, unowned-caller compatibility, `ingest_chat_file` call-site removal) |
| `docs/reviews/2026-08-25-schema-audit/GAP-008-IMPLEMENTATION-STATUS.md` | This document |

No file was deleted or moved. No file outside this packet's exclusive ownership was edited.
