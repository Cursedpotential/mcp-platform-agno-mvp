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
