# Forensic Evidence Database Architecture

### SPEC-1 · MCP Forensic-Evidence Agent Platform — Master Architecture Document

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_

---

> ## ⚠️ DRAFT — HUMAN-IN-THE-LOOP REVIEW REQUIRED ⚠️
>
> **This is a DRAFT architecture for human review. It is NOT a ratified specification and NOT a court-facing artifact.**
> It describes how a forensic-evidence database *should* be built; it does not assert any fact about any person.
> Nothing in this document may be exported, filed, or treated as an established finding without explicit human
> review (HITL). Where the document names data fields, enum values, or worked examples that could read as
> allegations or conclusions about a real person, those are **schema illustrations only** — see the
> *Appendix: Open critic findings still requiring human attention* before relying on any of them. Several
> court-safety items (conclusory vocabulary baked into enums, a person-level `is_flagged` attribute,
> both-parties parity, real-identifier scrubbing) are **flagged unresolved** and must be addressed by a human
> before this design produces any output about an actual case.

---

### Provenance of this document

This master document was **assembled by a multi-agent workflow**, not written in a single pass. The pipeline ran:
discovery agents (A1 capabilities/liveness, A2 SSOT/ADR drift, A3 prior-work crosswalk, A4 prior-reports
triage, A5 conversation-log mining) → a compacted context pack → 21 parallel section drafters → three
independent critics (completeness, court-safety/blank-slate, gap/staleness) → this synthesis/assembly pass.
Every section is **grounded in the discovery and gap artifacts** and cites the governing ADRs; on any conflict
the SSOT docs (`Agno-MCP-Platform/docs/PROJECT_CANON.md` + ADRs) win over this draft.

Grounding artifacts (all under `scratchpad/forensic-db-arch/`):

- Context pack (carry-forward digest): `discovery/CONTEXT_PACK.md`
- Gap, blind-spot & staleness report: `discovery/GAP_AND_STALENESS_REPORT.md`
- Discovery source reports (A1–A5): `discovery/` (referenced in the two artifacts above)
- Critic findings folded into this assembly: `review/completeness.md`, `review/court_safety.md`, `review/gap_staleness.md`
- The 21 source section drafts: `sections/01-…` through `sections/21-…`

**What the assembler changed vs. the section drafts:** sections are concatenated essentially verbatim (the
synthesis pass does not rewrite analytical content). The only inline edits applied are safe, mechanical fixes
flagged by the critics — e.g. scrubbing a real child's name from one illustrative string in §3 to
`[MINOR_1]`/`[PARTY_B]`. Everything substantive a critic raised is **left in place and catalogued in the
closing appendix** rather than silently rewritten or invented.

---

## Table of Contents

- [Provenance of this document](#provenance-of-this-document)
- [Pre-Scan & Existing-Work Reconciliation (Post-Scan Merge Report)](#pre-scan--existing-work-reconciliation-post-scan-merge-report)
  - [Staleness summary](#staleness-summary)

**Architecture sections (21):**

1. [Title, Executive Summary, and Goals & Non-Goals](#1-title-executive-summary-and-goals--non-goals)
2. [Core Data Domains](#core-data-domains)
3. [Canonical Data Model (the big one)](#canonical-data-model-the-big-one)
4. [PostgreSQL / DuckDB / PostGIS Schema Strategy](#postgresql--duckdb--postgis-schema-strategy)
5. [Milvus Vector Schema (Collections)](#milvus-vector-schema-collections)
6. [Neo4j / Graphiti / Semantica Graph Model](#neo4j--graphiti--semantica-graph-model)
7. [SurrealDB Consolidated Analysis Model](#surrealdb-consolidated-analysis-model)
8. [Temporal reasoning model (bitemporal)](#temporal-reasoning-model-bitemporal)
9. [Provenance & Chain-of-Custody Model](#provenance--chain-of-custody-model)
10. [Extraction Ontology per Source Type](#extraction-ontology-per-source-type)
11. [Multi-pass analysis workflow (19 phases)](#multi-pass-analysis-workflow-19-phases)
12. [Evidence-Gathering Plan Model](#evidence-gathering-plan-model)
13. [Confidence, Scoring & Human Review Framework](#confidence-scoring--human-review-framework)
14. [Security, Privacy & Safety Constraints](#security-privacy--safety-constraints)
15. [Risks, Assumptions & Open Questions](#risks-assumptions--open-questions)
16. [Implementation roadmap (MVP + Phases 1-8)](#implementation-roadmap-mvp--phases-1-8)
17. [Testing Strategy](#testing-strategy)
18. [Diagrams](#diagrams)
19. [Final Execution-Ready Plan](#final-execution-ready-plan)
20. [Persistent Work-Product Ledger & Micro-Memory Design](#persistent-work-product-ledger--micro-memory-design)
21. [Final Verdict](#final-verdict)

- [Appendix: Open critic findings still requiring human attention](#appendix-open-critic-findings-still-requiring-human-attention)

> _Note on count: the master prompt specified 23 deliverables; **21** architecture sections were produced.
> The Post-Scan Merge Report (below) and this appendix supply two cross-cutting deliverables; the residual
> count discrepancy is logged in the appendix (item C-1) for orchestrator reconciliation._

---

## Pre-Scan & Existing-Work Reconciliation (Post-Scan Merge Report)

This project is **not a blank slate**. Before any new design, the discovery agents scanned the user's prior
work — the `salem_v3` case knowledge graph, the TraceIQ timeline/geo schemas (R5/R10/R12), the salvaged
parser/ontology corpus in `extracted-code/MANIFEST.md`, the alpha forensic-DB schemas, the doc-intelligence
tables, and the Jan-era status/audit reports — and the locked ADR stack. The table below reconciles every
material prior asset into one of nine dispositions. It is distilled from the A3 crosswalk, the
`GAP_AND_STALENESS_REPORT.md`, and the three critic reviews. **Items in _Lost_, _Conflicting_, and
_Needs-Review_ are the ones that still require a human decision** and are expanded in the closing appendix.

| Disposition | Prior asset(s) | Reconciliation note | Where landed / ref |
|---|---|---|---|
| **Preserved** (as-hypothesis / as-note) | salem_v3 `USED_TACTIC`, `EXPLOITED_VULNERABILITY` (was `TARGETED_WOUND`), `DISPARAGES` (was `SPREADS_RUMOR`); prior human interpretations | Kept verbatim as **hypotheses**, never promoted to fact; HITL before any court use; append-only so prior interpretations are never overwritten | §6, §9, §13 |
| **Preserved** (pipeline-only note) | `temporal_alignment`, `enrichment_queue` | Operational/pipeline constructs — intentionally not in the canonical schema; recorded so the omission is explicit, not silent | §11 |
| **Adopted** (as-is) | salem_v3 core entities `Person`/`Incident`(`Event`)/`Location`/`Statement`/`Evidence`; edges `WAS_AT`/`PARTICIPATED_IN`/`MADE_STATEMENT`/`CONTRADICTS`; UUIDv7+SHA-256 chain-of-custody column contract; doc-intelligence `sections/chunks/spans/entities/findings/approvals`; Semantica PROV-O provenance/conflict pattern; Google raw-export JSON shape (raw-evidence contract); `positive_behaviors.ttl`, `behavioral_patterns.ttl`, `mcl_722_23.ttl` (12 MCL factors), `detection_patterns.py` (256-pattern/DARVO), `seed-patterns.ts ~303`, `hurtlex_loader`; parsers `enhanced-xml-chunker.py`, `sms_backup_parser`, `schema-resolver.ts` | Direct reuse; `positive_behaviors.ttl` adopted specifically to satisfy the both-parties / full-cycle guardrail (do **not** invent new node types) | §2, §3, §6, §9, §10 |
| **Adopted** (live infra) | Milvus (single vector store), Neo4j+Graphiti (bitemporal cognition), R2 object store, ContextForge MCP gateway, custom `agno-postgres:18-duckdb` image | Already LIVE; reused, not rebuilt | §4–§6, ADRs 0007/0013/0014/0026/0027 |
| **Adapted** (reshaped) | TraceIQ `timeline_enriched` → `timeline_event` (split raw vs enriched; TEXT timestamps → `timestamptz` **+ new precision class**); custody edge → `AFFECTED_PARENTING_ACCESS`/`EXPOSED_CHILD` (renamed); `Vulnerability`, `Tactic`/`BehavioralPattern` (sensitive → HITL); `vw_forensic_evidence_package` (HIGH/MED/LOW tiers); `is_private` → review gate; pgvector role → Milvus | Shape adapted to lane discipline, the timestamp-precision requirement, and the live stack | §3, §6, §8, §10, §13 |
| **Merged** | TraceIQ `people` ↔ salem `Person`; multiple timeline sources → unified `timeline_event`; geocode results ↔ caches → `geocode_resolution`; `normalized_messages` raw-JSON landing **+** TraceIQ typed `messages` → "raw landing → typed projection" | Identity/entity reconciliation; the messages merge is adopted in principle but its **field-merge rules remain open** (see Conflicting / Needs-Review) | §3, §10 |
| **Split** | salem `RELATED_TO` → typed causal/temporal/topical edges; `timeline_enriched` → raw vs enriched layers; `problematic_locations_contacts` → evidence-gathering **task**, not a person denylist (per court-safety F5) | Vague/over-broad constructs decomposed into typed, lane-correct ones | §6, §8, §12 |
| **Deprecated** (superseded — ignore as authority) | ADR-0003 (PG18 pgvector-only, NO DuckDB); standalone DuckDB; FalkorDB; Multicorn2/neo4j-fdw federation; Supabase/Chroma/LanceDB/pgvector target stack; flat `timeline_events`, stub tables, redundant caches, markdown report template; pgvector **vector role** (legacy-resident) | Clean supersession chain (0003→0013/0014/0027); the README still mislabels 0003 "Accepted" — **drift to fix** (see Conflicting) | §4, §15, §21, ADR-0013/0027/0032 |
| **Lost** (dropped — no section incorporated; human decision needed) | TraceIQ DuckDB analytical views `vw_place_analytics`, `vw_route_patterns`, `vw_bouncy_trips`, `vw_overnight_activity`, `vw_city_summary`; `data_quality_metrics` + `trig_quality_check`; SBV cluster parser + 4GB streaming-XML ingest design; doc-intelligence `summaries`/`keywords` tables; alpha tables `bertConfigs`/`severityWeights`/`schemaResolvers`/`forensicResults`; **Email** as a first-class source; weakly-covered `flagged_entity`, `multi_device` attribution, named raw-export JSON schema contracts | Genuinely dropped or only incidentally touched (critic-verified 0–2 hits). Several are easy re-adopts (the analytical views, `data_quality_metrics`); Email and streaming-XML are real capability gaps | Appendix items A-1…A-6 |
| **Conflicting** (open, needs decision) | `normalized_messages` raw-JSON vs typed `messages` field-merge rules; ADR-0003 README "Accepted" label; R6 "85% done" vs R7/R8 "40%" status; pg_duckdb-embedded vs standalone DuckDB; **no as-built DDL verification** (paper design vs unverified live stack) | Most are *resolved in principle* (embedded DuckDB wins; trust ADRs+probes over reports) but carry a concrete to-do (lock merge rules; fix README label; run a live-DDL reconciliation) | §4, §15, §21; Appendix B |
| **Needs-Review** (court-safety / scope — human required before use) | `is_flagged` person attribute; conclusory enum vocabulary (`pattern_category`, `reactive_context` field names); `love_bombing`/`escalation` as extracted-tier `event_type`; both-parties parity (positive lane is promissory); real identifiers in examples; XLSX/Snapchat-source/Instagram/Email ingest lanes; R5 two-copy dedupe + model extraction; 21-vs-23 deliverable count | These survive HITL-on-export but are **structural** court-safety or scope gaps; do not treat the design as court-ready until closed | Appendix items F1–F5, A-1…A-6, C-1 |

### Staleness summary

The discovery pass verified the currency of every resource it relied on (full table in
`discovery/GAP_AND_STALENESS_REPORT.md`, Part 2). Headlines:

- **Current / trust:** ADR-0013 (the `agno-postgres:18-duckdb` SSOT) and ADRs 0014/0024/0027/0030/0031/0032 +
  `PROJECT_CANON §5`; the A1 live probes (graphiti, coolify, agno-gateway, opencode all LIVE 2026-06-30);
  `extracted-code/MANIFEST.md` (deduped, provenance-tracked salvage — the canonical prior-art source);
  `casebible.duckdb` (Jun 23, local catalog/prototype); memsearch memory digests (≤ Jun 27).
- **Aging / re-target before reuse:** the Jan-era reports R5–R12 — richest on the *data model* (R5) and the
  TraceIQ *timeline* design (R10/R12), but they assume a **dead stack** (Supabase + Chroma + LanceDB +
  pgvector) that must be re-targeted to PG(+pg_duckdb+PostGIS)/Milvus/R2. R5 also exists as two byte-identical
  copies (dedupe pending).
- **Superseded — ignore as authority:** ADR-0003 (every axis); the README "Accepted" label for it (fix to
  "Superseded by 0013/0014/0027"); MIGRATION_PLAN_v8 / `docs/planning/*` (PG16, pgvector-hybrid,
  `uuid_generate_v4`).
- **Stale / last-resort only:** 78 `Workspace_Manifest_*.json` snapshots (Feb–Mar); the memsearch turn DB
  (Jun 11 metadata only); the `claude-context` index (unindexed for the workspace root — re-index before any
  code search).
- **Dead pointers:** the `TheBigOne` tree is **gone from all three disk roots** — every transcript absolute
  path is dead; resolve via `extracted-code/MANIFEST.md`. `osgrep` was uninstalled (06-11) — ignore.
- **Critic verdict on staleness contamination:** *clean.* The gap/staleness critic confirmed **no stale
  decision is silently inherited** — every superseded resource is treated as inventory-only and the live ADR
  is cited instead.

---
