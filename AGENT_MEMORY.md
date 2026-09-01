---
scope: .
status: current
verified_at: 2026-08-29
superseded_by: null
authority:
  - AGENTS.md
  - docs/INDEX.md
  - docs/PROJECT_CANON.md
  - docs/DECISION_LOG.md
  - docs/MEMORY_ARCHITECTURE.md
watches:
  - AGENTS.md
  - docs/INDEX.md
  - docs/PROJECT_CANON.md
  - docs/DECISION_LOG.md
contains_secrets: false
---

# Repository Agent Memory

> _Byline: Codex · GPT-5 · 2026-08-27; navigation verification refreshed 2026-08-29._

This file is a router, not an encyclopedia. Read only the branches relevant to the current task.

## Durable owner preferences

- **Owner directive:** lead with the result, use labeled sections and plain English, and use an
  HTML/diagram/table when complex relationships materially benefit from a visual surface.
- **Owner directive:** finish one functional vertical slice before adding another feature; never
  substitute an unapproved surface or disconnected stub without explicit disclosure.
- **Owner directive:** persist material findings, decisions, implementation, and verification in
  project documentation; chat-only results are not a handoff.
- **Owner directive:** preserve concurrent work, use bounded ownership, and never hard-delete.
- **Owner directive:** edit and validate source in this checkout; commit and push; Coolify builds
  and deploys on the VPS. Do not create a duplicate local infrastructure stack.

## Current cross-tree corrections

- SurrealDB remains the governed temporal-graph, walk, and analysis target. Only the retired legacy
  operational adapter/instance is parked. See `AGENTS.md` and ADR-0056.
- LanceDB is not part of the current platform stack. Milvus remains deliberately inactive; current
  search projection is Weaviate. See `AGENTS.md`.
- PostgreSQL remains canonical. Timesketch, search, graph, RAG, and operator surfaces are governed
  views or projections, not replacement authority.

## Path router

| Path in scope | Read next |
|---|---|
| `docs/**` | `docs/AGENT_MEMORY.md` |
| `server/**` | `server/AGENT_MEMORY.md` plus the closest nested memory |
| `engine/**` | `engine/AGENT_MEMORY.md` |
| `contracts/**` | `contracts/AGENT_MEMORY.md` |
| `sql/**` | `sql/AGENT_MEMORY.md` |
| `deploy/**` | `deploy/AGENT_MEMORY.md` |
| `docker/**` | `docker/AGENT_MEMORY.md`; for n8n also `docker/n8n/AGENT_MEMORY.md` |
| `workbench/**` | `workbench/AGENT_MEMORY.md` plus the closest nested memory |
| `timesketch-fork/**` | `timesketch-fork/AGENT_MEMORY.md` |
| `tests/**` | `tests/AGENT_MEMORY.md` |
| `knowledge/**` | `knowledge/AGENT_MEMORY.md` |
| `vendored/**`, `server/vendored/**` | `vendored/AGENT_MEMORY.md` |
| `llm_probe/**`, `llm_probe_ui/**` | `llm_probe/AGENT_MEMORY.md` or `llm_probe_ui/AGENT_MEMORY.md` |

Format and precedence: `docs/agent-memory/README.md`.

<!-- freshness
watches_hash: 692a4b7
last_verified: 2026-08-29
watches:
  - AGENTS.md
  - docs/INDEX.md
  - docs/PROJECT_CANON.md
  - docs/DECISION_LOG.md
  - docs/MEMORY_ARCHITECTURE.md
-->

## Geo lane is PARKED (D-121, 2026-08-31) — note for every future session
The location/GPS lane (stay_point, gps_track, geocode_*, home_base,
waypoint_device_split, vehicle, geofence, geocode_audit) is REAL, owner-ruled,
and deliberately OUT of the live database until ingest is proven on lesser
data. Complete one-file restore: `sql/parked/geo_lane_parked_20260831.sql`
(restore-proven against a clean target). Do NOT recreate these ad hoc; do NOT
treat their absence as a gap. Owner: "why am I gonna bring in the key to the
application I've been working on even longer than this, just to have it
fucked up too."

## Git on this repo: Desktop Commander ONLY
Sandbox cannot unlink .git locks or push (no credentials). Write a .ps1 to
C:\Temp, run via DC start_process. Proven 2026-08-31 (commit 15a1d87).
