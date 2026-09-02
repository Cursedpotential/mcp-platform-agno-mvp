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
