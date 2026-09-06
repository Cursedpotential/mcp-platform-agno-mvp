# MCP Platform vs. `edisc (1).md`: Implementation Gap Analysis

> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

**Repository:** [Cursedpotential/mcp-platform-agno-mvp](https://github.com/Cursedpotential/mcp-platform-agno-mvp)  
**Reviewed revision:** [`1e38d3a61d86fe5bd4d94a549b7797380f8faa1c`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/commit/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c) (`main`, 2026-08-18)  
**Comparison guidance:** `edisc (1).md`  
**Review date:** 2026-08-23

## Executive verdict

The repository is **architecturally ahead of the guidance in several important areas**, especially temporal provenance, append-only custody, multi-source attestation, horizon-safe retrieval, durable projection jobs, and governed human review. It is not a greenfield system and should not rebuild those capabilities.

It is nevertheless **not yet a defensible end-to-end eDiscovery/RAG release path** under the guidance's own standard. The central problem is maturity mismatch:

- core evidence primitives are implemented;
- several decisive migrations and product slices are explicitly held or unapplied;
- court-output, OCR, legal/factual citation grounding, statistical validation, and release-gate automation remain partial or absent;
- substantial behavior/factor logic lives in planning migrations and configuration rather than a mandatory, versioned event-to-court-output pipeline.

The highest-risk defect found is a **Michigan-factor label inversion**: the runtime behavioral configuration labels factor `(j)` as domestic violence and factor `(k)` as facilitation, while the descriptions and most category mappings reflect the correct opposite meanings. That can silently mislabel otherwise correct evidence in UI or exports.

## Scope and confidence

This was a static source audit of the current GitHub revision, including production namespaces, SQL migrations, tests, ADRs, the debt register, build plan, and recent handoffs. Repository-reported test results were considered as project evidence, but tests were not independently executed against the live services or database. Deployment state is therefore reported only where the repository itself makes an explicit claim.

Status meanings:

- **Implemented** — production-path code/schema exists with meaningful tests or invariants.
- **Partial** — useful primitives exist, but the guidance's full contract is not met.
- **Planned/Held** — designed or locally built, but expressly unapplied, unactivated, or not wired end to end.
- **Missing** — no implementation was located outside historical, planning, or vendored reference material.

## What should be preserved rather than rebuilt

| Capability | Verdict | Repository evidence |
|---|---|---|
| Append-only raw evidence and derived canonical spine | Implemented | [`sql/0009_raw_layer_and_derivation.sql`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/sql/0009_raw_layer_and_derivation.sql) separates verbatim per-source raw rows from deduplicated normalized records and preserves disagreeing attestations as findings. |
| Multi-clock and acquisition provenance | Implemented in schema; operational completion varies | [`sql/0008_temporal_clocks_and_provenance.sql`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/sql/0008_temporal_clocks_and_provenance.sql) models event, export, acquisition, realization, ingestion, and transaction clocks plus acquisition authority and artifact metadata. |
| Content hashing and custody coordinates | Implemented | [`server/evidence/custody.py`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/evidence/custody.py), [`vendored/sbv/internal/custody.go`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/vendored/sbv/internal/custody.go), and [`sql/0019_reconcile_evidence_hash.sql`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/sql/0019_reconcile_evidence_hash.sql). |
| Provenance-preserving knowledge-to-evidence promotion | Implemented locally; migration held | [`sql/0030_matter_case_foundation.sql`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/sql/0030_matter_case_foundation.sql) binds normalized record, custody hash, source/file/run, exact quote, and an idempotent pointer hash. |
| Native evidence vector projection | Implemented locally | [`server/evidence/vector_projection.py`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/evidence/vector_projection.py) uses a durable PostgreSQL outbox and re-resolves authoritative source availability before projection. |
| Horizon filter before vector ranking | Implemented in native path | [`server/core/evidence_vector_store.py`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/core/evidence_vector_store.py#L346-L398) builds a compound Weaviate allow-list before near-vector/hybrid ranking; [`server/evidence/retrieval.py`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/evidence/retrieval.py) audits each read. |
| As-lived/hindsight delta ledger | Strong implementation, held/applied state must be verified | [`sql/0027_walk_ledger.sql`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/sql/0027_walk_ledger.sql) and [`server/evidence/derivation.py`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/evidence/derivation.py) implement version-pinned, hash-attested walk derivation and contamination detection. |
| Candidate-not-fact extraction discipline | Implemented as a core invariant | [`sql/0010_extraction_candidate_and_acquisition_reconcile.sql`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/sql/0010_extraction_candidate_and_acquisition_reconcile.sql) and [ADR-0057](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/docs/adr/0057-claim-centered-evidence-assembly-and-established-facts.md). |
| Append-only human review history | Implemented locally | The R9 handoff reports append-only review decisions, terminal-state conflict protection, and separation of review from authentication/court-safe release: [`docs/HANDOFF-2026-08-15-R9-knowledge-to-case-mvp.md`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/docs/HANDOFF-2026-08-15-R9-knowledge-to-case-mvp.md). |

## Critical and high-priority gaps

### P0-1 — Michigan factors `(j)` and `(k)` are mislabeled

**Status:** Confirmed defect.

The active behavioral configuration defines:

- `(j)` with the name **Domestic Violence**, but the statutory description for facilitating the other parent-child relationship;
- `(k)` with the name **Willingness to Facilitate Relationship**, but the statutory description for domestic violence.

See [`server/analysis/config/behavioral_patterns.json`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/analysis/config/behavioral_patterns.json#L8-L82). Most category mappings appear to use the letters correctly—gatekeeping maps to `j`, violence/safety maps to `k`—which makes this particularly dangerous: correct internal codes can be rendered with incorrect human labels.

**Impact:** Mischaracterized evidence, incorrect headings, reviewer confusion, and potentially defective court-facing exports.

**Required correction:** Establish a canonical, versioned `reference.mcl_best_interest_factor` table from current official Michigan text; make configuration/UI/export resolve labels from that table rather than duplicating text in JSON. Add a contract test asserting all letters, names, descriptions, and current statutory text hashes.

### P0-2 — The guidance itself omits factor `(i)`

**Status:** Defect in the comparison baseline.

`edisc (1).md` says every event must map to one of twelve factors, but its table lists `(a)`–`(h)`, then `(j)`, `(k)`, `(l)`—only eleven entries. Factor `(i)`, the child's reasonable preference when the court considers the child old enough, is absent.

**Impact:** Blindly implementing the guidance would create an incomplete statutory taxonomy.

**Required correction:** Amend the guidance and any derived schema/prompt. Do not force every event to exactly one factor; support `0..n` factor links plus `unmapped/review_required`, because many facts are irrelevant or legitimately cross-factor.

### P0-3 — No RAG citation-grounding validation system

**Status:** Missing.

The guidance's central proposal—Bucket A/B grounding classification, stratified sampling, `CONFIRMED_GROUNDED` / `HALLUCINATED` / `MISGROUNDED` / `AMBIGUOUS` outcomes, per-stratum elusion rates, thresholds, and release escalation—has no production schema, service, worker, or court-release gate in the repository. Exact searches found no grounding-status vocabulary and no citation-elusion implementation.

The existing project does have strong generic audit and review primitives, but those do not answer the three grounding questions separately: source existence, pinpoint support, and characterization accuracy.

**Required implementation:**

1. Add `analysis.generated_claim`, `analysis.claim_citation`, `analysis.grounding_check`, `analysis.validation_population`, `analysis.validation_sample`, and `analysis.validation_release_gate`.
2. Store exact source span IDs and immutable content hashes, not only URLs or free-text citations.
3. Require deterministic backend verification before a claim may enter the “apparently grounded” pool.
4. Stratify by source type, model/prompt/retriever version, confidence band, and output destination.
5. Block court-facing export until all cited propositions have human disposition, regardless of aggregate sample performance.

### P0-4 — Court release remains explanatory/read-only, not an enforceable release action

**Status:** Partial.

The repository distinguishes actual `analysis.vw_court_export` membership from stricter content, custody, provenance, authentication, confidence, hypothesis, redaction, and sensitivity gates. That is good design. But the build plan explicitly describes the feature as a **read-only court-export/readiness explanation** and says it performs no release mutation: [`docs/BUILD_PLAN.md`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/docs/BUILD_PLAN.md#L40-L52).

Review also deliberately leaves `safe_for_legal_use=false` and `is_authenticated=false`; authentication and release are future gates.

**Impact:** The system can explain why something is or is not ready but cannot yet create a version-pinned, reproducible, signed release package whose contents are frozen.

**Required implementation:** A release transaction that freezes item/version/span hashes, gate results, reviewer identities, redaction transforms, citation checks, factor taxonomy version, export renderer version, and custody manifest; post-release changes create a new package version.

### P0-5 — Held/unapplied migrations prevent an end-to-end production claim

**Status:** Planned/Held.

The build plan says migrations `0026–0029` must not be cut over yet and `0030` is unapplied. Migration `0030` itself starts with “HELD FOR OWNER” and “NOT APPLIED TO ANY DATABASE.” See [`docs/BUILD_PLAN.md`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/docs/BUILD_PLAN.md#L18-L33) and [`sql/0030_matter_case_foundation.sql`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/sql/0030_matter_case_foundation.sql#L1-L11).

**Impact:** Source code contains the intended horizon, walk, grants, and matter/case features, but live behavior cannot be inferred from the repository.

**Required action:** Treat “merged,” “migration applied,” “service deployed,” “projection backfilled,” and “observed end-to-end” as five independent states in a machine-readable deployment ledger.

### P1-1 — Dual-granularity retrieval is incomplete

**Status:** Partial.

The repository has canonical normalized records plus derived chunks, conversation IDs, content hashes, and vector projection metadata. It does **not** implement the guidance's explicit two-representation contract for every event:

- isolated atomic fact embedding;
- context-enriched embedding with a stable `context_thread_id`/parent span linking to the complete surrounding exchange.

No `context_thread_id` or `parent_thread_id` implementation was located. `conversation_id` is useful, but it does not identify the exact context window, its bounds, its derivation version, or whether a result is atomic versus contextual.

**Required implementation:** Add `projection_kind = atomic_fact | contextual_exchange`, `parent_span_id`, `context_start_record_id`, `context_end_record_id`, context-window algorithm/version, and a deterministic context hash. Embed both projections once and link both to the same canonical claim/event.

### P1-2 — Retrieval lacks deviation cutoff and overlap de-duplication

**Status:** Missing in the native evidence search path.

The native store correctly prefilters by matter/case, availability, authority, disclosure tier, and horizon before ranking. It returns a fixed `limit`, but it does not implement:

- the guidance's top-score-relative deviation cutoff;
- parent/child or overlapping-window de-duplication;
- diversity/coverage controls across sources or conversations;
- explicit token-budget packing.

See [`server/core/evidence_vector_store.py#L346-L398`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/core/evidence_vector_store.py#L346-L398).

**Required implementation:** Perform post-ranking evidence assembly that groups by canonical record/claim and source lineage, removes overlapping projections, preserves the highest-quality context, and records every dropped result and reason. Calibrate any 25% rule empirically; do not hard-code the guidance's rough number without evaluation.

### P1-3 — Mandatory event-to-factor tagging is not implemented as a governed event relation

**Status:** Partial.

The repository contains a rich behavioral ontology whose categories carry `mcl_factors`, and [`server/analysis/patterns.py`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/server/analysis/patterns.py) validates factor letters. However:

- factors are attributes of behavior categories, not mandatory, reviewable links from each event/claim to statutory factors;
- some modules are explicitly marked `needs_review`;
- contradiction rules are “UNHOMED” in the live schema;
- the newest ontology migration is documented as not applied;
- there is no per-link rationale, supporting span, confidence, reviewer, statute-version, or supersession record.

**Required implementation:** `analysis.claim_factor_candidate` → governed `analysis.claim_factor_link`, with many-to-many cardinality, rationale/span, extractor and taxonomy versions, review disposition, and no auto-promotion to court-safe status.

### P1-4 — Behavioral synthesis is not yet a calibrated corpus-level measurement system

**Status:** Partial/Planned.

The ontology is unusually extensive and maps many relevant patterns—gatekeeping, triangulation, economic sabotage, substance endangerment, gaslighting subtypes, reactive-abuse framing, and more. But keyword/regex coverage and category counts are not equivalent to the guidance's global synthesis metrics such as cancellation frequency, appointment attendance ratios, or testimony/message contradictions.

The debt register states that classifier quality still needs a human-labeled evaluation, semantic/LLM challenger, and sampled high-confidence audit; timeline extraction remains future work: [`docs/DEBT.md`](https://github.com/Cursedpotential/mcp-platform-agno-mvp/blob/1e38d3a61d86fe5bd4d94a549b7797380f8faa1c/docs/DEBT.md#L138-L146).

**Required implementation:** Versioned measurement definitions, denominators, missing-data rules, source-independence grouping, temporal windows, disconfirming searches, calibration sets, and reproducible result manifests.

### P1-5 — OCR/VLM and forensic metadata capture are not production-ready

**Status:** Partial schema; deferred implementation.

`evidence.artifact_metadata` can store filesystem, embedded, and derived metadata, and the planning corpus references EXIF tooling. But the debt register says OCR/VLM selection remains a benchmark task and multimodal embeddings are unimplemented. Searches located OCR/EXIF/access-time handling mainly in planning documents, not a mandatory acquisition pipeline.

**Missing operational controls:**

- immutable original-image/PDF preservation before OCR;
- recorded OCR engine/model/version and page-level confidence;
- bounding boxes and exact source-page coordinates;
- EXIF/filesystem metadata extraction receipts;
- access-time preservation/verification;
- OCR correction as append-only supersession;
- representative private-corpus benchmark and failure thresholds.

### P1-6 — No EDRM production/load-file exports

**Status:** Missing.

No Opticon `.opt/.log`, Concordance `.dat`, EDRM XML, or equivalent review-platform load-file implementation was located. The current court-readiness surfaces and generic Semantica exporters do not satisfy this requirement.

**Required implementation:** Treat EDRM/load-file export as a distinct target, not the same thing as the judge-facing chronology. Export original/native references, text/OCR, stable document IDs, parent-child relationships, custodians, dates, hashes, confidentiality/sensitivity, and production Bates ranges with a package manifest.

### P1-7 — The courtroom matrix is not a complete export renderer

**Status:** Partial.

The system has evidence items, timelines, court-readiness views, export concepts, and a Workbench. It does not expose a verified renderer for the guidance's requested matrix:

1. date/time;
2. event/category;
3. best-interest factor(s);
4. factual description;
5. direct quote/evidence summary;
6. exhibit/source ID;
7. contradicting claim/testimony;
8. admissibility/authentication witness;
9. full context-thread link.

The absence of explicit `context_thread_id`, exhibit numbering, contradiction linkage, and governed factor links blocks a faithful renderer even if a spreadsheet template were added now.

### P1-8 — Deterministic internal IDs are not the same as stable exhibit IDs

**Status:** Partial.

UUIDs, content hashes, source-record keys, and idempotent pointer hashes are strong internal identity. The guidance also needs human-usable, stable evidence/exhibit identifiers such as `EX-2021-04-TEXT-01`. No implemented exhibit-ID service was located.

**Required implementation:** A separate immutable exhibit/document identity layer with reservation, aliases, Bates/exhibit numbering, supersession/versioning, collision handling, and links to all source attestations. Never derive court numbering from mutable sort order.

### P1-9 — No closed-world generation contract

**Status:** Missing.

The promotion layer can preserve an exact quote and authoritative source pointer, but the generation layer is not constrained so a model may cite only retrieved, addressable spans. No backend parser was located that rejects unknown source/span IDs or unsupported generated propositions.

**Required implementation:** Models receive opaque allowed span IDs; every factual/legal sentence emits structured claim-to-span links; the backend rejects any identifier not in the retrieval manifest and checks that quoted text is byte/normalized-text matched before rendering prose.

### P1-10 — Evaluation corpus and statistical release gates are insufficient

**Status:** Missing/Planned.

The debt register says `evals/cases.py` remains empty and classifier quality needs human-labeled evaluation. Repository tests strongly exercise contracts and failure modes, but unit/integration correctness is not evidence of factual extraction quality, retrieval recall, grounding accuracy, or court-export completeness.

**Required gold sets:** parser fidelity, OCR transcription, timestamp/sender attribution, source-span retrieval, claim extraction, factor mapping, contradiction detection, behavior classification, grounding, redaction, and final package completeness. Each must report confidence intervals and slice-level failures, not only aggregate accuracy.

## Medium-priority gaps

### P2-1 — Guidance batching rules are not represented as a reproducible corpus plan

The system chunks with versioned Chonkie policies and preserves conversation structure, which is preferable to an arbitrary 50–100-page rule. But there is no first-class corpus batch manifest encoding chronological month/quarter windows, page/message bounds, overlap, source completeness, and rerun identity. Add a batch-planning layer without replacing content-aware chunking.

### P2-2 — Legal verification status is not generalized to factual claims

The guidance correctly recommends extending the vLex-style legal status vocabulary to evidence-derived claims. The repository has generic review states and source pointers but no normalized factual-verification vocabulary equivalent to `VERIFIED_PRIMARY`, `CONFLICTED`, `STALE`, `SUPERSEDED`, and `ATTORNEY_REVIEW` with precise semantics. Create separate dimensions for source authenticity, factual support, legal currency, characterization, and release eligibility rather than one overloaded status.

### P2-3 — Revalidation after model/retriever/prompt change is not an automated gate

Projection metadata records chunker, embed model, embedder version, projection version, and hashes—excellent prerequisites. There is no automated dependency graph that invalidates prior grounding/evaluation approval when any relevant version changes. Add a release-policy engine that computes affected populations and requires fresh evaluation before activation.

### P2-4 — Backup and disaster-recovery evidence is incomplete

The debt register says recurring PostgreSQL/Neo4j-to-R2 backups remain planned. A defensible system also needs restore drills, hash verification, retention policy, immutable/offline copies, key-recovery procedures, and an evidence that backups restore the custody/audit history—not merely service availability.

### P2-5 — Fresh-schema reproducibility remains open

The debt register reports that the migration chain historically did not build from zero without a captured bootstrap, and the baseline still needs deterministic extension ordering, an explicit included-migration manifest, and an empty-database regression test. This directly affects the ability to reproduce a challenged analysis environment.

### P2-6 — NSRL/de-NISTing is absent and should be scope-gated

No NSRL/de-NIST implementation was located. For this custody corpus, de-NISTing may have little value for chat exports and could create unnecessary complexity. Implement it only for disk-image or broad filesystem acquisitions, record the NSRL release/version, and never delete filtered items—classify them as excluded with reversible manifests.

### P2-7 — Source existence, pinpoint support, and characterization are not separate review decisions

The repository's review model is substantial, but the guidance correctly identifies three independent citation questions. Make them separate fields/outcomes so a real source with a wrong pinpoint is not collapsed into the same state as a fabricated source, and a correctly quoted passage with an overstated conclusion is not marked grounded.

### P2-8 — Deployment truth is distributed across prose

The repository is admirably explicit about “built,” “held,” and “not deployed,” but those truths are distributed across handoffs, debt, build plans, and migration comments. Generate a machine-readable capability register with fields for code SHA, schema version, applied environment, projection/backfill state, last observed proof, test artifact, owner gate, and court-use eligibility.

## Requirement crosswalk

| Guidance requirement | Current state | Gap severity | Recommended owner |
|---|---|---:|---|
| Original-byte custody and hashing | Strong | Low | Evidence platform |
| Filesystem/EXIF preservation | Schema/planning only | High | Acquisition/OCR |
| NSRL/de-NIST | Absent | Medium, scope-dependent | Acquisition |
| Bitemporal/knowledge-horizon spine | Strong code; cutover state held | Critical operational | Data platform |
| Dual atomic + contextual embeddings | Partial | High | Retrieval |
| Pre-ranking horizon filter | Strong in native path | Low | Retrieval/security |
| Relative-score cutoff | Absent | Medium | Retrieval/evaluation |
| Overlap/parent-child dedupe | Absent | High | Retrieval |
| Candidate-not-fact extraction | Strong | Low | Analysis |
| Corpus-level pattern metrics | Partial | High | Analysis/evaluation |
| All Michigan factors, correctly labeled | Defective labels; baseline omits `(i)` | Critical | Legal schema |
| Per-event factor mapping | Not governed end to end | High | Legal schema/review |
| Closed-world citations | Absent | Critical | RAG platform |
| Grounding outcome schema | Absent | Critical | RAG/evaluation |
| Stratified elusion sampling | Absent | Critical | Evaluation |
| Human check of every court citation | Not enforced by release action | Critical | Review/release |
| Court chronology matrix | Partial concepts, no complete renderer | High | Export |
| EDRM/load files | Absent | High | Export/eDiscovery |
| Stable exhibit IDs | Partial internal identity only | High | Export/case management |
| Revalidate after pipeline changes | Metadata exists; gate absent | High | Release engineering |

## Recommended implementation sequence

### Gate 0 — Correct semantic truth before processing more case evidence

1. Fix the `(j)`/`(k)` name inversion and add factor `(i)` to the guidance-derived specification.
2. Establish one canonical official-text factor table and eliminate duplicated human labels.
3. Add regression tests for factor IDs, descriptions, display labels, and common behavior mappings.

### Gate 1 — Establish deployable database truth

1. Resolve the owner holds on `0026–0030` in their prescribed order.
2. Prove fresh-schema construction and rollback from an empty database.
3. Apply to a non-production rehearsal environment, backfill projections, and run planted-future-fact contamination tests.
4. Publish a machine-readable capability/deployment ledger.

### Gate 2 — Make every generated claim addressable and checkable

1. Add canonical span IDs for message, page, paragraph, image region, transcript interval, and context window.
2. Implement atomic and contextual projections with deterministic parent-span links.
3. Require structured claim-to-span output and reject citations outside the retrieval manifest.
4. Separate existence, pinpoint, and characterization checks.

### Gate 3 — Build measured validation

1. Populate human-labeled gold sets across ingestion, extraction, retrieval, factors, behavior, grounding, and export.
2. Implement stratified sampling and confidence intervals.
3. Calibrate retrieval cutoff/dedupe policies rather than adopting an untested 25% heuristic.
4. Invalidate approvals automatically when dependent versions change.

### Gate 4 — Complete acquisition and production outputs

1. Implement OCR/EXIF/filesystem receipts with immutable originals and append-only corrections.
2. Add stable exhibit/document IDs and production numbering.
3. Build the nine-field courtroom chronology renderer.
4. Build EDRM/Opticon/Concordance export separately, with package-level manifests.

### Gate 5 — Enforce court-safe release

1. Freeze a versioned release package in one transaction.
2. Require authentication, provenance, redaction, sensitivity, factor review, and per-claim citation grounding.
3. Require human review of every court-facing citation even when sampled elusion is within threshold.
4. Verify the rendered output against the frozen manifest, then hash and sign the package.

## Acceptance criteria for “guidance-complete”

The project should not claim compliance with `edisc (1).md` until one representative matter can demonstrate all of the following in a clean rehearsal environment:

1. Acquire an original export and scanned document without changing the preserved original.
2. Produce custody, acquisition, filesystem/embedded metadata, parser, OCR, and transformation receipts.
3. Rebuild canonical records and both projection granularities deterministically from original bytes.
4. Run an as-lived walk and hindsight query with planted future facts proving zero horizon leakage.
5. Retrieve and deduplicate exact supporting and contradicting spans with full context.
6. Map candidate claims to correctly labeled statutory factors through governed review.
7. Generate a claim only from allowed span IDs and reject a planted unknown citation.
8. Run stratified grounding validation and record existence/pinpoint/characterization outcomes.
9. Render the complete courtroom matrix and an EDRM/load-file package from the same frozen source set.
10. Freeze, hash, and reproduce a court-release package after a clean restore.

## Bottom line

The correct strategy is **not** to replace the repository's evidence spine with the simpler pipeline described in the guidance. The repository already has a more sophisticated temporal and provenance core. The work is to close the last-mile defensibility gaps: correct the statutory taxonomy, turn held code into observed deployment, add addressable dual-granularity spans, implement grounding statistics and closed-world citations, finish OCR/metadata acquisition, and create immutable court/EDRM release packages.

Until those gates are complete, the platform is best characterized as a **strong forensic and temporal evidence foundation with a locally advanced evidence desk—not yet a statistically validated, court-release-complete eDiscovery/RAG system**.
