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
| Surreal/investigation goal hierarchy | [GOALS-2026-08-15-surreal-investigation-memory.md](GOALS-2026-08-15-surreal-investigation-memory.md) | Accepted goals; implementation not started |
| Surreal/investigation technical blueprint | [SURREAL-INVESTIGATION-BLUEPRINT-2026-08-15.md](SURREAL-INVESTIGATION-BLUEPRINT-2026-08-15.md) | Accepted boundaries + proposed contracts |
| Workbench HTML design review | [mockup comparison](../workbench/design-mockups/index.html) | Local review artifact |
| Component boundaries | [ARCHITECTURE-BLUEPRINT-2026-08-15.md](ARCHITECTURE-BLUEPRINT-2026-08-15.md) | Accepted target |
| Migration/dependency views | [MIGRATION-DIAGRAMS-2026-08-15.md](MIGRATION-DIAGRAMS-2026-08-15.md) | Accepted target |
| Agent/lane ownership | [TASK-DISTRIBUTION-2026-08-15.md](TASK-DISTRIBUTION-2026-08-15.md) | Coordination contract |
| Executable handoffs | [HANDOFFS.md](HANDOFFS.md) | Current R0–R9 index |
| Pending Matter decisions | [Matter MVP owner packet](PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md) | Pending owner ruling; not an ADR |
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

ADR-0056–0058 add a governed Surreal analytical/walk-memory target, claim-centered evidence
assembly, Investigation Search, and scoped behavioral analysis. This does not reactivate the
parked legacy Surreal deployment or change PostgreSQL authority. See the goal hierarchy and
technical blueprint above; the new capabilities are design-only.

## Held activation

The Matter/CourtCase foundation, migration `0030`, neutral spine APIs,
Workbench adapters/UI, provenance-preserving Knowledge-to-Evidence promotion,
custody inspection, court-readiness read side, and activation preflight are
committed and pushed to `main`. The worktree is clean. Migrations `0026–0030`
remain unapplied and the feature remains undeployed; no live-service proof is
claimed. Use the R9 handoff and activation preflight pre-mortem for current
verification and release gates.

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
- [R10 Surreal analytical memory and investigation design](HANDOFF-2026-08-15-R10-surreal-investigation-design.md)

R9's earlier “Matter missing” statement is superseded by the committed local implementation above;
the packet remains valuable as its design and safety rationale.
