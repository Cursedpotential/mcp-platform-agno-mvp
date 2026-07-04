# S3 — SurrealDB Reconciliation (Resource 4: Consolidated Analysis / Orchestration Sink)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Status (as-built law).** SurrealDB = data-tier **Resource 4** (own service, own bind-mounted
> volume, independently start/stop/rebuild; a crash never tears down PG/Milvus/Neo4j). Per
> **ADR-0024** (amended 0027/0032) it is the downstream **analysis/orchestration sink** of a
> **PG→Surreal** pipeline: **RATIFIED in principle, NOT deployed (Phase D).** This doc reconciles the
> paper design (`sections/07-surrealdb.md`) against the as-built (`E1`), homes every object under the
> security boundary, reuses the `0004` custom-type vocabularies, fixes the `disclosure_tier`
> double-definition, cites prior-art provenance with adopt/adapt/merge/split/deprecate marks, and
> ends with an explicit **DEFER-vs-adopt** ruling. **Nothing here blesses a second system of record.**

---

## 0. Where SurrealDB sits in the security boundary (the homing rule)

SurrealDB is a **separate engine**, not a PG schema — so the as-built three-schema boundary
(`evidence` RO / `analysis` write-after-approval / `public` HITL+Agno, E1 §0) is honored by
**mapping**, not by re-creating schemas:

- SurrealDB is the **conceptual mirror of the PG `analysis` tier**, extended into a workspace.
  Its physical namespace/db = `forensic:analysis`. It holds **only** derived/inferred/analytical/
  legal-conclusion content (the "softer" lanes). **It NEVER holds raw or extracted evidence** — those
  remain canonical in PG `evidence.*` (RO) + Neo4j/Graphiti (CONTEXT_PACK §1, guardrail §6).
- It does **not** invent parallel `core/raw/geo/legal` top-level schemas (addendum §B). Anything raw is
  a **federated pointer** back to `evidence.evidence_hash` / `analysis.normalized_record`, never a copy.
- Every write into Surreal is gated by the **same HITL flow** that gates `analysis` writes: a recorded
  approval (native `agno_approvals`, E1 §2.6) before any sensitive label or court-facing promotion.
- **No shared lifecycle, no cross-engine FK.** ADR-0032 dropped FDW federation; references to
  PG/Milvus/Neo4j are **by id only** (§4). Surreal is rebuildable from upstream at any time.

| Lane (guardrail §6) | Canonical home | In Surreal? |
|---|---|---|
| raw evidence | PG `evidence.evidence_hash` (RO, append-only) | **No** — `fed_ref` pointer only |
| extracted fact (OCR/geocode/parse) | PG `analysis.normalized_record` + domain tables | **No** — pointer only |
| inferred fact (overnight/home_base/anomaly) | PG `analysis` (labeled inferred) | mirror/project (rebuildable) |
| analytical finding | **Surreal** (`finding`, `pattern`, `narrative_beat`) | **Yes** — primary workspace |
| legal conclusion | **Surreal** (`legal_strategy`, gated) | **Yes** — HITL-gated, never auto |

---

## 1. Reused as-built custom-type vocabularies (mirror, never redefine)

SurrealDB cannot share PG types, but it **mirrors the `0004` vocabularies verbatim** so cross-store
joins and the `source_system` crosswalk line up. Reuse — do not invent parallel enums (E1 §3, addendum §B).

| As-built `0004` type | Surreal mirror field | Use |
|---|---|---|
| `confidence` DOMAIN numeric(4,3) 0–1 | `confidence` float 0–1 (+ `confidence_band` HIGH/MED/LOW) | re-derivable; **never hard-coded 0.6** (A3 `vw_forensic_evidence_package` lesson) |
| `source_system` ENUM (postgres/neo4j/milvus/surrealdb) | `fed_ref.target_system` | which engine a pointer resolves against |
| `match_method` ENUM (exact/resolved/manual) | `identity_link.method` | how a cross-store identity was established (E5 alias-resolution gap) |
| `mcl_factor` ENUM (a–l) | `finding.mcl_factors[]`, `legal_strategy.mcl_factor` | MCL 722.23 tagging (canonical superset, E5 §8) |
| `0003` `disclosure_tier` TEXT (contemporaneous/hindsight/discovered) | `knowledge_horizon` | **bitemporal knowledge-time gating** (the substantive one) |
| `0004` enum → **rename to `sensitivity_tier`** (public/restricted/sealed) | `sensitivity_tier` | **access classification**, gates court export |
| `canonical_id` (uuid), `source_ref` composite | `fed_ref.target_locator`, provenance | provenance pointers |

### 1.1 disclosure_tier double-definition — FIXED here (E1 §5.1, addendum §B bug)

The name `disclosure_tier` is bound to **two disjoint concepts**. Resolution carried into Surreal:
- **Temporal / knowledge-horizon** = `0003` values `contemporaneous|hindsight|discovered` → field
  **`knowledge_horizon`** (the bitemporal "when did we learn it relative to the event" tier — keep).
- **Access / sensitivity** = `0004` enum `public|restricted|sealed` → renamed **`sensitivity_tier`**
  (aligns with the evidence/analysis/public boundary). The two are **separate envelope fields** in
  Surreal — they are never conflated, which is exactly the bug the as-built must rename out.

---

## 2. Common envelope (mixin on every assertion-bearing record)

Every finding/pattern/plan/strategy record embeds this provenance + classification envelope, enforced
via `DEFINE FIELD` on `SCHEMAFULL` tables (schemaless rejected for a court-facing store). This is the
DB-level expression of the lane-discipline + provenance + append-only guardrails.

| Field | Type | Provenance / rule |
|---|---|---|
| `assertion_type` | enum: raw/extracted/inferred/analytical/legal_conclusion | guardrail §6 lane discipline; salem_v3 "extraction-first then analysis" (E5 S2) |
| `confidence` + `confidence_band` | float 0–1 + HIGH/MED/LOW | mirrors `0004 confidence`; normalize prior numeric(5,2) scales → 0–1 (E5 §8) |
| `timestamp_certainty` | enum: exact/approximate/inferred/uncertain | **the precision class missing from ALL prior schemas** (A3, CONTEXT_PACK §3) |
| `knowledge_horizon` | enum: contemporaneous/hindsight/discovered | from `0003` (§1.1) |
| `sensitivity_tier` | enum: public/restricted/sealed | renamed `0004` enum (§1.1); gates export |
| `valid_time` | {start,end} datetime | bitemporal "true in the world"; complements Graphiti, does **not** duplicate it (§6) |
| `knowledge_time` | datetime, set-on-insert, append-only | "when we asserted it"; never overwrite (guardrail §6) |
| `conduct_party` | enum: petitioner/respondent/child/mutual | **both-parties mandate** — model the user's own conduct too (A3 ontology gap; guardrail §6) |
| `evidence_refs` | array<record(fed_ref)> | ≥1 federated citation; **MUST be non-empty for `assertion_type ≥ inferred`** |
| `provenance` | object | `{run_id, prompt_version, ontology_version, schema_version, model_id, tool_call_id}` (lineage; Semantica `Decision`/`DecisionContext`, E5 S7) |
| `review` | record(review_state) | HITL state link (§3.7) |
| `supersedes` | option<record> | append-only versioning — preserve prior interpretations (guardrail §6) |
| `case_id` | string | scope (salem caption generalized) |

---

## 3. Record types (tables) — with prior-art provenance & adopt/adapt marks

`DEFINE TABLE … SCHEMAFULL`. IDs are stable/traceable; a projected upstream row stores the upstream
key (uuidv7), never a renumbered surrogate.

| Surreal table | Purpose | Key fields (beyond envelope) | Provenance | Mark |
|---|---|---|---|---|
| `fed_ref` | Federated pointer to a canonical record (no payload copy) | `target_system`, `target_locator`, `digest` (sha256 of cited content), `snapshot_at` | federation primitive; SHA-256/uuidv7 custody (E1 §2.3, CONTEXT_PACK §3) | **new** |
| `analysis_run` | One pass of multi-pass analysis | `pass_no`, `pass_type` (priority/extraction/correlation/pattern/narrative/legal), `inputs[]`, `prompt_version`, `model_id`, `status`, `parent_run` | E4 §7 6-pass pipeline (S6/S7/S8); Semantica `Decision` lineage (E5 S7) | **adapt** |
| `finding` | An analytical finding from a run | `claim`, `finding_type`, `subject_refs[]`, `support[]`→fed_ref, `contradicts[]`, `inconsistency_flag`, `darvo_stage`, `cycle_phase` | salem `Statement` fields (E5 S2: darvo_stage/inconsistency/contradicts_evidence); dial-stack `detected_patterns` (E5 S5) | **adapt** |
| `pattern` | An **instance** of a behavioral-library pattern (not the library) | `pattern_key`→PG lexicon, `category`, `subcategory`, `polarity` (pos/neutral/love-bomb/repair/neg), `severity` 1–10, `mcl_factors[]`, `instances[]`→fed_ref, `recurrence` | E4 catalog (behavioral_patterns.ttl / seed-patterns.ts 308×26 / detection_patterns.py / 303-lib); `positive_behaviors.ttl` | **adapt** |
| `narrative_beat` | Unit of cross-source narrative reconstruction | `summary`, `ordered_refs[]`, `tone_surface`, `inferred_intent`, `relational_function`, `cycle_phase`, `context_before/after` | salem `RELATED_TO` **split** into typed beats (A3 §A); sentiment-separation + full-cycle (E4 §0, guardrail §6) | **split/new** |
| `timeline_view` | Saved parameterized timeline projection (rebuildable from PG `timeline.*`) | `lens` (party/topic/location/device), `event_refs[]`, per-row `(ts_raw,ts_utc,offset)` triple, `gap_flags[]` | TraceIQ `timeline_enriched`/`vw_*` (A3 §B, E3); multi-device attribution gap | **adapt** |
| `legal_strategy` | Legal-strategy workspace object (gated) | `issue`, `mcl_factor`, `theory`, `supporting_findings[]`, `risks[]`, `court_safe_wording`, `emotional_vs_legal_split` | `mcl_722_23.ttl` (E4 §6); irac-formatter skill | **adapt** |
| `evidence_plan` | Evidence-gathering / corroboration plan | `gap`, `hypothesis_ref`, `needed_evidence`, `source_hint`, `priority`, `status`, `corroboration_target` | "make clear what requires corroboration" (guardrail); E5 `evidence_plan` lane gap | **new** |
| `inferred_link` | Graph-discovered hidden relationship (hypothesis) | `entity_a/b`→fed_ref, `inferred_type`, `path_length`, `intermediaries[]`, `confidence` | dial-stack `inferred_relationships` (E5 S5) — **no as-built home** | **adopt** |
| `precedent` | Decision/precedent-similarity link | `source_run`, `similarity_score`, `relationship_type` (similar_scenario/same_policy/exception) | Semantica `Precedent` (E5 S7) — no as-built home | **adopt** |
| `review_state` | Human-review / approval state machine | `state`, `reviewer`, `decision`, `decided_at`, `notes`, `sensitive_label_gate` bool, `history[]` | dial-stack `pattern_approval_log` + HITL quartet (E5 S5); Semantica `ApprovalChain` (E5 S7); native `agno_approvals` (E1 §2.6) | **merge** |
| `identity_link` | Cross-store identity resolution (alias) | `aliases[]`, `resolves_to`→fed_ref, `method` (match_method) | salem `Person.aliases` (E5 S3) — **no as-built home**, surfaced gap | **adopt** |
| `work_product` | Persisted intermediate artifact | `kind` (scan/draft/index/classification/prompt/tool_output), `blob_ref`→R2, `archived`+`archive_reason` | persist-intermediate-work guardrail; never silent-discard | **new** |
| `session_memory` | Cross-session resume state (Agno-native) | `agent`, `task`, `context_blob`, `open_threads[]` | ADR-0024 store/session/memory | **adopt** |

**Behavioral-pattern LIBRARY stays in PG, not Surreal.** The ~308-pattern / 26-category lexicon
(regex/keyword/severity/MCL, child-name & vulnerability lexicons, E4 §3–4) is **config data** that
belongs in a PG `analysis` config table (`behavioral_patterns`/`lexicon`, `is_case_specific` rows),
loadable without touching the engine (E4 guardrail §5). Surreal stores only **pattern instances/findings**.
Carry the E4 open items into PG, not Surreal: severity-scale unification (1–10 canonical), category-name
normalization, and the **J↔K MCL remap** bug (E4 §6.2 — same off-by-one class as `disclosure_tier`).

### 3.x Sensitive-label gating (DB-enforced HITL, guardrail §6)

`pattern.polarity ∈ {coercive_control, gaslighting, alienation, weaponization, reactive_abuse}` and any
`legal_strategy.theory` using those labels **cannot** reach `assertion_type=legal_conclusion` or a
court-facing export until `review_state.sensitive_label_gate = true` AND `state = approved`. Enforced by
`DEFINE EVENT`/permission, not convention. Behavior/abuse labels are **hypotheses**, never auto-facts
(E4 §0: detection ≠ proof). Positive/love-bombing/repair patterns are tracked as **contradiction anchors
over time**, never as exoneration (full-cycle mandate, E4 §0.4).

---

## 4. Federated references to PG / Milvus / Neo4j (by id, never shared lifecycle)

SurrealDB has **no production federation** to the other engines, and ADR-0032 **dropped FDW**. Federation
= **reference-by-pointer + orchestrated fetch**, never live cross-engine join. `fed_ref` is the contract:

| `target_system` | `target_locator` shape | Resolved by | Notes |
|---|---|---|---|
| `postgres` | `{schema, table, pk uuidv7, as_of}` | forensic-data-agent via pg_duckdb | points at `evidence.evidence_hash` / `analysis.normalized_record`; `as_of` = point-in-time re-read |
| `neo4j` | `{label/edge, element_id, valid_time, knowledge_time}` | native Cypher (ADR-0032) | bitemporal coords preserved — Graphiti stays entity-truth |
| `milvus` | `{collection, embedder, vector_id, score, query_hash}` | Milvus SDK | **id + score only; never copy vectors** (ADR-0026) |
| `r2` | `{bucket, key, sha256, version_id}` | rclone mount / pg_duckdb S3 secret (ADR-0030) | `work_product` blobs / Iceberg time-travel |

**Tamper-evidence / custody.** `fed_ref.digest` = **sha256** of cited content at `snapshot_at`
(sha256 = canonical evidence identity; **md5 is pre-filter only**). At export the gatekeeper re-reads
upstream and compares digests; a mismatch flags the citation **stale/changed** rather than silently
exporting. This is the SHA-256/uuidv7 chain-of-custody (E1 §2.3, `pgcrypto.digest(...,'sha256')`)
projected into the analysis layer.

---

## 5. Edges (analysis-layer only; entity-truth graph stays in Neo4j)

`RELATE a->edge->b`; every edge carries the envelope (assertion_type/confidence/evidence_refs).

| Edge | Connects | Meaning | Provenance |
|---|---|---|---|
| `supports` | fed_ref → finding | evidence backs a finding | core |
| `contradicts` | finding↔finding / fed_ref→finding | impeachment / conflict (HITL) | salem `CONTRADICTS` (E5 S2) |
| `instantiates` | fed_ref → pattern | event is an instance of a pattern | E4 303-lib |
| `used_tactic?` | finding → pattern | **hypothesis** — alleged tactic | salem `USED_TACTIC` (preserve-as-hypothesis, A3) |
| `preceded`/`part_of`/`caused?` | beat → beat | temporal/causal (`caused?` always hypothesis) | salem `RELATED_TO` split (A3 §A) |
| `reacts_to` | beat → beat | user's reaction modeled in context (explanation ≠ excuse) | full-cycle mandate (guardrail §6) |
| `repair_attempt`/`love_bombing` | beat → beat | full relational cycle, both parties | `positive_behaviors.ttl` (E4 §5) |
| `informs` | finding → legal_strategy | finding feeds strategy | core |
| `gap_for` | evidence_plan → finding | plan addresses a weak/uncorroborated finding | core |
| `gates` | review_state → (finding/pattern/legal_strategy) | review controls promotion | HITL (E5 S5) |

**Timeline views** render only `review.state='approved'` beats; rough/hypothesis beats are filtered.
Lenses include per-device (multi-device attribution gap). **Pattern objects** bind to the 303-lib +
`positive_behaviors.ttl` so `polarity`+`cycle_phase` make contrast-over-time queryable (both parties).

---

## 6. Duplication & synchronization risk (the decisive analysis)

A second engine holding **projections** of canonical data is a dual-write / cache-coherence problem; for
a court-facing system, drift between the sink and the system of record is an **evidentiary-integrity
risk** (an export could cite a finding whose PG row has since changed). **Surreal is never authoritative
on conflict** (SSOT docs / canonical stores win).

| Risk | Mechanism | Severity | Mitigation |
|---|---|---|---|
| Stale projection | PG/Neo4j row changes; Surreal copy doesn't | HIGH | `fed_ref.digest` re-verify at export; pointer-not-copy; `as_of` reads |
| Dual source of truth | analysts treat Surreal as authoritative | HIGH | firewall §0; raw/extracted truth stays upstream; Surreal flagged read-derived |
| Sync = custom code | bespoke ETL/CDC violates "minimize custom code" | MED | Agno-native sync; **batch projection, not chatty dual-write** |
| Bitemporal double-bookkeeping | valid/knowledge time tracked in both Graphiti & Surreal | MED | Graphiti = entity-truth timeline; Surreal = analysis-workspace timeline; never the same facts |
| Operational surface | a 4th DB to deploy/back up/secure (no GPU, lean infra) | MED | bind-mount volume (owner rule); defer until Phase-D capacity |
| Vector duplication | copying embeddings into Surreal | HIGH (cost+drift) | store vector_id+score only; Milvus = single vector store (ADR-0026) |
| Maturity | Surreal less battle-tested than PG for forensic guarantees | MED | keep derived & rebuildable; never the only copy |

**The cheaper alternative — already-LIVE `agno-postgres:18-duckdb`.** Almost everything in §2–§5 builds
inside the existing PG `analysis` schema with **zero new infra**: JSONB for multi-pass findings;
pg_duckdb + Cypher + Milvus SDK for federated reach (ADR-0032, the *current* blessed reach); materialized
views over `analysis.normalized_record` for timelines; `btree_gist` EXCLUDE on `tstzrange` + append-only
history for bitemporality; `LISTEN/NOTIFY` for the live review queue; agno-gateway is **already
Postgres-backed** for session/memory. PG+views covers the requirement today with **one fewer engine, no
sync layer, no drift class**. Surreal's residual edge is *ergonomic/velocity* (Agno-native single surface,
native multi-model + `LIVE SELECT`, native workspace bitemporality) — not *capability*.

---

## 7. RECOMMENDATION — **DEFER (conditional adopt)**

1. **Phase A–C: build the entire consolidated-analysis model (§2–§5) inside PG `analysis`** (write-after-
   approval), reusing the `0004` types and the `evidence`/`analysis`/`public` boundary — **no new
   top-level schemas, no new engine, no sync layer, no drift risk**. Honors off-the-shelf-first /
   minimize-custom-code / reversible-work.
2. **Keep the schema "SurrealDB-shaped"** — the envelope (§2), `fed_ref` pointer contract (§4), and edge
   vocabulary (§5) are deliberately portable, so ADR-0024 intent stays alive without paying for it early.
3. **Promote to SurrealDB in Phase D only on a fired trigger:** (a) cross-3-engine agent query
   latency/complexity becomes the bottleneck; (b) Agno-native session/memory delivers a measurable win
   the PG path can't; (c) `LIVE SELECT` materially improves the review-queue UX. Record which trigger
   fired in a confirming note on ADR-0024.
4. **If adopted, adopt as a pure derived sink only:** reference-by-pointer (never copy payloads/vectors),
   digest-verified citations, **batch projection** (not dual-write), rebuildable from upstream, **never
   authoritative on conflict, never a second system of record.** The PG→Surreal projection job needs its
   own ADR; do not improvise dual-write.

---

## 8. Open items / needs-human-review

- **Deployment status (FLAG):** ADR-0024 = ratified, undeployed. Owner to confirm Phase-D spend is open.
- **Sync mechanism (GAP):** no live PG→Surreal projection DDL exists; design it as its own ADR if adopted.
- **Bitemporal boundary (FLAG):** draw the explicit split between Graphiti's entity-truth bitemporality and
  Surreal's workspace bitemporality to avoid double-bookkeeping (§6) — short ADR amendment.
- **Carry-over PG-side bugs (not Surreal's):** apply the `disclosure_tier` rename (§1.1) and the **J↔K MCL
  remap** (E4 §6.2) in the PG reconciliation migration; both are blocking for court use.
