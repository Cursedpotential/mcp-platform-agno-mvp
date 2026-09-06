# Ingest-day board appendix — post-spec build state (Codex/n8n/OpenCode recall)

> _Byline: Claude Code · Sonnet (design-recall lane) · 2026-09-02_
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

Purpose: recover what actually got BUILT after
`docs/reviews/2026-08-25-schema-audit/TEMPORAL-N8N-WORKFLOW-AND-GAPS.md` ("Workflow A" /
`ContextIntakeWorkflow`), so tonight's ingest work extends reality instead of re-deriving a
design that has already been superseded. Method: direct repo reads (code, docs, git log),
plus one sub-agent's live DuckDB/sqlite query of `opencode.db`. A second sub-agent (Codex
rollout mining across `~/.codex/sessions/2026/08/{28,29,30}`) was still fanning out 7 of its
own background sub-agents on ~900MB of session JSONL when this doc was written and never
returned verbatim quotes — its scoping-only findings are folded into §D as corroboration, not
as primary evidence. Everything else below is read directly from the repository.

## Headline finding

**`ContextIntakeWorkflow` (the spec's 10-activity chain) was never built under that name.** A
repo-wide grep for the literal string matches exactly one file — the spec doc itself. It was
superseded, same day (2026-08-25), by a sibling design doc that was drafted but not committed
until today: `docs/reviews/2026-08-25-schema-audit/SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html`
(recovered into the repo by commit `9c213cc`, "recover D-072..D-081 + the three lost
2026-08-25 ruling docs from Codex rollouts"). That boundary doc defines a 23-canon-activity
`UniversalImportWorkflow`, and **that** is what got built between 2026-08-27 and 2026-09-01:
`modules/engine/uiw.UniversalImportWorkflow`, driven by a 26-`StageID` stage graph
(`modules/engine/stagegraph/stage.go`) — 23 canon activities plus 3 legacy replay-only
aliases kept solely so already-started workflow histories can still resume
(`hash_source_activity`, `hash_raw_records_activity`, `hash_raw_generation_activity`; gated
off for new runs via `workflow.GetVersion`). The boundary doc's own status table, as drafted
2026-08-25, said "12 / 23 IMPLEMENTED" — that snapshot is now stale; current code implements
nearly all 23 plus a 24th activity (`publish_preview_activity`) added for the HITL gate that
the boundary doc didn't originally specify.

---

## A. Workflow A spec-vs-built matrix

| # | Spec activity (`ContextIntakeWorkflow`) | Status | Built-as |
|---|---|---|---|
| 1 | `land_context_source` | **EXISTS**, split into two atomic stages | `stagegraph.RegisterSource` (`register_source_activity`) + `stagegraph.RetainOriginal` (`retain_original_activity`) — `modules/engine/activities/source_lifecycle.go`. Identity registration and immutable retention are separated; neither writes an `evidence.*` row. |
| 2 | `compute_h1_fingerprint` | **PARTIAL / renamed, deliberately non-custody** | `stagegraph.FingerprintSource` (`fingerprint_source_activity`) — `modules/engine/activities/hashing.go`. Produces `context_source_fingerprint` (canon `context-source-fingerprint-v1`), explicitly documented as distinct from custody `h1_source`. |
| 3 | `inspect_format` | **EXISTS**, decomposed into a 3-way parallel fan-out | `stagegraph.CaptureFilesystemMetadata` + `InventoryContainer` + `ExtractEmbeddedMetadata` run in parallel (`uiw/workflow.go:125-137`), feeding `SelectParser` (`select_parser_activity`). |
| 4 | `parse` | **EXISTS, exact match** | `stagegraph.ExecuteParser` (`execute_parser_activity`) — `ParserActivities.ExecuteParser`, `modules/engine/activities/parser_runtime.go:129`. |
| 5 | `persist_parse_staging` | **EXISTS**, renamed | `stagegraph.PersistRawGeneration` (`persist_raw_generation_activity`) — `modules/engine/activities/raw_pipeline.go:167`. Streams the bundle by reference, per the spec's "no large payloads in Temporal history" rule. |
| 6 | `normalize` | **EXISTS, exact match** | `stagegraph.NormalizeGeneration` (`normalize_generation_activity`) — `modules/engine/activities/normalized_pipeline.go:186`. |
| 7 | `seal_normalized_generation` | **EXISTS**, reordered | `stagegraph.SealGeneration` (`seal_generation_activity`, `normalized_pipeline.go:427`) runs AFTER verification (post `VerifyNormalizedGeneration`), not before hashing as the spec ordered. Lineage freezing is handled earlier by `PersistLineage` + `ValidateRawLineage`. |
| 8 | `compute_h2_generation` | **MISSING as custody-grade** | `HashNormalizedRecords`/`HashNormalizedGeneration` exist but the code's own comment is explicit: "Neither of these is H2 or H3 — those names are reserved for the raw-custody hashes... (vendored/sbv/CUSTODY.md)." Custody hashing (R04) is registered "separately when R04 is implemented" — it isn't yet. Matches the spec doc's own gap table (TODO-207 open). |
| 9 | `compute_h3_generation` | **MISSING** | No `h3-chain-h1genesis-hexconcat-v1` implementation anywhere in `modules/engine`; zero grep hits for `compute_h3_generation`. |
| 10 | `commit_context_generation` | **MISSING under that name; closest analog `PublishGeneration`** | `stagegraph.PublishGeneration` (`publish_generation_activity`, `normalized_pipeline.go:460`) is the terminal sink, but is not documented as gating on H2/H3 reconciliation (since H2/H3 aren't computed in this workflow at all). |

**Score:** 2/10 exact match (`parse`, `normalize`) · 4/10 functionally equivalent under a
different name/split (`land_context_source`, `inspect_format`, `persist_parse_staging`,
`seal_normalized_generation`) · 1/10 renamed-and-narrowed (`compute_h1_fingerprint`) ·
3/10 missing by design (`compute_h2_generation`, `compute_h3_generation`,
`commit_context_generation` — these belong to a still-unbuilt custody-promotion path, not to
tonight's context-only intake).

**Doctrine behind the 3 "missing" rows** (`modules/engine/activities/hashing.go` header
comment): "Context integrity fingerprints (R02) are DISTINCT from custody hashes (R04)."
R02 kinds (`context_source_fingerprint`, `context_raw_record_fingerprint`,
`context_raw_generation_fingerprint`) are implemented now; R04 custody kinds (`h1_source`,
`raw_record_digest`, `h3_raw_generation`) are reserved but not wired to real Activities. This
is *correct* for a context-only landing workflow — tonight's ingest doesn't need custody H2/H3.

**Workflow identity, as built:**
- Registered workflow function: `uiw.UniversalImportWorkflow(ctx, in WorkflowInput) (WorkflowResult, error)` — `modules/engine/uiw/workflow.go:57`
- Registration: `registrar.RegisterWorkflow(uiw.UniversalImportWorkflow)` — `modules/engine/uiwworker/worker.go:48`
- Task queue: env `TEMPORAL_TASK_QUEUE` via `Config.TemporalTaskQueue` (`modules/engine/temporal/config.go:23,73`) — dedicated to this workflow, **must never be `evidence-pipeline`** (that queue belongs to a different, older classification pipeline — see §B).
- The old partial worker (`modules/engine/temporal/worker.go`) is retired and fails closed: *"partial universal-import worker retired; use cmd/universal-import-worker."*
- Sole production worker: `modules/engine/cmd/universal-import-worker` — registers all 23 canon Activities + the workflow on the dedicated queue.
- Sole HTTP relay for n8n (no native Temporal client): `modules/engine/temporal/cmd/starter` — owns `POST /reference-import/start`, `POST /reference-import/{workflow_id}/decision`, `GET /reference-import/{workflow_id}/preview`.

Five named files the spec-recall prompt asked about live in **`modules/engine/activities/`**,
not `modules/engine/uiwworker/`: `source_lifecycle.go`, `raw_pipeline.go`,
`normalized_pipeline.go`, `parser_runtime.go`, `uiw_preview.go`. `uiw_preview.go` implements
`PreviewProjectionActivity.Publish` (`publish_preview_activity`) — a HITL addition entirely
outside the original 10-activity spec, tied to the preview/repair Signal flow in
`uiw/workflow.go` (`awaitPreviewDecision`, `awaitRepairDecision`). `modules/engine/uiwworker/`
holds only worker bootstrap wiring (`Run`, `Config`), not activity bodies.

---

## B. n8n asset inventory

Two **distinct, unrelated** n8n pipeline efforts exist in the repo — do not conflate them
tonight.

### B1. `deploy/docker/n8n/workflows/universal-import/` — the live UIW pipeline (relevant tonight)

| File | Trigger | Calls |
|---|---|---|
| `wf-start-import.json` | Webhook POST `universal-import/start` | `engine/temporal` starter `POST /reference-import/start` — begins one real `UniversalImportWorkflow` run, mirroring `engine/uiw.WorkflowInput` exactly |
| `wf-select-parser-activity.json` | Webhook POST `universal-import/select-parser-activity` | `engine/runtimeapi` `/activities/select_parser_activity` (Go parser) |
| `wf-execute-parser-activity.json` | Webhook POST `universal-import/execute-parser-activity` | `engine/runtimeapi` `/activities/execute_parser_activity` (Go parser) |
| `wf-preview-decision.json` | Webhook POST `universal-import/decision` | starter `POST /reference-import/{workflow_id}/decision` — sends the approve/reject **Signal** |
| `wf-preview-status.json` | Webhook GET `universal-import/preview?workflow_id=` | starter `GET /reference-import/{workflow_id}/preview` — reads the **Query** |
| `wf-assess-source-repair-activity.json` / `wf-resolve-source-repair-activity.json` | Webhook | repair-decision path (assess/resolve source repair) alongside the preview decision path |

All five/seven exports use the same 5-node shape (Webhook → Code contract-check → httpRequest
→ Code response-check → respondToWebhook), no branches, no retry/wait/persistence nodes
(Temporal owns retries; n8n only relays). **All remain inactive in the checked-in export** —
they use fail-closed placeholder hosts (`https://import-runtime.example.invalid`,
`https://reference-import-starter.example.invalid`) and placeholder credentials
(`PLATFORM_IMPORT_RUNTIME`, `REFERENCE_IMPORT_STARTER`, `N8N_UNIVERSAL_IMPORT_WEBHOOK`) that
must be bound to real endpoints/secrets before activation — see `README.md` in the same
directory for the full deployment checklist (reproduced in §E below).

**This is not untested — it was already run live once, on 2026-08-27, and reverted.** Per
`docs/reviews/2026-08-27-n8n-uiw-live-readiness-fail-closed.md` (Codex · GPT-5, byline dated
2026-08-27, STATUS: BLOCKED / FAIL CLOSED): all five original workflows (not the two repair
ones) were imported into a real Coolify-managed n8n instance (service
`ddjgrmys36d9n8xwcwj0mml2`) alongside the Coolify-deployed parser runtime
(`o11nxvzqwskxrqmtbvup7iet`, healthy, 11 parsers ready), the starter
(`r1084s1lsm80fsv4ol9ocij0`, healthy), and the worker (`d24bb9eoo47qtw9eq1xc6u64`, running,
queue `universal-import-v1`, `activity_count=23`) and activated with real workflow IDs
(`Universal Import - start` = `7HDcx0GPDELB56J0`, etc.). Two independent live blockers were
hit and both now have a corresponding fix already merged:

1. **n8n rejected `$env` in node expressions** — the authenticated production start execution
   failed at node "HTTP - reference import starter start" with
   `ExpressionError: access to env vars denied`, producing no workflow/run ID. Fix: the
   checked-in exports now hardcode the endpoint as a literal, workflow-scoped HTTP-node URL
   field instead of `$env` (documented in the README's "Corrected 2026-08-27" note, §D below).
2. **`retain_original_activity` failed with a Postgres grant error** — a direct
   starter/Temporal isolation proof (bypassing n8n) using a repository-owned synthetic fixture
   (`vendored/sbv/backend/testdata/sample_backup.xml`) got as far as
   `register_source_activity` succeeding, then `retain_original_activity` failed:
   `resolve source version ownership: ERROR: permission denied for table source (SQLSTATE 42501)`.
   The workflow never reached `awaiting_decision`. Fix: `sql/0039_context_source_retention_lock.sql`
   (same byline, same date, 2026-08-27) grants `UPDATE (id)` on `context.source` to
   `context_import_writer` — its own header comment describes exactly this failure mode:
   *"retain_original_activity selects context.source_version joined to context.source with an
   unqualified FOR UPDATE. PostgreSQL therefore requires UPDATE privilege on at least one
   column of both selected tables."* Table-wide mutation stays blocked by the
   `source_append_only` trigger; only row-lock privilege was added.

All five workflows were then explicitly deactivated. **The receipt's own "required follow-up
gates" — reactivate through Coolify and rerun start → preview → reject, prove
`execute_parser_activity` did not run on a rejected/timed-out run, then run a separate
approve-to-publication + idempotency proof — were never subsequently confirmed complete** in
any doc or commit found during this recall. That is the actual state tonight inherits: not
"never tried," but "tried once, hit two bugs, both bugs now have merged fixes, never
re-verified end-to-end."

The preview hold itself is **inside** `UniversalImportWorkflow` — a genuine Temporal Signal +
Query + Timer (`engine/uiw/preview.go`), sitting between `select_parser_activity` and
`execute_parser_activity`, with a 24-hour `previewDecisionTimeout`. Phase enum:
`awaiting_decision | approved | rejected | timed_out`.

Also present: `deploy/docker/n8n/AGENT_MEMORY.md` (scope memory, authority-links to the spec
doc + a builder guide + a golive runbook), `deploy/docker/n8n/README.md` (deploy notes for the
standalone n8n+Postgres box, unrelated to workflow content), and
`deploy/docker/n8n/workflows/universal-import/README.md` (13KB, the authoritative build log —
quoted extensively in §C/§D below).

### B2. `docs/research/integration-audit-2026-08-24/composed/` — a DIFFERENT, older pipeline (NOT tonight's target)

`wf-classify-batch.json`, `wf-judge-gate.json`, `wf-persist-results.json`,
`wf-error-handler.json`, `wf-intake-dropdir.json` — a chunk-classification pipeline that
writes only to `analysis.chunk_classification`, driven by `ClassificationBatchPipeline` +
`n8n_webhook_activity` on the Temporal queue **`evidence-pipeline`** (per
`docs/runbooks/N8N-PIPELINE-GOLIVE-RUNBOOK.md`, 2026-08-24). This predates and is unrelated to
`UniversalImportWorkflow`. It is not the ingest workflow — flagging it only so it isn't
mistaken for one tonight; its queue name (`evidence-pipeline`) is exactly the name the UIW
worker explicitly refuses to bind to at startup.

No `*.n8n.json` files exist outside these two directories. A repo-wide content-shape grep for
`"connections"` in JSON (the n8n-export marker) confirms this is exhaustive within the
platform's own scope: the only other hits are `docs/research/integration-audit-2026-08-24/extracted/*.json`
(third-party community templates pulled for reference, not platform-authored — already noted
above), one unrelated Semantica cookbook example, and `modules/traceIQ/00_Documentation/STACK_Deployment/n8n/flows/image-to-r2.json`
— the latter belongs to `modules/traceIQ/`, a separate nested independent gitignored product
repo, not this platform. No git history shows n8n workflow JSON added-then-removed anywhere
in this repository's own tree.

---

## C. The 2026-08-30 preview-deadlock review — it never produced a resolution

**Directly relevant correction to the recall brief's premise:** the sub-agent that queried
`opencode.db` (copied read-only, attached via DuckDB's sqlite extension, joined
`session`→`message`→`part`) found that the "READ-ONLY ARCHITECTURAL REVIEW" session **ran but
never completed**. Five attempts, all in this repo, all within 2026-08-30 10:26:47–10:32:19
UTC:

| Session | Title | Model/Provider | Result |
|---|---|---|---|
| `ses_fadcae421ffe...` | "New session" | — | placeholder |
| `ses_fadca3c07ffe...` | "New session" | — | placeholder |
| `ses_fadc9cd9effe...` | "UIW preview approval gate architecture review" | opencode/`nemotron-3-ultra-free` | **Failed** — HTTP 400/404 "Provider returned error" |
| `ses_fadc69c7fffe...` | "UIW workflow architectural review and preview deadlock resolution" | openrouter/`claude-opus-latest` | **Failed** — HTTP 401 "Missing Authentication header" |
| `ses_fadc5d4a1ffe...` | "opencode-memory recall selector" | ollama-cloud/`glm-5.2` | Aborted (`MessageAbortedError`) |

Confirmed exhaustive: this is the **last row in the entire 713-session `opencode.db`**
(oldest 2026-01-10) — OpenCode usage stopped mid-failure on this exact task and was never
retried, in this repo or any other. No assistant `part` of type `text` exists for any of these
five attempts — only error objects. So there is no recorded conclusion, recommendation, or
design reasoning from this session about the deadlock, Signal/Query/Timer, or `preview_handle`.

The user framing prompt was captured verbatim (fullest version, from the second attempt):

> "READ-ONLY ARCHITECTURAL REVIEW. Do not edit any file. Inspect engine/uiw/workflow.go,
> engine/runtimeapi/uiw_preview.go, engine/activities/uiw_preview.go,
> engine/postgres/uiw_preview_store.go, engine/uiwworker/worker.go,
> engine/temporal/cmd/starter/main.go, and Workbench UIW clients. Determine the minimal
> correct design for the human approval gate and opaque preview projection. Temporal owns
> Signal/Query/Timer and durable identity; Workbench receives an opaque preview_handle;
> payloads remain reference-only. Resolve the deadlock where workflow pauses before parser
> execution while preview eligibility requires post-parse messages and six receipts. Report
> ordering, registrations/composition, compatibility concerns, tests. Concise findings only."

**But the deadlock this prompt describes was already resolved two days earlier, in code and
docs dated 2026-08-27** — before this failed OpenCode session ever ran. Whoever queued that
2026-08-30 review was likely re-confirming or re-deriving a decision that was already shipped;
it just never got a model response either way. The actual resolution:

- `modules/engine/to_be_deleted/temporal-holds.go.obsolete` (header comment, moved 2026-08-27,
  kept for history per owner's never-delete policy) records that an earlier design — the hold
  implemented via **Activity-level async-completion** (`execute_parser_activity` parks itself
  via `activity.ErrResultPending`; a separate HTTP starter calls `client.CompleteActivity`
  out-of-band, backed by an in-process, in-memory hold store) — **was rejected by the owner**:
  *"an in-memory map only survives as long as one worker process does, so the hold would NOT
  survive a worker restart or a replica change."*
- The corrected design puts the hold **inside `engine/uiw.UniversalImportWorkflow` itself, as
  a real Signal + Query + Timer** (`engine/uiw/preview.go`, `engine/uiw/workflow.go`), which
  Temporal makes durable via workflow-history replay — "no in-process state at all."
- `deploy/docker/n8n/workflows/universal-import/README.md` states the same resolution in
  deployment terms: *"The preview hold lives inside UniversalImportWorkflow itself, as a
  genuine Temporal Signal + Query + Timer, not as a trick at the Activity boundary in
  engine/temporal. That is a deliberate, load-bearing choice: only a workflow-level hold
  survives a worker restart or a replica change."*
- Placement answers the literal "pre-parser approval vs post-parser preview" framing directly:
  the hold sits **between `select_parser_activity` and `execute_parser_activity`** — i.e.,
  after the parser has been *selected* (so a preview of the intended parse is possible) but
  before it *executes* (so nothing is parsed without approval). Both horns of the stated
  deadlock are satisfied by that placement, not by picking one side.
- The `preview_handle` is opaque: callers pass/read the Temporal `workflow_id`; the Query
  response is `{"phase": ..., "select_ref": ..., "reason": ...}`, reference-only, never raw
  content.

**Implication for tonight's HITL gate: build nothing new here.** The design question the
2026-08-30 review was trying to answer is already answered and already implemented; the gate
just needs deployment (see §E), not architecture.

---

## D. Post-spec decisions found in code/docs, NOT present in `docs/DECISION_LOG.md`

Checked `docs/DECISION_LOG.md` directly (grep for `UniversalImportWorkflow`, `preview_handle`,
`stagegraph`, `Signal.*Query.*Timer`, `R02`, `R04`, `context integrity fingerprint`,
`h2-canonical`, `custody hash`, `n8n`, `UIW`, `preview.hold`) — no entry logs the following.
Not edited into DECISION_LOG per scope; listed here as an appendix pointer.

1. **Preview-hold architecture rejection + correction** (2026-08-27) — Activity-level
   async-completion hold → workflow-level Signal/Query/Timer. Source:
   `modules/engine/to_be_deleted/temporal-holds.go.obsolete` header +
   `deploy/docker/n8n/workflows/universal-import/README.md` (both quoted in §C). This is
   arguably the single most load-bearing post-spec decision for tonight's HITL gate and has no
   DECISION_LOG row.
2. **Substitute-workflow bug, corrected 2026-08-27**: *"`wf-start-import.json` and
   `engine/temporal` previously started a smaller, package-local substitute workflow instead
   of the real `UniversalImportWorkflow`, and implemented the preview hold as in-process
   Activity async-completion rather than a workflow-level Signal. Both are now the real
   workflow and a real Signal/Query/Timer."* (same README.)
3. **Wrong HTTP path, corrected 2026-08-27**: the select/execute n8n workflows called
   `.../v1/activities/<name>` — a path `engine/runtimeapi/parser_activities.go` "has never
   actually served"; corrected to the real mount `/activities/<name>` (no version prefix).
4. **Security gap, fixed 2026-08-27**: all five Webhook trigger nodes previously had **no
   authentication at all** — "anyone who discovered the webhook URL could invoke a real parser
   Activity." All five now require the `headerAuth` credential
   `N8N_UNIVERSAL_IMPORT_WEBHOOK (placeholder)`.
5. **Doc staleness worth flagging (not a decision, a drift)**: `SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html`'s
   own status table ("12 / 23 IMPLEMENTED", drafted 2026-08-25) is now stale — current code
   implements essentially all 23 canon activities plus the added preview activity. The doc was
   only committed to the repo today (`9c213cc`), so this drift was invisible until now.
6. **Two disjoint n8n pipelines coexist** (§B1 vs §B2) with no cross-reference in
   DECISION_LOG tying them together or apart — worth a line so a future reader doesn't merge
   them by assumption.
7. **A real live-fire test of the UIW n8n bridge already happened and was reverted**
   (`docs/reviews/2026-08-27-n8n-uiw-live-readiness-fail-closed.md`, §B1) — Coolify service IDs,
   two concrete failures (`$env` blocked; `context.source` grant denial), and two corresponding
   fixes (literal-URL correction; `sql/0039_context_source_retention_lock.sql`) all exist
   outside DECISION_LOG. The receipt's own required follow-up ("reactivate and rerun
   start→preview→reject, then prove approve-to-publication") has no recorded completion
   anywhere — this is the single most concrete "what's actually left" fact for tonight and it
   is not in DECISION_LOG.

Corroborating signal from the (incomplete) Codex-rollout mining sub-agent: exact-string hits
for the spec's literal activity names (`land_context_source`, `compute_h1_fingerprint`, etc.)
and `ContextIntakeWorkflow` cluster almost entirely in 2026-08-25–27 sessions (spec-drafting
period) with ~zero hits in 2026-08-28–30 build sessions, while `modules/engine/temporal`,
`modules/engine/activities`, `modules/engine/uiwworker`, and `uiw_preview` have heavy hit
density in 2026-08-29/30 (1,181 occurrences across 53 files). That is consistent with — not
independent proof of, since the sub-agent never returned verbatim quotes — everything found by
direct code/doc reading above: the spec's literal names were abandoned early in favor of the
`uiw`/`UniversalImportWorkflow` naming actually built.

---

## E. Tonight's wiring delta — shortest path to a working, HITL-gated ingest run

**The workflow, activities, and preview gate are already built — and were already deployed and
live-fired once, on 2026-08-27 (§B1/§D7).** Tonight is a re-verification and reactivation
task, not a first build or a first deploy. Both blockers hit on 2026-08-27 already have
merged fixes; nobody has confirmed the fixes actually work end-to-end. In order:

1. **Confirm the two 2026-08-27 fixes are actually live**, not just merged: (a) the checked-in
   `deploy/docker/n8n/workflows/universal-import/*.json` no longer reference `$env` anywhere
   (grep the exports before re-importing — the README claims this is fixed); (b) migration
   `sql/0039_context_source_retention_lock.sql` has actually been applied against the live
   `platform` database (its own `DO $$` block hard-fails if run against the wrong database or
   without the expected NOLOGIN roles, so applying it is a cheap, self-verifying check).
2. **Bind real endpoints.** Replace `https://import-runtime.example.invalid` (select/execute
   workflows) and `https://reference-import-starter.example.invalid` (start/decision/preview
   workflows) with the two live service URLs as literal, non-secret HTTP-node URL values — the
   same Coolify services from 2026-08-27 if still running (parser runtime
   `o11nxvzqwskxrqmtbvup7iet`, starter `r1084s1lsm80fsv4ol9ocij0`, worker
   `d24bb9eoo47qtw9eq1xc6u64`, n8n `ddjgrmys36d9n8xwcwj0mml2` — verify each is still
   `running:healthy` before assuming so).
3. **Bind three credentials** (all currently placeholders, so the workflows fail closed until
   this is done): `PLATFORM_IMPORT_RUNTIME` and `REFERENCE_IMPORT_STARTER` (`httpHeaderAuth`,
   on the select/execute and start/decision/preview HTTP nodes respectively), and
   `N8N_UNIVERSAL_IMPORT_WEBHOOK` (`headerAuth`, on all five Webhook triggers).
4. **Reactivate the five workflows** (`Universal Import - start/select/execute/preview/decision`
   — same n8n workflow IDs as 2026-08-27 if that instance/import was never deleted:
   `7HDcx0GPDELB56J0`, `fvKS2gcsRUdEKUun`, `YQoFBykpZoDrU0n6`, `nobMh2uO8eIBuH2p`,
   `abOE3dzoZo3yw26x`) through Coolify, per the receipt's own required-follow-up order.
5. **Rerun exactly the receipt's own unfinished checklist**: start → preview → **reject** first
   (prove `execute_parser_activity` never runs on a rejected/timed-out run), and only after
   that passes, run a separate **approve**-to-publication fixture plus the same-request
   idempotency proof. Use a disposable synthetic fixture as before
   (`vendored/sbv/backend/testdata/sample_backup.xml`), never real case material, and reconcile
   test state afterward per the project's disposable-test-data rule.
6. **Faster fallback if n8n reactivation is blocked tonight**: the starter's own HTTP endpoints
   (`POST /reference-import/start`, `POST /reference-import/{workflow_id}/decision`,
   `GET /reference-import/{workflow_id}/preview`) can be called directly (curl/CLI) — n8n is a
   thin relay in front of them, not a requirement. This gives a CLI-triggered
   `ContextIntakeWorkflow`-successor with the same HITL preview gate, without touching n8n at
   all, if step 5 turns out to be the long pole.
8. **Do not build custody H2/H3 tonight.** Per §A rows 8–10, this workflow deliberately
   computes context-integrity fingerprints (R02), not custody hashes (R04); that split is
   correct for context-only landing and matches the spec's own framing. `PublishGeneration`
   (`publish_generation_activity`) is the correct terminal sink for tonight's context
   generation — it is not, and should not become, a stand-in for a custody promotion step.
9. **Do not touch or reuse** `docs/research/integration-audit-2026-08-24/composed/*.json` or
   the `evidence-pipeline` Temporal queue — that is the unrelated classification pipeline
   (§B2), and the UIW worker already refuses to start against that queue name by design.
