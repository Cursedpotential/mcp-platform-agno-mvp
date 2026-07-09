# Architecture Directives

> **These are ACTIVE design directives, not archived history.** They were the owner's
> 2026-06-14 architecture-brainstorming set; most are still-good directives the build should
> follow. Moved here (from the old untracked `.planning/build/`) and renamed 2026-07-09 so
> they read as live guidance — earlier "build-notes-archive" naming undersold them.

| File | Directive | Lane |
|---|---|---|
| `ARCHITECTURE-HANDOFF-2026-06-14.md` | Architecture brainstorming handoff — the parent design intent | all |
| `architecture-validation-2026-06-14.md` | SurrealDB / pgwire / Portkey / federation validation | C (infra) |
| `contextforge-integration.md` | ContextForge MCP gateway integration design (EXEC tier / OVH-1) | C |
| `surrealdb-integration.md` | SurrealDB integration design (DRAFT — do not deploy yet) | C / B (analysis sink) |
| `dns-and-domains.md` | DNS + Traefik base-domain plan (mitechconsult.com) | C |
| `topology-rewire-notes.md` | compose.data.yaml + compose.exec.yaml topology rewire | C |
| `create-dns.mjs` | DNS-creation helper script | C |
| `README.md` | original `.planning/` working-plans note | — |

**Status:** these predate the current live infra (Lane C has since shipped ContextForge
v1.0.4, Portkey, coolify-mcp) — so treat them as **directives + design rationale to
reconcile against what's now live**, not as literal to-dos. Where a directive and live reality
disagree, live wins; capture the delta in an ADR.
