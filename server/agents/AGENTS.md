# server/agents/ — agent/team constructors

> Nested map. Parent: `../AGENTS.md`. Root: `../../AGENTS.md`.

## What's here

The outermost domain layer — builds every Agno `Agent`/`Team` and wires the
runtime context they share. Imports `evidence/`, `tools/`, `analysis/`, `core/`
(never the reverse — see the dependency direction in `../AGENTS.md`).

| File | Role |
|---|---|
| `factory.py` | Every `Agent`/`Team` built by a `build_<name>()` function; `build_agent_team(ctx)` assembles the full topology (see root `AGENTS.md` for the diagram) and returns a dict keyed by stable public name — UI/tests depend on these keys. |
| `providers.py` | Builds `PlatformContext` (context providers, `LearningMachine`, MCP wiring). `source_tools` is the single append point for new agno `@tool` lists (Graphiti, `gateway_tools`, `sbv_tools` all append here). |
| `instructions.py` | Authoritative role/guardrail text for every agent — change the docstring first, then the instruction strings. `GLOBAL_GUARDRAILS` prepends to every agent. |
| `*_orchestrator.py`, `dev_copilot.py`, `project_pal.py`, `forensic_data_agent.py`, `review_gatekeeper.py`, `document_digest.py`, `transcript_miner.py` | Individual agent/team builders — see the topology diagram in the root map. |
| `claude_code_agent.py` | `build_claude_code_agent()` — Claude Code (`agno.agents.claude.ClaudeAgent`) wrapped for AgentOS. **Staged, NOT mounted** into `build_agent_team()` / the Root Router — needs the `claude-code` extra installed and an explicit owner decision on where it sits in the topology (see the module docstring, 2026-08-01). |
| `tools/gateway_tools.py` | agno `@tool` wrappers over the G4 gateway (`server/tools/gateway/toolfinder.py`) — 5 thin functions instead of one per parser. |
| `tools/sbv_tools.py` | agno `@tool` wrappers over `SBVClient` (`server/tools/_sbv_client.py`) — mirrors the old facade's `/sbv/*` proxy surface + `sbv_hashes` (H1/H3 custody chain). |

## Conventions

- `agents/tools/` (this package) is distinct from `server/tools/` (the atomic parser
  registry) and `server/tools/gateway/` (the G4 meta-ops themselves) — this package
  holds only the thin agno-facing `@tool` adapters, kept next to `providers.py` which
  wires them into `source_tools`.
- Error convention (OQ-8, `docs/COORDINATION.md`): `@tool` wrappers do NOT catch and
  reshape exceptions into `{"error": ...}` dicts — they let `KeyError`/`ValueError`/
  `SBVError` propagate. agno's `Function.execute()` already catches and reports a
  structured `status="failure"` result; re-catching here would throw that signal away.

## Relevant ADRs / docs

- ADR-0006 — two-layer team topology (root Router over coordinate families)
- ADR-0033 — `server/` repack (this package's current home, was top-level `agents/`)
- `docs/planning/facade-collapse-plan.md` — why `gateway_tools`/`sbv_tools` exist as
  agno `@tool`s alongside (not instead of) the `docker/tools` facade (superseded banner
  explains the corrected architecture — read it before touching this area)

---

<!-- live-testing-policy:start -->
## Testing & Deployment Policy — LIVE ONLY, SPRINT MODE

> _Owner directive 2026-08-20 · recorded by Claude Code · Opus 5._
> _Supersedes any prior testing, staging, or change-approval guidance in this file._

- **Sprint mode is the default.** Bias to action. Ship the smallest working increment now,
  verify it live, keep moving. Do not stall on approval gates for routine work.
- **All testing is live testing.** Verify against the real deployed service, real data, real
  endpoints. A proxy signal is not verification.
- **No out-of-band testing.** No mocks, stubs, or synthetic fixtures standing in for a real
  dependency. A green unit test is not evidence the thing works.
- **No stubs. Write the whole function.** If it is a function, implement it fully. A stub is
  permitted ONLY when the real data or upstream service genuinely does not exist yet.
- **Any stub that must exist is marked LOUDLY and tracked.** Inline `# STUB:` / `// STUB:` at the
  site, plus an entry in `docs/URGENT-TODO.md`. A silent stub is a defect.
- **Ship and watch.** If it works, it stays up. If it breaks, fix it and put it back up.
  Breakage is the feedback loop, not a reason to stage.
- **On success, purge the test data.** Clear every row and artifact the live run created, then
  move on. Test data must never become canonical.
- **On failure, adjust in place and retry live.** Fix the real thing and run it again — never
  retreat to a mock, a staging copy, or a parallel instance to "prove" it.
- **No parallel stacks.** One live instance per service. No shadow deploys, no staging copies,
  no side-by-side `v2` beside `v1` — replace in place.
- **Fix forward.** Roll back only to restore service, never as a substitute for fixing the cause.
- **Mid-task feedback is QUEUED, not switched to.** If input arrives that is not about the task in
  flight, append it to `docs/URGENT-TODO.md` and keep going. Finish the current task; address the
  queued item at the point that work was already scheduled. Do not context-switch mid-task.

**Still stop and ask for:** destroying data, terminating/wiping a host, anything outward-facing
(publishing, sending, paying), and irreversible spend. Sprint mode removes ceremony, not judgment.
<!-- live-testing-policy:end -->
