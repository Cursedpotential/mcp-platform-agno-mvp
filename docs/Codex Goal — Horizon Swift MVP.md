# GOAL — Horizon Swift MVP (usable ingest → Workbench → minimal Surreal)

> _Byline: Owner-provided goal · captured by Codex · GPT-5 · 2026-08-16_
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

You are Codex working in `Cursedpotential/mcp-platform-agno-mvp` (Horizon).

This is a **persistent goal**, not a research ticket. Keep shipping a thin vertical slice until the acceptance tests below pass, or until you are blocked on an explicit owner hold. Do not stop at documentation. Do not re-derive architecture that already exists. Do not expand into Waves 4–10, Agno retirement, Graphiti replacement, AG2 bake-off, OpenCode, or court export.

Read these first, in this order, then start implementing:

1. `AGENTS.md`
2. `docs/PROJECT_CANON.md` §1 (knowledge-horizon mechanism — non-negotiable)
3. `docs/HANDOFFS.md` (current R0–R12 index)
4. The attached / referenced audit: **Horizon Platform Audit — R0–R12 Baseline** (workspace file `horizon_audit_report.md`, including the 2026-08-16 Swift-MVP addendum)
5. `docs/PLAN-2026-08-15-platform-runtime-migration.md`
6. `docs/ARCHITECTURE-BLUEPRINT-2026-08-15.md`
7. `docs/PRODUCT-BLUEPRINT-2026-08-15.md`
8. `docs/GOALS-2026-08-15-surreal-investigation-memory.md` (for Surreal non-goals and S1–S6 only)
9. `docs/DEBT.md` and `docs/DECISION_LOG.md` entries D-040, D-046, D-060, D-064
10. Skill `sequential-react-ship` (attached). If the host cannot load it, treat the attached `SKILL.md` plus `references/thinking-reversibility.md`, `references/thinking-map-territory.md`, and `references/thinking-pre-mortem.md` as the operating method.

If the audit and a handoff disagree, **prefer source + the dated R-series + ADRs**. If you cannot verify a claim, record it as unverified rather than inventing a fix.

---

## Operating method (mandatory)

Run this entire goal under `sequential-react-ship`. That skill is the conductor. Do not re-implement it here.

- **Spine:** numbered sequential thoughts (`ORIENT → CLASSIFY → PREMORTEM → PLAN → REACT → REVISE/BRANCH → CLOSE`). Revise out loud. Do not skip.
- **Motion:** ReAct — one `Thought` → one `Action` → one `Observation` per loop. Observation is territory. No Observation means you only have another map.
- **Load, do not rewrite:**
  - Before choosing how to proceed: `thinking-reversibility` (Type 1 / 1.5 / 2). Type 2: decide and ship locally. Type 1: HITL packet, then the next Type 2 slice. Never idle on a hold.
  - After a plan exists, before the first Act of a slice or any Type 1 door: `thinking-pre-mortem` (past tense, 5–10 reasons, top 3 become tests/holds/rollback). A pre-mortem with no plan change did not happen.
  - After every Observation and before any status claim: `thinking-map-territory`. Handoffs, ADRs, green tests, and `STATUS: COMPLETE` are maps. Running commands, live env, and file contents are territory. `BUILD_STATUS` is `UNKNOWN` unless you ran the named checks.

Show the slice card (Slice / Sequential / Holds / BUILD_STATUS) at the start and close of every slice. Keep the thought stream short during routine Type 2 edits; make it visible whenever a door type, hold, or BUILD_STATUS is at stake.

---

## North star

A local operator can:

1. Ingest knowledge (folder-walk **and** at least one SBV-covered export) through a **framework-neutral ingest port**.
2. See the ingested items in the **custom Workbench** (`/intake` progress, `/knowledge` browser, Matter-scoped view if the local `0030` slice is applied).
3. Query a **minimal Surreal analytical surface** bound to one immutable `HorizonContext` — a new disposable instance, never the parked Agno operational Surreal.
4. Stream a basic operator chat in Workbench via the **Vercel AI SDK** against framework-neutral routes, not AgentOS Studio.

That loop is the product. Everything else is later.

---

## Why this goal exists (from the audit)

The repo is over-documented and under-looped:

- Ingest is still Agno-central: `scripts/ingest_knowledge.py` calls `knowledge.ainsert()`.
- SBV is PRIMARY again (D-040 / PR #18) but `_sbv_enabled()` is false whenever `SBV_SERVICE_PASS` is empty; compose defaults it empty, so traffic silently hits the Python SMS-XML fallback.
- Semantica is VIP (ADR-0043 / R3) but `server/analysis/semantica_wiring.py` only emits config dicts — no worker, no candidate submission, no observed write.
- Chonkie wrappers exist (`server/analysis/chonkie_chunkers.py`) and D-046 install+verify is DONE, but `chonkie` is not in `requirements.txt` and `chunking_policy.py` defaults to Agno `RecursiveChunking` (`tuned=False`).
- Workbench already has `/intake`, `/knowledge`, `/matter`, `/evidence-queue`, but `workbench/web/package.json` has **no** `ai` / `@ai-sdk/*`.
- Surreal Phase-0 contracts pass (18 tests). Live adapter proof is UNKNOWN. `compose.data-surreal.yaml` is PARKED — do not deploy or reuse it.
- R9 holds remain: migration `0030` unapplied in live, Workbench key unprovisioned, no Coolify/Weaviate/Graphiti mutation.

Do not “fix” items the audit marks out of MVP scope (recurring backups, NIM→Portkey embedder, eval harness expansion, Go parallel import).

---

## Invariants (never violate)

1. PostgreSQL is canonical. Original bytes stay in custody-controlled object storage.
2. Extraction is horizon-blind. Agent experience is horizon-bound. No future fact enters retrieval, prompts, traces, Graphiti, or Surreal as-lived reads before activation.
3. One authored store. Derived pass materializations are allowed (ADR-0045 §B). Parallel authored as-lived/hindsight stores are forbidden.
4. Engine selection is **coverage-based, never size-based**. Go/SBV is primary for every format it covers.
5. Semantica is VIP: integrate it fully, never fork around it, never give it custody authority. Candidates submit through a governed promotion API. Correct S8’s direct-Neo4j worker drift; ADR-0043 wins.
6. No framework object crosses a public/domain contract. Agno may remain a **shadow adapter**. It must not own ingest, Workbench, or Surreal ports.
7. Self-host Next.js + Vercel AI SDK. Do **not** claim to self-host Vercel Functions or Vercel Sandbox.
8. Nothing is permanently deleted; superseded material moves to `to_be_deleted`.
9. `BUILD_STATUS` is UNKNOWN unless you actually ran the named checks.
10. All production / live-host writes, Coolify mutations, parked-Surreal contact, corpus copy onto Surreal, and Graphiti replacement stay **HITL / owner-gated**.

---

## VIP components — integrate around, never overwrite

Agno (current adapter only), custom Graphiti, **Semantica**, IBM ContextForge, **forked SBV**, CopilotKit. Keep Portkey, OpenCode, agent-sandbox, persistent Kasm.

---

## Work order (do in this sequence; finish each gate before starting the next)

### Slice 0 — Make the existing surfaces actually reachable (local only)

- Provision a local `WORKBENCH_API_KEY` and `SBV_SERVICE_PASS`. Fail closed. Do not deploy.
- Confirm `platform-tools` / SBV image `ghcr.io/cursedpotential/sbv-forensic:0.2.4-forensic` is the ingest path, facade on :8085, host map 8080:8085.
- Apply migration `0030` **only** to a local/scratch Postgres, never live, unless the owner explicitly lifts the R9 hold.
- Gate: Workbench `/health` public; every other Workbench route 401 without the key and 200 with it. SBV authenticates. One `GET` of SBV import API succeeds.

### Slice 1 — Framework-neutral ingest port (demigrate off Agno-central)

- Create a platform-owned ingest contract (HTTP + in-process) that does **not** import Agno, Graphiti, AI SDK, or Surreal clients.
- Inputs: staged file path or upload id, source identity, coverage hint, matter/case id (default `primary`).
- Pipeline: coverage route → SBV/Go when it matches, Python fallback otherwise → normalize → Chonkie chunk → persist canonical PG rows → optional Weaviate projection if the local store is up → emit an ingest receipt (ids, hashes, parser_id, chunker version, counts, rejections).
- Rewire `scripts/ingest_knowledge.py` and Workbench `/intake` “Start run” to this port. Agno `ainsert` may be called *behind* the port as a temporary projector, not as the public contract.
- Enforce ADR-0044: `transcripts.markdown` / whole-file fallback must not be reachable from the evidence lane. Add the DEBT.md regression test.
- Optional same-slice win: wire `sms_xml.parse()` through existing `iter_records()` and spill to NDJSON (audit: load-bearing fallback).
- Gate: contract tests import no Agno. One markdown/pdf folder-walk and one SBV-covered export both produce PG rows visible to the knowledge API.

### Slice 2 — Chonkie in the live ingest path

- Pin torch-free `chonkie[semantic,code,table]==1.7.0` in `requirements.txt` (D-046 step 4).
- Turn on the existing wrappers in `server/analysis/chunking_policy.py` for knowledge + transcript lanes. Keep Neural/Late/Slumber remote-only. Never install torch.
- Version the chunker in the ingest receipt.
- Gate: unit tests for wrappers pass without mocking “chonkie not installed”; a real ingest receipt names a `chonkie.*` chunker.

### Slice 3 — Workbench as the operator product (Vercel AI SDK)

- Keep `/intake`, `/knowledge`, `/matter`, `/evidence-queue`. Do not clone AgentOS Studio.
- `/intake`: upload → coverage decision → parser/SBV progress → receipt. No blind promote box.
- `/knowledge`: list ingested items with domain filter, source path, parser, chunker, hashes; open one item and see chunks + provenance. Graphiti pane stays read-only and labeled “memory, not evidence.”
- Add Vercel AI SDK to `workbench/web` for one operator chat/stream against a **framework-neutral** `/v1` route. Frontend must not import Agno or AG2 types.
- Self-host Next.js. No Vercel Functions, no Vercel Sandbox.
- Gate: operator can ingest a file in `/intake` and immediately find it in `/knowledge` without using AgentOS UI or a CLI except as a fallback.

### Slice 4 — Semantica VIP, governed candidates only

- Treat Semantica as the semantic-intelligence service. Do not replace, dilute, or fork around it.
- Freeze ExtractionPort: immutable normalized batch in; candidates + provenance out; zero custody writes; zero direct Neo4j/Weaviate/Surreal writes.
- Isolated worker image / in-process adapter that actually runs on a synthetic fixture (NER + relation/event candidates + provenance). First slice only.
- Promotion remains a human/platform step into PostgreSQL.
- Gate: one fixture batch produces candidate rows in PG (or a clearly named candidate table) with provenance; Semantica process has no credential that can write `evidence.*`. Observed behavior, not config-only. `semantica_wiring.py` is no longer the only runtime.

### Slice 5 — Minimal Surreal surface (disposable, owner-gated)

- Do **not** touch the parked Surreal in `compose.data-surreal.yaml`.
- Do **not** copy the live corpus, replace Graphiti, or activate production Surreal.
- Implement the smallest live adapter that satisfies Phase-0 contracts + R12 S1–S6 for **one** Matter:
  - shared Context, Matter scope
  - project approved/promoted items + chunks only
  - `HorizonContext`-bound retrieve
  - fail closed on drift; seal + linked rewalk, do not silently fallback to PG for as-lived reads *after* owner has declared parity (until then, label the pane “projection, not authority”)
- Workbench: one “Surreal projection” pane that can answer “what is in the projection for this item/horizon?” and shows source ids + hashes.
- Gate: 18 existing framework-neutral contract tests still pass; plus one *live* adapter test against an isolated disposable instance that you created locally. If the owner has not approved target creation, **stop at a complete adapter + compose overlay + runbook** and file the HITL packet. Do not invent a target.

---

## Explicit non-goals

- Reactivating Surreal as Agno’s operational DB.
- Moving canonical evidence, custody, or approval out of PostgreSQL.
- Shadow cutover / Agno retirement (Wave 10).
- AG2 bake-off, OpenCode workspace, provider-hot-switch GUI, TraceIQ, behavioral agent, court-safe export release.
- Go parallel imports (global mutex may stay for MVP).
- Recurring R2 backups, NIM embedder via Portkey, filling `evals/cases.py` with Agno evals.
- Applying migrations `0026`–`0030` or any Surreal schema to **live** hosts.
- Contacting the parked Surreal deployment.

---

## How to keep moving when stuck

Follow `sequential-react-ship` CLOSE + next-slice rules first. Then:

- If a hold is in force (R9 activation, R10/R11 no-production-change, parked Surreal): that is a Type 1 door. Implement locally, write the owner packet, CLASSIFY the next Type 2 slice, and continue. Do not idle.
- If docs disagree: map-territory. Trust running tests + source, then write a one-paragraph drift note in the slice handoff. Do not start a new architecture document.
- If you want to deepen Agno usage: stop. Put the capability on a framework-neutral port instead.
- If a finding in the audit looks wrong: re-verify against source the way `docs/DEBT.md` already does (file/line). Record REFUTED or CONFIRMED. Do not silently skip.
- Commit in PR-sized slices with tests. Update `docs/DEBT.md` when you close a row. Do not edit VIP upstream trees except via the existing vendored/fork workflow.
- After each slice: run the focused tests you touched + Ruff/format for those paths. Quote real counts. `BUILD_STATUS=UNKNOWN` if you did not run them.
- Anti-patterns from the skill still apply here: five planned Actions with no Observation; shipping a handoff; walking through a Type 1 door because the local path worked.

---

## Definition of done (stop condition)

All of the following are true, with evidence:

1. A local operator with `WORKBENCH_API_KEY` can upload or folder-walk a knowledge file in Workbench and see it in `/knowledge` with parser id, chunker id, and source hash.
2. At least one SBV-covered export is ingested via the Go/SBV path (`SBV_SERVICE_PASS` set; receipt `parser_id` is SBV, not `messages.sms-xml` / `transcripts.markdown`).
3. Ingest and Workbench talk to a framework-neutral port; contract tests for that port import no Agno / Graphiti / Surreal / AI SDK.
4. Prod lockfile includes torch-free Chonkie; a real ingest receipt names a `chonkie.*` chunker.
5. Semantica produces observed candidate+provenance output on a fixture without writing custody.
6. Either (a) a disposable local Surreal instance serves a HorizonContext-bound retrieve that Workbench can display, or (b) the adapter + compose overlay + owner HITL packet is complete and clearly waiting on target approval — not silently using the parked instance.
7. Workbench has one Vercel AI SDK chat/stream against a neutral `/v1` route. No AgentOS UI is required for the loop.
8. Audit items in scope (Agno-owned ingest, empty SBV password, Semantica config-only, Chonkie not in lockfile, no AI SDK, parked-vs-new Surreal) are updated in `docs/DEBT.md` as resolved or explicitly still-held.

When those eight are true, stop and write `docs/HANDOFF-YYYY-MM-DD-swift-mvp.md` in the existing HANDOFF v2 shape (verified state, BUILD_STATUS with real counts, remaining holds, next recommended slice). Do not invent Wave 11 work.

---

## Owner working style

Small self-contained units. HITL on any live write. Prefer building the already-sanctioned design over new ADRs. Verify observed behavior, not accepted configuration. Closest `AGENTS.md` wins inside a subtree.
