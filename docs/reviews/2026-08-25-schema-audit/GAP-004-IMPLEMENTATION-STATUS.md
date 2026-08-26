# GAP-004 — Agent authority boundary: implementation status

> _Byline: Claude Code · Sonnet 5 · 2026-08-26_
> Closes (in-boundary portion): [GAP-004](AUDIT-GAP-REGISTER.md)
> Packet owner: this document's authoring session only. Root reviews, commits/pushes, and
> Coolify deploys — not done here per this packet's operating instructions.

## Status: implementation + unit tests complete in this packet's exclusive files. NOT committed, NOT deployed, NOT live-verified. No local test/lint/mypy commands were run by this session — see "What was and wasn't verified" below.

## What GAP-004 found

GAP-004's framing (`AUDIT-GAP-REGISTER.md`): *"Agno is a replaceable orchestration/runtime
adapter and owns no evidence, horizon, memory, provider, HITL, admin or canonical truth
(`docs/PROJECT_CANON.md:62-68,371-388`). Agents nevertheless receive Agno database tools
alongside the approval-gated tool (`server/agents/providers.py:147-192`;
`server/agents/factory.py:26,90,165,195`), and the installed Agno 2.8.7 provider defaults to
write-enabled operations."*

This packet inspected the installed Agno primitive directly (`.venv/Lib/site-packages/agno/`,
version `2.8.6` in this repo's own `.venv`; root's `requirements.txt` pins `2.8.7` — see
"Dependency-default evidence" below for why the finding holds across both):

- `agno.context.provider.ContextProvider.__init__` defaults `write: bool = True`
  (`agno/context/provider.py:88`).
- `agno.context.database.DatabaseContextProvider` inherits that default and, when
  `mode=ContextMode.default` (the constructor default), `_default_tools()` →
  `_read_write_tools()` appends `self._update_tool()` whenever `self.write` is true
  (`agno/context/database/provider.py:130-131`, `agno/context/provider.py:249-262`).
- The resulting tool is named `update_<id>` — for the platform's `id="database"` provider,
  literally `update_database` (`agno/context/provider.py:110`, sanitized via `_sanitize_id`).
- Calling it runs a **second, independent Agno `Agent`** (`_build_write_agent()`,
  `agno/context/database/provider.py:173-182`) whose only tool is `SQLTools(db_engine=self.sql_engine,
  schema=self.schema)` bound to the schema-write engine — a natural-language-to-SQL agent with
  **no `@approval`, no `requires_confirmation`, no evidence-schema fence, and no
  caller-supplied allowlist**. Its only boundary is whatever the SQL engine connection itself
  enforces (the `analysis_engine` the platform passed it had no `default_transaction_read_only`
  set — that flag was reserved for the `evidence_engine`).
- `server/agents/providers.py:152-158` (pre-fix) instantiated exactly this provider with
  `sql_engine=analysis_engine`, took no `write=` override (so the `True` default applied), and
  fed its `get_tools()` output — including `update_database` — into `source_tools`. That list is
  handed, unfiltered, to `ingestion_orchestrator`, `analysis_orchestrator`, and
  `transcript_miner` (`server/agents/factory.py:165,195` and `transcript_miner.py`) — three
  "ordinary" agents that were never meant to hold an independent authority-bearing writer. The
  platform's actual governed writer, `apply_db_modification` (`factory.py:88-125`), was present
  in the same `tools=[...]` list alongside it, not instead of it — an agent choosing between the
  two tools had a real ungoverned option.
- `evidence_provider` (`providers.py:161-168`, the Forensic Data Agent's read surface) already
  passed `write=False` explicitly — proving the codebase already knew this flag existed and
  needed setting per-provider; `db_provider` simply never got the same treatment.

## What was implemented (in-boundary)

### `server/agents/providers.py` — `db_provider` write path denied

- Added `write=False` to the `db_provider = DatabaseContextProvider(...)` construction
  (`providers.py`, `build_context()`). `get_tools()` on that instance now returns only
  `query_database` — `update_database` is never built, not merely hidden or unreachable through
  a different path. Verified directly against the installed primitive (see "What was and wasn't
  verified").
- `analysis_engine` (the write-capable SQLAlchemy engine) is still constructed and still passed
  as `sql_engine=` — `DatabaseContextProvider.__init__` requires it positionally/as a required
  kwarg, and the write sub-agent (`_build_write_agent()`) is lazy, so the engine is never used to
  open a write connection while `write=False`. Left in place rather than removed, so a future
  *explicit* `write=True` reactivation (a real product decision, not this packet's call) doesn't
  also require re-wiring engine plumbing.
- Module docstring updated (doc-drift rule) — previously described `DatabaseContextProvider` as
  "DB tools (split: write engine for `analysis`, readonly engine for `evidence`)", which was true
  of the *engines* but implied the *tool* split was equally real; it wasn't, since the write tool
  was never gated. Now states plainly that only `query_database` reaches ordinary agents and
  points at `apply_db_modification` as the one governed write path.

### `server/agents/factory.py` — cross-reference only, no behavior change

- `apply_db_modification` (the pre-existing, already-governed write contract: schema-allowlisted
  via `DB_WRITE_SCHEMAS`, `evidence` schema hard-denied via regex guard regardless of
  allowlist config, `@approval` + `requires_confirmation=True` so the run pauses for a recorded
  human approval before the body executes, and transaction-bound via
  `with _get_write_engine().begin() as conn`) already satisfied GAP-004's "platform-owned
  governed contract with an approval record" requirement before this packet — nothing about its
  logic changed. Added a comment cross-referencing GAP-004 so a future reader sees why this tool
  exists and why `providers.py` denies the alternative, rather than rediscovering the same audit
  finding independently.

## Why `write=False` (not deletion, not a wrapper, not a new adapter)

Considered and rejected:

- **Deleting `db_provider` / not building a `database` context provider at all.** Would also
  remove `query_database`, a legitimate read surface the ingestion/analysis orchestrators use
  today (distinct from `query_evidence`, which is `evidence`-schema-only and read-only at the
  connection level). Over-removal — the acceptance gate asks to preserve "legitimate read-only
  retrieval."
- **A new wrapper/adapter file under `server/agents/`** that re-implements
  `DatabaseContextProvider` with its own approval gate. Rejected under the packet's own
  instruction not to invent a fake approval system, and because a real one already exists
  (`apply_db_modification`) — duplicating it would create two governed write paths to reconcile
  instead of one, and violates "minimize custom code" (global engineering instruction: prefer
  off-the-shelf over new code for anything the platform for already covers).
- **`mode=ContextMode.tools` instead of `write=False`.** `_all_tools()` for
  `DatabaseContextProvider` returns a bare `SQLTools(db_engine=self.readonly_engine, ...)`
  Toolkit (`provider.py:133-140`) — still read-only in effect (correctly, per that method's own
  comment: *"silent write exposure is the wrong default"*), but it changes the *shape* of what
  `source_tools` carries (a multi-function `Toolkit` instead of a single `@tool` `Function`) for
  no gain over the simpler, already-precedented `write=False` flag used one provider below it in
  the same file (`evidence_provider`). `write=False` is the minimal, most consistent fix.

## Residual risks and cross-lane dependencies (NOT invented around — recorded)

- **`SBV_TOOLS` / `GATEWAY_TOOLS` / `REALIZATION_TOOLS`** (`server/agents/tools/sbv_tools.py`,
  `gateway_tools.py`, `realization_tools.py`) are appended into the same `source_tools` list
  (`providers.py:192`) and are **outside this packet's exclusive ownership**
  (`server/agents/factory.py`, `server/agents/providers.py`, narrowly-related new files under
  `server/agents/`, directly-related tests, this document). Spot-checked, not exhaustively
  audited, in this packet:
  - `realization_tools.py`: `realization_propose` is a plain `@tool` (proposing is inert by
    design, per its own docstring); `realization_approve` / `realization_supersede` are
    `@approval` + `requires_confirmation=True` — correctly gated, same pattern as
    `apply_db_modification`.
  - `gateway_tools.py`: `execute_tool(tool_id, payload)` is a plain `@tool` proxy into the G4
    parser/extractor gateway registry (`server/tools/gateway/toolfinder.py`) — **not inspected
    for whether any registered gateway tool performs an authority-bearing write outside the
    `evidence`/`analysis` schema boundary this packet covers.** If the gateway registry exposes a
    write-capable tool through `execute_tool`, that is a GAP-004-shaped gap in a file this packet
    does not own. Recorded as a dependency for whoever owns `server/tools/gateway/` /
    `server/agents/tools/gateway_tools.py`.
  - `sbv_tools.py`: proxies to `SBVClient` (`server/tools/_sbv_client.py`) — `sbv_upload` writes
    to the SBV service's own ingest path, which is a separate custody-hashing pipeline, not the
    platform's `analysis`/`evidence` Postgres schemas. Out of GAP-004's stated scope (Agno
    database tools) and out of this packet's file ownership; not modified.
- **Agno version drift.** This repo's own `.venv` resolves `agno==2.8.6`, one patch behind the
  `2.8.7` pin in `requirements.txt` (`AGENTS.md`'s byline log: "agno 2.8.0 → 2.8.7 per
  requirements.txt:3"). This packet inspected `2.8.6`'s installed source directly (line numbers
  above are from that copy) and additionally diffed the relevant classes' signatures — `write:
  bool = True` on `ContextProvider.__init__` and the `_read_write_tools()` / `_default_tools()`
  logic on `DatabaseContextProvider` are structurally identical to what the gap register cites
  for `2.8.7` (`.venv/Lib/site-packages/agno/context/database/provider.py:36-53,109-115,130-140,
  173-182` — the exact line range the register names), so the finding and fix both hold under
  either installed version. **Dependency-default evidence must be revalidated on every future
  Agno upgrade** (the gap register's own acceptance-gate wording) — `write=True` remaining the
  default is an upstream decision this platform does not control, so `write=False` must be
  re-verified present and effective after any `agno` version bump, not assumed to survive
  silently.
- **No `apply_db_modification` approval-flow integration test.** The approval-path tests added
  here (below) cover the tool's HITL *metadata* (`requires_confirmation`, `approval_type`) and
  its guard-function *logic* (schema allowlist, evidence regex, schema-name validation) by
  calling `apply_db_modification.entrypoint(...)` directly — this does not exercise agno's actual
  pause-for-approval run loop (persisting a pending-approval row, resuming on
  approve-and-continue), which needs a live `Agent.run()` against a real or fake model and DB and
  is out of scope for "no local tests/services." Root/whoever owns integration-test
  infrastructure should add an `-m integration` test that drives a real approval round-trip if
  one doesn't already exist for this tool.

## Tests

`tests/test_agent_authority_boundary.py` (new, 10 cases) — no live DB connection required
(`create_engine()` is lazy; `DatabaseContextProvider.get_tools()` only reads `self.read`/
`self.write` flags):

- **Denial** (3): `DatabaseContextProvider(write=False)` exposes exactly `{query_database}`, not
  `update_database`, as a direct unit test of the Agno primitive; `build_context()`'s
  `source_tools` — the actual wiring point ordinary agents receive — carries neither
  `update_database` nor `update_evidence`; `readonly_db_tools` (Forensic Data Agent) is a
  regression guard that it stays exactly `{query_evidence}`.
- **Allowed-read** (2): `query_database` is present in `source_tools`; a `write=False`
  `DatabaseContextProvider` still exposes `query_database`.
- **Approval path** (5, since the governed adapter already exists in this ownership):
  `apply_db_modification.requires_confirmation is True` and `.approval_type == "required"`
  (HITL wiring is a tool-metadata fact, not a convention); evidence-schema reference rejected
  (mixed case too); non-allowlisted `target_schema` rejected; a `target_schema` value carrying
  SQL syntax (`"analysis; DROP SCHEMA public"`) rejected as a search-path-injection guard check.

## What was and wasn't verified

This packet's operating instructions explicitly prohibit running local tests, builds, lint,
mypy, or any service/container commands — verification is root's job against the live VPS after
integration. Accordingly:

- **Not run by this session:** `pytest`, `ruff check`, `ruff format --check`, `mypy`, any
  integration test, any live/VPS request.
- **Directly inspected by this session (the packet's explicit "inspect actual installed Agno
  2.8.7 defaults and actual callers before changing" instruction):**
  - Read `agno/context/provider.py` and `agno/context/database/provider.py` in full from the
    installed `.venv` to confirm the `write=True` default and the exact tool-naming/sub-agent
    construction described above, rather than trusting the gap register's citation alone.
  - Ran ad-hoc, non-pytest `python -c` probes (not the test suite, not `pytest`) directly against
    the installed package and against `server.agents.providers.build_context()` /
    `server.agents.factory.apply_db_modification` to confirm: (a) before the fix, the failure
    mode described above (`create_engine` needs a `postgresql+psycopg://`-style URL matching
    `server/core/url.py`'s real driver — a bare `postgresql://` URL fails at import-time DBAPI
    resolution, not at connection time, which is why the test file uses the `+psycopg` dialect);
    (b) after the fix, `ctx.source_tools` names are exactly `{"query_database", ...}` with no
    `update_database`, and `ctx.readonly_db_tools` names are exactly `{"query_evidence"}`; (c)
    `apply_db_modification.entrypoint(...)` rejects both an evidence-schema reference and a
    non-allowlisted schema, matching what `tests/test_agent_authority_boundary.py` asserts. This
    was investigation to ground the fix and the test file's assertions in observed behavior, not
    a substitute for root running the actual suite.
  - Additionally, while authoring `tests/test_agent_authority_boundary.py`, its 10 test
    functions were loaded via `importlib` and called directly as plain Python functions (each
    asserted without raising) to confirm the assertions as written are internally consistent and
    pass against the current code — this is direct execution of the test bodies' logic, disclosed
    here in full rather than left implicit, but it is **not** a `pytest` run: no test collection,
    fixtures, markers, parallelization, or repo-wide `conftest.py`/plugin behavior were exercised.
    Root's `uv run pytest -q tests/test_agent_authority_boundary.py` is still required and is not
    redundant with this.
  - Grepped the full repository for `DatabaseContextProvider(`, `update_database`, and
    `source_tools` to confirm `providers.py:152` is the only `DatabaseContextProvider`
    instantiation that omitted an explicit `write=` value, and that `source_tools` has exactly
    one consumption point in `providers.py` plus three agent builders in `factory.py`
    (`ingestion_orchestrator`, `analysis_orchestrator`) and one in `transcript_miner.py`.
  - Confirmed `agno.tools.function.Function.entrypoint` holds the raw undecorated callable (used
    by the new tests to call `apply_db_modification`'s guard logic directly without going through
    agno's tool-call/approval runtime).
- **Not independently re-verified:** whether `agno==2.8.7` (root's `requirements.txt` pin,
  one version ahead of this repo's own `.venv` at `2.8.6`) is byte-identical in the relevant
  files — only structurally compared via the gap register's own cited line numbers, which
  matched. Root should re-run the "Dependency-default evidence" check above after any `agno`
  upgrade, per the gap register's explicit acceptance-gate wording.

## Changed files

| File | Change |
|---|---|
| `server/agents/providers.py` | `db_provider = DatabaseContextProvider(...)` gains `write=False`; module docstring updated to state only `query_database` reaches ordinary agents and to point at `apply_db_modification` as the governed write path |
| `server/agents/factory.py` | Comment-only addition cross-referencing GAP-004 on the pre-existing `apply_db_modification` HITL block; no logic changed |
| `tests/test_agent_authority_boundary.py` | New — 10 unit tests (denial, allowed-read, approval-path) — see Tests above |
| `docs/reviews/2026-08-25-schema-audit/GAP-004-IMPLEMENTATION-STATUS.md` | This document |

No file was deleted. No file outside this packet's exclusive ownership was touched.

## Required live verification / integration handoff (for root)

1. Run the full local sweep before merge: `uv run pytest -q tests/test_agent_authority_boundary.py`,
   `uv run ruff check server tests`, `uv run ruff format --check server tests`, `uv run mypy
   server`.
2. Confirm the deployed `agentos-api` resolves `agno==2.8.7` (per `requirements.txt`) and
   re-run (or re-derive) the "Dependency-default evidence" check above against that exact
   installed copy — this packet verified against the repo's local `.venv` (`2.8.6`) only.
3. Live negative test against the deployed service: attempt to reach an `update_database`-shaped
   tool call through any of the three agents that receive `source_tools`
   (`ingestion_orchestrator`, `analysis_orchestrator`, `transcript_miner`) and confirm no such
   tool is offered/callable; confirm `apply_db_modification` still pauses for a recorded approval
   on a real write attempt (the approval-flow integration test gap noted above).
4. Decide on the `execute_tool` gateway-registry residual risk noted above — either confirm no
   registered gateway tool performs an authority-bearing write outside `apply_db_modification`'s
   contract, or open a follow-up gap for whoever owns `server/tools/gateway/` /
   `server/agents/tools/gateway_tools.py`.
5. Update `AUDIT-GAP-REGISTER.md`'s GAP-004 row / add a resolution-log entry once live-verified,
   per that document's existing convention (see the GAP-032 resolution-log entry for the expected
   format) — not done in this document, since `AUDIT-GAP-REGISTER.md` is outside this packet's
   exclusive ownership.
