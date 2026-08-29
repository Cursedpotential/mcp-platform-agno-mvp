# server/ — the backend boundary

> _Byline: Claude Code · 2026-07-27; navigation refresh by Codex · GPT-5.6-Sol · 2026-08-29._

> Nested map. Root map: `../AGENTS.md`. Closest file wins — if you're editing inside
> `contracts/`, `evidence/`, `timeline/`, `tools/`, or `agents/`, read THAT directory's `AGENTS.md` too.

## What's here

One backend boundary, domain-separated inside (ADR-0033 repacked every top-level
package — `agents/`, `app/`, `db/`, `evidence/`, `tools/` — under here; every import
is `server.*`). ADR-0035 sub-namespaced `server/tools/` by capability.

| Package | Role |
|---|---|
| `api/` | FastAPI/AgentOS entrypoint (`main.py`), MCP mount (`mcp_main.py`) |
| `core/` | Settings/model-provider factory, DB session, embedder, reranker |
| `contracts/` | Import-light record contract (`NormalizedRecord`) — see `contracts/AGENTS.md` |
| `evidence/` | The evidence spine (custody/store/workflows/cli) — see `evidence/AGENTS.md` |
| `tools/` | Cross-domain parser/extractor/gateway registry — see `tools/AGENTS.md` |
| `agents/` | Agent/team constructors, providers, `@tool` wrappers — see `agents/AGENTS.md` |
| `analysis/` | Behavioral domain: `detection.py`, `patterns.py`, `court_language.py`, `semantica_wiring.py` |
| `ingest/` | Framework-neutral ingest application service + PostgreSQL knowledge read model |
| `case_management/` | Case-management application services and governed case views |
| `observability/` | Audit, telemetry, and operational visibility helpers |
| `temporal/` | Temporal activities/workflows and durable orchestration integration |
| `timeline/` | Canonical timeline membership + Timesketch projection — see `timeline/AGENTS.md` |
| `vendored/` | Third-party projects (`chatminer`, `semantica`) — import-only, excluded from ruff/mypy/pytest |

## Dependency direction (downward only)

```
contracts/   <- innermost. No imports of anything else in server/.
core/        <- settings/session/embedder. No imports of evidence/tools/agents/api.
evidence/    <- imports contracts/, core/. THE spine (custody -> store -> workflows).
tools/       <- imports contracts/ (records), vendored/chatminer. Parsers depend
                INWARD on server.contracts.records, never on evidence/ or agents/.
analysis/    <- imports contracts/, core/, tools/ (registry).
ingest/      <- imports contracts/; composes evidence/tools lazily behind neutral ports.
case_management/, observability/, temporal/, timeline/ <- application/integration packages;
                preserve their governed source and dependency boundaries.
agents/      <- outermost domain layer. Imports evidence/, tools/, analysis/, core/.
api/         <- outermost. Mounts agents/ + evidence/ + tools/ into FastAPI/AgentOS.
```

Never import upward (e.g. `contracts/` must never import `evidence/` or `agents/`) —
`contracts/` in particular is imported by the dep-light `docker/tools` facade
container, so a heavy import there FATAL-loops that container (ADR-0035).

## Relevant ADRs

- ADR-0033 — the `server/` repack (this boundary's origin)
- ADR-0035 — `server/tools/` sub-namespacing + record contract home (`contracts/`)

## When to read deeper

| Task | Read |
|---|---|
| Adding/changing a parser or extractor | `tools/AGENTS.md` |
| Evidence custody/normalize/store work | `evidence/AGENTS.md` |
| Building/changing an agent or team | `agents/AGENTS.md` |
| Touching the record schema | `contracts/AGENTS.md` |
| Timeline membership or Timesketch projection | `timeline/AGENTS.md` |
| DB session, embedder, model provider chain | `core/settings.py`, `core/session.py` (no nested map — small, read the file) |

---

> _Sprint-mode policy REMOVED 2026-08-25 on owner order ("you're grounded — remove it entirely"). Confirm-and-discuss-before-changing is back in force._
