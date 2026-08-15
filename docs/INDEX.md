# Documentation Index — Current Entry Points

> _Byline: Codex · GPT-5 · 2026-08-15._

Use this page to distinguish durable canon, the accepted 2026-08-15 target, current local
implementation, and historical planning. A file describing a target does not prove it is
deployed.

## Start here

| Need | Document | Authority |
|---|---|---|
| Product invariant and locked decisions | [PROJECT_CANON.md](PROJECT_CANON.md) | Durable canon |
| Current forward order | [BUILD_PLAN.md](BUILD_PLAN.md) | Forward entry point |
| Framework-neutral migration plan | [PLAN-2026-08-15-platform-runtime-migration.md](PLAN-2026-08-15-platform-runtime-migration.md) | Accepted target |
| Product surfaces | [PRODUCT-BLUEPRINT-2026-08-15.md](PRODUCT-BLUEPRINT-2026-08-15.md) | Accepted target |
| Workbench HTML design review | [mockup comparison](../workbench/design-mockups/index.html) | Local review artifact |
| Component boundaries | [ARCHITECTURE-BLUEPRINT-2026-08-15.md](ARCHITECTURE-BLUEPRINT-2026-08-15.md) | Accepted target |
| Migration/dependency views | [MIGRATION-DIAGRAMS-2026-08-15.md](MIGRATION-DIAGRAMS-2026-08-15.md) | Accepted target |
| Agent/lane ownership | [TASK-DISTRIBUTION-2026-08-15.md](TASK-DISTRIBUTION-2026-08-15.md) | Coordination contract |
| Executable handoffs | [HANDOFFS.md](HANDOFFS.md) | Current R0–R9 index |
| Repository placement | [REPO_STRUCTURE.md](REPO_STRUCTURE.md) | Structural index |
| Live multi-lane log | [COORDINATION.md](COORDINATION.md) | Append-only coordination history |

## Current truth in one paragraph

Agno 2.8.7/AgentOS is the **current runtime adapter**, while framework-neutral contracts and
the custom Workbench are the **accepted target**. Knowledge is ingested once without horizon
restriction; agents later receive immutable, filtered horizon experiences. Semantica is a VIP
service whose findings may be governed candidates. PostgreSQL is authoritative; Graphiti is a
run-scoped belief projection. Portkey remains preferred routing, OpenCode adds persistent
workspace/provider flexibility, and AG2 remains a candidate coordination adapter. Go routing is
decoder-coverage based at every file size.

## Held local implementation

The dirty working tree contains the Matter/CourtCase foundation, migration `0030`, neutral
spine APIs, Workbench adapters/UI, and provenance-preserving Knowledge-to-Evidence promotion.
Focused tests have been run, but the migration is unapplied and the feature is uncommitted and
undeployed. Wave-1 migrations `0026–0029` are also held after the R0 audit.

Three divergent self-contained Workbench mockups and their evaluation reports
are available through the comparison page above. They are prototypes, not the
deployed Workbench.

## Lane packets

- [R0 Wave-1 audit](HANDOFF-2026-08-15-R0-wave1-audit.md)
- [R1 Go ingestion](HANDOFF-2026-08-15-R1-go-ingestion.md)
- [R2 horizon engine](HANDOFF-2026-08-15-R2-horizon-engine.md)
- [R3 Semantica VIP](HANDOFF-2026-08-15-R3-semantica.md)
- [R4 Graphiti/Zep memory](HANDOFF-2026-08-15-R4-graphiti-zep-memory.md)
- [R5 AG2 coordination](HANDOFF-2026-08-15-R5-ag2-coordination.md)
- [R6 provider switching](HANDOFF-2026-08-15-R6-provider-switching.md)
- [R7 OpenCode workspace](HANDOFF-2026-08-15-R7-opencode-workspace.md)
- [R8 custom Workbench](HANDOFF-2026-08-15-R8-workbench.md)
- [R9 Knowledge-to-case MVP](HANDOFF-2026-08-15-R9-knowledge-to-case-mvp.md)

R9's earlier “Matter missing” statement is superseded by the held local implementation above;
the packet remains valuable as its design and safety rationale.
