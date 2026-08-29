# HANDOFF S4 — ADR package + owner rulings sheet
> _Byline amendment: Codex · GPT-5 · 2026-08-18 (ADR-0059 supersession)._
> **ADR-0059 supersession addendum (2026-08-18, Codex · GPT-5):** Retain this handoff as
> historical evidence. Its universal realization/occurrence visibility rule is superseded:
> first-party source availability equals occurrence, acquired-third-party availability equals
> acquisition, and realization is zero-to-many linked knowledge. ADR-0045 §B's one-authored-spine
> rule remains. This addendum authorizes no deployment, migration, corpus copy, or live activation.
>
> _2026-08-09 · repo @ a68fabd · STATUS: READY · Depends: none · Blocks: S6 (ADR-0045), S5 (ADR-0047)_
> Inventory items: FA(ratification), SD-2, SD-9(void record), DA-1..9, M-2, TR-5(draft half), R-2 entry, OQ-1..11 dispositions.
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.

## Goal
Draft three ADRs for owner signature and present the consolidated rulings sheet. Drafting is
agent work; SIGNING is owner-only. Nothing in S6 ships until ADR-0045 is signed.

## Tasks
1. **Draft ADR-0045 — Horizon clocks & checkpoint-derivation architecture.** Sections:
   - Context: N1/N2/N3 (predicate keyed on superseded knowledge_time; clocks unwritten; tier
     hardcoded); FA (six-clock ruling exists only in COMPACT-SUMMARY-2026-08-01 — ratify it here);
     the 08-02→08-05 clock timeline.
   - Decision A (clock): `visible_from = COALESCE(realized_at, occurred_at)`; `acquired_at` = custody
     metadata only (document the bulk-acquisition failure case: 2026 acquisition of 2023 exports
     would blank historical horizons); `knowledge_time` frozen as row-write audit clock per 0008.
     Options table: (A) predicate-computed COALESCE + expression index [recommended] vs (B)
     materialized `visible_from` column (EXPLAIN legibility vs one more driftable field).
   - Decision B (derivation architecture, canon §1 amendment): parallel AUTHORED stores remain
     forbidden; version-pinned DERIVED pass materializations sanctioned under four conditions —
     refresher is sole writer (grant-enforced) · base-store version recorded per checkpoint ·
     every derivation hash-attested to audit ledger · cross-lane cuts from one base version.
     As-lived = incremental per walk step; hindsight = on-prompt. ONE predicate function, two
     schedules. Walk-ledger = the as-lived derivation log, chain-hashed, Postgres `working.*`
     (CLOSES OQ-1; supersedes sql/drafts walk_ledger HOLD rationale).
   - Decision C: disclosure_tier target type on working.normalized_record — TEXT+CHECK (as-built)
     vs ai.disclosure_horizon enum (as AGENTS.md claimed). Recommend TEXT+CHECK stands; AGENTS.md
     corrected (S1).
   - Consequences: S6 implementation map; analysis/observation tables append-only with
     (pass, run, base_version) attribution.
2. **Draft ADR-0046 — Universal MCP exposure contract.** Pays canon §5 item 11 "needs ADR".
   Contents: progressive disclosure quad (search_tools→describe_tool→invoke_tool→get_ref);
   ADR-0035 subnamespacing; annotations (readOnlyHint/destructiveHint mandatory — HITL visibility);
   pagination on evidence-returning tools; actionable errors; **horizon-binding rule**: evidence-
   reading MCP tools resolve HorizonContext server-side (pass_id ref), never accept a client
   horizon timestamp; hindsight = credential grant; fail-closed (no context → zero rows, loudly).
3. **Draft ADR-0047 — Audit-everything ledger.** Owner VIP ruling 2026-08-09: every decision,
   action, modification, and READ audited. `ops.audit_ledger` append-only, hash-chained
   (prev_hash — pattern from SBV repair ledger + evidence.custody_event): actor, action_type
   (decision|write|read|tool_call|approval|derivation), object ref, HorizonContext snapshot,
   base_version, ts. Retrieval: on-demand dump/query. Never multi-user — single-operator schema.
4. **DECISION_LOG entries** (drafts, each with an allocated D-NNN id — S1/S2 cite these ids and
   are gated on this task): (a) six-clock ruling ratification (backdate-note 2026-08-01, ratified
   2026-08-09); (b) SBV promotion to primary (2026-08-05, PR #18) so code/tests can cite it
   (TR-3/TR-5); (c) **R-2: never multi-case / never multi-user** (owner, 2026-08-09) — the most
   load-bearing ruling of the session; this entry also formally voids SD-9's multi-case/multi-user
   "revisit" items. Committing into docs/DECISION_LOG.md is S1 task 15, after owner approves text.
5. **Rulings sheet** (one page, yes/no per line, for owner):
   - OQ-4/OQ-6: sign ADR-0045 (Option A/B choice + tier type).
   - OQ-8: hindsight/discovered emitters — HITL-only, or trusted lanes (AI-chat) auto-assert?
   - OQ-9: PR #18 = Phase 5a shipped? (canon §6 wording follows)
   - OQ-10: Milvus cutover verified? → drop Dockerfile pymilvus or declare in pyproject.
   - OQ-11: sign D-008 (RESTART-0001 evidence schema) — gates S9 population.
   - OQ-2: extracted-code/ + MANIFEST.md — consumed (strike canon line) or workspace-side (mark
     workspace-relative)?
   - OQ-7: database/schema/00_analysis_graph.surql — `_stale/` or port design to Neo4j first?
   - Record CLOSED items for the log: OQ-1 (walk-ledger, by DA-6), OQ-5 (case_id, by never-multi-case).
   - OQ-3 is NOT an owner ruling — it is a live probe task, executed in S6.

## Acceptance
Three ADR drafts in `docs/adr/` numbering style, marked **Status: Proposed** until owner signs.
Three DECISION_LOG entry drafts with allocated D-NNN ids (grep-able: `grep -c "D-0" <draft>` = 3).
Rulings sheet: one line per OQ-2/4+6/7/8/9/10/11, each answerable yes/no or with one choice,
plus recorded closures for OQ-1/OQ-5. All new files carry traceability headers.

## Constraints
Standing constraints per PLAN master. Do not renumber existing ADRs. Do not mark anything
Accepted without explicit owner signature.
