---
scope: server
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/AGENTS.md
  - docs/CONVENTIONS.md
  - docs/REPO_STRUCTURE.md
  - docs/PROJECT_CANON.md
watches:
  - server/**
  - tests/**
contains_secrets: false
---

# Backend Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

## Stable conventions

- Keep dependency flow inward as mapped by `server/AGENTS.md`; contracts stay import-light.
- Python modules use purpose docstrings, future annotations, typed boundaries, Pydantic for
  governed schemas, descriptive names, and comments that explain why.
- Tools are atomic, capability-resolved, and transport-neutral. A parser parses; it does not hash,
  persist, normalize, analyze, or govern promotion.
- PostgreSQL owns canonical state and receipts. Search, graph, and UI systems consume governed
  projections or APIs.
- Every public capability ultimately needs an internal API and MCP exposure, but the current Agno
  adapter must not own the public contract being preserved through its replacement.

## Child memory

| Scope | Read |
|---|---|
| `server/api/**` | `server/api/AGENT_MEMORY.md` |
| `server/core/**` | `server/core/AGENT_MEMORY.md` |
| `server/contracts/**` | `server/contracts/AGENT_MEMORY.md` |
| `server/evidence/**` | `server/evidence/AGENT_MEMORY.md` |
| `server/tools/**` | `server/tools/AGENT_MEMORY.md` |
| `server/agents/**` | `server/agents/AGENT_MEMORY.md` |
| `server/analysis/**` | `server/analysis/AGENT_MEMORY.md` |
| `server/temporal/**` | `server/temporal/AGENT_MEMORY.md` |
| `server/timeline/**` | `server/timeline/AGENT_MEMORY.md` |

Closest nested `AGENTS.md` remains mandatory for contracts, evidence, tools, agents, timeline,
and repair work.

<!-- freshness
watches_hash: bbbf5c6
last_verified: 2026-08-27
watches:
  - server/**/*.py
  - server/**/AGENTS.md
  - docs/CONVENTIONS.md
  - docs/REPO_STRUCTURE.md
-->
