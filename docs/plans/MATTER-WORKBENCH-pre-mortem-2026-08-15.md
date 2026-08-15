# Matter Workbench + Knowledge Promotion — Pre-Mortem (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

STATUS: BUILT LOCALLY, VERIFIED, UNDEPLOYED

## Outcome

The local Workbench can create and browse an enduring Matter, add CourtCase
proceedings, resolve a custody-backed evidence-lane Knowledge result to an
exact normalized record, and create an idempotent draft evidence item. The
operator can then record an append-only reviewer-of-record decision through the
canonical `analysis.review_task` / `analysis.review_decision` system. Review
history remains visible after refresh with reviewer, rationale, outcome, and
decision time. Matter Home now contains the full canonical Knowledge journey:
its partition and primary CourtCase are prebound, while the standalone
Knowledge browser remains available. Review alone never authenticates the
evidence or marks it safe for legal use. The spine remains authoritative;
Workbench is an HTTP adapter. Horizon execution is intentionally absent.

## Pre-mortem failures and controls

| Failure | Consequence | Implemented control | Remaining risk |
|---|---|---|---|
| A ranked Knowledge chunk is treated as evidence | Context or generated text enters case work as fact | Promotion is offered only for evidence-lane hits with artifact UUID + SHA-256; the operator must select an exact normalized record | Live metadata completeness is not proven |
| The whole chunk is passed as an “exact quote” | Source resolution returns zero candidates or records a false span | Resolution omits chunk text; after selection, the exact normalized-record content is bound and server-verified | A later UI should support explicit sub-record quote spans |
| A non-evidence Knowledge lane appears promotable | Legal/context/platform Knowledge is mistaken for custody evidence | The browser labels those hits nonpromotable and the spine independently rejects every non-evidence lane | Future research-note promotion needs a different, non-evidence contract |
| CourtCase and Knowledge partition are conflated | Cross-matter leakage and identity drift | UUID Matter/CourtCase scope and text partition are separate; every request verifies the bridge and same-matter CourtCase ownership | Per-matter grants are not yet implemented |
| Workbench becomes an unauthenticated confused deputy | Any reachable caller uses the BFF's privileged spine credential as the owner | Mandatory fail-closed `WORKBENCH_API_KEY` protects API, docs, and static UI; only exact `/health` is public; actor inputs are fixed to the authenticated single-owner identity | Key provisioning, rotation, and eventual named principals remain deployment/future work |
| Multiple bound partitions silently select the wrong corpus | Retrieval and promotion use an arbitrary array order | Matter Home enables bound Knowledge only when exactly one partition exists; zero/multiple partitions fail closed | A later explicit partition picker must remain restricted to the Matter bridge |
| Retry duplicates evidence | Review queue silently accumulates duplicate drafts | Canonical pointer hash + transaction advisory lock + unique ledger constraints return the existing item | Live concurrent Postgres proof remains pending |
| Pointer metadata disagrees with immutable provenance | A misleading ledger survives even though relational IDs are correct | Migration trigger enforces evidence-only lane, pointer/ledger equality, canonical pointer hash, H1 SHA-256 algorithm/canon, and digest equality | Full custom-image baseline proof remains pending |
| New evidence is assumed court-ready | Unauthenticated material reaches exports | DB trigger, spine response, Workbench response validation, and UI labels require unreviewed/HITL/unsafe/unauthenticated state | Existing legacy review/export surfaces still need an end-to-end audit |
| Human approval silently means “court safe” | A record-level content review bypasses authentication/redaction gates | Review writes the canonical append-only decision, but always forces `safe_for_legal_use=false`; Workbench and proxy reject any response that claims authentication or legal safety | A separate authentication workflow remains required |
| A reviewer decides from a quote card without reopening canonical provenance | The human decision is not grounded in the exact record and custody chain | Every item has persistent provenance inspection; the review dialog fresh-loads the Matter-scoped record/H1/source/file-node detail and disables all decision controls until it succeeds | Source authentication and legal release remain separate gates |
| Double-click records two terminal decisions | Reviewer history forks | Evidence row + active review task are locked; terminal decisions resolve the task and a second terminal attempt returns 409 | Reconsideration will need an explicit new-task workflow |
| A status badge survives but its reviewer rationale disappears | Later operators cannot explain who decided what or why | Matter Workbench reads the canonical append-only review-decision history scoped through Matter + evidence item and displays reviewer, rationale, readiness, and timestamp | Reconsideration remains a future explicit new-task workflow |
| The operator leaves Matter Home and manually re-enters scope | A typo or stale selection targets the wrong Knowledge partition or proceeding | Matter Home prebinds its explicit partition and primary CourtCase; bound promotion never lists/reselects Matters, while the spine still rechecks ownership | Matters without a partition or primary CourtCase fail closed until configured |
| Graphiti belief memory looks like Matter evidence | Rebuildable agent belief state is promoted as canonical source material | The Matter-bound pane omits every Graphiti tab/call and labels that boundary explicitly | Authenticated per-run memory grants remain post-MVP |
| Agno removal breaks case management | Product logic stays trapped in the outgoing runtime | Contracts, repository, and `/v1` routes use platform vocabulary; Workbench calls the spine through a neutral HTTP adapter | Current boot still wraps the routes with AgentOS |
| Code deploys before schema | New routes 500 against missing tables | Migration 0030 is held and code is not committed, pushed, or deployed | Release ordering must be owner-reviewed with held 0026–0029 |

## Fresh local evidence

- Full Python suite: **721 passed, 24 skipped**.
- Full Ruff lint and mypy: **PASS**.
- Matter spine + migration focused tests: **25 passed**.
- Complete Workbench API suite: **88 passed**; Ruff lint and format: **PASS**.
- Workbench focused ESLint, TypeScript, and production build: **PASS**;
  `/matter` and `/knowledge` are static routes.
- Zero-dependency headless browser smoke: **1 passed**. It proved Matter-bound
  partition/primary-CourtCase prebinding, exact record resolution, default-unsafe
  promotion, immediate queue update, review, and persisted history; it rejected
  unscoped Matter discovery, cross-Matter requests, and Graphiti calls.
- Operator Matter/CourtCase creation dialogs: focused ESLint and TypeScript
  **PASS**; production build **PASS**, 15/15 static pages.
- Migration static validation and rollback-only PostgreSQL 18.4 execution:
  **PASS**, zero net writes against the isolated prerequisite fixture.
- Real repository integration on PostgreSQL 18.4: source resolution, promotion,
  retry dedupe, listing, exact custody detail (including a member H1 whose digest
  differs from the container source), foreign-Matter denial, reviewer decision,
  persisted review-history readback, and both atomic audit ledger writes **PASS**
  inside an outer rollback with zero net writes.

## Activation / rollback

- No migration persisted and no shared/deployed database, Coolify, deploy,
  push, or live-service mutation occurred. The isolated scratch server is
  stopped and retained under `to_be_deleted/` for owner-only deletion.
- Do not deploy the server/Workbench routes until migration 0030 has an approved
  application order after 0026–0029 and a live rollback rehearsal.
- Before activation, rollback is omitting or reverting the reviewed release commit.
  After promotion rows exist, preserve the append-only ledger; disable
  the route and supersede additively rather than dropping provenance.
