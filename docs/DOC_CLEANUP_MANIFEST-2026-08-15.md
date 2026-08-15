# Documentation Cleanup Manifest

> _Byline: Codex · GPT-5 · 2026-08-15_
<!-- Updated by: Codex (migration-passes/doc-patching) | Date: 2026-08-15 | Rev: 1 | Platform: Codex / win32 | Changes: Record completed doc true-up and concurrent Knowledge work | Context: Keep cleanup status accurate without moving or deleting owner files -->

STATUS: ENTRY-POINT REPAIR COMPLETE; QUARANTINE STILL PROPOSED — no files moved or deleted

## Rules

- Keep history that explains decisions; add a supersession banner and current pointer.
- Correct current operational instructions in place after verification.
- Consolidate exact duplicates only after comparing their unique facts.
- Move approved obsolete material to `to_be_deleted/docs-2026-08-15/` with this manifest and a replacement pointer.
- Only the owner permanently deletes from `to_be_deleted/`.

## Action queue

| Class | Candidates | Proposed action | Gate |
|---|---|---|---|
| Current canon | `AGENTS.md`, `docs/PROJECT_CANON.md`, active ADRs, change/decision logs | KEEP and update through normal decision process | Never bulk-move |
| New migration packet | 2026-08-15 plan, blueprints, diagrams, R0-R8 handoffs | KEEP; link from a single index after review | Owner accepts direction |
| Generated blueprint contract | `.agents/blueprint/*.md` | KEEP as app-blueprint output | Validate and commit |
| Prior blueprint | `docs/blueprint/*.md` | HISTORICAL_WITH_SUPERSESSION; later merge unique facts into new blueprint | Owner selects canonical location |
| Session compactions | `docs/COMPACT-SUMMARY-*.md` | INVENTORY_FOR_QUARANTINE; preserve unique rulings first | Content comparison + owner approval |
| Superseded store/runtime ADRs | SurrealDB, Milvus, LiteLLM-era ADRs/docs | KEEP HISTORICAL; add superseded-by banners/index links | ADR index review |
| Workbench operational drift | `workbench/api/README.md` | UPDATED_IN_PLACE 2026-08-15: deploy path, enforced layering, Weaviate schema behavior, and locally verified Knowledge routes corrected | Local tests/build pass; live validation still open |
| Workbench inline-code drift | `workbench/api/main.py`, inspect service/runtime docstrings, schema UI/types | UPDATE_IN_PLACE in a code-owned lane; Milvus labels remain compatibility/history debt | Code owner + tests |
| Knowledge surface | `workbench/web/src/app/knowledge/page.tsx` and related browser/API/service files | KEEP; locally verified, uncommitted implementation, not a cleanup target | Commit review + live verification |
| Deployment host drift | `deploy/data-weaviate.yaml`, `deploy/data-graphiti-case.yaml`, `deploy/data-neo4j.yaml` | UPDATE_IN_PLACE only after live inventory | Read-only live check |
| Wave-1 review docs | `docs/plans/WAVE1-*.md` | ADD CORRECTION/REVIEW BANNERS; do not quarantine | Owner reviews R0 findings |
| Semantica handoff drift | `docs/HANDOFF-2026-08-09-S8-semantica-graph-lane.md` | PRESERVE VIP status and full capabilities; correct only the governed canonical-write/CDC boundary | ADR-0043 + VIP owner ruling trace check |
| Parser size-routing language | Any `max_safe_size`/size-threshold guidance | CORRECT to coverage-based routing | ADR/owner-rule trace check |

## First cleanup batch — recommended

This batch is quick and low risk after approval:

1. ~~Correct Workbench README paths and Milvus comments.~~ **Documentation portion completed
   2026-08-15.** Remaining Milvus compatibility labels are in code/types and stay assigned to
   a code-owned follow-up.
2. Resolve the Classification Lab API prefix and navigation gaps in code/tests, then document observed behavior. **In progress; full lint repair assigned.**
3. ~~Add supersession banners to the old `docs/blueprint/` index and relevant historical store/runtime documents.~~ **Completed for the highest-risk executable entry points 2026-08-15.**
4. ~~Add a current documentation index linking canon, plan, blueprints, handoffs, and cleanup status.~~ **Completed: `docs/INDEX.md`.**
5. Run a broken-link/path-reference scan and a terminology scan. **Current-entry-point Markdown path scan passed; repository-wide historical scan remains.**

## Exact proposed quarantine set — owner review required

Nothing in this list has been moved. If approved after unique-fact extraction,
the recoverable destination is `to_be_deleted/docs-2026-08-15/`:

- `docs/blueprint/` — older duplicate blueprint; now carries a supersession banner.
- `docs/planning/gui-integration-spec.md` — native-AgentOS/LiteLLM UI direction superseded by the custom Workbench.
- `docs/ADR_RECONCILIATION.md` — June proposal sweep ending at ADR-0022; now bannered historical.
- `docs/planning/forensic-db-architecture/` — Milvus/SurrealDB-era draft packet, only after extracting unique court-safety rationale.
- Exact redundant `docs/COMPACT-SUMMARY-*.md` files, but only after a content/hash comparison proves their rulings are represented elsewhere.

Older handoffs, ADRs, pre-mortems, and inactive deployment manifests are **not**
part of this proposed first move. They remain historical or rollback evidence.

## Deferred quarantine batch

Do not move these merely because they are old:

- `docs/COMPACT-SUMMARY-*.md`
- older handoffs and pre-mortems
- superseded ADRs
- deployment manifests for inactive services

They may contain rulings, rollback instructions, or evidence of why a decision changed. First extract unique facts into canon/decision logs, record hashes and replacement pointers, then request owner approval for the exact move list.

## Clean-worktree protocol

1. Partition `git status` by owner/lane and generated artifact.
2. Validate each lane independently; do not mix Wave-1 migrations, Workbench classification, Portkey routing, and planning docs into one commit.
3. Commit accepted lanes with required co-author attribution.
4. Push only after the owner authorizes the branch/remote action and confirms no deployment-trigger surprise.
5. Re-run `git status --short --branch`; clean means no tracked modifications and no untracked files, including quarantined material.
6. If a file is rejected, move it to `to_be_deleted/` only after exact-target approval; never hard-delete.

## UNRESOLVED

- Whether `docs/blueprint/` or `.agents/blueprint/` should be the human-facing canonical location.
- Which compact summaries still contain facts not represented in current canon.
- Whether inactive deployment manifests remain rollback assets or should be quarantined.
- Which dirty-tree lanes belong to the other active agent and are ready for commit.
- Whether the locally validated Knowledge implementation is accepted for commit/deployment
  and passes live Weaviate/Graphiti verification.
- When Wave-1 migrations `0026`–`0029` will be reviewed, committed, rollback-tested, and
  applied; their presence in the working tree is not proof of live state.
