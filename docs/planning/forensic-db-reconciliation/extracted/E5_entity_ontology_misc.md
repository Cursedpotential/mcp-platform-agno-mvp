# E5 — Entity/Identity Ontology + Remaining Prior Schemas

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Scope: extract the entity/identity ontology lane and the remaining prior-iteration schemas
> (Salem Zep ontology, Zep ORM models, Agno-alpha SQL, dial-stack pattern persistence,
> document-intelligence models, Semantica decision/provenance models) and note overlap with
> the as-built `0004_custom_types.sql` (`entity_type` enum + custom types).

## Source files (canonical copies read)

| ID | Artifact | Path |
|----|----------|------|
| S1 | Salem v3 ontology (plain dict) | `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/AI_Config/MCP_Servers/zep-server-reference/ontology/salem_v3.py` |
| S2 | Zep Salem ontology v3 final (Pydantic EntityModel/EdgeModel) | `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/utilities/scripts/zep_salem_ontology_v3_final.py` |
| S3 | Zep server ORM models (Postgres mirror of graph) | `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/AI_Config/MCP_Servers/zep-server-reference/src/db/models.py` |
| S4 | Agno-MCP-Platform-alpha SQL | `dev-resources/Archives/Agno-MCP-Platform-alpha/sql/schema.sql` |
| S5 | dial-stack pattern persistence tables | `dev-resources/Archives/dial-stack/server/database/migrations/create_pattern_persistence_tables.sql` |
| S6 | document-intelligence models | `dev-resources/Archives/dial-stack/mcp-servers/py-mcp-server/src/document_intelligence/models.py` |
| S7 | Semantica decision/provenance models | `dev-resources/Archives/dial-stack/docs/wiki/tools/semantica/semantica/context/decision_models.py` |
| AB | As-built custom types (overlap target) | `Agno-MCP-Platform/sql/0004_custom_types.sql` |

(Each artifact had multiple identical archive copies; one canonical copy of each was read. dial-stack
copies are typically duplicated under `dial-stack/utilities/...` and `OTHER_RESOURCES_TO_SORT/...`.)

---

## 1. Entity types / node types

### S1 Salem v3 (graph-native, 7 entities)
`Person, Incident, Location, Statement, Vulnerability, Tactic, Evidence` — minimal descriptions only,
no fields. This is the conceptual seed.

### S2 Zep v3 final (the rich, queryable iteration — 5 entity types of 10-max, 8 edges of 10-max)
Design principle stated in code: **"Extraction first (who?), then analysis (are they safe?)"** —
each entity carries extraction fields + analysis fields. Zep caps: 10 entity fields, 10 entity types,
10 edge types (hard limits noted in comments).

- **Person** — `relationship_type, connection_to (petitioner/respondent/child/mutual), gender,
  risk_level (safe/high_risk/transient), is_replacement_candidate (bool), role_in_case
  (petitioner/respondent/witness/flying_monkey/neutral)`. Note: `name` auto-populated by Zep, omitted.
- **Location** — `category, safety_status (safe/unsafe/chaotic), owner`. Purpose: prove inconsistencies.
- **Incident** ("Iceberg events") — `event_type (medical_neglect/withholding/drunk_driving/threat/...),
  date_approx, substances_involved, context_of_use (maintenance/party/lethal),
  is_manufactured (bool — staged crisis), strategic_goal, trigger_person, mcl_factor (c/f/g/j/k)`.
- **Statement** ("core atom of evidence", at 10-field cap) — `content_summary, medium,
  topic_cluster (matt_abuse_narrative/sobriety_claim/...), told_to, inconsistency_flag (bool),
  darvo_stage (deny/attack/reverse_victim/reverse_offender/none), deception_strategy,
  contradicts_evidence (bool)`. Note: this entity **replaced** former `Fabricated_Narrative` and
  `DARVO` entities — collapsed into queryable fields (entity-budget compression pattern).
- **Vulnerability** (Factor K/F trauma targeting) — `category, description, owner`.

### S3 Zep ORM (Postgres-backed mirror — adds identity/provenance plumbing)
Same five core entities as Pydantic dataclasses **plus the cross-store + identity columns the graph
ontology lacks**:
- Every model: own `*_uuid` PK + `zep_node_id` (graph↔relational xref) + `created_at/updated_at`.
- **Person** adds `zep_user_id`, **`aliases: List[str]`** (← alias/identity-resolution), `notes`.
- FK-style cross-refs via UUID: `Location.owner_uuid`, `Incident.trigger_person_uuid`,
  `Statement.speaker_uuid` + `Statement.listener_uuid`, `Vulnerability.owner_uuid`.
- `Incident`/`Statement` carry `source_file`/`source_type`/`source_line_number` (provenance).

---

## 2. Relationships / edges (S1 + S2)

S2 edge models (Person/Statement/Incident sources) with typed attributes, registered via
`client.graph.set_ontology(...)`:

| Edge (registered name) | Class | Source→Target | Key attrs |
|------------------------|-------|---------------|-----------|
| `USED_TACTIC` | CoerciveTactic | Person→Incident, Person→Statement | tactic_type (intimidation/isolation/economic_sabotage/suicide_baiting/triangulation), financial_mode |
| `SPREADS_RUMOR` | SpreadsRumor | Person→Person | intent, effect_on_listener |
| `CONTRADICTS` | Contradicts | Statement→Statement, Statement→Incident | discrepancy_type (lie/projection/hypocritical) — "gaslighting detector" |
| `EXPOSED_CHILD` | ExposedTo | Person→Person, Incident→Person | duration, impact (Factor F) |
| `AFFECTED_ACCESS` | Facilitated | Person→Person | action, gatekeeping_subtype (Factor J) |
| `TARGETED_WOUND` | Exploits | Statement→Vulnerability, Incident→Vulnerability | mechanism, is_microaggression |
| `WAS_AT` | WasAt | Person→Location | date_approx, with_whom, source (text/photo/timeline/admission) |
| `MADE_STATEMENT` | MadeStatement | Person→Statement | date_approx |

S1 plain edges add `PARTICIPATED_IN (Person→Incident)` and generic `RELATED_TO (Incident→Incident)`.
S3 stores all edges generically in one **`ZepEdge`** table: `edge_uuid, zep_edge_id, edge_type,
source_uuid/source_table, target_uuid/target_table, attributes JSONB` — a polymorphic edge store.

---

## 3. Alias / identity-resolution + id_xref / cross-store correlation
- **Alias**: only explicit alias structure is `Person.aliases: List[str]` (S3). Graph ontology (S1/S2)
  has none — relies on Zep auto-`name` dedup.
- **Cross-store id correlation** (the id_xref lane): S3's `zep_node_id`/`zep_edge_id`/`zep_user_id`
  columns are the **graph↔relational crosswalk**; polymorphic `source_table`+`source_uuid`/
  `target_table`+`target_uuid` on `ZepEdge` are a generic cross-table pointer. This is the prior-art
  precursor to the as-built **`id_xref` crosswalk + `source_system` enum + `match_method` enum** in AB.
- S5 (dial-stack) correlates by free-text `entity_ids TEXT[]` / `entity1_id`/`entity2_id` (no FK,
  no alias resolution — IDs assumed already canonical upstream).

## 4. Pattern-persistence tables (S5) — HITL approval workflow
7 tables + 2 views + helper fn; all forensic pattern outputs are **pending → approved/rejected**
(human-in-the-loop) before becoming "facts":
- `detected_patterns` (temporal: repeating/sequence/evolution/motif; entity_ids[], occurrences,
  confidence, first/last_seen, pattern_data JSONB) + approval cols.
- `pattern_occurrences` (timeline instances, FK→detected_patterns, evidence_ids[]).
- `evidence_clusters` (kmeans/dbscan/hierarchical/cosine; cohesion metric) + approval.
- `spatial_patterns` (cluster/route/stop/meeting; **`location GEOMETRY(Point,4326)`** + GiST) + approval.
- `geofence_violations` (**auto-approved** — "facts, not interpretations"; entered/exited/present).
- `inferred_relationships` (graph-discovered hidden links: entity1/2, inferred_type, path_length,
  intermediaries[], confidence) + approval.
- `pattern_approval_log` (audit trail: pattern_table+pattern_id, action, actor, prev/new_status).
- Views `pending_patterns` / `approved_patterns` UNION across all 4 pattern tables; common approval
  quartet everywhere: `status, reviewed_by, reviewed_at, review_notes`.

## 5. Document-intelligence tables/models (S6)
Not SQL — runtime dataclasses/enums for a unified OCR/extraction result:
`EngineCapability` (ocr/table_extraction/layout_analysis/format_conversion/chunking/handwriting/
multilingual/form_extraction/context_aware/rag_native), `CostTier` (free/paid/enterprise),
`Locality` (local/cloud/hybrid); `TableCell`, `Table`, and `DocumentIntelligenceResult`
(text, tables[], engine_used, processing_time_ms, confidence, page_count, metadata, success/error).
Relevant as the shape feeding evidence rows (per-engine confidence + provenance of extraction).

## 6. Semantica decision / provenance models (S7)
Decision-tracking dataclasses (banking/legal/insurance framing) with `to_dict/from_dict/validate`:
- **Decision** — decision_id, category, scenario, reasoning, outcome, confidence(0-1), timestamp,
  decision_maker, `reasoning_embedding`, `node2vec_embedding`, metadata. (dual embedding: text + graph)
- **DecisionContext** — entity_snapshots, risk_factors[], cross_system_inputs (provenance snapshot).
- **Policy** — rules dict, version, created/updated (versioned policy).
- **PolicyException** — decision_id, policy_id, reason, approver, approval_timestamp, justification.
- **Precedent** — source_decision_id, similarity_score(0-1), relationship_type
  (similar_scenario/same_policy/exception_precedent).
- **ApprovalChain** — approver, approval_method (slack_dm/zoom_call/email/system), context, timestamp.
This is the provenance/audit + precedent-similarity lane (decision lineage, not entity ontology).

## 7. Agno-alpha SQL (S4) — agent-run lane (low ontology overlap)
`agent_run, approval_request (risk_level low/medium/high/critical; status pending/approved/rejected/
expired), learned_knowledge (namespace, confidence, VECTOR(1536)), transcript_insight (insight_type:
decision/code_artifact/goal/blocker/architecture/next_action/issue_found/learning, related_insight_ids[],
VECTOR(1536))`. Pgvector(1536). Mostly agent-orchestration + the same approval-workflow motif as S5.

---

## 8. Overlap with as-built `0004_custom_types.sql` (AB)

| As-built (AB) | Prior-art precursor | Reconciliation note |
|---------------|---------------------|---------------------|
| `entity_type ENUM (person,org,project,tech,location,concept)` | S1/S2 entities (Person, Location, Incident, Statement, Vulnerability, Tactic, Evidence) | **MISMATCH / gap.** AB enum is generic-knowledge-graph flavored (org/project/tech/concept) and **omits the forensic core types** Incident/Statement/Vulnerability/Evidence the Salem ontology proved load-bearing. If the forensic lane is in scope, add Incident/Statement/Vulnerability/Evidence — or make them first-class tables, not enum members. |
| `mcl_factor ENUM ('a'..'l')` | S2 `Incident.mcl_factor` (c/f/g/j/k subset); inventory MCL A–L table | AB is the superset/canonical (full a–l). Prior code only tagged the custody-relevant subset. Consistent; AB wins. |
| `disclosure_tier ENUM (public,restricted,sealed)` | none in prior schemas | New in AB (bitemporal knowledge-time gating). No prior overlap; note the known disclosure_tier boundary bug tracked elsewhere. |
| `source_system ENUM (postgres,neo4j,milvus,surrealdb)` + `match_method (exact,resolved,manual)` + `id_xref` crosswalk | S3 `zep_node_id`/`zep_user_id` + `ZepEdge.source_table/target_table` polymorphic pointers | Same intent (cross-store correlation). AB cleaner/typed; prior store set was neo4j(Zep)/postgres. Alias resolution (S3 `Person.aliases`) has **no AB home yet** — identity-resolution surface is a gap. |
| `event_type ENUM (milestone,decision,meeting,incident,change,memory,upcoming)` | S2 `Incident.event_type` (medical_neglect/withholding/drunk_driving/threat/...) | **Vocabulary mismatch.** AB event_type is project/PM-flavored; the forensic incident taxonomy (substance/neglect/violence) is far richer and unmapped — likely a domain column/table, not this enum. |
| `confidence DOMAIN numeric(4,3) 0-1` | confidence floats everywhere (S5 numeric(5,2) percent; S7 0-1; S4 numeric(5,4)) | AB domain unifies; prior scales differ. Normalize prior numeric(5,2) cohesion/confidence to 0-1 on ingest. |
| `source_ref COMPOSITE (system,native_id,locator)` | S3 source_file/source_line_number; S6 metadata; S5 evidence_ids[] | AB composite generalizes prior ad-hoc provenance columns. |
| approval-workflow quartet (status/reviewed_by/reviewed_at/review_notes) | S5 + S4 approval tables, S7 ApprovalChain/PolicyException | Strong cross-corpus convergence on HITL pending→approved; keep a single canonical approval pattern + audit log (S5 `pattern_approval_log`). |
| — (no AB equivalent) | S5 `inferred_relationships`, `spatial_patterns`, `geofence_violations`; S7 `Precedent` | Pattern/inference + precedent-similarity lanes have **no as-built home** — candidate new tables. |

### Key gaps surfaced for reconciliation
1. **entity_type enum is too generic** — missing forensic core (Incident/Statement/Vulnerability/Evidence).
2. **No alias / identity-resolution structure** in AB (S3 `Person.aliases` is the only prior precedent).
3. **event_type vocab** is PM-flavored, not forensic; incident taxonomy unmapped.
4. **Pattern-persistence + inferred-relationship + precedent lanes** (S5/S7) are unbuilt in AB.
5. Confidence scale normalization needed (numeric(5,2) → 0-1 domain).
