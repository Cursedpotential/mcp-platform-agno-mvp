# S1 — Milvus Collections (Reconciled to As-Built Law)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Resource 2 of 4** in the data-tier topology (PG+PostGIS+pg_duckdb · **Milvus** · Neo4j · SurrealDB).
> Milvus is its **own independently-restartable resource** — a Milvus crash must never tear down PG/Neo4j/SurrealDB (Context Pack §1; self-hosted Milvus 3.0 + WoodPecker + Attu v3 on Coolify/ovh2, ADR-0026).
>
> **What this doc is.** A reconciliation of the paper design (`sections/05-milvus.md`, 8 collections + shared envelope) against the **as-built law** (`extracted/E1_asbuilt_inventory.md`; migrations `sql/0001–0004`) and the addendum (`forensic-db-extension-and-reconciliation-addendum.md`). The paper's collection set, hybrid-search model, and append-only discipline are **ADOPTED**. The reconciliation deltas are: (1) re-home every PG-linkage `pg_schema` onto the three as-built schemas; (2) reuse the `0004` custom types as the cross-store link contract; (3) fix the `disclosure_tier` double-definition; (4) state the BM25 resolution; (5) pin the custody anchor to the real `evidence.evidence_hash`.
>
> **Milvus owns primary semantic + hybrid dense+sparse/BM25 retrieval (ADR-0027).** It is the *index, not the source of truth*: raw bytes + canonical rows live in PG (`agno-postgres:18-duckdb`, ADR-0013) and R2 (ADR-0007). Milvus is fully **rebuildable from PG** — disposable index.

---

## 1. Reconciliation deltas vs. the paper (what changed and why)

| # | Paper (sections/05) | As-built law (E1 / addendum) | Decision | Provenance |
|---|---|---|---|---|
| D1 | `pg_schema` ∈ {`evidence`,`multimodal`,`timeline`,`analysis`,`legal`,`provenance`} | **Only 3 schemas exist**: `evidence` (RO), `analysis` (write-after-approval), `public` (HITL audit + Agno) | **ADAPT** — re-home every linkage triple onto the 3 schemas; the paper's `multimodal/timeline/legal/provenance` become **table-name sub-domain prefixes** inside `evidence`/`analysis` (§2). | E1 §0; addendum §B |
| D2 | `disclosure_tier INT8` labelled "bitemporal disclosure tier" (single field) | `disclosure_tier` is **double-defined**: 0003 TEXT `contemporaneous/hindsight/discovered` (substantive bitemporal) vs 0004 ENUM `public/restricted/sealed` (access class) | **SPLIT** — keep `disclosure_tier` = the 0003 temporal vocab; add a **separate** `sensitivity_tier` for the access vocab (rename of the 0004 enum, per the agreed fix). Both first-class filterable scalars. | E1 §5.1; addendum §B bug |
| D3 | Join key = bare `pk == pg uuidv7` + free-text `pg_schema/pg_table/pg_pk` | `0004` ships `source_system` enum (`postgres/neo4j/milvus/surrealdb`), `match_method` enum (`exact/resolved/manual`), `source_ref` composite, `canonical_id` domain | **ADOPT** the custom types as the link contract: `milvus_pk ↔ PG row` recorded in an `analysis.id_xref` spine keyed by **`source_system`** (`'milvus'` ↔ `'postgres'`) with `match_method`; the PG row's `embedding_ref` = the Milvus `pk` (§5). | E1 §3.1; guardrail "milvus_pk ↔ analysis row id via source_system" |
| D4 | `source_id` → `custody.source` | No `custody` schema; custody = **`evidence.evidence_hash`** (`digest BYTEA` sha256, `blob_key`, `source_ref`, `meta`), append-only, 32-byte CHECK | **ADAPT** — `source_id` → `evidence.evidence_hash(id)`; **sha256 = canonical evidence identity** (md5 only a pre-filter, never stored as identity). | E1 §2.3 |
| D5 | Lineage table `provenance.vector_embedding` | `provenance` is not a schema | **ADAPT** — land it as **`analysis.vector_embedding`** (append-only embed lineage; was the stray-`public` risk the paper itself flagged, §9 item 7). | paper §5; E1 §0 |
| D6 | BM25 "Milvus BM25 Function" only | `pg_textsearch` **STAGED-not-baked**; BM25-location conflict (ADR-0013 vs ADR-0027) | **RESOLVED** (state explicitly): **Milvus owns primary semantic/hybrid/BM25**; PG keeps `tsvector`+`pg_trgm` for cheap local lookups; `pg_textsearch` is an **optional staged PG-local fallback**, not baked preemptively. | addendum §A; ADR-0027 |
| D7 | `D_TEXT=2048` from `nemotron-embed-vl-1b-v2` local CPU | Hardware = **CPU-only, models ≤4B, evidence stays local**; NIM dim contract ADR-0011 | **ADOPT with BLOCKING review** — dims are placeholders (`D_TEXT`/`D_IMG`/`D_CODE`/`D_CB`) until the live ovh2 instance is verified; cloud embedding of raw evidence is **forbidden without owner sign-off** (§7). | ADR-0011/0015; paper §2/§9 |

Everything else from the paper (the 8-collection split by content type within one embedding space, the shared envelope, RRF hybrid fusion, court-facing profile, append-only `superseded`, partition_key=`case_id`) is **ADOPTED unchanged**.

---

## 2. PG-linkage re-homing map (the law: 3 schemas only)

Sub-domain words (`media/timeline/legal/work/ocr`) survive as **table-name prefixes**, never as schemas. Raw vs derived obeys the security boundary: **raw → `evidence` (RO)**, **extracted/inferred/analytical/legal → `analysis` (write-after-approval)**.

| Collection | Paper `pg_schema.pg_table` | **Reconciled `pg_schema.pg_table`** | Lane | Note |
|---|---|---|---|---|
| `ev_message` | `evidence.message` | **`evidence.message`** (PK `message_id` uuidv7) | raw evidence | Stays — adopt from TraceIQ V4.1 `messages` (A3 §C). OCR-sourced bodies flag `assertion_type=extracted_fact`. |
| `ev_ai_transcript` | `provenance.work_artifact` | **`analysis.work_artifact`** (`artifact_kind='ai_transcript'`) | derived work-product | Re-homed; kept strictly **separate** from canonical evidence facts. Aligns with the existing `public.transcript_insight` (ChatMiner) but lives in `analysis` as derived. |
| `ev_ocr_text` | `multimodal.image` | raw img **`evidence.media_image`** · OCR **`analysis.media_ocr`** (vector links the OCR extraction) | extracted fact | OCR = extracted, so the canonical vector row is the `analysis.media_ocr` span referencing `evidence.media_image`. |
| `ev_event_summary` | `timeline.event` | **`analysis.timeline_event`** (FK → `analysis.normalized_record`) | derived/normalized | Timeline events are normalized artifacts; merge with the as-built `analysis.normalized_record` spine (record_type `event`). Adapt TraceIQ `timeline_enriched` (A3 §B). |
| `ev_claim` | `analysis.claim_verification` | **`analysis.claim_verification`** | extracted + analytical | Stays. Adapt TraceIQ `expected_schedule` claimed/observed (A3 §C). |
| `ev_pattern_finding` | `analysis.finding` | **`analysis.finding`** (+ `analysis.finding_version`) | analytical_finding | Stays. Seeded from ~303-pattern lib + `positive_behaviors.ttl` (full-cycle, both parties). |
| `ev_legal_issue` | `legal.legal_issue` | **`analysis.legal_issue`** (+ `analysis.evidence_relevance`) | legal_conclusion | Re-homed; `legal` → table prefix. Seeded `mcl_722_23.ttl` (A–L), reusing `mcl_factor` enum + `ltree` factor trees. |
| `ev_multimodal_desc` | `multimodal.scene_description` | desc **`analysis.media_scene_description`** · raw media **`evidence.media`** | inferred/analytical (caption) | Re-homed; model captions are analytical, raw media is evidence. |
| _(lineage)_ | `provenance.vector_embedding` | **`analysis.vector_embedding`** | provenance | Append-only embed lineage (§5). |
| _(custody anchor)_ | `custody.source` | **`evidence.evidence_hash`** | custody | `source_id` → `evidence.evidence_hash(id)`; sha256 identity. |

`pg_schema` field domain therefore collapses to exactly **{`evidence`,`analysis`,`public`}** — cleaner and law-compliant.

---

## 3. Shared entity envelope (reconciled)

Every collection inherits one field contract (paper §3) so retrieval/filter/provenance/HITL behave identically. **Reconciliation edits are bolded.**

| Field | Milvus type | Role | Reconciliation |
|---|---|---|---|
| `pk` | `VARCHAR(64)` PK | UUIDv7 of canonical PG row (ADR-0013); chunked = `{parent_uuid}:{chunk_seq}` | 1:1 PG join; no Milvus auto-id. |
| `dense` | `FLOAT_VECTOR(D_TEXT)` / `(D_IMG)` | Dense ANN, HNSW, COSINE | dim = placeholder (§7). |
| `sparse` | `SPARSE_FLOAT_VECTOR` | Lexical ANN | filled by Milvus **BM25 `Function`** over `text` — CPU-friendly, no external encoder (D6). |
| `text` | `VARCHAR(65535, enable_analyzer)` | BM25 input + snippet | full record stays in PG (lean-payload rule). |
| `case_id` | `VARCHAR(64)` | **Partition key** | generalized from "Salem v. Kinzel" caption. |
| **`disclosure_tier`** | `INT8` | **Bitemporal knowledge-horizon** | **`0 contemporaneous · 1 hindsight · 2 discovered`** — mirrors `analysis.normalized_record.disclosure_tier` (0003 TEXT CHECK). **NOT** the access vocab. (D2) |
| **`sensitivity_tier`** | `INT8` | **Access classification (NEW)** | **`0 public · 1 restricted · 2 sealed`** — the renamed `0004` enum (`sensitivity_tier`); aligns with the schema security boundary. (D2) |
| `assertion_type` | `INT8` | **Evidence-class guard** | `0 raw_evidence · 1 extracted_fact · 2 inferred_fact · 3 analytical_finding · 4 legal_conclusion` (mirror PG enum to be added in `analysis`). |
| `confidence` | `FLOAT` | rank/gate | maps `0004` `confidence numeric(4,3)` domain; **never** hard-coded 0.6 (A3). |
| `timestamp_certainty` | `INT8` | **Time-trust guard** | `0 exact · 1 approximate · 2 inferred · 3 uncertain` — the precision class missing from ALL prior schemas (A3 §B). |
| `event_time_utc` | `INT64` | valid-time filter | epoch ms; `-1` non-temporal; full `_raw`+`tz_offset`+precision in PG. |
| `ingested_at_utc` | `INT64` | knowledge-time | bitemporal write time. |
| `source_id` | `VARCHAR(64)` | **Custody anchor** | → **`evidence.evidence_hash(id)`** (sha256 chain). (D4) |
| `pg_schema`/`pg_table`/`pg_pk` | `VARCHAR` ×3 | **PG linkage triple** | `pg_schema` ∈ {`evidence`,`analysis`,`public`} only (D1). |
| `xref_id` | `VARCHAR(64)` | **Cross-store link (NEW)** | → `analysis.id_xref` row; `source_system='milvus'` ↔ `'postgres'`, `match_method`. (D3) |
| `provenance_id` | `VARCHAR(64)` | provenance join | → `analysis.vector_embedding` / run bundle (D5). |
| `embedding_model`/`embedding_dim`/`embedding_version` | `VARCHAR`/`INT16`/`VARCHAR` | embedder lineage (ADR-0011) | re-embed = new vector + version bump (append-only). |
| `prompt_version`/`ontology_version`/`schema_version`/`run_id` | `VARCHAR` ×4 | artifact lineage | trace any derived vector to its run/prompt/ontology/schema. |
| `review_status` | `INT8` | **HITL gate** | `0 pending · 1 approved · 2 rejected · 3 needs_review`; court-facing forces `==1`. |
| `is_sensitive` | `BOOL` | in-camera flag | from `is_private`/`requires_in_camera_review` (A3 §C). |
| `is_hypothesis` | `BOOL` | hypothesis guard | model interpretation; never auto-promoted to fact. |
| `subject_party` | `INT8` | **Both-parties guard** | `0 unknown · 1 user · 2 counterparty · 3 child · 4 third_party` — models the user's OWN conduct too (A3 ontology gap). |
| `superseded` | `BOOL` | soft-delete | append-only correction; old vector flagged, never overwritten (§6). |

---

## 4. The eight collections (reconciled linkage)

All `partition_key=case_id`; all text collections share the **one** `D_TEXT` dense space (split by content type for lifecycle/partitioning/HITL, not geometry). Embedding target + hybrid fields per paper §4; PG link re-homed per §2.

| Collection | Embedding target | Dense dim | Reconciled PG link (`pg_schema.pg_table`) | Key extra scalars | Hybrid / filters | Primary `assertion_type` | HITL |
|---|---|---|---|---|---|---|---|
| **`ev_message`** | message body (chunk → `chunk_seq`,`parent_pk`) | `D_TEXT` | `evidence.message` (PK `message_id`) | `platform`,`direction`,`sender_identity_id`,`thread_id`,`device_id`,`linked_location_event_id`,`tone_surface`,`inferred_intent`,`relational_function`,`cycle_phase` (positive/neutral/love-bombing/repair/conflict — **NOT only negatives**) | dense+BM25 RRF; filt `platform`,`direction`,`event_time_utc`,`cycle_phase`,`subject_party` | raw_evidence | in-camera flag |
| **`ev_ai_transcript`** | session transcript chunks | `D_TEXT` | `analysis.work_artifact` (`artifact_kind='ai_transcript'`) | `model_name`,`prompt_version`,`tool_call_ref`,`session_id`; `is_hypothesis=true` default | dense+sparse; default `assertion_type IN (inferred,analytical)`; "model-generated, unverified" badge | inferred/analytical | **always (model output)** |
| **`ev_ocr_text`** | OCR span per image region | `D_TEXT` | `analysis.media_ocr` → `evidence.media_image` | `region_ref`,`ocr_engine`,`ocr_confidence`,`perceptual_hash`,`linked_message_id` | dense+sparse (**BM25 strong** — names/handles/dates/phones); filt `ocr_confidence`,`is_sensitive` | extracted_fact | sensitive flag |
| **`ev_event_summary`** | NL summary of a timeline event | `D_TEXT` | `analysis.timeline_event` (FK → `analysis.normalized_record`) | `event_type`,`device_id`,`location_id`,`summary_author`,`is_inferred`,`multi_device_split` | dense+sparse + `event_time_utc` range + `event_type` | raw/extracted | low |
| **`ev_claim`** | claim text (claimed) + observed, paired `pair_id` | `D_TEXT` | `analysis.claim_verification` | `pair_id`,`claim_side`(claimed/observed),`claimant_identity_id`,`is_anomaly`(**gated**),`tolerance_ref`,`subject_party` | dense+sparse; filt `claim_side`,`is_anomaly` | extracted + analytical | anomaly label |
| **`ev_pattern_finding`** | finding desc + matched-pattern rationale | `D_TEXT` | `analysis.finding` (+ `analysis.finding_version`) | `pattern_id`,`pattern_polarity`(negative/neutral/positive/love_bombing/repair),`subject_party`,`cycle_phase`,`sensitive_label`(**NULL until approved**),`evidence_cite_count`(≥1) | dense+sparse; court-facing forces `review_status==1 AND sensitive_label IS NOT NULL` | analytical_finding | **HARD (sensitive labels)** |
| **`ev_legal_issue`** | issue/factor summary | `D_TEXT` | `analysis.legal_issue` (+ `analysis.evidence_relevance`) | `factor_code`(A–L / `mcl_factor` enum),`issue_type`,`legal_relevance_label`(**HITL**),`is_legal_conclusion` | dense+sparse; filt `factor_code` | legal_conclusion | relevance label |
| **`ev_multimodal_desc`** | caption text → `D_TEXT`; **+ image → `D_IMG`** (2nd vector field `dense_img`, same space) | `D_TEXT` + `D_IMG` | `analysis.media_scene_description` → `evidence.media` (`media_id`) | `media_type`,`caption_author`,`media_id`,`frame_ts`,`is_sensitive`,`region_ref` | dense(text)+BM25(caption); **dense(image) cross-modal** fused by RRF | inferred (caption) | sensitive media |

**Cross-modal layout (needs sign-off):** default = single `ev_multimodal_desc` with two `FLOAT_VECTOR` fields (`dense` text `D_TEXT`, `dense_img` image `D_IMG`), both COSINE; alternative = a separate `ev_image` collection if image volume dominates (§7).

---

## 5. PG ↔ Milvus link contract (reuses `0004` custom types — D3)

- **Join key:** Milvus `pk` == PG row `uuidv7` (ADR-0013). Retrieval returns `pk` + scalars + snippet; the app **re-hydrates the authoritative row** from PG via `pg_schema/pg_table/pg_pk`, and the originating raw artifact via `source_id` → `evidence.evidence_hash` (sha256 custody chain).
- **Cross-store xref spine — `analysis.id_xref`** (reuses the as-built types, NOT a parallel invention):

  | Column | Type | Note |
  |---|---|---|
  | `id` | `uuid` (`uuidv7()`) PK | |
  | `system_a` / `native_id_a` | `source_system` / `text` | e.g. `('postgres', pg_pk)` |
  | `system_b` / `native_id_b` | `source_system` / `text` | e.g. `('milvus', milvus_pk)` |
  | `match_method` | `match_method` | `exact` for the 1:1 PG↔Milvus identity link |
  | `confidence` | `confidence` | 0.000–1.000 domain |
  | `source` | `source_ref` (composite) | provenance pointer |

  The PG canonical row carries `embedding_ref = milvus pk`, satisfying §03's "vectors held in Milvus by `embedding_ref`".
- **Embed lineage — `analysis.vector_embedding`** (append-only, re-homed from the paper's `provenance.vector_embedding`): one row per embed write — `pk`, `collection`, `pg_schema/pg_table/pg_pk`, `embedding_model/dim/version` (ADR-0011), `model_run_id`, `prompt_version_id/ontology_version_id/schema_version_id`, `processing_run_id`, `ingested_at_utc`, `superseded_by (nullable)`.
- **Consistency:** PG authoritative; Milvus fully rebuildable. Nightly reconcile diffs PG PKs vs Milvus PKs per collection per `case_id` and re-embeds only the delta.

---

## 6. Append-only / corrections (never overwrite)

Milvus `upsert` overwrites → violates "preserve prior interpretations." Enforced at the pipeline layer: (1) a correction/re-embed **inserts a NEW entity** with fresh `embedding_version` (fresh `pk` when the PG row itself versioned via `analysis.finding_version`); (2) the prior entity is **`superseded=true`** (kept queryable for audit), never physically deleted; (3) default retrieval filters `superseded==false`, an explicit audit mode includes them; (4) physical deletes only via never-delete→`_stale` governance, for true dupes only, with a logged reason. Mirrors the bitemporal substrate (`ingested_at_utc`=knowledge-time, `event_time_utc`=valid-time) **without** making Milvus the temporal authority — Neo4j/Graphiti + SurrealDB remain the bitemporal SSOT (ADR-0014/0024).

---

## 7. Indexing, BM25 resolution, ops & needs-review

- **BM25 resolution (explicit, D6):** **Milvus owns primary semantic + hybrid dense+sparse/BM25** (`SPARSE_INVERTED_INDEX` driven by the Milvus BM25 `Function` over `text`; CPU-friendly, no external encoder) — ADR-0027. PG keeps `tsvector`+`pg_trgm` for cheap local lookups; **`pg_textsearch` is a STAGED, not-baked, PG-local fallback** (do not bake preemptively) — addendum §A.
- **Dense index:** `HNSW` (`M=16`, `efConstruction=256` starting point), metric `COSINE`; fall back to `IVF_FLAT`/`SCANN` only if RAM-bound (CPU-only host → modest query `ef`).
- **Hybrid fusion:** `hybrid_search` + `RRFRanker(k=60)` default; `WeightedRanker` when dense should dominate. Re-rank: NIM rerank for **non-sensitive** only; for **sensitive** evidence keep re-rank **local or skip** (needs owner decision).
- **Court-facing profile:** forced `review_status==1 AND superseded==false`; sensitive labels require approval; every hit carries `assertion_type` + `confidence` + `timestamp_certainty` so a hypothesis can never render as established fact. Sensitive-label search (`ev_pattern_finding`) additionally forces `sensitive_label IS NOT NULL AND review_status==1`.
- **Partition key:** `case_id` on every collection → physical per-case isolation, multi-case-safe.
- **Ingest:** CPU-local embedder is slow → async/batched workers (Windmill on ovh2); back-pressure acceptable (rebuildable index).
- **Hosting:** self-hosted Milvus 3.0 (embedded + WoodPecker) + Attu v3 on Coolify/ovh2 (ADR-0026); **bind-mounted volumes only** (owner mandate); own independently-deployable resource. Canonical recovery path = **re-embed from PG**, not "restore Milvus volume."

**Needs human review (carried forward):**
1. **BLOCKING — embedder locality:** verify `nemotron-embed-vl-1b-v2` runs **locally on CPU** (not cloud-only NIM) before any sensitive evidence is embedded; if cloud-only → switch to a local symmetric model (e.g. `bge-m3` 1024-d) and re-pin `D_TEXT` via an **ADR-0011 amendment**. Never ship raw forensic/abuse evidence to a cloud embedder without explicit owner approval.
2. All dims (`D_TEXT`/`D_IMG`/`D_CODE`/`D_CB`) and index params (`M`,`efConstruction`,`ef`) are **placeholders** until verified against the live ovh2 instance + Attu (as-built unknown — Context Pack §5).
3. `D_IMG` assumed = `D_TEXT` (shared VL space) — verify image-mode output dim before building `ev_multimodal_desc`.
4. Two-vector multimodal layout vs separate `ev_image` — owner pick if image volume dominates.
5. Confirm `analysis.id_xref` + `analysis.vector_embedding` are added to the canonical PG model (not stray `public` tables).
6. CaseBible/code collections (`D_CB=1536`, `D_CODE=4096`) share the Milvus instance but stay in **separate collections** — never mixed with evidence (out of forensic scope, ADR-0026/0027).
