# Documentation Patch Report — Runtime Migration and Blueprint Persistence

> _Byline: Codex · GPT-5 · 2026-08-15_
<!-- Updated by: Codex (migration-passes/doc-patching) | Date: 2026-08-15 | Rev: 1 | Platform: Codex / win32 | Changes: Record Workbench and BUILD_PLAN true-up | Context: Concurrent Knowledge implementation invalidated an earlier missing-page finding -->

> **Current-state correction — 2026-08-15 (Codex · GPT-5):** This report
> records an earlier documentation pass and intentionally preserves its
> then-current observations below. The Knowledge/Matter implementation,
> Classification Lab repair, court-readiness read side, and activation preflight
> are now committed and pushed on clean `main`. They remain undeployed;
> migrations `0026`–`0030`, credential provisioning, and live cross-service proof
> are still held. Use `docs/INDEX.md` and the R9 handoff for current status.

## True-up batch — 2026-08-15

- Updated `docs/BUILD_PLAN.md` without replacing historical phase text: Wave-1 files are
  present only in the dirty working tree and are not recorded as committed, applied, or
  deployed; the Knowledge page/API is locally verified but uncommitted/undeployed; Semantica is a VIP semantic-intelligence
  service whose candidate outputs remain governed proposals until human promotion.
- Updated `workbench/api/README.md` to point to `deploy/workbench.yaml`, verify the existing
  `tests/test_structure.py` enforcement gate, inventory the current API layers, and describe
  Weaviate schema inspection plus its deprecated `milvus` response alias.
- Documented the Knowledge routes and page as **locally verified, uncommitted, and undeployed**:
  `workbench/web/src/app/knowledge/page.tsx`,
  `workbench/web/src/components/knowledge/knowledge-browser.tsx`,
  `workbench/api/app/runtime/knowledge.py`, and
  `workbench/api/app/service/knowledge.py` now exist in the shared working tree.
- Did not edit code, migrations, canon, ADRs, deployment manifests, or Wave-1 plans; did not
  move or delete any file.

## PLANNED CHANGE

- **Scope:** persist the runtime-migration plan, product/architecture blueprints, migration diagrams, task handoffs, and a documentation-cleanup proposal.
- **Safety:** additive files only in this pass, except a dated addendum to the explicitly requested review report. No document was removed, relocated, or silently rewritten.
- **Approval boundary:** architecture-bearing corrections and moves remain proposals until owner review. Any eventual removal goes to `to_be_deleted/`, never permanent deletion.

## Created artifacts

| Artifact set | Purpose | Status |
|---|---|---|
| `docs/PLAN-2026-08-15-platform-runtime-migration.md` | Executable migration waves and gates | Added |
| `docs/PRODUCT-BLUEPRINT-2026-08-15.md` | Product planes, surfaces, memory taxonomy | Added |
| `docs/ARCHITECTURE-BLUEPRINT-2026-08-15.md` | Polyglot ownership and runtime boundaries | Added |
| `docs/MIGRATION-DIAGRAMS-2026-08-15.md` | Target, strangler, Go, and dependency diagrams | Added |
| `docs/TASK-DISTRIBUTION-2026-08-15.md` | Nine research/implementation lanes | Added |
| `docs/HANDOFF-2026-08-15-R0-*.md` through `R8-*.md` | HANDOFF-v2 work packets | Added |
| `.agents/blueprint/*.md` | App-blueprint v2 reverse/forward bundle | Added |
| `docs/DOC_CLEANUP_MANIFEST-2026-08-15.md` | Safe drift and quarantine queue | Added |
| `docs/reports/mcp-platform-agno-review.md` | Dated current-state addendum | Appended |

## Drift findings

### Stale references

- **APPLIED 2026-08-15:** `workbench/api/README.md` no longer points to missing
  `compose.workbench.yaml`; it now identifies `deploy/workbench.yaml`.
- **APPLIED 2026-08-15:** the README now correctly identifies
  `workbench/api/tests/test_structure.py` as the dependency-direction gate.
- `workbench/api/main.py:7-11` still describes PG/Milvus views and Milvus-backed knowledge after Weaviate became authoritative.
- `deploy/data-weaviate.yaml:18` and `deploy/data-graphiti-case.yaml:68` retain the retired `100.119.96.29` host in instructions/defaults.
- Historical Portkey documentation contains LiteLLM-live prose followed by a later retirement correction; current supervisor config keeps LiteLLM disabled.

### Missing or broken product coverage

- ~~Workbench navigation declares `/knowledge`, but no page exists.~~ **Corrected later
  2026-08-15:** `workbench/web/src/app/knowledge/page.tsx` and its browser component now
  exist as concurrent uncommitted implementation. Local tests/build pass; live validation remains pending.
- `/copilot` exists but is absent from sidebar navigation.
- The uncommitted Classification Lab appears to call `/api/{classification|sentiment|comparison}` while its routers are mounted without the `/api` prefix.
- Semantica is a VIP semantic-intelligence component, not a “candidate service.” Its
  deployment and observed writes remain unverified; configuration is not proof of a working
  integration. “Candidate” names its entity/claim/time/event proposal outputs, which remain
  outside authored canonical truth until governed human promotion.

### Architecture drift requiring owner-approved correction

- Existing `docs/blueprint/` predates this `.agents/blueprint/` package and describes a narrower ADR-0051/0053 system. It should remain historical until the owner chooses consolidation or supersession.
- `docs/HANDOFF-2026-08-09-S8-semantica-graph-lane.md` should preserve Semantica’s VIP/full-capability status while being checked against ADR-0043’s governed PostgreSQL promotion boundary before implementation.
- Any `max_safe_size` parser-routing language conflicts with the owner’s coverage-based routing decision.
- Graphiti/Neo4j has distinct root-compose and deployed-case variants; documentation must not collapse them into one universal topology.
- Wave-1 pre-mortems need review banners that link to the R0 gap audit before their success claims are used for cutover.
- Historical SurrealDB, Milvus, and LiteLLM ADRs should receive explicit supersession navigation, not be erased.

## Intent and example drift

- The old review addendum frames derived horizon tables as a possible departure from “pass as filter.” Current ADR-0045/Wave-1 work treats walk materializations as derived, pinned run products rather than parallel authored stores. The new addendum records this distinction without rewriting the historical discussion.
- Workbench comments and examples should use current platform vocabulary: Weaviate, neutral runtime route, belief projection, and created work products—not obsolete store names or framework-owned IDs.

## Verification performed

- Repository source paths and line references were checked on 2026-08-15.
- The current working tree was treated as the review target; it contains substantial pre-existing uncommitted work.
- No live service or deployment mutations were performed.
- Rechecked every path named in the true-up batch. `deploy/workbench.yaml`,
  `workbench/api/tests/test_structure.py`, and all Knowledge implementation paths exist.
- Local validation passed: 48 Workbench API tests, focused ESLint over the Knowledge files,
  and the Next.js production build with `/knowledge` statically generated. Full frontend lint
  remains red only in the separate uncommitted Classification Lab lane.
- Mermaid CLI (`mmdc`) was not installed. A structural hand-check found 17 closed Mermaid blocks across five documents, balanced Markdown fences, and zero broken local Markdown links. Render validation remains pending; no package was installed merely to claim it.

## Owner decisions requested

1. Make `.agents/blueprint/` the generated-agent blueprint contract and keep `docs/blueprint/` as historical until consolidated.
2. Review the applied low-risk Workbench **documentation** corrections; route/navigation or
   schema-label code fixes remain a separate implementation task.
3. Approve supersession banners for historical runtime/store docs.
4. Approve moving only confirmed redundant session summaries/obsolete duplicates to `to_be_deleted/docs-2026-08-15/` after a manifest review.
