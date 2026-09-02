# Deduplicated Audit Gap Register — 2026-08-26


> _Recovery note: this file was lost (never committed) after being authored in a Codex CLI session on 2026-08-26/27. Reconstructed 2026-09-02 by Claude Code · Sonnet (recovery lane C) from the session's own `apply_patch` tool-call history in `C:\Users\matts\.codex\sessions\2026\08\`, per the method in `RECOVERY-NOTE.md`. 9 of 10 accepted `apply_patch` hunks located and applied cleanly. One gap: a `## Resolution log` section (with three dated resolution entries) existed in the live document by 2026-08-26T21:53Z but its creation is not present in the scanned 2026-08-25/26/27 session transcripts (created via a mechanism other than a captured `apply_patch` call — see gap note at the end of this file)._

This register converts the repository and read-only live/parity audit into dependency-ordered,
testable work. Severity reflects the controlled-replay product: a silent authority or horizon leak
is critical even when it merely makes an agent appear smarter.

Live observations are dated 2026-08-26 and are not substitutes for R14 attestation artifacts.

> **Current-target override — 2026-08-27 (D-091/D-092):** findings about database `ai`, role
> `ai`, role `agno_app`, and their applied schemas remain accurate dated legacy observations. They
> are no longer the forward cutover target. R00/R01/R14 must build and attest the consolidated
> baseline in fresh database `platform`, with `platform_admin`, `platform_runtime`, and narrow
> capability roles; legacy `ai` remains untouched through preservation review. Migration 0036 is
> held and must never be applied to `ai`. Canonical content has no ingestion/query redaction state;
> redaction is only an explicit derived court-export operation.

| ID | Severity | Lanes | Gap and evidence | Acceptance gate |
|---|---|---|---|---|
| GAP-001 | Critical | R00/R14 | Current truth conflicts on Graphiti/Surreal and one-case/Matter architecture (`AGENTS.md:83,96-106`; `docs/PROJECT_CANON.md:95-105,357,427-442,708-716`; `docs/DECISION_LOG.md:28-31`). ADR index still marks superseded choices accepted (`docs/adr/README.md:54-60,72`). | One successor ADR chain and current-truth set; automated contradiction scan passes; R00 owner sign-off. |
| GAP-002 | Critical | R02/R04/R13 | Every inspected active evidence-intake path starts custody (`server/ingest/service.py:302-320`; `server/evidence/workflows.py:621-676,733-740`; `server/temporal/activities.py:149-182`), and `ingest_artifact()` writes `evidence.*` immediately (`server/evidence/custody.py:277-328`). The context-chat CLI is a separate context-first path and does not cure the evidence-intake boundary (`scripts/ingest_context_chat.py:122-155`; `server/analysis/context_chat_ingest.py:593-650`). Current truth also still describes custody before parse (`docs/PROJECT_CANON.md:81-83`). | Failed parse leaves zero evidence/custody writes; context receipt is durable; owner-selected promotion is the only custody entry; current-truth documentation describes context-first intake. |
| GAP-003 | Critical | R03/R04/R14 | Promotion trusts ingest-time H1 and never independently proves normalized H2/full ordered generation/H3 (`server/case_management/repository.py:643-659,793-895`; `sql/0030_matter_case_foundation.sql:309-332`). Precise D-076 H3 tag has no production writer. | Atomic promotion rehashes original, recomputes selected H2 and full generation membership/H3, records exact tags/revisions, and fails closed on every mismatch. |
| GAP-004 | Critical | R00/R01/R04/R07/R13/R14 | Owner correction: Agno is a replaceable orchestration/runtime adapter and owns no evidence, horizon, memory, provider, HITL, admin or canonical truth (`docs/PROJECT_CANON.md:62-68,371-388`). Agents nevertheless receive Agno database tools alongside the approval-gated tool (`server/agents/providers.py:147-192`; `server/agents/factory.py:26,90,165,195`), and the installed Agno 2.8.7 provider defaults to write-enabled operations (`.venv/Lib/site-packages/agno/context/database/provider.py:36-53,109-115,130-140,173-182`). | Agno has no independent authority-bearing writer; `update_database` is absent or denied for non-approved agents; all writes cross platform-owned governed contracts; approval record is mandatory and transaction-bound; denial/approval integration tests pass; dependency-default evidence is revalidated on upgrades. |
| GAP-005 | Critical | R04/R05/R07/R09 | The SQL trigger queues every normalized chunk (`sql/0026_realization_event.sql:519-554`). The projector deactivates unapproved message routes through `source_available_from()` (`sql/0026_realization_event.sql:316-333`; `server/evidence/vector_projection.py:174-179`), but it does not enforce owner promotion/custody eligibility and otherwise stamps active (`server/evidence/vector_projection.py:188-215`). | One PG eligibility predicate gates outbox and projector; revoked/superseded material deactivates; object carries promotion/custody revision and exact locator. |
| GAP-006 | Critical | R05/R11/R14 | Weaviate REST/gRPC is anonymously exposed (`deploy/data-weaviate-native-v1.yaml:9-16`; `deploy/data-weaviate.yaml:16-30`) and client auth/TLS is optional (`server/core/session.py:115-138`), bypassing API horizon controls. | Anonymous direct REST/gRPC read/write denied; service identities and read/write roles enforced; direct-store future-fact canary is inaccessible. |
| GAP-007 | Critical | R06/R07/R09/R13 | Semantica is a candidate-only local proof (`server/analysis/semantica_worker.py:1-8,120-159`; `server/analysis/semantica_wiring.py:26-33,133-160`); no governed candidate-to-fact runner or source-anchored Neo4j projector/receipt exists. | Temporal extraction runner, governed review transition, node/edge-level source anchors, supersession/retraction and PG projection receipts pass integration tests. |
| GAP-008 | Critical | R00/R06/R09/R11/R14 | Retired Graphiti remains writable and directly tailnet-exposed; the tracked manifest alone does not establish public-internet exposure (`server/agents/providers.py:194-212`; `server/analysis/context_chat_ingest.py:320-357,532-562`; `deploy/data-graphiti.yaml:90-118`). Live exec still sets `GRAPHITI_MCP_URL` (read-only Coolify probe, 2026-08-26). | Approved retirement/cutover removes Graphiti MCP from the agent roster and its sink/outbox producer, unsets the live URL, and proves zero callers/pending jobs through a controlled restart; the direct port is denied or the application is retired. |
| GAP-009 | Critical | R01/R05/R06/R08/R09/R10/R14 | No universal PG `projection_receipt`/`aggregation_manifest` exists; each proof uses local markers/files. Required contract is `RECONCILIATION-DOMAIN-WORKSTREAMS.md:202-212`. | R09 independently reconciles every R04–R08 manifest by count/membership/content hash/version and blocks Surreal on mismatch/staleness/orphan. |
| GAP-010 | Critical | R09/R10/R13/R14 | Surreal path is synthetic/disposable (`deploy/compose.surreal-phase1.yaml:1-4,48-74`; runner `:37-60`) and does not consume R09 or return PG receipts. | Production schema/projector consumes only authorized R09 manifest; rebuild, revoke, supersede, quarantine and receipt parity pass live. |
| GAP-011 | Critical | R10/R11/R12/R13/R14 | PG derivation writes no agent beliefs/conclusions and `vw_walk_delta` is not a paired run comparison (`server/evidence/derivation.py:220-365`; `sql/0027_walk_ledger.sql:381-396`). | Surreal executes bound as-lived and hindsight walks, seals/restarts correctly, emits cited paired delta manifest, and Workbench/legal consumer acknowledges it. |
| GAP-012 | Critical | R01/R04/R09/R11/R13/R14 | Dated legacy probe: exec configuration used PG superuser `ai`, not `agno_app` (read-only Coolify/PG probe, 2026-08-26), contradicting `docs/HANDOFF-2026-08-24-n8n-pipeline-golive.md:22`. D-091 now requires a fresh `platform` database and `platform_runtime`; neither legacy role is the forward runtime target. | Fresh `platform` baseline reproducibly creates `platform_admin`, `platform_runtime`, and narrow capability roles; runtime operations pass while DDL/role/admin/cross-walk operations fail under integration transaction; no writer targets legacy `ai`. |
| GAP-013 | High | R00/R12/R14 | Public APIs and writers still create Matter/CourtCase objects despite D-072 (`server/api/case_management_routes.py:62-82`; `server/case_management/repository.py:514-624`). | Creation routes disabled/removed after consumer census; compatibility rows do not proliferate; one-case invariant test passes. |
| GAP-014 | High | R00/R01/R14 | Numbered migrations cannot bootstrap custody and legacy `agno_app` was created out of band (`sql/README.md:61-147`; `sql/0019_reconcile_evidence_hash.sql:23-33,90-119`; `sql/0033_chunk_classification_drafts.sql:45`). D-091 rejects replaying this history blindly into the replacement application. | A reviewed consolidated baseline bootstraps fresh database `platform`, every required schema, and `platform_admin`/`platform_runtime`/capability roles; its manifest matches the approved target. Legacy `ai` remains unchanged and 0036 cannot target it. |
| GAP-015 | High | R01/R04/R14 | Latest tracked handoff says immutability is OFF; migration 0031 permits evidence/working mutation unless `app.evidence_live=on` (`docs/HANDOFF-2026-08-24-ingest-testing.md:14-23`; `sql/0031_dev_mode_immutability_gate.sql:40-113`). | Production boot fails unless enforcing flag and trigger census are correct; prohibited UPDATE/DELETE tests fail under runtime role. |
| GAP-016 | High | R01/R02/R13/R14 | HTTP ingest returns 202 but schedules only an in-process asyncio task (`server/api/ingest_routes.py:85-159`) with no startup recovery consumer. | Temporal/outbox/lease dispatch survives crash-after-202 and resumes or terminally reconciles the same idempotency identity. |
| GAP-017 | High | R02/R04/R13/R14 | Temporal ChatTranscript is inert to callers and encodes custody→parse→store; required separate hashing Activities are absent (`server/temporal/workflows.py:2-18,172-304`; `server/temporal/worker.py:47-74`). | Reference-only Activity contracts for H1, H2/H3, promotion verification and reverification execute durably with exact retry/idempotency proofs. |
| GAP-018 | High | R02/R03/R07/R11/R13/R14 | Live n8n is healthy but has zero workflows (authenticated read-only API probe, 2026-08-26); staged workflows remain unimported (`docs/HANDOFF-2026-08-24-n8n-pipeline-golive.md:36-45`). | Approved workflows imported/activated with authenticated webhooks; 10-row smoke shows n8n→Temporal→PG receipts and safe purge. |
| GAP-019 | High | R00/R01/R05/R06/R10/R12/R13/R14 | Many Coolify Watch Paths still reference pre-move `compose.*` names while active manifests are under `deploy/` (read-only Coolify probe, 2026-08-26); app `git_commit_sha` values are `HEAD`, not immutable SHAs. | Per-app checker proves branch, manifest path, watch paths, rendered config hash and finished deployment SHA against intended remote commit. |
| GAP-020 | High | R05/R09/R11/R14 | Both Weaviate tiers are live, but exec's `NATIVE_EVIDENCE_ENABLED` value is descriptive text and evaluates false (`server/core/native_evidence_runtime.py:131-134`; `deploy/exec.yaml:116-124`; live probe 2026-08-26). | Exact schema/object/backfill/reconciliation/canary evidence passes; approved flag cutover and rollback are observed; legacy caller telemetry is zero. |
| GAP-021 | High | R00-R14 | CI runs only unit/default pytest. Two files carry the integration marker, but the live ingest test is opt-in and the schema-documentation check is not a live system proof (`.github/workflows/validate.yml:41-48`; `tests/integration/test_ingest_scratch_live.py:21-30`; `tests/test_schema_docs_current.py:19-21`). | Required integration job provisions scratch services, fails when all live tests skip, and publishes custody/horizon/store/walk/live receipts. |
| GAP-022 | High | R04/R12 | Approval leaves `safe_for_legal_use` and `is_authenticated` false, with no other writer found (`server/case_management/repository.py:939-989`; required view/constraint `sql/bootstrap/schema_baseline.sql:3470,4205`). | Explicit governed authentication/legal-safety transition, actor/reason/source proof and revocation path produce court-safe view rows only when complete. |
| GAP-023 | High | R02/R04/R12/R14 | Workbench “promote” calls `/v1/evidence/import`, the custody-first legacy workflow (`workbench/api/app/service/promote.py:1-15,70-143`; `server/api/evidence_routes.py:63-96`). | UI verb maps only to owner selection plus R04 promotion verification; context import and evidence promotion are visibly distinct; E2E proves no early custody. |
| GAP-024 | High | R05/R13/R14 | Weaviate boot failure permanently removes knowledge from built agents; reconnect does not rewire them (`server/api/main.py:269-281,314-322,430-439`). | Boot-down→reconnect test proves retrieval restoration without manual restart, or readiness fails closed until rebuild/restart completes. |
| GAP-025 | High | R02/R13 | Temporal activity retries and store internal retries multiply up to 16 DB transactions (`server/temporal/workflows.py:111-116,256-267`; `server/evidence/store.py:85-89,206-225`). | One retry owner; transient-failure test asserts exact attempt/backoff budget and idempotent row counts. |
| GAP-026 | High | R01/R08/R09/R14 | PostGIS creation can fail and continue (`sql/0001_init_extensions.sql:25-39`; `sql/0004_custom_types.sql:67-75`), while no governed geo source/generation/outbox/receipt lifecycle exists. | Required extension health fails closed; raw/normalized geo generations retain CRS/time/provenance and return R09-compatible receipts. |
| GAP-027 | High | R01/R11/R14 | Pass roles are not bound by tracked runtime code; `pass_reader` can select every run and no per-agent RLS exists (`sql/0029_pass_grants.sql:20-27,95-99,145-153`). Live PG has RLS on 0/143 audited base tables (2026-08-26). | Separate runtime pools/roles bind actor+walk claims; cross-walk/hindsight reads are denied and canary tests pass. |
| GAP-028 | Medium/High | R00/R12/R14 | Live exec has `RUNTIME_ENV=dev`; dependency skew only logs and continues (`deploy/exec.yaml:76`; `server/api/main.py:68,209-243`). AgentOS uses `authorization=False` (`server/api/main.py:424-459`); protected-route denial was not live-proven. | Production environment fails on incompatible deps/config; unauthenticated protected routes deny, bearer succeeds, and cold restart smoke passes. |
| GAP-029 | Medium | R11/R13 | **Corrected owner model:** the capability already binds the exact `walk_run_id`/step/checkpoint tuple and the read-only endpoint resolves that tuple against current PG walk/checkpoint state on every request. Repeated reads during the same valid step are allowed; a one-use nonce ledger is unnecessary. The remaining gap is explicit lifecycle proof that advance, seal, terminal failure, projection mismatch, and a new `rewalk_of` identity make the old tuple unusable. | Integration tests prove the current tuple reads only its own walk; advance/seal/terminal/mismatch reject the old tuple; a rewalk has a new run identity and cannot read through its predecessor capability. No per-request nonce table or single-use state. |
| GAP-030 | Medium | R12/R13 | Async Workbench routes call synchronous HTTP/storage and `time.sleep`, blocking the event loop (`workbench/api/app/runtime/promote.py:17-29`; `workbench/api/app/service/promote.py:71-179`; `workbench/api/app/service/runs.py:89-105`). | Async clients or bounded thread offload; concurrent slow-operation latency test meets budget. |
| GAP-031 | High | R07/R13/R14 | The registered Temporal classification workflow accepts arbitrary signal text; only exact `abort` stops it. Any other value releases the gate and appends every `needs_review` item to the persistence payload without item-level adjudication (`server/temporal/classification_workflow.py:81-84,131-164`; registration `server/temporal/worker.py:61-69`). The staged persistence workflow rejects non-accepted gate outcomes (`docs/research/integration-audit-2026-08-24/composed/wf-persist-results.json:71-74`), so the composed path is fail-open at the signal boundary and cannot express valid partial adjudication. | Signal contract is an exact normalized enum allowlist; each item records decision ID, actor, decision, reason and source; only individually approved/corrected items become accepted while untouched items remain pending; invalid, mixed, partial and replayed-signal tests prove no unintended write and deterministic resume. |
| GAP-032 | **Critical** | R02/R04/R12/R14 | D-082 permanently excludes AI chats from evidence, but Workbench chat-export promotion dispatches to `/v1/evidence/import` (`workbench/api/app/service/promote.py:122-158`), which starts the evidence workflow (`server/api/evidence_routes.py:63-98`) and custody/evidence persistence (`server/evidence/workflows.py:588-624`). | AI-chat source types are denied at Workbench, API, workflow and DB/promotion boundaries; a production negative test submits a chat export through every reachable route and proves zero custody/evidence/fact-support/citation rows plus an attributable denial receipt. |
| GAP-033 | High | R00/R02/R07/R09/R14 | D-083 requires typed legal-issue/concern, observation, strategy and context-created-work outputs, but the current physical proposal and runtime cover only entity/fact/event candidates and generic assets/products. `working.candidate_fact` and `working.investigation_event` also carry misleading authority names, and no authoritative claim-chart table/read model exists. | Reviewed physical contracts add the missing typed lifecycles and exact chat anchors; `candidate_fact` reconciles to append-only `claim_candidate`; the lead/concern register is distinct from event/fact authority; the claim chart is a derived read model; created-work adoption into R12 is explicit and never evidence promotion. |
| GAP-034 | High | R01/R02/R07/R09/R14 | D-084/D-085 and ADR-0060 require a maintained Timesketch fork, immutable PG timeline projection generations, governed individual/bulk context curation, and amendment-candidate re-review for approved entries. No fork, projector, curation ledger/API, reconciliation receipts, deployment, or live round-trip proof currently exists. | TS-00–TS-08 in `TIMESKETCH-FORK-CURATION-HANDOFF.md` pass: fork baseline; PG generation/member/receipt contracts; any-context and governed visibility; itemized/atomic bulk edits; approved-entry immutability and amendment successor flow; R09 rebuild/reconciliation; Coolify deployment; mandatory live negative/replay/rollback evidence. |

## Activation blockers

No production cutover should proceed while any of GAP-001 through GAP-012 is open. Every High or
Medium/High finding, including GAP-031 through GAP-034, is mandatory before its owning lane can hand off to R14.
Medium findings require an explicit acceptance, mitigation or scheduled completion; they are not
silently waived.

## Evidence limitations

- Live probes were read-only; no deploy, restart, workflow execution, credential change or database
  mutation was performed.
- Live rendered compose/config hashes and container files were not inspected.
- Neo4j authenticated queries, Weaviate object counts, Temporal gRPC execution and legacy Surreal
  process state remain unverified.
- CCC used a SQLite-backed index and was incomplete; no per-file failure-resolution manifest proves
  full semantic-index coverage or final-artifact freshness.
- The handoff-required DuckDB repository catalog/dependency-analysis step is not evidenced; product
  `pg_duckdb` inspection is not a substitute for that discovery artifact.
- Dated handoffs support only the state recorded on their date unless independently reprobed above.

---

## Recovery gap note (2026-09-02, lane C)

A `## Resolution log` section existed in the live document between 2026-08-26T21:53:18Z and
2026-08-26T22:09:27Z (three accepted `apply_patch` calls reference it as pre-existing context), but
no `apply_patch` call creating that section's header or introductory sentence appears anywhere in
the scanned `C:\Users\matts\.codex\sessions\2026\08\{25,26,27}\` rollout transcripts. This
matches the same "content produced by a mechanism other than a captured `apply_patch` call" pattern
the original `RECOVERY-NOTE.md` documented for `SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html`.

The following three fragments are recovered **verbatim** from the `+` lines of the hunks that
referenced this section, in chronological order. Their exact position/spacing relative to each other
and to any other resolution-log content is **not** independently confirmed — only the ordering implied
by each hunk's own context lines. They are not spliced into the body above because the section's
header and full original structure could not be located.

1. Header and intro sentence (recovered as unchanged **context** lines in a 2026-08-26T22:04:09Z hunk,
   confirming they already existed by that point, but their own creation call is not in scope):
   > `## Resolution log`
   >
   > `Findings below are corrected in place at their original row (audit history is never edited) — this section records what changed and where the current implementation stands.`

2. First known resolution-log entry added (2026-08-26T21:53:56Z, call `call_Nv2f8PEQD9uhYm7QRJvteSR2` —
   the hunk that inserts it was itself unlocatable/FAILED against this reconstruction, but its `+` text
   is intact):
   > **2026-08-26 follow-up — Workbench surface shipped and proven:** commit `1d7a72a` reached both
   > `main` and `workbench/sprint`; Coolify deployment `spqradjsvl8skt1o9c2w5zqf` finished and the
   > replacement Workbench container is healthy. An authenticated live upload was classified
   > `chat_export`; its live `/api/promote/{id}` call returned the permanent D-082 failure with
   > `No promotion attempted; no network call made`. Live PG counts on `evidence.source`,
   > `evidence.evidence_hash`, `evidence.custody_event`, and `evidence.ingest_run` remained `0 → 0`.
   > The Workbench and platform REST negative surfaces are closed. GAP-032 remains partial only for
   > the positive real `sms-xml` live proof and the required full live integration run.
   >
   > (Context shows this text was appended directly after an existing sentence referencing
   > `[WP-C01-IMPLEMENTATION-STATUS.md]("knowledge-workbench unblock" section)` — that base sentence's
   > own origin is also not in the scanned transcripts.)

3. GAP-029 model-correction entry (2026-08-26T22:04:09Z, call `call_gFThHsQGhA1wVLBfJSb3pIHU`, hunk 2 —
   FAILED to locate in this reconstruction because its anchor text did not yet exist here):
   > **GAP-029 model correction** (owner, 2026-08-26): the audit's single-use nonce requirement was
   > overdesign for a read-only, exact-walk-step capability. A candidate in-memory nonce/TTL patch was
   > not committed or deployed; it was preserved under
   > `to_be_deleted/gap029-nonce-experiment-20260826/`. The active code remains the simpler signed
   > run/step/checkpoint binding plus the canonical PG lifecycle check. Remaining work is lifecycle
   > integration proof, not another persistence ledger.

4. GAP-004 partial-resolution entry (2026-08-26T22:09:27Z, call `call_9Isvg0ewFWoc4QgaNSzF5DAp` —
   FAILED for the same reason; its own hunk's context confirms it was inserted immediately before the
   GAP-029 entry above, i.e. entry order in the section was GAP-004 then GAP-029):
   > **GAP-004 partial resolution** (2026-08-26, Claude Code · Sonnet 5; root deployment
   > verification): commit `a358fd2` makes the ordinary-agent Agno
   > `DatabaseContextProvider` explicitly read-only (`write=False`) while preserving
   > `query_database`. Coolify deployment `v7lgr3vk4e9l8piz5ybz4fvv` finished for live exec-tier
   > application `rz41wqhpjfh1rj796ixvjhfs`; the replacement `agentos-api` container returned HTTP
   > 200 from `/health`, ran the pinned system `agno==2.8.7`, and its deployed provider exposed only
   > `query_database` with no `update_database`. Ten targeted tests plus Ruff lint/format and mypy
   > passed before deployment. The bypass is closed; the full gap remains partial until a live
   > approval-record/transaction test and the separate gateway-registry writer census are recorded.
   > Full receipt: [`GAP-004-IMPLEMENTATION-STATUS.md`](GAP-004-IMPLEMENTATION-STATUS.md).

The GAP-029 **table row** itself (row ID `GAP-029` in the register above) was successfully recovered
and reflects the corrected owner model — only this narrative resolution-log entry is the gap.
