# Ingest simplification plan — custody only at promotion, one activity per file

> _Byline: Claude Code · Opus 5 · 2026-09-03. Orchestrator plan per `/make-plan`._
>
> **STATUS: ITERATING — NOT DONE.** This plan is done only when the owner says it
> is done (owner, 2026-09-03: "You don't decide when the plan is done… We iterate
> until I say the plan is done"). Every phase below is a proposal until ratified.
>
> Owner direction, 2026-09-03 (verbatim fragments): "at the point that it becomes
> evidence we are going to re-extract it from the original binary… store that
> immutably… add all of our metadata and our tables away from the file… once it
> gets promoted to evidence it will get re-extracted and run through the entire
> hashing process… we can completely split the evidence process from the
> normalized ingestion process… one activity for the entire workflow" — refined
> to "one activity per file, so if the workflow is calling a batch it will call
> multiple activities… large files broken into chunks early… processed in
> parallel." And: "H1 still happens… likely the chunks also… it's more
> verification than anything." And on identity (corrected same day): promotion
> writes **new rows into `evidence.*` tables linked by FK to the working rows** —
> "create new tables for the evidence that has everything included and then it
> can just link to that particular foreign key for its provenance… just like it
> does through the change detection and into the graph and the vectors." An
> earlier verify-in-place variant was rejected because the D-128 immutability
> guards attach to `evidence.*` tables, so a flagged working row would be
> unguarded evidence.
>
> Each phase is self-contained for a fresh session. Every task is framed as
> COPY-FROM-A-CITED-LOCATION, not "migrate". Every phase ends with a proof
> checklist and anti-pattern guards. Nothing here is done until its checklist
> passes on the live stack.

## The model in one table

| Moment | Before (D-124) | After (this plan) | Hash family |
|---|---|---|---|
| Intake — whole file | context fingerprint | **keep** | `context-source-fingerprint-v1` |
| Intake — chunking | (chunker orphaned) | **wire in, hash each chunk** | `content_sha256` + byte range (D-116) |
| Normalization | normalized digests | **DELETE** — tables also hold AI chats | — |
| Promotion | custody H1/H2/H3 (never built) | **BUILD — project into `evidence.*`, FK to working rows** | `h1-rawbytes-v1`, `h2-rawelement-v1`, `h3-chain-sbv-genesisempty-v1` |
| Later | reverification | keep | — |

**Why this is safe:** `context-source-fingerprint-v1` and `h1-rawbytes-v1` are the
same computation over the same bytes (`modules/engine/activities/hashing.go:212`
and `modules/forks/sbv/internal/custody.go:35`). Same value, different claim.
Promotion recomputes over the sealed original, compares to the intake
fingerprint, and if equal records the number under its custody tag. The naming
discipline (D-088/D-089) is what stops a fingerprint from ever being presented
as custody. Chunk hashes are **not** promotable to H2 (different bytes, post-
chunking) — they prove chunking was lossless and re-extraction deterministic,
which is exactly the verification job the owner named.

---

## Phase 0 — Discovery (DONE; consolidated here so later phases need not repeat it)

Source: Explore subagent report 2026-09-03, all claims file:line-cited. Read
these before any phase; do not re-derive them.

### Allowed APIs and existing patterns (cite these; do not invent)

| Need | Exists at | Notes |
|---|---|---|
| File-level fingerprint | `modules/engine/activities/hashing.go:182-228` (`fingerprintSource`) | uses `custodyhash.HashReaderH1` under tag `context-source-fingerprint-v1` (`:43`) |
| Per-record fingerprint | `hashing.go:291-365` (`hashRecordBytes`) | tags at `:44-45` |
| Generation fold | `hashing.go:421-508` | `custodyhash.NewChain("")` at `:377` |
| Custody-kind constants (reserved) | `hashing.go:28-31` | `HashKindH1Source`, `HashKindRawRecordDigest`, `HashKindH3RawGeneration` — declared, **unused**, comment: "R04 owner promotion only" |
| Custody primitives | `modules/forks/sbv/internal/custody.go:65` `HashFileH1`; `HashRecordH2`; `ChainH3` | vendored at `modules/engine/vendor/github.com/lowcarbdev/sbv/internal/` |
| Canon tags | `custody.go:35` `h1-rawbytes-v1`; `CUSTODY.md:137` `h2-rawelement-v1`, `h3-chain-sbv-genesisempty-v1` | |
| Chunker | `modules/engine/chunk/chunk.go` — `digest()` at `:167`; lossless validator `:150-165` | proves every chunk is an original-source slice with full coverage |
| Chunk activity | `modules/engine/activities/chunking.go:13` `chunk_document_activity` | registered, **NOT in `Stages`**, not workflow-invoked (`stagegraph/stage.go:79-106` explains why) |
| Chunk table | `working.content_chunk` (`sql/bootstrap/schema_baseline_20260830.sql:3415`) | `id uuid DEFAULT uuidv7()`, `content_sha256`, byte ranges |
| Stage list (26) | `modules/engine/stagegraph/stage.go:14-41`; DAG `registry.go:55-223` | 5 hash stages asserted by `graph_test.go:160-185` (`TestFiveHashComputationStagesAreDistinct`) |
| Hash stages | `FingerprintSource`, `FingerprintRawRecords`, `FingerprintRawGeneration`, `HashNormalizedRecords`, `HashNormalizedGeneration` | the last two are hash moment 2 |
| Workflow | `modules/engine/uiw/workflow.go` | version gates via `workflow.GetVersion` (`:13-41`) |
| Fidelity digest | `modules/engine/fidelity/fidelity.go` | 4-field seal; role changes in this plan (see Phase 1) |
| n8n flow → Activity | `modules/engine/temporal/flowbinding.go`, `flowactivity.go` | declare a flow, get an Activity |
| Tool gateway | `modules/engine/toolgateway/`, `cmd/tool-gateway/` | built, **undeployed** |
| Python H1 custody write on ingest | `server/evidence/custody.py:418-427` | writes `level='H1'`, `canon_version='h1-rawbytes-v1'` on EVERY `ingest_artifact` — **the leftover to remove** |
| Python H2/H3 | `custody.py:582-658` `reconcile_sbv_import` | SBV-only path; digests received from SBV, not computed |
| ELT canon deviation | `modules/engine/postgres/elt_structured_repository.go:65` `h2-rawelement-duckdb-json-v1`; open question at `:33-49` | must be resolved as a **fingerprint**, not custody |

### Facts that shape the plan

- **Go ingest already computes zero custody hashes.** Only context fingerprints under distinct tags. The custody symbols are declared-unused. (Agent: repo-wide grep excluding `vendor/` returned only the declaration lines.)
- **No promotion code exists anywhere** — not in `modules/engine`, not in `server/evidence/`. Only comments saying R04 will do it. Phase 4 is greenfield.
- **The chunker is orphaned.** Built, tested, registered, never scheduled by the workflow.
- **`content_chunk.id` is `uuidv7()`** — random, and it stays put: promotion never touches working rows. Evidence rows get their own `uuidv7` plus a FK back — the standard provenance link, same as every CDC projection.
- **Python still writes custody H1 at ingest** (`custody.py:418`). This is the only real "custody at ingest" left, and it's the one to cut.

### Anti-patterns (global, every phase)

- Writing `h1-rawbytes-v1`, `h2-rawelement-v1`, or any `h3-chain-*` tag anywhere except the promotion activity.
- Promotion MUTATING working rows (tier flips, content edits, id changes). It writes new `evidence.*` rows and links back by FK; working rows keep evolving.
- Evidence living anywhere other than `evidence.*` — that is the D-128 guard boundary, and a flagged working row is unguarded evidence.
- Hashing anything in `analysis.normalized_record` / normalized generations.
- A parser or chunker computing a hash it then persists as custody (D-130 rule 1/2).
- Regenerating `uuidv7` for a record that already exists.
- Returning an empty record set on an unrecognized shape (the 516-MMS failure). Raise.
- Inventing a Temporal API — copy the `workflow.GetVersion` gate shape from `uiw/workflow.go:13-41`.

---

## Phase 1 — Canon first (docs + decision log), so nothing below can drift

**Goal:** record the ruling before touching code, per the doc-drift rule.

**Implement:**
1. Append to `docs/DECISION_LOG.md` (copy the row shape of D-136 exactly):
   - **D-137** — Custody only at promotion; promotion verifies existing rows in place; one activity per file; chunks early and parallel. Quote the owner fragments in the header of this plan.
   - **D-124 amendment** — hash moment 2 (normalized digests) is DELETED; moments 1, 3, 4 stand. Strike-through the old moment-2 text with a dated correction (never silently delete).
   - **D-130 amendment** — "one unit does one thing" is satisfied by *ingest a file*; a per-file activity is compliant. Atomic sub-units remain the shape *inside* Go for parallelism, not the Temporal boundary.
2. Update `docs/reference/HASH-TAXONOMY-2026-08-29.md` "The recurring shape" table: remove the Normalized row from *custody-relevant* families; add a sentence that chunk hashes are verification-only and not promotable to H2.
3. Update `modules/engine/fidelity/fidelity.go` package comment: its job is the **comparison check at promotion** (stored row vs fresh parse), not a join key. Keep the construction and canon tag unchanged — changing the tag would invalidate nothing yet, but don't.
4. Update `modules/engine/AGENTS.md` "Boundaries that are rulings" with the promotion-only custody rule and the verify-in-place rule.

**Verification:**
- `grep -n "D-137" docs/DECISION_LOG.md` → 1 hit
- `grep -n "moment 2\|normalized digest" docs/reference/HASH-TAXONOMY-2026-08-29.md` shows the struck-through correction, not a deletion
- `git diff --stat` touches only docs + the fidelity doc comment (no logic)

**Guards:** no code behavior changes in this phase.

---

## Phase 2 — Cut custody out of ingest

**Goal:** after this phase, NOTHING on the ingest path writes a custody tag.

**Implement:**
1. `server/evidence/custody.py:418-427` — the `INSERT INTO evidence.evidence_hash … level='H1', canon_version='h1-rawbytes-v1'` on every `ingest_artifact`. Change it to write the **context fingerprint** under `context-source-fingerprint-v1` into the context receipt table used by `hashing.go:217` (copy the write shape from `modules/engine/postgres/hash_repository.go:427-435` ref-kind mapping). Keep the SHA-256 computation (`_sha256_file`, `:228`) — it's the same number. Only the tag and destination change.
2. `verify_artifact` (`custody.py:458-462`) must keep working against the fingerprint row — update its lookup, don't delete it.
3. Delete hash moment 2 from the workflow: in `modules/engine/uiw/workflow.go`, stop scheduling `HashNormalizedRecords` and `HashNormalizedGeneration`. Do this behind a NEW `workflow.GetVersion` gate — copy the exact shape at `uiw/workflow.go:13-41` (`fingerprintVocabularyChangeID`) so in-flight histories replay. Do NOT delete the activity code yet; unregister it from the DAG in `stagegraph/registry.go` and update `graph_test.go:160-185` (`TestFiveHashComputationStagesAreDistinct`) to assert **three** hash stages.
4. `verify_normalized_generation_activity` (`normalized_pipeline.go:348`, recompute at `:386`) depends on moment 2. Reduce it to lineage/coverage checks only, or remove it under the same version gate.
5. Resolve the ELT open question at `elt_structured_repository.go:33-49`: `raw.<format>.content_hash` is a **context fingerprint**. Rename the constant at `:65` from `h2-rawelement-duckdb-json-v1` to `context-rawrecord-duckdb-json-fingerprint-v1` and update the SQL defaults at `sql/0009_raw_layer_and_derivation.sql:111` and `schema_baseline.sql:4678,4710,4742,4774,4830,4889` via a NEW migration (never edit an applied one). Strike the open-question comment with the resolution.

**Verification:**
- `grep -rn "h1-rawbytes-v1\|h2-rawelement-v1\|h3-chain" server/ modules/engine --include=*.py --include=*.go | grep -v vendor | grep -v _test | grep -v promotion` → **zero hits outside the (not-yet-built) promotion package** and the constant declarations at `hashing.go:28-31`
- `go test ./stagegraph/` passes with the hash-stage count = 3
- `uv run pytest tests/ -k custody` passes; `verify_artifact` test still green
- Replay test: an in-flight workflow history recorded before the gate still replays (copy the pattern from `uiw/workflow_test.go`)

**Guards:** never edit an applied migration; the `GetVersion` gate is mandatory or live runs break on redeploy; keep the SHA-256 computation, only retag.

---

## Phase 3 — Wire chunking in early; one activity per file; parallel chunks

**Goal:** the workflow shape the owner described.

**Implement:**
1. Add `chunk_document_activity` to `stagegraph.Stages` and the DAG in `registry.go`, depending on `retain_original` and running **before** parse for already-normalized text (markdown, plain text) and **after** parse for decoded records. Read `stage.go:79-106` first — it explains why it was excluded (it's an OR-branch, not a converging dependency). Model it as two entry points if needed; do not fake a linear dependency.
2. Chunk hashing: the chunker already emits `ContentHash` and byte ranges (`chunk.go:150-167`). Persist them to `working.content_chunk.content_sha256` — copy the repository write shape from `modules/engine/postgres/chunk_repository.go` (built in C1, 2026-09-02).
3. Per-file activity: introduce a `IngestFileWorkflow` (child workflow) in `modules/engine/uiw/` that runs the existing stage sequence for ONE source. The batch entry point fans out one child per file — copy the child-workflow shape from the Temporal Go SDK vendored at `modules/engine/vendor/go.temporal.io/sdk/workflow/` (`ExecuteChildWorkflow`). Do not invent a fan-out helper; the SDK has one.
4. Parallel chunks: inside the per-file activity, chunk processing (fingerprint/persist) fans out with a bounded `errgroup` — copy the concurrency pattern already used in `hashing.go:291-365` if present, else the standard `golang.org/x/sync/errgroup` (check `go.mod` before adding).
5. Heartbeat: any activity that processes a multi-GB file must call `activity.RecordHeartbeat` — copy from wherever the vendored SDK examples do it; the 86 GB SMS/MMS bucket has single files that need it.

**Verification:**
- `go test ./stagegraph/` — chunk stage present, DAG acyclic, dependency test passes
- `go test ./uiw/` — child-workflow fan-out test: 3 fixtures → 3 child runs
- Live: start a batch of 3 fixtures via the starter; Temporal UI shows 3 child workflows
- Chunk rows carry `content_sha256` and the validator's lossless-coverage check is exercised in a test

**Guards:** the chunker never hashes for custody; chunk hashes are verification only. No activity may exceed Temporal's default start-to-close without heartbeating.

---

## Phase 4 — Build promotion (greenfield): project into `evidence.*`, FK to working rows

**Goal:** R04. The only place custody tags are ever written. Evidence is a
**projection** of working data into the guarded schema — the same shape as the
ADR-0052 CDC fan-out into graph and vectors — never a mutation of working rows.

**Implement** — new package `modules/engine/promotion/`, new activity `promote_source_version_activity`:
1. Input: `source_version_ref` + the operator's decision receipt (copy the request/receipt shape from `activities/repair.go:100-140`, which already models an operator-gated activity).
2. Re-read the sealed original via the acquisition resolver (`acquisition.NewSchemeRouter` — same one the gateway uses). Recompute SHA-256; assert equal to the intake `context_source_fingerprint`. **Mismatch → fail closed, no promotion.**
3. Re-parse through the SAME parser id+version recorded on the source version (`postgres/parser_activity_store.go` persists it). Re-chunk.
4. **Verify against working rows:** for every produced chunk, look up the existing `working.content_chunk` row by `(source_version, byte_start, byte_end)`; assert `content_sha256` equal. Any mismatch → surface the diff as a receipt and **stop** — the exhibit must be the thing that was reviewed. Never mutate the working row.
5. On full match, **write the evidence projection**: new rows in `evidence.*` tables (a NEW migration adds `evidence.message`/`evidence.chunk` or reuses existing evidence tables — inventory `evidence.*` in `schema_baseline_20260830.sql` first and reuse before adding). Each evidence row carries its own `uuidv7`, the complete record content, and a FK `working_chunk_id` / `working_record_id` back to its source row. The FK is the provenance link; it is the only join and it is the platform's standard one.
6. Write custody on the evidence rows — H1 (`HashFileH1`, tag `h1-rawbytes-v1`), H2 per raw record span (`HashRecordH2`, `h2-rawelement-v1`), H3 fold (`ChainH3`, `h3-chain-sbv-genesisempty-v1`) — into `evidence.evidence_hash` using the column contract at `server/evidence/custody.py:415-432`.
7. Message-level check: for each promoted message, compute `fidelity.Digest` from the working row and from the evidence row; assert equal. That equality is the recorded proof that the exhibit equals what was reviewed.
8. Working rows are untouched and keep evolving — investigation continues after promotion; the evidence rows are the frozen snapshot under the D-128 guards.
9. Register under `stagegraph` as its own stage; it is NOT part of the ingest DAG. It is invoked by the operator's decision, not by ingest completion.

**Verification:**
- Unit: byte-identical re-parse → promotes; one altered byte in the original → refuses at step 2; one altered stored chunk → refuses at step 4 with a diff receipt; a swapped-direction message → refuses at step 7
- `grep -rn "h1-rawbytes-v1\|h2-rawelement-v1\|h3-chain" modules/engine server --include=*.go --include=*.py | grep -v vendor | grep -v _test` → hits ONLY in `modules/engine/promotion/` and the constant declarations
- `grep -n "UPDATE working\.\|DELETE FROM working\." modules/engine/promotion/` → **0** (promotion never mutates working)
- Live: promote the synthetic fixture (`upload://72640c6c…`, 95 messages, 555-numbers); `evidence.evidence_hash` gains H1 + 95 H2 + 1 H3; `evidence.*` gains 95 message rows each with a valid FK; `working.content_chunk` row count and every `id` are unchanged (snapshot ids before/after)
- Every evidence row's FK resolves: `SELECT count(*) FROM evidence.message e LEFT JOIN working.content_chunk w ON w.id = e.working_chunk_id WHERE w.id IS NULL` → 0

**Guards:** never mutate working rows; evidence only in `evidence.*`; never promote on any mismatch; custody tags nowhere else; reuse existing `evidence.*` tables before adding new ones.

## Phase 5 — Deploy and rehearse on real data

**Blocked on the owner for two actions** (unchanged since 2026-09-02): mint a tagged (`tag:docker`) Tailscale auth key for the gateway, and add the shared materialize mount to platform-tools.

**Implement:**
1. Deploy `deploy/tool-gateway.yaml` on ovh-app (host dirs already prepped at `/data/agno/volumes/tool-gateway/`). Confirm `svc:tool-gateway` appears in `tailscale serve status`.
2. Rehearsal on the synthetic fixture through the full new shape: batch → per-file child → chunk → fingerprint → preview → operator approve → **promotion**.
3. First real ingest: **Google Voice** — ~29,300 HTML conversation files across `r2:casebible-raw` and `r2:casebible-sorted` (inventory `docs/reviews/2026-09-03-r2-messaging-inventory-and-export-shapes.md`), parser `google_voice_html` already registered, zero new code. Run as a batch; do not promote anything real without the owner present.

**Verification:**
- Gateway `GET /healthz` 200 over its Service FQDN; `POST /tools/repair.detect/run` with an `upload://` locator returns 200 (the 2026-09-02 404 is gone)
- Temporal UI: one child workflow per file; no activity exceeds heartbeat timeout
- A Google Voice batch of 50 files completes with 0 silent-empty results (`stats.record_count > 0` or a raised error, never 0 without error)

---

## Phase 6 — Verification sweep

1. Anti-pattern grep (run all, expect the stated results):
   - custody tags outside promotion → 0
   - `uuidv7()` regeneration in promotion → 0 (`grep -n "uuidv7\|NewString" modules/engine/promotion/`)
   - normalized-table hashing → 0 (`grep -n "HashNormalized" modules/engine/uiw/workflow.go` inside the live branch of the version gate)
   - `return None` / empty-set on unrecognized shape in any parser → review each hit
2. `go build ./... && go vet ./... && go test ./...` in `modules/engine/` — green
3. `uv run ruff check server tests && uv run mypy server && uv run pytest -q` — green, and the pre-existing 26 failures (deploy-contract drift, `FrozenInstanceError`, opencode-ops) are either fixed or explicitly listed as out of scope with their cause
4. Doc drift: `grep -rn "hash moment 2\|normalized digest at normalization" docs/` shows only struck-through, dated corrections
5. Live proof, not inferred: Temporal UI screenshot of a completed promotion; `SELECT count(*) FROM evidence.evidence_hash WHERE level IN ('H1','H2','H3')` matches the fixture's 1 + 95 + 1

---

## What this plan deliberately does NOT do

- It does not touch AI-chat ingest (`transcripts.*`, D-082). Those never promote and never get custody.
- It does not rename the repo or the Go module (parked; see D-131/naming thread).
- It does not build the screenshot→message OCR inference lane (separate; ADR-0053 rung 3 provider is still unselected).
- It does not stand up Authentik (D-133; separate).
