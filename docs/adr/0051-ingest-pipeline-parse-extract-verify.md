# ADR-0051: The ingest pipeline — SBV parses+previews, extraction is a separate triggered stage, HITL verifies

- Status: **Superseded in part by ADR-0053** for AI-chat landing, post-chunk routing,
  selective HITL, multimodal assets, and the investigation register. The general parse →
  async extract → verify direction remains accepted. Original status: **Accepted as direction** — owner stated this architecture emphatically across the
  2026-08-10 session ("SBV should be in charge of parsing and previewing and then handing it off
  to the next part of the process which handles all of the extractions … and then there's the
  human-in-the-loop part that comes after"). **NOT YET BUILT** — the current-reality gap is
  documented below and is the work this ADR authorizes.
- Date: 2026-08-10
- _Byline: Claude Code · Opus 4.8 · 2026-08-10_
- _Amendment byline: Codex · GPT-5 · 2026-08-13_
- Ties together: ADR-0049 (SBV = the universal parser) · ADR-0050 (six-lane knowledge storage) ·
  ADR-0043 (Semantica extraction worker) · ADR-0044 (evidence-vs-context boundary) ·
  ADR-0002/0047 (native HITL + audit ledger). This ADR is the **flow**; those are the parts.

## Context

ADR-0049 says what parses (SBV). ADR-0050 says where knowledge lands (six lanes). Neither says how
a file becomes knowledge end to end, and the code has drifted into **two disconnected ingest paths**
that each do part of the job. The owner re-stated the intended flow many times on 2026-08-10 because
it was written down nowhere. This ADR writes it down.

The one-sentence shape: **one file → one pipeline → three stages (parse+preview, extract, verify),
with the custody chain level as the ONLY branch between evidence and context material.**

## Decision

### The pipeline (target)

```
ANY source file  (evidence · SMS · AI chat · email · all formats — NO separate pipelines)
      │
      ▼
[ intake ]   file → DuckDB: cache + assign UUID + link to catalog
      │              (R2 = lakehouse, wired into PG + DuckDB; pg_duckdb is the bulk-ingest point, ADR-0050 §6)
      ▼
[ STAGE 1 · SBV ]   parse + PREVIEW  (the one GUI, fork of lowcarbdev/sbv, mostly Go — ADR-0049)
      │              SBV's job ends at "parsed + previewable." It then HANDS OFF. It does not extract.
      ▼
   working.normalized_record  (Postgres — the source of truth)
      │
      │  ◀── STAGE 2 is TRIGGERED, not called inline:
      │      a PG CHANGE-DETECTION monitor fires the fan-out (new/changed rows → downstream).
      ▼
[ STAGE 2 · EXTRACTION ]   chunk → multipass extraction → artifact extraction → entities → timeline
      │        fan-out targets: Weaviate (chunk+embed → the six lanes, ADR-0050) ·
      │        Semantica (multipass extraction + artifacts, ADR-0043) ·
      │        Graphiti (entities + relationships + timeline → Neo4j)
      ▼
[ STAGE 3 · HITL VERIFY ]   human approves/corrects extracted candidates before they become canonical
      │        (native @approval, ADR-0002; every decision to ops.audit_ledger, ADR-0047)
      ▼
   canonical knowledge + timeline, queryable per lane
```

### The invariants

1. **One pipeline for everything.** Evidence, SMS, AI chats, email — same parse → extract → verify
   path. There is not an "evidence pipeline" and a "knowledge pipeline."
2. **Custody tier is the ONLY branch.** Evidence material takes the FULL custody hash chain
   (H1/H2/H3, ADR-0034); context material takes LIGHT custody. Everything downstream of custody is
   shared. (ADR-0044 is the boundary; this ADR says the boundary is a *tier flag*, not a fork.)
3. **SBV parses and previews, then hands off.** Extraction is NOT SBV's job and must not be folded
   into the parser. SBV's output is normalized records + previews; the extraction stage consumes
   them.
4. **Extraction is triggered by PG change-detection, not called inline.** PG is the source of
   truth; a change monitor fans out to Weaviate / Semantica / Graphiti / "everything else." This
   decouples parse latency from extraction cost and lets any lane be rebuilt from PG.
5. **One AI chat → MANY domains.** Domain (lane) is assigned at the SEGMENT/TURN level, never
   one-per-file (ADR-0050 §3, PROJECT_CANON §3). A single conversation can land chunks in
   `platform`, `legal`, `personal_history`, and `relationship_timeline` at once.
6. **HITL verifies extraction output.** Extracted entities/timeline/artifacts are candidates until
   a human approves them (ADR-0002); approvals and denials are audited (ADR-0047).
7. **Everything is CLI-accessible; MCP wraps the CLI; agents run it via MCP** (ADR-0023/0046).
8. **Knowledge base first.** Process conversations → build the timeline → learn what evidence to
   hunt. Evidence/SMS ingestion is second. Google Timeline/Takeout is PARKED (ADR-0048/0049).

## Current reality — the gap this ADR authorizes closing (verified in code 2026-08-10)

This is what exists TODAY. None of it should be read as the target above being built.

- **Two disconnected ingest paths, not one:**
  - `build_chat_transcript_workflow` / `build_sms_xml_workflow`
    (`server/evidence/workflows.py`) — 4 steps: custody → parse → store → knowledge. The knowledge
    step (`_knowledge_step_impl`, `server/evidence/workflows.py:446`) calls `ingest_into_knowledge`
    with a SINGLE `domain` string. **No chunk / multipass / artifact / entity / timeline stage, and
    one-domain-per-file** — violates invariants 1, 3-as-flow, 5.
  - `server/analysis/context_chat_ingest.py` — a SEPARATE script: parse → ~~`chunk_records` → dual
    write to Weaviate `platform_context` + Graphiti CASE lane~~. This is where chunking + entities +
    timeline actually live today, OUTSIDE the evidence workflow.
    **Update 2026-08-12 (owner ruling "it's all supposed to go back into pg And then change detection
    will move it into vector db" · D-048 · sql/0021):** this path is now **PG-first** — parse →
    `store_context_records()` into **`working.context_record`** (a SEPARATE source-of-truth table,
    Option B: no evidence FK, so context never enters the evidence spine — ADR-0044 boundary) →
    `sync_pending_context()` projects the pending rows to Weaviate `platform_context` + the Graphiti
    CASE lane and stamps them synced. The dual-write-to-vector-store-directly design is retired; the
    SQLite `IngestLedger` is gone (PG `content_hash` UNIQUE + `*_synced_at` stamps are the dedup/sync
    authority now). It is still a separate path from the evidence workflow (invariant 1 not yet met),
    and it still bypasses SBV (invariant, ADR-0049 Gap 2 — AI-chat Go decoder exists but isn't the
    front door yet) and Semantica multipass (below).
- **Semantica is unwired.** `server/analysis/semantica_wiring.py` is called by neither path;
  multipass extraction + artifact extraction (ADR-0043) do not run in any ingest flow.
- ~~**No PG change-detection exists.**~~ **Partial, 2026-08-12:** the context path's projection is now
  a **change-detection-shaped** consumer — `sync_pending_context(sink)` reads rows
  `WHERE <sink>_synced_at IS NULL` (partial-indexed) and stamps them after projecting, so Weaviate/
  Graphiti are subscribers to PG state rather than inline targets, and any lane can be rebuilt by
  clearing its stamp. The consumer is exposed as a registered tool — capability
  **`ingest.context-drain`** (`server/tools/ingest/context_drain.py`) + CLI
  `scripts/drain_context.py` — so the batch projection is triggerable on demand from CLI/agent/MCP
  (owner 2026-08-12: "written as a tool ... so we can easily trigger that batch process ... until we
  do get the full workflow built out"). **Still deferred:** the generic trigger/outbox/cursor spine
  (invariant 4 for ALL paths, ADR-0052) — today the consumer is polled (inline after an ingest, or
  the drain tool / `--no-project`), not fired by a DB trigger. The evidence workflow still writes its
  Weaviate insert inline.
- ~~**AI chats do NOT go through SBV.**~~ **Update 2026-08-12 (D-049):** the parse step is now
  **engine-dynamic** — `parse_chat_export(engine="python"|"go"|"auto", format=...)` can route AI
  chats to the SBV Go service (`server/analysis/sbv_transcript.py`) OR the Python registry, per an
  explicit override (owner: "it shouldn't be dedicated to one format or the other"). The Go engine
  now has a ChatGPT decoder (D-047/4accbf2). **Still true:** `auto` defaults to Python for the MVP
  (detection router deferred), and only ChatGPT has a Go decoder so far (Claude/Perplexity/Gemini
  still Python-only). So AI chats *can* go through SBV on request, but don't by default yet.
- **HITL is native and works for writes (ADR-0002), but there is no HITL gate positioned AFTER an
  extraction stage** — because there is no extraction stage in the workflow yet.
- **SBV large-file upload + 0-message parse** need fixing before SBV can be the real front door
  (see the 2026-08-10 session finding; DEBT).

## Consequences

- This ADR does not authorize a big-bang rewrite. It authorizes **converging the two paths onto the
  one flow**, stage by stage, with per-stage verification (the ADR-0050 phased-plan discipline).
- The **PG change-detection spine** is the highest-leverage missing piece: once it exists, Weaviate,
  Semantica, and Graphiti become subscribers instead of inline calls, and the two paths collapse.
- Sequencing follows "knowledge first": prove one conversation end-to-end (parse → chunk → extract →
  entities/timeline → HITL → queryable per lane) before hardening evidence/SMS.
- Open design questions that need their own decisions:
  - **PG change-detection mechanism** — Postgres triggers vs `LISTEN/NOTIFY` vs logical replication
    vs polling. (Own ADR when chosen.)
  - **Where the segment→lane classifier runs** — inside SBV preview, or in the extraction stage.
  - **Whether extraction runs pre- or post-custody-approval** for evidence-tier material.

## Alternatives considered

- **Keep the two paths** (evidence workflow + context script) — rejected by invariant 1; it is the
  source of the drift this ADR exists to end.
- **Fold extraction into SBV** — rejected by owner directive: SBV parses and previews, then hands
  off. A parser that also extracts cannot be swapped or previewed independently.
- **Call extraction inline from the workflow** (no CDC) — rejected: couples parse latency to
  extraction cost, and keeps every new subscriber (a new lane, a new extractor) a code change in the
  workflow instead of a subscriber to PG.
