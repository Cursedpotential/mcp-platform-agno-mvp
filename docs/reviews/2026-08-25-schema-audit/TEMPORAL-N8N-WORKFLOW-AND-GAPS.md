# Temporal + n8n workflow and current gaps

> _Owner-directed architecture record · 2026-08-25 · D-077_

> **Maturity context:** Temporal and n8n entered the platform architecture only within the last
> few days. The incomplete workflow coverage below is expected early integration work, not evidence
> that the new architecture has failed. “Gap” means the next boundary to compose or migrate. The
> exceptions are explicitly identified legacy behaviors that conflict with newer owner rulings.

## Governing boundary

n8n owns the visual business/agent flow: triggers, operator interaction, agent bodies,
notifications, and decisions about which durable process to start or signal. Temporal owns the
durable execution of that process: ordered activity scheduling, retries, timeouts, idempotency,
signals, checkpoints, and execution history.

n8n therefore starts or signals a Temporal Workflow. A Temporal Workflow schedules every tracked
Activity, including calls whose body is an n8n workflow. n8n must not bypass Temporal and invoke a
load-bearing activity directly; doing so would make its execution invisible to the durable history.

Hashing is a standalone callable capability with Temporal Activity wrappers. It is never hidden
inside parsing, normalization, context storage, promotion, or evidence storage. Each calculation or
verification has its own Activity event and append-only result reference.

## PostgreSQL change-detection backbone

PostgreSQL is the canonical source-and-control plane. Every lifecycle state is first committed to
PG. The same transaction appends a domain/outbox event. Change detection claims that event and starts
or signals the appropriate Temporal Workflow. No sister database watches another sister database,
and no sister database can authorize work merely because a row/object appeared there.

The canonical engine is PostgreSQL 18 plus `pg_duckdb`, PostGIS, and pgvector. Analytical/object-
store scans, raw and normalized geo operations, and canonical/local vector identity can therefore
happen under PG authority. External stores remain derived workload surfaces.

```text
PostgreSQL canonical state
  -> PG outbox/change detection
  -> Temporal Workflow/Activity
  -> specialist processor or projection
       Weaviate: search chunks/embeddings
       Neo4j: Semantica semantic candidate/relationship graph
       geo/other engine: modality-native derived state
  -> PG projection result + provenance receipt
  -> PG cross-store reconciliation manifest
  -> Temporal Surreal aggregation Activity
  -> Surreal final temporal graph
  -> PG Surreal projection receipt/readiness state
```

Weaviate, Neo4j, geo, and every other sister database are rebuildable derived surfaces. Their native
payloads remain there, while PG holds canonical source IDs, candidate/fact authority, job identity,
projection generation, target object IDs, provenance, status, counts, hashes, and reconciliation.
Surreal receives a PG-authorized manifest; it never treats a direct sister-store read as authority.

## Data passed between Activities

Temporal history carries only immutable identifiers and compact manifests—not files, full parser
outputs, normalized corpora, or embedding payloads. Activity inputs reference context source
versions, object keys, record-generation IDs, promotion selections, and pinned canon versions.
Activity results return counts, hashes, receipt IDs, status, and failure details. Native bytes and
large record sets remain in object storage/PostgreSQL/specialist stores.

Every mutating Activity is idempotent under a key derived from:

```text
workflow_id + source_version_id + operation + canon/generation/version
```

A Temporal retry must return or reconcile the same durable receipt. It must not create a second
custody assertion, promotion, fact, projection, or chain head.

## Hash execution topology

Hash computation runs on a dedicated `custody-hash` Temporal task queue/worker behind one
canon-dispatching implementation. The compute worker receives read-only access to immutable context
blobs and sealed generation manifests and has no `evidence.*` write credentials. It computes or
verifies bytes and returns a content-addressed result-manifest reference.

The main platform worker owns separate persistence/commit Activities. Provisional results land in
context/working hash-manifest relations; promotion verification attempts remain pre-custody records;
only `commit_custody_promotion_activity` may write accepted hashes and custody events. Temporal
workflow/activity IDs are provenance and idempotency coordinates and never enter hashed bytes.

Required hash Activity family:

- `hash_context_source_activity`: stream immutable original bytes; compute provisional H1; heartbeat
  bytes processed.
- `seal_normalized_generation_activity`: freeze source lineage, parser/normalizer/canon versions,
  unique contiguous ordinals, and the exact ordered membership manifest. This is a data Activity,
  not a cryptographic calculation.
- `hash_normalized_generation_activity`: compute every canonical H2 and full-generation H3; return
  only a manifest reference/digest, canons, member count, and head.
- `persist_provisional_hash_manifest_activity`: validate and idempotently record provisional results.
- `verify_promotion_generation_activity`: independently recompute and compare the complete canon
  tuple and generation; record success or mismatch without writing custody.
- `commit_custody_promotion_activity`: atomically accept the verified manifest into custody and
  create only the selected evidence items.
- `recompute_evidence_generation_activity` plus `append_evidence_reverification_activity`: later
  independent checking and append-only results.
- `record_sbv_import_receipt_activity`: optional raw-source accounting only; it cannot satisfy the
  normalized evidence H2/H3 verification contract.

Retryable failures include transient blob/network/worker/DB availability and serialization errors.
Unknown or ambiguous canons, changed source versions, missing originals, unsealed/gapped membership,
hash/count/order mismatch, unapproved promotion, and idempotency-key/input conflicts are stable
non-retryable failures. Large hashing Activities heartbeat progress; exhausted retries leave the
workflow repairable and produce no false n8n success callback.

## Workflow A — context intake and normalization

```text
n8n trigger/operator action
  -> start ContextIntakeWorkflow in Temporal
  -> land_context_source_activity
  -> compute_h1_fingerprint_activity
  -> inspect_format_activity
  -> parse_activity
  -> persist_parse_staging_activity
  -> normalize_activity
  -> seal_normalized_generation_activity
  -> compute_h2_generation_activity
  -> compute_h3_generation_activity
  -> commit_context_generation_activity
  -> emit context.normalized
```

Responsibilities:

1. `land_context_source_activity` writes the original context source/version and immutable object
   reference. It creates no `evidence.*` row.
2. `compute_h1_fingerprint_activity` invokes the standalone hash capability over original bytes and
   records a provisional `h1-rawbytes-v1` computation receipt.
3. `inspect_format_activity` and `parse_activity` select and execute the best parser behind one
   common parser contract. The deferred SBV/ChatMiner consolidation belongs behind this boundary;
   parser language never changes the result contract or destination.
4. `persist_parse_staging_activity` stores parser output by reference so large payloads never enter
   Temporal history.
5. `normalize_activity` produces deterministic canonical record representations. It does not
   compute hashes internally.
6. `seal_normalized_generation_activity` freezes the source lineage, parser/normalizer versions,
   unique contiguous ordinals, canonical fields, and exact membership manifest.
7. `compute_h2_generation_activity` invokes the hash capability for every normalized record using
   `h2-canonical-v2` and writes provisional computation receipts.
8. `compute_h3_generation_activity` folds the complete ordered H2 generation under
   `h3-chain-h1genesis-hexconcat-v1` and writes the provisional membership/count/head receipt.
9. `commit_context_generation_activity` atomically marks the generation complete only after record
   counts, H2 membership, and provisional H3 reconcile. Nothing becomes evidence.

## Workflow B — owner promotion into custody-backed evidence

```text
n8n owner review
  -> signal/start EvidencePromotionWorkflow
  -> lock_promotion_selection_activity
  -> verify_h1_activity
  -> reproduce_normalization_generation_activity
  -> verify_h2_generation_activity
  -> verify_h3_generation_activity
  -> commit_custody_promotion_activity
  -> emit evidence.promoted
```

The verification Activities independently read the original source and pinned normalization policy;
they do not trust provisional values merely because they exist. Any H1, H2, H3, membership, order,
count, or canon mismatch fails closed. The failed attempt is recorded for review, but no partial
custody chain is written.

`commit_custody_promotion_activity` is the sole transaction that creates/reuses the custody source,
records accepted H1/H2/H3 assertions and custody events, creates the selected evidence item(s), and
appends the promotion result. H3 covers the complete backing normalized source generation while the
promotion decision identifies only the selected records approved as evidence.

## Workflow C — evidence reverification

```text
n8n manual/scheduled request
  -> start EvidenceReverificationWorkflow
  -> load_accepted_hash_manifest_activity
  -> reverify_h1_activity
  -> reverify_h2_generation_activity
  -> reverify_h3_generation_activity
  -> append_reverification_result_activity
  -> notify_or_open_integrity_review_activity
```

Reverification never updates prior hashes. It appends a pass/fail result and exact computation
receipt. A mismatch opens an integrity review and prevents dependent promotion/projection work from
silently continuing.

## Workflow D — semantic extraction and governed facts

```text
PG context.normalized / evidence.promoted outbox event
  -> start SemanticExtractionWorkflow in Temporal
  -> semantica_extract_activity
  -> persist_candidate_batch_activity
  -> project_semantica_neo4j_activity
  -> record_neo4j_projection_receipt_activity
  -> n8n review/agent workflow
  -> signal governance decision
  -> establish_fact_activity
  -> append fact.established outbox event
```

Semantica extracts provenance-linked entity, relation, event, temporal, claim, and conflict
candidates and resolution proposals. It does not declare truth. `establish_fact_activity` applies
the governed decision and exact source support in PG. Neo4j is primarily Semantica's graph surface:
every node and edge carries PG candidate IDs, exact source record/chunk/span identities, extraction
run/version, temporal fields, and candidate/governance state. The Neo4j write is incomplete until
its receipt returns to PG and reconciles. Established facts are not inferred from graph presence.

## Workflow E — specialist projection and Surreal aggregation

```text
PG source/fact/projection-change outbox events
  -> start SpecialistProjectionWorkflow
  -> project_weaviate_search_activity
  -> project_neo4j_semantic_or_fact_activity
  -> project_geo_or_other_modality_activity
  -> record each projection receipt in PG
  -> reconcile_cross_store_generation_activity
  -> if reconciled and governed: project_surreal_generation_activity
  -> record Surreal receipt/readiness in PG
```

Weaviate is the search surface. Every vector object contains or resolves through PG to the exact
source/version, normalized record, chunk/span boundaries, projection generation, custody/promotion
state, `occurred_at`, `source_available_from`, disclosure/access policy, and embedding version.
Search applies the horizon/access predicate before ranking and returns source-resolving hits; a
similarity hit is never a fact or promotion decision.

Neo4j holds Semantica-derived semantic candidates and relationships and may receive a governed-fact
projection after approval. Candidate and fact labels/graphs remain distinguishable. Every graph
element resolves to PG provenance; unsupported/fabricated edges are prohibited.

`reconcile_cross_store_generation_activity` verifies required receipts, input/output counts, object
IDs, source links, versions, hashes, governance state, and revocation state. It seals one immutable
PG aggregation manifest. Surreal receives that manifest plus typed references into PG and the
  specialist stores. Raw originals remain in custody storage; canonical/normalized state and geo
  remain in augmented PG; serving vectors remain in Weaviate; semantic graph details remain in Neo4j.

## Workflow F — final paired walk and delta analysis

```text
n8n investigation request
  -> start PairedWalkWorkflow
  -> pin_surreal_projection_activity
  -> run_as_lived_walk activities (ordered horizon steps)
  -> run_hindsight_walk activity
  -> compare_walks_activity
  -> persist_delta_candidate_activity
  -> n8n owner review / legal-work workflow
```

Temporal pins one reconciled Surreal projection generation and immutable run specification. The
as-lived walk advances one horizon step at a time; hindsight requires an explicit grant. Surreal is
the final temporal-graph retrieval and analysis surface. Healthy pauses resume a reconciled
checkpoint; terminal drift seals the run and creates a linked rewalk. Delta output remains
analytical until governed.

## Current implementation reality

| Area | Present now | Gap to target |
|---|---|---|
| Temporal infrastructure | Server/UI/worker deployment and a restart durability probe are recorded as live; workflow/activity modules exist. | The lifecycle workflows are not yet broadly dispatched end-to-end; this is expected for the newly adopted stack. |
| Transcript workflow | Inert `ChatTranscriptIngest`: `custody -> parse -> store -> knowledge`. | Wrong D-069 boundary; custody occurs before context/normalization/promotion. Replace, do not extend as the target. |
| Activity granularity | Four coarse Activities wrap existing functions. | Parsing, normalization, storage, hashing, promotion, extraction, projection, and walk execution need explicit boundaries. |
| Hashing | H1 is embedded in `custody_activity`; SBV computes raw H2/H3 inside its parser path. | No standalone Temporal hash Activity family; no D-075/D-076 normalized H2/H3 compute/verify/reverify flow. |
| Hash service | Importable Go `custodyhash` package exists for SBV raw-record formulas. | No production callable implements `h2-canonical-v2` plus `h3-chain-h1genesis-hexconcat-v1`; TODO-207 remains open. |
| Normalized generation | Normalized rows exist, but no immutable full-generation membership object governs their sequence. | D-076 cannot be verified until source lineage, exact unique/contiguous ordinals, parser/normalizer versions, membership count, and manifest digest are sealed. |
| Canon edge cases | Existing message-oriented H2 recipe assumes sequence, role, UTC occurrence, and content. | Null/non-message canonicalization is underspecified; it must fail closed or receive a separately versioned recipe rather than silently hashing empty fields. |
| Context-first intake | Existing activity calls `ingest_artifact()` and writes `evidence.*`. | No context-only source landing Activity or promotion-only custody writer. |
| Parser handoff | Current parse Activity sends full records through Temporal payloads and warns about the ~2 MiB limit. | Persist parser output and pass an immutable staging reference. Deferred universal router must preserve one contract/destination. |
| Normalization | Hidden inside `store_activity`. | Must be its own version-pinned Activity producing a deterministic generation for H2/H3. |
| Promotion | Ledger/schema concepts exist. | No working owner-promotion Temporal Workflow, independent hash verification chain, or atomic promotion-to-custody writer. |
| n8n bridge | Generic `n8n_webhook_activity` and `ClassificationBatchPipeline` demonstrate Temporal-owned retries/history. | Recorded n8n workflow JSONs are staged/not yet imported; ingest, promotion, review, extraction, projection, reverify, and walks are not bound. This is early composition work. |
| HITL | Temporal Signal gate patterns exist. | Workbench/n8n decisions are not wired consistently to promotion/fact/walk workflows. Review payloads need immutable decision IDs, not blanket batch approval. |
| Semantica | Candidate sink/worker code exists but is deployment-gated and effectively test-only. | No Temporal extraction workflow, production trigger, reviewer, fact promoter, or downstream projector. |
| Specialist stores | PostgreSQL and vector/message projections exist; geo is parked/deferred. | No governed fact projection receipts spanning every modality and no single reconciliation manifest. |
| PG change detection | Native vector outbox/job machinery and Stage-2 CDC direction exist. | No universal domain-event/outbox contract starts every Temporal projection/extraction workflow; several paths still call downstream stores directly or optionally skip. |
| Weaviate source linkage | Native evidence projection joins chunks to normalized records/source availability and native search prefilters. | Native collection/jobs were recorded empty/unactivated; context/legacy paths differ; source-span, promotion/governance, projection receipt, and result-resolution contracts are not uniformly enforced. |
| Neo4j/Semantica | Semantica candidate contracts and a future graph configuration exist. | No production Semantica-to-Neo4j writer, exact node/edge provenance contract, PG projection receipt, governance-state projection, or reconciliation reader. |
| Sister-store return path | Some PG outbox/job state exists for vectors. | No uniform completion receipt returns object IDs/counts/hashes/source-link validation from every sister store to PG. |
| Surreal final graph | ADR/model target exists; legacy instance is parked. | No production graph schema/projector/reconciler, no canon-aware horizon query surface, and no agent binding. |
| Walk/delta | PostgreSQL walk derivation and search API scaffolding exist. | No Temporal paired-walk orchestration, n8n agent binding, Surreal retrieval execution, belief accumulation, or final delta product. |
| Observability | Temporal history and Postgres run ledgers both exist conceptually. | Correlation contract is incomplete. Every Activity must carry workflow/run/activity/attempt and domain receipt IDs; PG remains domain authority. |
| Hash progress/retry | Current synchronous hash/custody calls have no heartbeat contract. | Large hash Activities need heartbeat timeout/cancellation and retry-after-commit tests; inputs must use immutable blob refs, never ephemeral local paths. |

## Implementation sequence

1. Define compact immutable Activity contracts and the shared idempotency/receipt envelope.
2. Build the standalone canon-dispatching hash capability and its Temporal Activities first.
3. Build context-only intake/normalization Activities using references instead of record payloads.
4. Build promotion verification plus the atomic promotion-to-custody writer before disabling the old
   ingest-time custody path.
5. Bind n8n triggers, operator decisions, and notifications to Temporal start/signal APIs.
6. Add Semantica extraction, provenance-complete Neo4j projection, and governed fact Activities.
7. Generalize the PG outbox/job/receipt contract across Weaviate, Neo4j, geo, and every specialist
   store; require all result metadata and source validation to return to PG.
8. Add the PG cross-store reconciliation manifest and Surreal projection Activities.
9. Add paired-walk/delta workflows only after fail-closed Surreal horizon retrieval is proven.
10. Retire old paths only after live zero-use proof, reconciliation, export, and owner approval; move
   retired files to `to_be_deleted` and never permanently delete them.

## Non-negotiable tests before activation

- Temporal retry/worker-crash tests prove one durable receipt per idempotency key.
- Planted future facts prove horizon filtering occurs before ranking in every retrieval store.
- Hash vectors cover every active H1/H2/H3 canon tuple and verifier dispatch.
- Promotion mismatch tests prove zero partial custody writes.
- Temporal histories contain references, never source bytes or large record batches.
- n8n retries/re-delivery collapse under the Temporal workflow and Activity idempotency keys.
- Parser substitution produces the same normalized contract and destination regardless of language.
- Surreal projection reconciliation proves exact fact/source counts and hashes before a walk starts.
