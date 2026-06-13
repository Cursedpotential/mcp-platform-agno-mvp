# ADR-0022: The wiki is a comprehensive, living, dual-purpose (AI + human) knowledge base
- Status: Accepted (vision locked; build deferred)
- Date: 2026-06-11
- Relates to: ADR-0020 (multi-domain knowledge engine) — the wiki is its human-readable face.

## Context
Documentation today is fragmented (ADRs, canon, stale skeleton readmes, three large archived
wikis in `dev-resources`). The owner wants ONE wiki that is **both AI-queryable and
human-readable** and that **covers everything** — not a subset, not just architecture.

## Decision
Build a single **living, comprehensive wiki** that is the documentation layer of the whole
platform. It is **dual-rendered**:
- **Human-readable** — navigable, cross-linked markdown (Obsidian-style).
- **AI-queryable** — ingested into the multi-domain knowledge engine (ADR-0020) so any agent
  can query it.

**Scope = everything**, including at minimum:
- **Every library used** — purpose, version, how we use it, gotchas (a living dependency encyclopedia).
- **Every application/service used** — each stack component, its config, ports, quirks.
- **Every bit of code created** — the codebase documented (modules, contracts, tools/workflows).
- **Every decision** — ADRs flow in; the canon flows in.
- **Every strategy** — platform strategy AND legal strategy.

It is **living**: kept current as part of the work (agents maintain it — a documentation role in
the Builder family + doc-generation skills), not a one-time dump. It absorbs and supersedes the
three archived wikis (`dev-resources/.../wiki`, mined into domains + reusable code).

## Consequences
- Every domain of the knowledge engine (platform_design, legal_strategy, timeline, personal) has
  a wiki surface; the wiki and the knowledge engine are the same content, two renderings.
- Doc generation/maintenance becomes a standing agent responsibility (not ad-hoc).
- ADRs + `PROJECT_CANON.md` are inputs/sections, not competitors — the wiki is the superset.
- Large build: deferred (tracked task). Until then, `PROJECT_CANON.md` is the interim source of truth.

## Alternatives considered
- Keep docs fragmented (ADRs + readmes only) — rejected: not comprehensive, not queryable, drifts.
- Human-only wiki — rejected: agents must query it. AI-only index — rejected: the owner must read it too.
