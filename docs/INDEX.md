# Documentation Index — Current Entry Points

> _Byline: Codex · GPT-5 · 2026-08-15 · updated 2026-08-18 (Codex · GPT-5)._
> _2026-08-23 amendment: Claude Code · Opus 5 — corrected the "Held activation" migration
> claim (0026-0030 are applied, CH-15/CH-16) and added the Temporal plan, ingestion-readiness
> note, and cross-repo review directory to Start Here._

Use this page to distinguish durable canon, the accepted 2026-08-15 target, current local
implementation, and historical planning. A file describing a target does not prove it is
deployed.

## Start here

| Need | Document | Authority |
|---|---|---|
| Product invariant and locked decisions | [PROJECT_CANON.md](PROJECT_CANON.md) | Durable canon |
| Current forward order | [BUILD_PLAN.md](BUILD_PLAN.md) | Forward entry point |
| Entire application TODO | [MASTER-TODO-2026-08-18.md](MASTER-TODO-2026-08-18.md) | Authoritative production resume ledger |
| Independent verification of the above | [OWNER-REVIEW-2026-08-18-verified-todo-audit.md](OWNER-REVIEW-2026-08-18-verified-todo-audit.md) | Confirms/contradicts MASTER-TODO against live code+DB; lists gaps and owner-blocked items |
| Evidence Desk handoff | [HANDOFF-2026-08-18-evidence-operations-desk-mvp.md](HANDOFF-2026-08-18-evidence-operations-desk-mvp.md) | Immediate production MVP |
| Derived-document ingest wiring | [HANDOFF-2026-08-29-derived-document-ingest-wiring.md](HANDOFF-2026-08-29-derived-document-ingest-wiring.md) | AI work products (chronologies/strategy/guides) → context → timeline/vectors/graphs; WP-1..WP-11 |
| Repository placement | [REPO_STRUCTURE.md](REPO_STRUCTURE.md) | Structural index |
| Live multi-lane log | [COORDINATION.md](COORDINATION.md) | Append-only coordination history |
| Pending historical review | [pending-review/README.md](pending-review/README.md) | Moved records; all claims UNVERIFIED |
| Archive policy | [archive/README.md](archive/README.md) | Verified or explicitly historical records only |
| Temporal adoption plan | [plans/TEMPORAL-INTEGRATION-PLAN-2026-08-23.md](plans/TEMPORAL-INTEGRATION-PLAN-2026-08-23.md) | Phased adoption plan; D-067 ruled it 2026-08-23 |
| Ingestion readiness | [INGESTION-READINESS-2026-08-23.md](INGESTION-READINESS-2026-08-23.md) | What's up and working for tonight's ingest |
| Cross-repo evidence audit | [reviews/2026-08-23-cross-repo-evidence-audit/](reviews/2026-08-23-cross-repo-evidence-audit/) | Issues/TODO register (ISS-/TODO-numbered), framework-roles ruling (TODO-212), custody ruling (TODO-101/207) |

## Current truth in one paragraph

Agno 2.8.7/AgentOS is the **current runtime adapter**, while framework-neutral contracts and
the custom Workbench are the **accepted target**. Knowledge is ingested once without horizon
restriction; agents later receive immutable, filtered horizon experiences. Semantica is a VIP
service whose findings may be governed candidates. PostgreSQL is authoritative; Graphiti is a
run-scoped belief projection. Portkey remains preferred routing, OpenCode adds persistent
workspace/provider flexibility, and AG2 remains a candidate coordination adapter. Go routing is
decoder-coverage based at every file size.

ADR-0056–0058 add a governed Surreal analytical/walk-memory target, claim-centered evidence
assembly, Investigation Search, and scoped behavioral analysis. This does not reactivate the
parked legacy Surreal deployment or change PostgreSQL authority. See the goal hierarchy and
technical blueprint above; the new capabilities are design-only.

The Phase-0 review package now defines logical contracts, routes 33 unresolved questions,
specifies the gold corpus/evaluation gates, and adds a 14-test synthetic future-fact canary.
It does not verify live adapters or authorize Phase 1. Six compact owner choices remain pending.

## Held activation

The Matter/CourtCase foundation, migration `0030`, neutral spine APIs,
Workbench adapters/UI, provenance-preserving Knowledge-to-Evidence promotion,
custody inspection, court-readiness read side, and activation preflight are
committed and pushed to `main`. ~~The worktree is clean.~~ **Corrected
2026-08-18 (Claude Code · Fable 5): the worktree is currently DIRTY** — live
`git status` shows uncommitted changes (docs reorg, SurrealDB runner files,
`AGENTS.md`, compose/deploy yaml); see
[OWNER-REVIEW-2026-08-18-verified-todo-audit.md](OWNER-REVIEW-2026-08-18-verified-todo-audit.md)
Part 2. ~~Migrations `0026–0030`
remain unapplied~~ **Corrected 2026-08-23 (Claude Code · Opus 5, CH-15/CH-16): migrations
`0026`–`0030` are APPLIED** to live PG18 (`100.91.190.107:5432`, db `ai`) — `0026`-`0029`
were found already live (stale banners), `0030` was applied the same night on owner
instruction. The **feature** (Matter/CourtCase-aware evidence pipeline, native evidence
vectors) remains undeployed; no live-service proof beyond the applied schema is
claimed. Use the R9 handoff and activation preflight pre-mortem for current
verification and release gates.

Three divergent self-contained Workbench mockups and their evaluation reports
are available through the comparison page above. They are prototypes, not the
deployed Workbench.

## Archived lane packets and historical plans

- [R0–R14 packets](pending-review/handoffs/) (pending independent review)

Historical packets, dated plans, inventories, summaries, evaluations, and design history are
archived by category. They remain read-only context and never override current production truth.
