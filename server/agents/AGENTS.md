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
