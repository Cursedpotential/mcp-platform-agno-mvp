# HANDOFF S6 — Horizon spine & derivation engine (the core)
> _2026-08-09 · repo @ a68fabd · STATUS: BLOCKED until ADR-0045 SIGNED + OQ-8 ruled · Depends: S3, S5 · Blocks: S8, S9_
> Inventory items: N1, N2, N3, N4, N6, N7, FD, F-E, SD-1..8, DA-1..9(execution), DA-11, M-1(D9), TR-3(0018 half), OQ-3 probe.
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.
> ORDERING IS NON-NEGOTIABLE: task 0 first; tasks 1–3 before 4–10; task 10's migration rides task
> 4's 0022. Binding readers before the clocks are real admits the whole corpus while every test
> passes — the most dangerous failure mode this platform has.

## Goal
Clocks real → derivation engine attested → every read lane (Postgres, Weaviate, Graphiti, MCP,
context lane) bound and audited. After this segment, "what did Pass N know" is a hash-attested,
reproducible artifact.

## Tasks
0. [DA-9 execution] IMMEDIATELY after ADR-0045 signature: amend PROJECT_CANON.md §1 — parallel
   AUTHORED stores remain forbidden; version-pinned DERIVED pass materializations sanctioned under
   the four ADR-0045 conditions — and update AGENTS.md's invariant block pointer. This is the doc
   half S1 could not do pre-signature. Check: canon §1 and ADR-0045 agree verbatim on the four
   conditions.
1. [N1/SD-2] Clock migration per signed ADR-0045: `sql/0021_visible_from.sql` — predicate repointed
   to `COALESCE(realized_at, occurred_at)` (or materialized column if owner chose Option B);
   expression index; `knowledge_time` comment updated to "frozen: row-write audit clock only".
   Retroactive citation (TR-3): `ADR-0045` header comment on the 0018-defined functions this
   supersedes. Check: row with occurred_at 2023-06-01 / ingest 2026 is INVISIBLE to a 2023-05-01
   horizon, VISIBLE to 2023-07-01 and to hindsight.
2. [N2] Writers: extend server/contracts/records.py + server/evidence/store.py INSERT with
   realized_at / acquired_at / realized_evidence / acquisition_id. acquired_at set by ingest
   (knowable); realized_at ONLY via native `@approval` HITL flow (never auto-committed — cite
   canon HITL lock; never a custom approval table). Check: vw_record_disclosure returns non-NULL
   derived tier after a test ingest + one approved realization.
3. [N3] Tier derivation per OQ-8 ruling: parser value becomes `disclosure_tier_asserted` hint
   (parsers stay horizon-blind — their hardcoding is CORRECT, do not teach parsers to classify);
   authoritative tier derived from clocks + HITL. Check: a hindsight row is excluded by a horizoned
   derivation and included by hindsight (the anti-leak guard finally fires in a test).
4. [DA-1..8, F-E, FD] Derivation engine `server/analysis/derivation.py` (+ `sql/0022_pass_corpora.sql`):
   - ONE predicate implementation consumed by both schedules AND by tests (kills F-E's two-copy
     problem — the 0018 test mirror is replaced by calls to the real function).
   - `HorizonContext` frozen dataclass (SD-1): case_id, pass_id, horizon|None, actor. Server-side
     construction only.
   - Incremental schedule (as-lived): per walk step, append newly-visible slice to the pass corpus;
     chain-hash per step (prev_hash); the step rows ARE the walk-ledger (DA-6, working.walk_ledger).
   - On-prompt schedule (hindsight): full materialization.
   - Base-version pinning (DA-5): walk records ledger seq at start; mid-walk ingestion → next run;
     runs citable as (pass, run_no, base_version).
   - Grants (DA-3): refresher role = sole INSERT on pass tables; `horizon_agent` role = SELECT own
     pass corpus only, NO grant on working.normalized_record base table [closes N4's biggest hole].
   - Attestation (DA-4): every derivation → ops.audit_ledger `derivation` row with corpus hash.
   - Cross-lane consistency (DA-8): PG + Weaviate cut from the same base_version in one checkpoint op.
   - Pass runner: agno.workflow Loop (native — never a custom DAG executor); delta computed between
     attested snapshots in plain code.
   Check: derivation reproducibility — re-derive at same base_version → identical corpus hash.
5. [N4 remainder] Enforcement closeout: transaction-scoped `set_config` (SD-8, pooling-safe) for
   any residual predicate-path reads; fail-closed everywhere (SD-3: missing context → zero rows AND
   raise; hindsight only via explicit allow_hindsight grant); fix server/api/inspect_routes.py to
   read via vw_spine_horizon/pass corpora; scope agents' DatabaseContextProvider to the agent role.
   Every read → ledger `read` row (S5 interface). Check: unscoped SELECT on the base table from
   horizon_agent role FAILS; a bypass attempt appears nowhere (impossible), a legit read appears in
   the ledger.
6. [SD-4/DA-7] Weaviate lane: `horizon_axes()` emits `visible_from_epoch` (replacing
   knowledge_time_epoch); per-pass collections materialized at checkpoint (vectors copied, no
   re-embed); agent KnowledgeHandle binds to its pass collection; domain filters remain runtime
   DICT filters (never FilterExpr — inline comment: `# ADR-0040 — dict filters ONLY: agno Weaviate
   adapter silently drops FilterExpr`). Regression test asserts the OUTBOUND WIRE PAYLOAD carries
   the dict filter — never result counts. Reads → ledger.
7. [N6/SD-5/OQ-3] Graphiti clock: FIRST probe live graphiti-mcp `add_memory` for reference_time
   support (`docker compose run --rm agentos-api python tool-skills/graphiti-client/scripts/grc.py
   doctor` + a probe episode; grc doctor also catches read-healthy/write-dead stalls). If
   supported: graphiti_case_client sends reference_time = party-knowledge time; group_id =
   (case, pass) belief groups (legitimate — belief state, not an evidence copy). If NOT supported:
   STOP, report — image-rebuild decision goes back to owner (do not send a param the server drops).
   Searches → ledger. Check: new episode's reference_time reflects occurred_at, verified by grc
   search round-trip.
8. [M-1] MCP doors (D9): evidence-reading tools in server/api/mcp_main.py + gateway invoke_tool
   resolve HorizonContext server-side from pass_id ref; NEVER accept a raw client horizon; hindsight
   = credential grant; fail-closed; invocations + reads → ledger. ADR-0046 cited in headers.
   Check: MCP call without resolvable context → zero rows + explicit error, and the attempt is in
   the ledger.
9. [N7] Context lane: context_chat_ingest.py stamps horizon axes (+ tier per OQ-8 ruling) on
   platform_context writes and Graphiti episodes. Check: no un-axed chunk retrievable through any
   bound reader.
10. [DA-11] Analysis/observation tables: append-only with (pass_id, run_no, base_version)
    attribution columns (migration rides 0022). Re-runs append; never mutate.

## Acceptance (segment)
End-to-end demo, containerized: ingest fixture corpus containing one planted future fact →
sign one realized_at via HITL → run a 3-step as-lived walk + one hindsight derivation →
(a) planted fact absent from every as-lived step, present in hindsight; (b) every derivation,
read, tool call, and approval visible in `audit_dump.py`; (c) re-derivation reproduces identical
corpus hashes; (d) wire-level Weaviate filter test green.

## Constraints
Standing constraints per PLAN master. Extraction stays horizon-blind (F-G — Semantica/parsers
never filter). One store authored; pass corpora derived-only. Dict filters only on Weaviate.
No multi-case/multi-user anything. All new files cite ADR-0045/0046/0047 as applicable.
