# S2 — Neo4j + Graphiti + Semantica (Resource 3) Reconciliation

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Law (ground truth):** `extracted/E1_asbuilt_inventory.md` (the four `sql/0001–0004` migrations).
> **Design under reconciliation:** paper `…/scratchpad/forensic-db-arch/sections/06-neo4j-graphiti-semantica.md`.
> **Inputs:** `addendum.md`, `CONTEXT_PACK.md`, `A3_crosswalk.md`, `E4_behavioral_ontology.md`, `E5_entity_ontology_misc.md`.
>
> This doc does **not** re-derive the graph model (paper §06 is the full node/edge catalog). It
> **reconciles** that model to the as-built law: re-homes every `pg_table` onto the real
> `evidence`/`analysis`/`public` schemas, reuses the `0004` custom types for the cross-store
> crosswalk, fixes the `disclosure_tier` double-definition, and cites adopt/adapt/merge/split/deprecate
> provenance for each prior-art element. On conflict, **E1 wins** over the paper.

---

## 0. Topology & engine (confirmed, unchanged)

- **Resource 3 = Neo4j, its own independently-restartable resource** (own container, own bind-mounted
  volume — Docker mapped-volumes preference). A Neo4j crash must never tear down PG (Resource 1:
  PostgreSQL+PostGIS+embedded DuckDB/pg_duckdb), Milvus (Resource 2), or SurrealDB (Resource 4), and
  vice-versa. (CONTEXT_PACK §1; E1 is silent on Neo4j — it owns only the PG side.)
- **Engine = Neo4j Community + Graphiti** (ADR-0014/0018/0031, VIP-never-replaced). Multi-DB is
  emulated via Graphiti `group_id` + a `lane` property, **not** separate Neo4j databases.
- **Apache AGE is NOT used.** AGE was only an *alternative backend option* if Semantica ran its own
  embedded graph. We deploy a real Neo4j, so Semantica writes **into our Neo4j** and AGE is out of
  scope. (Confirms `0004.source_system` enum lists `neo4j`, not `age`; addendum "Apache AGE = Semantica
  backend option only, not deployed.")
- **Two writers, one graph.** **Graphiti** = agent-memory/bitemporal writer. **Semantica** = case-KG
  builder running **seed-first hybrid**, writing **our Neo4j + Milvus** — **not a second graph store**
  (ADR ~0035, CANON §5). Both pass through one **Graph Write Adapter** (§7) so origin stays
  traceable/separable/reversible.

**Rebuild contract (hard rule):** Neo4j = `project(PostgreSQL)`. PG is SSOT; the graph holds pointers
and relationship-shape, never an un-backed fact. If Neo4j is wiped it is fully rebuildable from PG.

---

## 1. SECURITY-BOUNDARY RE-HOMING — the primary reconciliation fix

Paper §06 routed graph `pg_table` back-refs to top-level schemas `entity.*`, `timeline.*`, `geo.*`,
`legal.*`. **Those schemas do not exist and are forbidden by the as-built law** (E1 §0: only
`evidence`, `analysis`, `public`). Per the guardrail, `entity`/`timeline`/`geo`/`legal` become
**table-name prefixes/sub-domains inside the three real schemas**. Every graph node's `pg_table`
property is re-homed as follows; the lane (raw vs derived) decides the schema.

| Graph label | Paper `pg_table` (WRONG schema) | **Re-homed `pg_table` (as-built law)** | Schema rationale |
|---|---|---|---|
| `:Evidence`/`:EvidenceItem` | `evidence.*`/`custody.file_node` | `evidence.evidence_hash` (+ `evidence.source`) | raw/custody → **evidence** (RO, sha256 identity) |
| `:Message` | `evidence.message` | `evidence.message` | raw message body → **evidence** (RO) |
| `:Identifier` (raw observed) | `entity.identifier` | `evidence.identifier_raw` | raw sender/handle as seen → **evidence** |
| `:Platform`/`:CommunicationChannel` | `entity.platform` | `evidence.platform` | raw channel → **evidence** |
| `:Person` (canonical, resolved) | `entity.person` | `analysis.entity_person` | identity-resolution output (post-HITL) → **analysis** |
| `:Child` (co-label) | `entity.person` | `analysis.entity_person` (`is_minor=true`) | derived classification → **analysis** |
| `:Organization` | `entity.person/org` | `analysis.entity_org` | derived registry → **analysis** |
| `:Device` | `entity.device` | `analysis.entity_device` | resolved attribution → **analysis** |
| `:Account` | `entity.account` | `analysis.entity_account` | resolved → **analysis** |
| `:Event`/`:Incident` | `timeline.event` | `analysis.timeline_event` (enriched); raw segments stay `evidence.raw_visit/activity/path/trip` | enriched event = derived → **analysis**; raw Google segments → **evidence** |
| `:Location` | `geo.location` | `analysis.geo_location` (PostGIS geom SSOT here); raw GPS → `evidence.geo_gps_point` | canonical dedup'd place = derived → **analysis** |
| `:Statement`/`:Claim`/`:Allegation` | `analysis.*`/`evidence.*` | `analysis.statement` / `analysis.claim` (raw verbatim quote → `evidence.message`) | declaration extraction = derived → **analysis** |
| `:Contradiction` | `analysis.contradiction` | `analysis.contradiction` | ✓ already correct |
| `:Pattern`/`:Tactic`/`:Vulnerability`/`:CyclePhase`/`:Finding` | `analysis.*` | `analysis.finding` (+ `analysis.behavioral_pattern`, `analysis.relationship_phase`) | analytical findings → **analysis** (sensitive, HITL) |
| `:LegalIssue`/`:CustodyFactor`/`:Exhibit` | `legal.*` | `analysis.legal_issue` / `analysis.custody_factor` / `analysis.exhibit` | legal conclusions → **analysis** (review-gated, court-export-gated) |
| HITL audit / Agno stores | — | `public.*` (`agno_approvals`, knowledge, sessions) | the review decisions that gate graph writes live in **public** |

**Net rule:** `:*` node `pg_table` ∈ {`evidence.*` (raw, RO), `analysis.*` (derived, write-after-approval)}
only; the gating `human_review_id` resolves into `public.agno_approvals`. No graph node may claim a
`pg_table` outside these three schemas.

---

## 2. REUSE the as-built `0004` custom types for the cross-store crosswalk (do not redefine)

The paper's `uid`/`pg_pk`/`provenance_id`/`source_id` back-ref scheme is the **same intent** as the
as-built `id_xref` crosswalk lane (E5 §8). Reconcile by binding the graph's back-refs to the existing
`0004` types — **never invent parallel enums/domains**:

| As-built type (`0004`) | Use in the Neo4j ↔ PG bridge | Classification |
|---|---|---|
| `source_system` ENUM (`postgres,neo4j,milvus,surrealdb`) | the crosswalk axis: a graph node is `id_xref(source_system='neo4j', native_id=<uid>)` ↔ `('postgres', pg_pk)`; back-refs to Milvus/SurrealDB use the same enum | **Adopt** (cleaner-typed successor to Zep `zep_node_id`/`source_table`, E5 S3) |
| `match_method` ENUM (`exact,resolved,manual`) | how each `:IDENTIFIED_BY` / identity-resolution link was established; stamps the crosswalk row + the graph edge `match_method` prop | **Adopt** |
| `canonical_id` DOMAIN (`uuid`) | the canonical entity key shared across stores; `uid = "<Label>:<canonical_id>"` so MERGE is idempotent and 1:1 to PG | **Adopt** — but fix doc/impl mismatch (§5.3 E1: comment says "uuid string", base is `uuid`; keep `uuid`, drop the misleading comment) |
| `confidence` DOMAIN (`numeric(4,3)`, 0–1) | the single confidence scale for every node/edge `confidence` prop; normalize prior `numeric(5,2)`/percent scales to 0–1 on ingest (E5 §8) | **Adopt** (unifies S5/S7 scales) |
| `source_ref` COMPOSITE (`system source_system, native_id text, locator text`) | the flattened provenance pointer carried on each node (the paper's `source_id`+`pg_table`+`pg_pk` triple) | **Adopt** — name collides with `evidence_hash.source_ref` TEXT column (E1 §5.2); keep the composite for graph provenance, rename future *columns* to avoid `source_ref source_ref` |
| `entity_type` ENUM (`person,org,project,tech,location,concept`) | classifies the PG-side entity row a node mirrors | **Adapt — GAP** (see §6): omits forensic core `Incident/Statement/Vulnerability/Evidence`; graph **label** is authoritative, enum must be extended or those stay first-class tables |
| `event_type` ENUM (`milestone,decision,meeting,incident,change,memory,upcoming`) | `:Event` node `event_type` | **Adapt — vocab mismatch** (PM-flavored; forensic incident taxonomy `medical_neglect/withholding/threat/…` is richer → a domain column on `analysis.timeline_event`, not this enum) |
| `mcl_factor` ENUM (`a`…`l`) | `:CustodyFactor` / `:SUPPORTS_FACTOR` factor key | **Adopt** (canonical superset; AB wins over S2's c/f/g/j/k subset — E5 §8). **Flag the J↔K label-swap bug** from `mcl_722_23.ttl` (E4 §6.2): key on statutory definition, not the buggy `.ttl` label |
| `temporal_class` ENUM (`historical,current,future`) | coarse staging on `:Event`; finer `t_precision/t_certainty` (`exact/approximate/inferred/uncertain`) is the per-fact axis missing from all prior schemas (added in §06 §5) | **Adopt** + extend |

**Note:** Neo4j itself uses none of these PG types directly (graph props are untyped). They govern the
**PG-side `id_xref` crosswalk table and entity mirror** that the seed projects from; the graph just
carries their *values* as string props. The crosswalk table itself is an **adopt** of the E5-S3 Zep
`zep_node_id`/polymorphic-edge precedent, re-expressed with these typed `0004` enums.

---

## 3. Fix the `disclosure_tier` double-definition (E1 §5.1) — graph-side resolution

The two incompatible `disclosure_tier` definitions map to **two different graph property lanes**; the
graph makes the split unavoidable, so resolve it the same way as the PG fix:

| As-built source | Values | Meaning | **Reconciled name** | Carried on graph as |
|---|---|---|---|---|
| `0003` text CHECK (the substantive one) | `contemporaneous, hindsight, discovered` | bitemporal **knowledge-horizon** (when a fact became known vs the event) | keep as `disclosure_tier` / `knowledge_horizon` | edge prop `knowledge_horizon`, alongside `valid_from/valid_to` + `recorded_at/invalidated_at` |
| `0004` ENUM (the mis-commented one) | `public, restricted, sealed` | **access sensitivity / classification** | **rename → `sensitivity_tier`** | node/edge prop `sensitivity_tier`, aligned to the `evidence`/`analysis`/`public` boundary + `safe_for_legal_use` gate |

These are **orthogonal** to the §06 five-tier `assertion_type` epistemics
(`raw_evidence|extracted_fact|inferred_fact|analytical_finding|legal_conclusion`). All three coexist as
distinct props — never conflated. Action: rename the `0004` enum to `sensitivity_tier` (PG migration);
the graph carries `knowledge_horizon` (bitemporal), `sensitivity_tier` (access), and `assertion_type`
(epistemic) as three separate properties.

---

## 4. What is graph vs what stays relational (confirmed)

Decision rule unchanged from §06: **Neo4j stores relationship-shape + identity keys; PG stores content,
bytes, full provenance, and versioned history.** Promotion rule: a relational row reaches the graph only
if (a) it participates in a relationship a human/agent will traverse, or (b) it needs
network/path/contradiction analysis. High-volume raw rows (every GPS ping, every raw activity segment,
full message bodies, OCR text, vectors, custody bytes) **stay in PG/DuckDB/Milvus**; only
**resolved entities, significant/stay-point events, claims, contradictions, patterns, findings, legal
links** are projected. See §06 §2 table for the full data→home matrix (it is correct once the schemas
in §1 above are substituted).

- **sha256 = canonical evidence identity.** `:Evidence.pg_pk` → `evidence.evidence_hash(id)`; the node
  carries the `sha256` digest ref (BYTEA in PG, hex string in graph). **md5 = pre-filter only**, never an
  identity key. Custody hashing = `pgcrypto.digest(…, 'sha256')` (PG side; E1 §1, addendum §A/D6).
- Append-only everywhere: superseding a fact sets `invalidated_at` on the old edge and MERGEs a new one;
  originals and prior interpretations are never overwritten (§06 §6).

---

## 5. Node labels & edge types (adopt §06 §3–§4 wholesale, with provenance)

The §06 §3 label set and §4 edge set are **adopted unchanged** (only the `pg_table` schema is corrected
per §1). Provenance/classification, condensed:

- **Adopt (court-grade, deterministic):** `:Person`, `:Location`, `:Event`/`:Incident`, `:Statement`,
  `:Evidence` and edges `WAS_AT`, `PARTICIPATED_IN`, `MADE_STATEMENT`/`AUTHORED`, `CONTRADICTS`,
  `EXPOSED_CHILD` — from **salem_v3** (E5 S1/S2; A3 §A). `:Message`, `:Device`, `:Identifier`,
  `:Platform` from **TraceIQ V4.1** (A3 §C); `:Person` **merges** TraceIQ `people` ↔ salem `Person`.
- **Adapt (sensitive, HITL):** `:Vulnerability`, `:Tactic`, `:Pattern`/`:BehavioralPattern` — salem_v3
  + the **behavioral ontology** (`behavioral_patterns.ttl`, `detection_patterns.py` 256/18-cat/DARVO,
  `mcl_722_23.ttl`; E4). `AFFECTED_ACCESS`→**`AFFECTED_PARENTING_ACCESS`** (renamed for precision).
- **Preserve-as-Hypothesis (allegation ≠ fact, HITL before court):** `USED_TACTIC`,
  `TARGETED_WOUND`→**`EXPLOITED_VULNERABILITY`**, `SPREADS_RUMOR`→**`DISPARAGES`** (all `hypothesis=true`,
  `safe_for_legal_use=false`).
- **Split:** vague `RELATED_TO` → typed `:PRECEDED`/`:FOLLOWED`/`:ANCHORED_TO`/`:CO_OCCURRED`/`:PART_OF`
  (temporal) · `:CAUSED` (causal, hypothesis-only — causation≠correlation) · `:CONTRASTS_WITH` (topical).
- **Add (both-parties / full-cycle — NEEDS OWNER SIGN-OFF, extends VIP salem_v3, does not replace it):**
  `:CyclePhase`/`:RelationshipPhase` (`calm/tension/escalation/reconciliation/love_bombing/separation`),
  `:DURING_PHASE`, `:REACTION_TO`, `conduct_party` prop — sourced from **`positive_behaviors.ttl`** (E4
  §5; "do NOT invent new node types"). Models the user's own conduct/repair with the same fidelity as
  adverse conduct (CONTEXT_PACK §6; MP 2431–2444).
- **Graphiti-managed structural labels** (`:Episodic`, `:Entity`, `:Community`) are Graphiti's, not
  redefined; case-KG nodes carry **both** a domain label and `:Entity` when written via the JSON-episode
  path, so Graphiti's bitemporal bookkeeping and our ontology coexist on one node.

**Deprecate:** markdown `output_format` blobs (A3 §F) — structured rows only. **Preserve-as-Note:**
brittle FB/Snapchat CSS parser configs feed PG, not the graph.

---

## 6. GAP carried forward (not silently invented — flagged for HITL)

1. **`entity_type` enum omits the forensic core** (E5 §8): `Incident/Statement/Vulnerability/Evidence`
   are graph labels with **no enum member**. Recommend: either extend the `0004` `entity_type` enum, or
   (preferred) keep them as first-class `analysis.*` tables and let the **graph label** be authoritative.
   Owner decision needed.
2. **No alias / identity-resolution structure in AB** — only prior precedent is Zep `Person.aliases`
   (E5 S3). The `:IDENTIFIED_BY` edge + `id_xref(match_method)` is the graph-side surface; the PG-side
   alias/resolution table is a **gap** to build (uses `fuzzystrmatch`+`pg_trgm`+`citext`).
3. **`:CAUSED` and every hypothesis edge** stay `safe_for_legal_use=false` pending review; the
   causation-vs-correlation and selective-framing checks are review-gatekeeper responsibilities, not
   encoded in the graph alone.
4. **Semantica wiring (ADR ~0035) assumed, not confirmed** — the adapter (§7) is the hedge; only the
   adapter's Semantica binding changes if the real impl differs.
5. **Graphiti default extractor is cloud-LLM** — the privacy guardrail (seed-first + structured-JSON
   episodes + local ≤4B for any case content) must be enforced in the adapter **and** the deployed
   `graphiti` MCP server config before any case content is ingested. Verify model binding.

---

## 7. Graph Write Adapter, bitemporal mapping, provenance, constraints (adopt §06 §5–§13)

- **Adapter = single chokepoint** for all writes (Graphiti, Semantica, manual). Enforces the §06 §5
  property block (`uid, pg_table, pg_pk, provenance_id, source_id, assertion_type, confidence,
  hypothesis, safe_for_legal_use, review_status, human_review_id, writer, write_batch_id, lane,
  group_id, knowledge_horizon, sensitivity_tier, valid_from/valid_to, recorded_at/invalidated_at,
  t_precision/t_certainty, ontology/schema/prompt/model_run versions`). **Traceable** (`writer`),
  **separable** (`group_id`/`lane`), **reversible** (`write_batch_id` → `DELETE` by batch), **idempotent**
  (`MERGE` on `uid`). **Privacy guardrail:** blocks cloud-LLM extraction on `lane=case_kg`; routes case
  content to local ≤4B. **HITL gate:** sensitive labels/edges written `safe_for_legal_use=false`;
  promotion requires the `agno-gateway` **review-gatekeeper** approval → `public.agno_approvals`
  (`human_review_id`). No silent `hypothesis=true`→`false` flip.
- **Bitemporal mapping to Graphiti native** (§06 §6): our `valid_from/valid_to` ↔ Graphiti
  `valid_at/invalid_at`; `recorded_at/invalidated_at` ↔ `created_at/expired_at`. PG-side mirror tables
  enforce no-overlap via **`btree_gist EXCLUDE` on `tstzrange`** (addendum §D3); the graph is
  append-only.
- **Provenance:** `provenance.provenance` is the PG system-of-record; graph carries `provenance_id`
  pointer + flattened subset. Semantica writes modeled on PROV-O (`prov:Entity/Activity/Agent`).
- **Constraints/indexes:** `uid` UNIQUE per domain label; btree on `pg_pk`, `provenance_id`, `source_id`,
  `group_id`, `write_batch_id`, `review_status`, `safe_for_legal_use`, `valid_from/valid_to`.
  Court-facing default filter: `WHERE n.safe_for_legal_use = true AND n.hypothesis = false`.
- **Two-phase Semantica** (§06 §10): **SEED** = deterministic FK projection from PG (zero LLM,
  court-grade, idempotent); **HYBRID** = local ≤4B enrichment, every write `hypothesis=true`,
  review-gated. Node embeddings → Milvus (`vector_id` back-ref).
