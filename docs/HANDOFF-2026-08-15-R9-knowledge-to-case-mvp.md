# HANDOFF — R9 Knowledge to Case-Management MVP (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: PARTIAL — local foundation slice built; live activation still held
BUILD_STATUS: PASS (local R9 slice only; deployment/live proof UNKNOWN)

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Branch | `main` equals `origin/main`; activation preflight is pushed as `6c37548` |
| Knowledge UI | `/knowledge` exists in the working tree and is included in the Next.js static build |
| Knowledge isolation | Workbench search always sends a non-empty `case_id` dict prefilter before Weaviate ranking; default is `primary` |
| Memory separation | Graphiti facts/nodes/episodes render in a separately labeled read-only memory pane, never as canonical evidence |
| Matter foundation | ADR-0055 / D-060 accepted; migration 0030, neutral spine APIs, Workbench proxies, `/matter`, and governed Add-to-case are built locally |
| Backend validation | Root suite: 750 passed / 24 skipped; Workbench API: 92 passed; full Ruff and server mypy pass |
| Frontend validation | Full ESLint and TypeScript pass; Next.js production build passes with 15 static pages |
| Migration validation | Static contract and 11 migration tests pass. PostgreSQL 18.4 scratch execution of 0030 plus custody/promotion negative cases passed in rollback with zero net writes |
| Workbench auth | Mandatory fail-closed `WORKBENCH_API_KEY`; only exact `/health` is public. Key is not provisioned or deployed |
| Court readiness | Read-only Matter/item endpoint and dialog distinguish actual export-view membership from stricter supplemental gates; no release mutation |
| Deployment | UNKNOWN — no live Workbench, Weaviate, Graphiti, migration, or Coolify mutation was performed |

## Historical baseline findings / work done

> This section records the state before the Matter addendum. Current state is
> the verified-live table and the newest addendum below.

- Added the missing Workbench Knowledge page and browser. It supports case/lane-scoped canonical search, content catalog browsing, and explicitly separate Graphiti memory reads.
- Strengthened `workbench/api/app/service/knowledge.py`: `case_id` is mandatory, blank values fail closed, and the Weaviate-compatible filter is always a dictionary containing the case key.
- Added an explicit Graphiti group parameter for read operations. This is namespace selection only; authorization remains unresolved and cannot be delegated to `group_id`.
- The repository has no canonical `matter` or `case` table. Textual knowledge partitions use `case_id='primary'`, while `analysis.evidence_item`, `analysis.evidence_task`, `analysis.export_package`, and `reference.legal_issue` use UUID `case_id` columns. Directly converting `primary` into a UUID would be unsafe.
- Existing case-management building blocks are substantial: `analysis.evidence_item`, `analysis.timeline_event`, `analysis.evidence_task`, `reference.legal_issue`, `working.entity/person`, `working.artifact_registry`, review tables, and court-export views/packages.
- The next vertical slice should turn a case-prefiltered Knowledge hit into a provenance-preserving, review-gated draft evidence item. Matter identity must land first so the promotion cannot deepen current ID drift.
- Documentation now records local Knowledge verification, correct Workbench deployment paths, Weaviate terminology, Semantica VIP status, and Wave-1’s pushed/unapplied state.

## UNRESOLVED (current, mandatory)

- Full-baseline execution proof — the isolated minimal-schema PostgreSQL run
  passed; replay against a disposable full baseline remains a release gate
  after migrations 0026–0029 are resolved.
- Live service proof — deployed Weaviate case prefiltering, Graphiti namespace
  behavior, and the Workbench-to-spine promotion path remain unexercised.
- Graphiti authorization — the server allowlist is a safe interim boundary, not
  authenticated per-Matter/per-Run grants.
- Release ordering — 0030 is held and cannot leapfrog held migrations 0026–0029.
- Commit custody — Wave 1, Workbench/Matter, and documentation/design were
  partitioned and pushed as `e503bfa`, `a52ff13`, and `c0fac88`.
- Horizon execution — Wave-1 replay/proposal-contamination defects block product use; reserve delta contracts but do not expose unsafe execution.

## Pending owner decisions

The current review packet with recommended defaults and consequences is
[`PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md`](PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md).
It is intentionally not an ADR and grants no schema/apply/deployment authority.

> **Resolved 2026-08-15:** the owner approved the recommended foundation-first
> path, separate Matter/CourtCase identities, one authored timeline, and delayed
> Horizon execution. ADR-0055 / D-060 is authoritative. The original decision
> cards remain below as the review trail.

- Adopt Matter Workspace Foundation next — **WHAT:** build matter/court-case identity plus Knowledge-to-Evidence promotion · **WHY:** every case-management screen needs stable scope and provenance · **APPROACHES:** foundation-first, evidence-only screen, or full dashboard · **SHORTCOMINGS:** foundation-first delays richer visuals but avoids disconnected records. **Recommendation:** foundation-first.
- Model both matter and court case — **WHAT:** an enduring matter owns one or more proceedings · **WHY:** docket/court identity must not become the universal knowledge partition · **APPROACHES:** two entities or one combined case table · **SHORTCOMINGS:** two entities add initial schema/API work. **Recommendation:** two entities.
- Preserve one authored timeline — **WHAT:** keep `analysis.timeline_event` canonical and make legal timeline a projection · **WHY:** two authored timelines will drift · **APPROACHES:** canonical plus projection or two writable tables · **SHORTCOMINGS:** canonical-plus-projection needs adapters. **Recommendation:** one authored timeline.
- Delay Horizon UI execution — **WHAT:** reserve run/delta references without enabling unsafe Wave-1 execution · **WHY:** current run replay and proposal isolation are not proven · **APPROACHES:** delay, expose experimental, or ship immediately · **SHORTCOMINGS:** the first case-management slice omits the signature delta UI. **Recommendation:** delay execution only.

## Historical next steps (completed locally unless stated)

1. Record the owner’s matter/court-case decision in an ADR.
2. Freeze neutral `Matter`, `CourtCase`, `EvidenceItem`, `SourcePointer`, and `ReviewState` contracts.
3. Add a new numbered migration; never edit applied migrations.
4. Add neutral Matter/Evidence APIs with cross-matter denial and idempotency.
5. Add Matter Home and “Add to case” actions on Knowledge results.
6. Prove provenance, default-unsafe review state, retry dedupe, and cross-matter isolation.
7. Add People/Timeline only after the foundation slice passes.
8. Repair the separate Classification Lab lint/API-prefix lane before claiming a clean Workbench gate.

Remaining activation order: owner review → resolve/apply 0026–0029 → execute the
0030 rollback-only PostgreSQL proof → approve/apply 0030 → deploy and exercise
the live Workbench/Weaviate/Graphiti path. Horizon execution stays held.

## Owner working-style contract

- Structured replies: answer first, short sections, clear decisions.
- Confirm architecture/schema changes; never hard-delete; quarantine only after exact-target approval.
- Byline every artifact and verify before claiming completion.

## Addendum — Knowledge safety and multi-base repair (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

STATUS remains **PARTIAL** and BUILD_STATUS remains **FAIL** for the complete
case-management objective. The following working-tree repair is verified
locally but is not deployed or live-proven.

### Completed in this addendum

- Replaced the retired `domain` request contract with the current structural
  `lane` contract.
- Resolved each registered AgentOS Knowledge base through its deterministic
  `knowledge_id`; an all-lane search now queries the five allowed bases
  independently with the mandatory `case_id` dictionary prefilter applied
  before each Weaviate ranking operation.
- Made the Sources catalog require both `case_id` and one structural lane.
  Because AgentOS cannot metadata-filter its content catalog, the trusted
  Workbench service scans that one base and returns only matching-case rows;
  rows without a matching case key fail closed.
- Added server-side bounds/enums for query, case, lane, result limits,
  pagination, and Graphiti search kind.
- Added a temporary server-side Graphiti namespace allowlist, defaulting to
  `platform`; the browser can no longer submit an arbitrary group ID.
- Cleared Graphiti results before requests and after failures, bound displayed
  namespace provenance to the successful request, and excluded invalidated
  facts from the default current-facts view.
- Added accessible tab/panel/loading semantics to the Knowledge browser.

### Fresh validation evidence

- Workbench API focused Ruff over all touched backend/test files: **PASS**.
- Workbench API complete suite: **64 passed, 1 third-party deprecation warning**.
- Knowledge frontend focused ESLint: **PASS**.
- Workbench TypeScript `--noEmit --incremental false`: **PASS**.
- Workbench Next.js production build: **PASS**, 14 static routes including
  `/knowledge`.

### Still unresolved

- The deterministic Knowledge-ID catalog is an Agno anti-corruption adapter;
  replace it with a neutral spine-owned registry endpoint during runtime
  decoupling.
- Workbench still lacks authenticated Matter/Run grants. The Graphiti
  allowlist is a safe temporary operator boundary, not the final authorization
  model.
- Source rows lacking current `case_id` metadata are intentionally invisible
  until reindexed or migrated.
- No deployed AgentOS/Weaviate/Graphiti endpoint was exercised in this
  addendum.
- Matter/CourtCase identity, provenance resolution, idempotent
  Knowledge-to-Evidence promotion, review gating, and cross-matter denial
  remain the next product slice.
- Full Workbench lint remains red in the separate Classification Lab lane;
  this addendum makes no broader lint claim.

## Addendum — Matter foundation and governed promotion (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

### Built locally

- Accepted ADR-0055 / D-060: an enduring Matter owns one or more CourtCase
  proceedings; text Knowledge partitions remain separate and map explicitly.
- Added held, unapplied migration `sql/0030_matter_case_foundation.sql` with
  `analysis.matter`, `analysis.court_case`,
  `analysis.matter_knowledge_partition`, paired nullable Matter/CourtCase scope
  on legacy evidence items, and an append-only idempotent promotion ledger.
- Added framework-neutral spine Matter/Evidence contracts and seven `/v1`
  routes. The API resolves a selected normalized record through its H1 custody
  hash, rejects cross-matter/partition access, writes promotion + audit in one
  transaction, and returns an existing draft on a stable retry.
- Added matching Workbench `/api` proxy routes, a static-export-compatible
  `/matter?matter_id=<UUID>` workspace, and a Knowledge “Add to case” flow.
  Promotion is exposed only for custody-backed evidence-lane hits, requires an
  explicit normalized-record and CourtCase selection, and binds the exact
  selected record text rather than treating a ranked chunk as evidence.
- Added three self-contained HTML Workbench design directions under
  `workbench/design-mockups/`, plus cross-review reports under
  `docs/design/workbench-mockups-2026-08-15/`.

### Fresh validation evidence

- Full Python unit suite: **714 passed, 24 skipped**.
- Full `server`/`tests` Ruff lint: **PASS**.
- Full `server` mypy: **PASS**.
- Focused spine API + migration tests: **25 passed**.
- Complete Workbench API suite: **74 passed**; full Workbench API Ruff lint and
  format gates: **PASS**.
- Migration static validator: **PASS**; no database connection or apply.
- Workbench full ESLint and TypeScript: **PASS** (including the separate
  Classification Lab cleanup).
- Workbench production build: **PASS**, 15 static pages including `/knowledge`
  and `/matter`.
- Full Ruff format: **PASS** after a mechanical-only format of the separate
  uncommitted `server/evidence/derivation.py` Wave-1 file; no logic changed.
- All three Workbench HTML variants received a final evaluator **PASS**;
  Variant 3 passed after one revision round.

### Activation status and remaining gates

- Migration 0030 is **HELD/UNAPPLIED** and must not leapfrog held migrations
  0026–0029.
- No migration was persisted or applied to a shared/deployed database; no
  deployment, Coolify, commit, or push action was performed.
- Live cross-service proof against deployed Postgres/Weaviate/Graphiti remains
  outstanding.
- Horizon execution remains deliberately unavailable until the R0/R2
  contamination and replay defects are resolved.

## Addendum — strengthened rollback-only proof harness (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

- Expanded `scripts/_matter_validate_0030.py` so an explicitly labeled clean
  scratch/development/staging database exercises a complete synthetic custody
  chain and governed promotion inside one transaction.
- The proof asserts default-unsafe review state, request-key dedupe,
  source-pointer dedupe, append-only enforcement, provenance mismatch denial,
  cross-matter partition denial, and post-rollback zero retention.
- Production and ambiguous targets remain rejected. A database already
  containing 0030 objects is also rejected.
- Fresh static evidence: focused Ruff lint/format PASS; migration tests **11
  passed**; static validator PASS; diff check PASS.
- Observed PostgreSQL proof: a new isolated PostgreSQL 18.4 cluster loaded
  `tests/fixtures/matter_0030_prerequisites.sql`; migration 0030 and every
  positive/negative promotion assertion passed inside rollback with zero net
  writes. The first run exposed and led to fixing an ambiguous JSON parameter
  cast in the harness.
- The server was stopped after validation. Its data directory remains
  quarantined at `to_be_deleted/matter-validation-pg/` for owner-only deletion.
- Honest limit: this was a purpose-built minimal prerequisite schema, not a full
  restored production baseline and not a deployed-service test.
- A separate clean scratch database ran the actual `server.case_management`
  repository and audit writer against the fixture+migration inside one outer
  transaction. Source resolution, first promotion, retry dedupe, evidence
  listing, and the atomic audit row all passed; rollback removed every fixture,
  migration, and data object.
- Closed the remaining operator-flow gap: `/matter` now provides forms to
  create a Matter (with an atomic default CourtCase/partition) and add further
  CourtCase proceedings, including explicit primary-proceeding selection.
  Focused ESLint and TypeScript passed; the production build passed all 15
  static pages.
- Converted the spine’s blocking SQLAlchemy route handlers from `async def` to
  synchronous FastAPI handlers so concurrent requests run in the framework’s
  worker threadpool rather than blocking the event loop. Matter scope changes
  now also retain a truthful loading state instead of briefly rendering blank.
- Full-bootstrap audit: the isolated stock PostgreSQL lacks pg_duckdb, PostGIS,
  and pgvector. A numbered-chain probe reached the already-documented canonical
  failure at 0008 (`evidence.source` is out-of-band), confirming that the chain
  is historical rather than a bootstrap. The probe was quarantined, not
  deleted. Release proof must use `schema_baseline.sql` in the custom extension
  image and then apply 0026–0030 in order.
- Safety-retired `scripts/_wave0_fresh_restore.py`: its historical implementation
  is preserved, but the executable entry point now refuses before reading
  credentials or connecting because it both replays a known-invalid chain and
  performs database drops. A regression test pins the refusal behavior.
- Added the missing human-review stage without inventing a second approval
  system. Promotion now opens an `analysis.review_task`; the Matter workspace
  can record an append-only `analysis.review_decision` as approved, rejected,
  needs changes/context, held, or escalated. Terminal review resolves the task;
  a second terminal decision returns 409. Review deliberately leaves
  `safe_for_legal_use=false` and `is_authenticated=false`; authentication and
  court-safe release remain separate future gates. The real PostgreSQL
  repository harness proved promotion → review → audit under rollback.

## Addendum — persisted reviewer history (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

- Added a Matter-scoped read side for canonical append-only evidence review
  decisions. The platform and Workbench endpoints return reviewer, decision,
  rationale, court-readiness classification, task reference, and decision time.
- Matter Workbench now exposes review history for every promoted evidence item,
  including after terminal review removes the active HITL action. Each dialog
  clears stale data before a request and after failure.
- The real PostgreSQL 18.4 repository probe proved promotion → review → history
  → audit inside one outer transaction; rollback left zero net writes. The
  isolated server was stopped afterward.
- Fresh broad gates: root Ruff + mypy **PASS**; root tests **716 passed / 24
  skipped**; Workbench API Ruff + format **PASS** and tests **76 passed**;
  frontend ESLint + TypeScript + production build **PASS** with 15 static pages.
- Activation status is unchanged: migration 0030 remains held/unapplied; no
  deploy, shared database mutation, commit, or push occurred.

## Addendum — Matter-bound Knowledge operator journey (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

- Closed the final fragmented local MVP workflow: `/matter` now embeds canonical
  Knowledge search with its explicit partition and primary CourtCase prebound.
  The operator no longer re-enters `case_id` or reselects a Matter/proceeding.
- Bound search starts in the evidence lane, pins each successful result set to
  its immutable partition/lane scope, and still requires custody metadata plus
  explicit exact normalized-record selection before promotion.
- A successful promotion immediately upserts the returned unsafe/HITL draft
  into the Matter evidence queue. Review and persisted history then complete in
  the same workspace.
- Graphiti tabs and requests are absent from the Matter-bound pane, with an
  explicit warning that belief memory is noncanonical agent state. Standalone
  `/knowledge` behavior remains intact.
- Added `workbench/web/smoke/matter-flow.smoke.test.mjs`, a zero-dependency
  headless Edge/Chrome CDP journey with strict same-origin API fixtures. Fresh
  result: **1 passed** for search → resolve → promote → review → history. It
  asserts no unscoped Matter discovery, cross-Matter request, or Graphiti call.
- Frontend ESLint, TypeScript, and production build remain **PASS** with 15
  static pages. The smoke's isolated profiles are quarantined under
  `to_be_deleted/` for owner-only cleanup.
- Local MVP code is now functionally complete. Release completion is still not
  claimed: migration ordering/full-baseline execution and deployed
  Postgres/Weaviate/Workbench proof remain outstanding and owner-held.
- A fresh local feasibility probe found no Windows Docker CLI, and WSL Podman
  could not start because its VHDX is media-write-protected. Therefore the
  required custom PG18 (`pg_duckdb` + PostGIS + pgvector) full-baseline rehearsal
  was not attempted through a substitute engine and no VPS/shared database was
  touched. Resume that gate only in a disposable instance of the canonical
  custom image; stock PostgreSQL is insufficient.

## Addendum — adversarial release hardening (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

- Adversarial review changed the release verdict from functionally complete to
  **NEEDS REVISION**, then closed the verified local blockers without activating
  the held migration or touching a shared service.
- Added mandatory fail-closed Workbench authentication. Exact `/health` is the
  only public path; all APIs, docs, and static UI require either Bearer
  `WORKBENCH_API_KEY` or HTTP Basic `owner:<key>`. An unset key returns `503`
  rather than silently exposing the privileged spine proxy. Caller-supplied
  audit identities are constrained to the authenticated single-owner model.
- Corrected idempotent promotion retries so an existing item remains a valid
  response after review; initial unsafe/HITL invariants are enforced only for a
  newly created draft. Added synchronous client mutexes for promotion and
  append-only review submission, stale-response guards, truthful legal-safety
  copy, and accessible error announcements.
- Matter-bound Knowledge now fails closed when zero or multiple partitions are
  present instead of silently choosing array element zero. Promotability also
  requires a non-empty retrieval ID and rejects explicit metadata whose
  partition disagrees with the successful search scope.
- Hardened provenance resolution to require H1, SHA-256, 32-byte digest, and
  `h1-rawbytes-v1`; quote filtering now occurs in SQL before the candidate
  limit. Migration 0030 now enforces the evidence lane and independently
  validates pointer fields, canonical pointer hash, hash algorithm/canon, and
  digest at the database boundary.
- Fresh broad gates: root Ruff/mypy **PASS**, root tests **717 passed / 24
  skipped**; Workbench API Ruff/format **PASS**, tests **85 passed**; frontend
  ESLint/TypeScript/build **PASS** with 15 static pages; browser journey **1
  passed**. The PostgreSQL 18 rollback-only repository proof, including the new
  non-evidence and tampered-pointer negative cases, passed with zero net writes;
  the scratch server was stopped and port 55439 reports no response.
- Added `docs/RELEASE-CUSTODY-2026-08-15.md` with exact commit partitions,
  shared-file hunk warnings, gates, and post-commit documentation custody.
- Release status remains **PARTIAL**: `WORKBENCH_API_KEY` is not provisioned,
  migrations 0026–0030 are unapplied, the canonical custom-image full-baseline
  rehearsal is outstanding, and no deliberate deployment or migration apply occurred.

## Addendum — exact evidence and custody inspection (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

- Added a framework-neutral, Matter-scoped read endpoint for one promoted
  evidence item. Its fail-closed join binds the item, promotion ledger,
  canonical normalized record, H1 custody hash, source, and optional file node;
  cross-Matter or internally inconsistent provenance returns 404.
- The response is an explicit public allowlist. Local paths, object-store keys,
  raw metadata, and unknown source-pointer fields are excluded. H1/member and
  container-source hashes remain independent rather than being falsely forced
  equal.
- Added persistent “Inspect provenance” to Matter evidence. Human review now
  fresh-loads and validates the exact detail; decision, rationale, and submit
  controls remain disabled on loading, error, stale identity, or provenance
  mismatch.
- The browser journey now proves that canonical content and H1 custody render
  before review and that exactly one Matter-scoped detail request occurs.
- Fresh broad gates: root Ruff/format/mypy **PASS**, root tests **721 passed / 24
  skipped**; Workbench API Ruff/format **PASS**, tests **88 passed**; frontend
  ESLint/TypeScript/build **PASS** with 15 static routes; Matter smoke **1
  passed**.
- The real PostgreSQL 18.4 repository proof exercised a file-node/member H1
  whose digest differs from its containing source SHA, plus foreign-Matter 404,
  inside rollback with zero net writes. The disposable server was stopped and
  port 55439 is closed.
- Status remains **PARTIAL**: this follow-on is committed/pushed as `be286a8` and undeployed;
  migrations 0026–0030 and live activation remain owner-held. People/Timeline
  remains design-only pending an explicit Matter association model.

## Addendum — read-only court-export readiness (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

- Added a Matter-scoped read endpoint and Workbench dialog for one promoted
  evidence item. The contract reports actual `analysis.vw_court_export`
  membership separately from `readiness_passed`, the stricter aggregate of
  content review, exact provenance, custody, authentication, confidence,
  hypothesis, redaction, sensitivity, and release checks.
- This slice is diagnostic only. It does not authenticate evidence, change
  confidence, apply redaction, mark material safe, or perform legal release.
  The UI labels the result as database status—not admissibility, satisfaction
  of court rules, or legal advice.
- Exact custody checks remain fail-closed and Matter-scoped. A verification
  event qualifies only when it is source-wide or matches the selected H1 and
  file node; a verified sibling member cannot verify the selected item.
- The legacy custody trigger rendered timestamps in the writer session's time
  zone. The read verifier reconstructs the exact legacy input over the complete
  modern civil-offset grid (105 candidates per event), making reads independent
  of the current session time zone. This is bounded MVP compatibility debt; a
  versioned canonical writer/verifier and large-chain benchmark remain future
  hardening.
- Adversarial review initially returned **NEEDS REVISION** for export-view
  conflation, sibling verification leakage, and timezone-dependent digest
  checking. All three were corrected; final bounded re-review returned **PASS**.
- Fresh broad gates: root Ruff/format/mypy **PASS**, root tests **743 passed / 24
  skipped**; Workbench API Ruff/format **PASS**, tests **92 passed**; frontend
  ESLint/TypeScript/build **PASS** with 15 static routes; Matter smoke **1
  passed**.
- PostgreSQL 18.4 rollback proof passed with zero net writes. It proves sibling
  isolation, actual view member/nonmember states, and identical readiness after
  switching the reader between UTC and America/New_York. The first attempt
  exposed a harness bind-literal bug; it was fixed and the proof rerun. The
  disposable server was stopped and port 55439 is closed.
- Status remains **PARTIAL** and undeployed. Migration ordering, full custom-image
  baseline rehearsal, key provisioning, and live service proof remain owner-held.
  The verified read-only slice is committed and pushed as `7b6aaf6`.

## Addendum — fail-closed activation preflight (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

- Added a read-only static/database/activation preflight that converts the remaining release
  assertions into itemized PASS/FAIL/BLOCKED output. It checks clean/pushed git
  state, migration custody/order, Workbench fail-closed auth wiring, credential
  separation, PostgreSQL 18 extensions, uniform migration state, and live
  Matter/Knowledge/Graphiti/Weaviate reads.
- Secrets and DSNs are accepted only through named environment variables and
  are never emitted. Missing inputs return `NOT READY`; the command never
  applies migrations or deploys services.
- Focused tests and static analysis pass locally. The activation scope remains
  intentionally unexecuted until the owner provisions credentials, approves the
  0026–0030 sequence, and provides the reviewed canonical/deployed targets.
- A deliberate negative database run against the quarantined stock PostgreSQL
  validator correctly rejected its missing canonical extensions, confirmed the
  five migrations uniformly absent, emitted no secrets, and left port 55439 closed.
- The preflight is committed/pushed as `6c37548`. Static scope then returned
  **READY** with every checkout/release-contract check passing from clean `main`.
