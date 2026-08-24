# Owner review — independently verified TODO audit (2026-08-18)

> _Byline: Claude Code · Fable 5 · 2026-08-18._
>
> **Purpose:** Codex (GPT-5) spent 2026-08-18 moving 70 stale/superseded documents from `docs/`
> into `docs/pending-review/` and writing a fresh `docs/MASTER-TODO-2026-08-18.md`. The owner
> asked for an **independent** second pass: reconcile every iteration of every task thread up to
> today, verify what Codex's MASTER-TODO claims against live code/tests/git/production Postgres
> (not just doc text), and hand back a single list of what's actually undone or ambiguous.
>
> **Method:** 9 parallel subagents — a read-only DuckDB probe against the live production
> Postgres (tailnet `100.91.190.107`), 4 code/test verification passes against MASTER-TODO's own
> claims, a full sweep of `docs/DEBT.md` + `docs/DECISION_LOG.md` + `docs/CHANGE-ORDER.md` +
> `docs/RULINGS-SHEET-2026-08-09.md` + `docs/UNRESOLVED-QUESTIONS-*.md`, and two sweeps of the 33
> handoff docs and 17 plan docs Codex moved into `docs/pending-review/`. Every claim below is
> traceable to a specific agent finding; nothing here is re-stated doc text taken on faith.

## Bottom line

**Codex's `MASTER-TODO-2026-08-18.md` is substantially accurate and did not overstate progress
anywhere this audit checked.** Every "IMPLEMENTED LOCAL ONLY" / "IN PROGRESS" / "HELD" claim it
makes was independently confirmed against real code, real tests, or the real production
database. Its self-imposed caveat — "no item is DONE+LIVE VERIFIED" — is itself verified true:
the production Postgres has **zero rows** in every table the newest work would populate
(realization/walk/pass-grant tables don't exist at all; ADR-0059 message-projection tables don't
exist at all; the chat pipeline tables exist but hold 0 rows).

What Codex's document is missing is **coverage**, not accuracy: several real work threads (an
entire "Investigation/Behavioral Analysis" surface, the parser-lane debt backlog, the MCP
registry/ContextForge↔Portkey split, the backup lane, TraceIQ) never made it into its 11-row
status table, and its own `docs/HANDOFFS.md` index has two factual defects (see Part 2). This
audit also caught one claim living outside MASTER-TODO — `docs/INDEX.md`'s "the worktree is
clean" — that is flatly false right now.

---

## Part 1 — What's independently CONFIRMED (code/test/DB level, not "live verified")

| Surface | Verdict | Evidence |
|---|---|---|
| Custody/ingest/parser spine (`server/evidence/`, `server/contracts/`) | Real, substantial, tested | `custody.py`(546L), `store.py`(848L), `workflows.py`(1203L) — no stubs; 153 passed/1 skipped |
| ADR-0059 message projection (`server/evidence/message_projection.py`) | Real, matches ADR, fail-closed owner-exclusion check present | 586L; migrations `sql/0026-0029` build exactly what's claimed |
| Weaviate cutover runbook | HELD, blue target populated, no alias cutover, matches claim exactly | `docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md` |
| Agno FilterExpr-drop landmine (AGENTS.md warning) | STILL PRESENT, confirmed at cited line numbers | Installed agno is **2.8.6**, `weaviate.py:414-416,441-443,883-885` |
| Phase 4 agent→lane wiring (six-lane KB) | Confirmed NOT started, matches "NEXT" note from 2026-08-11 | Zero matches for `lane`/`KnowledgeHandle`/`create_knowledge` in `factory.py`/`providers.py` |
| Evidence-desk / human-review drill-through (`workbench/`) | Real, substantial, tested — NOT a mockup | Full chain `get_matter→get_evidence_detail→...→review_evidence_item`; 47/47 tests pass |
| Workbench live instance | Reachable and healthy | `GET 100.72.169.40:8020/health` → real `200 OK` `{"status":"ok",...}` |
| Horizon-walk migrations (`sql/0026-0029`) | Exist, correct, explicitly marked **NOT APPLIED TO PROD** in their own headers | `0029` even notes the app connects as Postgres superuser, so its deny-by-default grants would be inert even if applied |
| Realization agent tools (`realization_tools.py`) | Really wired into every agent via `providers.py:192` | Not just a comment — genuine import + append |
| Graphiti↔Neo4j agent binding | Real, env-gated | `providers.py:194-207` |
| Surreal R14 vs. production Horizon walk | **Two separate efforts, correctly kept apart** | R14 runs against a fully isolated synthetic Coolify app/network; its own text says it never touched prod Postgres, prod Horizon route, prod agents, or Graphiti |
| Surreal investigation thread overall | Accurately "parked design-only, no activation" everywhere reviewed | 17 plan docs + `COORDINATION.md` R10-R14 blocks agree |

**Production Postgres reality-check (live, read-only probe, 221 tables across 7 schemas):**

| Table | Exists? | Rows |
|---|---|---|
| `working.context_record` | yes | 1,741 |
| `working.normalized_record` | yes | 11 |
| `evidence.evidence_hash` | yes | 3 |
| `evidence.custody_event` | yes | 0 |
| `analysis.human_label` / `human_label_gold` | yes | 1,918 each |
| `ops.audit_ledger` | yes | 7 |
| `working.chat_conversation`/`chat_message`/`chat_chunk*` (8 tables) | yes (structure only) | **0** |
| `message_projection`, `first_party_message`, `acquired_third_party_message` | **NO** | — |
| `matter`, `court_case` | **NO** (migration 0030 unapplied) | — |
| `realization_event`, `realization_link`, `walk_ledger`, `pass_grant*` | **NO** (0026-0029 unapplied) | — |

---

## Part 2 — Contradictions and drift found

1. **`docs/INDEX.md:46` says "The worktree is clean" — FALSE right now.** Live `git status` shows
   a dirty tree with many uncommitted changes (docs reorg, SurrealDB runner files, `AGENTS.md`,
   compose/deploy yaml). This is a live-checkable claim that was wrong at time of writing.
2. **`requirements.txt:3` pins `agno==2.8.7`; the installed venv is running `2.8.6`.** The
   FilterExpr-drop landmine warning in `AGENTS.md` (verified "STILL PRESENT... re-verified 2.8.7")
   was actually re-verified against 2.8.6 — the pin and the running code disagree. Re-check the
   landmine once the venv is actually upgraded to 2.8.7.
3. **`docs/DECISION_LOG.md` D-030 vs. `AGENTS.md`'s stack line on LiteLLM.** D-030 (2026-07-29)
   records LiteLLM retirement as "done (docs; teardown pending)" — the container was never torn
   down. `AGENTS.md` states flatly "LiteLLM retired" with no caveat. DECISION_LOG is the more
   precise, and equally current, source — treat teardown as **not actually done**.
4. **`docs/HANDOFFS.md` (the current handoff index) has two factual defects:**
   - Its R14 row ("Core live gates pass / full set partial") doesn't surface that the R14 file
     itself now carries a 2026-08-18 addendum saying its results predate ADR-0059's new contract
     and are **not current live proof**. A reader trusting only the index table would over-credit
     R14.
   - Two of its prose links (`GOALS-2026-08-15-surreal-investigation-memory.md`,
     `SURREAL-INVESTIGATION-BLUEPRINT-2026-08-15.md`) point at `docs/`, but both files were moved
     to `docs/pending-review/plans/` in today's reorg — broken links.
5. **The 2026-08-09 "S1–S10" handoff series has zero coverage in `docs/HANDOFFS.md`'s index.**
   Cross-referencing suggests it was folded forward into the R0–R9 series (e.g., S6's
   horizon/derivation work → R2 "Horizon engine," still "Partial"), but nothing in the current
   docs states this explicitly. A reader has no way to know these 10 files are superseded rather
   than abandoned.
6. **The realization/walk/derivation test count doesn't match a session-memory figure.** Memory
   cites "688 passed/24 skipped" for Wave-1 gates; the current full collection is **938/939
   tests**. The scoped realization/horizon/walk/derivation slice is unambiguously green (56
   passed/1 skipped) either way — but the 688/24 figure is stale and shouldn't be quoted as
   current.
7. **Retrieval-side horizon filtering has no wiring at all — not just "not applied to prod."**
   `grep -rn "app.horizon" server/**/*.py` returns **zero matches**. Even if migrations 0026-0029
   were applied today, nothing in the app sets the `app.horizon`/`app.case_id` session GUCs that
   `working.vw_spine_horizon` reads. MASTER-TODO's "production activation... remains held" is
   accurate but understates how much retrieval-side work is still undone — this is a real gap in
   the codebase, not just a deploy gate.

---

## Part 3 — Gaps: real work threads missing from MASTER-TODO's 11-row table

- **Investigation Search / scoped Behavioral Analysis surface** (DECISION_LOG D-062/D-063,
  candidate-claim evidence assembly, design-only as of 2026-08-15) — no row anywhere in
  MASTER-TODO. `docs/INDEX.md` mentions ADR-0056–0058 add this design; it's real scope, currently
  untracked in the master ledger.
- **CDC worker / replay / alert lane** (`docs/DEBT.md`, ADR-0053 follow-ups) — no row.
- **MCP registry / ContextForge↔Portkey split gateway** — dedicated PG DSN, migration, credential
  provisioning all outstanding, absent from MASTER-TODO entirely.
- **Parser-lane debt items 0, 0b, 2, 3, 4, 5** (`docs/DEBT.md`) — ADR-0044 blob-ban unenforced in
  code, Python SMS-XML iterative/file-spill directive (owner, 2026-08-10), cross-parser
  ingestion writer/backpressure, registry priority/quality metadata, ChatMiner hardening, repair-
  layer wiring. None named in MASTER-TODO.
- **Court-readiness custody-event digest writer/verifier versioning debt** (2026-08-15) — not
  mentioned.
- **Recurring backups lane** — only a one-time host-retirement snapshot script exists (skips
  Neo4j/Milvus); MASTER-TODO's "Backup" row doesn't call this out specifically.
- **TraceIQ geo projection** (UQ-27–29) — no TraceIQ row anywhere.
- **Graphiti-replacement bake-off criteria** (UQ-30–33) — MASTER-TODO's Graphiti row doesn't
  mention the bake-off gate at all.
- **R2 blob upload still `dry_run`** (CHANGE-ORDER CH-1, 0 objects actually uploaded) and the
  **fresh-from-zero schema-restore gap** (CH-5c, needed for Wave 5) — neither mentioned.
- **`evals` harness still stubbed** — `CASES: tuple[Case, ...] = ()`.
- **Classifier-quality eval, OCR/VLM provider benchmark, multimodal embedding, timeline-
  extraction workers, investigation-register UI** — all listed under "ADR-0053 implementation
  follow-ups" in DEBT.md, no corresponding row.

---

## Part 4 — Owner-decision-blocked items (NOT engineering debt — distinct category)

These are not "undone work" in the normal sense; they're stalled on a decision only the owner
can make. Surfacing them separately so they don't get conflated with straightforward build work.

**Still open — never actually ruled on** (from `docs/pending-review/plans/PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md`; the doc's own compact-ruling recommendation was never confirmed by the owner):

- **P1** People authority — is `analysis.matter_person` Matter-local, or must every person tie back to `working.person`?
- **P2** Review meaning for an operator-created person — usable immediately at `safe_for_legal_use=false`, or does creation imply approval?
- **P3** Role cardinality — single optional `primary_role` now, vs. a normalized many-role table now?
- **P4** Court-specific timeline membership — explicit scope table, vs. every event auto-appearing in every CourtCase?
- **P5** Cross-Matter identity — Matter-local profiles only, or a global canonical-person registry now?
- **R1** Combined vs. separate authentication/court-release decisions?
- **R2** Confidence policy — never auto-upgrade default-low, vs. derive medium/high from model scores?
- **R3** First mutation supports only `hash_chain_of_custody`, vs. expose every authentication label now?
- **R4** Does `redaction_status=none` alone satisfy readiness, or must a release decision explicitly affirm no redaction is needed?
- **R5** Who may release to court — re-authenticated confirmation, vs. any valid Workbench session?
- **R6** Should evidence court-release couple to source custody `released` status, or stay independent?
- **A1–A4** — approve the disposable canonical-image rehearsal + migrations 0026–0030; name the apply target; provision distinct `WORKBENCH_API_KEY`/`AGENTOS_API_TOKEN`; approve the exact Workbench deploy/live-proof scope. (Doc marks A1 approved, A2-A4 held pending A1's report.)

**Other standing owner-only items:**
- **D-001** — Cloudflare Global API key rotation (owner-only; still OPEN).
- **UQ-17, 19, 21/22, 24/25, 30** — explicitly flagged "Later owner review" in
  `docs/UNRESOLVED-QUESTIONS-2026-08-16-surreal-investigation-phase0.md`.
- A larger block of Owner/Contract/Empirical-class unresolved questions (UQ-03, 05, 06, 09-15,
  20, 23, 26-29, 31-33) gate R10-series Phases 2-7 — deferred by design, not stalled work.
- **Weaviate cutover and MCP-registry control-plane** each require a separate owner-approved
  activation gate per `docs/DEBT.md` — explicitly "activation held," not stalled engineering.

---

## Part 5 — Ambiguous items needing explicit owner clarification

1. **"Horizon walk" vs. the Surreal R-series both read as "IN PROGRESS"/"held," but they are two
   unrelated efforts sharing vocabulary** (horizon, walk, sealed snapshot, rewalk). The actual
   production mechanism is the Postgres realization/walk-ledger migrations + `derivation.py`/
   `realization.py` (held pending owner apply). The Surreal R-series is a small, disposable,
   fully isolated prototype that validates horizon-filter *concepts* in SurrealDB syntax and
   never touches prod. **Recommend**: the master ledger should list these as two distinct rows so
   R14's "core live gates pass" can never be mistakenly credited toward the real Postgres
   Horizon-walk readiness.
2. **`RELEASE-CUSTODY-2026-08-15.md` claims "partitioned commits pushed to main"** — this claim
   was flagged for verification by the plans-sweep agent but not independently confirmed in this
   pass. Needs a direct `git log` check against the specific commits named in that file.
3. **`PLAN-2026-08-15-platform-runtime-migration.md`** (the 10-wave AG2/polyglot migration plan)
   reads as a firm "Decision summary"/"Governing invariants" document with no owner-approval
   disclaimer, unlike the Surreal-thread docs — but `MASTER-TODO-2026-08-18.md` never references
   this wave framework at all, and `COORDINATION.md`'s R0-R9 table shows every lane as "Partial"
   or "Research complete." Recommend treating this plan as an **unapproved/aspirational
   architecture proposal**, not a committed roadmap, until the owner explicitly confirms it —
   MASTER-TODO wins on any conflict.
4. **Whether the Weaviate-cutover DEBT row and the MCP-registry-control-plane DEBT row need one
   owner sign-off or two separate ones** — DEBT.md gates each behind "a separate owner-approved
   release/activation gate per step," but it's not clear whether these are sequential or
   independent asks.

---

## Part 6 — Consolidated action list for next session

**Immediate (matches MASTER-TODO's own critical path, independently confirmed as still accurate):**
1. Inventory current SHA, dirty worktree (confirmed dirty — see Part 2 #1), Coolify app/watch
   paths, environment, and the old `100.72.169.40:8020` endpoint's actual deployed commit (no
   `/version` route exists — this needs Coolify dashboard/API access this desktop doesn't have).
2. Commit or discard the current dirty tree before anything else ships.
3. Correct `docs/INDEX.md:46` ("worktree is clean" → false) and the two broken links in
   `docs/HANDOFFS.md` in the same pass — per this repo's own doc-drift rule, fix stale claims the
   moment they're found.
4. Add the S1-S10 folding note to `docs/HANDOFFS.md` and the R14-supersession note to its own row.
5. Resolve the `agno` version drift (pin says 2.8.7, venv has 2.8.6) — upgrade or re-pin, then
   re-verify the FilterExpr landmine against whichever version actually ships.

**Structural (owner should see before more work is scheduled):**
6. Add the five missing surfaces from Part 3 to the master ledger, or explicitly rule them
   out-of-scope for now.
7. Get the 15 pending Matter-MVP P/R/A decisions (Part 4) in front of the owner — they're
   blocking the same evidence-desk work the critical path already prioritizes.
8. Decide whether `PLAN-2026-08-15-platform-runtime-migration.md` is live scope or shelved
   (Part 5 #3) — right now nothing tracks it either way.

**Engineering (real undone work, not blocked on anything):**
9. Retrieval-side horizon filtering has zero wiring (Part 2 #7) — this is separate from and
   larger than "apply migrations 0026-0029."
10. Phase 4 agent→lane wiring for the six-lane KB build — confirmed not started.
11. `evals` harness `CASES=()` stub, R2 blob-upload `dry_run`, recurring-backup lane (Neo4j/Milvus
    not covered) — all real, bounded, unblocked engineering tasks.
