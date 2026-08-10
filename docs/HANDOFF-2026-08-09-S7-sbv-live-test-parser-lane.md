# HANDOFF S7 — SBV live test & parser lane
> _2026-08-09 · repo @ a68fabd · STATUS: READY after S5 · Depends: S2 (green suite), S5 (ledger, for audit hooks) · Blocks: S9 (population quality)_
> Inventory items: R-3, D4f items 2–5, M-3, OQ-9 (doc note only).
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.

## Goal
Prove the promoted SBV universal engine against the live service, then finish the parser lane:
metadata-driven resolution, generalized ingestion contract, chatminer hardening, repair adoption.

## Tasks
1. [R-3] SBV live verification (owner: "rewrite should be just about complete and ready for
   testing"): `docker compose --profile tools up -d` (SBV service); run the golden SMS-XML corpus
   through `messages.sms-xml-sbv` end-to-end. Verify against LIVE service: import_id binding on
   every row; H1 local-vs-SBV match; H2/H3 canon checks; `claimed = accepted + rejected +
   accounted-duplicate` reconciliation; rejection fetch. Every run → audit ledger. Record results
   in a dated report under docs/reports/. If Phase-5a ship status matters to wording, follow OQ-9
   ruling; work does not block on it.
2. [D4f-3] Registry metadata `server/tools/registry.py`: add priority / quality_tier / streaming /
   custody_capabilities / max_safe_size to the ToolPlugin contract + resolve() ordering. Resolution
   must stop depending on module-name alphabetical order (current mechanism per sbv_sms.py's own
   docstring). Golden corpora per format; primary/fallback equivalence tests; SBV shadow-comparison
   harness. Orchestration on top stays native agno.workflow (Router/Condition/Loop,
   on_error="fail" explicit) — never a custom DAG executor.
3. [D4f-2] Generalize the ingestion contract: streaming/batch parser protocol; lift SBV's
   reconciliation gate into the shared contract; `evidence.raw_rejected` writer +
   record_count_claimed for ALL parsers (funnel schema already exists — sql/0012/0013). Replace
   the in-memory multipart upload path. Check: a deliberately-malformed export produces
   raw_rejected rows and the gate balances.
4. [D4f-4] ChatMiner hardening: message_hash → content_fingerprint (full digest; NEVER custody
   vocabulary — H1/H2/H3 stays clean per AGENTS.md); deterministic IDs from (artifact H1, parser
   version, source indices); tz-aware UTC timestamps; bounded detection probes.
5. [D4f-5] Repair-layer adoption one format at a time — SMS-XML first, then CSV — ONLY after task 3's
   ledger/rejection writers exist (the observability contract IS the acceptance criterion).
   Preserve lazy-import discipline (module-level lxml import would fatal-loop the dep-light facade
   — ADR-0033 paid for this once). Coordinate with feat/stream-repair-layer per docs/COORDINATION.md.
6. [M-3] Facade tool grooming (ContextForge 14 + gateway): readOnlyHint/destructiveHint annotations
   on every tool (HITL visibility requires destructive tools to look destructive); actionable error
   messages; pagination on any tool returning evidence rows. Cite ADR-0046.

## Acceptance
Live SBV run report committed with hashes + ledger refs; renaming a parser module changes nothing
about resolution order; malformed-input funnel balances; repair path emits ledger + rejection rows
for SMS-XML; every facade tool carries annotations.

## Constraints
Standing constraints per PLAN master. SBV fork is VIP — never fork around; changes go through the
subtree→fork flow per COORDINATION.md. Parsers stay horizon-blind. Tool calls audited (S5 hooks).
