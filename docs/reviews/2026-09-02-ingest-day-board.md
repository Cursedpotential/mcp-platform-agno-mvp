# Ingest Day Board — 2026-09-02

> _Byline: Claude Code · Fable 5 · 2026-09-02._
> Owner delivery order (morning, verbatim intent): **"When I get home from work, I want
> to start ingesting chats and messages."** Built exactly to the decision record — no
> assuming, no guessing; every claimed completion re-verified against this contract
> first ("slow and steady wins the race").

## The delivery contract (owner, 2026-09-02, dictated)

1. **Everything goes through Temporal.** "Every engine call calls on a Temporal
   activity, or is part of a Temporal activity." n8n handles the workflow and the
   different sources when need be. (Hardens D-077/D-078 into tonight's acceptance
   bar.)
2. **Human-in-the-loop is the functionality bar.** "The metadata completion and
   correction processes and fields and previews all are incorporated. If I can't fix
   it or add the missing context — if I can't see what is being ingested — it's not
   functional." (D-123 preview gates; `context.uiw_preview_*` store; UIW
   source-context revision + repair paths.)
3. **Context only.** "We don't need to be able to commit it to evidence. I just want
   to get it into context." (Pure D-069: everything lands as context; custody/
   promotion is OUT of tonight's scope; `engine/uiw` custody writer untouched.)

## Acceptance test (what "done" means tonight)

From this desktop (D-055 route), take a real chat/message export and:
file → Temporal workflow (live worker) → Activities: context fingerprints
(sql/0048 kinds; D-124 moment 1) → `raw.*` verbatim landing → parse via the one
Go-selected contract (D-049/D-051: SBV Go primary, Python registry behind the
contract) or skip-to-chunk for plain text (08-29 ruling) → normalized digests
(moment 2) → D-116 tables (`chat_conversation`/`chat_message` for AI chats;
`first/third_party_context_thread*` for human messages) → `working.content_chunk`
— **with a preview the owner can open, inspect, correct/complete metadata on, and
approve before the context commit.** Structured CSV/NDJSON goes through the
pg_duckdb ELT lane (Tweak 4 / H-07 / D-080).

## Governing decisions (cite, don't re-derive)

D-049 · D-051 · D-053 · D-055 · D-069 · D-071 · D-077 · D-078 · D-080 · D-082 ·
D-087/D-088/D-089 · D-116 · D-119 · D-123 · D-124 · ADR-0049 · ADR-0053 · ADR-0061 ·
HASH-TAXONOMY-2026-08-29 · TEMPORAL-N8N-WORKFLOW-AND-GAPS (Workflow A) ·
repo-review Tweak 4 (ELT).

## Phase 0 — verification of every claimed completion (RUNNING)

| Lane | Scope | Status |
|---|---|---|
| V1 Go engine + Temporal | build/tests, workflow↔activity roster, worker runnability vs live Temporal, pipeline write targets vs live schema, chunk writer reachability, deploy-path staleness | dispatched |
| V2 Parse dispatch + SBV + CLI | detect_format on real fixtures, SBV live service end-to-end, Python registry lane, context_chat_ingest vs current schema (rollback-verified), skip-to-chunk gap confirmation, Python fingerprint coverage | dispatched |
| V3 Fingerprints + DuckDB ELT | sql/0048 writers + reachability, live hash_kind constraints vs taxonomy doc, pg_duckdb live execution + R2 secret, raw_csv ELT feasibility, minimal-activity gap list | dispatched |

Also running: recovery lanes A–D (the 38 rollout-authored schema-audit files; the
R02/R03 domain guides directly feed this build).

## Phase 1 — build (sequenced after Phase 0 verdicts land)

Planned lanes, to be finalized strictly from Phase 0 evidence: Temporal worker
live; ingest Workflow A wiring (fingerprint→raw→parse→normalize→chunk activities);
skip-to-chunk route; UIW preview surface usable for view/correct/approve; DuckDB
ELT activity deployed; migrations 0066+ only for gaps Phase 0 proves (zero-net-write
validated before apply).

## Status log

- 05:33 — contract received; landing tables live-verified (raw 13 tables; context 43;
  working 58; `content_chunk` columns confirmed). pg_duckdb 1.1.0 live; no duckdb
  secrets yet.
- 05:40 — V1–V3 verification lanes dispatched; recovery lanes A–D running.

## Addenda (owner, 2026-09-02 morning)

- **Workflow A IS the spec** — the recovered TEMPORAL-N8N-WORKFLOW-AND-GAPS.md
  Workflow A activity chain governs tonight verbatim (topology). Its H2/H3 tag
  names predate D-087/D-088 — topology stands, tags follow D-087/D-088 + D-124.
- **"Get DuckDB functional to its potential"** — the ELT lane is not a checkbox:
  structured extraction (read_csv_auto/read_json_auto), set-based normalization
  joins, coverage reconciliation counts, and R2 pushdown per Tweak 4 scope.
- **V4 design-recall lane dispatched** — mining Codex rollouts 08-28..09-01,
  repo n8n assets, and the OpenCode 08-30 pre-parser-approval-vs-post-parser-
  preview deadlock resolution into an appendix:
  `2026-09-02-ingest-day-board-appendix-codex-state.md` (spec-vs-built matrix +
  shortest wiring delta).

## Status log — continued (morning, owner at work)

- 06:0x — V1/V2/V3 verdicts in. Verified: engine green; UniversalImportWorkflow
  26 activities fail-closed; context.* writers match live schema; fingerprint
  constraints byte-match taxonomy; pg_duckdb live (read_csv_auto proven).
  Broken/blocking: 3 Go Dockerfiles copy from pre-restructure paths (worker/
  starter/parser-runtime exited:unhealthy, watch paths stale); chunk stage
  orphaned (no writer/activity); ELT activity unbuilt; SBV desktop creds absent
  (found in exec-platform-tools env); context_chat_ingest chunk layer targets
  dropped tables; fingerprints Go-only by trigger design.
- 06:1x — Build lanes dispatched: E1 (DuckDB ELT activity + secret-idempotence
  fix), D1 (Dockerfile/vendor repair + watch-path list), C1 (chunk repository +
  activity + workflow wiring), W1 (Workbench HITL verify + D-125 bypass flag +
  metadata-fields assessment).
- Recovery phase 2 COMPLETE: lanes A-D committed/pushed (34/38 recovered, 3
  correctly excluded as Claude-authored, 1 pending other-source). D-072..D-081
  in the log; D-123/D-124/D-125 recorded.
- Codex mining synthesis (verbatim-sourced): HITL decisions ONLY on
  /evidence/preview (post-parse, six receipts); append-only decision snapshots
  (DB-enforced); indefinite Signal waits (GetVersion legacy 24h); opaque
  preview_handle; starter HTTP POST /reference-import/start | /{id}/decision |
  GET /{id}/preview on ${BIND_IP}:8091; n8n = 5-7 inactive bridge workflows,
  binding contract in deploy/docker/n8n/workflows/universal-import/README.md
  (placeholder endpoints + 3 credential objects; no $env in JSON); worker
  acquisition resolver currently accepts file:// only (upload/R2 resolvers
  exist unwired); known incident uiw-live-reject-20260828-001 root-caused to
  the H2 stage substring(bytea) call (0048 repair lane addressed the guard).

## Queued enhancements (owner suggestions, post-tonight)

- **tsnet for the Go services** (owner, 2026-09-02): embed `tailscale.com/tsnet`
  in universal-import-starter/-worker so each is a first-class tailnet node
  (own IP + MagicDNS name + ACL identity) instead of ${BIND_IP} host binding.
  Complements the existing Tailscale-Serve pattern (deploy/tailscale/
  workbench-serve.hujson). Not tonight-critical.
- **D-090 candidate packages + OCR ladder**: the community-node candidates
  (D-090) and the OCR/semantic-chunking options doc
  (CLAIMED_COMPLETE_LIKELY_LIES/OCR-SEMANTIC-CHUNKING-AND-TAGGING-OPTIONS)
  remain the approved sourcing lists for capability packages - each requires
  the D-090 representative-corpus gates before adoption.

## SEQUENTIAL TODO (owner order: think sequentially, act sequentially)

1. [x] D1 landed: vendored hermetic Go build (50M vendor, proven with submodule
       hidden), 3 Dockerfiles + 3 compose files fixed (context: .. — build was
       broken even pre-restructure), WATCH-PATHS.md written, tests green.
2. [x] .dockerignore scoped for repo-root context (nested repos + docs excluded).
3. [ ] Update Coolify watch paths (3 apps) per deploy/WATCH-PATHS.md — API.
4. [ ] Verify PLATFORM_DATABASE_URL on worker/starter/parser-runtime embeds
       platform_runtime and the credential still authenticates (D-122 rotation
       risk) — BEFORE redeploy.
5. [ ] Redeploy universal-import-worker, universal-import-starter,
       parser-activity-runtime; verify healthy + worker registered on
       universal-import-v1 (26 activities).
6. [ ] Bind + activate the n8n universal-import bridge workflows per
       deploy/docker/n8n/workflows/universal-import/README.md substitution map
       (real endpoints: starter ${BIND_IP}:8091, parser-runtime addr; 3
       credential objects). Without this SelectParser/ExecuteParser 404s.
7. [ ] Land + merge C1/E1/P1/W1 as they return (register.go merge is mine).
8. [ ] SBV desktop creds -> ~/.secrets/Agno-MCP-Platform.env (from
       exec-platform-tools env) for the desktop CLI lane.
9. [ ] REHEARSAL (disposable fixture, never real case data): starter
       /reference-import/start (real registry matter/court_case UUIDs) ->
       preview -> REJECT first (prove execute_parser never fires) -> new run ->
       approve -> publication + idempotency; verify context.* rows + receipts.
10. [ ] Evening handoff note for owner: what works, exact ingest steps, gaps.

### Pre-mortem watchlist (applied to steps above)
- Coolify context '..' resolution — probe-verified only; watch the first build log (step 5).
- Old preserved Temporal histories: any workflow-def change must be GetVersion-gated (relayed to C1).
- Worker acquisition resolver accepts file:// only — tonight's lane is the starter upload -> shared
  UIW_SOURCE_OBJECT_DIR path; r2:// sources are OUT of scope tonight (resolver unwired).
- Working-layer projection (D-116 message/thread tables) has NO writer — tonight ends at approved
  published context generations + preview; that projection is the next build, not silently missing.
- Classification/enrichment (D-053 lanes, D-090 nodes) not wired into UIW — scope boundary, stated.
- register.go collision between C1/E1 — orchestrator merges.

## Status log — deploy chain (2026-09-02 ~11:50-12:20 ET)

Steps 3-5 executed. **The Go build chain is repaired end to end** — all three
apps now build and start; what remains are config/grant issues, not build ones.

- **Step 3 DONE** — watch paths set on all three apps via Coolify API per
  deploy/WATCH-PATHS.md.
- **Step 4 DONE** — PLATFORM_DATABASE_URL on all three embeds `platform_runtime`
  @100.91.190.107/platform (64-char password); credential live-verified
  authenticating (D-122 rotation risk cleared).
- **Step 5 PARTIAL:**
  - `parser-activity-runtime` — **LIVE**: `parser Activity runtime listening
    address=:8090 parser_count=11`. Required two fixes beyond D1: its Coolify
    app was a **dockerfile** buildpack pinned to the pre-restructure path
    `/docker/parser-activity-runtime/Dockerfile` (so it never read its compose
    file, hence `PARSER_ARTIFACT_DIR is required` — that var only exists in the
    compose). Switched to `dockercompose` +
    `/deploy/parser-activity-runtime.yaml`; host dir
    `/data/agno/volumes/universal-import/parser-artifacts` created and chowned
    to 10001:10001 to match its siblings (compose sets create_host_path:false).
  - `universal-import-worker` / `universal-import-starter` — build + container
    start OK; both crash-loop on their own fail-closed gate:
    `UIW schema admission: catalog verification unavailable`.

### Root cause of the admission failure (diagnosed, lane S1 fixing)

The probe QUERY errors (not a check returning false). Live evidence as
`platform_runtime`:
- `permission denied for schema ops` (probe reads ops.migration_ledger)
- `permission denied for schema registry` (probe requires registry.matter /
  registry.court_case — post-0062 names)
- also no USAGE on `raw` (the raw pipeline's write target)
- `analysis.case_registry_import_receipt` has **0 rows**; the probe requires
  exactly one owner-approved receipt matching its hardcoded hashes.
- All required migrations (0036-0039, 0042, 0050-0051, 0053-0054) ARE ledgered.

**sql/0062_registry_split.sql granted USAGE+SELECT on `registry` to
platform_api / platform_worker / platform_reader but NOT to platform_runtime**,
which D-094 made the actual runtime login. That is the regression.

### Infrastructure finding — Docker address pools (ovh-files)

`Error response from daemon: all predefined address pools have been fully
subnetted` killed container creation for all three apps. `/etc/docker/daemon.json`
has **no** `default-address-pools`, so Docker's built-in pool was exhausted at 33
networks. `docker network prune -f` freed 3 (librechat, windmill, horizon-scratch
leftovers) which unblocked today's deploys — headroom is now ~3 networks.

**OWNER DECISION NEEDED:** the durable fix is adding `default-address-pools`
(e.g. base 10.201.0.0/16 size 24) to daemon.json, which requires a **Docker
daemon restart — a full outage of every container on ovh-files** (PG, Neo4j,
Weaviate, Surreal, n8n, Infisical, workbench...). Not taken unilaterally.

---

## EVENING STATUS — 2026-09-02 ~18:10 EDT

> _Byline: Claude Code / Opus 5 / 2026-09-02. Written at owner instruction to get the
> record caught up before any further building._

### Delivered today

| Item | State |
|---|---|
| Go build chain (3 apps) | **fixed** - all building; hermetic vendored Docker builds |
| Schema admission gate | **fixed** - 0066 grants, 0067 constraints, 0069 DEV identity |
| Three ingest services live | worker (26 activities), starter (:8091), parser runtime (:8090, 11 parsers) |
| n8n bridge | 7 workflows active, URLs + credentials corrected both directions |
| Security default inversion | **fixed** - workbench tailnet bypass defaulted ON, now OFF |
| DuckDB secret leak | **fixed** - 94 duplicate R2 secrets collapsed to a fixed name |
| **Acquisition seam** | **FIXED AND PROVEN LIVE** - see below |

### The rehearsal ran, and it did its job

Two runs against a synthetic fixture (95 messages, 555-prefix numbers, DEV sentinel
identity - never real case data).

**Run 1** found the defect that had blocked every UIW run ever attempted: the API boundary
admits only `upload://` and `r2://`, the worker resolved only `file://`, and the
intersection was empty. `acquisition.NewSchemeRouter` and `NewUploadIngressResolver` already
existed and were already tested - `uiwworker/worker.go` simply never used them.

**Run 2**, after the fix deployed, resolved an `upload://` reference and retained an
original for the first time. `retain_original_activity` succeeded.

**Run 2 then failed one stage later**, at `assess_source_repair_activity`: the UIW hands
platform-tools a worker-local filesystem path, but the worker runs on ovh-files and
platform-tools runs on ovh-app, where that volume does not exist. Ruled fix is the Go tool
gateway on tsnet (**D-132**); an interim second platform-tools was explicitly rejected as
temporary-permanent.

### Corrections to earlier claims in this board and in chat

- **Format coverage was understated.** An earlier count of "11 parsers" covered only the Go
  engine. platform-tools exposes **39 tools**, including `transcripts.claude-ai-export`,
  `transcripts.chatgpt-official`, `transcripts.perplexity-gdpr`, `transcripts.markdown`,
  `documents.extract-docling`, and `repair.pdf-inspect`. The Lost and Found corpus is far
  better covered than reported; the gap is delivery, not capability.
- **Coolify auto-deploy is NOT broken.** It was briefly reported as not firing; it fired
  correctly and took ~4 minutes to build. The check was made too early.

### Delivery contract vs reality

The contract was: ingest figured out, schemas done, tables done, Go engine functioning,
parsing and chunking figured out, DuckDB ELT deployed - ready to ingest chats and messages
tonight.

**Met:** schemas, tables, Go engine building and running, parsing/chunking stages built and
wired, DuckDB structured-ELT activity built, all three services live, the n8n bridge bound.

**Not met:** a completed end-to-end ingest. Two blockers were found by actually running it;
the first is fixed and proven, the second is ruled but not built. No real case material has
been ingested.

### Open, carried forward

1. **D-132 Go tool gateway (tsnet)** - ruled, not built. This is the next build item.
2. **D-131 SBV donor absorption** - ruled, not executed (subtree into `modules/engine/decode/`).
3. **B2 backups stale since 2026-08-01** - nothing automated writes them; found today.
4. **Docker address pools (ovh-files)** - unchanged owner decision; ~3 networks headroom.
5. **Platform rename** - `propria` favored as an option, not ruled. Repo is still
   `mcp-platform-agno-mvp` (also carries a stale "mvp").
6. **Lost and Found corpus** staged as the first real ingest once the gateway lands:
   `C:/Users/matts/OneDrive/Desktop/Google Drive (Not synced)/Lost and Found` - 18 markdown
   chats, 2 ChatGPT exports, 2 Claude exports, 12 docx, 5 call-log PDFs.

