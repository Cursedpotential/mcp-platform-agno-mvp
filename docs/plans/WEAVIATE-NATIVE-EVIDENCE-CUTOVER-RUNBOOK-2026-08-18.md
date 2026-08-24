# HELD runbook — native Weaviate evidence-vector cutover

> _Byline: Codex · GPT-5 · 2026-08-18._
> _Byline amendment: Codex · GPT-5 · 2026-08-18 (side-by-side blue full-instance migration)._
>
> **Status:** the full legacy/custom instance clone to blue has executed under owner authority;
> independent target attestation and application cutover remain gated. Native `EvidenceChunkV1`
> is still held behind PostgreSQL migrations `0026`–`0029` and its separate evidence canaries.

## Actual side-by-side Coolify topology and legacy clone

- Preserved source: `http://100.91.190.107:8081`, gRPC `50051`.
- New blue target: `http://100.91.190.107:8082`, gRPC `50052`.
- The application still points at the preserved source. No alias or endpoint cutover has occurred.
- Two independent hot source inventories matched all seven schemas and 3,035 semantic objects.
- Create-only replay copied all seven source collections to blue: `Evidence_knowledge` 0,
  `Legal_knowledge` 30, `Personal_history_knowledge` 1, `Platform_code_knowledge` 0,
  `Platform_context` 2,790, `Platform_knowledge` 213, and
  `Relationship_timeline_knowledge` 1. Source inventory recorded 2,978 vector-bearing objects,
  57 intentionally vectorless objects, zero cross-references, zero tenants, and no aliases.
- `scripts/migrate_weaviate_instance.py` owns complete schema/alias/tenant/object/vector/reference
  export, create-only two-pass replay, and independent semantic target verification. Multi-tenant
  collections are enumerated tenant-by-tenant and replay tenant definitions before objects.
- Do not change `WEAVIATE_HTTP_PORT` to `8082`, stop `8081`, or create the native evidence alias
  until target manifest parity and application read/write canaries pass. Preserve both instances.
- Independent blue export reconciled every semantic manifest field with SHA-256
  `a16781f745e03cf715b5807a9f7103e2a99dd05bdd4a1e2d1f25ddc8f949ead6`.
  A real Python v4 near-vector + hybrid query against `Platform_context` returned the identical
  self-hit on source and blue; hybrid top-five membership/order matched exactly, while near-vector
  top-five membership matched with a benign tie-order swap below rank one.

## Target and invariants

- PostgreSQL remains the authored evidence spine. Weaviate is a rebuildable projection only.
- The immutable target is `EvidenceChunkV1`; the stable reader alias is `EvidenceChunks`.
- The retired Agno evidence collection is preserved intact throughout cutover and rollback.
- `source_available_from` is a typed Weaviate `DATE` with range filtering. The companion epoch
  field is typed `INT`. Every search applies the complete case/source/horizon predicate before
  vector or hybrid ranking. `realized_at` is not an evidence-chunk visibility field.
- Vectors remain self-provided `nvidia/nv-embed-v1`, 4096 dimensions. A different schema,
  embedder, dimension, or projection contract requires `EvidenceChunkV2`, never an in-place V1
  mutation.
- Weaviate must be at least 1.26 for the native contract. The operator alias step additionally
  requires a server release that supports collection aliases (1.32 or later); the checkout pins
  1.38.7. Verify the running server rather than assuming the deployment file was applied.

## Release gates

1. Obtain explicit owner approval for migrations `0026`–`0029`, the native collection create,
   the production backfill, and the alias/read-path switch. An approval for one gate does not
   imply approval for the others.
2. Archive the static preflight JSON and require every non-git check to pass. Static mode reads
   the checkout only and must not contact Weaviate:

   ```powershell
   uv run python scripts/_matter_activation_preflight.py --scope static --json
   ```

3. Apply and attest `0026`, `0027`, `0028`, then `0029` only after approval. Stop if the state is
   partial. Do not start the backfill until `working.normalized_record_chunk`, the authoritative
   source-availability function/materialization, and projection permissions reconcile.
4. Take and verify PostgreSQL and Weaviate backups using the checked-in typed logical backup and
   complete-instance migration utilities. Record service version, schema, old collection name,
   object/vector/reference/tenant counts, and backup receipt.

## Build the inactive target

1. Query the running `/v1/meta` and record its exact version. Fail below 1.26; fail below 1.32 if
   the alias operation is planned.
2. Create `EvidenceChunkV1` through `ensure_evidence_vector_collection`. It uses self-provided
   vectors and must be absent or match the checked-in V1 contract exactly. Never repair a
   mismatched V1 in place.
3. Keep all readers on the old Agno collection. Do not create or move `EvidenceChunks` yet.
4. Freeze a PostgreSQL backfill watermark and projection version. Read approved rows from
   `working.normalized_record_chunk` joined to the canonical normalized record, approved
   source-class projection, and authoritative `working.source_available_from(record_id)` result.
   Reject any row with a missing source boundary, source identity, content hash, projection hash,
   embedder identity/dimension, or custody-backed third-party acquisition boundary.
5. Upsert deterministically by stable `chunk_id`. Supply the stored/recomputed 4096-d vector;
   Weaviate must not vectorize content. Record batch start/end keys, counts, failures, and the
   PostgreSQL watermark so the backfill is resumable and repeatable.
6. Re-run from the same watermark until the pending set is empty. A changed source row produces a
   new projection receipt; it is not silently folded into the frozen reconciliation set.

## Exact reconciliation

Build two independently generated, ordinally sorted manifests—one from the frozen PostgreSQL
source and one by scanning `EvidenceChunkV1`. Each row must contain at least:

```text
chunk_id | artifact_id | source_sha256 | case_id | source_kind | projection_kind |
authority_state | source_availability_complete | source_available_from UTC |
normalized_record_id | conversation_id | chunker_id | embed_model | embed_dimension |
embedder_version | projection_version | projection_hash | content_hash |
source_content_hash
```

Canonicalize timestamps to UTC RFC 3339 and hash the UTF-8 manifest with SHA-256. Activation is
blocked unless all of the following are exact:

- PostgreSQL eligible count = attempted-success count = Weaviate object count;
- no duplicate or missing `chunk_id`, no extra Weaviate object, and identical ordered membership;
- PostgreSQL manifest SHA-256 = Weaviate manifest SHA-256;
- every vector is present and dimension 4096; embedder/version fields match the frozen receipt;
- first-party canary: visible at occurrence and excluded immediately before it;
- acquired-third-party canary: excluded after occurrence but before acquisition, included at
  acquisition, and the owner is not fabricated as sender/recipient/participant;
- planted-future-fact canary: excluded at the ignorant horizon and included at hindsight;
- cross-case and disallowed-tier canaries return zero leakage;
- near-vector and hybrid searches return the requested `k` from the eligible set, proving the
  predicate ran before ranking rather than after top-k.

Archive counts, both manifests and hashes, canary query inputs/results, server/schema versions,
and the PostgreSQL watermark as the cutover receipt. Any mismatch aborts; do not switch readers.

## Operator alias switch

1. Stop projection writes briefly or drain the outbox to a recorded cursor. Replay the delta into
   `EvidenceChunkV1` and repeat exact count/hash/canary reconciliation.
2. Create or atomically repoint the `EvidenceChunks` alias to `EvidenceChunkV1` using the native
   Weaviate alias API. This is an explicit operator action; application startup must never move it.
3. Read the alias metadata back and prove its target. Run the complete canary suite through the
   alias, then bind only the evidence-vector reader to `EvidenceChunks` under a separately approved
   deploy. Platform/legal/personal Agno knowledge collections are outside this cutover.
4. Preserve the prior Agno evidence collection, its schema receipt, and its reader configuration.
   Do not delete, rename, compact, or backfill over it during the observation window.

## Rollback

If any integrity, latency, authorization, or horizon check fails, stop new native projection
writes, return the evidence reader to the recorded old Agno collection/configuration, and verify
the old canaries. Preserve `EvidenceChunkV1`, both receipts, and failure evidence for diagnosis;
do not delete either collection. A failed cutover does not authorize reverting PostgreSQL history
or resuming a terminally contaminated walk. Record the rollback decision and start a new governed
cutover attempt after repair and fresh reconciliation.
